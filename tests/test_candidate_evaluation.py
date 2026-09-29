# seam-scope: implementation-infrastructure (candidate evaluation public seams)
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from docops.evaluator import evaluate_package
from docops.pipeline import PipelineOptions, run_pipeline
from docops.revisions import package_revisions


def _package(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text(
        "# Authentication\n\nToken validation and errors.\n",
        encoding="utf-8",
    )
    output = tmp_path / "candidate"
    result = run_pipeline(
        source,
        options=PipelineOptions(output_dir=output, slug="fixture", license="MIT"),
    )
    assert result.ok
    return output


def test_unsupported_response_claim_fails_the_fidelity_gate(tmp_path: Path) -> None:
    package = _package(tmp_path)
    golden = {
        "schema_version": 1,
        "reviewed": True,
        "cases": [
            {
                "id": "case-critical",
                "query": "How are authentication tokens validated?",
                "expected_filepath": "guide.md",
                "kind": "factual",
                "reviewed": True,
            }
        ],
    }
    revisions = package_revisions(package, golden=golden)
    response_receipt = {
        "schema_version": 1,
        "generation_id": "generation-candidate",
        "candidate_id": "candidate-fixture",
        "package_composition_hash": revisions["composition_hash"],
        "golden_revision": revisions["golden_revision"],
        "evaluator": {
            "name": "fixture-response-judge",
            "version": "1.0",
            "independent": True,
        },
        "cases": [
            {
                "case_id": "case-critical",
                "critical": True,
                "claims": [
                    {
                        "claim_id": "claim-unsupported",
                        "supported": False,
                        "requires_citation": True,
                        "citations": [],
                    }
                ],
            }
        ],
    }

    result = evaluate_package(
        package,
        golden,
        adapter="memory",
        response_receipt=response_receipt,
    )

    assert not result.ok
    assert any(error["code"] == "response_fidelity_below_threshold" for error in result.errors)


def test_evaluate_cli_imports_external_response_receipt(tmp_path: Path) -> None:
    package = _package(tmp_path)
    golden = {
        "schema_version": 1,
        "reviewed": True,
        "cases": [
            {
                "id": "case-critical",
                "query": "How are authentication tokens validated?",
                "expected_filepath": "guide.md",
                "kind": "factual",
                "reviewed": True,
            }
        ],
    }
    revisions = package_revisions(package, golden=golden)
    cases_path = tmp_path / "golden.json"
    cases_path.write_text(json.dumps(golden), encoding="utf-8")
    receipt_path = tmp_path / "response-receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generation_id": "generation-candidate",
                "candidate_id": "candidate-fixture",
                "package_composition_hash": revisions["composition_hash"],
                "golden_revision": revisions["golden_revision"],
                "evaluator": {
                    "name": "fixture-response-judge",
                    "version": "1.0",
                    "independent": True,
                },
                "cases": [
                    {
                        "case_id": "case-critical",
                        "critical": True,
                        "claims": [
                            {
                                "claim_id": "claim-unsupported",
                                "supported": False,
                                "requires_citation": True,
                                "citations": [],
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "docops",
            "evaluate",
            "--package",
            str(package),
            "--cases",
            str(cases_path),
            "--adapter",
            "memory",
            "--response-receipt",
            str(receipt_path),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 1, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["metadata"]["response"]["status"] == "failed"
    assert payload["metadata"]["configuration"]["adapter"] == "memory"
    assert payload["metadata"]["revisions"]["composition_hash"] == revisions["composition_hash"]
    assert any(error["code"] == "critical_response_claim_unsupported" for error in payload["errors"])


def test_response_metrics_use_not_applicable_for_zero_denominator(tmp_path: Path) -> None:
    package = _package(tmp_path)
    golden = {
        "schema_version": 1,
        "reviewed": True,
        "cases": [
            {
                "id": "case-no-claims",
                "query": "Authentication",
                "expected_filepath": "guide.md",
                "kind": "factual",
                "reviewed": True,
            }
        ],
    }
    revisions = package_revisions(package, golden=golden)
    receipt = {
        "schema_version": 1,
        "generation_id": "generation-empty",
        "candidate_id": "candidate-fixture",
        "package_composition_hash": revisions["composition_hash"],
        "golden_revision": revisions["golden_revision"],
        "evaluator": {"name": "fixture-response-judge", "version": "1.0", "independent": True},
        "cases": [{"case_id": "case-no-claims", "claims": []}],
    }

    result = evaluate_package(package, golden, adapter="memory", response_receipt=receipt)

    assert result.ok, result.errors
    assert result.metrics["response_fidelity"] is None
    assert result.metrics["citation_coverage"] is None
    assert result.metadata["response"]["status"] == "not_applicable"
    assert result.metadata["response"]["metric_status"] == {
        "response_fidelity": "not_applicable",
        "citation_coverage": "not_applicable",
    }


def test_supported_response_claims_produce_fidelity_and_citation_metrics(tmp_path: Path) -> None:
    package = _package(tmp_path)
    golden = {
        "schema_version": 1,
        "reviewed": True,
        "cases": [
            {
                "id": "case-supported",
                "query": "How are authentication tokens validated?",
                "expected_filepath": "guide.md",
                "kind": "factual",
                "reviewed": True,
            }
        ],
    }
    revisions = package_revisions(package, golden=golden)
    receipt = {
        "schema_version": 1,
        "generation_id": "generation-supported",
        "candidate_id": "candidate-fixture",
        "package_composition_hash": revisions["composition_hash"],
        "golden_revision": revisions["golden_revision"],
        "evaluator": {"name": "fixture-response-judge", "version": "1.0", "independent": True},
        "cases": [
            {
                "case_id": "case-supported",
                "claims": [
                    {
                        "claim_id": "claim-supported",
                        "supported": True,
                        "requires_citation": True,
                        "citations": ["guide.md"],
                    }
                ],
            }
        ],
    }

    result = evaluate_package(package, golden, adapter="memory", response_receipt=receipt)

    assert result.ok, result.errors
    assert result.metrics["response_fidelity"] == 1.0
    assert result.metrics["citation_coverage"] == 1.0
    assert result.metadata["response"]["status"] == "passed"
    assert result.metadata["response"]["generation_id"] == "generation-supported"
    assert result.metadata["response"]["receipt_hash"]
    evidence = json.loads((package / ".docops" / "evaluation.json").read_text(encoding="utf-8"))
    assert evidence["response"]["generation_id"] == "generation-supported"


def test_critical_response_claim_fails_even_when_average_fidelity_is_high(tmp_path: Path) -> None:
    package = _package(tmp_path)
    golden = {
        "schema_version": 1,
        "reviewed": True,
        "cases": [
            {
                "id": "case-critical",
                "query": "Authentication",
                "expected_filepath": "guide.md",
                "kind": "factual",
                "reviewed": True,
            }
        ],
    }
    revisions = package_revisions(package, golden=golden)
    claims = [
        {
            "claim_id": f"claim-{index}",
            "supported": index < 100,
            "requires_citation": False,
        }
        for index in range(101)
    ]
    receipt = {
        "schema_version": 1,
        "generation_id": "generation-critical",
        "candidate_id": "candidate-fixture",
        "package_composition_hash": revisions["composition_hash"],
        "golden_revision": revisions["golden_revision"],
        "evaluator": {"name": "fixture-response-judge", "version": "1.0", "independent": True},
        "cases": [{"case_id": "case-critical", "critical": True, "claims": claims}],
    }

    result = evaluate_package(package, golden, adapter="memory", response_receipt=receipt)

    assert not result.ok
    assert result.metrics["response_fidelity"] > 0.98
    assert result.metadata["response"]["critical_failures"] == 1
    assert any(error["code"] == "critical_response_claim_unsupported" for error in result.errors)


def test_lexical_adapter_stays_diagnostic_and_does_not_claim_response_fidelity(tmp_path: Path) -> None:
    package = _package(tmp_path)
    golden = {
        "schema_version": 1,
        "reviewed": True,
        "cases": [
            {
                "query": "Authentication",
                "expected_filepath": "guide.md",
                "kind": "factual",
                "reviewed": True,
            }
        ],
    }

    result = evaluate_package(package, golden, adapter="lexical")

    assert result.ok, result.errors
    assert result.metadata["mode"] == "diagnostic"
    assert "response" not in result.metadata
    assert "response_fidelity" not in result.metrics
    assert any("diagnostic" in diagnostic.lower() for diagnostic in result.diagnostics)
    assert result.metadata["configuration"]["mode"] == "diagnostic"


def test_response_receipt_is_rejected_after_candidate_composition_drift(tmp_path: Path) -> None:
    package = _package(tmp_path)
    golden = {
        "schema_version": 1,
        "reviewed": True,
        "cases": [
            {
                "id": "case-drift",
                "query": "Authentication",
                "expected_filepath": "guide.md",
                "kind": "factual",
                "reviewed": True,
            }
        ],
    }
    revisions = package_revisions(package, golden=golden)
    receipt = {
        "schema_version": 1,
        "generation_id": "generation-drift",
        "candidate_id": "candidate-fixture",
        "package_composition_hash": revisions["composition_hash"],
        "golden_revision": revisions["golden_revision"],
        "evaluator": {"name": "fixture-response-judge", "version": "1.0", "independent": True},
        "cases": [
            {
                "case_id": "case-drift",
                "claims": [
                    {
                        "claim_id": "claim-supported",
                        "supported": True,
                        "requires_citation": True,
                        "citations": ["guide.md"],
                    }
                ],
            }
        ],
    }
    skill_path = package / "skill" / "SKILL.md"
    skill_path.write_text(skill_path.read_text(encoding="utf-8") + "\nDrift.\n", encoding="utf-8")

    result = evaluate_package(package, golden, adapter="memory", response_receipt=receipt)

    assert not result.ok
    assert any(error["code"] == "response_receipt_stale" for error in result.errors)
