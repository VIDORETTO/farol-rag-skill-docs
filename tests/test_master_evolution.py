# seam-scope: implementation-infrastructure (synthetic fixture helpers)

from __future__ import annotations

import json
from pathlib import Path

import pytest

from docops import (
    activate_project_change,
    adopt_project_package,
    answer_project_init,
    authorize_factual_change,
    backup_project,
    create_delegated_authorization,
    dispatch_project_enrichment,
    evaluate_project_candidate,
    finalize_project_init,
    inspect_project_health,
    inspect_project_init,
    load_project_preset,
    prepare_project_change,
    prepare_project_rag_candidate,
    propose_project_change,
    restore_project,
    resume_project_supervisor,
    rollback_project_adoption,
    run_project_supervisor_once,
    start_project_init,
    submit_project_enrichment,
    validate_dependency_mitigation,
    verify_project_backup,
)
from docops.contracts import validate_artifact
from docops.rag_snapshots import package_rag_config_text
from docops.revisions import content_hash, package_revisions
from scripts.check_documentation import check_documentation


def _rag_package(path: Path, *, profile: str = "compact") -> Path:
    (path / "rag" / "documents").mkdir(parents=True)
    (path / "config.yaml").write_text(
        package_rag_config_text().replace("profile: compact", f"profile: {profile}"), encoding="utf-8"
    )
    (path / "manifest.json").write_text(json.dumps({"package_id": path.name}), encoding="utf-8")
    (path / "rag" / "documents" / "guide.md").write_text("# Guia\n\nAPI estável para a fixture.\n", encoding="utf-8")
    return path


def _legacy_package(path: Path, package_id: str, body: str) -> Path:
    (path / "skill").mkdir(parents=True)
    (path / "router").mkdir()
    (path / "rag" / "documents").mkdir(parents=True)
    (path / "skill" / "SKILL.md").write_text(
        "---\nname: fixture-skill\ndescription: Synthetic legacy skill\n---\n# Fixture\n",
        encoding="utf-8",
    )
    (path / "router" / "SKILL.md").write_text(
        "# Router\nUse fixture-skill and search_knowledge; cite each factual answer.\n",
        encoding="utf-8",
    )
    (path / "rag" / "documents" / "guide.md").write_text(body, encoding="utf-8")
    (path / "rag" / "index.json").write_text(
        json.dumps({"status": "ready", "documents": 1, "chunks": 1}), encoding="utf-8"
    )
    (path / "config.yaml").write_text(package_rag_config_text(), encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "run_id": package_id,
        "package_id": package_id,
        "source": {"input": f"fixture://{package_id}", "canonical": f"fixture://{package_id}"},
        "provenance": {"license": "MIT", "redistribution": "private-only"},
        "artifacts": {"skill": "skill", "router": "router", "rag": "rag", "config": "config.yaml"},
    }
    manifest["revisions"] = package_revisions(path, golden_revision="fixture-golden")
    (path / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return path


def _finalized_project(path: Path, *, deliverables: list[str] | None = None) -> dict:
    started = start_project_init(
        path,
        {
            "name": "Fixture project",
            "objective": "Explain a synthetic workflow",
            "deliverables": deliverables or ["knowledge"],
        },
        now="2026-09-08T12:00:00Z",
    )
    assert started["ok"] is True
    return finalize_project_init(path, session_id=started["data"]["session"]["session_id"], now="2026-09-08T12:00:00Z")


def _answer_value(session: dict, key: str):
    return next(item["value"] for item in session["answers"] if item["question_key"] == key)


def test_documentation_checker_validates_flags_and_allows_explicit_future_examples(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        """
# Commands

```text
python -m docops work --loop --interval-seconds 60 --queue <queue> --json
python -m docops work --once --queue <queue> --json
```

Future proposal (not available in this runtime):

```text
python -m docops work --loop --interval-seconds 60 --queue <queue> --json
```
""",
        encoding="utf-8",
    )

    result = check_documentation(tmp_path)

    assert result["ok"] is False
    findings = result["findings"]
    assert any(finding["code"] == "documented_option_unknown" for finding in findings)


def test_project_init_persists_answers_and_rejects_stale_revision(tmp_path: Path):
    project = tmp_path / "project"
    started = start_project_init(
        project,
        {"name": "Knowledge fixture", "deliverables": ["knowledge"]},
        idempotency_key="start-1",
    )
    assert started["ok"] is True
    assert started["outcome"] == "needs_input"
    session_id = started["data"]["session"]["session_id"]
    revision = started["session_revision"]

    answered = answer_project_init(
        project,
        session_id=session_id,
        answers={"objective": "Explain the stable API"},
        expected_revision=revision,
        idempotency_key="answer-1",
    )
    assert answered["ok"] is True
    assert answered["outcome"] == "applied"
    assert _answer_value(answered["data"]["session"], "objective") == "Explain the stable API"

    resumed = inspect_project_init(project, session_id=session_id)
    assert resumed["ok"] is True
    assert _answer_value(resumed["data"]["session"], "objective") == "Explain the stable API"

    stale = answer_project_init(
        project,
        session_id=session_id,
        answers={"objective": "should not overwrite"},
        expected_revision=revision,
        idempotency_key="answer-stale",
    )
    assert stale["ok"] is False
    assert stale["errors"][0]["code"] == "STALE_REVISION"
    assert _answer_value(inspect_project_init(project, session_id=session_id)["data"]["session"], "objective") == (
        "Explain the stable API"
    )

    finalized = finalize_project_init(
        project,
        session_id=session_id,
        expected_revision=answered["session_revision"],
        idempotency_key="finalize-1",
    )
    assert finalized["ok"] is True
    assert finalized["outcome"] == "applied"
    assert (project / "revisions" / finalized["data"]["project_revision_id"] / "brief.json").is_file()


def test_audience_correction_propagates_to_the_brief_only(tmp_path: Path) -> None:
    project = tmp_path / "project"
    started = start_project_init(
        project,
        {
            "name": "Audience fixture",
            "objective": "Explain a synthetic workflow",
            "audience": "new sellers",
        },
        now="2026-09-08T12:00:00Z",
    )
    assert started["ok"] is True
    answered = answer_project_init(
        project,
        {
            "audience": {"value": "experienced sellers", "origin": "user_explicit"},
        },
        expected_revision=started["session_revision"],
        now="2026-09-08T12:01:00Z",
    )
    assert answered["ok"] is True
    finalized = finalize_project_init(
        project,
        session_id=started["data"]["session"]["session_id"],
        expected_revision=answered["session_revision"],
        now="2026-09-08T12:02:00Z",
    )
    assert finalized["ok"] is True
    base_revision = finalized["data"]["project_revision_id"]
    base_dir = project / "revisions" / base_revision
    decisions = json.loads((base_dir / "decisions.json").read_text(encoding="utf-8"))
    audience_decision = next(item for item in decisions["items"] if item["key"] == "audience")

    proposed = propose_project_change(
        project,
        {
            "change_id": "change-audience-correction",
            "base_project_revision_id": base_revision,
            "operations": [
                {
                    "type": "decision_correct",
                    "target_id": audience_decision["decision_id"],
                    "expected_hash": content_hash(audience_decision),
                    "payload": {"value": "new sellers"},
                }
            ],
            "requested_by": "operator",
            "reason": "correct the audience recorded in the brief",
            "dependency_graph": {"nodes": [], "edges": [], "unknown_dependencies": False},
        },
        now="2026-09-08T12:03:00Z",
    )
    assert proposed["ok"] is True
    prepared = prepare_project_change(project, "change-audience-correction", now="2026-09-08T12:04:00Z")
    assert prepared["ok"] is True, prepared.get("errors")
    target_dir = project / "revisions" / prepared["data"]["receipt"]["project_revision_id"]
    target_brief = json.loads((target_dir / "brief.json").read_text(encoding="utf-8"))
    assert target_brief["audience"] == "new sellers"
    assert not (target_dir / "course.json").exists()
    assert not (target_dir / "page.json").exists()


def test_adoption_is_idempotent_recoverable_and_does_not_infer_rights(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    legacy_a = _legacy_package(tmp_path / "legacy-a", "legacy-a", "source A")
    legacy_b = _legacy_package(tmp_path / "legacy-b", "legacy-b", "source B")

    first = adopt_project_package(project, legacy_a, now="2026-09-08T12:00:00Z")
    assert first["ok"] is True
    assert first["data"]["index_rebuilt"] is False
    assert first["data"]["pending_fields"] == ["rights_policy", "privacy_policy"]
    identity = first["data"]["source_identity"]
    repeated = adopt_project_package(project, legacy_a, now="2026-09-08T12:00:00Z")
    assert repeated["ok"] is True
    assert repeated["outcome"] == "unchanged"
    assert repeated["data"]["source_identity"]["package_id"] == identity["package_id"]
    assert repeated["data"]["source_identity"]["release_id"] == identity["release_id"]

    monkeypatch.setenv("DOCOPS_TEST_ADOPTION_CRASH_AFTER_SWAP", "1")
    with pytest.raises(RuntimeError, match="adoption interruption"):
        adopt_project_package(project, legacy_b, now="2026-09-08T12:00:00Z")
    monkeypatch.delenv("DOCOPS_TEST_ADOPTION_CRASH_AFTER_SWAP")
    assert json.loads((project / "package" / "manifest.json").read_text(encoding="utf-8"))["package_id"] == "legacy-a"

    changed = adopt_project_package(project, legacy_b, now="2026-09-08T12:00:00Z")
    assert changed["ok"] is True
    backup_id = Path(changed["data"]["backup_path"]).name
    restored = rollback_project_adoption(project, backup_id, now="2026-09-08T12:00:00Z")
    assert restored["ok"] is True
    assert json.loads((project / "package" / "manifest.json").read_text(encoding="utf-8"))["package_id"] == "legacy-a"

    unsupported = _legacy_package(tmp_path / "legacy-unsupported", "legacy-unsupported", "unsupported")
    unsupported_manifest = json.loads((unsupported / "manifest.json").read_text(encoding="utf-8"))
    unsupported_manifest["schema_version"] = 2
    (unsupported / "manifest.json").write_text(json.dumps(unsupported_manifest), encoding="utf-8")
    rejected = adopt_project_package(project, unsupported, now="2026-09-08T12:00:00Z")
    assert rejected["ok"] is False
    assert rejected["errors"][0]["code"] == "UNSUPPORTED_SCHEMA_VERSION"


def test_adoption_dry_run_is_non_mutating_and_receipt_uses_portable_locators(tmp_path: Path) -> None:
    project = tmp_path / "project"
    legacy_a = _legacy_package(tmp_path / "legacy-a", "legacy-a", "source A")
    legacy_b = _legacy_package(tmp_path / "legacy-b", "legacy-b", "source B")

    first = adopt_project_package(project, legacy_a, now="2026-09-08T12:00:00Z")
    assert first["ok"] is True
    before_project = (project / "project.json").read_bytes()
    before_manifest = (project / "package" / "manifest.json").read_bytes()

    receipt = json.loads((project / ".docops-project" / "last-adoption.json").read_text(encoding="utf-8"))
    assert not Path(receipt["source_path"]).is_absolute()
    assert receipt["source_locator"] == legacy_a.name
    assert receipt["rights_policy"] == "unknown"
    assert receipt["privacy_policy"] == "unknown"

    preview = adopt_project_package(project, legacy_b, dry_run=True, now="2026-09-08T12:01:00Z")
    assert preview["ok"] is True
    assert preview["outcome"] == "applied"
    assert preview["data"]["dry_run"] is True
    assert preview["data"]["would_replace"] is True
    assert preview["data"]["backup_required"] is True
    assert preview["data"]["project"]["write_revision"] == first["data"]["project"]["write_revision"]
    assert (project / "project.json").read_bytes() == before_project
    assert (project / "package" / "manifest.json").read_bytes() == before_manifest


def test_adoption_dry_run_does_not_create_project_metadata(tmp_path: Path) -> None:
    project = tmp_path / "project"
    legacy = _legacy_package(tmp_path / "legacy", "legacy", "source")

    preview = adopt_project_package(project, legacy, dry_run=True, idempotency_key="preview-1")

    assert preview["ok"] is True
    assert not (project / "project.json").exists()
    assert not (project / ".docops-project").exists()


def test_governance_is_per_purpose_and_transcription_requires_explicit_intervals(tmp_path: Path):
    package = tmp_path / "package"
    (package / "rag" / "documents").mkdir(parents=True)
    governance = {
        "source_id": "video-1",
        "observed_revision": "source-rev-1",
        "source_type": "video_transcript",
        "captured_at": "2026-09-08T12:00:00Z",
        "use_policy": {
            "grants": [
                {
                    "purpose": "acquisition",
                    "decision": "allowed",
                    "evidence_ref": "perm-1",
                    "actor": "operator",
                    "valid_until": "2027-01-01T00:00:00Z",
                },
                {
                    "purpose": "storage",
                    "decision": "allowed",
                    "evidence_ref": "perm-1",
                    "actor": "operator",
                    "valid_until": "2027-01-01T00:00:00Z",
                },
                {
                    "purpose": "internal_query",
                    "decision": "allowed",
                    "evidence_ref": "perm-1",
                    "actor": "operator",
                    "valid_until": "2027-01-01T00:00:00Z",
                },
                {
                    "purpose": "indexing",
                    "decision": "allowed",
                    "evidence_ref": "perm-1",
                    "actor": "operator",
                    "valid_until": "2027-01-01T00:00:00Z",
                },
                {"purpose": "redistribution", "decision": "denied"},
            ]
        },
        "privacy": {"classification": "internal", "redaction_required": True},
    }
    registered = __import__("docops").register_source_governance(package, governance, now="2026-09-08T12:00:00Z")
    assert registered["ok"] is True
    assert (
        __import__("docops").source_use_decision(package, "video-1", "internal_query", now="2026-09-08T12:00:00Z")[
            "allowed"
        ]
        is True
    )
    assert (
        __import__("docops").source_use_decision(package, "video-1", "redistribution", now="2026-09-08T12:00:00Z")[
            "allowed"
        ]
        is False
    )

    rejected = __import__("docops").ingest_external_transcription(
        package, "video-1", "This has no timestamps", now="2026-09-08T12:00:00Z"
    )
    assert rejected["ok"] is False
    assert rejected["errors"][0]["code"] == "INVALID_INPUT"
    accepted = __import__("docops").ingest_external_transcription(
        package,
        "video-1",
        "[00:10-00:20] A stable fact\n[00:20-00:30] A second fact",
        video_url="https://example.test/video",
        provider="fixture",
        permission_ref="perm-1",
        now="2026-09-08T12:00:00Z",
    )
    assert accepted["ok"] is True
    assert accepted["data"]["segment_count"] == 2
    assert accepted["data"]["redistribution_allowed"] is False
    assert (package / ".docops" / "transcripts" / "video-1.md").is_file()

    out_of_order = __import__("docops").ingest_external_transcription(
        package,
        "video-1",
        {
            "text": "first\nsecond",
            "segments": [
                {"start_ms": 2_000, "end_ms": 3_000, "text_ref": "first"},
                {"start_ms": 1_000, "end_ms": 2_000, "text_ref": "second"},
            ],
        },
        now="2026-09-08T12:00:00Z",
    )
    assert out_of_order["ok"] is False
    assert out_of_order["errors"][0]["code"] == "INVALID_INPUT"


def test_evidence_query_prioritizes_current_official_claim_and_returns_insufficient_for_wrong_region(tmp_path: Path):
    package = tmp_path / "package"
    (package / "rag" / "documents").mkdir(parents=True)
    __import__("docops").register_source_governance(
        package,
        {
            "source_id": "official-1",
            "observed_revision": "rev-official",
            "source_type": "official_documentation",
            "authority_class": "official",
            "captured_at": "2026-09-08T12:00:00Z",
            "use_policy": {
                "grants": [
                    {
                        "purpose": "internal_query",
                        "decision": "allowed",
                        "evidence_ref": "registry",
                        "actor": "operator",
                        "valid_until": "2027-01-01T00:00:00Z",
                    }
                ]
            },
            "privacy": {"classification": "public"},
        },
        now="2026-09-08T12:00:00Z",
    )
    __import__("docops").register_source_governance(
        package,
        {
            "source_id": "opinion-1",
            "observed_revision": "rev-opinion",
            "source_type": "article",
            "authority_class": "practitioner",
            "captured_at": "2026-09-08T12:00:00Z",
            "use_policy": {
                "grants": [
                    {
                        "purpose": "internal_query",
                        "decision": "allowed",
                        "evidence_ref": "registry",
                        "actor": "operator",
                        "valid_until": "2027-01-01T00:00:00Z",
                    }
                ]
            },
            "privacy": {"classification": "public"},
        },
        now="2026-09-08T12:00:00Z",
    )
    official_ref = {
        "source_id": "official-1",
        "observed_revision": "rev-official",
        "document_id": "official.md",
        "content_hash": "a" * 64,
        "locator": {"kind": "section", "value": "rule", "end": None},
    }
    opinion_ref = {
        "source_id": "opinion-1",
        "observed_revision": "rev-opinion",
        "document_id": "opinion.md",
        "content_hash": "b" * 64,
        "locator": {"kind": "section", "value": "view", "end": None},
    }
    __import__("docops").record_project_claim(
        package,
        {
            "claim_id": "claim-official",
            "text": "Stable API rule",
            "classification": "official_rule",
            "region": "BR",
            "evidence_refs": [official_ref],
        },
    )
    __import__("docops").record_project_claim(
        package,
        {
            "claim_id": "claim-opinion",
            "text": "Stable API rule is flexible",
            "classification": "opinion",
            "region": "US",
            "evidence_refs": [opinion_ref],
        },
    )
    result = __import__("docops").query_project_evidence(
        package, "Stable API rule", filters={"region": "BR"}, now="2026-09-08T12:00:00Z"
    )
    assert result["ok"] is True
    assert result["data"]["outcome"] == "supported"
    assert result["data"]["claims"][0]["claim_id"] == "claim-official"
    wrong = __import__("docops").query_project_evidence(
        package, "Stable API rule", filters={"region": "PT"}, now="2026-09-08T12:00:00Z"
    )
    assert wrong["data"]["outcome"] == "insufficient_evidence"


def test_evidence_query_filters_revoked_or_foreign_retrieval_hits(tmp_path: Path):
    package = tmp_path / "package"
    (package / "rag" / "documents").mkdir(parents=True)
    grants = [
        {
            "purpose": "internal_query",
            "decision": "allowed",
            "evidence_ref": "registry",
            "actor": "operator",
            "valid_until": "2027-01-01T00:00:00Z",
        }
    ]
    for source_id in ("source-revoked", "source-active"):
        __import__("docops").register_source_governance(
            package,
            {
                "source_id": source_id,
                "observed_revision": f"rev-{source_id}",
                "source_type": "article",
                "authority_class": "practitioner",
                "captured_at": "2026-09-08T12:00:00Z",
                "use_policy": {"grants": grants},
                "privacy": {"classification": "public"},
            },
            now="2026-09-08T12:00:00Z",
        )
    __import__("docops").revoke_project_source(package, "source-revoked", now="2026-09-08T12:00:00Z")

    class Adapter:
        def search(self, query: str, *, max_results: int = 5):
            return [
                {
                    "source": "revoked.md",
                    "content": "revoked",
                    "score": 1.0,
                    "metadata": {"source_id": "source-revoked"},
                },
                {"source": "active.md", "content": "active", "score": 0.5, "metadata": {"source_id": "source-active"}},
                {
                    "source": "foreign.md",
                    "content": "foreign",
                    "score": 0.4,
                    "metadata": {"source_id": "source-foreign"},
                },
            ]

    result = __import__("docops").query_project_evidence(package, "fact", adapter=Adapter(), now="2026-09-08T12:00:00Z")
    assert result["ok"] is True
    assert [item["source"] for item in result["data"]["results"]] == ["active.md"]


def test_project_revision_artifacts_are_hashed_and_validate_against_normative_contracts(tmp_path: Path):
    project = tmp_path / "project"
    finalized = _finalized_project(project)
    revision = project / "revisions" / finalized["data"]["project_revision_id"]
    artifact_map = {
        "project.json": "project",
        "init/session.json": "init-session",
        "revision.json": "project-revision",
        "brief.json": "brief",
        "decisions.json": "decisions",
        "policy.json": "policy",
        "dependencies.json": "dependencies",
    }
    for relative, kind in artifact_map.items():
        path = (
            project / relative if relative.startswith("project") or relative.startswith("init") else revision / relative
        )
        payload = json.loads(path.read_text(encoding="utf-8"))
        result = validate_artifact(kind, payload)
        assert result.ok, (kind, result.errors)


def test_profile_candidate_is_isolated_and_unreviewed_golden_cannot_pass(tmp_path: Path):
    project = tmp_path / "project"
    _finalized_project(project)
    _rag_package(project / "package", profile="compact")
    candidate = _rag_package(tmp_path / "candidate", profile="multilingual")
    before_pointer = json.loads((project / "project.json").read_text(encoding="utf-8"))["active_project_revision_id"]

    prepared = prepare_project_rag_candidate(
        project,
        candidate,
        selected_profile="multilingual",
        now="2026-09-08T12:00:00Z",
    )
    assert prepared["ok"] is True, prepared.get("errors")
    assert prepared["data"]["comparison"]["requires_full_rebuild"] is True
    assert prepared["data"]["receipt"]["publication_allowed"] is False
    assert (
        json.loads((project / "project.json").read_text(encoding="utf-8"))["active_project_revision_id"]
        == before_pointer
    )
    assert validate_artifact("project-rag-candidate-receipt", prepared["data"]["receipt"]).ok
    prepared_again = prepare_project_rag_candidate(
        project,
        candidate,
        selected_profile="multilingual",
        now="2026-09-08T12:00:00Z",
    )
    assert prepared_again["ok"] is True
    assert prepared_again["outcome"] == "unchanged"

    unprepared = evaluate_project_candidate(
        project,
        candidate,
        {"schema_version": 1, "reviewed": True, "cases": []},
        candidate_id="candidate-rag-not-prepared",
    )
    assert unprepared["ok"] is False
    assert unprepared["errors"][0]["code"] == "DECISION_REQUIRED"

    blocked = evaluate_project_candidate(
        project,
        candidate,
        {"schema_version": 1, "reviewed": False, "cases": []},
        candidate_id=prepared["data"]["candidate_id"],
    )
    assert blocked["ok"] is False
    assert blocked["outcome"] == "blocked"
    assert any(item["code"] == "golden_not_reviewed" for item in blocked["data"]["evaluation"]["errors"])


def test_factual_delegation_binds_exact_proposal_and_activation_is_idempotent(tmp_path: Path):
    project = tmp_path / "project"
    finalized = _finalized_project(project)
    base_revision = finalized["data"]["project_revision_id"]
    proposed = propose_project_change(
        project,
        {
            "change_id": "change-source-add",
            "base_project_revision_id": base_revision,
            "operations": [
                {
                    "type": "source_add",
                    "target_id": "source-fixture",
                    "payload": {
                        "source_type": "article",
                        "captured_at": "2026-09-08T12:00:00Z",
                        "authority_class": "practitioner",
                    },
                }
            ],
            "requested_by": "operator",
            "reason": "add a synthetic factual source",
            "dependency_graph": {"nodes": [], "edges": [], "unknown_dependencies": False},
        },
        now="2026-09-08T12:00:00Z",
    )
    assert proposed["ok"] is True
    auth = create_delegated_authorization(
        project,
        {
            "authorization_id": "auth-source-add",
            "owner": "fixture-owner",
            "actions": ["source_update"],
            "source_ids": ["source-fixture"],
            "authority_ref": "fixture-attestation",
            "expires_at": "2027-01-01T00:00:00Z",
            "budget": {"max_operations": 1, "used_operations": 0},
        },
        now="2026-09-08T12:00:00Z",
    )
    assert auth["ok"] is True
    changed_policy = __import__("docops").register_source_governance(
        project,
        {
            "source_id": "policy-change-source",
            "source_type": "article",
            "captured_at": "2026-09-08T12:00:00Z",
            "authority_class": "practitioner",
        },
        now="2026-09-08T12:00:00Z",
    )
    assert changed_policy["ok"] is True
    stale_authorization = authorize_factual_change(
        project, "change-source-add", "auth-source-add", now="2026-09-08T12:00:00Z"
    )
    assert stale_authorization["ok"] is False
    assert stale_authorization["errors"][0]["code"] == "RIGHTS_BLOCKED"
    auth = create_delegated_authorization(
        project,
        {
            "authorization_id": "auth-source-add",
            "owner": "fixture-owner",
            "actions": ["source_update"],
            "source_ids": ["source-fixture"],
            "authority_ref": "fixture-attestation",
            "expires_at": "2027-01-01T00:00:00Z",
            "budget": {"max_operations": 1, "used_operations": 0},
        },
        now="2026-09-08T12:00:00Z",
    )
    assert auth["ok"] is True
    prepared = prepare_project_change(project, "change-source-add", now="2026-09-08T12:00:00Z")
    assert prepared["ok"] is True, prepared.get("errors")

    authorized = authorize_factual_change(project, "change-source-add", "auth-source-add", now="2026-09-08T12:00:00Z")
    assert authorized["ok"] is True
    activated = activate_project_change(
        project,
        "change-source-add",
        authorization_id="auth-source-add",
        now="2026-09-08T12:00:00Z",
    )
    assert activated["ok"] is True, activated.get("errors")
    assert activated["outcome"] == "applied"
    stored_auth = json.loads((project / ".docops-project" / "authorizations.json").read_text(encoding="utf-8"))
    assert stored_auth["authorizations"][0]["status"] == "exhausted"

    replay = authorize_factual_change(project, "change-source-add", "auth-source-add", now="2026-09-08T12:00:00Z")
    assert replay["ok"] is True
    assert replay["outcome"] == "unchanged"
    assert replay["data"]["idempotent"] is True
    revoked = __import__("docops").revoke_delegated_authorization(
        project, "auth-source-add", now="2026-09-08T12:00:00Z"
    )
    assert revoked["ok"] is True
    assert (
        authorize_factual_change(project, "change-source-add", "auth-source-add", now="2026-09-08T12:00:00Z")["errors"][
            0
        ]["code"]
        == "RIGHTS_BLOCKED"
    )


def test_supervisor_coalesces_events_redacts_work_and_recovers_missed_cycles(tmp_path: Path):
    project = tmp_path / "project"
    _finalized_project(project)
    resumed = resume_project_supervisor(project, now="2026-09-08T12:00:00Z")
    assert resumed["ok"] is True
    missing = project / "missing-source.md"
    first = run_project_supervisor_once(
        project,
        source_path=missing,
        max_missed_cycles=2,
        now="2026-09-08T12:01:00Z",
    )
    assert first["ok"] is False
    assert first["errors"][0]["code"] == "SOURCE_UNAVAILABLE"
    second = run_project_supervisor_once(
        project,
        source_path=missing,
        max_missed_cycles=2,
        now="2026-09-08T12:02:00Z",
    )
    assert second["data"]["supervisor"]["missed_cycles"] == 2
    degraded = inspect_project_health(project, now="2026-09-08T12:02:00Z")
    assert degraded["data"]["health"] == "degraded"
    assert [item["code"] for item in degraded["data"]["incidents"]] == ["SUPERVISOR_MISSED_CYCLES"]

    source = tmp_path / "source.md"
    source.write_text("synthetic source", encoding="utf-8")
    queue = tmp_path / "queue.db"
    changed = run_project_supervisor_once(
        project,
        source_path=source,
        source_id="source-fixture",
        queue_path=queue,
        work={"query": "private text", "token": "must-not-persist", "safe": "fixture"},
        now="2026-09-08T12:03:00Z",
    )
    assert changed["ok"] is True
    event = json.loads((project / ".docops-project" / "supervisor-event.json").read_text(encoding="utf-8"))
    assert "query" not in event["payload"]["work"]
    assert "token" not in event["payload"]["work"]
    stable = run_project_supervisor_once(
        project,
        source_path=source,
        source_id="source-fixture",
        queue_path=queue,
        now="2026-09-08T12:04:00Z",
    )
    assert stable["outcome"] == "unchanged"
    duplicate = __import__("docops").submit_event(
        queue, project / ".docops-project" / "supervisor-event.json", now="2026-09-08T12:04:00Z"
    )
    assert duplicate["code"] == "event_duplicate"
    assert len(__import__("docops").list_jobs(queue)["jobs"]) == 1
    recovered = inspect_project_health(project, now="2026-09-08T12:04:00Z")
    assert recovered["data"]["incidents"] == []
    history = recovered["data"]["incident_history"]
    assert sum(1 for item in history if item["code"] == "SUPERVISOR_MISSED_CYCLES") == 1
    assert next(item for item in history if item["code"] == "SUPERVISOR_MISSED_CYCLES")["status"] == "closed"


def test_presets_are_declarative_and_keep_commercial_authorization_unknown():
    neutral = load_project_preset("neutral")
    generic = load_project_preset("generic")
    assert neutral["id"] == "neutral"
    assert neutral["commercial_claims"] == "unknown"
    assert generic["id"] == "neutral"
    assert all(isinstance(theme["queries"], list) and theme["queries"] for theme in neutral["themes"])


def test_change_preparation_preserves_unchanged_artifacts_byte_for_byte(tmp_path: Path):
    project = tmp_path / "project"
    finalized = _finalized_project(project)
    base_revision = finalized["data"]["project_revision_id"]
    base_dir = project / "revisions" / base_revision
    base_policy = json.loads((base_dir / "policy.json").read_text(encoding="utf-8"))
    before = {
        name: (base_dir / name).read_bytes()
        for name in ("brief.json", "decisions.json", "dependencies.json")
        if (base_dir / name).is_file()
    }
    proposed = propose_project_change(
        project,
        {
            "change_id": "change-policy-only",
            "base_project_revision_id": base_revision,
            "operations": [
                {
                    "type": "policy_change",
                    "target_id": base_policy["id"],
                    "expected_hash": base_policy["content_hash"],
                    "payload": {"private_draft_only": True},
                }
            ],
            "requested_by": "operator",
            "reason": "keep the generated knowledge artifacts unchanged",
            "dependency_graph": {"nodes": [], "edges": [], "unknown_dependencies": False},
        },
        now="2026-09-08T12:00:00Z",
    )
    assert proposed["ok"] is True
    prepared = prepare_project_change(project, "change-policy-only", now="2026-09-08T12:00:00Z")
    assert prepared["ok"] is True, prepared.get("errors")
    target_dir = project / "revisions" / prepared["data"]["receipt"]["project_revision_id"]
    assert {name: (target_dir / name).read_bytes() for name in before} == before


def test_backup_restore_preserves_tombstones_and_excludes_sensitive_files(tmp_path: Path):
    project = tmp_path / "project"
    _finalized_project(project)
    (project / ".docops").mkdir(exist_ok=True)
    (project / ".docops" / "tombstones.json").write_text('{"tombstones":["old"]}', encoding="utf-8")
    (project / ".docops" / "secrets").mkdir()
    (project / ".docops" / "secrets" / "token.txt").write_text("secret", encoding="utf-8")
    backup = tmp_path / "backup"
    created = backup_project(project, backup, now="2026-09-08T12:00:00Z")
    assert created["ok"] is True, created.get("errors")
    assert verify_project_backup(backup)["ok"] is True
    assert (backup / ".docops" / "tombstones.json").is_file()
    assert not (backup / ".docops" / "secrets" / "token.txt").exists()

    (project / ".docops" / "tombstones.json").write_text('{"tombstones":["new"]}', encoding="utf-8")
    restored = restore_project(backup, tmp_path / "restored", current_root=project, now="2026-09-08T12:01:00Z")
    assert restored["ok"] is True, restored.get("errors")
    restored_tombstones = json.loads(
        (tmp_path / "restored" / ".docops" / "tombstones.json").read_text(encoding="utf-8")
    )
    assert restored_tombstones == {"tombstones": ["new"]}

    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    tamper_path = backup / manifest["files"][0]["path"]
    tamper_path.write_bytes(tamper_path.read_bytes() + b"tamper")
    assert verify_project_backup(backup)["ok"] is False


def test_backup_restore_snapshots_external_supervisor_queue_in_isolation(tmp_path: Path):
    project = tmp_path / "project"
    _finalized_project(project)
    assert resume_project_supervisor(project, now="2026-09-08T12:00:00Z")["ok"] is True
    source = tmp_path / "source.md"
    source.write_text("synthetic queue source", encoding="utf-8")
    queue = tmp_path / "queue.db"
    queued = run_project_supervisor_once(
        project,
        source_path=source,
        queue_path=queue,
        now="2026-09-08T12:01:00Z",
    )
    assert queued["ok"] is True

    backup = tmp_path / "backup"
    created = backup_project(project, backup, now="2026-09-08T12:02:00Z")
    assert created["ok"] is True, created.get("errors")
    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["extensions"]["queue"]["included"] is True
    assert (backup / ".docops-project" / "queue.sqlite3").is_file()

    restored_root = tmp_path / "restored"
    restored = restore_project(backup, restored_root, now="2026-09-08T12:03:00Z")
    assert restored["ok"] is True, restored.get("errors")
    assert restored["data"]["queue_restored"] is True
    supervisor = json.loads((restored_root / ".docops-project" / "supervisor.json").read_text(encoding="utf-8"))
    assert supervisor["queue_path"] == str(restored_root / ".docops-project" / "queue.sqlite3")
    health = inspect_project_health(restored_root, now="2026-09-08T12:03:00Z")
    assert health["data"]["checks"]["queue"]["job_count"] == 1


def test_project_mutation_cas_and_idempotency_cover_evidence_governance_and_supervisor(tmp_path: Path):
    project = tmp_path / "project"
    _finalized_project(project)

    def revision() -> int:
        return json.loads((project / "project.json").read_text(encoding="utf-8"))["write_revision"]

    claim_a_revision = revision()
    claim_a = __import__("docops").record_project_claim(
        project,
        {"claim_id": "claim-a", "text": "A", "classification": "opinion", "evidence_refs": []},
        expected_revision=claim_a_revision,
        idempotency_key="claim-a-write",
        now="2026-09-08T12:00:00Z",
    )
    assert claim_a["ok"] is True
    claim_a_replay = __import__("docops").record_project_claim(
        project,
        {"claim_id": "claim-a", "text": "A", "classification": "opinion", "evidence_refs": []},
        expected_revision=claim_a_revision,
        idempotency_key="claim-a-write",
        now="2026-09-08T12:30:00Z",
    )
    assert claim_a_replay == claim_a

    claim_b = __import__("docops").record_project_claim(
        project,
        {"claim_id": "claim-b", "text": "B", "classification": "opinion", "evidence_refs": []},
        expected_revision=revision(),
        idempotency_key="claim-b-write",
        now="2026-09-08T12:00:00Z",
    )
    assert claim_b["ok"] is True
    conflict_revision = revision()
    conflict = __import__("docops").record_project_conflict(
        project,
        {"conflict_id": "conflict-ab", "claim_ids": ["claim-a", "claim-b"], "relation": "contradicts"},
        expected_revision=conflict_revision,
        idempotency_key="conflict-ab-write",
        now="2026-09-08T12:00:00Z",
    )
    assert conflict["ok"] is True
    assert (
        __import__("docops").record_project_conflict(
            project,
            {"conflict_id": "conflict-ab", "claim_ids": ["claim-a", "claim-b"], "relation": "contradicts"},
            expected_revision=conflict_revision,
            idempotency_key="conflict-ab-write",
            now="2026-09-08T12:30:00Z",
        )
        == conflict
    )
    stored_claims = json.loads((project / ".docops" / "project-evidence.json").read_text(encoding="utf-8"))["claims"]
    assert all("conflict-ab" in item["conflict_ids"] for item in stored_claims)

    stale = __import__("docops").record_project_claim(
        project,
        {"claim_id": "claim-stale", "text": "stale", "classification": "opinion", "evidence_refs": []},
        expected_revision=1,
        idempotency_key="claim-stale-write",
    )
    assert stale["ok"] is False
    assert stale["errors"][0]["code"] == "STALE_REVISION"

    register_revision = revision()
    registered = __import__("docops").register_source_governance(
        project,
        {"source_id": "source-cas", "source_type": "article", "captured_at": "2026-09-08T12:00:00Z"},
        expected_revision=register_revision,
        idempotency_key="source-cas-register",
        now="2026-09-08T12:00:00Z",
    )
    assert registered["ok"] is True
    revoke_revision = revision()
    revoked = __import__("docops").revoke_project_source(
        project,
        "source-cas",
        expected_revision=revoke_revision,
        idempotency_key="source-cas-revoke",
        now="2026-09-08T12:00:00Z",
    )
    assert revoked["ok"] is True
    assert (
        __import__("docops").revoke_project_source(
            project,
            "source-cas",
            expected_revision=revoke_revision,
            idempotency_key="source-cas-revoke",
            now="2026-09-08T12:30:00Z",
        )
        == revoked
    )

    resume_revision = revision()
    resumed = resume_project_supervisor(
        project,
        expected_revision=resume_revision,
        idempotency_key="supervisor-resume",
        now="2026-09-08T12:00:00Z",
    )
    assert resumed["ok"] is True
    assert (
        resume_project_supervisor(
            project,
            expected_revision=resume_revision,
            idempotency_key="supervisor-resume",
            now="2026-09-08T12:30:00Z",
        )
        == resumed
    )


def test_editorial_derivative_seam_is_removed(tmp_path: Path):
    project = tmp_path / "project"
    _finalized_project(project)
    assert not hasattr(__import__("docops"), "validate_project_derivatives")
    assert not hasattr(__import__("docops"), "prepare_project_derivatives")


def test_enrichment_is_scoped_budgeted_and_receipt_bound(tmp_path: Path):
    project = tmp_path / "project"
    finalized = _finalized_project(project)
    unsafe = dispatch_project_enrichment(
        project,
        {"request_id": "enrichment-unsafe", "allowed_artifacts": ["../outside"]},
        now="2026-09-08T12:00:00Z",
    )
    assert unsafe["ok"] is False
    assert unsafe["errors"][0]["code"] == "INVALID_INPUT"
    dispatched = dispatch_project_enrichment(
        project,
        {
            "request_id": "enrichment-fixture",
            "allowed_artifacts": ["skill"],
            "budget": {"max_files": 1, "max_bytes": 100},
            "harness": None,
        },
        now="2026-09-08T12:00:00Z",
    )
    assert dispatched["ok"] is True
    request = dispatched["data"]["request"]
    receipt = {
        "schema_version": 1,
        "request_id": "enrichment-fixture",
        "base_project_revision_id": request["base_project_revision_id"],
        "policy_revision": request["policy_revision"],
        "candidate_id": "candidate-fixture",
        "base_release_id": "release-fixture",
        "base_composition_hash": "a" * 64,
        "candidate_composition_hash": "b" * 64,
        "tool": {"name": "fixture", "version": "1"},
        "inputs": [{"path": "source.md", "sha256": "c" * 64}],
        "outputs": [{"path": "skill/skill.md", "sha256": "d" * 64, "size": 20}],
        "validation": {"ok": True},
        "provenance": {},
    }
    acknowledged = submit_project_enrichment(project, "enrichment-fixture", receipt, now="2026-09-08T12:00:00Z")
    assert acknowledged["ok"] is True, acknowledged.get("errors")
    assert acknowledged["data"]["request"]["state"] == "acknowledged"
    assert (
        acknowledged["data"]["request"]["base_project_revision_id"]
        == request["base_project_revision_id"]
        == finalized["data"]["project_revision_id"]
    )

    second_request = dispatch_project_enrichment(
        project,
        {"request_id": "enrichment-fixture-2", "allowed_artifacts": ["skill"]},
        now="2026-09-08T12:00:00Z",
    )
    assert second_request["ok"] is True
    bad_receipt = dict(receipt)
    bad_receipt["request_id"] = "other-request"
    rejected = submit_project_enrichment(project, "enrichment-fixture-2", bad_receipt, now="2026-09-08T12:00:00Z")
    assert rejected["ok"] is False
    assert rejected["errors"][0]["code"] == "INVALID_INPUT"


def test_dependency_mitigation_cannot_mask_new_findings_or_changed_threat_model():
    raw = {
        "findings": [{"id": "ADV-1"}],
        "lockfile_hash": "a" * 64,
        "artifact_hash": "b" * 64,
        "threat_model": "local-persistent-client-v1",
        "dependencies": [{"name": "chromadb", "version": "1.5.9"}],
    }
    decision = {
        "decision": "tolerated",
        "finding_ids": ["ADV-1"],
        "artifact": "evidence/sbom.json",
        "artifact_hash": "b" * 64,
        "lockfile_hash": "a" * 64,
        "threat_model": "local-persistent-client-v1",
        "owner": "maintainer",
        "evidence_ref": "evidence-1",
        "expires_at": "2027-01-01T00:00:00Z",
        "dependency": "chromadb",
        "version": "1.5.9",
    }
    supported = validate_dependency_mitigation(raw, decision, now="2026-09-08T12:00:00Z")
    assert supported["ok"] is True
    changed = dict(decision, finding_ids=["ADV-1", "ADV-2"])
    assert validate_dependency_mitigation(raw, changed, now="2026-09-08T12:00:00Z")["ok"] is False
    altered_model = dict(decision, threat_model="different-model")
    altered_result = validate_dependency_mitigation(raw, altered_model, now="2026-09-08T12:00:00Z")
    assert altered_result["ok"] is False
    assert any(item["code"] == "MITIGATION_THREAT_MODEL_MISMATCH" for item in altered_result["errors"])
    expired = dict(decision, expires_at="2026-01-01T00:00:00Z")
    assert any(
        item["code"] == "MITIGATION_EXPIRED"
        for item in validate_dependency_mitigation(raw, expired, now="2026-09-08T12:00:00Z")["errors"]
    )


def test_delegation_rejects_conflict_changes_even_with_factual_scope(tmp_path: Path):
    project = tmp_path / "project"
    finalized = _finalized_project(project)
    proposed = propose_project_change(
        project,
        {
            "change_id": "change-conflict",
            "base_project_revision_id": finalized["data"]["project_revision_id"],
            "operations": [
                {
                    "type": "conflict_record",
                    "target_id": "conflict-1",
                    "expected_hash": "a" * 64,
                    "payload": {"claim_ids": ["claim-a", "claim-b"], "relation": "contradicts"},
                }
            ],
            "requested_by": "operator",
            "reason": "synthetic conflict",
            "dependency_graph": {"nodes": [], "edges": [], "unknown_dependencies": False},
        },
        now="2026-09-08T12:00:00Z",
    )
    assert proposed["ok"] is True
    created = create_delegated_authorization(
        project,
        {
            "authorization_id": "auth-factual-only",
            "owner": "fixture-owner",
            "actions": ["factual_update"],
            "source_ids": [],
            "authority_ref": "fixture-attestation",
            "expires_at": "2027-01-01T00:00:00Z",
            "budget": {"max_operations": 1, "used_operations": 0},
        },
        now="2026-09-08T12:00:00Z",
    )
    assert created["ok"] is True
    blocked = authorize_factual_change(project, "change-conflict", "auth-factual-only", now="2026-09-08T12:00:00Z")
    assert blocked["ok"] is False
    assert blocked["errors"][0]["code"] == "RIGHTS_BLOCKED"
