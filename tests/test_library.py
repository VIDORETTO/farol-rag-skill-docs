# seam-scope: public-seam (S1/S2: `farol library` and `farol mcp --library`)
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _cli(cwd: Path, home: Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "docops", *args],
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=cwd,
        timeout=120,
        env={**os.environ, "PYTHONPATH": str(ROOT), "FAROL_HOME": str(home)},
    )


def _project(tmp_path: Path, home: Path, name: str, text: str) -> Path:
    source = tmp_path / f"{name}-docs"
    source.mkdir()
    (source / "notes.md").write_text(f"# Notes\n\n## Facts\n\n{text}\n", encoding="utf-8")
    project = tmp_path / name
    project.mkdir()
    _cli(project, home, "add", str(source), "--name", "notes", "--license", "MIT")
    assert _cli(project, home, "build").returncode == 0
    return project


def _search(home: Path, cwd: Path, query: str) -> dict[str, Any]:
    stdin = "".join(
        json.dumps(message) + "\n"
        for message in (
            {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "search_knowledge", "arguments": {"query": query, "top_k": 5}},
            },
        )
    )
    completed = _cli(cwd, home, "mcp", "--library", stdin=stdin)
    return json.loads(completed.stdout.splitlines()[-1])["result"]["structuredContent"]


def test_library_registers_projects_idempotently(tmp_path: Path) -> None:
    home = tmp_path / "home"
    alpha = _project(tmp_path, home, "alpha", "Alpha deploys on Mondays.")

    first = json.loads(_cli(tmp_path, home, "library", "add", str(alpha), "--json").stdout)
    second = json.loads(_cli(tmp_path, home, "library", "add", str(alpha), "--json").stdout)
    listed = json.loads(_cli(tmp_path, home, "library", "list", "--json").stdout)
    removed = json.loads(_cli(tmp_path, home, "library", "remove", "alpha", "--json").stdout)

    assert first["status"] == "added" and second["status"] == "unchanged"
    assert [item["name"] for item in listed["projects"]] == ["alpha"]
    assert listed["projects"][0]["sources"] == 1
    assert removed["status"] == "removed"


def test_one_mcp_server_answers_from_every_registered_project(tmp_path: Path) -> None:
    home = tmp_path / "home"
    alpha = _project(tmp_path, home, "alpha", "Alpha deploys on Mondays.")
    beta = _project(tmp_path, home, "beta", "Beta deploys on Fridays.")
    for project in (alpha, beta):
        _cli(tmp_path, home, "library", "add", str(project))

    result = _search(home, tmp_path, "which day does beta deploy")

    packages = {hit["package"] for hit in result["hits"]}
    assert packages <= {"alpha/notes", "beta/notes"} and "beta/notes" in packages
    assert result["hits"][0]["package"] == "beta/notes"


def test_a_broken_package_is_isolated_and_reported(tmp_path: Path) -> None:
    home = tmp_path / "home"
    alpha = _project(tmp_path, home, "alpha", "Alpha deploys on Mondays.")
    beta = _project(tmp_path, home, "beta", "Beta deploys on Fridays.")
    for project in (alpha, beta):
        _cli(tmp_path, home, "library", "add", str(project))
    for index in (alpha / "packages" / "notes" / "rag" / "local-index").glob("*.sqlite"):
        index.write_bytes(b"broken")

    result = _search(home, tmp_path, "deploys")

    assert {hit["package"] for hit in result["hits"]} == {"beta/notes"}
    assert result["unavailable"] == [{"package": "alpha/notes", "code": "index_unreadable"}]
