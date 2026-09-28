# seam-scope: implementation-infrastructure (generated CLI/MCP reference and site configuration)
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/gen_reference.py", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=60,
    )


def test_reference_is_generated_from_the_code_and_checked() -> None:
    completed = _run("--check")

    assert completed.returncode == 0, completed.stdout
    cli = (ROOT / "docs" / "reference" / "cli.md").read_text(encoding="utf-8")
    mcp = (ROOT / "docs" / "reference" / "mcp.md").read_text(encoding="utf-8")
    assert "## farol add" in cli and "--license" in cli
    assert "## search_knowledge" in mcp and "`query`" in mcp


def test_site_navigation_points_to_existing_pages() -> None:
    import yaml

    config = yaml.safe_load((ROOT / "mkdocs.yml").read_text(encoding="utf-8"))

    def pages(items: list) -> list[str]:
        found = []
        for item in items:
            value = next(iter(item.values())) if isinstance(item, dict) else item
            found.extend(pages(value) if isinstance(value, list) else [value])
        return found

    listed = pages(config["nav"])
    assert "reference/cli.md" in listed and "reference/mcp.md" in listed
    assert all((ROOT / "docs" / page).is_file() for page in listed)


def test_documented_recipes_run_offline() -> None:
    import json
    import os

    completed = subprocess.run(
        [sys.executable, "scripts/run_examples.py", "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=300,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )

    report = json.loads(completed.stdout)
    assert report["ok"], report
    assert {item["recipe"] for item in report["recipes"]} == {
        "documentation-folder",
        "video-subtitles",
        "several-sources",
    }
