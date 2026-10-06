# seam-scope: implementation-infrastructure (Farol 3 public module seam: S1: `farol build` and `farol connect <harness>`)
"""TK-209: a small, backend-neutral router, installed once per project."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
_STALE_TERMS = re.compile(r"ragflow|lifecycle|generation", re.IGNORECASE)
# A 3.0 router (abridged) as Farol 3.0.0 generated it.
_ROUTER_3_0 = (
    "---\nname: {slug}-router\ndescription: Routes {slug} conceptual questions to the skill and factual "
    "questions to RAGFlow evidence.\nmetadata:\n  type: router\n  generated_by: docops\n  policy_revision: 2\n---\n\n"
    "# {slug}-router\n\nFor literal questions call `search_knowledge` and cite each hit's `citation`.\n"
    "Readers use the generation declared in `harness.json`.\n"
)


def _cli(cwd: Path, *args: str) -> tuple[int, Any]:
    completed = subprocess.run(
        [sys.executable, "-m", "docops", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=cwd,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        timeout=180,
    )
    try:
        return completed.returncode, json.loads(completed.stdout)
    except json.JSONDecodeError:
        return completed.returncode, completed.stdout + completed.stderr


def _project(tmp_path: Path, names: tuple[str, ...] = ("alpha-docs",)) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    for name in names:
        source = tmp_path / name
        source.mkdir()
        (source / "guide.md").write_text(f"# {name}\n\n## Retries\n\nThe {name} client retries 5 times.\n", "utf-8")
        _cli(project, "add", str(source), "--license", "MIT")
    code, built = _cli(project, "build", "--json")
    assert code == 0, built
    return project


def test_generated_router_is_small_and_backend_neutral(tmp_path: Path) -> None:
    project = _project(tmp_path)

    text = (project / "packages" / "alpha-docs" / "router" / "SKILL.md").read_text(encoding="utf-8")

    assert len(text) // 4 <= 350
    assert not _STALE_TERMS.search(text)
    assert "search_knowledge" in text and "get_context" in text and "citation" in text
    assert "insufficient_evidence" in text


def test_connect_installs_one_project_router_instead_of_one_per_source(tmp_path: Path) -> None:
    project = _project(tmp_path, ("alpha-docs", "beta-docs", "gamma-docs"))
    target = tmp_path / "repo"
    stale = target / ".claude" / "skills" / "alpha-docs-router" / "SKILL.md"
    stale.parent.mkdir(parents=True)
    stale.write_text("old per-source router installed by Farol 3.0\n", encoding="utf-8")
    record = {
        f"claude-code:{target.resolve()}": {"configs": {}, "files": [".claude/skills/alpha-docs-router/SKILL.md"]}
    }
    (project / ".farol" / "connect.json").write_text(json.dumps(record), encoding="utf-8")

    code, result = _cli(project, "connect", "claude-code", "--target", str(target), "--json")

    assert code == 0, result
    installed = sorted(path.name for path in (target / ".claude" / "skills").iterdir())
    assert installed == ["alpha-docs", "beta-docs", "farol-distill", "gamma-docs", "project-router"]
    router = (target / ".claude" / "skills" / "project-router" / "SKILL.md").read_text(encoding="utf-8")
    assert router.startswith("---\nname: project-router\n")
    assert all(f"`{name}`" in router for name in ("alpha-docs", "beta-docs", "gamma-docs"))
    assert len(router) // 4 <= 350 + 60 * 3
    assert not _STALE_TERMS.search(router)

    _cli(project, "connect", "claude-code", "--target", str(target), "--remove", "--json")
    assert not (target / ".claude" / "skills").exists()


def test_build_upgrades_a_3_0_router_and_keeps_revisions_consistent(tmp_path: Path, monkeypatch) -> None:
    from docops import generation, journey

    source = tmp_path / "alpha-docs"
    source.mkdir()
    (source / "guide.md").write_text("# alpha\n\n## Retries\n\nThe client retries 5 times.\n", "utf-8")
    project = tmp_path / "project"
    journey.add_source(project, str(source), license="MIT")
    with monkeypatch.context() as patched:  # build exactly as Farol 3.0.0 did
        patched.setattr(generation, "router_artifact", lambda slug: _ROUTER_3_0.format(slug=slug))
        assert journey.build(project)["ok"]
    package = project / "packages" / "alpha-docs"
    assert "RAGFlow" in (package / "router" / "SKILL.md").read_text(encoding="utf-8")
    assert _cli(ROOT, "validate", str(package), "--json")[0] == 0

    code, built = _cli(project, "build", "--json")
    text = (package / "router" / "SKILL.md").read_text(encoding="utf-8")
    code_validate, validated = _cli(ROOT, "validate", str(package), "--json")

    assert code == 0, built
    assert "get_context" in text and not _STALE_TERMS.search(text)
    assert code_validate == 0, validated
