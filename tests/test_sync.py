# seam-scope: implementation-infrastructure (Farol 3 public module seam: S1/S7: `farol sync`, refresh of stale skills, scheduling)
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from docops.agent_tasks import next_task, plan_synthesis, submit_task, synthesis_status
from docops.journey import add_source, build, status, sync

ROOT = Path(__file__).resolve().parents[1]


def _write(directory: Path, files: dict[str, str]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (directory / name).write_text(content, encoding="utf-8")
    return directory


def _answer(task: dict[str, Any], out: Path) -> Path:
    if task["kind"] == "chapter":
        refs = [item["ref"] for item in task["inputs"]["blocks"]]
        cite = " ".join(f"[{ref}]" for ref in refs)
        return _write(
            out,
            {
                "chapter.md": (
                    f"# {task['inputs']['title']}\n\n## Core idea\nIdea {cite}.\n\n## Key concepts\n- Concept {cite}.\n\n"
                    f"## How to apply\nApply {cite}.\n\n## Pitfalls\nPitfall {cite}.\n\n## Takeaways\n- Takeaway {cite}.\n"
                )
            },
        )
    links = "\n".join(f"- [{c['title']}](chapters/{c['file']})" for c in task["inputs"]["chapters"])
    return _write(
        out,
        {
            "SKILL.md": "---\nname: docs\ndescription: Use when working with the Acme client and its releases.\n---\n\n"
            f"## When to use\nAcme.\n\n## Mental models\n- M.\n\n## Decision rules\n- R.\n\n## Chapters\n{links}\n",
            "glossary.md": "# Glossary\n\n- **A**: a\n",
            "patterns.md": "# Patterns\n\n- p\n",
            "cheatsheet.md": "# Cheatsheet\n\n- c\n",
        },
    )


def _distilled_project(tmp_path: Path) -> tuple[Path, Path, Path]:
    source = tmp_path / "docs"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\n\n## Retries\n\nThe client retries 5 times.\n", encoding="utf-8")
    (source / "release.md").write_text("# Release\n\n## 2.0\n\nVersion 2.0 removed /v1/orders.\n", encoding="utf-8")
    project = tmp_path / "project"
    add_source(project, str(source), license="MIT")
    build(project)
    package = project / "packages" / "docs"
    plan_synthesis(package, language="en", outline="heuristic", task_source_tokens=5)
    while task := next_task(package):
        assert (
            submit_task(package, task["task_id"], _answer(task, tmp_path / "a" / task["task_id"]))["status"]
            == "accepted"
        )
    assert status(project)["sources"][0]["state"] == "ready"
    return project, package, source


def test_sync_without_changes_reports_no_change(tmp_path: Path) -> None:
    project, package, _source = _distilled_project(tmp_path)
    before = json.loads((package / "rag" / "local-index" / "ACTIVE.json").read_text(encoding="utf-8"))

    report = sync(project)

    assert report["sources"][0]["changes"] == {"state": "no_change", "added": 0, "removed": 0}
    after = json.loads((package / "rag" / "local-index" / "ACTIVE.json").read_text(encoding="utf-8"))
    assert after == before and report["state"] == "ready"


def test_changed_cited_block_marks_only_its_chapter_stale_and_refresh_reopens_it(tmp_path: Path) -> None:
    project, package, source = _distilled_project(tmp_path)
    skill = (package / "skill" / "SKILL.md").read_text(encoding="utf-8")
    (source / "guide.md").write_text("# Guide\n\n## Retries\n\nThe client retries 7 times.\n", encoding="utf-8")

    report = sync(project)
    entry = report["sources"][0]

    assert entry["changes"]["state"] == "changed" and entry["changes"]["removed"] == 1
    assert entry["state"] == "stale" and len(entry["stale_chapters"]) == 1
    assert "farol task plan --refresh" in entry["next_action"]
    assert (package / "skill" / "SKILL.md").read_text(encoding="utf-8") == skill

    plan_synthesis(package, refresh=True)
    pending = [task["task_id"] for task in synthesis_status(package)["tasks"] if task["status"] != "accepted"]

    assert pending == [entry["stale_chapters"][0], "core"]
    task = next_task(package)
    assert "7 times" in json.dumps(task["inputs"]["blocks"])
    while task := next_task(package):
        submit_task(package, task["task_id"], _answer(task, tmp_path / "b" / task["task_id"]))
    assert status(project)["sources"][0]["state"] == "ready"


def test_unchanged_blocks_reuse_their_embeddings(tmp_path: Path) -> None:
    from docops.backends import QueryRequest
    from docops.package_index import build_package_index, open_package_index

    class CountingEmbedder:
        profile = {"model": "count", "dim": 2, "window": 80, "stride": 60}
        embedded: list[str] = []

        def embed_documents(self, texts: list[str]) -> Any:
            import numpy as np

            CountingEmbedder.embedded.extend(texts)
            return np.ones((len(texts), 2), dtype=np.float32)

        def embed_query(self, text: str) -> Any:
            import numpy as np

            return np.ones(2, dtype=np.float32)

    project, package, source = _distilled_project(tmp_path)
    embedder = CountingEmbedder()
    build_package_index(package, embedder=embedder)
    first = len(CountingEmbedder.embedded)
    (source / "guide.md").write_text("# Guide\n\n## Retries\n\nThe client retries 9 times.\n", encoding="utf-8")
    build(project)
    build_package_index(package, embedder=embedder)

    assert first == 2 and len(CountingEmbedder.embedded) == first + 1
    backend, index = open_package_index(package, embedder=embedder)
    assert "9 times" in backend.query(index, QueryRequest(query="retries", top_k=1)).hits[0]["text"]


def test_schedule_prints_exact_lines_without_installing_anything(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "farol.json").write_text('{"schema_version": 1, "name": "p", "language": "en", "sources": []}')

    completed = subprocess.run(
        [sys.executable, "-m", "docops", "sync", "--schedule", "cron", "--project", str(project)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=project,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        timeout=60,
    )

    assert completed.returncode == 0
    line = next(line for line in completed.stdout.splitlines() if line.startswith("0 3 * * *"))
    assert f"-m docops sync --project {project.resolve()}" in line
    for kind in ("systemd", "windows"):
        other = subprocess.run(
            [sys.executable, "-m", "docops", "sync", "--schedule", kind, "--project", str(project)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=project,
            env={**os.environ, "PYTHONPATH": str(ROOT)},
            timeout=60,
        )
        assert other.returncode == 0 and "sync --project" in other.stdout
