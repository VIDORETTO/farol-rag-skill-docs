"""Controlled text adapter used until high-fidelity format adapters land."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Mapping

from ..api_types import CapabilityV2
from ..ir import ExtractionReceipt, IRBlock, IRDocument
from ..normalizer import normalize_file
from ..revisions import content_hash
from .base import ExtractionResult, ExtractorError, ExtractorPolicy


class LegacyTextExtractor:
    """Wrap the 1.x normalizer with an explicit v2 fidelity receipt."""

    def __init__(self, *, name: str = "legacy-text", version: str = "1.0", execution: str = "local") -> None:
        self.name = name
        self.version = version
        self.execution = execution

    def describe(self) -> CapabilityV2:
        return CapabilityV2(
            name=self.name,
            version=self.version,
            status="available" if self.execution == "local" else "disabled",
            supports=["text/plain", "text/markdown", "text/html", ".md", ".markdown", ".txt", ".html", ".htm"],
            fidelity=["text-fallback"],
            execution=self.execution,
            permissions=["read-private-staging"],
            dependencies=[],
        )

    def extract(
        self,
        artifact: Path | str | Mapping[str, Any],
        policy: ExtractorPolicy,
        budget: Mapping[str, Any],
    ) -> ExtractionResult:
        path, metadata = _artifact_path(artifact)
        if not path.is_file() or path.is_symlink():
            raise ExtractorError("artifact_unavailable", "artifact must be a regular file")
        maximum = int(budget.get("max_bytes", policy.max_bytes))
        if path.stat().st_size > maximum:
            raise ExtractorError("budget_exceeded", "artifact exceeds extractor byte budget")
        if not policy.rights_ref:
            raise ExtractorError("rights_required", "rights_ref is required before extraction")
        normalized = normalize_file(path, source_url=metadata.get("canonical"), max_bytes=maximum)
        input_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        status = (
            "extracted" if normalized.status == "accepted" and normalized.quality_status == "accepted" else "degraded"
        )
        fidelity = "text-fallback"
        if normalized.status != "accepted":
            status = "quarantined" if normalized.status == "ocr_required" else "failed"
        if normalized.quality_status == "quarantine":
            status = "quarantined"
        extractor = {"name": self.name, "version": self.version, "execution": self.execution}
        receipt = ExtractionReceipt(
            artifact_id=str(metadata.get("artifact_id") or path.name),
            source_id=policy.source_id,
            source_revision_id=policy.source_revision_id,
            extractor=extractor,
            fidelity=fidelity,
            status=status,
            input_hash=input_hash,
            warnings=list(normalized.warnings),
            errors=[
                {"code": normalized.error_code or normalized.status, "message": normalized.error or normalized.status}
            ]
            if normalized.status != "accepted"
            else [],
            quarantine_reason=normalized.quality_reason if status == "quarantined" else None,
        )
        if status not in {"extracted", "degraded"}:
            return ExtractionResult(None, receipt, {"code": receipt.errors[0]["code"] if receipt.errors else status})
        blocks = _blocks_from_text(normalized.content, normalized.locators, policy.source_id)
        if len(blocks) > int(budget.get("max_blocks", policy.max_blocks)):
            raise ExtractorError("budget_exceeded", "extracted block count exceeds budget")
        document = IRDocument(
            document_id=str(metadata.get("document_id") or f"ir-{input_hash[:24]}"),
            source_id=policy.source_id,
            source_revision_id=policy.source_revision_id,
            artifact_id=receipt.artifact_id,
            content_hash=input_hash,
            media_type=str(metadata.get("media_type") or _media_type(path)),
            language=str(metadata.get("language") or "und"),
            extractor=extractor,
            fidelity={"level": fidelity, "capabilities": ["text", "locators"], "degradations": ["layout"]},
            rights_ref=policy.rights_ref,
            captured_at=str(metadata.get("captured_at") or "1970-01-01T00:00:00Z"),
            effective_at=metadata.get("effective_at") if isinstance(metadata.get("effective_at"), str) else None,
            region=metadata.get("region") if isinstance(metadata.get("region"), str) else None,
            blocks=blocks,
            origin=normalized.origin,
        )
        receipt = ExtractionReceipt(**{**receipt.__dict__, "ir_revision": document.revision_hash()})
        return ExtractionResult(document, receipt)


def _artifact_path(artifact: Path | str | Mapping[str, Any]) -> tuple[Path, dict[str, Any]]:
    if isinstance(artifact, Mapping):
        raw = artifact.get("path") or artifact.get("local_path")
        if not isinstance(raw, str):
            raise ExtractorError("artifact_invalid", "artifact path is required")
        return Path(raw).expanduser().resolve(), dict(artifact)
    path = Path(artifact).expanduser().resolve()
    return path, {}


def _media_type(path: Path) -> str:
    return {
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".html": "text/html",
        ".htm": "text/html",
        ".txt": "text/plain",
    }.get(path.suffix.casefold(), "application/octet-stream")


def _blocks_from_text(content: str, locators: list[dict[str, Any]], source_id: str) -> list[IRBlock]:
    blocks: list[IRBlock] = []
    heading_path: list[str] = []
    for ordinal, line in enumerate(content.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", stripped)
        if heading:
            level = len(heading.group(1))
            heading_path = heading_path[: level - 1] + [heading.group(2).strip()]
            kind = "heading"
        elif re.match(r"^(?:[-*+] |\d+[.)] )", stripped):
            kind = "list"
        elif stripped.startswith("```"):
            kind = "code"
        else:
            kind = "paragraph"
        line_number = ordinal + 1
        matching = [dict(item) for item in locators if item.get("line_start") == line_number]
        for locator in matching:
            if locator.get("kind") == "normalized_section":
                locator["kind"] = "section"
                locator["label"] = str(locator.get("label") or "normalized-content")
        if not matching:
            matching = [{"kind": "line", "label": str(line_number), "line": line_number, "available": True}]
        block_id = hashlib.sha256(f"{source_id}:{line_number}:{stripped}".encode("utf-8")).hexdigest()[:24]
        blocks.append(
            IRBlock(
                block_id=block_id,
                parent_id=None,
                ordinal=len(blocks),
                kind=kind,
                text=stripped,
                heading_path=list(heading_path),
                locators=matching,
                source_fragment_hash=content_hash({"source": source_id, "line": line_number, "text": stripped}),
            )
        )
    return blocks
