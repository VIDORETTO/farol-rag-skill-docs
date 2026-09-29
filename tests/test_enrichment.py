# seam-scope: implementation-infrastructure (enrichment public seams)
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import docops
from docops.harness import export_enrichment_request
from docops.readiness import assess_readiness


def _request(
    source: Path,
    output: Path,
    *,
    publication_policy: str = "direct",
    mode: str = "run",
) -> docops.OperationRequest:
    return docops.OperationRequest(
        source,
        docops.OperationOptions(
            output_dir=output,
            source_root=source.parent,
            slug="enrichment-guide",
            license="MIT",
            mode=mode,
            publication_policy=publication_policy,
        ),
    )


def _candidate_fixture(tmp_path: Path) -> tuple[Path, Path, str, dict[str, object], bytes]:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\nInitial facts.\n", encoding="utf-8")
    output = tmp_path / "package"
    initial = docops.apply(docops.plan(_request(source, output)))
    assert initial.ok, initial.errors
    active_manifest = (output / "manifest.json").read_bytes()

    (source / "guide.md").write_text("# Guide\nCandidate facts.\n", encoding="utf-8")
    created = docops.apply(docops.plan(_request(source, output, mode="update", publication_policy="candidate")))
    assert created.ok, created.errors
    candidate_id = str(created.outcome["candidate_id"])
    request = export_enrichment_request(output, candidate_id)
    return source, output, candidate_id, request, active_manifest


def _receipt(
    request: dict[str, object],
    candidate_id: str,
    *,
    outputs: list[dict[str, str]],
    base_release_id: str | None = None,
    base_composition_hash: str | None = None,
    provenance: dict[str, object] | None = None,
) -> dict[str, object]:
    snapshot = request["snapshot"]
    assert isinstance(snapshot, dict)
    input_hashes = snapshot["input_hashes"]
    assert isinstance(input_hashes, dict)
    return {
        "schema_version": 1,
        "request_id": request["request_id"],
        "candidate_id": candidate_id,
        "base_release_id": base_release_id or request["base_release_id"],
        "base_composition_hash": base_composition_hash or request["base_composition_hash"],
        "candidate_composition_hash": snapshot["candidate_revisions"]["composition_hash"],
        "tool": {"name": "book-to-skill", "version": "fixture"},
        "inputs": [{"path": path, "sha256": digest} for path, digest in input_hashes.items()],
        "outputs": outputs,
        "validation": {"ok": True},
        "provenance": provenance or {"source": "synthetic-fixture"},
    }


def _submit(
    output: Path,
    candidate_id: str,
    source_dir: Path,
    receipt: dict[str, object],
    receipt_path: Path,
) -> subprocess.CompletedProcess[str]:
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "docops",
            "candidate-submit",
            "--package",
            str(output),
            "--candidate-id",
            candidate_id,
            "--source-dir",
            str(source_dir),
            "--receipt",
            str(receipt_path),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_candidate_submit_rejects_scope_escape_without_touching_active(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\nInitial facts.\n", encoding="utf-8")
    output = tmp_path / "package"

    initial = docops.apply(docops.plan(_request(source, output)))
    assert initial.ok, initial.errors
    active_manifest = (output / "manifest.json").read_bytes()

    (source / "guide.md").write_text("# Guide\nCandidate facts.\n", encoding="utf-8")
    created = docops.apply(docops.plan(_request(source, output, mode="update", publication_policy="candidate")))
    assert created.ok, created.errors
    candidate_id = created.outcome["candidate_id"]
    request = export_enrichment_request(output, candidate_id)

    source_dir = tmp_path / "external-output"
    source_dir.mkdir()
    (source_dir / "manifest.json").write_text("must never be imported\n", encoding="utf-8")
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "request_id": request["request_id"],
                "candidate_id": candidate_id,
                "base_release_id": request["base_release_id"],
                "base_composition_hash": request["base_composition_hash"],
                "candidate_composition_hash": request["snapshot"]["candidate_revisions"]["composition_hash"],
                "tool": {"name": "book-to-skill", "version": "fixture"},
                "inputs": [
                    {"path": path, "sha256": digest} for path, digest in request["snapshot"]["input_hashes"].items()
                ],
                "outputs": [
                    {
                        "path": "../manifest.json",
                        "sha256": "0" * 64,
                    }
                ],
                "validation": {"ok": True},
                "provenance": {},
            }
        ),
        encoding="utf-8",
    )

    submitted = subprocess.run(
        [
            sys.executable,
            "-m",
            "docops",
            "candidate-submit",
            "--package",
            str(output),
            "--candidate-id",
            candidate_id,
            "--source-dir",
            str(source_dir),
            "--receipt",
            str(receipt),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert submitted.returncode != 0
    report = json.loads(submitted.stdout)
    assert report["errors"][0]["code"] == "enrichment_scope_rejected"
    assert (output / "manifest.json").read_bytes() == active_manifest


def test_candidate_request_is_explicit_and_missing_harness_stays_awaiting_enrichment(tmp_path: Path) -> None:
    _source, output, candidate_id, request, _active_manifest = _candidate_fixture(tmp_path)
    candidate_root = next(
        item["locator"] for item in docops.inspect(output)["candidates"] if item["candidate_id"] == candidate_id
    )
    candidate_path = output.parent / Path(candidate_root)
    (candidate_path / "harness.json").unlink()

    repeated = export_enrichment_request(output, candidate_id)
    assert repeated["request_id"] == request["request_id"]
    assert assess_readiness(candidate_path)["enrichment"] == "awaiting_enrichment"


def test_valid_external_enrichment_is_imported_only_into_candidate(tmp_path: Path) -> None:
    _source, output, candidate_id, request, active_manifest = _candidate_fixture(tmp_path)
    candidate = next(item for item in docops.inspect(output)["candidates"] if item["candidate_id"] == candidate_id)
    candidate_path = output.parent / Path(candidate["locator"])
    original_skill = (candidate_path / "skill" / "SKILL.md").read_text(encoding="utf-8")
    enriched = original_skill.replace(
        "structural scaffold contains headings and provenance only",
        "external harness supplied reviewed conceptual guidance",
    )
    source_dir = tmp_path / "external-output"
    (source_dir / "skill").mkdir(parents=True)
    skill_output = source_dir / "skill" / "SKILL.md"
    skill_output.write_text(enriched, encoding="utf-8")
    output_hash = hashlib.sha256(skill_output.read_bytes()).hexdigest()
    submitted = _submit(
        output,
        candidate_id,
        source_dir,
        _receipt(request, candidate_id, outputs=[{"path": "skill/SKILL.md", "sha256": output_hash}]),
        tmp_path / "receipt.json",
    )

    assert submitted.returncode == 0, submitted.stdout + submitted.stderr
    report = json.loads(submitted.stdout)
    assert report["status"] == "candidate_received"
    assert report["published"] is False
    assert (output / "manifest.json").read_bytes() == active_manifest
    assert (candidate_path / "skill" / "SKILL.md").read_text(encoding="utf-8") == enriched
    assert (candidate_path / ".docops" / "enrichment-receipt.json").is_file()
    inspected = docops.inspect(output)
    received = next(item for item in inspected["candidates"] if item["candidate_id"] == candidate_id)
    assert received["status"] == "review_required"
    assert assess_readiness(candidate_path)["enrichment"] == "skill-enriched"


def test_external_enrichment_rejects_base_drift_and_preserves_candidate(tmp_path: Path) -> None:
    _source, output, candidate_id, request, active_manifest = _candidate_fixture(tmp_path)
    candidate = next(item for item in docops.inspect(output)["candidates"] if item["candidate_id"] == candidate_id)
    candidate_path = output.parent / Path(candidate["locator"])
    before = (candidate_path / "skill" / "SKILL.md").read_bytes()
    source_dir = tmp_path / "external-output"
    (source_dir / "skill").mkdir(parents=True)
    skill_output = source_dir / "skill" / "SKILL.md"
    skill_output.write_text(
        (candidate_path / "skill" / "SKILL.md")
        .read_text(encoding="utf-8")
        .replace("structural scaffold contains headings and provenance only", "new content"),
        encoding="utf-8",
    )
    submitted = _submit(
        output,
        candidate_id,
        source_dir,
        _receipt(
            request,
            candidate_id,
            base_release_id="stale-release",
            outputs=[
                {
                    "path": "skill/SKILL.md",
                    "sha256": hashlib.sha256(skill_output.read_bytes()).hexdigest(),
                }
            ],
        ),
        tmp_path / "receipt.json",
    )

    assert submitted.returncode != 0
    report = json.loads(submitted.stdout)
    assert report["errors"][0]["code"] == "enrichment_base_mismatch"
    assert (output / "manifest.json").read_bytes() == active_manifest
    assert (candidate_path / "skill" / "SKILL.md").read_bytes() == before


def test_external_enrichment_rejects_reviewed_golden_and_credential_fields(tmp_path: Path) -> None:
    _source, output, candidate_id, request, active_manifest = _candidate_fixture(tmp_path)
    candidate = next(item for item in docops.inspect(output)["candidates"] if item["candidate_id"] == candidate_id)
    candidate_path = output.parent / Path(candidate["locator"])
    source_dir = tmp_path / "external-output"
    source_dir.mkdir()
    (source_dir / "golden.json").write_text("must not enter candidate\n", encoding="utf-8")
    golden_hash = hashlib.sha256((source_dir / "golden.json").read_bytes()).hexdigest()
    submitted = _submit(
        output,
        candidate_id,
        source_dir,
        _receipt(request, candidate_id, outputs=[{"path": "golden.json", "sha256": golden_hash}]),
        tmp_path / "golden-receipt.json",
    )
    assert submitted.returncode != 0
    assert json.loads(submitted.stdout)["errors"][0]["code"] == "enrichment_scope_rejected"

    credential_receipt = _receipt(
        request,
        candidate_id,
        outputs=[{"path": "golden.json", "sha256": golden_hash}],
        provenance={"api_token": "must-not-be-accepted"},
    )
    submitted = _submit(
        output,
        candidate_id,
        source_dir,
        credential_receipt,
        tmp_path / "credential-receipt.json",
    )
    assert submitted.returncode != 0
    assert json.loads(submitted.stdout)["errors"][0]["code"] == "enrichment_private_data"
    assert (output / "manifest.json").read_bytes() == active_manifest
    assert (candidate_path / "golden.json").exists() is False
