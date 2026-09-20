"""Check normative DOCOPS schemas against representative public envelopes."""

from __future__ import annotations

import argparse
import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from docops import OperationOptions  # noqa: E402
from docops.contracts import contract_names, load_schema, schema_path, validate_artifact  # noqa: E402
from docops.harness import build_harness_manifest  # noqa: E402
from docops.manifest import build_manifest  # noqa: E402
from docops.operations import plan as build_plan  # noqa: E402
from docops.package_validator import ValidationResult  # noqa: E402
from docops.revisions import content_hash  # noqa: E402
from docops.source_resolver import SourceResolver  # noqa: E402
from scripts.sync_schemas import check_schema_distribution  # noqa: E402


def _schema_policy_findings() -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    policy = ROOT / "docs" / "CONTRACT-COMPATIBILITY.md"
    if not policy.is_file():
        return [{"code": "compatibility_policy_missing", "artifact": "documentation", "message": str(policy)}]
    try:
        policy_text = policy.read_text(encoding="utf-8").casefold()
    except (OSError, UnicodeError) as exc:
        return [{"code": "compatibility_policy_unreadable", "artifact": "documentation", "message": str(exc)}]
    for marker in ("schema_version", "expand-contract", "fail closed"):
        if marker not in policy_text:
            findings.append(
                {
                    "code": "compatibility_policy_incomplete",
                    "artifact": "documentation",
                    "message": f"compatibility policy is missing {marker!r}",
                }
            )
    for name in contract_names():
        try:
            schema = load_schema(name)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            findings.append({"code": "schema_unavailable", "artifact": name, "message": str(exc)})
            continue
        required = schema.get("required")
        properties = schema.get("properties")
        version_rule = properties.get("schema_version") if isinstance(properties, dict) else None
        if not isinstance(required, list) or "schema_version" not in required:
            findings.append(
                {"code": "schema_version_missing", "artifact": name, "message": "schema_version is required"}
            )
        if not isinstance(version_rule, dict) or not isinstance(version_rule.get("const"), int):
            findings.append(
                {
                    "code": "schema_version_undeclared",
                    "artifact": name,
                    "message": "schema_version.const must declare an integer version",
                }
            )
    return findings


def _examples() -> dict[str, object]:
    resolution = SourceResolver().resolve("https://docs.example.test/guide")
    with tempfile.TemporaryDirectory() as temporary:
        source = Path(temporary) / "source.md"
        source.write_text("# Guide\n", encoding="utf-8")
        operation = build_plan(
            source,
            options=OperationOptions(output_dir=Path(temporary) / "package", slug="guide", license="MIT"),
        )
        plan_example = operation.to_dict()
    return {
        "manifest": build_manifest(
            resolution,
            entries=[],
            provenance={"license": "MIT", "redistribution": "private-only"},
            artifacts={"skill": "skill", "router": "router", "rag": "rag"},
        ),
        "harness": build_harness_manifest(ROOT),
        "golden": {
            "schema_version": 1,
            "reviewed": True,
            "cases": [{"query": "guide", "expected_filepath": "guide.md", "reviewed": True}],
        },
        "validation": ValidationResult(True).to_dict(),
        "outcome": {
            "schema_version": 1,
            "status": "succeeded",
            "code": "completed",
            "phase": "validate",
            "message": "ok",
            "exit_code": 0,
        },
        "plan": plan_example,
        "result": {
            "schema_version": 1,
            "ok": True,
            "outcome": {
                "schema_version": 1,
                "status": "succeeded",
                "code": "completed",
                "phase": "validate",
                "message": "ok",
                "exit_code": 0,
            },
            "manifest": {},
            "validation": ValidationResult(True).to_dict(),
            "state_diff": {"added": 0, "updated": 0, "removed": 0},
            "written_files": 0,
            "errors": [],
            "warnings": [],
        },
        "evaluation": {
            "schema_version": 1,
            "ok": True,
            "metrics": {"recall_at_5": 1.0, "mrr_at_5": 1.0},
            "cases": [],
            "errors": [],
            "warnings": [],
            "diagnostics": [],
            "thresholds": {"recall_at_5": 0.85, "mrr_at_5": 0.7},
            "metadata": {"backend": "memory", "mode": "test"},
        },
        "golden-candidates": {
            "schema_version": 1,
            "reviewed": False,
            "cases": [{"query": "guide", "expected_filepath": "guide.md", "reviewed": False, "review_note": "review"}],
        },
        "enrichment-request": {
            "schema_version": 1,
            "request_id": "enrichment-request-fixture",
            "candidate_id": "candidate-" + "a" * 32,
            "base_release_id": "release-fixture",
            "base_composition_hash": "b" * 64,
            "snapshot": {
                "candidate_revisions": {"composition_hash": "c" * 64},
                "input_hashes": {"skill": "d" * 64, "router": "e" * 64},
            },
            "diff": {"kind": "conceptual_enrichment", "layers": ["conceptual"]},
            "allowed_artifacts": ["skill", "router"],
            "policy_revision": "policy-fixture",
            "language": "pt-BR",
            "budget": {"max_files": 4, "max_bytes": 2000000},
        },
        "enrichment-receipt": {
            "schema_version": 1,
            "request_id": "enrichment-request-fixture",
            "candidate_id": "candidate-" + "a" * 32,
            "base_release_id": "release-fixture",
            "base_composition_hash": "b" * 64,
            "candidate_composition_hash": "c" * 64,
            "tool": {"name": "book-to-skill", "version": "fixture"},
            "inputs": [{"path": "skill", "sha256": "d" * 64}],
            "outputs": [{"path": "skill/SKILL.md", "sha256": "f" * 64}],
            "validation": {"ok": True},
            "provenance": {"source": "synthetic"},
            "usage": {"files": 1},
        },
        "evaluation-receipt": {
            "schema_version": 1,
            "generation_id": "generation-fixture",
            "candidate_id": "candidate-" + "a" * 32,
            "package_composition_hash": "b" * 64,
            "golden_revision": "c" * 64,
            "rubric_revision": "rubric-fixture",
            "evaluator": {"name": "response-judge", "version": "fixture", "independent": True},
            "cases": [
                {
                    "case_id": "case-fixture",
                    "critical": False,
                    "claims": [
                        {
                            "claim_id": "claim-fixture",
                            "supported": True,
                            "requires_citation": True,
                            "citations": ["guide.md"],
                        }
                    ],
                }
            ],
        },
        "approval": {
            "schema_version": 1,
            "approval_id": "approval-fixture",
            "candidate_id": "candidate-" + "a" * 32,
            "status": "approved",
            "approval_kind": "conceptual_manual",
            "actor": {"id": "editor@example.test", "role": "human_approver"},
            "base_release_id": "release-base",
            "base_composition_hash": "b" * 64,
            "candidate_revisions": {
                "composition_hash": "c" * 64,
                "release_id": "release-candidate",
                "golden_revision": "d" * 64,
                "policy_revision": "policy-fixture",
            },
            "evaluation_hash": "e" * 64,
            "policy_revision": "policy-fixture",
            "approved_at": "2026-09-05T00:00:00Z",
            "authority": {
                "authenticated": True,
                "source": "synthetic-fixture",
                "subject": "editor-fixture",
                "role": "human_approver",
                "proof_hash": "f" * 64,
            },
        },
        "publication": {
            "schema_version": 1,
            "release_id": "release-candidate",
            "candidate_id": "candidate-" + "a" * 32,
            "approval_id": "approval-fixture",
            "composition_hash": "c" * 64,
            "parent_release_id": "release-base",
            "published_at": "2026-09-05T00:00:00Z",
        },
        "history": {
            "schema_version": 1,
            "history_id": "history-fixture",
            "release_id": "release-candidate",
            "composition_hash": "c" * 64,
            "index_revision": "index-fixture",
            "retained_at": "2026-09-05T00:00:00Z",
            "revoked": False,
            "index_compatible": True,
            "parent_release_id": "release-base",
            "source_candidate_id": "candidate-" + "a" * 32,
        },
        "rollback": {
            "schema_version": 1,
            "rollback_id": "rollback-fixture",
            "target_release_id": "release-candidate",
            "previous_release_id": "release-current",
            "rolled_back_at": "2026-09-05T00:00:00Z",
        },
        "source-registration": {
            "schema_version": 1,
            "source_id": "source-fixture",
            "canonical": "https://docs.example.test/guide",
            "kind": "web",
            "scope": "docs/**",
            "version_policy": "pinned",
            "version": "1.0",
            "language": "en",
            "rights": "MIT",
            "privacy": "public",
            "authority": "official",
            "owner": "fixture",
            "status": "active",
            "registered_at": "2026-09-05T00:00:00Z",
            "withdrawn_at": None,
            "last_observed_revision": None,
            "last_observed_version": None,
            "last_observed_at": None,
            "last_observed_entries": 0,
        },
        "acquisition-snapshot": {
            "schema_version": 1,
            "source_id": "source-fixture",
            "revision": "revision-fixture",
            "version": "1.0",
            "entries": [{"canonical": "https://docs.example.test/guide/index"}],
            "scope": "docs/**",
            "completeness": "complete",
            "observation_time": "2026-09-05T00:00:00Z",
            "errors": [],
            "warnings": [],
        },
        "event": {
            "schema_version": 1,
            "event_id": "event-fixture",
            "type": "source_changed",
            "package_id": "package-fixture",
            "source_id": "source-fixture",
            "observed_revision": "revision-fixture",
            "occurred_at": "2026-09-05T00:00:00Z",
            "origin": "synthetic-fixture",
            "causation_id": None,
            "payload": {"policy_revision": "policy-fixture"},
        },
        "job": {
            "schema_version": 1,
            "job_id": "job-fixture",
            "job_key": "job-key-fixture",
            "type": "source_changed",
            "package_id": "package-fixture",
            "target_revision": "revision-fixture",
            "state": "pending",
            "attempt": 0,
            "due_at": "2026-09-05T00:01:00Z",
            "first_event_at": "2026-09-05T00:00:00Z",
            "last_event_at": "2026-09-05T00:00:00Z",
            "event_count": 1,
            "lease_until": None,
            "result_ref": None,
            "error_code": None,
            "policy_revision": "policy-fixture",
            "completed_files": ["guide.md"],
            "deferred_files": [],
        },
        "rag-authorization": {
            "schema_version": 1,
            "authorization_id": "rag-authorization-fixture",
            "package_id": "package-fixture",
            "action": "index_rag",
            "target_revision": "revision-fixture",
            "policy_revision": "policy-fixture",
            "actor": {"id": "operator-fixture", "role": "human_approver"},
            "authorized_at": "2026-09-05T00:00:00Z",
            "expires_at": None,
            "scope": "package-fixture",
        },
        "job-receipt": {
            "schema_version": 1,
            "job_id": "job-fixture",
            "package_id": "package-fixture",
            "target_revision": "revision-fixture",
            "request_hash": "a" * 64,
            "status": "succeeded",
            "effect_code": "candidate_prepared",
            "result_ref": "candidate-" + "b" * 32,
            "recorded_at": "2026-09-05T00:00:00Z",
        },
        "conceptual-impact": {
            "schema_version": 1,
            "ok": True,
            "package_id": "package-fixture",
            "cursor": {
                "last_event_at": "2026-09-05T00:00:00Z",
                "last_event_id": "event-fixture",
            },
            "relevant_count": 1,
            "affected_ratio": 0.01,
            "documents": [
                {
                    "document_id": "docs/guide.md",
                    "revision": "revision-fixture",
                    "base_revision": "base-fixture",
                    "impact": "conceptual",
                    "support_valid": True,
                }
            ],
            "reverted_documents": [],
            "factual_documents": [],
            "uncertain_documents": [],
            "batch": {
                "status": "candidate_requested",
                "batch_id": "conceptual-batch-fixture",
                "batch_key": "batch-key-fixture",
                "causation_id": "event-fixture",
                "document_ids": ["docs/guide.md"],
                "publication_allowed": False,
                "reason": "conceptual_impact_threshold_reached",
                "created_at": "2026-09-05T00:00:00Z",
            },
            "backlog_count": 0,
            "backlog": [],
            "revocations": [],
        },
        "reader-session": {
            "schema_version": 1,
            "session_id": "reader-session-fixture",
            "package_id": "package-fixture",
            "generation": {
                "release_id": "release-fixture",
                "composition_hash": "c" * 64,
            },
            "snapshot": {
                "snapshot_id": "snapshot-fixture",
                "release_id": "release-fixture",
                "composition_hash": "c" * 64,
                "corpus_hash": "d" * 64,
                "profile": "compact",
                "embedding_fingerprint": "e" * 64,
                "model": {"name": "fixture-model", "revision": "fixture"},
                "configuration_hash": "f" * 64,
                "artifacts_hash": "a" * 64,
                "revocation_hash": "b" * 64,
            },
            "created_at": "2026-09-05T00:00:00Z",
            "expires_at": "2026-09-05T01:00:00Z",
            "status": "active",
            "permissions": {
                "profile": "reader",
                "read_only": True,
                "allowed_tools": ["search_knowledge", "get_document"],
                "denied_tools": ["add_document", "reindex_documents"],
            },
            "backend": {
                "adapter": "memory",
                "concurrent_publication_allowed": False,
                "capability_source": "synthetic-fixture",
            },
        },
        "reader-query": {
            "schema_version": 1,
            "ok": True,
            "session_id": "reader-session-fixture",
            "generation": {
                "release_id": "release-fixture",
                "composition_hash": "c" * 64,
            },
            "tool": "search_knowledge",
            "query": "guide",
            "results": [{"source": "guide.md", "content": "Guide", "score": 1.0}],
            "cache_hit": False,
            "metadata": {"adapter": "memory", "backend": "synthetic"},
        },
        "rag-snapshot": {
            "schema_version": 1,
            "snapshot_id": "snapshot-fixture",
            "package_id": "package-fixture",
            "release": {
                "release_id": "release-fixture",
                "composition_hash": "c" * 64,
                "corpus_revision": "corpus-fixture",
                "index_revision": "index-fixture",
            },
            "documents_root": "rag/documents",
            "documents": {
                "guide.md": {
                    "sha256": "a" * 64,
                    "size": 5,
                    "mtime_ns": 1,
                }
            },
            "document_count": 1,
            "total_bytes": 5,
            "corpus_hash": "b" * 64,
            "embedding": {
                "profile": "compact",
                "embedding_fingerprint": "c" * 64,
            },
            "model": {"name": "fixture-model", "revision": "fixture"},
            "configuration": {
                "path": "config.yaml",
                "sha256": "e" * 64,
                "content_hash": "f" * 64,
                "redacted": True,
            },
            "artifacts": {"content_hash": "a" * 64, "file_count": 0, "files": {}},
            "backend": {
                "name": "memory",
                "supports_incremental": True,
                "version": None,
            },
            "backend_snapshot": {
                "index": {"present": False, "sha256": None, "size": 0, "mtime_ns": 0},
                "data": {
                    "root": "rag/data",
                    "present": False,
                    "files": {},
                    "file_count": 0,
                    "total_bytes": 0,
                    "content_hash": "d" * 64,
                },
            },
            "revocation": {"content_hash": "b" * 64, "files": [], "blocked_documents": []},
        },
        "rag-reuse-plan": {
            "schema_version": 1,
            "ok": True,
            "snapshot_id": "snapshot-fixture",
            "mode": "incremental",
            "reason": "incremental_reuse",
            "reused_count": 1,
            "changed_count": 0,
            "removed_count": 0,
            "changed_paths": [],
            "removed_paths": [],
            "logical_stats": {
                "current_documents": 1,
                "previous_documents": 1,
                "reused_documents": 1,
                "current_bytes": 5,
            },
            "active_preserved": True,
            "publication_allowed": False,
        },
        "learning-proposal": {
            "schema_version": 1,
            "proposal_id": "proposal-fixture",
            "capture_opt_in": True,
            "excerpt": "Minimized fixture excerpt.",
            "claim": {
                "text": "The fixture policy is deterministic.",
                "kind": "factual_correction",
                "scope": "project",
            },
            "evidence": [
                {
                    "kind": "primary_source",
                    "reference": "fixture://policy",
                    "quote": "The policy is deterministic.",
                    "independent": True,
                    "verification": {
                        "status": "verified",
                        "verifier": "fixture-verifier",
                        "provenance": "fixture://policy",
                        "authority": "fixture-authority",
                        "license": "MIT",
                        "supports_claim": True,
                        "evidence_hash": "a" * 64,
                        "receipt_hash": "b" * 64,
                    },
                }
            ],
            "source": {
                "kind": "conversation",
                "conversation_id": "conversation-fixture",
                "author_id": "user-fixture",
            },
            "consent": {
                "holder_id": "user-fixture",
                "scope": "project",
                "purpose": "synthetic-validation",
                "granted_at": "2026-09-04T00:00:00Z",
                "expires_at": "2030-01-01T00:00:00Z",
                "revoked_at": None,
                "consent_hash": "c" * 64,
            },
            "privacy": "project",
            "state": "quarantined",
            "submitted_at": "2026-09-05T00:00:00Z",
            "proposal_hash": "a" * 64,
        },
        "learning-review": {
            "schema_version": 1,
            "review_id": "review-fixture",
            "proposal_id": "proposal-fixture",
            "proposal_hash": "a" * 64,
            "decision": "admit",
            "actor": "reviewer-fixture",
            "role": "human_approver",
            "evidence_check": {
                "independent": True,
                "response_excluded": True,
                "references": ["fixture://policy"],
            },
            "publication_allowed": False,
            "derived": [],
            "state": "admitted",
            "reviewed_at": "2026-09-05T00:01:00Z",
        },
        "feedback": {
            "schema_version": 1,
            "feedback_id": "feedback-fixture",
            "event_id": "event-feedback-fixture",
            "package_id": "package-fixture",
            "generation": {
                "release_id": "release-fixture",
                "composition_hash": "c" * 64,
                "corpus_revision": "corpus-fixture",
                "index_revision": "index-fixture",
                "golden_revision": "golden-fixture",
                "harness_revision": "harness-fixture",
                "configuration_hash": "configuration-fixture",
            },
            "kind": "wrong_answer",
            "question": "<redacted-query>",
            "question_hash": "d" * 64,
            "privacy": "redacted",
            "source": {
                "channel": "synthetic-fixture",
                "reporter_hash": "e" * 64,
                "session_hash": "f" * 64,
            },
            "authentication": {
                "authenticated": True,
                "source": "synthetic-feedback-idp",
                "subject_hash": "1" * 64,
                "proof_hash": "2" * 64,
            },
            "usage": {"latency_ms": 120.0, "cost_units": 1.5, "denominator": 1},
            "comparison": None,
            "occurred_at": "2026-09-05T00:00:00Z",
            "state": "received",
            "occurrence_hash": "a" * 64,
            "feedback_hash": "b" * 64,
        },
        "feedback-report": {
            "schema_version": 1,
            "ok": True,
            "report_id": "feedback-report-fixture",
            "package_id": "package-fixture",
            "window": {
                "start": "2026-09-04T00:00:00Z",
                "end": "2026-09-05T00:00:00Z",
                "days": 1,
            },
            "counts": {
                "submissions": 0,
                "unique_occurrences": 0,
                "duplicate_submissions": 0,
                "investigations": 0,
            },
            "usage": {
                "latency_ms": {},
                "cost_units": {},
                "denominators": {},
            },
            "comparison": {},
            "occurrences": [],
            "investigations": [],
            "publication_allowed": False,
            "golden_changed": False,
            "expected_response_changed": False,
        },
        "investigation": {
            "schema_version": 1,
            "investigation_id": "investigation-fixture",
            "package_id": "package-fixture",
            "kind": "wrong_answer",
            "status": "candidate_requested",
            "reviewed": False,
            "occurrence_ids": ["occurrence-fixture"],
            "golden_candidate": {
                "candidate_id": "golden-feedback-fixture",
                "reviewed": False,
                "publication_allowed": False,
            },
            "publication_allowed": False,
            "created_at": "2026-09-05T00:00:00Z",
        },
        "cutover-decision": {
            "schema_version": 2,
            "kind": "cutover_decision",
            "status": "not_run",
            "ok": False,
            "legacy_preserved": True,
            "gates": {
                "legacy_arm": False,
                "ragflow_arm": False,
                "candidate": True,
                "ir_revision": True,
                "golden_revision": True,
                "corpus_digest": True,
                "environment": True,
                "backend": False,
                "mappings": False,
                "recall_at_5": False,
                "mrr_at_5": False,
                "citation_coverage": False,
                "lineage_coverage": False,
                "id_parity": False,
                "lifecycle": False,
                "recovery": False,
                "rollback": False,
                "cleanup": False,
                "arm_hashes": True,
            },
            "blockers": ["legacy_arm", "ragflow_arm"],
            "candidate": "93bb8894d816aad3c3b3682ccec317db1da39d45",
            "ir_revision": "ir-fixture",
            "golden_revision": "golden-fixture",
            "corpus_digest": "a" * 64,
            "environment": {"python": "3.14.2", "profile": "core", "runtime": "python"},
            "metrics": {
                "recall_at_5": None,
                "mrr_at_5": None,
                "citation_coverage": None,
                "lineage_coverage": None,
                "id_parity": None,
            },
            "backends": {
                "legacy": {"name": "knowledge-rag", "version": "4.8.5"},
                "ragflow": None,
            },
            "arm_statuses": {"legacy": "not_run", "ragflow": "not_run"},
            "arm_identities": {"legacy": None, "ragflow": None},
            "arm_metrics": {"legacy": None, "ragflow": None},
            "arm_lifecycles": {"legacy": None, "ragflow": None},
            "mappings": {"legacy": None, "ragflow": None},
            "mapping_hashes": {"legacy": None, "ragflow": None},
            "arm_hashes": {"legacy": "b" * 64, "ragflow": "c" * 64},
            "lifecycle": {"queryable": False, "recovery": False, "rollback": False},
            "cleanup": "not_run",
            "receipt_hash": "b" * 64,
        },
        # Farol 2.0 IR envelopes (AC-004/AC-009). These are what the format
        # extractors emit, so the gate validates the canonical contract, not only
        # the structural rules every schema shares.
        "ir-block": {
            "schema_version": 2,
            "kind": "heading",
            "block_id": "block-fixture",
            "parent_id": None,
            "ordinal": 0,
            "text": "Intro",
            "structured": None,
            "heading_path": ["Intro"],
            "symbol": None,
            "locators": [{"kind": "section", "label": "Intro"}],
            "language": "en",
            "confidence": None,
            "quality_flags": [],
            "source_fragment_hash": "a" * 64,
        },
        "ir-document": {
            "schema_version": 2,
            "kind": "ir_document",
            "document_id": "document-fixture",
            "source_id": "source-fixture",
            "source_revision_id": "source-rev-fixture",
            "artifact_id": "guide.md",
            "content_hash": "b" * 64,
            "media_type": "text/markdown",
            "language": "en",
            "extractor": {"name": "text-web", "version": "2.0", "execution": "local"},
            "fidelity": {"level": "structured-native", "capabilities": ["section"], "degradations": []},
            "rights_ref": "rights-fixture",
            "captured_at": "2026-09-05T00:00:00Z",
            "effective_at": None,
            "region": None,
            "blocks": [{"block_id": "block-fixture", "ordinal": 0, "text": "Intro"}],
            "assets": [],
            "origin": "fixture://guide.md",
        },
        "extraction-receipt": {
            "schema_version": 2,
            "kind": "extraction_receipt",
            "artifact_id": "guide.md",
            "source_id": "source-fixture",
            "source_revision_id": "source-rev-fixture",
            "extractor": {"name": "text-web", "version": "2.0", "execution": "local"},
            "fidelity": "structured-native",
            "status": "extracted",
            "input_hash": "a" * 64,
            "ir_revision": "b" * 64,
            "warnings": [],
            "errors": [],
            "quarantine_reason": None,
            "metadata": {},
        },
    }


def _master_doc(kind: str, identifier: str, payload: dict[str, object]) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": 1,
        "kind": kind,
        "id": identifier,
        "created_at": "2026-09-08T00:00:00Z",
        **payload,
    }
    value["content_hash"] = content_hash(value)
    return value


def _master_examples() -> dict[str, object]:
    project_id = "project-contract-fixture"
    revision_id = "project-revision-contract-fixture"
    return {
        "project": _master_doc(
            "project",
            project_id,
            {
                "project_id": project_id,
                "name": "Fixture",
                "active_project_revision_id": None,
                "working_project_revision_id": None,
                "package_locator": None,
                "write_revision": 1,
                "visibility": "private",
            },
        ),
        "init-session": _master_doc(
            "init_session",
            "session-contract-fixture",
            {
                "session_id": "session-contract-fixture",
                "project_id": project_id,
                "session_revision": 1,
                "status": "collecting",
                "preset": None,
                "requested_deliverables": ["knowledge"],
                "answers": [],
                "decisions": [],
                "pending_questions": [],
                "finalized_revision_id": None,
            },
        ),
        "project-revision": _master_doc(
            "project_revision",
            revision_id,
            {
                "project_revision_id": revision_id,
                "project_id": project_id,
                "parent_project_revision_id": None,
                "package_ref": None,
                "artifacts": [],
                "pending_decision_ids": [],
                "change_id": None,
                "status": "private_draft",
            },
        ),
        "brief": _master_doc(
            "brief",
            "brief-contract-fixture",
            {
                "revision_id": revision_id,
                "project_id": project_id,
                "goal": "Fixture goal",
                "audience": None,
                "region": None,
                "language": None,
                "deliverables": ["knowledge"],
                "constraints": [],
                "open_decision_ids": [],
            },
        ),
        "decisions": _master_doc(
            "decisions",
            "decisions-contract-fixture",
            {
                "revision_id": revision_id,
                "project_id": project_id,
                "items": [],
            },
        ),
        "policy": _master_doc(
            "policy",
            "policy-contract-fixture",
            {
                "revision_id": revision_id,
                "project_id": project_id,
                "publication_mode": "manual",
                "delegation_ref": None,
                "private_draft_only": True,
                "rights_policy_revision": "unknown",
                "privacy_policy_revision": "unknown",
            },
        ),
        "dependencies": _master_doc(
            "dependencies",
            "dependencies-contract-fixture",
            {
                "revision_id": revision_id,
                "project_id": project_id,
                "nodes": [],
                "edges": [],
            },
        ),
        "source-governance": _master_doc(
            "source_governance_registry",
            "governance-contract-fixture",
            {
                "sources": [],
                "policy_revision": "unknown",
                "updated_at": "2026-09-08T00:00:00Z",
            },
        ),
        "claim": _master_doc(
            "claim",
            "claim-contract-fixture",
            {
                "claim_id": "claim-contract-fixture",
                "project_id": project_id,
                "text": "Fixture claim",
                "classification": "factual_observation",
                "region": None,
                "validity": {"from": None, "until": None, "checked_at": None, "review_after": None},
                "evidence_refs": [],
                "conflict_ids": [],
                "review_status": "proposed",
                "reviewer_ref": None,
            },
        ),
        "conflict": _master_doc(
            "conflict",
            "conflict-contract-fixture",
            {
                "conflict_id": "conflict-contract-fixture",
                "project_id": project_id,
                "claim_ids": ["a", "b"],
                "relation": "contradicts",
                "status": "open",
                "resolution": None,
                "reviewer_ref": None,
            },
        ),
        "change-proposal": _master_doc(
            "change_proposal",
            "change-contract-fixture",
            {
                "change_id": "change-contract-fixture",
                "project_id": project_id,
                "base_project_revision_id": revision_id,
                "base_package_ref": None,
                "operations": [
                    {"type": "source_add", "target_id": "source-fixture", "expected_hash": None, "payload": {}}
                ],
                "requested_by": "fixture",
                "reason": "fixture",
                "policy_revision": "fixture",
                "dependency_graph": {},
                "status": "proposed",
            },
        ),
        "impact-report": _master_doc(
            "impact_report",
            "impact-contract-fixture",
            {
                "change_id": "change-contract-fixture",
                "base_project_revision_id": revision_id,
                "classification": "unknown",
                "affected_nodes": [],
                "required_checks": [],
                "blockers": [],
                "existing_conceptual_report_ref": None,
                "unknown_dependencies": True,
            },
        ),
        "dependency-graph": _master_doc(
            "dependency_graph",
            "graph-contract-fixture",
            {
                "nodes": [],
                "edges": [],
                "unknown_dependencies": False,
            },
        ),
        "backup-manifest": _master_doc(
            "backup_manifest",
            "backup-contract-fixture",
            {
                "backup_id": "backup-contract-fixture",
                "project_id": project_id,
                "created_at_source": "2026-09-08T00:00:00Z",
                "root_locator": "folder",
                "files": [],
                "excluded": [],
                "rpo_observed_at": "2026-09-08T00:00:00Z",
            },
        ),
        "project-enrichment-request": _master_doc(
            "enrichment_request",
            "enrichment-contract-fixture",
            {
                "request_id": "enrichment-contract-fixture",
                "project_id": project_id,
                "base_project_revision_id": revision_id,
                "policy_revision": "fixture",
                "allowed_artifacts": ["skill"],
                "budget": {},
                "state": "dispatched",
                "attempt": 1,
                "deadline_at": "2026-09-09T00:00:00Z",
                "harness": None,
                "created_at_external": "2026-09-08T00:00:00Z",
            },
        ),
        "delegated-authorization": _master_doc(
            "delegated_authorization",
            "authorization-contract-fixture",
            {
                "authorization_id": "authorization-contract-fixture",
                "project_id": project_id,
                "owner": "fixture",
                "actions": ["factual_update"],
                "source_ids": [],
                "expires_at": "2026-09-09T00:00:00Z",
                "budget": {},
                "authority_ref": "fixture-authority",
                "policy_revision": "policy-fixture",
                "kill_switch": False,
                "status": "active",
            },
        ),
        "supervisor-status": _master_doc(
            "supervisor_status",
            "supervisor-status",
            {
                "status": "stopped",
                "tick": 0,
                "last_source_hash": None,
                "pending_events": [],
                "last_error": None,
                "missed_cycles": 0,
                "max_missed_cycles": 3,
                "queue_path": None,
                "last_success_at": None,
            },
        ),
        "project-rag-candidate-receipt": _master_doc(
            "rag_candidate_receipt",
            "candidate-rag-contract-fixture",
            {
                "candidate_id": "candidate-rag-contract-fixture",
                "project_id": project_id,
                "candidate_package_ref": "candidate:fixture",
                "base_package_ref": None,
                "snapshot_id": "snapshot-contract-fixture",
                "corpus_hash": "a" * 64,
                "profile": "multilingual",
                "embedding_fingerprint": "b" * 64,
                "model": {},
                "rebuild_required": True,
                "active_preserved": True,
                "publication_allowed": False,
                "evaluation_status": "pending",
                "evaluation_hash": None,
            },
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.parse_args(argv)
    findings: list[dict[str, str]] = []
    distribution = check_schema_distribution(ROOT / "schemas", ROOT / "docops" / "schemas")
    findings.extend(
        {"code": item["code"], "artifact": "schema-distribution", "message": item["message"]}
        for item in distribution["findings"]
    )
    findings.extend(_schema_policy_findings())
    for name in contract_names():
        try:
            load_schema(name)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            findings.append({"code": "schema_unavailable", "artifact": name, "message": str(exc)})
    examples = _examples()
    examples.update(_master_examples())
    for name, payload in examples.items():
        if name not in contract_names():
            continue
        result = validate_artifact(name, payload)
        if not result.ok:
            findings.extend(
                {"code": error["code"], "artifact": name, "message": error["message"]} for error in result.errors
            )
        if isinstance(payload, dict):
            required = load_schema(name).get("required", [])
            if isinstance(required, list) and required:
                invalid = copy.deepcopy(payload)
                invalid.pop(required[0], None)
                if validate_artifact(name, invalid).ok:
                    findings.append(
                        {
                            "code": "negative_fixture_accepted",
                            "artifact": name,
                            "message": f"removing {required[0]!r} must fail",
                        }
                    )
        package_schema = ROOT / "docops" / "schemas" / Path(schema_path(name) or "").name
        checkout_schema = ROOT / "schemas" / Path(schema_path(name) or "").name
        try:
            schema_matches = package_schema.is_file() and json.loads(
                package_schema.read_text(encoding="utf-8")
            ) == json.loads(checkout_schema.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            schema_matches = False
        if not schema_matches:
            findings.append(
                {"code": "schema_drift", "artifact": name, "message": "bundled and checkout schemas differ"}
            )
    report = {"schema_version": 1, "ok": not findings, "artifacts": list(contract_names()), "findings": findings}
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
