# seam-scope: public-seam (S1: `farol init/add/build/status` journey and `farol mcp --project`)
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _cli(project: Path, *args: str, stdin: str | None = None) -> tuple[int, Any]:
    completed = subprocess.run(
        [sys.executable, "-m", "docops", *args],
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=project,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        timeout=120,
    )
    try:
        return completed.returncode, json.loads(completed.stdout)
    except json.JSONDecodeError:
        return completed.returncode, completed.stdout + completed.stderr


def _sources(tmp_path: Path) -> tuple[Path, Path]:
    guide = tmp_path / "acme-docs"
    guide.mkdir()
    (guide / "guide.md").write_text(
        "# Acme Guide\n\n## Retries\n\nThe client retries 5 times with exponential backoff.\n", encoding="utf-8"
    )
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "notes.md").write_text("# Team notes\n\n## Deploys\n\nDeploys happen on Tuesdays.\n", encoding="utf-8")
    return guide, notes


def test_add_registers_sources_and_status_tells_the_next_step(tmp_path: Path) -> None:
    guide, notes = _sources(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    code, added = _cli(project, "add", str(guide), "--license", "MIT", "--json")
    _cli(project, "add", str(notes), "--json")
    _, status = _cli(project, "status", "--json")

    assert code == 0 and added["source"]["id"] == "acme-docs"
    config = json.loads((project / "farol.json").read_text(encoding="utf-8"))
    assert [source["id"] for source in config["sources"]] == ["acme-docs", "notes"]
    states = {source["id"]: source for source in status["sources"]}
    assert states["acme-docs"]["state"] == "added"
    assert states["notes"]["warnings"] and "license" in states["notes"]["warnings"][0]
    assert status["next_action"] == "farol build"


def test_build_makes_every_source_queryable_and_hands_synthesis_to_the_agent(tmp_path: Path) -> None:
    guide, notes = _sources(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    _cli(project, "add", str(guide), "--license", "MIT")
    _cli(project, "add", str(notes), "--license", "CC-BY-4.0")

    code, built = _cli(project, "build", "--json")
    _, status = _cli(project, "status", "--json")

    assert code == 0, built
    assert {source["state"] for source in status["sources"]} == {"awaiting_agent"}
    assert status["state"] == "awaiting_agent"
    assert "farol task next" in status["next_action"]
    for source in status["sources"]:
        assert (project / "packages" / source["id"] / "rag" / "local-index" / "ACTIVE.json").is_file()
    stdin = "".join(
        json.dumps(message) + "\n"
        for message in (
            {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "search_knowledge", "arguments": {"query": "when do deploys happen"}},
            },
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "list_skills", "arguments": {}}},
        )
    )
    completed = subprocess.run(
        [sys.executable, "-m", "docops", "mcp", "--project", str(project)],
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=project,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        timeout=60,
    )
    responses = {line["id"]: line for line in map(json.loads, completed.stdout.splitlines())}
    hit = responses[1]["result"]["structuredContent"]["hits"][0]
    assert "Tuesdays" in hit["text"] and hit["package"] == "notes"
    skills = {skill["name"] for skill in responses[2]["result"]["structuredContent"]["skills"]}
    assert {"acme-docs", "notes"} <= skills


def test_rebuild_after_a_source_change_refreshes_facts_and_keeps_the_distilled_skill(tmp_path: Path) -> None:
    from docops.agent_tasks import next_task, submit_task

    guide, _notes = _sources(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    _cli(project, "add", str(guide), "--license", "MIT")
    _cli(project, "build")
    package = project / "packages" / "acme-docs"
    answers = tmp_path / "answers"
    while task := next_task(package):
        out = answers / task["task_id"]
        out.mkdir(parents=True)
        if task["kind"] == "chapter":
            ref = task["inputs"]["blocks"][0]["ref"]
            (out / "chapter.md").write_text(
                f"# Retries\n\n## Core idea\nRetry with backoff [{ref}].\n\n## Key concepts\n- Backoff [{ref}].\n\n"
                f"## How to apply\nBound retries [{ref}].\n\n## Pitfalls\nInfinite loops.\n\n## Takeaways\n- Bound it [{ref}].\n",
                encoding="utf-8",
            )
        else:
            links = "\n".join(f"- [{c['title']}](chapters/{c['file']})" for c in task["inputs"]["chapters"])
            (out / "SKILL.md").write_text(
                "---\nname: acme-docs\ndescription: Use when configuring retries of the Acme client.\n---\n\n"
                f"## When to use\nRetries.\n\n## Mental models\n- Backoff.\n\n## Decision rules\n- Bound.\n\n## Chapters\n{links}\n",
                encoding="utf-8",
            )
            for name in ("glossary.md", "patterns.md", "cheatsheet.md"):
                (out / name).write_text(f"# {name}\n\n- item\n", encoding="utf-8")
        assert submit_task(package, task["task_id"], out)["status"] == "accepted"
    _, ready = _cli(project, "status", "--json")
    skill = (package / "skill" / "SKILL.md").read_text(encoding="utf-8")
    (guide / "guide.md").write_text(
        (guide / "guide.md").read_text(encoding="utf-8") + "\n## Timeouts\n\nThe default timeout is 7 seconds.\n",
        encoding="utf-8",
    )

    code, rebuilt = _cli(project, "build", "--json")
    _, after = _cli(project, "status", "--json")

    assert ready["sources"][0]["state"] == "ready"
    assert code == 0, rebuilt
    assert (package / "skill" / "SKILL.md").read_text(encoding="utf-8") == skill
    assert after["sources"][0]["state"] == "ready"
    from docops.backends import QueryRequest
    from docops.package_index import open_package_index

    backend, index = open_package_index(package)
    assert "7 seconds" in backend.query(index, QueryRequest(query="default timeout", top_k=1)).hits[0]["text"]


def test_help_shows_the_journey_and_keeps_advanced_commands_working(tmp_path: Path) -> None:
    code, text = _cli(tmp_path, "--help")

    usage = text.split("\n\n", 1)[0]
    commands = usage[usage.index("{") + 1 : usage.index("}")].split(",")
    assert code == 0 and len(commands) <= 8 + 1
    assert {"add", "build", "status", "task", "mcp", "doctor", "advanced"} <= set(commands)
    code, advanced = _cli(tmp_path, "advanced")
    assert code == 0 and "validate" in advanced and "lifecycle" in advanced
    code, _ = _cli(tmp_path, "validate", str(tmp_path / "missing"), "--json")
    assert code == 1


def test_task_commands_inside_a_project_pick_the_next_waiting_source(tmp_path: Path) -> None:
    guide, _notes = _sources(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    _cli(project, "add", str(guide), "--license", "MIT")
    _cli(project, "build")

    code, task = _cli(project, "task", "next", "--json")
    _, progress = _cli(project, "task", "status", "--json")

    assert code == 0 and task["kind"] == "chapter"
    assert task["package"] == "packages/acme-docs"
    assert "--package packages/acme-docs" in task["instructions"]
    assert progress["state"] == "awaiting_agent"
