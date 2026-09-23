# seam-scope: compatibility-infrastructure (external RAGFlow contract spike)
"""Opt-in contract spike for the pinned RAGFlow v0.27.2 runtime.

The core suite never starts Docker or contacts a remote service.  Set
``DOCOPS_RAGFLOW_INTEGRATION=1`` together with an endpoint, token, image digest
and SDK version to run this test against an operator-provisioned instance.
Missing external resources are reported as an explicit ``not_run`` skip.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from docops.backends.ragflow import RagFlowAdapter
from docops.ir import IRBlock
from docops.router import GlobalRouter

pytestmark = pytest.mark.integration

_PAGE_MARKERS = {
    "page_1": "FAROL_PAGE_ONE",
    "page_2": "FAROL_PAGE_TWO",
}


def _required_environment() -> tuple[str, str, str, str]:
    if os.environ.get("DOCOPS_RAGFLOW_INTEGRATION") != "1":
        pytest.skip("not_run: RAGFlow integration is opt-in")

    endpoint = os.environ.get("DOCOPS_RAGFLOW_ENDPOINT", "").strip()
    token = os.environ.get("DOCOPS_RAGFLOW_TOKEN", "").strip()
    image_digest = os.environ.get("DOCOPS_RAGFLOW_IMAGE_DIGEST", "").strip()
    sdk_version = os.environ.get("DOCOPS_RAGFLOW_SDK_VERSION", "").strip()
    missing = [
        name
        for name, value in (
            ("DOCOPS_RAGFLOW_ENDPOINT", endpoint),
            ("DOCOPS_RAGFLOW_TOKEN", token),
            ("DOCOPS_RAGFLOW_IMAGE_DIGEST", image_digest),
            ("DOCOPS_RAGFLOW_SDK_VERSION", sdk_version),
        )
        if not value
    ]
    if missing:
        pytest.skip(f"not_run: missing external RAGFlow inputs {', '.join(missing)}")
    if not re.fullmatch(r".+@sha256:[0-9a-f]{64}", image_digest):
        pytest.fail("RAGFlow image must be pinned by repository and sha256 digest")
    return endpoint, token, image_digest, sdk_version


def _sdk_value(value: object, name: str, default: object = None) -> object:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _sha256_identity(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _positive_page(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        page = value
    elif isinstance(value, float) and math.isfinite(value) and value.is_integer():
        page = int(value)
    elif isinstance(value, str) and re.fullmatch(r"[1-9]\d*", value.strip()):
        page = int(value.strip())
    else:
        return None
    return page if page >= 1 else None


def _position_records(value: object) -> list[object]:
    if isinstance(value, Mapping):
        return [value]
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    values = list(value)
    if not values:
        return []
    # RAGFlow emits either one flat [page, left, right, top, bottom] position
    # or a list of those structured records.  Keep the distinction explicit so
    # a truthy opaque value cannot satisfy the contract.
    if all(_is_number(item) for item in values):
        return [values]
    return values


def _structured_locators(chunk: object) -> list[dict[str, Any]]:
    """Return only canonical, verifiable RAGFlow PDF position records."""

    raw_positions = _sdk_value(chunk, "positions")
    locators: list[dict[str, Any]] = []
    for record in _position_records(raw_positions):
        if isinstance(record, Sequence) and not isinstance(record, (str, bytes, bytearray)):
            values = list(record)
            if len(values) < 5:
                continue
            raw_page = values[0]
            if isinstance(raw_page, Sequence) and not isinstance(raw_page, (str, bytes, bytearray)):
                page_values = list(raw_page)
                page = _positive_page(page_values[-1]) if page_values else None
            else:
                page = _positive_page(raw_page)
            coordinates = values[1:5]
            if page is None or not all(_is_number(item) for item in coordinates):
                continue
            left, right, top, bottom = (float(item) for item in coordinates)
            if right <= left or bottom <= top:
                continue
            locators.append(
                {
                    "page": page,
                    "shape": "sequence-page-bbox",
                    "bbox": [left, right, top, bottom],
                }
            )
    return locators


def _wait_for_dataset_absence(client: object, dataset_id: str, *, timeout_seconds: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while True:
        # RAGFlow's delete endpoint removes the dataset from the user's normal
        # listing immediately, while a follow-up list filtered by the deleted
        # ID returns a permission error.  The unfiltered listing is therefore
        # the provider-supported absence check for a dataset we just deleted.
        datasets = client.list_datasets(page=1, page_size=100)  # type: ignore[attr-defined]
        if not any(str(_sdk_value(dataset, "id", "")) == dataset_id for dataset in datasets):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.5)


def _fixture_pdf(path: Path) -> None:
    # Two tiny text pages keep the oracle independent of a production corpus.
    # The instance is still responsible for proving whether page locators are
    # exported by its parser.  Build a valid PDF with an xref table so the
    # oracle exercises parsing rather than malformed-input recovery.
    def page_stream(label: str) -> bytes:
        content = f"BT /F1 12 Tf 20 100 Td ({label}) Tj ET".encode("ascii")
        return f"<< /Length {len(content)} >>\nstream\n".encode("ascii") + content + b"\nendstream"

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Count 2 /Kids [3 0 R 4 0 R] >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Resources << /Font << /F1 7 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Resources << /Font << /F1 7 0 R >> >> /Contents 6 0 R >>",
        page_stream("FAROL_PAGE_ONE"),
        page_stream("FAROL_PAGE_TWO"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode("ascii"))
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    output.extend(b"".join(f"{offset:010d} 00000 n \n".encode("ascii") for offset in offsets[1:]))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    path.write_bytes(bytes(output))


def _wait_for_parse(dataset: object, document_id: str, *, timeout_seconds: float = 120.0) -> object:
    deadline = time.monotonic() + timeout_seconds
    while True:
        documents = dataset.list_documents(id=document_id, page=1, page_size=1)  # type: ignore[attr-defined]
        assert documents, "RAGFlow no longer exposes the uploaded document"
        document = documents[0]
        status = str(getattr(document, "run", getattr(document, "status", ""))).casefold()
        if status in {"fail", "failed", "cancel", "cancelled", "canceled", "error"}:
            pytest.fail(f"RAGFlow parsing failed with status {status!r}")
        if (
            status in {"done", "success", "succeeded", "completed"}
            or float(getattr(document, "progress", 0.0) or 0.0) >= 1.0
        ):
            return document
        if time.monotonic() >= deadline:
            pytest.fail("RAGFlow parsing did not finish before the 120 second deadline")
        time.sleep(0.5)


def test_ragflow_v0272_dataset_parse_retrieve_and_cleanup(tmp_path: Path) -> None:
    endpoint, token, image_digest, sdk_version = _required_environment()
    if sdk_version != "0.27.2":
        pytest.fail(f"RAGFlow SDK contract is pinned to 0.27.2, got {sdk_version!r}")

    try:
        from ragflow_sdk import RAGFlow  # type: ignore[import-not-found]
    except ImportError:
        pytest.skip("not_run: ragflow_sdk 0.27.2 is not installed in the integration environment")

    fixture = tmp_path / "two-pages.pdf"
    _fixture_pdf(fixture)
    dataset: object | None = None
    dataset_id = ""
    document_id = ""
    chunks: list[object] = []
    retrieved: list[object] = []
    locator_summary: list[dict[str, Any]] = []
    marker_pages = {key: set() for key in _PAGE_MARKERS}
    cleanup = {"delete_requested": False, "dataset_absent": False}
    dataset_name = f"farol-v2-spike-{os.urandom(8).hex()}"
    client = RAGFlow(api_key=token, base_url=endpoint)
    try:
        # A bounded list proves that the authenticated SDK can reach the
        # instance without putting any corpus or credential in the receipt.
        assert isinstance(client.list_datasets(page=1, page_size=1), list)
        dataset = client.create_dataset(name=dataset_name)
        dataset_id = str(_sdk_value(dataset, "id", ""))
        assert dataset_id, "RAGFlow created a dataset without an identity"
        assert str(_sdk_value(dataset, "name", "")) == dataset_name
        documents = dataset.upload_documents([{"display_name": fixture.name, "blob": fixture.read_bytes()}])
        assert documents, "RAGFlow accepted a dataset but returned no uploaded document"
        document = documents[0]
        document_id = str(_sdk_value(document, "id", ""))
        assert document_id, "RAGFlow returned an uploaded document without an identity"
        dataset.parse_documents([document_id])
        document = _wait_for_parse(dataset, document_id)
        assert str(_sdk_value(document, "id", "")) == document_id
        parse_status = str(_sdk_value(document, "run", _sdk_value(document, "status", ""))).casefold()
        assert (
            parse_status in {"done", "success", "succeeded", "completed"}
            or float(_sdk_value(document, "progress", 0.0) or 0.0) >= 1.0
        )
        chunks = document.list_chunks()
        assert chunks, "RAGFlow parsing produced no chunks"
        observed_pages: set[int] = set()
        for chunk_index, chunk in enumerate(chunks):
            chunk_document_id = str(_sdk_value(chunk, "document_id", ""))
            assert chunk_document_id == document_id, (
                f"RAGFlow chunk {chunk_index} is not owned by the uploaded document"
            )
            content = str(_sdk_value(chunk, "content", ""))
            assert content.strip(), f"RAGFlow chunk {chunk_index} has no content"
            locators = _structured_locators(chunk)
            assert locators, f"RAGFlow chunk {chunk_index} has no structured page locator"
            pages = {int(locator["page"]) for locator in locators}
            observed_pages.update(pages)
            locator_summary.append(
                {
                    "chunk_ordinal": chunk_index,
                    "pages": sorted(pages),
                    "shapes": sorted({str(locator["shape"]) for locator in locators}),
                }
            )
            for page_key, marker in _PAGE_MARKERS.items():
                if marker in content:
                    marker_pages[page_key].update(pages)

        chunk_text = "\n".join(str(_sdk_value(chunk, "content", "")) for chunk in chunks)
        assert _PAGE_MARKERS["page_1"] in chunk_text
        assert _PAGE_MARKERS["page_2"] in chunk_text
        assert 1 in marker_pages["page_1"], "page-one content was not tied to a page-one locator"
        assert 2 in marker_pages["page_2"], "page-two content was not tied to a page-two locator"
        assert {1, 2}.issubset(observed_pages), "RAGFlow did not expose both PDF pages in structured locators"

        retrieved = client.retrieve(
            question="Which page contains FAROL_PAGE_TWO?",
            dataset_ids=[dataset_id],
            page=1,
            page_size=5,
            top_k=5,
        )
        assert retrieved, "RAGFlow retrieval returned no result for known fixture content"
        retrieved_dataset_ids = {str(_sdk_value(hit, "dataset_id", "")) for hit in retrieved}
        retrieved_document_ids = {str(_sdk_value(hit, "document_id", "")) for hit in retrieved}
        retrieved_pages: set[int] = set()
        for hit_index, hit in enumerate(retrieved):
            assert str(_sdk_value(hit, "dataset_id", "")) == dataset_id, (
                f"RAGFlow retrieval hit {hit_index} is not owned by the requested dataset"
            )
            assert str(_sdk_value(hit, "document_id", "")) == document_id, (
                f"RAGFlow retrieval hit {hit_index} is not owned by the uploaded document"
            )
            hit_content = str(_sdk_value(hit, "content", ""))
            assert hit_content.strip(), f"RAGFlow retrieval hit {hit_index} has no content"
            hit_locators = _structured_locators(hit)
            assert hit_locators, f"RAGFlow retrieval hit {hit_index} has no structured page locator"
            retrieved_pages.update(int(locator["page"]) for locator in hit_locators)
        assert retrieved_dataset_ids == {dataset_id}, "RAGFlow retrieval returned an unexpected dataset"
        assert retrieved_document_ids == {document_id}, (
            "RAGFlow retrieval returned a different or unidentified document"
        )
        retrieved_text = "\n".join(str(_sdk_value(hit, "content", "")) for hit in retrieved)
        assert _PAGE_MARKERS["page_2"] in retrieved_text, "RAGFlow retrieval did not return the requested page content"
        assert 2 in retrieved_pages, "RAGFlow retrieval did not return a page-two locator"
    finally:
        if dataset_id:
            cleanup["delete_requested"] = True
            client.delete_datasets(ids=[dataset_id])
            cleanup["dataset_absent"] = _wait_for_dataset_absence(client, dataset_id)

    assert cleanup == {"delete_requested": True, "dataset_absent": True}, (
        "RAGFlow cleanup did not prove dataset absence"
    )

    safe_receipt = {
        "schema_version": 1,
        "status": "passed",
        "runtime": {
            "sdk_version": sdk_version,
            "image_digest_sha256": _sha256_identity(image_digest),
        },
        "operations": {
            "health": "passed",
            "dataset_create": "passed",
            "upload": "passed",
            "parse_terminal": "passed",
            "chunks": "passed",
            "locators": "passed",
            "retrieval": "passed",
            "cleanup": "passed",
        },
        "fixture": {
            "name": fixture.name,
            "sha256": _sha256_identity(fixture.read_bytes()),
        },
        "dataset": {
            "name_sha256": _sha256_identity(dataset_name),
            "id_sha256": _sha256_identity(dataset_id),
        },
        "document": {
            "id_sha256": _sha256_identity(document_id),
            "chunk_count": len(chunks),
        },
        "pages": {
            "required": 2,
            "observed": sorted({page for pages in marker_pages.values() for page in pages}),
            "page_1_content_verified": True,
            "page_2_content_verified": True,
        },
        "locators": {
            "chunks_with_structured_positions": len(locator_summary),
            "pages": sorted({page for item in locator_summary for page in item["pages"]}),
            "shapes": sorted({shape for item in locator_summary for shape in item["shapes"]}),
        },
        "retrieval": {
            "hit_count": len(retrieved),
            "owned_dataset_ids_sha256": sorted(
                {_sha256_identity(_sdk_value(hit, "dataset_id", "")) for hit in retrieved}
            ),
            "owned_document_ids_sha256": sorted(
                {_sha256_identity(_sdk_value(hit, "document_id", "")) for hit in retrieved}
            ),
            "pages": sorted(retrieved_pages),
            "page_2_content_verified": True,
        },
        "cleanup": cleanup,
    }
    receipt_json = json.dumps(safe_receipt, ensure_ascii=False, sort_keys=True)
    assert safe_receipt["status"] == "passed"
    assert "token" not in safe_receipt
    assert "endpoint" not in safe_receipt
    assert str(tmp_path) not in receipt_json
    assert all(marker not in receipt_json for marker in _PAGE_MARKERS.values())
    for private_value in (dataset_id, document_id, dataset_name):
        if len(private_value) >= 8:
            assert private_value not in receipt_json
    if len(token) >= 8:
        assert token not in receipt_json
    assert endpoint not in receipt_json
    print(f"RAGFLOW_RECEIPT {receipt_json}")


def test_farol_ragflow_adapter_real_lifecycle_mapping_query_and_cleanup() -> None:
    endpoint, token, image_digest, sdk_version = _required_environment()
    if sdk_version != "0.27.2":
        pytest.fail(f"RAGFlow SDK contract is pinned to 0.27.2, got {sdk_version!r}")

    try:
        from ragflow_sdk import RAGFlow  # type: ignore[import-not-found]
    except ImportError:
        pytest.skip("not_run: ragflow_sdk 0.27.2 is not installed in the integration environment")

    identity = os.urandom(8).hex()
    marker = f"FAROL_ADAPTER_{identity.upper()}"
    project_revision = f"project-{identity}"
    ir_revision = f"ir-{identity}"
    block_id = f"block-{identity}"
    source_id = f"source-{identity}"
    source_revision_id = f"source-revision-{identity}"
    block_text = f"{marker} is present in the canonical IR block."
    canonical_block = {
        "block_id": block_id,
        "text": block_text,
        "source_id": source_id,
        "source_revision_id": source_revision_id,
        "locators": [{"kind": "section", "label": "Adapter Integration"}],
        "heading_path": ["Adapter Integration"],
        "kind": "paragraph",
        "source_fragment_hash": hashlib.sha256(marker.encode("utf-8")).hexdigest(),
    }
    documents = [
        {
            "document_id": f"ir-document-{identity}",
            "content": block_text,
            "blocks": [canonical_block],
        }
    ]
    ir_block = IRBlock(
        block_id=block_id,
        parent_id=None,
        ordinal=0,
        kind="paragraph",
        text=block_text,
        heading_path=["Adapter Integration"],
        locators=[{"kind": "section", "label": "Adapter Integration"}],
        source_fragment_hash=canonical_block["source_fragment_hash"],
    )
    router = GlobalRouter([{"node_id": "adapter", "title": "Adapter Integration", "slug": "adapter"}])
    adapter = RagFlowAdapter(
        config={
            "endpoint": endpoint,
            "allow_insecure_localhost": True,
            "timeout_seconds": 120,
            "retry_limit": 1,
        }
    )
    candidate = None
    dataset_ids: list[str] = []
    result_summary: dict[str, Any] = {}
    raw_client = RAGFlow(api_key=token, base_url=endpoint)
    try:
        probe = adapter.probe()
        assert probe.status == "healthy"
        candidate = adapter.prepare(
            project_revision,
            ir_revision,
            metadata={"documents": documents},
        )
        first_dataset_id = str(candidate.metadata.get("dataset_id") or "")
        assert first_dataset_id
        dataset_ids.append(first_dataset_id)
        index = adapter.apply(candidate)
        assert index.state == "queryable"
        mapping = adapter.mapping(index)
        assert len(mapping.entries) == 1
        assert mapping.entries[0]["block_id"] == block_id
        assert mapping.entries[0]["source_id"] == source_id
        assert mapping.entries[0]["locators"] == [{"kind": "section", "label": "Adapter Integration"}]
        query_request = adapter.query_request(marker, top_k=1, project_revision=project_revision)
        evidence = adapter.query(index, query_request)
        assert evidence.outcome == "ok"
        assert len(evidence.hits) == 1
        assert evidence.hits[0]["block_id"] == block_id
        assert evidence.hits[0]["source_id"] == source_id
        filtered = router.filter_evidence(query_request, evidence.hits, [ir_block])
        assert filtered.outcome == "ok"
        assert filtered.hits[0]["citations"] == [
            f"source/{source_id}@{source_revision_id}#section=Adapter%20Integration"
        ]
        snapshot = adapter.snapshot(index)
        assert snapshot.index_revision == index.index_revision
        first_projection = {
            "block_id": filtered.hits[0]["block_id"],
            "source_id": filtered.hits[0]["source_id"],
            "source_revision_id": filtered.hits[0]["source_revision_id"],
            "citations": filtered.hits[0]["citations"],
        }
        first_index_revision = index.index_revision
        adapter.discard(candidate)
        candidate = None
        assert _wait_for_dataset_absence(raw_client, first_dataset_id)

        candidate = adapter.prepare(project_revision, ir_revision, metadata={"documents": documents})
        second_dataset_id = str(candidate.metadata.get("dataset_id") or "")
        assert second_dataset_id and second_dataset_id != first_dataset_id
        dataset_ids.append(second_dataset_id)
        rebuilt_index = adapter.apply(candidate)
        rebuilt_query = adapter.query(rebuilt_index, query_request)
        rebuilt_filtered = router.filter_evidence(query_request, rebuilt_query.hits, [ir_block])
        rebuilt_projection = {
            "block_id": rebuilt_filtered.hits[0]["block_id"],
            "source_id": rebuilt_filtered.hits[0]["source_id"],
            "source_revision_id": rebuilt_filtered.hits[0]["source_revision_id"],
            "citations": rebuilt_filtered.hits[0]["citations"],
        }
        assert rebuilt_projection == first_projection
        assert rebuilt_index.index_revision != first_index_revision
        result_summary = {
            "probe": "passed",
            "prepare": "passed",
            "apply": "passed",
            "mapping": "passed",
            "query": "passed",
            "citations": "passed",
            "snapshot": "passed",
            "rebuild": "passed",
        }
    finally:
        if candidate is not None:
            adapter.discard(candidate)
        adapter.close()

    assert dataset_ids and all(_wait_for_dataset_absence(raw_client, dataset_id) for dataset_id in dataset_ids)
    safe_receipt = {
        "schema_version": 1,
        "status": "passed",
        "runtime": {
            "sdk_version": sdk_version,
            "image_digest_sha256": _sha256_identity(image_digest),
        },
        "operations": {**result_summary, "cleanup": "passed"},
        "canonical_mapping": {
            "block_id_sha256": _sha256_identity(block_id),
            "source_id_sha256": _sha256_identity(source_id),
            "locator_kind": "section",
        },
    }
    receipt_json = json.dumps(safe_receipt, ensure_ascii=False, sort_keys=True)
    assert token not in receipt_json
    assert endpoint not in receipt_json
    assert marker not in receipt_json
    assert all(dataset_id not in receipt_json for dataset_id in dataset_ids)
    print(f"RAGFLOW_ADAPTER_RECEIPT {receipt_json}")
