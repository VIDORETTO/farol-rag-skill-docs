# seam-scope: public-seam (error catalog, human error output and `farol doctor --fix`)
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _cli(cwd: Path, *args: str) -> tuple[int, str]:
    completed = subprocess.run(
        [sys.executable, "-m", "docops", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=cwd,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        timeout=120,
    )
    return completed.returncode, completed.stdout + completed.stderr


def _json(cwd: Path, *args: str) -> tuple[int, Any]:
    code, output = _cli(cwd, *args, "--json")
    return code, json.loads(output)


def test_every_public_error_code_is_in_the_catalog() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/check_error_catalog.py", "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=60,
    )

    report = json.loads(completed.stdout)
    assert report["ok"], report["findings"]
    assert report["codes"] >= 20


def test_catalog_check_catches_an_uncatalogued_code(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT))
    from scripts.check_error_catalog import check_catalog

    module = tmp_path / "module.py"
    module.write_text('raise JourneyError("brand_new_failure", "boom")\n', encoding="utf-8")

    report = check_catalog([module])

    assert not report["ok"]
    assert report["findings"][0]["code"] == "brand_new_failure"


def test_errors_tell_the_user_what_to_do_next(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    code, text = _cli(project, "build")
    code_json, payload = _json(project, "build")

    assert code == 2 and "next: farol add <source>" in text
    assert payload["error"]["code"] == "project_missing" and payload["next_action"]
    (project / "farol.json").write_text('{"schema_version": 1, "name": "p", "language": "en", "sources": []}')
    _, connect = _cli(project, "connect", "claude-code")
    assert "next:" in connect


def test_doctor_finds_and_fixes_a_broken_index(tmp_path: Path) -> None:
    source = tmp_path / "docs"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\n\n## Retries\n\nThe client retries 5 times.\n", encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    _cli(project, "add", str(source), "--license", "MIT")
    _cli(project, "build")
    for index in (project / "packages" / "docs" / "rag" / "local-index").glob("*.sqlite"):
        index.write_bytes(b"corrupted")

    _, before = _json(project, "doctor", "--root", str(project))
    _, fixed = _json(project, "doctor", "--root", str(project), "--fix")
    _, after = _json(project, "doctor", "--root", str(project), "--fix")

    assert before["checks"]["project"]["issues"][0]["code"] == "index_unreadable"
    assert fixed["checks"]["project"]["fixed"] == [{"source": "docs", "action": "rebuilt_index"}]
    assert after["checks"]["project"]["issues"] == [] and after["checks"]["project"]["fixed"] == []
    assert set(after["checks"]["extras"]) >= {"formats", "semantic", "media"}
