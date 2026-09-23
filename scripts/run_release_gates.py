"""Run the DOCOPS release gates sequentially in isolated stage workspaces.

The runner is deliberately an orchestration seam, not a second implementation
of the gates.  Each stage delegates to an existing public CLI, checker or
pytest command, records the exact command and a redacted diagnostic, and stops
on the first required failure.  RAG stages are optional only when the caller
explicitly allows the documented skip.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import locale
import math
import os
import platform
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ISOLATION = "unique-temporary-workspace"
PYTEST_COUNT_RE = re.compile(r"(?P<count>\d+)\s+(?P<label>passed|failed|skipped|xfailed|xpassed|error|errors)")
PYTEST_DURATION_RE = re.compile(r"in\s+(?P<seconds>[0-9]+(?:\.[0-9]+)?)s")
DEFAULT_PIPELINE_TIMEOUT_SECONDS = 7200.0


@dataclass(frozen=True)
class GateStage:
    """A serial gate with one private workspace and one or more commands."""

    name: str
    commands: tuple[tuple[str, ...], ...]
    artifacts: tuple[str, ...]
    required: bool = True
    requires_rag: bool = False
    environment: dict[str, str] = field(default_factory=dict)


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _display(value: str | Path, root: Path, output: Path | None = None) -> str:
    text = str(value)
    for original, replacement in ((str(root), "<root>"), (str(output) if output else "", "<artifacts>")):
        if original:
            text = text.replace(original, replacement)
    return text


def _command_display(command: Iterable[str], root: Path, output: Path | None) -> list[str]:
    return [_display(value, root, output) for value in command]


def _safe_tail(value: str, root: Path, output: Path | None) -> str:
    # Logs are evidence, but they must not turn a gate report into a corpus or
    # machine-layout export.  The underlying gate remains responsible for its
    # own content redaction; this layer removes known local path identifiers.
    redacted = _display(value, root, output)
    return redacted[-4000:]


def _counts(text: str) -> dict[str, int | float]:
    result: dict[str, int | float] = {}
    for match in PYTEST_COUNT_RE.finditer(text):
        label = match.group("label")
        if label == "errors":
            label = "error"
        result[label] = int(match.group("count"))
    duration = PYTEST_DURATION_RE.search(text)
    if duration:
        result["duration_seconds"] = float(duration.group("seconds"))
    return result


def _platform_report(python: Path) -> dict[str, Any]:
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "python_executable": str(python),
        "shells": {name: shutil.which(name) is not None for name in ("sh", "bash", "pwsh")},
        "symlink_capability": _probe_symlink_capability(),
    }


def _probe_symlink_capability() -> bool:
    try:
        with tempfile.TemporaryDirectory(prefix="docops-gate-symlink-") as temporary:
            root = Path(temporary)
            target = root / "target"
            link = root / "link"
            target.write_text("x", encoding="utf-8")
            link.symlink_to(target)
            return link.is_symlink() and link.read_text(encoding="utf-8") == "x"
    except (OSError, NotImplementedError):
        return False


def _version_report(python: Path) -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "python_executable": str(python),
        "runner": "run_release_gates/1",
    }


def _source_report(root: Path) -> dict[str, Any]:
    def git_value(*arguments: str) -> str | None:
        try:
            completed = subprocess.run(
                ["git", "-C", str(root), *arguments],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if completed.returncode:
            return None
        value = completed.stdout.strip()
        return value or None

    status = git_value("status", "--porcelain=v1", "--untracked-files=all")
    return {
        "commit": git_value("rev-parse", "--verify", "HEAD"),
        "branch": git_value("branch", "--show-current"),
        "worktree_entries": len(status.splitlines()) if status else 0,
        "binding": "checkout identity captured before gate execution",
    }


def _script(root: Path, name: str) -> str:
    return str(root / "scripts" / name)


def _artifact_path(stage_root: Path, name: str) -> str:
    return str(stage_root / name)


def _stage(
    name: str,
    root: Path,
    python: Path,
    stage_root: Path,
    commands: Iterable[Iterable[str]],
    *,
    artifacts: Iterable[str] = (),
    required: bool = True,
    requires_rag: bool = False,
    environment: dict[str, str] | None = None,
) -> GateStage:
    command_values = tuple(tuple(str(item) for item in command) for command in commands)
    artifact_values = tuple(str(Path(stage_root) / item) for item in artifacts)
    if not artifact_values:
        artifact_values = (_artifact_path(stage_root, "stage-report.json"),)
    return GateStage(
        name=name,
        commands=command_values,
        artifacts=artifact_values,
        required=required,
        requires_rag=requires_rag,
        environment=dict(environment or {}),
    )


def build_gate_plan(root: Path, python: Path, output: Path, profile: str) -> list[GateStage]:
    """Build the public, ordered gate plan without executing any command."""

    stage_root = output / "stages"
    py = str(python)
    root = root.expanduser().resolve()
    # Keep child Python's stdout encoding aligned with the host locale.  Forcing
    # UTF-8 here breaks existing subprocess seams on Windows: their parent
    # decodes text with the locale encoding, while Python would emit UTF-8.
    # The runner itself decodes and writes evidence explicitly below.
    common_env = {
        "PYTHONNOUSERSITE": "1",
        "DOCOPS_RAGFLOW_INTEGRATION": "0",
        "DOCOPS_OCR_INTEGRATION": "0",
    }
    clean_clone_command = [
        py,
        _script(root, "verify_clean_clone.py"),
        "--source",
        str(root),
        "--python",
        py,
        "--bootstrap",
    ]
    stages = [
        _stage(
            "platform-info",
            root,
            python,
            stage_root / "01-platform-info",
            ((py, "--version"),),
            artifacts=("platform.json",),
            environment=common_env,
        ),
        _stage(
            "supply-chain-no-pip",
            root,
            python,
            stage_root / "02-supply-chain-no-pip",
            (
                (
                    py,
                    "-m",
                    "pytest",
                    "-q",
                    "tests/test_candidate_identity.py::test_candidate_falls_back_when_bootstrap_no_install_leaves_a_venv_without_pip",
                ),
            ),
            artifacts=("pytest.log",),
            environment=common_env,
        ),
        _stage(
            "doctor",
            root,
            python,
            stage_root / "03-doctor",
            ((py, "-m", "docops", "doctor", "--root", str(root), "--json"),),
            artifacts=("doctor.json",),
            environment={**common_env, "DOCOPS_SKIP_RAG": "1"},
        ),
        _stage(
            "support-matrix",
            root,
            python,
            stage_root / "04-support-matrix",
            ((py, _script(root, "check_support_matrix.py"), "--json"),),
            artifacts=("support-matrix.json",),
            environment=common_env,
        ),
        _stage(
            "contracts",
            root,
            python,
            stage_root / "05-contracts",
            ((py, _script(root, "check_contracts.py"), "--json"),),
            artifacts=("contracts.json",),
            environment=common_env,
        ),
        _stage(
            "documentation",
            root,
            python,
            stage_root / "06-documentation",
            ((py, _script(root, "check_documentation.py"), "--root", str(root), "--json"),),
            artifacts=("documentation.json",),
            environment=common_env,
        ),
        _stage(
            "master-evolution-fixture",
            root,
            python,
            stage_root / "07-master-evolution-fixture",
            (
                (
                    py,
                    _script(root, "run_master_evolution_fixture.py"),
                ),
            ),
            artifacts=("master-evolution.json",),
            environment=common_env,
        ),
        _stage(
            "farol-v2-provider-free-fixture",
            root,
            python,
            stage_root / "08-farol-v2-fixture",
            (
                (
                    py,
                    _script(root, "run_farol_v2_fixture.py"),
                    "--output",
                    str(stage_root / "08-farol-v2-fixture" / "package"),
                ),
            ),
            artifacts=("fixture.log",),
            environment=common_env,
        ),
        _stage(
            "public-seams",
            root,
            python,
            stage_root / "09-public-seams",
            ((py, _script(root, "check_public_seams.py"), "--tests", str(root / "tests"), "--json"),),
            artifacts=("public-seams.json",),
            environment=common_env,
        ),
        _stage(
            "security",
            root,
            python,
            stage_root / "10-security",
            (
                (
                    py,
                    "-m",
                    "pytest",
                    "-q",
                    "tests/test_release_audit.py",
                    "tests/test_source_registry.py",
                    "tests/test_learning.py",
                    "tests/test_usage_feedback.py",
                ),
            ),
            artifacts=("pytest.log",),
            environment=common_env,
        ),
        _stage(
            "dependency-audit",
            root,
            python,
            stage_root / "11-dependency-audit",
            (
                (
                    py,
                    _script(root, "audit_dependencies.py"),
                    "--requirements",
                    str(root / "requirements.lock"),
                    "--local",
                    "--strict",
                    "--evidence-dir",
                    str(stage_root / "11-dependency-audit" / "evidence"),
                ),
            ),
            artifacts=("evidence", "evidence/summary.json"),
            environment=common_env,
        ),
        _stage(
            "pip-check",
            root,
            python,
            stage_root / "12-pip-check",
            ((py, "-m", "pip", "check"),),
            artifacts=("pip-check.log",),
            environment=common_env,
        ),
        _stage(
            "workflow-yaml",
            root,
            python,
            stage_root / "13-workflow-yaml",
            (
                (
                    py,
                    _script(root, "validate_workflows.py"),
                    "--workflows",
                    str(root / ".github" / "workflows"),
                    "--json",
                ),
            ),
            artifacts=("workflows.json",),
            environment=common_env,
        ),
        _stage(
            "pytest",
            root,
            python,
            stage_root / "14-pytest",
            ((py, "-m", "pytest", "-q"),),
            artifacts=("pytest.log",),
            environment=common_env,
        ),
        _stage(
            "ruff",
            root,
            python,
            stage_root / "15-ruff",
            ((py, "-m", "ruff", "check", "docops", "tests", "scripts"),),
            artifacts=("ruff.log",),
            environment=common_env,
        ),
        _stage(
            "format",
            root,
            python,
            stage_root / "16-format",
            ((py, "-m", "ruff", "format", "--check", "docops", "tests", "scripts"),),
            artifacts=("format.log",),
            environment=common_env,
        ),
        _stage(
            "compileall",
            root,
            python,
            stage_root / "17-compileall",
            ((py, "-m", "compileall", "-q", "docops", "tests", "scripts"),),
            artifacts=("compileall.log",),
            environment=common_env,
        ),
        _stage(
            "diff-check",
            root,
            python,
            stage_root / "18-diff-check",
            (("git", "-C", str(root), "diff", "--check"),),
            artifacts=("diff-check.log",),
            environment=common_env,
        ),
        _stage(
            "clean-clone",
            root,
            python,
            stage_root / "19-clean-clone",
            (tuple(clean_clone_command),),
            artifacts=("clean-clone.json",),
            environment=common_env,
        ),
        _stage(
            "wheel-core",
            root,
            python,
            stage_root / "20-wheel-core",
            ((py, _script(root, "verify_wheel.py"), "--core"),),
            artifacts=("wheel-core.json",),
            environment=common_env,
        ),
        _stage(
            "crash-matrix",
            root,
            python,
            stage_root / "21-crash-matrix",
            (
                (
                    py,
                    "-m",
                    "pytest",
                    "-q",
                    "tests/test_history_rollback.py",
                    "tests/test_promotion_recovery.py",
                    "tests/test_worker.py",
                ),
            ),
            artifacts=("pytest.log",),
            environment=common_env,
        ),
        _stage(
            "revocation",
            root,
            python,
            stage_root / "22-revocation",
            (
                (
                    py,
                    "-m",
                    "pytest",
                    "-q",
                    "tests/test_reader_sessions.py",
                    "tests/test_learning.py",
                    "tests/test_candidate_publication.py",
                ),
            ),
            artifacts=("pytest.log",),
            environment=common_env,
        ),
    ]
    if profile in {"full", "book-to-skill"}:
        stages.append(
            _stage(
                "book-to-skill-contract",
                root,
                python,
                stage_root / "23-book-to-skill-contract",
                ((py, _script(root, "run_book_to_skill_profile.py"), "--json"),),
                artifacts=("book-to-skill-report.json",),
                environment=common_env,
            )
        )
    if profile in {"full", "ragflow"}:
        stages.extend(
            [
                _stage(
                    "ragflow-contract",
                    root,
                    python,
                    stage_root / "24-ragflow-contract",
                    ((py, _script(root, "run_ragflow_profile.py"), "--json"),),
                    artifacts=("ragflow-report.json",),
                    environment={**common_env, "DOCOPS_RAGFLOW_INTEGRATION": "1"},
                ),
                _stage(
                    "ocr-contract",
                    root,
                    python,
                    stage_root / "25-ocr-contract",
                    ((py, _script(root, "run_ocr_profile.py"), "--json"),),
                    artifacts=("ocr-report.json",),
                    environment={**common_env, "DOCOPS_OCR_INTEGRATION": "1"},
                ),
            ]
        )
    return stages


def _initial_report(root: Path, python: Path, output: Path, profile: str, execution: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": execution == "plan",
        "execution": execution,
        "profile": profile,
        "root": _display(root, root, output),
        "artifacts_root": _display(output, root, output),
        "platform": _platform_report(python),
        "versions": _version_report(python),
        "source": _source_report(root),
        "denominators": {"stages": 0, "passed": 0, "failed": 0, "blocked": 0, "skipped": 0, "not_run": 0},
        "skip_policy": {
            "allowed": False,
            "observable": "status=skipped with an explicit reason; a required skip is never green",
        },
        "isolation": {
            "mode": "serial",
            "workspace_policy": ISOLATION,
            "build_directories_shared": False,
        },
        "stages": [],
    }


def _plan_payload(stages: list[GateStage], root: Path, output: Path) -> list[dict[str, Any]]:
    planned: list[dict[str, Any]] = []
    for order, stage in enumerate(stages, start=1):
        planned.append(
            {
                "order": order,
                "name": stage.name,
                "status": "planned",
                "required": stage.required,
                "requires_rag": stage.requires_rag,
                "isolation": ISOLATION,
                "workspace": _display(Path(stage.artifacts[0]).parent, root, output),
                "commands": [_command_display(command, root, output) for command in stage.commands],
                "artifacts": [_display(path, root, output) for path in stage.artifacts],
            }
        )
    return planned


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _stage_record(
    stage: GateStage,
    order: int,
    *,
    root: Path,
    output: Path,
    status: str,
    reason: str | None = None,
) -> dict[str, Any]:
    return {
        "order": order,
        "name": stage.name,
        "status": _canonical_status(status) or status,
        "required": stage.required,
        "requires_rag": stage.requires_rag,
        "isolation": ISOLATION,
        "workspace": _display(Path(stage.artifacts[0]).parent, root, output),
        "commands": [_command_display(command, root, output) for command in stage.commands],
        "artifacts": [_display(path, root, output) for path in stage.artifacts],
        "reason": reason,
    }


def _last_json_line(text: str) -> str | None:
    """Return the last complete JSON line from a command capture, if any."""

    for line in reversed(text.splitlines()):
        candidate = line.strip()
        if not candidate:
            continue
        try:
            json.loads(candidate)
        except json.JSONDecodeError:
            continue
        return candidate
    return None


def _last_json_payload(text: str) -> dict[str, Any] | None:
    raw = _last_json_line(text)
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _canonical_status(status: Any) -> str | None:
    if not isinstance(status, str):
        return None
    normalized = status.strip().casefold().replace("-", "_")
    return normalized if normalized in {"passed", "failed", "blocked", "skipped", "not_run"} else None


def _command_status(command_result: dict[str, Any]) -> tuple[str | None, str | None]:
    """Extract an explicit blocked/not-run result without masking real failures."""

    output = "\n".join(str(command_result.get(key, "")) for key in ("stdout_tail", "stderr_tail"))
    payload = _last_json_payload(output)
    if payload is not None:
        status = _canonical_status(payload.get("status"))
        if status in {"blocked", "not_run", "failed"}:
            reason = payload.get("reason") or payload.get("code")
            return status, str(reason) if reason else None

    counts = command_result.get("denominators")
    if (
        command_result.get("returncode") == 0
        and isinstance(counts, dict)
        and int(counts.get("passed", 0) or 0) == 0
        and int(counts.get("skipped", 0) or 0) > 0
        and int(counts.get("failed", 0) or 0) == 0
        and int(counts.get("error", 0) or 0) == 0
        and int(counts.get("xpassed", 0) or 0) == 0
    ):
        return "not_run", "command completed with skips and no executed tests"
    return None, None


def _materialize_declared_artifacts(stage: GateStage, command_results: list[dict[str, Any]]) -> None:
    """Ensure every declared capture artifact is a real, bounded file or directory."""

    stdout = str(command_results[-1].get("stdout_tail", "")) if command_results else ""
    stderr = str(command_results[-1].get("stderr_tail", "")) if command_results else ""
    for raw_path in stage.artifacts:
        path = Path(raw_path)
        if path.exists():
            continue
        if path.name == "stage-report.json":
            continue
        try:
            if path.suffix.casefold() == ".json":
                payload = _last_json_line(stdout)
                if payload is None:
                    payload = json.dumps(
                        {
                            "schema_version": 1,
                            "stage": stage.name,
                            "stdout_tail": stdout,
                            "stderr_tail": stderr,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(payload.rstrip() + "\n", encoding="utf-8")
            elif path.suffix:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(stdout + ("\n" + stderr if stderr else ""), encoding="utf-8")
            else:
                path.mkdir(parents=True, exist_ok=True)
        except OSError:
            # The command result and stage report remain authoritative when an
            # optional capture path cannot be materialized by the host.
            continue


def _run_stage(
    stage: GateStage,
    order: int,
    *,
    root: Path,
    output: Path,
    python: Path,
    timeout: int,
    deadline: float | None = None,
) -> dict[str, Any]:
    stage_dir = Path(stage.artifacts[0]).parent
    stage_dir.mkdir(parents=True, exist_ok=True)
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.casefold() not in {"pythonpath", "pythonhome", "pythonioencoding", "pythonutf8"}
    }
    environment["PYTHONPATH"] = os.pathsep.join(
        str(value) for value in (root, os.environ.get("PYTHONPATH", "")) if value
    )
    environment.update(stage.environment)
    started = time.monotonic()
    started_at = _utc_now()
    record = _stage_record(stage, order, root=root, output=output, status="running")
    command_results: list[dict[str, Any]] = []
    stage_status = "passed"
    stage_reason: str | None = None
    for command_index, command in enumerate(stage.commands, start=1):
        command_timeout: float = float(timeout)
        deadline_limited = False
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                stage_status = "failed"
                stage_reason = "pipeline_timeout"
                command_results.append(
                    {
                        "index": command_index,
                        "command": _command_display(command, root, output),
                        "returncode": None,
                        "error": "release gate pipeline deadline expired before command start",
                        "denominators": {},
                    }
                )
                break
            command_timeout = min(command_timeout, remaining)
            deadline_limited = command_timeout < float(timeout)
        try:
            completed = subprocess.run(
                list(command),
                cwd=root,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
                encoding=locale.getpreferredencoding(False),
                errors="replace",
                timeout=command_timeout,
            )
            result = {
                "index": command_index,
                "command": _command_display(command, root, output),
                "returncode": completed.returncode,
                "stdout_tail": _safe_tail(completed.stdout, root, output),
                "stderr_tail": _safe_tail(completed.stderr, root, output),
                "denominators": _counts(completed.stdout + "\n" + completed.stderr),
            }
            command_results.append(result)
            (stage_dir / f"command-{command_index:02d}-stdout.log").write_text(result["stdout_tail"], encoding="utf-8")
            (stage_dir / f"command-{command_index:02d}-stderr.log").write_text(result["stderr_tail"], encoding="utf-8")
            command_status, command_reason = _command_status(result)
            if command_status is not None and command_status != "passed":
                stage_status = command_status
                stage_reason = command_reason
                break
            if completed.returncode:
                stage_status = "failed"
                break
        except subprocess.TimeoutExpired as exc:
            stage_status = "failed"
            stage_reason = (
                "pipeline_timeout"
                if deadline_limited or (deadline is not None and time.monotonic() >= deadline)
                else "command_timeout"
            )
            command_results.append(
                {
                    "index": command_index,
                    "command": _command_display(command, root, output),
                    "returncode": None,
                    "error": f"release gate command timed out ({stage_reason})",
                    "stdout_tail": _safe_tail(str(exc.stdout or ""), root, output),
                    "stderr_tail": _safe_tail(str(exc.stderr or ""), root, output),
                    "denominators": {},
                }
            )
            break
        except (OSError, subprocess.SubprocessError) as exc:
            stage_status = "failed"
            command_results.append(
                {
                    "index": command_index,
                    "command": _command_display(command, root, output),
                    "returncode": None,
                    "error": str(exc),
                    "denominators": {},
                }
            )
            break
    finished = time.monotonic()
    _materialize_declared_artifacts(stage, command_results)
    record.update(
        {
            "status": stage_status,
            "started_at": started_at,
            "duration_seconds": round(finished - started, 3),
            "returncode": (
                0
                if stage_status == "passed"
                else next(
                    (
                        item.get("returncode")
                        for item in command_results
                        if isinstance(item.get("returncode"), int) and item.get("returncode") != 0
                    ),
                    0,
                )
            ),
            "commands_run": command_results,
        }
    )
    record["status"] = stage_status
    record["reason"] = stage_reason
    # The stage report itself is an artifact and contains only redacted tails.
    _write_json(stage_dir / "stage-report.json", record)
    return record


def _update_denominators(report: dict[str, Any]) -> None:
    stages = report["stages"]
    denominators: dict[str, int] = {
        "stages": len(stages),
        "passed": 0,
        "failed": 0,
        "blocked": 0,
        "skipped": 0,
        "not_run": 0,
    }
    for stage in stages:
        status = _canonical_status(stage.get("status"))
        key = status if status in {"passed", "failed", "blocked", "skipped", "not_run"} else None
        if key:
            denominators[key] += 1
        for command in stage.get("commands_run", []):
            for label, count in command.get("denominators", {}).items():
                if label == "duration_seconds":
                    continue
                denominators[label] = denominators.get(label, 0) + count
    report["denominators"] = denominators


def run_gate_pipeline(
    *,
    root: Path,
    python: Path,
    output: Path,
    profile: str,
    allow_rag_skip: bool = False,
    timeout: int = 1800,
    pipeline_timeout: float = DEFAULT_PIPELINE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    if not math.isfinite(float(pipeline_timeout)) or float(pipeline_timeout) <= 0:
        raise ValueError("pipeline_timeout must be finite and positive")
    stages = build_gate_plan(root, python, output, profile)
    report = _initial_report(root, python, output, profile, "run")
    report["skip_policy"]["allowed"] = bool(profile != "full" or allow_rag_skip)
    report["timeouts"] = {
        "per_command_seconds": max(1, timeout),
        "pipeline_seconds": float(pipeline_timeout),
    }
    deadline = time.monotonic() + float(pipeline_timeout)
    blocked = False
    for order, stage in enumerate(stages, start=1):
        if blocked:
            record = _stage_record(
                stage,
                order,
                root=root,
                output=output,
                status="not-run",
                reason="blocked by an earlier required gate",
            )
        elif time.monotonic() >= deadline:
            record = _stage_record(
                stage,
                order,
                root=root,
                output=output,
                status="failed",
                reason="pipeline_timeout",
            )
            blocked = True
        else:
            record = _run_stage(
                stage,
                order,
                root=root,
                output=output,
                python=python,
                timeout=timeout,
                deadline=deadline,
            )
            if record["status"] == "failed" and stage.required:
                blocked = True
        report["stages"].append(record)
        if record["status"] in {"failed", "blocked", "not_run"} and stage.required:
            blocked = True
        _update_denominators(report)
        _write_json(output / "release-gates.json", report)
    report["ok"] = not any(
        stage.get("status") in {"failed", "blocked", "not_run"}
        or (stage.get("status") == "skipped" and stage.get("required", True))
        for stage in report["stages"]
    )
    report["finished_at"] = _utc_now()
    _update_denominators(report)
    _write_json(output / "release-gates.json", report)
    return report


def _unique_output(root: Path, requested: Path | None) -> Path:
    if requested is not None:
        output = requested.expanduser().resolve()
        if output.exists() and any(output.iterdir()):
            raise RuntimeError(f"gate output must be a new or empty directory: {output}")
        return output
    root = root.expanduser().resolve()
    # A clock-only name can collide when two shells start the gate at the same
    # instant.  The random suffix makes the default output safe even before a
    # second process reaches the non-empty-directory guard.
    return root / "artifacts" / f"release-gates-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(8)}"


def _absolute_path_preserving_symlink(path: Path) -> Path:
    """Make a path absolute without discarding a virtualenv symlink."""

    return Path(os.path.abspath(os.fspath(path.expanduser())))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--profile", choices=("core", "full", "ragflow", "book-to-skill"), default="full")
    parser.add_argument("--allow-rag-skip", action="store_true")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--pipeline-timeout", type=float, default=DEFAULT_PIPELINE_TIMEOUT_SECONDS)
    parser.add_argument("--plan", action="store_true", help="print the ordered plan without executing commands")
    parser.add_argument("--json", action="store_true", help="emit the machine-readable report")
    args = parser.parse_args(argv)
    root = args.root.expanduser().resolve()
    # Keep a virtual-environment symlink intact.  Resolving it to the base
    # interpreter drops the isolated site-packages that the gates are meant
    # to exercise (notably pytest and pip-audit).
    python = _absolute_path_preserving_symlink(args.python)
    try:
        output = _unique_output(root, args.output)
        stages = build_gate_plan(root, python, output, args.profile)
        if args.plan:
            report = _initial_report(root, python, output, args.profile, "plan")
            report["stages"] = _plan_payload(stages, root, output)
            report["denominators"]["stages"] = len(stages)
        else:
            if not (root / "pyproject.toml").is_file():
                raise RuntimeError(f"repository metadata is missing: {root / 'pyproject.toml'}")
            output.mkdir(parents=True, exist_ok=True)
            report = run_gate_pipeline(
                root=root,
                python=python,
                output=output,
                profile=args.profile,
                allow_rag_skip=args.allow_rag_skip,
                timeout=max(1, args.timeout),
                pipeline_timeout=args.pipeline_timeout,
            )
    except (OSError, RuntimeError, ValueError) as exc:
        report = {
            "schema_version": SCHEMA_VERSION,
            "ok": False,
            "execution": "plan" if args.plan else "run",
            "profile": args.profile,
            "error": {"code": "release_gate_runner_failed", "message": str(exc)},
        }
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
