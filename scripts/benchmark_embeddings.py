"""Benchmark candidate embedding models on the acceptance corpus (TK-205, decision D-302).

Rebuilds the local index of each package already built by
``scripts/acceptance_real.py`` in ``--work-dir`` with every candidate model and
reports recall@5 / MRR@5 per split (English, Portuguese, validation) plus build
time. The packages' active index is left on the last model measured, so point
``--work-dir`` at a scratch copy. A model that cannot be loaded is ``not_run``.

Adopt a new default only if D-302 holds: validation recall@5 +0.05 or more and
the 500-page book builds in at most 3x the current time.

    python scripts/benchmark_embeddings.py --work-dir <copy-of-acceptance-dir> --json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from docops.backends import QueryRequest  # noqa: E402
from docops.backends.semantic import DEFAULT_MODEL, FastEmbedEmbedder  # noqa: E402
from docops.package_index import build_package_index, open_package_index  # noqa: E402

CANDIDATES = (
    DEFAULT_MODEL,
    "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    "intfloat/multilingual-e5-large",
    "Qwen/Qwen3-Embedding-0.6B-Q",
    "minishlab/potion-multilingual-128M",
)
GOLDEN = PROJECT_ROOT / "golden-set" / "real"


def _normalize(value: str) -> str:
    return " ".join(value.replace("`", "").casefold().split())


def _cases(path: Path) -> list[dict[str, Any]]:
    return [case for case in json.loads(path.read_text(encoding="utf-8"))["cases"] if case.get("kind") == "factual"]


def _score(backend: Any, index: Any, cases: list[dict[str, Any]]) -> dict[str, Any]:
    reciprocal = []
    for case in cases:
        hits = backend.query(index, QueryRequest(query=case["question"], top_k=5)).hits
        wanted = _normalize(case["expected_text"])
        rank = next((position for position, hit in enumerate(hits, 1) if wanted in _normalize(hit["text"])), None)
        reciprocal.append(1.0 / rank if rank else 0.0)
    total = len(cases) or 1
    return {
        "cases": len(cases),
        "recall_at_5": round(sum(1 for value in reciprocal if value) / total, 4),
        "mrr_at_5": round(sum(reciprocal) / total, 4),
    }


def run(work: Path, models: list[str]) -> dict[str, Any]:
    test, validation = _cases(GOLDEN / "cases.json"), _cases(GOLDEN / "validation-cases.json")
    packages = {path.parent.name: path for path in sorted(work.glob("*/package")) if (path / "manifest.json").is_file()}
    if not packages:
        return {"status": "not_run", "code": "acceptance_packages_missing"}
    report: dict[str, Any] = {"schema_version": 1, "status": "not_run", "models": {}}
    for model in models:
        try:
            embedder = FastEmbedEmbedder(model)
        except Exception as exc:  # extra missing or download blocked
            report["models"][model] = {
                "status": "not_run",
                "code": "embedding_model_unavailable",
                "detail": type(exc).__name__,
            }
            continue
        entry: dict[str, Any] = {"status": "measured", "profile": embedder.profile, "sources": {}}
        for source, package in packages.items():
            started = time.perf_counter()
            build_package_index(package, embedder=embedder)
            seconds = round(time.perf_counter() - started, 1)
            backend, index = open_package_index(package, embedder=embedder)
            mine = [case for case in test if case["source"] == source]
            splits = {
                "en": [case for case in mine if case.get("language", "en") == "en"],
                "pt": [case for case in mine if case.get("language") == "pt"],
                "validation": [case for case in validation if case["source"] == source],
            }
            entry["sources"][source] = {
                "build_seconds": seconds,
                **{name: _score(backend, index, cases) for name, cases in splits.items() if cases},
            }
        report["models"][model] = entry
        report["status"] = "measured"
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--model", action="append", help="candidate model (repeatable)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = run(args.work_dir, args.model or list(CANDIDATES))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "measured" else 1


if __name__ == "__main__":
    raise SystemExit(main())
