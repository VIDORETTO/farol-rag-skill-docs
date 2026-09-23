"""Copy the distributable tree to a temporary directory and run its checks."""

from __future__ import annotations

import argparse
import json
import locale
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_IGNORED_DIRS = {
    ".git",
    ".venv",
    ".venv-rag",
    ".venv-posix",
    ".venv-windows",
    "data",
    "models_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    ".docops",
    "artifacts",
    "build",
    "dist",
    ".scratch",
}
_IGNORED_FILES = {".rag_state.json"}


def _ignore(directory: str, names: list[str]) -> set[str]:
    relative = Path(directory).resolve()
    ignored = {name for name in names if name in _IGNORED_DIRS or name in _IGNORED_FILES or name.endswith(".egg-info")}
    if relative.name == "documents":
        ignored.update(name for name in names if name not in {"README.md", "examples", "fixtures"})
    return ignored


def copy_distributable_tree(source: Path, destination: Path) -> None:
    """Copy source code and synthetic fixtures, excluding local state."""

    shutil.copytree(source, destination, ignore=_ignore)


def _clone_python(destination: Path) -> Path:
    relative = Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    return destination / ".venv" / relative


def _preflight(python: str, destination: Path, *, tests_required: bool) -> dict[str, object]:
    required = ["docops"] + (["pytest"] if tests_required else [])
    missing: list[str] = []
    for module in required:
        try:
            completed = subprocess.run(
                [python, "-c", f"import {module}"],
                cwd=destination,
                env={
                    key: value
                    for key, value in os.environ.items()
                    if key.casefold() not in {"pythonioencoding", "pythonutf8"}
                },
                check=False,
                capture_output=True,
                text=True,
                encoding=locale.getpreferredencoding(False),
                errors="replace",
            )
        except OSError:
            completed = None
        if completed is None or completed.returncode:
            missing.append(module)
    return {
        "profile": "core-dev" if tests_required else "core",
        "required_modules": required,
        "missing_modules": missing,
        "ok": not missing,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="run scripts/bootstrap.py --dev in the clone when the preflight is missing dependencies",
    )
    parser.add_argument("--keep", action="store_true", help="keep the temporary clone and print its path")
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    temporary = tempfile.mkdtemp(prefix="docops-clean-clone-")
    destination = Path(temporary) / source.name
    copy_distributable_tree(source, destination)
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.casefold() not in {"pythonpath", "pythonhome", "pythonioencoding", "pythonutf8", "docops_skip_rag"}
    }
    environment["PYTHONNOUSERSITE"] = "1"
    environment["DOCOPS_SKIP_RAG"] = "1"
    preflight = _preflight(args.python, destination, tests_required=not args.skip_tests)
    reports: list[dict[str, object]] = [{"step": "preflight", **preflight}]
    release_audited = False
    if args.bootstrap and Path(args.python).is_file():
        release_command = [args.python, "scripts/audit_release.py", "--root", str(destination), "--json"]
        release_audit = subprocess.run(
            release_command,
            cwd=destination,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        reports.append(
            {
                "step": "pre-bootstrap-release-audit",
                "command": release_command,
                "returncode": release_audit.returncode,
                "stdout": release_audit.stdout[-4000:],
                "stderr": release_audit.stderr[-4000:],
            }
        )
        if release_audit.returncode:
            print(
                json.dumps(
                    {"ok": False, "code": "release_audit_failed", "clone": str(destination), "reports": reports},
                    indent=2,
                    ensure_ascii=False,
                )
            )
            if not args.keep:
                shutil.rmtree(Path(temporary), ignore_errors=True)
            return release_audit.returncode
        release_audited = True
    if args.bootstrap or not preflight["ok"]:
        if not args.bootstrap:
            bootstrap = [args.python, "scripts/bootstrap.py", "--root", str(destination), "--dev"]
            payload = {
                "ok": False,
                "code": "bootstrap_required",
                "clone": str(destination),
                "preflight": preflight,
                "bootstrap": {"command": bootstrap, "profile": "core-dev"},
                "reports": reports,
            }
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            if not args.keep:
                shutil.rmtree(Path(temporary), ignore_errors=True)
            return 2
        bootstrap_command = [args.python, "scripts/bootstrap.py", "--root", str(destination), "--dev"]
        try:
            bootstrap = subprocess.run(
                bootstrap_command,
                cwd=destination,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
                timeout=600,
            )
        except FileNotFoundError:
            reports.append(
                {
                    "step": "bootstrap",
                    "command": bootstrap_command,
                    "returncode": None,
                    "error": "the requested bootstrap interpreter was not found",
                }
            )
            print(
                json.dumps(
                    {
                        "ok": False,
                        "code": "bootstrap_interpreter_missing",
                        "clone": str(destination),
                        "reports": reports,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
            if not args.keep:
                shutil.rmtree(Path(temporary), ignore_errors=True)
            return 2
        except subprocess.TimeoutExpired:
            reports.append(
                {
                    "step": "bootstrap",
                    "command": bootstrap_command,
                    "returncode": None,
                    "error": "bootstrap exceeded the 600 second limit",
                }
            )
            print(
                json.dumps(
                    {"ok": False, "code": "bootstrap_timeout", "clone": str(destination), "reports": reports},
                    indent=2,
                    ensure_ascii=False,
                )
            )
            if not args.keep:
                shutil.rmtree(Path(temporary), ignore_errors=True)
            return 2
        reports.append(
            {
                "step": "bootstrap",
                "command": bootstrap_command,
                "returncode": bootstrap.returncode,
                "stdout": bootstrap.stdout[-4000:],
                "stderr": bootstrap.stderr[-4000:],
            }
        )
        if bootstrap.returncode:
            print(
                json.dumps(
                    {"ok": False, "code": "bootstrap_failed", "clone": str(destination), "reports": reports},
                    indent=2,
                    ensure_ascii=False,
                )
            )
            if not args.keep:
                shutil.rmtree(Path(temporary), ignore_errors=True)
            return bootstrap.returncode
        candidate_python = _clone_python(destination)
        if not candidate_python.is_file():
            print(
                json.dumps(
                    {"ok": False, "code": "bootstrap_python_missing", "clone": str(destination), "reports": reports},
                    indent=2,
                    ensure_ascii=False,
                )
            )
            if not args.keep:
                shutil.rmtree(Path(temporary), ignore_errors=True)
            return 2
        args.python = str(candidate_python)
    commands = [[args.python, "-m", "docops", "doctor", "--root", str(destination), "--json"]]
    if not release_audited:
        commands.append([args.python, "scripts/audit_release.py", "--root", str(destination), "--json"])
    if not args.skip_tests:
        commands.append([args.python, "-m", "pytest", "-q"])
    for command in commands:
        completed = subprocess.run(
            command, cwd=destination, env=environment, check=False, capture_output=True, text=True
        )
        reports.append(
            {
                "command": command,
                "returncode": completed.returncode,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
            }
        )
        if completed.returncode:
            print(
                json.dumps({"ok": False, "clone": str(destination), "reports": reports}, indent=2, ensure_ascii=False)
            )
            if not args.keep:
                shutil.rmtree(Path(temporary), ignore_errors=True)
            return completed.returncode
    print(json.dumps({"ok": True, "clone": str(destination), "reports": reports}, indent=2, ensure_ascii=False))
    if not args.keep:
        shutil.rmtree(Path(temporary), ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
