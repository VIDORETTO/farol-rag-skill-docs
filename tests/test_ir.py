# seam-scope: implementation-infrastructure (public IR boundary fixtures)
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from docops.ir import (
    BackendMapping,
    IRBlock,
    IRDocument,
    IRStore,
    IRValidationError,
    validate_ir_document,
)


def _document() -> IRDocument:
    return IRDocument(
        document_id="ir-document-fixture",
        source_id="source-fixture",
        source_revision_id="source-revision-fixture",
        artifact_id="artifact-fixture",
        content_hash="c" * 64,
        media_type="text/markdown",
        language="en",
        extractor={"name": "fixture", "version": "1.0", "execution": "local"},
        fidelity={"level": "structured-native", "capabilities": ["headings", "lists"], "degradations": []},
        rights_ref="rights-fixture",
        captured_at="2026-09-11T00:00:00Z",
        effective_at=None,
        region=None,
        blocks=[
            IRBlock(
                block_id="block-heading",
                parent_id=None,
                ordinal=0,
                kind="heading",
                text="Authentication",
                heading_path=["Authentication"],
                locators=[{"kind": "section", "label": "Authentication", "line": 1}],
                language="en",
                confidence=1.0,
                source_fragment_hash="a" * 64,
            ),
            IRBlock(
                block_id="block-paragraph",
                parent_id="block-heading",
                ordinal=1,
                kind="paragraph",
                text="Use a token.",
                heading_path=["Authentication"],
                locators=[{"kind": "line", "label": "2", "line": 2}],
                language="en",
                confidence=1.0,
                source_fragment_hash="b" * 64,
            ),
        ],
    )


def test_ir_round_trips_with_stable_hash_and_explicit_locator() -> None:
    document = _document()
    payload = document.to_dict()
    result = validate_ir_document(payload)

    assert result.ok, result.errors
    assert len(document.revision_hash()) == 64
    assert document.revision_hash() == IRDocument.from_dict(payload).revision_hash()
    restored = IRDocument.from_dict(json.loads(json.dumps(payload)))
    assert restored.to_dict() == payload
    assert restored.blocks[1].locators[0]["line"] == 2


def test_ir_validation_rejects_dangling_parent_and_missing_rights() -> None:
    payload = _document().to_dict()
    payload["blocks"][1]["parent_id"] = "missing"
    result = validate_ir_document(payload)
    assert not result.ok
    assert "dangling_parent" in {error["code"] for error in result.errors}

    payload = _document().to_dict()
    payload.pop("rights_ref")
    result = validate_ir_document(payload)
    assert not result.ok
    assert "required" in {error["code"] for error in result.errors}


def test_ir_validation_rejects_non_hex_content_hash_and_revision_mismatch() -> None:
    payload = _document().to_dict()
    payload["content_hash"] = "z" * 64
    result = validate_ir_document(payload)
    assert not result.ok
    assert "hash_mismatch" in {error["code"] for error in result.errors}

    payload = _document().to_dict()
    payload["revision_id"] = "0" * 64
    result = validate_ir_document(payload)
    assert not result.ok
    assert "hash_mismatch" in {error["code"] for error in result.errors}


def test_ir_validation_rejects_invalid_ranges_confidence_and_block_order() -> None:
    payload = _document().to_dict()
    payload["blocks"][1]["ordinal"] = 3
    payload["blocks"][1]["confidence"] = math.nan
    payload["blocks"][1]["locators"] = [{"kind": "line", "label": "0", "line": 0}]

    result = validate_ir_document(payload)

    assert not result.ok
    assert {"ordinal_sequence", "confidence", "locator_range"}.issubset({error["code"] for error in result.errors})


def test_ir_validation_rejects_parent_cycles() -> None:
    payload = _document().to_dict()
    payload["blocks"][0]["parent_id"] = "block-paragraph"

    result = validate_ir_document(payload)

    assert not result.ok
    assert "parent_cycle" in {error["code"] for error in result.errors}


def test_ir_store_is_immutable_and_atomic(tmp_path: Path) -> None:
    store = IRStore(tmp_path / "ir")
    document = _document()
    first = store.put(document)
    second = store.put(document)

    assert first == second
    assert (first / "ir-document.json").is_file()
    with pytest.raises(IRValidationError):
        store.put(
            IRDocument(
                **{**document.__dict__, "blocks": [IRBlock(**{**document.blocks[0].__dict__, "parent_id": "x"})]}
            )
        )

    # A failed validation cannot leave a staged partial revision behind.
    revision_dirs = [path for path in (tmp_path / "ir" / "ir-document-fixture").iterdir() if path.is_dir()]
    assert len(revision_dirs) == 1
    assert not list((tmp_path / "ir").rglob("*.tmp"))


def test_mapping_keeps_external_ids_out_of_canonical_ir(tmp_path: Path) -> None:
    mapping = BackendMapping(
        project_revision="project-1",
        ir_revision="ir-1",
        backend="ragflow",
        backend_version="0.27.2",
        dataset_id="dataset-external",
        entries=[{"block_id": "block-1", "document_id": "doc-external", "chunk_ids": ["chunk-external"]}],
    )
    path = IRStore(tmp_path / "ir").put_mapping(mapping)
    assert json.loads(path.read_text(encoding="utf-8"))["entries"][0]["chunk_ids"] == ["chunk-external"]
