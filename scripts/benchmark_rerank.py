"""Benchmark candidate rerankers on the acceptance corpus (TK-204, decision D-301).

Uses the packages already built by ``scripts/acceptance_real.py`` in
``--work-dir`` and the golden cases (test, validation and Portuguese splits).
For each candidate model it reports recall@5, MRR@5 and latency (p50/p95) with
and without reranking. A model that cannot be loaded (extra missing, download
blocked) is ``not_run``, never a pass.

    python scripts/benchmark_rerank.py --work-dir data/acceptance --json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from docops.mcp_server import KnowledgeServer  # noqa: E402
from docops.ranking import RERANKER_LICENSES, load_reranker  # noqa: E402

DEFAULT_MODELS = ("BAAI/bge-reranker-base", "Xenova/ms-marco-MiniLM-L-12-v2")
GOLDEN = PROJECT_ROOT / "golden-set" / "real"


def _normalize(value: str) -> str:
    return " ".join(value.replace("`", "").casefold().split())


def _cases(path: Path) -> list[dict[str, Any]]:
    return [case for case in json.loads(path.read_text(encoding="utf-8"))["cases"] if case.get("kind") == "factual"]


def _measure(server: KnowledgeServer, cases: list[dict[str, Any]]) -> dict[str, Any]:
    reciprocal: list[float] = []
    latencies: list[float] = []
    for case in cases:
        started = time.perf_counter()
        hits = server.search_knowledge(case["question"], top_k=5)["hits"]
        latencies.append((time.perf_counter() - started) * 1000)
        wanted = _normalize(case["expected_text"])
        rank = next((position for position, hit in enumerate(hits, 1) if wanted in _normalize(hit["text"])), None)
        reciprocal.append(1.0 / rank if rank else 0.0)
    total = len(cases) or 1
    ordered = sorted(latencies) or [0.0]
    return {
        "cases": len(cases),
        "recall_at_5": round(sum(1 for value in reciprocal if value) / total, 4),
        "mrr_at_5": round(sum(reciprocal) / total, 4),
        "latency_ms_p50": round(statistics.median(ordered), 1),
        "latency_ms_p95": round(ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))], 1),
    }


def _splits(server: KnowledgeServer, source: str, test: list[dict], validation: list[dict]) -> dict[str, Any]:
    mine = [case for case in test if case["source"] == source]
    groups = {
        "en": [case for case in mine if case.get("language", "en") == "en"],
        "pt": [case for case in mine if case.get("language") == "pt"],
        "validation": [case for case in validation if case["source"] == source],
    }
    return {name: _measure(server, cases) for name, cases in groups.items() if cases}


def run(work: Path, models: list[str]) -> dict[str, Any]:
    test, validation = _cases(GOLDEN / "cases.json"), _cases(GOLDEN / "validation-cases.json")
    packages = {
        path.parent.name: path
        for path in sorted(work.glob("*/package"))
        if (path / "rag" / "local-index" / "ACTIVE.json").is_file()
    }
    if not packages:
        return {"status": "not_run", "code": "acceptance_packages_missing"}
    report: dict[str, Any] = {"schema_version": 1, "status": "measured", "baseline": {}, "models": {}}
    for source, package in packages.items():
        report["baseline"][source] = _splits(KnowledgeServer(package), source, test, validation)
    for model in models:
        ranker, problem = load_reranker(model)
        entry: dict[str, Any] = {"license": RERANKER_LICENSES.get(model, "unknown")}
        if ranker is None:
            entry.update(status="not_run", code=str(problem))
        else:
            entry["status"] = "measured"
            entry["sources"] = {
                source: _splits(KnowledgeServer(package, ranker=ranker), source, test, validation)
                for source, package in packages.items()
            }
        report["models"][model] = entry
    if not any(entry["status"] == "measured" for entry in report["models"].values()):
        report["status"] = "not_run"
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--work-dir", type=Path, default=PROJECT_ROOT / "data" / "acceptance")
    parser.add_argument("--model", action="append", help="candidate model (repeatable)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = run(args.work_dir, args.model or list(DEFAULT_MODELS))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "measured" else 1


if __name__ == "__main__":
    raise SystemExit(main())
