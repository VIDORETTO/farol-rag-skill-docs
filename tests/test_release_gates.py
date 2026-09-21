# seam-scope: compatibility-infrastructure (release gate runner CLI)
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from scripts.run_release_gates import (
    GateStage,
    _absolute_path_preserving_symlink,
    _probe_symlink_capability,
    _run_stage,
    _update_denominators,
    build_gate_plan,
    run_gate_pipeline,
)


def test_release_gate_plan_is_sequential_and_declares_isolated_outputs(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_release_gates.py",
            "--root",
            str(tmp_path),
            "--profile",
            "core",
            "--plan",
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads(completed.stdout)
    stages = report["stages"]
    assert report["ok"] is True
    assert report["execution"] == "plan"
    assert [stage["order"] for stage in stages] == list(range(1, len(stages) + 1))
    assert len({stage["name"] for stage in stages}) == len(stages)
    assert all(stage["isolation"] == "unique-temporary-workspace" for stage in stages)
    assert all(stage["artifacts"] for stage in stages)


def test_release_gate_report_preserves_versions_denominators_and_skip_reason(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_release_gates.py",
            "--root",
            str(tmp_path),
            "--profile",
            "core",
            "--plan",
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    report = json.loads(completed.stdout)
    assert report["versions"]["python"]
    assert "denominators" in report
    assert report["skip_policy"]["observable"]
    assert report["artifacts_root"]


def test_full_external_profiles_use_the_selected_interpreter(tmp_path: Path) -> None:
    python = Path(sys.executable).resolve()
    stages = build_gate_plan(tmp_path, python, tmp_path / "artifacts", "full")
    synthesis_stage = next(stage for stage in stages if stage.name == "book-to-skill-contract")

    assert synthesis_stage.commands[0][0] == str(python)
    assert synthesis_stage.commands[0][1].endswith("run_book_to_skill_profile.py")


def test_lint_stages_use_the_selected_interpreter(tmp_path: Path) -> None:
    python = Path(sys.executable).resolve()
    stages = build_gate_plan(tmp_path, python, tmp_path / "artifacts", "core")

    lint_commands = {stage.name: stage.commands[0] for stage in stages if stage.name in {"ruff", "format"}}

    assert lint_commands["ruff"][:3] == (str(python), "-m", "ruff")
    assert lint_commands["format"][:3] == (str(python), "-m", "ruff")


def test_ragflow_profile_repeats_core_and_adds_fail_closed_external_contract_stages(tmp_path: Path) -> None:
    stages = build_gate_plan(tmp_path, Path(sys.executable).resolve(), tmp_path / "artifacts", "ragflow")

    assert len(stages) == 24
    assert [stage.name for stage in stages[-2:]] == ["ragflow-contract", "ocr-contract"]
    assert all(stage.commands[0][-1] == "--json" for stage in stages[-2:])
    assert stages[-2].artifacts[-1].endswith("ragflow-report.json")
    assert stages[-1].artifacts[-1].endswith("ocr-report.json")


def test_ragflow_integration_flag_is_isolated_to_the_ragflow_contract(tmp_path: Path) -> None:
    core_stages = build_gate_plan(tmp_path, Path(sys.executable).resolve(), tmp_path / "core", "core")
    ragflow_stages = build_gate_plan(tmp_path, Path(sys.executable).resolve(), tmp_path / "ragflow", "ragflow")

    assert all(stage.environment["DOCOPS_RAGFLOW_INTEGRATION"] == "0" for stage in core_stages)
    assert all(stage.environment["DOCOPS_RAGFLOW_INTEGRATION"] == "0" for stage in ragflow_stages[:-2])
    assert ragflow_stages[-2].environment["DOCOPS_RAGFLOW_INTEGRATION"] == "1"
    assert ragflow_stages[-1].environment["DOCOPS_RAGFLOW_INTEGRATION"] == "0"
    assert all(stage.environment["DOCOPS_OCR_INTEGRATION"] == "0" for stage in ragflow_stages[:-1])
    assert ragflow_stages[-1].environment["DOCOPS_OCR_INTEGRATION"] == "1"


def test_selected_interpreter_path_preserves_virtualenv_symlink(tmp_path: Path) -> None:
    if not _probe_symlink_capability():
        pytest.skip("symlink creation is unavailable on this host")

    selected = tmp_path / "bin" / "python"
    selected.parent.mkdir()
    selected.symlink_to(sys.executable)

    assert _absolute_path_preserving_symlink(selected) == selected


def test_release_gate_denominators_are_idempotent_and_normalize_not_run() -> None:
    report = {
        "denominators": {
            "stages": 0,
            "passed": 0,
            "failed": 0,
            "blocked": 0,
            "skipped": 0,
            "not_run": 0,
        },
        "stages": [
            {
                "status": "passed",
                "commands_run": [{"denominators": {"passed": 2, "skipped": 1}}],
            },
            {
                "status": "not_run",
                "commands_run": [],
            },
        ],
    }

    _update_denominators(report)
    first = dict(report["denominators"])
    _update_denominators(report)

    assert report["denominators"] == first
    assert report["denominators"] == {
        "stages": 2,
        "passed": 3,
        "failed": 0,
        "blocked": 0,
        "skipped": 1,
        "not_run": 1,
    }


def test_required_gate_preserves_structured_blocked_result(tmp_path: Path) -> None:
    stage = GateStage(
        name="external-contract",
        commands=(
            (
                sys.executable,
                "-c",
                "import json; print(json.dumps({'ok': False, 'status': 'blocked', 'reason': 'missing_external_inputs'})); raise SystemExit(1)",
            ),
        ),
        artifacts=(str(tmp_path / "stage-report.json"),),
    )

    record = _run_stage(
        stage,
        1,
        root=tmp_path,
        output=tmp_path / "artifacts",
        python=Path(sys.executable),
        timeout=30,
    )

    assert record["status"] == "blocked"
    assert record["reason"] == "missing_external_inputs"
    assert record["commands_run"][0]["returncode"] == 1


def test_skip_only_command_is_not_marked_as_passed(tmp_path: Path) -> None:
    stage = GateStage(
        name="skip-only",
        commands=((sys.executable, "-c", "print('1 skipped in 0.01s')"),),
        artifacts=(str(tmp_path / "stage-report.json"),),
    )

    record = _run_stage(
        stage,
        1,
        root=tmp_path,
        output=tmp_path / "artifacts",
        python=Path(sys.executable),
        timeout=30,
    )

    assert record["status"] == "not_run"
    assert record["reason"] == "command completed with skips and no executed tests"


def test_release_gate_denominators_count_blocked_stages() -> None:
    report = {"denominators": {}, "stages": [{"status": "blocked", "commands_run": []}]}

    _update_denominators(report)

    assert report["denominators"] == {
        "stages": 1,
        "passed": 0,
        "failed": 0,
        "blocked": 1,
        "skipped": 0,
        "not_run": 0,
    }


def test_release_gate_pipeline_has_a_global_deadline(tmp_path: Path, monkeypatch) -> None:
    stage = GateStage(
        name="slow",
        commands=((sys.executable, "-c", "import time; time.sleep(10)"),),
        artifacts=(str(tmp_path / "stage-report.json"),),
    )
    monkeypatch.setattr("scripts.run_release_gates.build_gate_plan", lambda *args: [stage])

    started = time.monotonic()
    report = run_gate_pipeline(
        root=tmp_path,
        python=Path(sys.executable),
        output=tmp_path / "artifacts",
        profile="core",
        timeout=30,
        pipeline_timeout=0.1,
    )

    assert time.monotonic() - started < 5
    assert report["ok"] is False
    assert report["stages"][0]["status"] == "failed"
    assert report["stages"][0]["reason"] == "pipeline_timeout"
