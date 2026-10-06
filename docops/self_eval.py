"""``farol eval``: a package measures its own retrieval (TK-215).

Every accepted skill statement is linked to the blocks that support it
(``lineage.json``). Searching the statement and checking that a supporting
block comes back is a self-assessment available for any source the user adds,
without a curated golden set. It is optimistic, because the statements were
written from those blocks; agent-written questions (the optional ``questions``
task) are reported separately when they exist.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from .backends.base import QueryRequest

TOP_K = 5
_REF = re.compile(r"\[(?:b\d+(?:\s*,\s*b\d+)*)\]")
NOTE = (
    "Self-assessment: statements were written from the blocks they cite, so lineage recall is optimistic; "
    "agent-written questions, when present, are closer to real use."
)


def _rank(hits: list[Mapping[str, Any]], block_ids: set[str]) -> int | None:
    return next((position for position, hit in enumerate(hits, 1) if hit["block_id"] in block_ids), None)


def _summary(ranks: list[int | None]) -> dict[str, Any]:
    total = len(ranks)
    return {
        "cases": total,
        "recall_at_5": round(sum(1 for rank in ranks if rank) / total, 4) if total else 0.0,
        "mrr_at_5": round(sum(1.0 / rank for rank in ranks if rank) / total, 4) if total else 0.0,
    }


def _measure(backend: Any, index: Any, cases: list[tuple[str, str, set[str]]]) -> tuple[dict, dict[str, list]]:
    ranks: list[int | None] = []
    by_chapter: dict[str, list[int | None]] = {}
    for chapter, query, block_ids in cases:
        hits = backend.query(index, QueryRequest(query=query, top_k=TOP_K)).hits
        rank = _rank(hits, block_ids)
        ranks.append(rank)
        by_chapter.setdefault(chapter, []).append(rank)
    return _summary(ranks), by_chapter


def evaluate_package(package: Path | str) -> dict[str, Any]:
    from .package_index import open_package_index

    root = Path(package).resolve()
    lineage_path = root / ".docops" / "synthesis" / "lineage.json"
    if not lineage_path.is_file():
        return {"status": "not_run", "code": "skill_not_distilled", "next_action": "farol task next"}
    claims = json.loads(lineage_path.read_text(encoding="utf-8")).get("claims", [])
    backend, index = open_package_index(root)
    cases = [
        (str(claim.get("chapter") or ""), _REF.sub("", str(claim["text"])), {str(item) for item in claim["block_ids"]})
        for claim in claims
        if claim.get("text") and claim.get("block_ids")
    ]
    lineage, by_chapter = _measure(backend, index, cases)
    chapters = sorted(
        ({"chapter": name, **_summary(ranks)} for name, ranks in by_chapter.items()),
        key=lambda item: (item["recall_at_5"], item["chapter"]),
    )
    report: dict[str, Any] = {
        "status": "measured",
        "note": NOTE,
        "lineage": {"method": "lineage-self-assessment", **lineage, "chapters": chapters},
    }
    questions = _agent_questions(root)
    if questions:
        summary, _ = _measure(backend, index, questions)
        report["questions"] = {"method": "agent-questions", **summary}
    return report


def _agent_questions(root: Path) -> list[tuple[str, str, set[str]]]:
    from .agent_tasks import SYNTHESIS_DIR, _load_task

    path = root / SYNTHESIS_DIR / "accepted" / "questions" / "questions.json"
    if not path.is_file():
        return []
    task = _load_task(root, "questions")
    refs = {ref: block_id for chapter in task["inputs"]["chapters"] for ref, block_id in chapter["blocks"].items()}
    cases = []
    for item in json.loads(path.read_text(encoding="utf-8")).get("questions", []):
        block_ids = {refs[ref] for ref in item.get("refs", []) if ref in refs}
        if block_ids:
            cases.append(("questions", str(item["question"]), block_ids))
    return cases


def evaluate(target: Path | str) -> dict[str, Any]:
    """A package, or every built source of a project."""

    root = Path(target).resolve()
    if (root / "manifest.json").is_file():
        return evaluate_package(root)
    from .journey import project_packages

    packages = {source_id: evaluate_package(path) for source_id, path in project_packages(root).items()}
    measured = any(item["status"] == "measured" for item in packages.values())
    return {"status": "measured" if measured else "not_run", "note": NOTE, "sources": packages}
