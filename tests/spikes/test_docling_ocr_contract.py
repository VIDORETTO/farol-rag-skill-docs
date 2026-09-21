# seam-scope: implementation-infrastructure (external OCR contract spike)
"""Opt-in real OCR contract for the pinned local Docling adapter."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import pytest

from docops.extractors import ExtractorPolicy
from docops.extractors.pdf import DoclingOcrAdapter, PdfExtractor

pytestmark = pytest.mark.integration


def _scanned_pdf(path: Path) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore[import-not-found]
    except ImportError:
        pytest.skip("not_run: Pillow is unavailable in the OCR integration environment")
    markers = ("FAROL OCR PAGE ONE", "FAROL OCR PAGE TWO")
    pages = []
    for marker in markers:
        image = Image.new("RGB", (1800, 1000), "white")
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default(size=72)
        draw.text((100, 380), marker, fill="black", font=font)
        pages.append(image)
    pages[0].save(path, "PDF", save_all=True, append_images=pages[1:], resolution=150.0)


def test_docling_ocr_real_scanned_pdf_preserves_text_pages_bbox_and_confidence(tmp_path: Path) -> None:
    if os.environ.get("DOCOPS_OCR_INTEGRATION") != "1":
        pytest.skip("not_run: Docling OCR integration is opt-in")
    source = tmp_path / "scan.pdf"
    _scanned_pdf(source)
    result = PdfExtractor(ocr=DoclingOcrAdapter()).extract(
        source,
        ExtractorPolicy(
            rights_ref="rights-synthetic-ocr",
            source_id="source-synthetic-ocr",
            source_revision_id="source-revision-synthetic-ocr",
            required_fidelity="external-converter",
            allow_remote=False,
            authorized_extractors=("docling-ocr",),
            ocr_confidence_threshold=0.8,
        ),
        {"max_bytes": 5_000_000, "max_blocks": 100},
    )

    assert result.document is not None, result.to_dict()
    assert result.receipt.status == "extracted"
    assert result.receipt.fidelity == "external-converter"
    assert result.document.extractor["execution"] == "local"
    text_by_page: dict[int, str] = {}
    for block in result.document.blocks:
        locator = block.locators[0]
        page = int(locator["page"])
        text_by_page[page] = text_by_page.get(page, "") + " " + str(block.text or "")
        bbox = locator.get("bbox")
        assert isinstance(bbox, list) and len(bbox) == 4
        assert all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in bbox)
        assert block.confidence is not None and block.confidence >= 0.8
        assert "ocr" in block.quality_flags
    assert "FAROL OCR PAGE ONE" in text_by_page[1].upper()
    assert "FAROL OCR PAGE TWO" in text_by_page[2].upper()
    receipt = {
        "schema_version": 1,
        "status": "passed",
        "adapter": {"name": DoclingOcrAdapter.name, "version": DoclingOcrAdapter.version, "execution": "local"},
        "pages": sorted(text_by_page),
        "blocks": len(result.document.blocks),
        "bbox": "passed",
        "confidence": "passed",
    }
    serialized = json.dumps(receipt, sort_keys=True)
    assert str(tmp_path) not in serialized
    assert "FAROL OCR PAGE" not in serialized
    print(f"OCR_RECEIPT {serialized}")
