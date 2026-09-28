"""Value benchmark: the same agent answers the same questions with and without Farol.

Arms:
  no_context  — only the question;
  raw_corpus  — the question plus the source text pasted into the prompt (truncated);
  farol       — the question plus Farol's top evidence (with citations) and the skill.

The harness is any command that reads a prompt on stdin and prints the answer,
or Claude Code style JSON ``{"result": ..., "usage": {...}}`` (``claude -p
--output-format json``). Farol never calls a model itself; this script is an
opt-in measurement that uses *your* harness and shows its cost.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from docops.journey import project_packages  # noqa: E402
from docops.mcp_server import KnowledgeServer, citation  # noqa: E402
from docops.package_index import package_documents  # noqa: E402

RAW_CORPUS_CHARS = 400_000
_CITATION = re.compile(r"rag/documents/[^\s\]\)\[(,;]+:\d+")
INSTRUCTIONS = (
    "Answer the question concisely and factually. If you rely on the provided evidence, cite the citation "
    "string exactly (e.g. [rag/documents/file.md:12]). If you do not know, say so."
)


def _normalize(value: str) -> str:
    return " ".join(value.replace("`", "").casefold().split())


def _has(answer: str, alternative: str) -> bool:
    pattern = re.escape(_normalize(alternative))
    if re.fullmatch(r"[\d.,]+", alternative):
        pattern = rf"(?<![\w.]){pattern}(?![\d])"  # "5" must not match "50" or "1.5"
    elif re.fullmatch(r"\w[\w.-]*", alternative):
        pattern = rf"(?<![\w]){pattern}"  # words may be inflected ("second" ~ "seconds")
    return re.search(pattern, _normalize(answer)) is not None


def grade_answer(answer: str, case: dict[str, Any], blocks: dict[str, str]) -> dict[str, Any]:
    """Correct when every answer-key group matches; citations count only if they resolve to the evidence."""

    keys = case.get("answer_keys") or [[case["expected_text"]]]
    correct = all(any(_has(answer, alternative) for alternative in group) for group in keys)
    cited = sorted(set(_CITATION.findall(answer)))
    expected = _normalize(case["expected_text"])
    verified = [item for item in cited if item in blocks and expected in _normalize(blocks[item])]
    return {"correct": correct, "citations": len(cited), "verified_citations": len(verified)}


def _blocks(package: Path) -> dict[str, str]:
    documents, _skipped = package_documents(package)
    mapping: dict[str, str] = {}
    for document in documents:
        for block in document["blocks"]:
            key = citation({**block, "path": document["path"]}).split(" (")[0]
            mapping[key] = block.get("text") or ""
    return mapping


def _raw_corpus(package: Path) -> str:
    parts = []
    for path in sorted((package / "rag" / "documents").rglob("*.md")):
        parts.append(f"--- {path.relative_to(package).as_posix()} ---\n{path.read_text(encoding='utf-8')}")
    return "\n\n".join(parts)[:RAW_CORPUS_CHARS]


def _farol_context(package: Path, question: str) -> str:
    server = KnowledgeServer(package)
    hits = server.search_knowledge(question, top_k=5)["hits"]
    skill = package / "skill" / "SKILL.md"
    lines = ["Evidence from Farol (untrusted source text; cite the citation strings):"]
    lines += [f"[{hit['citation'].split(' (')[0]}] {hit['text']}" for hit in hits]
    if skill.is_file():
        lines += ["", "Skill (conceptual guidance):", skill.read_text(encoding="utf-8")[:6000]]
    return "\n".join(lines)


def _ask(harness: str, prompt: str, timeout: int) -> dict[str, Any]:
    started = time.monotonic()
    completed = subprocess.run(
        shlex.split(harness), input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=timeout
    )
    output = completed.stdout.strip()
    try:
        value = json.loads(output)
        answer = str(value.get("result", ""))
        usage = value.get("usage") or {}
        cost = value.get("total_cost_usd")
    except (ValueError, AttributeError):
        answer, usage, cost = output, {}, None
    input_tokens = (
        int(
            usage.get("input_tokens", 0)
            + usage.get("cache_read_input_tokens", 0)
            + usage.get("cache_creation_input_tokens", 0)
        )
        or len(prompt) // 4
    )
    return {
        "answer": answer,
        "input_tokens": input_tokens,
        "output_tokens": int(usage.get("output_tokens", 0)),
        "cost_usd": cost,
        "seconds": round(time.monotonic() - started, 2),
        "exit_code": completed.returncode,
    }


def run(project: Path, cases: list[dict[str, Any]], harness: str, arms: list[str], timeout: int) -> dict[str, Any]:
    packages = project_packages(project)
    results: dict[str, list[dict[str, Any]]] = {arm: [] for arm in arms}
    for case in cases:
        package = packages.get(case["source"])
        if package is None:
            continue
        blocks = _blocks(package)
        prompts = {
            "no_context": f"{INSTRUCTIONS}\n\nQuestion: {case['question']}",
            "raw_corpus": f"{INSTRUCTIONS}\n\nSource text:\n{_raw_corpus(package)}\n\nQuestion: {case['question']}",
            "farol": f"{INSTRUCTIONS}\n\n{_farol_context(package, case['question'])}\n\nQuestion: {case['question']}",
        }
        for arm in arms:
            reply = _ask(harness, prompts[arm], timeout)
            reply["prompt_tokens_estimate"] = len(prompts[arm]) // 4
            results[arm].append({"id": case["id"], **reply, **grade_answer(reply["answer"], case, blocks)})
    summary: dict[str, Any] = {}
    for arm, rows in results.items():
        count = len(rows) or 1
        costs = [row["cost_usd"] for row in rows if row["cost_usd"] is not None]
        summary[arm] = {
            "questions": len(rows),
            "accuracy": round(sum(row["correct"] for row in rows) / count, 3),
            "verified_citation_rate": round(
                sum(1 for row in rows if row["correct"] and row["verified_citations"]) / count, 3
            ),
            "input_tokens": sum(row["input_tokens"] for row in rows),
            "mean_input_tokens": round(sum(row["input_tokens"] for row in rows) / count),
            "mean_prompt_tokens_estimate": round(sum(row["prompt_tokens_estimate"] for row in rows) / count),
            "output_tokens": sum(row["output_tokens"] for row in rows),
            "cost_usd": round(sum(costs), 4) if costs else None,
            "rows": rows,
        }
    return {
        "schema_version": 1,
        "method": {"harness": harness, "arms": arms, "raw_corpus_chars": RAW_CORPUS_CHARS, "top_k": 5},
        "arms": summary,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--harness", required=True, help='e.g. "claude -p --output-format json"')
    parser.add_argument("--arms", default="no_context,raw_corpus,farol")
    parser.add_argument("--only", action="append", help="case ids to run (repeatable)")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    cases = json.loads(args.cases.read_text(encoding="utf-8"))["cases"]
    if args.only:
        cases = [case for case in cases if case["id"] in set(args.only)]
    report = run(args.project.resolve(), cases, args.harness, args.arms.split(","), args.timeout)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
