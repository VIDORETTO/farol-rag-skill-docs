from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import docops


def _request(
    source: Path,
    output: Path,
    *,
    mode: str = "run",
    policy: str = "direct",
    layers: tuple[str, ...] = ("conceptual", "factual"),
) -> docops.OperationRequest:
    return docops.OperationRequest(
        source,
        docops.OperationOptions(
            output_dir=output,
            source_root=source.parent,
            slug="publication-guide",
            license="MIT",
            mode=mode,
            publication_policy=policy,
            layers=layers,
        ),
    )


def _candidate_fixture(tmp_path: Path) -> tuple[Path, Path, str]:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\nInitial facts.\n", encoding="utf-8")
    output = tmp_path / "package"
    initial = docops.apply(docops.plan(_request(source, output)))
    assert initial.ok, initial.errors

    (source / "guide.md").write_text("# Guide\nCandidate facts.\n", encoding="utf-8")
    prepared = docops.apply(docops.plan(_request(source, output, mode="update", policy="candidate")))
    assert prepared.ok, prepared.errors
    return source, output, str(prepared.outcome["candidate_id"])


def _candidate_dir(output: Path, candidate_id: str) -> Path:
    return output.parent / f".{output.name}.candidates" / candidate_id


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "docops", *args, "--json"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _evaluate_candidate(output: Path, candidate_id: str, tmp_path: Path) -> None:
    candidate = _candidate_dir(output, candidate_id)
    golden = tmp_path / "golden.json"
    golden.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "reviewed": True,
                "cases": [
                    {
                        "id": "candidate-facts",
                        "query": "Candidate facts",
                        "expected_filepath": "guide.md",
                        "kind": "factual",
                        "reviewed": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    evaluated = _run_cli(
        "evaluate",
        "--package",
        str(candidate),
        "--cases",
        str(golden),
        "--adapter",
        "memory",
    )
    assert evaluated.returncode == 0, evaluated.stdout + evaluated.stderr
    assert json.loads(evaluated.stdout)["ok"] is True


def test_candidate_content_flag_does_not_authorize_publication(tmp_path: Path) -> None:
    _source, output, candidate_id = _candidate_fixture(tmp_path)
    candidate_path = output.parent / f".{output.name}.candidates" / candidate_id
    candidate_receipt_path = candidate_path / ".docops" / "candidate.json"
    candidate_receipt = json.loads(candidate_receipt_path.read_text(encoding="utf-8"))
    candidate_receipt["approved"] = True
    candidate_receipt["status"] = "approved"
    candidate_receipt_path.write_text(json.dumps(candidate_receipt), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "docops",
            "candidate-publish",
            "--package",
            str(output),
            "--candidate-id",
            candidate_id,
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 1, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["errors"][0]["code"] == "approval_missing"
    assert (output / "manifest.json").is_file()


def test_candidate_approval_and_publication_are_explicit_and_transactional(tmp_path: Path) -> None:
    _source, output, candidate_id = _candidate_fixture(tmp_path)
    _evaluate_candidate(output, candidate_id, tmp_path)

    approved = _run_cli(
        "candidate-approve",
        "--package",
        str(output),
        "--candidate-id",
        candidate_id,
        "--actor",
        "editor@example.test",
        "--role",
        "human_approver",
    )
    assert approved.returncode == 0, approved.stdout + approved.stderr
    approval_payload = json.loads(approved.stdout)
    assert approval_payload["status"] == "approved"
    active_before = (output / "manifest.json").read_bytes()

    published = _run_cli(
        "candidate-publish",
        "--package",
        str(output),
        "--candidate-id",
        candidate_id,
    )
    assert published.returncode == 0, published.stdout + published.stderr
    publication_payload = json.loads(published.stdout)
    assert publication_payload["status"] == "published"
    assert publication_payload["approval_id"] == approval_payload["approval_id"]
    assert (output / "manifest.json").read_bytes() != active_before

    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["publication"]["candidate_id"] == candidate_id
    assert manifest["publication"]["approval_id"] == approval_payload["approval_id"]
    candidate = _candidate_dir(output, candidate_id)
    receipt = json.loads((candidate / ".docops" / "candidate.json").read_text(encoding="utf-8"))
    assert receipt["status"] == "published"
    assert (candidate / ".docops" / "publication.json").is_file()
    assert docops.inspect(output)["active"]["validation"]["ok"] is True


def test_candidate_evidence_change_invalidates_approval_and_preserves_active(tmp_path: Path) -> None:
    _source, output, candidate_id = _candidate_fixture(tmp_path)
    _evaluate_candidate(output, candidate_id, tmp_path)
    approved = _run_cli(
        "candidate-approve",
        "--package",
        str(output),
        "--candidate-id",
        candidate_id,
        "--actor",
        "editor@example.test",
        "--role",
        "human_approver",
    )
    assert approved.returncode == 0, approved.stdout
    active_before = (output / "manifest.json").read_bytes()

    candidate = _candidate_dir(output, candidate_id)
    evaluation_path = candidate / ".docops" / "evaluation.json"
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    evaluation["metrics"]["recall_at_5"] = 0.5
    evaluation_path.write_text(json.dumps(evaluation), encoding="utf-8")

    published = _run_cli(
        "candidate-publish",
        "--package",
        str(output),
        "--candidate-id",
        candidate_id,
    )
    assert published.returncode == 1
    assert json.loads(published.stdout)["errors"][0]["code"] == "approval_invalidated"
    assert (output / "manifest.json").read_bytes() == active_before


def test_candidate_approval_rejects_advanced_active_base(tmp_path: Path) -> None:
    source, output, candidate_id = _candidate_fixture(tmp_path)
    _evaluate_candidate(output, candidate_id, tmp_path)
    approved = _run_cli(
        "candidate-approve",
        "--package",
        str(output),
        "--candidate-id",
        candidate_id,
        "--actor",
        "editor@example.test",
        "--role",
        "human_approver",
    )
    assert approved.returncode == 0, approved.stdout

    source.joinpath("guide.md").write_text("# Guide\nBase advanced.\n", encoding="utf-8")
    advanced = docops.apply(docops.plan(_request(source, output, mode="update")))
    assert advanced.ok, advanced.errors
    active_after_advance = (output / "manifest.json").read_bytes()

    published = _run_cli(
        "candidate-publish",
        "--package",
        str(output),
        "--candidate-id",
        candidate_id,
    )
    assert published.returncode == 1
    assert json.loads(published.stdout)["errors"][0]["code"] == "stale_base"
    assert (output / "manifest.json").read_bytes() == active_after_advance


def test_candidate_approval_role_is_bound_to_scope(tmp_path: Path) -> None:
    source, output, factual_candidate_id = _candidate_fixture(tmp_path)
    source.joinpath("guide.md").write_text("# Guide\nFactual-only candidate.\n", encoding="utf-8")
    factual = docops.apply(
        docops.plan(
            _request(
                source,
                output,
                mode="update",
                policy="candidate",
                layers=("factual",),
            )
        )
    )
    assert factual.ok, factual.errors
    factual_candidate_id = str(factual.outcome["candidate_id"])
    _evaluate_candidate(output, factual_candidate_id, tmp_path)

    wrong_factual_role = _run_cli(
        "candidate-approve",
        "--package",
        str(output),
        "--candidate-id",
        factual_candidate_id,
        "--actor",
        "editor@example.test",
        "--role",
        "human_approver",
    )
    assert wrong_factual_role.returncode == 1
    assert json.loads(wrong_factual_role.stdout)["errors"][0]["code"] == "approval_role_mismatch"
    delegated = _run_cli(
        "candidate-approve",
        "--package",
        str(output),
        "--candidate-id",
        factual_candidate_id,
        "--actor",
        "factual-policy-v1",
        "--role",
        "delegated_policy",
    )
    assert delegated.returncode == 0, delegated.stdout + delegated.stderr

    conceptual = docops.apply(
        docops.plan(
            _request(
                source,
                output,
                mode="update",
                policy="candidate",
                layers=("conceptual", "factual"),
            )
        )
    )
    assert conceptual.ok, conceptual.errors
    conceptual_candidate_id = str(conceptual.outcome["candidate_id"])
    _evaluate_candidate(output, conceptual_candidate_id, tmp_path)
    wrong_conceptual_role = _run_cli(
        "candidate-approve",
        "--package",
        str(output),
        "--candidate-id",
        conceptual_candidate_id,
        "--actor",
        "factual-policy-v1",
        "--role",
        "delegated_policy",
    )
    assert wrong_conceptual_role.returncode == 1
    assert json.loads(wrong_conceptual_role.stdout)["errors"][0]["code"] == "approval_role_mismatch"


@pytest.mark.parametrize(
    "failpoint",
    (
        "before-active-to-backup",
        "after-active-to-backup-before-journal",
        "after-active-to-backup",
        "after-stage-to-active-before-journal",
        "after-stage-to-active",
    ),
)
def test_candidate_publication_recovers_a_journaled_crash_before_retry(tmp_path: Path, failpoint: str) -> None:
    _source, output, candidate_id = _candidate_fixture(tmp_path)
    _evaluate_candidate(output, candidate_id, tmp_path)
    approved = _run_cli(
        "candidate-approve",
        "--package",
        str(output),
        "--candidate-id",
        candidate_id,
        "--actor",
        "editor@example.test",
        "--role",
        "human_approver",
    )
    assert approved.returncode == 0, approved.stdout + approved.stderr

    crashed = subprocess.run(
        [
            sys.executable,
            "-m",
            "docops",
            "candidate-publish",
            "--package",
            str(output),
            "--candidate-id",
            candidate_id,
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "DOCOPS_TEST_PROMOTION_FAILPOINT": failpoint},
    )
    assert crashed.returncode == 86, crashed.stdout + crashed.stderr
    assert (output.parent / f".{output.name}.docops.promotion.json").is_file()

    retried = _run_cli(
        "candidate-publish",
        "--package",
        str(output),
        "--candidate-id",
        candidate_id,
    )
    assert retried.returncode == 0, retried.stdout + retried.stderr
    assert json.loads(retried.stdout)["status"] == "published"


def test_revoked_source_dependency_blocks_candidate_approval(tmp_path: Path) -> None:
    _source, output, candidate_id = _candidate_fixture(tmp_path)
    _evaluate_candidate(output, candidate_id, tmp_path)
    candidate_manifest = json.loads(
        (_candidate_dir(output, candidate_id) / "manifest.json").read_text(encoding="utf-8")
    )
    canonical = candidate_manifest["source"]["canonical"]
    (output / ".docops" / "source-registry.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "registry_revision": "revoked-source-fixture",
                "registrations": [
                    {
                        "source_id": "docs-main",
                        "canonical": canonical,
                        "status": "withdrawn",
                    }
                ],
                "snapshots": [],
                "withdrawals": [],
            }
        ),
        encoding="utf-8",
    )

    blocked = _run_cli(
        "candidate-approve",
        "--package",
        str(output),
        "--candidate-id",
        candidate_id,
        "--actor",
        "editor@example.test",
        "--role",
        "human_approver",
    )

    assert blocked.returncode == 1
    assert json.loads(blocked.stdout)["errors"][0]["code"] == "source_revoked"


def test_approval_persists_an_authenticated_external_authority_attestation(tmp_path: Path) -> None:
    _source, output, candidate_id = _candidate_fixture(tmp_path)
    _evaluate_candidate(output, candidate_id, tmp_path)
    approved = _run_cli(
        "candidate-approve",
        "--package",
        str(output),
        "--candidate-id",
        candidate_id,
        "--actor",
        "editor@example.test",
        "--role",
        "human_approver",
        "--authority-json",
        json.dumps(
            {
                "authenticated": True,
                "source": "test-idp",
                "subject": "editor@example.test",
                "roles": ["human_approver"],
                "proof": "signed-test-attestation",
            }
        ),
    )
    assert approved.returncode == 0, approved.stdout + approved.stderr
    receipt = json.loads(
        (_candidate_dir(output, candidate_id) / ".docops" / "approval.json").read_text(encoding="utf-8")
    )
    authority = receipt["authority"]
    assert authority["authenticated"] is True
    assert authority["source"] == "test-idp"
    assert authority["subject"] == "editor@example.test"
    assert authority["role"] == "human_approver"
    assert authority["proof_hash"]
    assert "proof" not in authority


def test_unverified_authority_cannot_approve_a_candidate(tmp_path: Path) -> None:
    _source, output, candidate_id = _candidate_fixture(tmp_path)
    _evaluate_candidate(output, candidate_id, tmp_path)
    blocked = _run_cli(
        "candidate-approve",
        "--package",
        str(output),
        "--candidate-id",
        candidate_id,
        "--actor",
        "editor@example.test",
        "--role",
        "human_approver",
        "--authority-json",
        json.dumps(
            {
                "authenticated": False,
                "source": "untrusted-input",
                "subject": "editor@example.test",
                "roles": ["human_approver"],
                "proof": "not-verified",
            }
        ),
    )
    assert blocked.returncode == 1
    assert json.loads(blocked.stdout)["errors"][0]["code"] == "approval_authority_invalid"
