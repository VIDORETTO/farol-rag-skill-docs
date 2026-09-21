"""Run the provider-free P0-P5 master-evolution protocol on synthetic data."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from docops import (  # noqa: E402
    activate_project_change,
    answer_project_init,
    authorize_factual_change,
    backup_project,
    create_delegated_authorization,
    finalize_project_init,
    ingest_external_transcription,
    inspect_project_recovery,
    load_project_preset,
    prepare_project_change,
    propose_project_change,
    query_project_evidence,
    record_project_claim,
    record_project_conflict,
    recover_project_activation,
    register_source_governance,
    restore_project,
    revoke_delegated_authorization,
    revoke_project_source,
    start_project_init,
)
from docops.revisions import content_hash  # noqa: E402

NOW = "2026-09-08T12:00:00Z"
LATER = "2027-01-01T00:00:00Z"


def _require(result: dict[str, Any], label: str) -> dict[str, Any]:
    if result.get("ok") is not True:
        raise RuntimeError(f"{label} failed: {result.get('errors')}")
    return result


def _step(steps: list[dict[str, Any]], name: str, action: Callable[[], Any]) -> Any:
    try:
        value = action()
    except Exception as exc:  # pragma: no cover - the report is the assertion surface
        steps.append({"name": name, "status": "failed", "error": str(exc)})
        raise
    steps.append({"name": name, "status": "passed"})
    return value


def run_fixture() -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="docops-master-fixture-") as temporary:
        root = Path(temporary) / "project"
        started = _step(
            steps,
            "init-start",
            lambda: _require(
                start_project_init(
                    root,
                    {"name": "Synthetic master project", "deliverables": ["knowledge"]},
                    now=NOW,
                ),
                "init-start",
            ),
        )
        session_id = started["data"]["session"]["session_id"]
        answered = _step(
            steps,
            "init-resume-and-answer",
            lambda: _require(
                answer_project_init(
                    root,
                    session_id=session_id,
                    answers={"objective": "Prove the synthetic master protocol"},
                    expected_revision=started["session_revision"],
                    now=NOW,
                ),
                "init-answer",
            ),
        )
        finalized = _step(
            steps,
            "init-finalize",
            lambda: _require(
                finalize_project_init(
                    root,
                    session_id=session_id,
                    expected_revision=answered["session_revision"],
                    now=NOW,
                ),
                "init-finalize",
            ),
        )

        grants = [
            {
                "purpose": purpose,
                "decision": "allowed",
                "evidence_ref": "fixture-permission",
                "actor": "fixture",
                "valid_until": LATER,
            }
            for purpose in ("acquisition", "storage", "internal_query", "indexing", "quotation", "derivatives")
        ]
        grants.append({"purpose": "redistribution", "decision": "denied"})
        _step(
            steps,
            "source-governance",
            lambda: _require(
                register_source_governance(
                    root,
                    {
                        "source_id": "fixture-video",
                        "observed_revision": "video-revision-1",
                        "source_type": "video_transcript",
                        "authority_class": "practitioner",
                        "captured_at": NOW,
                        "use_policy": {"grants": grants},
                        "privacy": {"classification": "internal", "redaction_required": True},
                    },
                    now=NOW,
                ),
                "source-governance",
            ),
        )
        _step(
            steps,
            "timestamped-transcription",
            lambda: _require(
                ingest_external_transcription(
                    root,
                    "fixture-video",
                    "[00:10-00:20] Synthetic fact one\n[00:20-00:30] Synthetic fact two",
                    video_url="https://example.test/fixture",
                    provider="synthetic",
                    permission_ref="fixture-permission",
                    now=NOW,
                ),
                "transcription",
            ),
        )
        refs = [
            {
                "source_id": "fixture-video",
                "observed_revision": "video-revision-1",
                "document_id": "fixture-video.md",
                "content_hash": "a" * 64,
                "locator": {"kind": "timestamp", "value": "10000-20000", "end": "20000"},
            }
        ]
        _step(
            steps,
            "claim-supported",
            lambda: _require(
                record_project_claim(
                    root,
                    {
                        "claim_id": "claim-a",
                        "text": "Synthetic fact one",
                        "classification": "factual_observation",
                        "evidence_refs": refs,
                    },
                    now=NOW,
                ),
                "claim-a",
            ),
        )
        _step(
            steps,
            "claim-opinion",
            lambda: _require(
                record_project_claim(
                    root,
                    {
                        "claim_id": "claim-b",
                        "text": "Synthetic fact one is useful",
                        "classification": "opinion",
                        "evidence_refs": refs,
                    },
                    now=NOW,
                ),
                "claim-b",
            ),
        )
        _step(
            steps,
            "conflict-record",
            lambda: _require(
                record_project_conflict(
                    root,
                    {"conflict_id": "conflict-ab", "claim_ids": ["claim-a", "claim-b"], "relation": "scope_difference"},
                    now=NOW,
                ),
                "conflict",
            ),
        )
        queried = _step(
            steps, "evidence-query-conflicting", lambda: query_project_evidence(root, "Synthetic fact one", now=NOW)
        )
        if queried.get("data", {}).get("outcome") != "conflicting":
            raise RuntimeError(f"conflict outcome was not preserved: {queried}")
        steps[-1]["outcome"] = queried["data"]["outcome"]
        _step(
            steps,
            "source-revocation",
            lambda: _require(revoke_project_source(root, "fixture-video", now=NOW), "source-revocation"),
        )
        revoked = query_project_evidence(root, "Synthetic fact one", now=NOW)
        if revoked.get("data", {}).get("outcome") != "insufficient_evidence":
            raise RuntimeError(f"revoked source remained eligible: {revoked}")
        steps.append({"name": "revocation-filter", "status": "passed", "outcome": revoked["data"]["outcome"]})

        base_revision = finalized["data"]["project_revision_id"]
        policy_path = root / "revisions" / base_revision / "policy.json"
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        change = _step(
            steps,
            "change-propose-prepare",
            lambda: _require(
                propose_project_change(
                    root,
                    {
                        "change_id": "change-crash-fixture",
                        "base_project_revision_id": base_revision,
                        "operations": [
                            {
                                "type": "policy_change",
                                "target_id": policy["id"],
                                "expected_hash": policy["content_hash"],
                                "payload": {"private_draft_only": True},
                            }
                        ],
                        "requested_by": "fixture",
                        "reason": "exercise atomic activation recovery",
                        "dependency_graph": {"nodes": [], "edges": [], "unknown_dependencies": False},
                    },
                    now=NOW,
                ),
                "change-propose",
            ),
        )
        prepared = _require(
            prepare_project_change(root, change["data"]["change"]["change_id"], now=NOW), "change-prepare"
        )
        steps[-1]["prepared_revision_id"] = prepared["data"]["receipt"]["project_revision_id"]
        crash_before = os.environ.get("DOCOPS_TEST_PROJECT_CRASH_AFTER_POINTER")
        os.environ["DOCOPS_TEST_PROJECT_CRASH_AFTER_POINTER"] = "1"
        try:
            try:
                activate_project_change(root, "change-crash-fixture", manual_reviewed=True, now=NOW)
            except RuntimeError:
                pass
            else:
                raise RuntimeError("synthetic activation crash was not observed")
        finally:
            if crash_before is None:
                os.environ.pop("DOCOPS_TEST_PROJECT_CRASH_AFTER_POINTER", None)
            else:
                os.environ["DOCOPS_TEST_PROJECT_CRASH_AFTER_POINTER"] = crash_before
        recovery = _step(steps, "activation-recovery", lambda: inspect_project_recovery(root))
        if recovery.get("status") not in {"pending", "clean"}:
            raise RuntimeError(f"unexpected recovery state: {recovery}")
        _step(steps, "activation-recover", lambda: _require(recover_project_activation(root), "activation-recover"))

        (root / ".docops").mkdir(exist_ok=True)
        (root / ".docops" / "tombstones.json").write_text(
            json.dumps({"tombstones": ["fixture-video"]}), encoding="utf-8"
        )
        backup_root = root.parent / "backup"
        backup_started = time.perf_counter()
        backup_result = _step(steps, "backup", lambda: _require(backup_project(root, backup_root, now=NOW), "backup"))
        backup_elapsed = round(time.perf_counter() - backup_started, 6)
        restore_started = time.perf_counter()
        restore_result = _step(
            steps,
            "restore",
            lambda: _require(
                restore_project(backup_root, root.parent / "restored", current_root=root, now=NOW), "restore"
            ),
        )
        restore_elapsed = round(time.perf_counter() - restore_started, 6)
        backup_timestamp = backup_result["data"]["manifest"]["rpo_observed_at"]
        source_timestamp = NOW
        rpo_seconds = (
            datetime.fromisoformat(backup_timestamp.replace("Z", "+00:00"))
            - datetime.fromisoformat(source_timestamp.replace("Z", "+00:00"))
        ).total_seconds()
        steps[-2].update({"rpo_seconds": rpo_seconds, "backup_seconds": backup_elapsed})
        steps[-1].update({"rto_seconds": restore_elapsed, "restore_ok": restore_result.get("ok") is True})

        current_revision = json.loads((root / "project.json").read_text(encoding="utf-8"))["active_project_revision_id"]
        factual_change = _require(
            propose_project_change(
                root,
                {
                    "change_id": "change-revoked-delegation",
                    "base_project_revision_id": current_revision,
                    "operations": [
                        {
                            "type": "source_add",
                            "target_id": "fixture-new-source",
                            "payload": {"source_type": "article", "captured_at": NOW},
                        }
                    ],
                    "requested_by": "fixture",
                    "reason": "exercise revoked delegation",
                    "dependency_graph": {"nodes": [], "edges": [], "unknown_dependencies": False},
                },
                now=NOW,
            ),
            "delegated-change-propose",
        )
        _step(
            steps,
            "delegation-create-and-revoke",
            lambda: _require(
                create_delegated_authorization(
                    root,
                    {
                        "authorization_id": "fixture-auth",
                        "owner": "fixture",
                        "actions": ["source_update"],
                        "source_ids": ["fixture-new-source"],
                        "authority_ref": "fixture-attestation",
                        "expires_at": LATER,
                        "budget": {"max_operations": 1, "used_operations": 0},
                    },
                    now=NOW,
                ),
                "delegation-create",
            ),
        )
        _require(revoke_delegated_authorization(root, "fixture-auth", now=NOW), "delegation-revoke")
        blocked = authorize_factual_change(root, factual_change["data"]["change"]["change_id"], "fixture-auth", now=NOW)
        if blocked.get("ok") is not False or blocked.get("errors", [{}])[0].get("code") != "RIGHTS_BLOCKED":
            raise RuntimeError(f"revoked delegation was not blocked: {blocked}")
        steps.append({"name": "delegation-revoked-block", "status": "passed", "code": blocked["errors"][0]["code"]})

        neutral = load_project_preset("neutral")
        generic = load_project_preset("generic")
        steps.append(
            {
                "name": "presets-neutral-and-generic",
                "status": "passed",
                "neutral_themes": len(neutral["themes"]),
                "generic_id": generic["id"],
            }
        )
        return {
            "schema_version": 1,
            "ok": True,
            "fixture": "master-evolution-provider-free-v1",
            "temporary_root": str(root),
            "steps": steps,
            "recovery_metrics": {
                "rpo_seconds": rpo_seconds,
                "backup_seconds": backup_elapsed,
                "rto_seconds": restore_elapsed,
            },
            "external_state_changed": False,
            "limitations": [
                "External RAGFlow retrieval, real corpus/index rebuild, commercial authority and publication credentials were not exercised by design.",
                "The fixture proves blocked outcomes for those boundaries; it does not grant external authorization.",
            ],
            "identity": content_hash(
                {"fixture": "master-evolution-provider-free-v1", "steps": [item["name"] for item in steps]}
            ),
        }


def main() -> int:
    try:
        report = run_fixture()
    except Exception as exc:
        print(
            json.dumps(
                {"schema_version": 1, "ok": False, "fixture": "master-evolution-provider-free-v1", "error": str(exc)},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
