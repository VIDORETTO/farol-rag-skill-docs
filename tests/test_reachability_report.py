# seam-scope: implementation-infrastructure (Farol 3.1 TK-216: maintainer script `scripts/reachability_report.py`)
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_reachability_report_lists_modules_unused_by_the_journey() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/reachability_report.py", "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        timeout=300,
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    unused = set(report["modules_unused_by_journey"])
    modules = {item["module"]: item for item in report["modules"]}
    assert report["method"] == "observed-journey"
    # The journey's own modules run; the 2.0 governance and release tooling do not.
    for module in ("docops/journey.py", "docops/mcp_server.py", "docops/agent_tasks.py", "docops/connect.py"):
        assert module not in unused and modules[module]["executed_functions"] > 0
    assert {"docops/release_v2.py", "docops/backends/ragflow.py", "docops/reader_sessions.py"} <= unused
    totals = report["totals"]
    assert 0 < totals["executed_functions"] < totals["functions"]
