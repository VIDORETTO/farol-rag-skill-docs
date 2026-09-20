"""IR value objects, validators and an atomic revision store."""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from ..revisions import content_hash
from ..storage import write_json_atomic

IR_SCHEMA_VERSION = 2
FIDELITY_LEVELS = (
    "structured-native",
    "text-fallback",
    "external-converter",
    "metadata-only",
    "unsupported",
)
BLOCK_KINDS = (
    "title",
    "heading",
    "paragraph",
    "list",
    "table",
    "table_row",
    "code",
    "quote",
    "figure",
    "caption",
    "equation",
    "metadata",
)
LOCATOR_KINDS = ("section", "line", "page", "bbox", "slide", "sheet", "cell", "timestamp", "symbol")


class IRValidationError(ValueError):
    """Typed invalid IR that must never be promoted from staging."""

    def __init__(self, code: str, message: str, *, errors: list[dict[str, Any]] | None = None) -> None:
        self.code = code
        self.errors = list(errors or [{"code": code, "message": message}])
        super().__init__(message)


@dataclass(frozen=True)
class ValidationReport:
    ok: bool
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "errors": self.errors, "warnings": self.warnings}


def _copy(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))


@dataclass(frozen=True)
class IRBlock:
    block_id: str
    parent_id: str | None
    ordinal: int
    kind: str
    text: str | None = None
    structured: Mapping[str, Any] | None = None
    heading_path: list[str] = field(default_factory=list)
    symbol: str | None = None
    locators: list[dict[str, Any]] = field(default_factory=list)
    language: str | None = None
    confidence: float | None = None
    quality_flags: list[str] = field(default_factory=list)
    source_fragment_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _copy(
            {
                "schema_version": IR_SCHEMA_VERSION,
                "block_id": self.block_id,
                "parent_id": self.parent_id,
                "ordinal": self.ordinal,
                "kind": self.kind,
                "text": self.text,
                "structured": dict(self.structured) if self.structured is not None else None,
                "heading_path": self.heading_path,
                "symbol": self.symbol,
                "locators": self.locators,
                "language": self.language,
                "confidence": self.confidence,
                "quality_flags": self.quality_flags,
                "source_fragment_hash": self.source_fragment_hash,
            }
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "IRBlock":
        return cls(
            block_id=str(value.get("block_id", "")),
            parent_id=value.get("parent_id") if isinstance(value.get("parent_id"), str) else None,
            ordinal=int(value.get("ordinal", -1)),
            kind=str(value.get("kind", "")),
            text=value.get("text") if isinstance(value.get("text"), str) else None,
            structured=value.get("structured") if isinstance(value.get("structured"), Mapping) else None,
            heading_path=[str(item) for item in value.get("heading_path", []) if isinstance(item, str)],
            symbol=value.get("symbol") if isinstance(value.get("symbol"), str) else None,
            locators=[dict(item) for item in value.get("locators", []) if isinstance(item, Mapping)],
            language=value.get("language") if isinstance(value.get("language"), str) else None,
            confidence=value.get("confidence") if isinstance(value.get("confidence"), (int, float)) else None,
            quality_flags=[str(item) for item in value.get("quality_flags", []) if isinstance(item, str)],
            source_fragment_hash=value.get("source_fragment_hash")
            if isinstance(value.get("source_fragment_hash"), str)
            else None,
        )


@dataclass(frozen=True)
class IRDocument:
    document_id: str
    source_id: str
    source_revision_id: str
    artifact_id: str
    content_hash: str
    media_type: str
    language: str
    extractor: Mapping[str, Any]
    fidelity: Mapping[str, Any]
    rights_ref: str
    captured_at: str
    effective_at: str | None
    region: str | None
    blocks: list[IRBlock]
    assets: list[dict[str, Any]] = field(default_factory=list)
    origin: str | None = None
    revision_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": IR_SCHEMA_VERSION,
            "kind": "ir_document",
            "document_id": self.document_id,
            "source_id": self.source_id,
            "source_revision_id": self.source_revision_id,
            "artifact_id": self.artifact_id,
            "content_hash": self.content_hash,
            "media_type": self.media_type,
            "language": self.language,
            "extractor": dict(self.extractor),
            "fidelity": dict(self.fidelity),
            "rights_ref": self.rights_ref,
            "captured_at": self.captured_at,
            "effective_at": self.effective_at,
            "region": self.region,
            "blocks": [block.to_dict() for block in self.blocks],
            "assets": self.assets,
            "origin": self.origin,
        }
        if self.revision_id is not None:
            payload["revision_id"] = self.revision_id
        return _copy(payload)

    def revision_hash(self) -> str:
        payload = self.to_dict()
        payload.pop("revision_id", None)
        payload.pop("content_hash", None)
        return content_hash(payload)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "IRDocument":
        return cls(
            document_id=str(value.get("document_id", "")),
            source_id=str(value.get("source_id", "")),
            source_revision_id=str(value.get("source_revision_id", "")),
            artifact_id=str(value.get("artifact_id", "")),
            content_hash=str(value.get("content_hash", "")),
            media_type=str(value.get("media_type", "")),
            language=str(value.get("language", "")),
            extractor=dict(value.get("extractor", {})) if isinstance(value.get("extractor"), Mapping) else {},
            fidelity=dict(value.get("fidelity", {})) if isinstance(value.get("fidelity"), Mapping) else {},
            rights_ref=str(value.get("rights_ref", "")),
            captured_at=str(value.get("captured_at", "")),
            effective_at=value.get("effective_at") if isinstance(value.get("effective_at"), str) else None,
            region=value.get("region") if isinstance(value.get("region"), str) else None,
            blocks=[IRBlock.from_dict(item) for item in value.get("blocks", []) if isinstance(item, Mapping)],
            assets=[dict(item) for item in value.get("assets", []) if isinstance(item, Mapping)],
            origin=value.get("origin") if isinstance(value.get("origin"), str) else None,
            revision_id=value.get("revision_id") if isinstance(value.get("revision_id"), str) else None,
        )


@dataclass(frozen=True)
class ExtractionReceipt:
    artifact_id: str
    source_id: str
    source_revision_id: str
    extractor: Mapping[str, Any]
    fidelity: str
    status: str
    input_hash: str
    ir_revision: str | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    quarantine_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _copy(
            {
                "schema_version": IR_SCHEMA_VERSION,
                "kind": "extraction_receipt",
                "artifact_id": self.artifact_id,
                "source_id": self.source_id,
                "source_revision_id": self.source_revision_id,
                "extractor": dict(self.extractor),
                "fidelity": self.fidelity,
                "status": self.status,
                "input_hash": self.input_hash,
                "ir_revision": self.ir_revision,
                "warnings": self.warnings,
                "errors": self.errors,
                "quarantine_reason": self.quarantine_reason,
                "metadata": self.metadata,
            }
        )


@dataclass(frozen=True)
class BackendMapping:
    project_revision: str
    ir_revision: str
    backend: str
    backend_version: str
    dataset_id: str | None
    entries: list[dict[str, Any]]
    parser_fingerprint: str | None = None
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _copy(
            {
                "schema_version": IR_SCHEMA_VERSION,
                "kind": "backend_mapping",
                "project_revision": self.project_revision,
                "ir_revision": self.ir_revision,
                "backend": self.backend,
                "backend_version": self.backend_version,
                "dataset_id": self.dataset_id,
                "entries": self.entries,
                "parser_fingerprint": self.parser_fingerprint,
                "created_at": self.created_at,
            }
        )


def _error(errors: list[dict[str, Any]], code: str, message: str, path: str = "$") -> None:
    errors.append({"code": code, "path": path, "message": message})


def validate_ir_document(value: Mapping[str, Any] | IRDocument) -> ValidationReport:
    payload = value.to_dict() if isinstance(value, IRDocument) else dict(value)
    errors: list[dict[str, Any]] = []
    required = (
        "schema_version",
        "kind",
        "document_id",
        "source_id",
        "source_revision_id",
        "artifact_id",
        "content_hash",
        "media_type",
        "language",
        "extractor",
        "fidelity",
        "rights_ref",
        "captured_at",
        "blocks",
    )
    for key in required:
        if key not in payload:
            _error(errors, "required", f"missing field {key}", f"$.{key}")
    if payload.get("schema_version") != IR_SCHEMA_VERSION:
        _error(errors, "schema_version", "unsupported IR schema version", "$.schema_version")
    if payload.get("kind") != "ir_document":
        _error(errors, "kind", "IR document kind is invalid", "$.kind")
    for key in ("document_id", "source_id", "source_revision_id", "artifact_id", "rights_ref"):
        if key in payload and (not isinstance(payload[key], str) or not payload[key].strip()):
            _error(errors, "empty_identity", f"{key} must be a non-empty string", f"$.{key}")
    if not isinstance(payload.get("content_hash"), str) or not re.fullmatch(
        r"[0-9a-fA-F]{64}", str(payload.get("content_hash"))
    ):
        _error(errors, "hash_mismatch", "content_hash must be a SHA-256 hex identity", "$.content_hash")
    fidelity = payload.get("fidelity")
    if not isinstance(fidelity, Mapping) or fidelity.get("level") not in FIDELITY_LEVELS:
        _error(errors, "fidelity", "fidelity.level must be a declared fidelity level", "$.fidelity.level")
    blocks = payload.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        _error(errors, "blocks", "IR document must contain ordered blocks", "$.blocks")
        blocks = []
    ids: set[str] = set()
    ordinals: set[int] = set()
    for index, block in enumerate(blocks):
        path = f"$.blocks[{index}]"
        if not isinstance(block, Mapping):
            _error(errors, "block_type", "IR block must be an object", path)
            continue
        if block.get("schema_version") != IR_SCHEMA_VERSION:
            _error(errors, "schema_version", "IR block schema version is invalid", f"{path}.schema_version")
        block_id = block.get("block_id")
        if not isinstance(block_id, str) or not block_id:
            _error(errors, "block_id", "block_id is required", f"{path}.block_id")
        elif block_id in ids:
            _error(errors, "duplicate_block", "block_id must be unique", f"{path}.block_id")
        else:
            ids.add(block_id)
        ordinal = block.get("ordinal")
        if not isinstance(ordinal, int) or ordinal < 0:
            _error(errors, "ordinal", "ordinal must be a non-negative integer", f"{path}.ordinal")
        elif ordinal in ordinals:
            _error(errors, "duplicate_ordinal", "block ordinals must be unique", f"{path}.ordinal")
        else:
            ordinals.add(ordinal)
            if ordinal != index:
                _error(
                    errors,
                    "ordinal_sequence",
                    "block ordinals must be contiguous and match document order",
                    f"{path}.ordinal",
                )
        if block.get("kind") not in BLOCK_KINDS:
            _error(errors, "block_kind", "block kind is not supported", f"{path}.kind")
        fragment_hash = block.get("source_fragment_hash")
        if fragment_hash is not None and (
            not isinstance(fragment_hash, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", fragment_hash)
        ):
            _error(
                errors,
                "hash_mismatch",
                "source_fragment_hash must be a SHA-256 hex identity",
                f"{path}.source_fragment_hash",
            )
        confidence = block.get("confidence")
        if confidence is not None and (
            not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or not math.isfinite(float(confidence))
            or not 0.0 <= float(confidence) <= 1.0
        ):
            _error(errors, "confidence", "confidence must be finite and between zero and one", f"{path}.confidence")
        if block.get("text") is None and not isinstance(block.get("structured"), Mapping):
            _error(errors, "block_content", "block needs text or structured content", path)
        locators = block.get("locators")
        if not isinstance(locators, list) or not locators:
            _error(errors, "locator_missing", "every block needs a locator", f"{path}.locators")
        else:
            for locator_index, locator in enumerate(locators):
                locator_path = f"{path}.locators[{locator_index}]"
                if not isinstance(locator, Mapping) or locator.get("kind") not in LOCATOR_KINDS:
                    _error(errors, "locator_invalid", "locator kind is not supported", locator_path)
                elif not isinstance(locator.get("label"), str) or not locator["label"].strip():
                    _error(errors, "locator_label", "locator label is required", f"{locator_path}.label")
                else:
                    _validate_locator_range(locator, locator_path, errors)
        parent = block.get("parent_id")
        if parent is not None and (not isinstance(parent, str) or not parent):
            _error(errors, "parent_invalid", "parent_id must be null or a block id", f"{path}.parent_id")
    for index, block in enumerate(blocks):
        if isinstance(block, Mapping) and block.get("parent_id") and block.get("parent_id") not in ids:
            _error(
                errors, "dangling_parent", "parent_id does not reference an IR block", f"$.blocks[{index}].parent_id"
            )
    parent_by_id = {
        str(block["block_id"]): str(block["parent_id"])
        for block in blocks
        if isinstance(block, Mapping)
        and isinstance(block.get("block_id"), str)
        and block.get("block_id") in ids
        and isinstance(block.get("parent_id"), str)
        and block.get("parent_id") in ids
    }
    visited: set[str] = set()
    visiting: set[str] = set()

    def visit(block_id: str) -> None:
        if block_id in visited:
            return
        if block_id in visiting:
            _error(errors, "parent_cycle", "IR block parent graph must be acyclic", "$.blocks")
            return
        visiting.add(block_id)
        parent_id = parent_by_id.get(block_id)
        if parent_id is not None:
            visit(parent_id)
        visiting.discard(block_id)
        visited.add(block_id)

    for block_id in ids:
        visit(block_id)
    expected_hash = None
    try:
        document = IRDocument.from_dict(payload)
        expected_hash = document.revision_hash()
    except (TypeError, ValueError, KeyError):
        pass
    revision_id = payload.get("revision_id")
    if revision_id is not None:
        if not isinstance(revision_id, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", revision_id):
            _error(errors, "hash_mismatch", "revision_id must be a SHA-256 hex identity", "$.revision_id")
        elif expected_hash and revision_id != expected_hash:
            _error(errors, "hash_mismatch", "revision_id does not match the canonical IR hash", "$.revision_id")
    return ValidationReport(not errors, errors)


def _validate_locator_range(locator: Mapping[str, Any], path: str, errors: list[dict[str, Any]]) -> None:
    kind = str(locator.get("kind") or "")
    if kind in {"line", "page", "slide"}:
        value = locator.get(kind)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            _error(errors, "locator_range", f"{kind} locator must be a positive integer", f"{path}.{kind}")
    if kind == "timestamp":
        value = locator.get("timestamp")
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
            or float(value) < 0
        ):
            _error(errors, "locator_range", "timestamp locator must be finite and non-negative", f"{path}.timestamp")
    bbox = locator.get("bbox")
    if kind == "bbox" and bbox is None:
        _error(errors, "locator_range", "bbox locator requires four coordinates", f"{path}.bbox")
    if bbox is not None and (
        not isinstance(bbox, list)
        or len(bbox) != 4
        or any(
            not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value))
            for value in bbox
        )
    ):
        _error(errors, "locator_range", "bbox must contain four finite coordinates", f"{path}.bbox")


class IRStore:
    """Write IR revisions and backend mappings with no partial promotion."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, document: IRDocument) -> Path:
        report = validate_ir_document(document)
        if not report.ok:
            raise IRValidationError("invalid_ir", "IR document failed validation", errors=report.errors)
        revision = document.revision_hash()
        destination = self.root / document.document_id / revision
        target = destination / "ir-document.json"
        if target.is_file() and not target.is_symlink():
            existing = json.loads(target.read_text(encoding="utf-8"))
            expected = document.to_dict()
            existing.pop("revision_id", None)
            if existing == expected:
                return destination
            raise IRValidationError("hash_collision", "existing IR revision has different bytes")
        parent = self.root / document.document_id
        parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=f".{revision}.", dir=str(parent)))
        try:
            payload = document.to_dict()
            payload["revision_id"] = revision
            write_json_atomic(temporary / "ir-document.json", payload)
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary, ignore_errors=True)
        return destination

    def read(self, document_id: str, revision: str) -> IRDocument:
        path = self.root / document_id / revision / "ir-document.json"
        if path.is_symlink() or not path.is_file():
            raise FileNotFoundError("IR revision is unavailable")
        document = IRDocument.from_dict(json.loads(path.read_text(encoding="utf-8")))
        report = validate_ir_document(document)
        if not report.ok:
            raise IRValidationError("invalid_ir", "stored IR revision failed validation", errors=report.errors)
        return document

    def put_mapping(self, mapping: BackendMapping) -> Path:
        destination = self.root / "mappings" / f"{mapping.project_revision}-{mapping.ir_revision}.json"
        if destination.is_file() and not destination.is_symlink():
            current = json.loads(destination.read_text(encoding="utf-8"))
            if current == mapping.to_dict():
                return destination
            raise IRValidationError("mapping_immutable", "backend mapping already exists with different bytes")
        write_json_atomic(destination, mapping.to_dict())
        return destination
