# seam-scope: implementation-infrastructure (Farol 3.1 TK-211: S1/S2/S5 composite skills over several sources)
"""TK-211: one thematic skill distilled from several sources."""

from __future__ import annotations

import json
from pathlib import Path

from docops import journey

BOOK = (
    "# Retry Book\n\n## Budgets\n\nA retry budget caps extra load at ten percent of normal traffic.\n\n"
    "## Jitter\n\nAdd random jitter so clients do not retry in lockstep.\n"
)
DOCS = "# Client Docs\n\n## Retries\n\nThe client retries 5 times with exponential backoff by default.\n"


def _project(tmp_path: Path, *, no_skill: bool = False) -> Path:
    project = tmp_path / "project"
    for name, text in (("retry-book", BOOK), ("client-docs", DOCS)):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "notes.md").write_text(text, encoding="utf-8")
        journey.add_source(project, str(folder), license="MIT", skill=not no_skill)
    from docops.composite import compose_skill

    compose_skill(project, "retries", ["retry-book", "client-docs"])
    assert journey.build(project)["ok"]
    return project


def _write_chapter(task: dict, folder: Path) -> Path:
    refs = [(item["ref"], item["citation"]) for item in task["inputs"]["blocks"]]
    book = next(ref for ref, cite in refs if cite.startswith("retry-book/"))
    docs = next(ref for ref, cite in refs if cite.startswith("client-docs/"))
    folder.mkdir(parents=True)
    (folder / "chapter.md").write_text(
        f"# {task['inputs']['title']}\n\n## Core idea\nRetries need a budget [{book}].\n\n"
        f"## Key concepts\n- Default of five attempts [{docs}].\n\n## How to apply\nCap extra load [{book}].\n\n"
        f"## Pitfalls\nLockstep retries [{book}].\n\n## Takeaways\n- Budget and jitter [{book}, {docs}].\n",
        encoding="utf-8",
    )
    return folder


def test_compose_plans_tasks_citing_blocks_from_every_member(tmp_path: Path) -> None:
    from docops.agent_tasks import next_task

    project = _project(tmp_path)
    composite = project / "packages" / "@retries"

    task = next_task(composite)

    cited = {item["citation"].split("/", 1)[0] for item in task["inputs"]["blocks"]}
    assert task["kind"] == "chapter" and cited == {"retry-book", "client-docs"}
    config = json.loads((project / "farol.json").read_text(encoding="utf-8"))
    assert config["skills"] == [{"name": "retries", "sources": ["retry-book", "client-docs"], "language": "en"}]


def _distil(project: Path, tmp_path: Path) -> Path:
    from docops.agent_tasks import next_task, submit_task

    composite = project / "packages" / "@retries"
    while (task := next_task(composite)) and task["kind"] == "chapter":
        assert (
            submit_task(composite, task["task_id"], _write_chapter(task, tmp_path / task["task_id"]))["status"]
            == "accepted"
        )
    core = next_task(composite)
    links = "\n".join(f"- [{item['title']}](chapters/{item['file']})" for item in core["inputs"]["chapters"])
    folder = tmp_path / "core"
    folder.mkdir()
    files = {
        "SKILL.md": "---\nname: retries\ndescription: Use when designing retries across clients.\n---\n\n# Retries\n\n"
        f"## When to use\nRetries.\n\n## Mental models\n- Budget.\n\n## Decision rules\n- Jitter.\n\n## Chapters\n{links}\n",
        "glossary.md": "# Glossary\n\n- **Budget**: cap.\n",
        "patterns.md": "# Patterns\n\n- Jitter.\n",
        "cheatsheet.md": "# Cheatsheet\n\n- Cap retries.\n",
    }
    for name, content in files.items():
        (folder / name).write_text(content, encoding="utf-8")
    assert submit_task(composite, "core", folder)["status"] == "accepted"
    return composite


def test_composite_lineage_qualifies_blocks_by_package(tmp_path: Path) -> None:
    project = _project(tmp_path)

    composite = _distil(project, tmp_path)

    lineage = json.loads((composite / ".docops" / "synthesis" / "lineage.json").read_text(encoding="utf-8"))
    packages = {item["package"] for claim in lineage["claims"] for item in claim["sources"]}
    assert packages == {"retry-book", "client-docs"}
    status = {item["name"]: item for item in journey.status(project)["skills"]}
    assert status["retries"]["state"] == "ready"


def test_member_change_marks_composite_chapters_stale(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _distil(project, tmp_path)
    notes = tmp_path / "retry-book" / "notes.md"
    notes.write_text(notes.read_text(encoding="utf-8").replace("ten percent", "twenty percent"), encoding="utf-8")

    journey.sync(project)

    status = {item["name"]: item for item in journey.status(project)["skills"]}
    assert status["retries"]["state"] == "stale" and status["retries"]["stale_chapters"]


def test_no_skill_member_keeps_its_index_but_skips_synthesis(tmp_path: Path) -> None:
    project = _project(tmp_path, no_skill=True)

    report = {item["id"]: item for item in journey.status(project)["sources"]}

    assert report["retry-book"]["state"] == "indexed" and report["retry-book"]["next_action"] is None
    assert not (project / "packages" / "retry-book" / ".docops" / "synthesis" / "plan.json").exists()
    assert (project / "packages" / "retry-book" / "rag" / "local-index" / "ACTIVE.json").is_file()


def test_mcp_lists_the_composite_skill_and_searches_its_members(tmp_path: Path) -> None:
    from docops.mcp_server import KnowledgeServer

    project = _project(tmp_path)
    _distil(project, tmp_path)

    server = KnowledgeServer(packages=journey.project_packages(project), composites=journey.project_composites(project))
    skills = {item["name"]: item for item in server.list_skills()["skills"]}
    hits = server.search_knowledge("retry budget default attempts", package="@retries")["hits"]

    assert skills["retries"]["package"] == "@retries"
    assert server.get_skill("retries")["markdown"].startswith("---\nname: retries")
    assert {hit["package"] for hit in hits} == {"retry-book", "client-docs"}


def test_connect_installs_the_composite_skill(tmp_path: Path) -> None:
    from docops.connect import connect

    project = _project(tmp_path, no_skill=True)
    _distil(project, tmp_path)
    target = tmp_path / "repo"
    target.mkdir()

    connect(project, "claude-code", target=target)

    assert (target / ".claude" / "skills" / "retries" / "SKILL.md").is_file()
    router = (target / ".claude" / "skills" / "project-router" / "SKILL.md").read_text(encoding="utf-8")
    assert "`retries`" in router


def test_synthesis_layer_reads_the_composite_lineage(tmp_path: Path) -> None:
    from docops.mcp_server import KnowledgeServer

    project = _project(tmp_path, no_skill=True)
    _distil(project, tmp_path)
    server = KnowledgeServer(packages=journey.project_packages(project), composites=journey.project_composites(project))

    scoped = server.search_knowledge("retry budget", package="@retries", layer="synthesis")["synthesis"]
    everywhere = server.search_knowledge("retry budget", layer="synthesis")["synthesis"]

    assert scoped and scoped[0]["package"] == "@retries"
    assert scoped[0]["supports"] and {item["package"] for item in scoped[0]["supports"]} <= {
        "retry-book",
        "client-docs",
    }
    assert any(item["package"] == "@retries" for item in everywhere)
