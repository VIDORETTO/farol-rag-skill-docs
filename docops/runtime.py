"""Small runtime helpers shared by local tools and the RAGFlow profile."""

from __future__ import annotations

import importlib.metadata
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Mapping

RAG_RUNTIME_VERSION = "0.27.2"


def venv_directory(project_root: Path | str) -> Path:
    """Select the native project virtual-environment directory."""

    root = Path(project_root).expanduser().resolve()
    platform_specific = root / platform_venv_name()
    primary = root / ".venv"
    if platform_specific.exists() and venv_config_matches_host(platform_specific):
        return platform_specific
    if primary.exists() and not venv_config_matches_host(primary):
        return platform_specific
    return primary


@dataclass(frozen=True)
class Executable:
    path: Path
    source: str

    @property
    def exists(self) -> bool:
        return self.path.is_file()


def platform_venv_name() -> str:
    return ".venv-windows" if os.name == "nt" else ".venv-posix"


def venv_config_matches_host(directory: Path) -> bool:
    config = directory / "pyvenv.cfg"
    if not config.is_file():
        return False
    home = ""
    try:
        for line in config.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip().lower().startswith("home") and "=" in line:
                home = line.split("=", 1)[1].strip()
                break
    except OSError:
        return False
    if not home:
        return True
    if os.name == "nt":
        return bool(PureWindowsPath(home).drive)
    return PurePosixPath(home).is_absolute() and not PureWindowsPath(home).drive


def discover_rag_python(project_root: Path | str, *, environ: Mapping[str, str] | None = None) -> Executable:
    """Select an explicitly configured Python for integration diagnostics."""

    env = os.environ if environ is None else environ
    explicit = str(env.get("DOCOPS_RAG_PYTHON") or "").strip()
    if explicit:
        return Executable(Path(explicit).expanduser().resolve(), "environment")
    root = Path(project_root).expanduser().resolve()
    for candidate in (root / ".venv-rag", root / platform_venv_name(), root / ".venv"):
        executable = candidate / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if executable.is_file():
            return Executable(executable, "project-venv")
    return Executable(Path(sys.executable).resolve(), "current-interpreter")


def selected_runtime_version(python: Path | str, *, environ: Mapping[str, str] | None = None) -> str | None:
    del environ
    executable = Path(python).expanduser()
    if executable.resolve() == Path(sys.executable).resolve():
        try:
            return importlib.metadata.version("ragflow-sdk")
        except importlib.metadata.PackageNotFoundError:
            return None
    try:
        result = subprocess.run(
            [str(executable), "-c", "import importlib.metadata; print(importlib.metadata.version('ragflow-sdk'))"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else None


def runtime_contract(
    project_root: Path | str,
    *,
    python: Path | str | None = None,
    python_source: str | None = None,
    environ: Mapping[str, str] | None = None,
    expected_version: str | None = None,
) -> dict[str, str | None]:
    selected = (
        Path(python).expanduser().resolve() if python else discover_rag_python(project_root, environ=environ).path
    )
    observed = selected_runtime_version(selected, environ=environ)
    return {
        "backend": "ragflow",
        "expected_version": expected_version or observed or RAG_RUNTIME_VERSION,
        "selected_version": observed,
        "python_source": python_source or "explicit",
    }


def runtime_environment(
    project_root: Path | str,
    *,
    environ: Mapping[str, str] | None = None,
    disable_watcher: bool = True,
    vendor_root: Path | str | None = None,
    read_only: bool | None = None,
) -> dict[str, str]:
    del project_root, disable_watcher, vendor_root, read_only
    environment = dict(os.environ if environ is None else environ)
    environment["PYTHONUNBUFFERED"] = "1"
    environment.pop("HF_ENDPOINT", None)
    return environment


def config_path(project_root: Path | str, *, environ: Mapping[str, str] | None = None) -> Path:
    root = Path(project_root).expanduser().resolve()
    env = os.environ if environ is None else environ
    configured = str(env.get("DOCOPS_CONFIG") or "").strip()
    path = Path(configured).expanduser() if configured else Path("config.yaml")
    return (path if path.is_absolute() else root / path).resolve()


def runtime_provenance(
    project_root: Path | str,
    *,
    python: Path | str | None = None,
    python_source: str | None = None,
    environ: Mapping[str, str] | None = None,
    expected_version: str | None = None,
) -> dict[str, str | None]:
    contract = runtime_contract(
        project_root,
        python=python,
        python_source=python_source,
        environ=environ,
        expected_version=expected_version,
    )
    return {
        "backend": "ragflow",
        "backend_version": contract["selected_version"] or contract["expected_version"],
        "backend_source": "external-ragflow",
        "selected_runtime_version": contract["selected_version"],
        "expected_version": contract["expected_version"],
        "python_source": contract["python_source"],
    }
