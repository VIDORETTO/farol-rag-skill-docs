from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.verify_clean_clone import _clone_python


def test_clean_clone_bootstrap_uses_the_clone_owned_virtualenv(tmp_path: Path) -> None:
    expected = tmp_path / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

    assert _clone_python(tmp_path) == expected


def test_ci_invokes_clean_clone_with_bootstrap_isolation() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "python scripts/verify_clean_clone.py --bootstrap" in workflow


def test_clean_clone_reports_an_actionable_bootstrap_when_interpreter_is_unavailable(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "pyproject.toml").write_text("[project]\nname='fixture'\n", encoding="utf-8")
    missing_python = tmp_path / "missing-python.exe"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/verify_clean_clone.py",
            "--source",
            str(source),
            "--python",
            str(missing_python),
            "--skip-tests",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 2
    report = json.loads(completed.stdout)
    assert report["code"] == "bootstrap_required"
    assert report["preflight"]["missing_modules"] == ["docops"]
    assert report["bootstrap"]["profile"] == "core-dev"
    assert "scripts/bootstrap.py" in report["bootstrap"]["command"]

    bootstrapped = subprocess.run(
        [
            sys.executable,
            "scripts/verify_clean_clone.py",
            "--source",
            str(source),
            "--python",
            str(missing_python),
            "--skip-tests",
            "--bootstrap",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert bootstrapped.returncode == 2
    assert json.loads(bootstrapped.stdout)["code"] == "bootstrap_interpreter_missing"
