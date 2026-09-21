# seam-scope: compatibility-infrastructure (release gate boundary fixtures)
from __future__ import annotations

from copy import deepcopy

import pytest

from docops.release_v2 import (
    build_cutover_receipt,
    cutover_metrics_from_arms,
    evaluate_cutover,
    require_cutover_approved,
)
from docops.revisions import content_hash


def _dual_context() -> dict[str, object]:
    return {
        "candidate": "candidate-sha",
        "ir_revision": "ir-sha",
        "golden_revision": "golden-sha",
        "corpus_digest": "c" * 64,
        "environment": {"profile": "cutover", "runtime": "python", "python": "3.14.2"},
    }


def _dual_arm(role: str, *, context: dict[str, object] | None = None, id_parity: float = 1.0) -> dict[str, object]:
    identity = dict(context or _dual_context())
    backend = (
        {"name": "knowledge-rag", "version": "4.8.5"} if role == "legacy" else {"name": "ragflow", "version": "0.27.2"}
    )
    mappings = {"block-1": {"block_id": "block-1", "source": "fixture"}}
    return {
        "ok": True,
        "status": "passed",
        "backend": backend,
        "identity": identity,
        "metrics": {"id_parity": id_parity},
        "lifecycle": {"queryable": True, "recovery": True, "rollback": True},
        "mappings": mappings,
        "mapping_hash": content_hash(mappings),
    }


def _dual_pair(
    *,
    legacy: dict[str, object] | None = None,
    ragflow: dict[str, object] | None = None,
    context: dict[str, object] | None = None,
) -> tuple[dict[str, object] | None, dict[str, object] | None, dict[str, object]]:
    shared = dict(context or _dual_context())
    ragflow_arm = ragflow if ragflow is not None else _dual_arm("ragflow", context=shared)
    ragflow_arm["metrics"] = {"recall_at_5": 1.0, "mrr_at_5": 0.9, "id_parity": 1.0}
    ragflow_arm["coverage"] = {"citation_coverage": 1.0, "lineage_coverage": 1.0}
    legacy_arm = legacy if legacy is not None else _dual_arm("legacy", context=shared)
    return legacy_arm, ragflow_arm, shared


def _valid_receipt() -> tuple[dict[str, object], dict[str, object]]:
    legacy, ragflow, context = _dual_pair()
    metrics = cutover_metrics_from_arms(
        legacy,
        ragflow,
        candidate=context["candidate"],
        ir_revision=context["ir_revision"],
        golden_revision=context["golden_revision"],
        corpus_digest=context["corpus_digest"],
        environment=context["environment"],
        cleanup="passed",
    )
    receipt = build_cutover_receipt(evaluate_cutover(metrics))
    expected_context = {
        "candidate": receipt["candidate"],
        "ir_revision": receipt["ir_revision"],
        "golden_revision": receipt["golden_revision"],
        "corpus_digest": receipt["corpus_digest"],
        "environment": receipt["environment"],
        "backends": receipt["backends"],
        "arm_statuses": receipt["arm_statuses"],
        "arm_identities": receipt["arm_identities"],
        "mapping_hashes": receipt["mapping_hashes"],
        "arm_hashes": receipt["arm_hashes"],
    }
    return receipt, expected_context


def test_cutover_gate_requires_all_measured_thresholds_and_recovery() -> None:
    decision = evaluate_cutover(
        {
            "recall_at_5": 1.0,
            "mrr_at_5": 0.86,
            "citation_coverage": 1.0,
            "lineage_coverage": 1.0,
            "lifecycle": True,
            "recovery": True,
            "rollback": True,
            "ragflow_status": "passed",
        }
    )
    assert decision.status == "cutover_rejected"
    assert decision.legacy_preserved is True


def test_cutover_gate_approves_only_a_complete_measured_pair() -> None:
    receipt, _ = _valid_receipt()

    assert receipt["status"] == "cutover_approved"
    assert receipt["ok"] is True
    assert receipt["legacy_preserved"] is True


def test_cutover_gate_does_not_turn_external_not_run_into_pass() -> None:
    decision = evaluate_cutover(
        {
            "recall_at_5": 1.0,
            "mrr_at_5": 0.9,
            "citation_coverage": 1.0,
            "lineage_coverage": 1.0,
            "lifecycle": True,
            "recovery": True,
            "rollback": True,
            "ragflow_status": "not_run",
        }
    )
    assert decision.status == "not_run"
    assert decision.ok is False


def test_cutover_gate_rejects_below_threshold_without_removing_legacy() -> None:
    legacy, ragflow, context = _dual_pair()
    ragflow["metrics"]["recall_at_5"] = 0.99
    metrics = cutover_metrics_from_arms(
        legacy,
        ragflow,
        candidate=context["candidate"],
        ir_revision=context["ir_revision"],
        golden_revision=context["golden_revision"],
        corpus_digest=context["corpus_digest"],
        environment=context["environment"],
        cleanup="passed",
    )
    decision = evaluate_cutover(metrics)

    assert decision.status == "cutover_rejected"
    assert decision.legacy_preserved is True


def test_cutover_receipt_is_schema_valid_and_binds_its_inputs() -> None:
    receipt, expected_context = _valid_receipt()

    assert receipt["status"] == "cutover_approved"
    assert receipt["kind"] == "cutover_decision"
    assert len(receipt["receipt_hash"]) == 64
    require_cutover_approved(receipt, expected_context=expected_context)
    # The hash binds the exact inputs, so a later edit changes it.
    assert build_cutover_receipt(receipt)["receipt_hash"] == receipt["receipt_hash"]


def test_cutover_receipt_refuses_a_partial_or_forged_payload() -> None:
    with pytest.raises(RuntimeError):
        build_cutover_receipt({"status": "cutover_approved", "ok": True})


def test_cutover_receipt_does_not_promote_an_absent_external_run() -> None:
    decision = evaluate_cutover(
        {
            "recall_at_5": 1.0,
            "mrr_at_5": 0.9,
            "citation_coverage": 1.0,
            "lineage_coverage": 1.0,
            "lifecycle": True,
            "recovery": True,
            "rollback": True,
            "ragflow_status": "blocked",
        }
    )

    receipt = build_cutover_receipt(decision)

    assert receipt["status"] == "not_run"
    assert receipt["ok"] is False
    assert receipt["legacy_preserved"] is True
    with pytest.raises(RuntimeError):
        require_cutover_approved(receipt)


def test_dual_arm_composer_keeps_an_absent_or_blocked_arm_as_not_run() -> None:
    legacy, _, context = _dual_pair()
    assert (
        evaluate_cutover(
            cutover_metrics_from_arms(
                legacy,
                None,
                candidate=context["candidate"],
                ir_revision=context["ir_revision"],
                golden_revision=context["golden_revision"],
                corpus_digest=context["corpus_digest"],
                environment=context["environment"],
                cleanup="not_run",
            )
        ).status
        == "not_run"
    )
    blocked = cutover_metrics_from_arms(
        legacy,
        {"ok": False, "status": "blocked"},
        candidate=context["candidate"],
        ir_revision=context["ir_revision"],
        golden_revision=context["golden_revision"],
        corpus_digest=context["corpus_digest"],
        environment=context["environment"],
        cleanup="not_run",
    )
    assert evaluate_cutover(blocked).status == "not_run"


def test_dual_arm_composer_requires_measured_coverage_and_lifecycle() -> None:
    legacy, ragflow, context = _dual_pair()
    ragflow.pop("coverage")
    ragflow.pop("lifecycle")
    partial = cutover_metrics_from_arms(
        legacy,
        ragflow,
        candidate=context["candidate"],
        ir_revision=context["ir_revision"],
        golden_revision=context["golden_revision"],
        corpus_digest=context["corpus_digest"],
        environment=context["environment"],
        cleanup="passed",
    )
    assert evaluate_cutover(partial).status == "cutover_rejected"


def test_dual_arm_composer_promotes_only_a_complete_measured_pair() -> None:
    legacy, ragflow, context = _dual_pair()
    metrics = cutover_metrics_from_arms(
        legacy,
        ragflow,
        candidate=context["candidate"],
        ir_revision=context["ir_revision"],
        golden_revision=context["golden_revision"],
        corpus_digest=context["corpus_digest"],
        environment=context["environment"],
        cleanup="passed",
    )
    receipt = build_cutover_receipt(evaluate_cutover(metrics))
    assert receipt["status"] == "cutover_approved"
    assert receipt["candidate"] == "candidate-sha"


def test_cutover_requires_a_valid_legacy_arm() -> None:
    legacy, ragflow, context = _dual_pair()
    legacy["ok"] = False

    decision = evaluate_cutover(
        cutover_metrics_from_arms(
            legacy,
            ragflow,
            candidate=context["candidate"],
            ir_revision=context["ir_revision"],
            golden_revision=context["golden_revision"],
            corpus_digest=context["corpus_digest"],
            environment=context["environment"],
            cleanup="passed",
        )
    )

    assert decision.status == "cutover_rejected"
    assert decision.legacy_preserved is True


@pytest.mark.parametrize(
    "identity_key", ["candidate", "ir_revision", "golden_revision", "corpus_digest", "environment"]
)
def test_cutover_rejects_divergent_arm_identity(identity_key: str) -> None:
    legacy, ragflow, context = _dual_pair()
    if identity_key == "environment":
        ragflow["identity"]["environment"] = {"profile": "different", "runtime": "python", "python": "3.14.2"}
    else:
        ragflow["identity"][identity_key] = "different"

    decision = evaluate_cutover(
        cutover_metrics_from_arms(
            legacy,
            ragflow,
            candidate=context["candidate"],
            ir_revision=context["ir_revision"],
            golden_revision=context["golden_revision"],
            corpus_digest=context["corpus_digest"],
            environment=context["environment"],
            cleanup="passed",
        )
    )

    assert decision.status == "cutover_rejected"
    assert decision.legacy_preserved is True


@pytest.mark.parametrize(
    ("field", "value"),
    [("name", "other-rag"), ("version", "0.27.1")],
)
def test_cutover_rejects_backend_divergence(field: str, value: str) -> None:
    legacy, ragflow, context = _dual_pair()
    ragflow["backend"][field] = value

    decision = evaluate_cutover(
        cutover_metrics_from_arms(
            legacy,
            ragflow,
            candidate=context["candidate"],
            ir_revision=context["ir_revision"],
            golden_revision=context["golden_revision"],
            corpus_digest=context["corpus_digest"],
            environment=context["environment"],
            cleanup="passed",
        )
    )

    assert decision.status == "cutover_rejected"
    assert decision.legacy_preserved is True


@pytest.mark.parametrize("arm_role", ["legacy", "ragflow"])
@pytest.mark.parametrize("id_parity", [None, 0.99])
def test_cutover_requires_id_parity_gate(arm_role: str, id_parity: float | None) -> None:
    legacy, ragflow, context = _dual_pair()
    arm = legacy if arm_role == "legacy" else ragflow
    if id_parity is None:
        arm["metrics"].pop("id_parity")
    else:
        arm["metrics"]["id_parity"] = id_parity

    decision = evaluate_cutover(
        cutover_metrics_from_arms(
            legacy,
            ragflow,
            candidate=context["candidate"],
            ir_revision=context["ir_revision"],
            golden_revision=context["golden_revision"],
            corpus_digest=context["corpus_digest"],
            environment=context["environment"],
            cleanup="passed",
        )
    )

    assert decision.status == "cutover_rejected"
    assert decision.legacy_preserved is True


def test_cutover_receipt_rejects_incomplete_gates() -> None:
    receipt, _ = _valid_receipt()
    receipt["gates"].pop("id_parity")

    with pytest.raises(RuntimeError):
        build_cutover_receipt(receipt)


def test_cutover_receipt_recomposes_mapping_hashes() -> None:
    receipt, _ = _valid_receipt()
    receipt["mappings"]["legacy"]["block-1"]["source"] = "tampered"

    with pytest.raises(RuntimeError):
        build_cutover_receipt(receipt)


def test_cutover_receipt_rejects_an_incorrect_receipt_hash() -> None:
    receipt, _ = _valid_receipt()
    receipt["receipt_hash"] = "0" * 64

    with pytest.raises(RuntimeError):
        build_cutover_receipt(receipt)


def test_cutover_receipt_rejects_a_stale_expected_context() -> None:
    receipt, expected_context = _valid_receipt()
    stale = deepcopy(expected_context)
    stale["candidate"] = "newer-candidate"

    with pytest.raises(RuntimeError):
        require_cutover_approved(receipt, expected_context=stale)


def test_cutover_guard_requires_current_context_not_just_status_and_ok() -> None:
    with pytest.raises(RuntimeError):
        require_cutover_approved({"status": "cutover_approved", "ok": True})
