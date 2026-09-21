"""Safe DOCX and EPUB extraction into the canonical IR."""

from __future__ import annotations

import hashlib
import posixpath
import zipfile
from pathlib import Path
from typing import Any, Mapping
from xml.etree import ElementTree

from ..api_types import CapabilityV2
from ..ir import ExtractionReceipt, IRBlock, IRDocument
from ..revisions import content_hash
from .base import ExtractionResult, ExtractorError, ExtractorPolicy
from .text_web import _HTMLStructureParser


class OfficeEbookExtractor:
    name = "office-ebook"
    version = "2.0"

    def describe(self) -> CapabilityV2:
        return CapabilityV2(
            name=self.name,
            version=self.version,
            status="available",
            supports=[
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/epub+zip",
                ".docx",
                ".epub",
            ],
            fidelity=["structured-native", "metadata-only"],
            execution="local",
            permissions=["read-private-staging", "archive-safe"],
            dependencies=[{"name": "python-docx", "optional": True}],
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
        input_hash = hashlib.sha256(raw).hexdigest()
        try:
            _check_archive(path, budget or policy.to_dict())
            suffix = path.suffix.casefold()
            if suffix == ".docx":
                blocks = _docx_blocks(path, input_hash)
                media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            elif suffix == ".epub":
                blocks = _epub_blocks(path, input_hash)
                media_type = "application/epub+zip"
            else:
                raise ExtractorError("unsupported", "office-ebook extractor only accepts DOCX and EPUB")
        except ExtractorError as exc:
            return _failed_result(path, policy, input_hash, exc.code, str(exc))
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
            media_type=media_type,
            language=str(metadata.get("language") or "und"),
            extractor={"name": self.name, "version": self.version, "execution": "local"},
            fidelity={
                "level": "structured-native",
                "capabilities": ["order", "headings", "tables", "chapters"],
                "degradations": [],
            },
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
            fidelity="structured-native",
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


def _check_archive(path: Path, budget: Mapping[str, Any]) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            max_files = int(budget.get("max_archive_files", 10_000))
            max_uncompressed = int(budget.get("max_archive_bytes", 100 * 1024 * 1024))
            if len(infos) > max_files:
                raise ExtractorError("archive_limit", "archive contains too many members")
            total = 0
            for info in infos:
                name = info.filename.replace("\\", "/")
                if name.startswith("/") or any(part in {"", ".", ".."} for part in name.split("/")):
                    raise ExtractorError("invalid_archive", "archive member path is unsafe")
                mode = (info.external_attr >> 16) & 0o170000
                if mode == 0o120000:
                    raise ExtractorError("invalid_archive", "archive symbolic links are not accepted")
                total += int(info.file_size)
            if total > max_uncompressed:
                raise ExtractorError("archive_limit", "archive expands beyond the byte budget")
    except zipfile.BadZipFile as exc:
        raise ExtractorError("invalid_archive", "archive is not a valid ZIP") from exc


def _docx_blocks(path: Path, input_hash: str) -> list[IRBlock]:
    try:
        from docx import Document  # type: ignore[import-not-found]
        from docx.table import Table  # type: ignore[import-not-found]
        from docx.text.paragraph import Paragraph  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ExtractorError("dependency_missing", "python-docx is required for DOCX extraction") from exc
    document = Document(str(path))
    blocks: list[IRBlock] = []
    for ordinal, child in enumerate(document.element.body.iterchildren()):
        if child.tag.endswith("}p"):
            paragraph = Paragraph(child, document)
            text = paragraph.text.strip()
            if not text:
                continue
            style = str(paragraph.style.name or "")
            kind = "heading" if style.casefold().startswith("heading") else "paragraph"
            heading_path = [text] if kind == "heading" else []
            locator = {"kind": "section" if kind == "heading" else "line", "label": text, "line": len(blocks) + 1}
            blocks.append(_block(input_hash, len(blocks), kind, text, heading_path, [locator]))
        elif child.tag.endswith("}tbl"):
            table = Table(child, document)
            rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
            if rows:
                blocks.append(
                    _block(
                        input_hash,
                        len(blocks),
                        "table",
                        "\n".join(" | ".join(row) for row in rows),
                        [],
                        [{"kind": "cell", "label": f"table-{len(blocks) + 1}", "cell": "*"}],
                        {"rows": rows},
                    )
                )
    return blocks


def _epub_blocks(path: Path, input_hash: str) -> list[IRBlock]:
    with zipfile.ZipFile(path) as archive:
        container = ElementTree.fromstring(archive.read("META-INF/container.xml"))
        rootfile = next(
            (node.attrib.get("full-path") for node in container.iter() if node.tag.endswith("rootfile")), None
        )
        if not rootfile:
            raise ExtractorError("invalid_archive", "EPUB has no OPF rootfile")
        opf = ElementTree.fromstring(archive.read(rootfile))
        base = posixpath.dirname(rootfile)
        manifest = {
            node.attrib.get("id"): node.attrib.get("href")
            for node in opf.iter()
            if node.tag.endswith("item") and node.attrib.get("id") and node.attrib.get("href")
        }
        ids = [node.attrib.get("idref") for node in opf.iter() if node.tag.endswith("itemref")]
        blocks: list[IRBlock] = []
        for chapter, identifier in enumerate(ids, 1):
            href = manifest.get(identifier)
            if not href:
                continue
            member = posixpath.normpath(posixpath.join(base, href))
            if member.startswith("../") or member.startswith("/"):
                raise ExtractorError("invalid_archive", "EPUB spine escapes the archive root")
            parser = _HTMLStructureParser(f"epub://{member}")
            parser.feed(archive.read(member).decode("utf-8"))
            parser.close()
            for value in parser.blocks:
                text = str(value.get("text") or "").strip()
                if not text:
                    continue
                heading_path = [f"Chapter {chapter}", *[str(item) for item in value.get("heading_path", [])]]
                locator = {"kind": "section", "label": text, "chapter": chapter, "origin": member}
                blocks.append(
                    _block(
                        input_hash,
                        len(blocks),
                        str(value.get("kind") or "paragraph"),
                        text,
                        heading_path,
                        [locator],
                        value.get("structured"),
                    )
                )
        return blocks


def _block(
    input_hash: str,
    ordinal: int,
    kind: str,
    text: str,
    heading_path: list[str],
    locators: list[dict[str, Any]],
    structured: Mapping[str, Any] | None = None,
) -> IRBlock:
    return IRBlock(
        block_id=hashlib.sha256(f"{input_hash}:{ordinal}:{text}".encode("utf-8")).hexdigest()[:24],
        parent_id=None,
        ordinal=ordinal,
        kind=kind if kind in {"heading", "paragraph", "table", "list", "code", "quote", "caption"} else "paragraph",
        text=text,
        structured=dict(structured) if isinstance(structured, Mapping) else None,
        heading_path=heading_path,
        locators=locators,
        source_fragment_hash=content_hash({"ordinal": ordinal, "text": text}),
    )


def _failed_result(path: Path, policy: ExtractorPolicy, input_hash: str, code: str, reason: str) -> ExtractionResult:
    receipt = ExtractionReceipt(
        artifact_id=path.name,
        source_id=policy.source_id,
        source_revision_id=policy.source_revision_id,
        extractor={"name": "office-ebook", "version": "2.0", "execution": "local"},
        fidelity="metadata-only",
        status="failed",
        input_hash=input_hash,
        errors=[{"code": code, "message": reason}],
    )
    return ExtractionResult(None, receipt, {"code": code})
