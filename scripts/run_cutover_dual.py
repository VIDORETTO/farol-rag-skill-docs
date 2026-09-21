"""Compose two backend arm reports into a validated Farol 2.0 cutover receipt.

TK-018 measures the same IR/candidate against the retained migration arm and
RAGFlow and decides whether the legacy contraction may proceed. This runner
never invents a measurement: it reads the per-arm reports produced by the
cutover measurement profile, composes them through
``cutover_metrics_from_arms`` and emits a receipt that must satisfy the
canonical ``cutover-decision`` schema.

An absent or non-``passed`` RAGFlow arm yields ``not_run`` and preserves the
legacy backend. Only a complete, measured pair may reach ``cutover_approved``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from docops.release_v2 import build_cutover_receipt, cutover_metrics_from_arms, evaluate_cutover  # noqa: E402


def _read_report(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def run(
    *,
    legacy_report: Path | None,
    ragflow_report: Path | None,
    candidate: str | None,
    golden_revision: str | None,
    corpus_digest: str | None,
    environment: dict[str, Any] | None,
    cleanup: str | None,
    ir_revision: str | None = None,
) -> tuple[dict[str, Any], int]:
    metrics = cutover_metrics_from_arms(
        _read_report(legacy_report),
        _read_report(ragflow_report),
        candidate=candidate,
        ir_revision=ir_revision,
        golden_revision=golden_revision,
        corpus_digest=corpus_digest,
        environment=environment,
        cleanup=cleanup,
    )
    decision = evaluate_cutover(metrics)
    receipt = build_cutover_receipt(decision)
    if receipt["status"] == "cutover_approved":
        return receipt, 0
    if receipt["status"] == "cutover_rejected":
        return receipt, 1
    return receipt, 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-report", type=Path, help="JSON report from the legacy backend arm")
    parser.add_argument("--ragflow-report", type=Path, help="JSON report from the RAGFlow arm")
    parser.add_argument("--candidate")
    parser.add_argument("--ir-revision")
    parser.add_argument("--golden-revision")
    parser.add_argument("--corpus-digest")
    parser.add_argument("--cleanup", choices=("passed", "failed", "not_required"))
    parser.add_argument("--environment", type=Path, help="JSON object describing the measured environment")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    environment = _read_report(args.environment) if args.environment else None
    receipt, code = run(
        legacy_report=args.legacy_report,
        ragflow_report=args.ragflow_report,
        candidate=args.candidate,
        ir_revision=args.ir_revision,
        golden_revision=args.golden_revision,
        corpus_digest=args.corpus_digest,
        environment=environment,
        cleanup=args.cleanup,
    )
    print(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
