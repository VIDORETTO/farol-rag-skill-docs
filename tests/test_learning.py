# seam-scope: implementation-infrastructure (learning public seams)
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import docops
from docops.learning import read_learning_proposal, rollback_learning_guard


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "docops", *args, "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _package(tmp_path: Path) -> tuple[Path, Path, Path]:
    source = tmp_path / "source"
    source.mkdir()
    document = source / "guide.md"
    document.write_text("# Guide\nInitial facts.\n", encoding="utf-8")
    output = tmp_path / "package"
    request = docops.OperationRequest(
        source,
        docops.OperationOptions(
            output_dir=output,
            source_root=source.parent,
            slug="learning-guide",
            license="MIT",
            mode="run",
            layers=("conceptual", "factual"),
            publication_policy="direct",
            index_rag=False,
        ),
    )
    result = docops.apply(docops.plan(request))
    assert result.ok, result.errors
    return source, document, output


def _proposal(
    *,
    proposal_id: str,
    claim_text: str,
    claim_kind: str,
    scope: str,
    privacy: str,
    evidence: list[dict[str, object]],
    author_id: str = "user-1",
) -> dict[str, object]:
    normalized_evidence: list[dict[str, object]] = []
    for evidence_item in evidence:
        item = dict(evidence_item)
        kind = str(item.get("kind") or "")
        reference = str(item.get("reference") or "")
        quote = item.get("quote")
        evidence_hash = hashlib.sha256(
            json.dumps(
                {"kind": kind, "reference": reference, "quote": quote},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        verifier = "external:fixture-verifier"
        receipt_hash = hashlib.sha256(
            json.dumps(
                {"evidence_hash": evidence_hash, "verifier": verifier, "status": "verified"},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        item["verification"] = {
            "status": "verified" if item.get("independent") is True else "unverified",
            "verifier": verifier if item.get("independent") is True else None,
            "provenance": "fixture://verified-source" if item.get("independent") is True else None,
            "authority": "fixture-authority" if item.get("independent") is True else None,
            "license": "MIT" if item.get("independent") is True else None,
            "supports_claim": item.get("independent") is True,
            "evidence_hash": evidence_hash if item.get("independent") is True else None,
            "receipt_hash": receipt_hash if item.get("independent") is True else None,
        }
        normalized_evidence.append(item)
    return {
        "proposal_id": proposal_id,
        "capture_opt_in": True,
        "excerpt": f"Minimized excerpt for {proposal_id}.",
        "claim": {"text": claim_text, "kind": claim_kind, "scope": scope},
        "evidence": normalized_evidence,
        "source": {"kind": "conversation", "conversation_id": f"conversation-{proposal_id}", "author_id": author_id},
        "consent": {
            "holder_id": author_id,
            "scope": privacy,
            "purpose": "governed-knowledge-improvement",
            "granted_at": "2026-09-05T00:00:00Z",
            "expires_at": "2030-01-01T00:00:00Z",
            "revoked_at": None,
        },
        "privacy": privacy,
    }


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_learning_capture_requires_opt_in_and_stays_quarantined(tmp_path: Path) -> None:
    _source, _document, package = _package(tmp_path)
    proposal = _proposal(
        proposal_id="quarantined-fact",
        claim_text="The fixture service uses a deterministic retry policy.",
        claim_kind="factual_correction",
        scope="project",
        privacy="project",
        evidence=[{"kind": "primary_source", "reference": "fixture://policy", "independent": True}],
    )
    proposal["approved"] = True
    proposal["capture_opt_in"] = False
    proposal_path = tmp_path / "proposal.json"
    _write_json(proposal_path, proposal)

    missing_opt_in = _run_cli("learning-submit", "--package", str(package), "--proposal", str(proposal_path))
    assert missing_opt_in.returncode == 1
    assert json.loads(missing_opt_in.stdout)["errors"][0]["code"] == "capture_not_opted_in"

    proposal["capture_opt_in"] = True
    _write_json(proposal_path, proposal)
    submitted = _run_cli(
        "learning-submit",
        "--package",
        str(package),
        "--proposal",
        str(proposal_path),
        "--capture-opt-in",
    )
    assert submitted.returncode == 0, submitted.stdout + submitted.stderr
    report = json.loads(submitted.stdout)
    assert report["state"] == "quarantined"
    assert report["searchable"] is False
    assert report["approval_field_ignored"] is True
    assert not (package / "rag" / "documents" / "learning" / "quarantined-fact.md").exists()
    stored = read_learning_proposal(package, "quarantined-fact")
    assert stored["state"] == "quarantined"
    assert stored["consent"]["holder_id"] == "user-1"
    assert stored["consent"]["scope"] == "project"
    assert stored["consent"]["consent_hash"]


def test_learning_capture_rejects_expired_or_revoked_consent(tmp_path: Path) -> None:
    _source, _document, package = _package(tmp_path)
    for proposal_id, mutation, expected_code in (
        (
            "expired-consent",
            lambda consent: consent.update({"expires_at": "2026-09-05T12:00:00Z"}),
            "consent_expired",
        ),
        (
            "revoked-consent",
            lambda consent: consent.update({"revoked_at": "2026-09-05T11:00:00Z"}),
            "consent_revoked",
        ),
    ):
        proposal = _proposal(
            proposal_id=proposal_id,
            claim_text="Consent must be active before capture.",
            claim_kind="factual_correction",
            scope="project",
            privacy="project",
            evidence=[],
        )
        mutation(proposal["consent"])
        proposal_path = tmp_path / f"{proposal_id}.json"
        _write_json(proposal_path, proposal)

        result = _run_cli(
            "learning-submit",
            "--package",
            str(package),
            "--proposal",
            str(proposal_path),
            "--capture-opt-in",
            "--now",
            "2026-09-05T13:00:00Z",
        )

        assert result.returncode == 1
        assert json.loads(result.stdout)["errors"][0]["code"] == expected_code


def test_learning_does_not_treat_an_independent_flag_as_verified_evidence(tmp_path: Path) -> None:
    _source, _document, package = _package(tmp_path)
    proposal = _proposal(
        proposal_id="unverified-fact",
        claim_text="The fixture service uses a deterministic retry policy.",
        claim_kind="factual_correction",
        scope="project",
        privacy="project",
        evidence=[{"kind": "primary_source", "reference": "fixture://policy", "independent": True}],
    )
    proposal["evidence"][0].pop("verification", None)
    proposal_path = tmp_path / "unverified.json"
    _write_json(proposal_path, proposal)

    submitted = _run_cli(
        "learning-submit",
        "--package",
        str(package),
        "--proposal",
        str(proposal_path),
        "--capture-opt-in",
    )
    assert submitted.returncode == 0, submitted.stdout + submitted.stderr

    admitted = _run_cli(
        "learning-review",
        "--package",
        str(package),
        "--proposal-id",
        "unverified-fact",
        "--decision",
        "admit",
        "--actor",
        "reviewer-1",
    )
    assert admitted.returncode == 1
    assert json.loads(admitted.stdout)["errors"][0]["code"] == "learning_admission_blocked"


def test_learning_review_separates_verified_facts_preferences_and_agent_output(tmp_path: Path) -> None:
    _source, _document, package = _package(tmp_path)
    fact_path = tmp_path / "fact.json"
    _write_json(
        fact_path,
        _proposal(
            proposal_id="verified-fact",
            claim_text="The fixture service uses a deterministic retry policy.",
            claim_kind="factual_correction",
            scope="project",
            privacy="project",
            evidence=[{"kind": "primary_source", "reference": "fixture://policy", "independent": True}],
        ),
    )
    submitted = _run_cli(
        "learning-submit",
        "--package",
        str(package),
        "--proposal",
        str(fact_path),
        "--capture-opt-in",
    )
    assert submitted.returncode == 0, submitted.stdout + submitted.stderr

    admitted = _run_cli(
        "learning-review",
        "--package",
        str(package),
        "--proposal-id",
        "verified-fact",
        "--decision",
        "admit",
        "--actor",
        "reviewer-1",
    )
    assert admitted.returncode == 0, admitted.stdout + admitted.stderr
    admitted_report = json.loads(admitted.stdout)
    assert admitted_report["code"] == "learning_admitted"
    assert admitted_report["reindex_required"] is True
    assert admitted_report["publication_allowed"] is False
    fact_document = package / "rag" / "documents" / "learning" / "verified-fact.md"
    assert fact_document.is_file()
    assert "deterministic retry policy" in fact_document.read_text(encoding="utf-8")

    preference_path = tmp_path / "preference.json"
    _write_json(
        preference_path,
        _proposal(
            proposal_id="private-preference",
            claim_text="The operator prefers short Portuguese summaries.",
            claim_kind="preference",
            scope="private",
            privacy="private",
            evidence=[{"kind": "user_confirmation", "reference": "fixture://confirmation", "independent": True}],
        ),
    )
    assert (
        _run_cli(
            "learning-submit",
            "--package",
            str(package),
            "--proposal",
            str(preference_path),
            "--capture-opt-in",
        ).returncode
        == 0
    )
    preference_review = _run_cli(
        "learning-review",
        "--package",
        str(package),
        "--proposal-id",
        "private-preference",
        "--decision",
        "admit",
        "--actor",
        "reviewer-1",
    )
    assert preference_review.returncode == 0, preference_review.stdout + preference_review.stderr
    assert (package / ".docops" / "learning" / "private" / "private-preference.json").is_file()
    assert not (package / "rag" / "documents" / "learning" / "private-preference.md").exists()

    agent_path = tmp_path / "agent.json"
    _write_json(
        agent_path,
        _proposal(
            proposal_id="agent-output",
            claim_text="The assistant suggested enabling the fixture mode.",
            claim_kind="agent_response",
            scope="project",
            privacy="project",
            evidence=[{"kind": "agent_response", "reference": "fixture://assistant", "independent": True}],
        ),
    )
    assert (
        _run_cli(
            "learning-submit",
            "--package",
            str(package),
            "--proposal",
            str(agent_path),
            "--capture-opt-in",
        ).returncode
        == 0
    )
    blocked = _run_cli(
        "learning-review",
        "--package",
        str(package),
        "--proposal-id",
        "agent-output",
        "--decision",
        "admit",
        "--actor",
        "reviewer-1",
    )
    assert blocked.returncode == 1
    assert json.loads(blocked.stdout)["errors"][0]["code"] == "learning_admission_blocked"
    assert not (package / "rag" / "documents" / "learning" / "agent-output.md").exists()


def test_learning_revocation_leaves_tombstone_and_blocks_historical_rollback(tmp_path: Path) -> None:
    _source, document, package = _package(tmp_path)
    proposal_path = tmp_path / "proposal.json"
    _write_json(
        proposal_path,
        _proposal(
            proposal_id="revoked-fact",
            claim_text="This verified claim must not survive revocation.",
            claim_kind="factual_correction",
            scope="project",
            privacy="project",
            evidence=[{"kind": "primary_source", "reference": "fixture://revocation", "independent": True}],
        ),
    )
    assert (
        _run_cli(
            "learning-submit",
            "--package",
            str(package),
            "--proposal",
            str(proposal_path),
            "--capture-opt-in",
        ).returncode
        == 0
    )
    assert (
        _run_cli(
            "learning-review",
            "--package",
            str(package),
            "--proposal-id",
            "revoked-fact",
            "--decision",
            "admit",
            "--actor",
            "reviewer-1",
        ).returncode
        == 0
    )
    document.write_text("# Guide\nUpdated facts.\n", encoding="utf-8")
    rebuilt = docops.apply(
        docops.plan(
            docops.OperationRequest(
                _source,
                docops.OperationOptions(
                    output_dir=package,
                    source_root=_source.parent,
                    slug="learning-guide",
                    license="MIT",
                    mode="update",
                    layers=("conceptual", "factual"),
                    publication_policy="direct",
                    index_rag=False,
                ),
            )
        )
    )
    assert rebuilt.ok, {"errors": rebuilt.errors, "outcome": rebuilt.outcome}

    revoked = _run_cli(
        "learning-review",
        "--package",
        str(package),
        "--proposal-id",
        "revoked-fact",
        "--decision",
        "revoke",
        "--actor",
        "reviewer-1",
    )
    assert revoked.returncode == 0, revoked.stdout + revoked.stderr
    report = json.loads(revoked.stdout)
    assert report["code"] == "learning_revoked"
    assert report["rollback_blocked"] is True
    derived_path = package / "rag" / "documents" / "learning" / "revoked-fact.md"
    assert not derived_path.exists()

    historical = tmp_path / "historical"
    historical_target = historical / "rag" / "documents" / "learning" / "revoked-fact.md"
    historical_target.parent.mkdir(parents=True)
    historical_target.write_text("old revoked derivative\n", encoding="utf-8")
    conflict = rollback_learning_guard(package, historical)
    assert conflict == {
        "proposal_id": "revoked-fact",
        "path": "rag/documents/learning/revoked-fact.md",
        "code": "revoked_learning_derivative",
    }
