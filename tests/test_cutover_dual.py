# seam-scope: compatibility-infrastructure (cutover dual-run boundary fixtures)
from __future__ import annotations

import json
from pathlib import Path

from docops.revisions import content_hash
from scripts.run_cutover_dual import run


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _arm(
    role: str,
    *,
    candidate: str,
    ir_revision: str,
    golden_revision: str,
    corpus_digest: str,
    environment: dict[str, str],
    recall: float = 1.0,
) -> dict:
    mappings = {"block-1": {"block_id": "block-1", "source": "fixture"}}
    metrics = {"id_parity": 1.0}
    if role == "ragflow":
        metrics.update({"recall_at_5": recall, "mrr_at_5": 0.9})
    return {
        "ok": True,
        "status": "passed",
        "backend": {
            "name": "knowledge-rag" if role == "legacy" else "ragflow",
            "version": "4.8.5" if role == "legacy" else "0.27.2",
        },
        "identity": {
            "candidate": candidate,
            "ir_revision": ir_revision,
            "golden_revision": golden_revision,
            "corpus_digest": corpus_digest,
            "environment": environment,
        },
        "metrics": metrics,
        "coverage": ({} if role == "legacy" else {"citation_coverage": 1.0, "lineage_coverage": 1.0}),
        "lifecycle": {"queryable": True, "recovery": True, "rollback": True},
        "mappings": mappings,
        "mapping_hash": content_hash(mappings),
    }


def test_dual_runner_blocks_without_a_passed_ragflow_arm(tmp_path: Path) -> None:
    legacy = _write(tmp_path / "legacy.json", {"ok": True, "status": "passed", "metrics": {"id_parity": 1.0}})

    receipt, code = run(
        legacy_report=legacy,
        ragflow_report=None,
        candidate="candidate-sha",
        golden_revision=None,
        corpus_digest=None,
        environment=None,
        cleanup=None,
    )

    assert code == 2
    assert receipt["status"] == "not_run"
    assert receipt["legacy_preserved"] is True


def test_dual_runner_approves_only_a_complete_measured_pair(tmp_path: Path) -> None:
    context = {
        "candidate": "candidate-sha",
        "ir_revision": "ir-rev-1",
        "golden_revision": "golden-rev-1",
        "corpus_digest": "a" * 64,
        "environment": {"profile": "cutover", "runtime": "python", "python": "3.14.2"},
    }
    legacy = _write(tmp_path / "legacy.json", _arm("legacy", **context))
    ragflow = _write(tmp_path / "ragflow.json", _arm("ragflow", **context))

    receipt, code = run(
        legacy_report=legacy,
        ragflow_report=ragflow,
        candidate=context["candidate"],
        ir_revision=context["ir_revision"],
        golden_revision="golden-rev-1",
        corpus_digest="a" * 64,
        environment=context["environment"],
        cleanup="passed",
    )

    assert code == 0
    assert receipt["status"] == "cutover_approved"
    assert receipt["candidate"] == "candidate-sha"
    assert receipt["receipt_hash"]


def test_dual_runner_rejects_below_threshold_but_keeps_legacy(tmp_path: Path) -> None:
    context = {
        "candidate": "candidate-sha",
        "ir_revision": "ir-rev-1",
        "golden_revision": "golden-rev-1",
        "corpus_digest": "a" * 64,
        "environment": {"profile": "cutover", "runtime": "python", "python": "3.14.2"},
    }
    legacy = _write(tmp_path / "legacy.json", _arm("legacy", **context))
    ragflow = _write(tmp_path / "ragflow.json", _arm("ragflow", **context, recall=0.99))

    receipt, code = run(
        legacy_report=legacy,
        ragflow_report=ragflow,
        candidate=context["candidate"],
        ir_revision=context["ir_revision"],
        golden_revision=context["golden_revision"],
        corpus_digest=context["corpus_digest"],
        environment=context["environment"],
        cleanup=None,
    )

    assert code == 1
    assert receipt["status"] == "cutover_rejected"
    assert receipt["legacy_preserved"] is True
