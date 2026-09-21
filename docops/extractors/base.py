"""Extractor public DTOs and authorization policy."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

from ..api_types import CapabilityV2
from ..ir import ExtractionReceipt, IRDocument


class ExtractorError(RuntimeError):
    """Typed extractor selection or execution failure."""

    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(message)


@dataclass(frozen=True)
class ExtractorPolicy:
    rights_ref: str | None = None
    source_id: str = "source-unknown"
    source_revision_id: str = "source-revision-unknown"
    required_fidelity: str = "text-fallback"
    allow_remote: bool = False
    authorized_extractors: tuple[str, ...] = ()
    max_bytes: int = 25 * 1024 * 1024
    max_blocks: int = 100_000
    purpose: str = "knowledge"
    ocr_confidence_threshold: float = 0.85

    def to_dict(self) -> dict[str, Any]:
        return json.loads(
            json.dumps(
                {
                    "rights_ref": self.rights_ref,
                    "source_id": self.source_id,
                    "source_revision_id": self.source_revision_id,
                    "required_fidelity": self.required_fidelity,
                    "allow_remote": self.allow_remote,
                    "authorized_extractors": list(self.authorized_extractors),
                    "max_bytes": self.max_bytes,
                    "max_blocks": self.max_blocks,
                    "purpose": self.purpose,
                    "ocr_confidence_threshold": self.ocr_confidence_threshold,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )


@dataclass(frozen=True)
class ExtractionResult:
    document: IRDocument | None
    receipt: ExtractionReceipt
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "document": self.document.to_dict() if self.document is not None else None,
            "receipt": self.receipt.to_dict(),
            "error": dict(self.error) if self.error else None,
        }


class Extractor(Protocol):
    def describe(self) -> CapabilityV2: ...

    def extract(
        self, artifact: Path | str | Mapping[str, Any], policy: ExtractorPolicy, budget: Mapping[str, Any]
    ) -> ExtractionResult: ...
