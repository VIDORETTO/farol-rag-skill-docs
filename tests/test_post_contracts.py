# seam-scope: compatibility-infrastructure (contract implementation fixtures)
from __future__ import annotations

import json
from pathlib import Path

from docops.contracts import validate_artifact
from docops.evaluator import evaluate_package
from docops.harness import read_harness_manifest
from docops.package_validator import validate_package
from docops.pipeline import PipelineOptions, run_pipeline
from docops.readiness import assess_readiness, record_release_evidence, record_skill_enrichment


def test_public_contract_rejects_missing_required_manifest_fields() -> None:
    result = validate_artifact("manifest", {"schema_version": 1})

    assert not result.ok
    assert "contract_required" in {error["code"] for error in result.errors}


def test_generated_manifest_type_drift_is_rejected_at_the_package_seam(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\n", encoding="utf-8")
    package = tmp_path / "package"
    assert run_pipeline(source, options=PipelineOptions(output_dir=package, slug="guide", license="MIT")).ok

    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["counts"] = "not-an-object"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = validate_package(package)

    assert not result.ok
    assert any(error["code"] == "contract_type" for error in result.errors)


def test_handoff_reader_uses_the_public_contract(tmp_path: Path) -> None:
    path = tmp_path / "harness.json"
    path.write_text(
        json.dumps({"schema_version": 1, "package_root": ".", "skills": "wrong", "mcp": {}}), encoding="utf-8"
    )

    try:
        read_harness_manifest(path)
    except ValueError as exc:
        assert "contract" in str(exc)
    else:
        raise AssertionError("invalid handoff unexpectedly passed")


def test_terminal_outcome_cannot_disagree_with_manifest_status(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\n", encoding="utf-8")
    package = tmp_path / "package"
    assert run_pipeline(source, options=PipelineOptions(output_dir=package, slug="guide", license="MIT")).ok

    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["outcome"]["status"] = "failed"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = validate_package(package)

    assert not result.ok
    assert "outcome_status_mismatch" in {error["code"] for error in result.errors}


def test_manifest_cannot_claim_skill_enrichment_without_evidence(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\n", encoding="utf-8")
    package = tmp_path / "package"
    assert run_pipeline(source, options=PipelineOptions(output_dir=package, slug="guide", license="MIT")).ok

    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["readiness"]["skill"] = "skill-enriched"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = validate_package(package)

    assert not result.ok
    assert "readiness_overclaim" in {error["code"] for error in result.errors}


def test_terminal_result_is_validated_by_the_public_result_contract(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\n", encoding="utf-8")
    result = run_pipeline(source, options=PipelineOptions(output_dir=tmp_path / "package", slug="guide", license="MIT"))

    contract = validate_artifact("result", result.to_dict())

    assert contract.ok, contract.errors


def test_skill_enrichment_requires_external_evidence_and_records_provenance(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\n", encoding="utf-8")
    package = tmp_path / "package"
    assert run_pipeline(source, options=PipelineOptions(output_dir=package, slug="guide", license="MIT")).ok
    skill = package / "skill" / "SKILL.md"
    skill.write_text(
        skill.read_text(encoding="utf-8").replace(
            "This structural scaffold contains headings and provenance only; an external `book-to-skill` skill may fold richer mental models into it.",
            "## Mental model\n\nThis enriched skill explains the guide decisions.",
        ),
        encoding="utf-8",
    )

    evidence_path = record_skill_enrichment(
        package, tool="book-to-skill", version="2.0", provenance={"source": "fixture"}
    )

    readiness = assess_readiness(package)
    assert evidence_path.is_file()
    assert readiness["skill"] == "skill-enriched"
    assert json.loads((package / "manifest.json").read_text(encoding="utf-8"))["readiness"]["skill"] == "skill-enriched"


def test_skill_enrichment_evidence_redacts_harness_provenance(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\n", encoding="utf-8")
    package = tmp_path / "package"
    assert run_pipeline(source, options=PipelineOptions(output_dir=package, slug="guide", license="MIT")).ok
    skill = package / "skill" / "SKILL.md"
    skill.write_text(
        skill.read_text(encoding="utf-8").replace(
            "This structural scaffold contains headings and provenance only; an external `book-to-skill` skill may fold richer mental models into it.",
            "## Mental model\n\nThis enriched skill explains the guide decisions.",
        ),
        encoding="utf-8",
    )
    secret = "z" * 24
    private_path = "C:" + r"\Users\gabri\private\provenance.txt"

    evidence_path = record_skill_enrichment(
        package,
        tool="book-to-skill",
        version="2.0",
        provenance={"note": "token=" + secret + " path=" + private_path},
    )

    serialized = evidence_path.read_text(encoding="utf-8")
    assert secret not in serialized
    assert private_path not in serialized


def test_release_evidence_requires_the_real_mcp_evaluation(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\n\nA guide about lifecycle.\n", encoding="utf-8")
    package = tmp_path / "package"
    assert run_pipeline(source, options=PipelineOptions(output_dir=package, slug="guide", license="MIT")).ok

    skill = package / "skill" / "SKILL.md"
    skill.write_text(
        skill.read_text(encoding="utf-8").replace(
            "This structural scaffold contains headings and provenance only; an external `book-to-skill` skill may fold richer mental models into it.",
            "## Mental model\n\nThis enriched skill explains the guide decisions.",
        ),
        encoding="utf-8",
    )
    record_skill_enrichment(package, tool="book-to-skill", version="2.0")
    golden = {
        "schema_version": 1,
        "reviewed": True,
        "cases": [{"query": "lifecycle", "expected_filepath": "guide.md", "kind": "factual", "reviewed": True}],
    }
    assert evaluate_package(package, golden, adapter="memory").ok

    try:
        record_release_evidence(package, version="1.0.1", gates={"tests": True})
    except ValueError as exc:
        assert "RAGFlow" in str(exc)
    else:
        raise AssertionError("memory evaluation unexpectedly qualified for release evidence")
