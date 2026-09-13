# seam-scope: compatibility-infrastructure (documentation checker CLI)

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_check_documentation_script_runs_from_repository_root() -> None:
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "scripts/check_documentation.py"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads(completed.stdout)
    assert report["ok"] is True
