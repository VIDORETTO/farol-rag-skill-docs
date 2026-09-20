"""Environment diagnostics for a clean clone.

The doctor intentionally reports capabilities instead of trying to install
anything. Installation belongs to the bootstrap command and to the user's
chosen harness; this module stays deterministic and has no model integration.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

from .backends.ragflow import RagFlowAdapter
from .config_audit import audit_config_file
from .extractors import default_registry
from .runtime import platform_venv_name, venv_config_matches_host


@dataclass(frozen=True)
class PythonDiscovery:
    """A Python executable candidate and how it was found."""

    path: Path
    source: str

    @property
    def exists(self) -> bool:
        return self.path.is_file()


@dataclass
class DoctorReport:
    """Machine-readable result of the portable environment checks."""

    project_root: Path
    ok: bool
    checks: dict[str, dict[str, object]]
    capabilities: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "project_root": ".",
            "ok": self.ok,
            "checks": self.checks,
            "capabilities": self.capabilities,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False, sort_keys=True)


def _candidate_paths(project_root: Path) -> list[tuple[Path, str]]:
    """Return runnable venv candidates without selecting a foreign OS config."""

    candidates: list[tuple[Path, str]] = []
    platform_specific = platform_venv_name()
    other_platform = ".venv-posix" if platform_specific == ".venv-windows" else ".venv-windows"
    if os.name == "nt":
        native = (Path("Scripts") / "python.exe", Path("Scripts") / "python")
        fallback = (Path("bin") / "python", Path("bin") / "python3")
    else:
        native = (Path("bin") / "python", Path("bin") / "python3")
        fallback = (Path("Scripts") / "python.exe", Path("Scripts") / "python")
    for venv_name in (platform_specific, ".venv", ".venv-rag", other_platform):
        directory = project_root / venv_name
        if not directory.is_dir() or (not venv_config_matches_host(directory) and (directory / "pyvenv.cfg").is_file()):
            continue
        source = "project-venv" if venv_name != ".venv-rag" else "rag-venv"
        for relative in native:
            candidates.append((directory / relative, source))
        # A fixture may contain a layout-neutral placeholder without a config;
        # real cross-platform venvs are never selected through this fallback.
        if not (directory / "pyvenv.cfg").is_file():
            for relative in fallback:
                candidates.append((directory / relative, source))
    return candidates


def discover_python(
    project_root: Path | str,
    *,
    environ: Mapping[str, str] | None = None,
) -> PythonDiscovery:
    """Find the Python executable without assuming a Windows-only path.

    ``DOCOPS_PYTHON`` is an explicit override and is returned even if it does
    not exist, allowing the doctor to explain the broken configuration.
    """

    root = Path(project_root).resolve()
    env = os.environ if environ is None else environ
    override = env.get("DOCOPS_PYTHON", "").strip()
    if override:
        path = Path(override).expanduser()
        return PythonDiscovery(path if path.is_absolute() else root / path, "environment")

    for candidate, source in _candidate_paths(root):
        if candidate.is_file():
            return PythonDiscovery(candidate, source)

    for command in ("python3", "python"):
        found = shutil.which(command)
        if found:
            return PythonDiscovery(Path(found).absolute(), "PATH")

    return PythonDiscovery(Path(sys.executable).absolute(), "runtime")


def _display_path(path: Path, project_root: Path) -> str:
    """Return an actionable path label without disclosing a private root."""

    try:
        relative = path.resolve().relative_to(project_root.resolve())
    except ValueError:
        return path.name or "<external>"
    return relative.as_posix() or "."


def _file_check(path: Path, description: str, *, project_root: Path) -> dict[str, object]:
    exists = path.is_file()
    result: dict[str, object] = {
        "ok": exists,
        "path": _display_path(path, project_root),
        "description": description,
    }
    if not exists:
        result["hint"] = f"Create {path.name} in the project root."
    return result


def run_doctor(
    project_root: Path | str,
    *,
    environ: Mapping[str, str] | None = None,
) -> DoctorReport:
    """Inspect the clone and return a JSON-serializable report."""

    root = Path(project_root).resolve()
    env = os.environ if environ is None else environ
    python = discover_python(root, environ=env)
    checks: dict[str, dict[str, object]] = {
        "python": {
            "ok": python.exists,
            "path": _display_path(python.path, root),
            "source": python.source,
            "version": f"{sys.version_info.major}.{sys.version_info.minor}",
        },
        "project_metadata": _file_check(root / "pyproject.toml", "project metadata", project_root=root),
        "dependency_lock": _file_check(root / "requirements.lock", "locked dependencies", project_root=root),
        "operator_skill": _file_check(
            root / "skills" / "doc-to-rag-operator" / "SKILL.md",
            "operator Agent Skill",
            project_root=root,
        ),
    }
    config_path = root / "config.yaml"
    if config_path.is_file():
        try:
            config_result = audit_config_file(config_path)
        except (OSError, ValueError) as exc:
            checks["config"] = {
                "ok": False,
                "transport": "unknown",
                "errors": [{"code": "config_unreadable", "message": str(exc)}],
            }
        else:
            checks["config"] = {
                "ok": config_result.ok,
                "transport": config_result.transport,
                "errors": config_result.errors,
            }

    skip_rag = env.get("DOCOPS_SKIP_RAG", "").lower() in {"1", "true", "yes"}
    if skip_rag:
        capabilities = {
            "rag": "skipped",
            "network": "not-probed",
            "harness": "external Agent Skills + RAGFlow",
            "operator_skill": "skills/doc-to-rag-operator/SKILL.md",
            "ragflow_transport": "HTTPS required except explicit loopback development",
        }
        checks["rag"] = {"ok": True, "status": "skipped", "reason": "DOCOPS_SKIP_RAG"}
    else:
        rag_required = env.get("DOCOPS_REQUIRE_RAGFLOW", "").lower() in {"1", "true", "yes"}
        ragflow_check = _ragflow_check(env)
        rag_ok = ragflow_check.get("status") == "ready"
        checks["rag"] = {
            "ok": rag_ok or not rag_required,
            "status": "available" if rag_ok else "missing",
            "required": rag_required,
            "hint": "Configure the RAGFlow integration profile before indexing." if not rag_ok else None,
        }
        capabilities = {
            "rag": "available" if rag_ok else "missing",
            "network": "not-probed",
            "harness": "external Agent Skills + RAGFlow",
            "operator_skill": "skills/doc-to-rag-operator/SKILL.md",
            "ragflow_transport": "HTTPS required except explicit loopback development",
        }

    ragflow_check = _ragflow_check(env)
    checks["ragflow"] = ragflow_check
    capabilities["ragflow"] = str(ragflow_check["status"])

    extractor_registry = default_registry()
    checks["extractors"] = {
        "ok": True,
        "status": "available",
        "capabilities": extractor_registry.capabilities(),
        "execution": "local-only by default",
    }
    capabilities["extractors"] = (
        "native local format adapters plus legacy-text (text-fallback); third-party/remotes require opt-in"
    )

    required_names = ["python", "project_metadata", "dependency_lock"]
    if "config" in checks:
        required_names.append("config")
    if checks["rag"].get("required") is True:
        required_names.append("rag")
    if checks["ragflow"].get("required") is True:
        required_names.append("ragflow")
    required_ok = all(checks[name].get("ok", False) is True for name in required_names)
    return DoctorReport(root, required_ok, checks, capabilities)


def _ragflow_check(environ: Mapping[str, str]) -> dict[str, object]:
    """Describe RAGFlow inputs without exposing credentials or probing by default."""

    endpoint = environ.get("DOCOPS_RAGFLOW_ENDPOINT", "").strip()
    token_env = environ.get("DOCOPS_RAGFLOW_TOKEN_ENV", "DOCOPS_RAGFLOW_TOKEN").strip()
    token_present = bool(environ.get(token_env, "").strip())
    sdk_version = environ.get("DOCOPS_RAGFLOW_SDK_VERSION", "").strip()
    image_digest = environ.get("DOCOPS_RAGFLOW_IMAGE_DIGEST", "").strip()
    digest_pinned = bool(re.fullmatch(r".+@sha256:[0-9a-fA-F]{64}", image_digest))
    endpoint_valid = _valid_ragflow_endpoint(endpoint)
    ready = bool(endpoint and endpoint_valid and token_present and sdk_version == RagFlowAdapter.expected_version)
    if not endpoint:
        status = "not_configured"
        reason = "endpoint_missing"
    elif not endpoint_valid:
        status = "unavailable"
        reason = "endpoint_invalid"
    elif not token_present:
        status = "unavailable"
        reason = "token_missing"
    elif sdk_version != RagFlowAdapter.expected_version:
        status = "not_ready"
        reason = "sdk_version_missing_or_mismatch"
    elif not digest_pinned:
        status = "not_ready"
        reason = "image_digest_missing_or_unpinned"
    else:
        status = "configured"
        reason = "probe_not_requested"

    health = "not_probed"
    version = sdk_version or RagFlowAdapter.expected_version
    capabilities: list[str] = []
    if ready:
        capabilities = ["dataset", "upload", "parse", "chunks", "retrieval", "snapshot", "discard"]
        if environ.get("DOCOPS_RAGFLOW_PROBE", "").casefold() in {"1", "true", "yes"}:
            adapter = RagFlowAdapter(
                config={
                    "endpoint": endpoint,
                    "token_env": token_env,
                    "allow_insecure_localhost": environ.get("DOCOPS_RAGFLOW_ALLOW_INSECURE_LOCALHOST", "").casefold()
                    in {"1", "true", "yes"},
                }
            )
            probe = adapter.probe()
            health = probe.status
            version = probe.version or version
            capabilities = list(probe.capabilities) or capabilities
            reason = str(probe.diagnostics.get("reason") or reason)
            if health != "healthy":
                status = "unavailable"

    required = environ.get("DOCOPS_REQUIRE_RAGFLOW", "").casefold() in {"1", "true", "yes"}
    return {
        "ok": (
            health == "healthy" if required else status in {"not_configured", "configured"} and health != "unavailable"
        ),
        "required": required,
        "status": status,
        "reason": reason,
        "endpoint": _safe_ragflow_endpoint(endpoint),
        "authentication": "configured" if token_present else "missing",
        "token_env": token_env,
        "version": version,
        "expected_version": RagFlowAdapter.expected_version,
        "sdk_version": sdk_version or None,
        "image_digest_pinned": digest_pinned,
        "capabilities": capabilities,
        "health": health,
        "probe": "explicit"
        if environ.get("DOCOPS_RAGFLOW_PROBE", "").casefold() in {"1", "true", "yes"}
        else "disabled",
    }


def _valid_ragflow_endpoint(endpoint: str) -> bool:
    if not endpoint:
        return False
    parsed = urlsplit(endpoint)
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)


def _safe_ragflow_endpoint(endpoint: str) -> str:
    if not endpoint:
        return "<unconfigured>"
    parsed = urlsplit(endpoint)
    if not parsed.scheme or not parsed.hostname:
        return "<invalid>"
    default_port = 443 if parsed.scheme == "https" else 80
    try:
        port = parsed.port or default_port
    except ValueError:
        return "<invalid>"
    return f"{parsed.scheme}://{parsed.hostname}:{port}"
