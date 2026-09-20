"""PDF text/page extraction and explicitly authorized OCR handoff."""

from __future__ import annotations

import hashlib
import importlib.metadata
import math
from pathlib import Path
from typing import Any, Callable, Mapping

from ..api_types import CapabilityV2
from ..ir import ExtractionReceipt, IRBlock, IRDocument
from ..revisions import content_hash
from .base import ExtractionResult, ExtractorError, ExtractorPolicy


class DoclingOcrAdapter:
    """Local, optional Docling/RapidOCR bridge for scanned PDF blocks."""

    name = "docling-ocr"
    version = "2.129.0"
    execution = "local"

    def _converter(self) -> Any:
        try:
            from docling.datamodel.base_models import InputFormat  # type: ignore[import-not-found]
            from docling.datamodel.pipeline_options import (  # type: ignore[import-not-found]
                OcrMode,
                PdfPipelineOptions,
                RapidOcrOptions,
            )
            from docling.document_converter import (  # type: ignore[import-not-found]
                DocumentConverter,
                PdfFormatOption,
            )
        except ImportError as exc:
            raise ExtractorError(
                "dependency_missing",
                "docling and onnxruntime are required for local PDF OCR",
            ) from exc
        try:
            installed = importlib.metadata.version("docling")
        except importlib.metadata.PackageNotFoundError as exc:
            raise ExtractorError("dependency_missing", "docling is required for local PDF OCR") from exc
        if installed != self.version:
            raise ExtractorError(
                "dependency_version_mismatch",
                f"local PDF OCR requires docling {self.version}",
            )
        options = PdfPipelineOptions(do_ocr=True, do_table_structure=False)
        options.ocr_options = RapidOcrOptions(mode=OcrMode.FULL_PAGE)
        return DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})

    def __call__(self, path: Path, _policy: ExtractorPolicy) -> list[Mapping[str, Any]]:
        try:
            result = self._converter().convert(path)
        except ExtractorError:
            raise
        except Exception as exc:
            raise ExtractorError("ocr_failed", "Docling OCR failed to convert the PDF") from exc
        confidence = _docling_confidence(result)
        records: list[dict[str, Any]] = []
        for item, _level in result.document.iterate_items():
            text = str(getattr(item, "text", "") or "").strip()
            if not text:
                continue
            for item_provenance in list(getattr(item, "prov", []) or []):
                bbox = getattr(item_provenance, "bbox", None)
                record: dict[str, Any] = {
                    "page": getattr(item_provenance, "page_no", None),
                    "text": text,
                    "confidence": confidence,
                }
                if bbox is not None:
                    record["bbox"] = [
                        float(getattr(bbox, "l")),
                        float(getattr(bbox, "b")),
                        float(getattr(bbox, "r")),
                        float(getattr(bbox, "t")),
                    ]
                records.append(record)
        return records


class PdfExtractor:
    name = "pdf"
    version = "2.0"

    def __init__(self, *, ocr: Callable[[Path, ExtractorPolicy], list[Mapping[str, Any]]] | None = None) -> None:
        self.ocr = ocr

    def describe(self) -> CapabilityV2:
        return CapabilityV2(
            name=self.name,
            version=self.version,
            status="available",
            supports=["application/pdf", ".pdf"],
            fidelity=["structured-native", "external-converter", "metadata-only"],
            execution="local",
            permissions=["read-private-staging", "ocr-opt-in"],
            dependencies=[
                {"name": "pypdf", "optional": True},
                {"name": "docling", "version": DoclingOcrAdapter.version, "optional": True},
            ],
        )

    def extract(
        self,
        artifact: Path | str | Mapping[str, Any],
        policy: ExtractorPolicy,
        budget: Mapping[str, Any],
    ) -> ExtractionResult:
        if not policy.rights_ref:
            raise ExtractorError("rights_required", "rights_ref is required before extraction")
        path, metadata = _artifact_path(artifact)
        if not path.is_file() or path.is_symlink():
            raise ExtractorError("artifact_unavailable", "artifact must be a regular file")
        raw = path.read_bytes()
        if len(raw) > int(budget.get("max_bytes", policy.max_bytes)):
            raise ExtractorError("budget_exceeded", "PDF exceeds extractor byte budget")
        input_hash = hashlib.sha256(raw).hexdigest()
        try:
            pages = _extract_pages(path)
        except ExtractorError as exc:
            return _failed_result(path, policy, input_hash, exc.code, exc.code)
        if not pages:
            ocr_name = str(getattr(self.ocr, "name", "ocr"))
            ocr_execution = str(getattr(self.ocr, "execution", "remote"))
            authorized = bool({"ocr", ocr_name}.intersection(policy.authorized_extractors))
            if not authorized or (ocr_execution != "local" and not policy.allow_remote):
                return _failed_result(path, policy, input_hash, "ocr_required", "ocr_required")
            if self.ocr is None:
                return _failed_result(path, policy, input_hash, "ocr_adapter_missing", "dependency_missing")
            try:
                pages = _normalize_ocr_pages(self.ocr(path, policy))
            except ExtractorError as exc:
                return _failed_result(path, policy, input_hash, exc.code, exc.code)
            except (TypeError, ValueError):
                return _failed_result(path, policy, input_hash, "ocr_output_invalid", "ocr_output_invalid")
            if not pages:
                return _failed_result(path, policy, input_hash, "ocr_empty", "ocr_empty")
            confidence = min(float(page["confidence"]) for page in pages)
            if confidence < policy.ocr_confidence_threshold:
                return _failed_result(path, policy, input_hash, "low_confidence", "low_confidence")
            fidelity = "external-converter"
            execution = ocr_execution
        else:
            fidelity = "structured-native"
            execution = "local"
        blocks: list[IRBlock] = []
        for ordinal, page in enumerate(pages):
            page_number = int(page.get("page", ordinal + 1))
            text = str(page.get("text") or "").strip()
            if not text:
                continue
            confidence = page.get("confidence")
            blocks.append(
                IRBlock(
                    block_id=hashlib.sha256(f"{input_hash}:{page_number}:{text}".encode("utf-8")).hexdigest()[:24],
                    parent_id=None,
                    ordinal=len(blocks),
                    kind="paragraph",
                    text=text,
                    heading_path=[f"Page {page_number}"],
                    locators=[
                        {
                            "kind": "page",
                            "label": f"Page {page_number}",
                            "page": page_number,
                            "bbox": page.get("bbox"),
                            "available": True,
                        }
                    ],
                    confidence=float(confidence) if isinstance(confidence, (int, float)) else None,
                    quality_flags=["ocr"],
                    source_fragment_hash=content_hash({"page": page_number, "text": text}),
                )
            )
        if not blocks:
            return _failed_result(path, policy, input_hash, "empty_document", "empty_document")
        if len(blocks) > int(budget.get("max_blocks", policy.max_blocks)):
            raise ExtractorError("budget_exceeded", "extracted block count exceeds budget")
        document = IRDocument(
            document_id=str(metadata.get("document_id") or f"ir-{input_hash[:24]}"),
            source_id=policy.source_id,
            source_revision_id=policy.source_revision_id,
            artifact_id=str(metadata.get("artifact_id") or path.name),
            content_hash=input_hash,
            media_type="application/pdf",
            language=str(metadata.get("language") or "und"),
            extractor={"name": self.name, "version": self.version, "execution": execution},
            fidelity={"level": fidelity, "capabilities": ["page", "text"], "degradations": []},
            rights_ref=policy.rights_ref,
            captured_at=str(metadata.get("captured_at") or "1970-01-01T00:00:00Z"),
            effective_at=None,
            region=None,
            blocks=blocks,
            origin=str(metadata.get("canonical") or path.resolve().as_uri()),
        )
        receipt = ExtractionReceipt(
            artifact_id=document.artifact_id,
            source_id=policy.source_id,
            source_revision_id=policy.source_revision_id,
            extractor=document.extractor,
            fidelity=fidelity,
            status="extracted",
            input_hash=input_hash,
            ir_revision=document.revision_hash(),
        )
        return ExtractionResult(document, receipt)


def _artifact_path(artifact: Path | str | Mapping[str, Any]) -> tuple[Path, dict[str, Any]]:
    if isinstance(artifact, Mapping):
        raw = artifact.get("path") or artifact.get("local_path")
        if not isinstance(raw, str):
            raise ExtractorError("artifact_invalid", "artifact path is required")
        return Path(raw).expanduser().resolve(), dict(artifact)
    return Path(artifact).expanduser().resolve(), {}


def _extract_pages(path: Path) -> list[dict[str, Any]]:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ImportError:
        raise ExtractorError("dependency_missing", "pypdf is required for local PDF extraction")

    try:
        header = path.read_bytes()[:5]
    except OSError as exc:
        raise ExtractorError("read_failed", "PDF could not be read") from exc
    if header != b"%PDF-":
        raise ExtractorError("malformed", "PDF header is missing or invalid")

    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            raise ExtractorError("encrypted", "encrypted PDFs require an authorized decrypting adapter")
        pages = []
        for index, page in enumerate(reader.pages, 1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append({"page": index, "text": text})
        return pages
    except ExtractorError:
        raise
    except Exception as exc:
        raise ExtractorError("malformed", "PDF structure could not be parsed") from exc


def _normalize_ocr_pages(raw_pages: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_pages, list):
        raise ExtractorError("ocr_output_invalid", "OCR output must be a page list")
    pages: list[dict[str, Any]] = []
    for raw_page in raw_pages:
        if not isinstance(raw_page, Mapping):
            raise ExtractorError("ocr_output_invalid", "OCR page must be an object")
        page = dict(raw_page)
        raw_page_number = page.get("page", len(pages) + 1)
        if isinstance(raw_page_number, bool):
            raise ExtractorError("ocr_output_invalid", "OCR page number must be a positive integer")
        if isinstance(raw_page_number, float) and not raw_page_number.is_integer():
            raise ExtractorError("ocr_output_invalid", "OCR page number must be a positive integer")
        if isinstance(raw_page_number, str) and not raw_page_number.strip().isdigit():
            raise ExtractorError("ocr_output_invalid", "OCR page number must be a positive integer")
        try:
            page_number = int(raw_page_number)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ExtractorError("ocr_output_invalid", "OCR page number must be a positive integer") from exc
        if page_number < 1:
            raise ExtractorError("ocr_output_invalid", "OCR page numbers must be positive")
        confidence = float(page.get("confidence", 0.0))
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise ExtractorError("ocr_output_invalid", "OCR confidence must be finite and between zero and one")
        page["page"] = page_number
        page["confidence"] = confidence
        pages.append(page)
    return pages


def _docling_confidence(result: Any) -> float:
    confidence = getattr(result, "confidence", None)
    for name in ("ocr_score", "mean_score", "low_score"):
        value = getattr(confidence, name, None)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
            numeric = float(value)
            if 0.0 <= numeric <= 1.0:
                return numeric
    raise ExtractorError("ocr_output_invalid", "Docling OCR did not expose a finite confidence score")


def _failed_result(
    path: Path, policy: ExtractorPolicy, input_hash: str, code: str, quarantine_reason: str
) -> ExtractionResult:
    status = "quarantined" if quarantine_reason in {"ocr_required", "low_confidence"} else "failed"
    receipt = ExtractionReceipt(
        artifact_id=path.name,
        source_id=policy.source_id,
        source_revision_id=policy.source_revision_id,
        extractor={"name": "pdf", "version": "2.0", "execution": "local"},
        fidelity="metadata-only",
        status=status,
        input_hash=input_hash,
        errors=[{"code": code, "message": code}],
        quarantine_reason=quarantine_reason if status == "quarantined" else None,
    )
    return ExtractionResult(None, receipt, {"code": code})
