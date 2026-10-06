# seam-scope: implementation-infrastructure (public format extractor fixtures)
from __future__ import annotations

import math
from pathlib import Path

from pypdf import PdfWriter

from docops.extractors import ExtractorPolicy
from docops.extractors.pdf import DoclingOcrAdapter, PdfExtractor
from docops.ir import validate_ir_document


def _pdf_page(text: str, *, page_count: int = 1) -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Count {page_count} /Kids [{' '.join(f'{3 + index} 0 R' for index in range(page_count))}] >>".encode(),
    ]
    for index in range(page_count):
        content_id = 3 + page_count + index
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Resources << /Font << /F1 {3 + page_count * 2} 0 R >> >> /Contents {content_id} 0 R >>".encode()
        )
    for index in range(page_count):
        value = f"PAGE_{index + 1}_{text}".encode()
        stream = b"BT /F1 12 Tf 20 100 Td (" + value + b") Tj ET"
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.append(b"<< /Producer (Farol fixture) >>")
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for object_id, body in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{object_id} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(output)


def _policy(**kwargs: object) -> ExtractorPolicy:
    return ExtractorPolicy(
        rights_ref="rights-pdf",
        source_id="source-pdf",
        source_revision_id="revision-pdf",
        required_fidelity="structured-native",
        **kwargs,
    )


def _blank_pdf(path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with path.open("wb") as stream:
        writer.write(stream)


def test_textual_pdf_preserves_page_locators(tmp_path: Path) -> None:
    source = tmp_path / "guide.pdf"
    source.write_bytes(_pdf_page("KNOWN", page_count=2))
    result = PdfExtractor().extract(source, _policy(), {})

    assert result.document is not None
    assert result.receipt.fidelity == "structured-native"
    assert [block.locators[0]["page"] for block in result.document.blocks] == [1, 2]
    assert "PAGE_1_KNOWN" in " ".join(block.text or "" for block in result.document.blocks)
    assert validate_ir_document(result.document).ok


def test_scanned_pdf_is_quarantined_without_authorized_ocr(tmp_path: Path) -> None:
    source = tmp_path / "scan.pdf"
    _blank_pdf(source)
    result = PdfExtractor().extract(source, _policy(), {})

    assert result.document is None
    assert result.receipt.status == "quarantined"
    assert result.receipt.errors[0]["code"] == "ocr_required"


def test_malformed_pdf_reports_a_typed_parse_failure_instead_of_requesting_ocr(tmp_path: Path) -> None:
    source = tmp_path / "malformed.pdf"
    source.write_bytes(b"this is not a PDF")

    result = PdfExtractor().extract(source, _policy(), {})

    assert result.document is None
    assert result.receipt.status == "failed"
    assert result.receipt.errors[0]["code"] == "malformed"


def test_encrypted_pdf_reports_a_typed_encryption_failure(tmp_path: Path) -> None:
    source = tmp_path / "encrypted.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt("secret")
    with source.open("wb") as stream:
        writer.write(stream)

    result = PdfExtractor().extract(source, _policy(), {})

    assert result.document is None
    assert result.receipt.status == "failed"
    assert result.receipt.errors[0]["code"] == "encrypted"


def test_ocr_requires_opt_in_and_low_confidence_stays_quarantined(tmp_path: Path) -> None:
    source = tmp_path / "scan.pdf"
    _blank_pdf(source)
    calls: list[str] = []

    def ocr(path: Path, _policy: ExtractorPolicy):
        calls.append(path.name)
        return [{"page": 1, "text": "OCR text", "confidence": 0.4}]

    denied = PdfExtractor(ocr=ocr).extract(source, _policy(), {})
    assert calls == []
    assert denied.receipt.status == "quarantined"

    allowed = PdfExtractor(ocr=ocr).extract(
        source,
        _policy(allow_remote=True, authorized_extractors=("ocr",)),
        {},
    )
    assert calls == ["scan.pdf"]
    assert allowed.document is None
    assert allowed.receipt.quarantine_reason == "low_confidence"


def test_ocr_rejects_non_finite_confidence_instead_of_promoting_invalid_ir(tmp_path: Path) -> None:
    source = tmp_path / "scan.pdf"
    _blank_pdf(source)

    def ocr(_path: Path, _policy: ExtractorPolicy):
        return [{"page": 1, "text": "OCR text", "confidence": math.nan}]

    result = PdfExtractor(ocr=ocr).extract(
        source,
        _policy(allow_remote=True, authorized_extractors=("ocr",)),
        {},
    )

    assert result.document is None
    assert result.receipt.status == "failed"
    assert result.receipt.errors[0]["code"] == "ocr_output_invalid"


def test_ocr_rejects_non_positive_page_locators(tmp_path: Path) -> None:
    source = tmp_path / "scan.pdf"
    _blank_pdf(source)

    def ocr(_path: Path, _policy: ExtractorPolicy):
        return [{"page": 0, "text": "OCR text", "confidence": 0.9}]

    result = PdfExtractor(ocr=ocr).extract(
        source,
        _policy(allow_remote=True, authorized_extractors=("ocr",)),
        {},
    )

    assert result.document is None
    assert result.receipt.status == "failed"
    assert result.receipt.errors[0]["code"] == "ocr_output_invalid"


def test_docling_ocr_adapter_converts_structured_items_to_page_bbox_records(monkeypatch, tmp_path: Path) -> None:
    Bbox = type("Bbox", (), {"l": 10.0, "t": 90.0, "r": 80.0, "b": 20.0})

    class Provenance:
        page_no = 2
        bbox = Bbox()

    class Item:
        text = "OCR text"
        prov = [Provenance()]

    class Confidence:
        ocr_score = 0.93

    class Document:
        @staticmethod
        def iterate_items():
            return iter([(Item(), 1)])

    class Result:
        document = Document()
        confidence = Confidence()

    class Converter:
        @staticmethod
        def convert(_path):
            return Result()

    monkeypatch.setattr(DoclingOcrAdapter, "_converter", lambda self: Converter())

    records = DoclingOcrAdapter()(tmp_path / "scan.pdf", _policy())

    assert records == [
        {
            "page": 2,
            "text": "OCR text",
            "confidence": 0.93,
            "bbox": [10.0, 20.0, 80.0, 90.0],
        }
    ]


# -- Farol 3.1 TK-212: digital PDFs with layout and tables (extra `layout`) ----


def _layout_pdf(tmp_path: Path) -> Path:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    path = tmp_path / "handbook.pdf"
    with path.open("wb") as handle:
        writer.write(handle)
    return path


def test_layout_converter_emits_headings_tables_and_pages(tmp_path: Path, monkeypatch) -> None:
    from fixtures_31 import FakeLayoutConverter

    from docops import normalizer

    monkeypatch.setenv("FAROL_PDF_LAYOUT", "1")
    monkeypatch.setattr(normalizer, "_layout_converter", lambda: FakeLayoutConverter())

    markdown = normalizer._extract_pdf(_layout_pdf(tmp_path))

    assert "## Page 2" in markdown and "### Defaults by client" in markdown
    assert "| urllib3 | 3 | 0.5 s |" in markdown and "\\| urllib3" not in markdown
    assert "Retry Handbook — draft" not in markdown
    assert "- Extraction: layout (docling)" in markdown


def test_without_the_layout_extra_pdf_stays_text_fallback_and_says_so(tmp_path: Path, monkeypatch) -> None:
    from docops import normalizer

    def missing() -> object:
        raise ImportError("docling")

    monkeypatch.setenv("FAROL_PDF_LAYOUT", "1")
    monkeypatch.setattr(normalizer, "_layout_converter", missing)
    pdf = _layout_pdf(tmp_path)

    assert normalizer._extract_pdf(pdf) == normalizer._extract_pdf_text(pdf)
    from docops.doctor import run_doctor

    report = run_doctor(tmp_path, environ={})
    assert report.checks["extras"]["layout"] in {True, False}


def test_table_blocks_are_indexed_and_cited_by_page(tmp_path: Path, monkeypatch) -> None:
    from fixtures_31 import FakeLayoutConverter

    import docops
    from docops import normalizer
    from docops.mcp_server import KnowledgeServer
    from docops.package_index import build_package_index

    monkeypatch.setenv("FAROL_PDF_LAYOUT", "1")
    monkeypatch.setattr(normalizer, "_layout_converter", lambda: FakeLayoutConverter())
    source = tmp_path / "source"
    source.mkdir()
    _layout_pdf(source)
    package = tmp_path / "package"
    assert docops.apply(
        docops.plan(
            docops.OperationRequest(
                source,
                docops.OperationOptions(output_dir=package, source_root=source.parent, slug="hb", license="MIT"),
            )
        )
    ).ok
    build_package_index(package, embedder=None)

    top = KnowledgeServer(package).search_knowledge("urllib3 attempts backoff", top_k=1)["hits"][0]

    assert "| urllib3 | 3 | 0.5 s |" in top["text"]
    assert "(page 2)" in top["citation"] or "page=2" in top["citation"]
