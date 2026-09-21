"""Create a portable project environment.

Examples:
    python scripts/bootstrap.py                 # project + format helpers
    python scripts/bootstrap.py --dev           # install test/lint tools too
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import venv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from docops.runtime import venv_directory  # noqa: E402

BOOTSTRAP_PIP_VERSION = "26.2.1"
BOOTSTRAP_SETUPTOOLS_VERSION = "84.0.0"


def venv_python(root: Path) -> Path:
    relative = (Path("Scripts") / "python.exe") if sys.platform == "win32" else (Path("bin") / "python")
    return venv_directory(root) / relative


def install_command(python: Path, root: Path, *, rag: bool = False, formats: bool, dev: bool) -> list[str]:
    if rag:
        raise ValueError("the legacy RAG profile was removed; use the opt-in RAGFlow integration profile")
    command = [str(python), "-m", "pip", "install", "--editable", str(root)]
    if formats:
        command.extend(["PyYAML==6.0.3", "pypdf==6.16.2", "python-docx==1.2.0"])
    if dev:
        command.extend(
            ["pytest==9.1.1", "ruff==0.12.7", "pip-audit==2.10.1", f"setuptools=={BOOTSTRAP_SETUPTOOLS_VERSION}"]
        )
    return command


def pip_upgrade_command(python: Path) -> list[str]:
    """Return the pinned installer upgrade used before project packages."""
    return [
        str(python),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        f"pip=={BOOTSTRAP_PIP_VERSION}",
        f"setuptools=={BOOTSTRAP_SETUPTOOLS_VERSION}",
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    formats_group = parser.add_mutually_exclusive_group()
    formats_group.add_argument(
        "--formats", dest="formats", action="store_true", help="install optional document format helpers (default)"
    )
    formats_group.add_argument(
        "--no-formats", dest="formats", action="store_false", help="skip optional document format helpers"
    )
    parser.set_defaults(formats=True)
    parser.add_argument("--dev", action="store_true", help="install pytest and ruff")
    parser.add_argument("--no-install", action="store_true", help="create the venv but do not run pip")
    args = parser.parse_args(argv)
    root = args.root.expanduser().resolve()
    if not (root / "pyproject.toml").is_file():
        print(
            json.dumps(
                {"ok": False, "error": {"code": "project_metadata_missing", "message": str(root / "pyproject.toml")}}
            )
        )
        return 1
    python = venv_python(root)
    if not python.exists():
        venv.EnvBuilder(with_pip=not args.no_install, clear=False).create(python.parent.parent)
    command = install_command(python, root, formats=args.formats, dev=args.dev)
    if not args.no_install:
        upgraded = subprocess.run(pip_upgrade_command(python), cwd=root, check=False)
        if upgraded.returncode:
            return upgraded.returncode
        completed = subprocess.run(command, cwd=root, check=False)
        if completed.returncode:
            return completed.returncode
    print(
        json.dumps(
            {"ok": True, "python": str(python), "formats": args.formats, "dev": args.dev},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
