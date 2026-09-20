"""Capability-aware extractor selection with fail-closed authorization."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .base import ExtractionResult, Extractor, ExtractorError, ExtractorPolicy


class ExtractorRegistry:
    def __init__(self, extractors: list[Extractor] | None = None) -> None:
        self._extractors: dict[str, Extractor] = {}
        for extractor in extractors or []:
            self.register(extractor)

    def register(self, extractor: Extractor) -> None:
        capability = extractor.describe()
        if capability.name in self._extractors:
            raise ExtractorError("extractor_conflict", f"extractor {capability.name!r} is already registered")
        self._extractors[capability.name] = extractor

    def capabilities(self) -> list[dict[str, Any]]:
        return [self._extractors[name].describe().to_dict() for name in sorted(self._extractors)]

    def choose(
        self,
        artifact: Path | str | Mapping[str, Any],
        *,
        policy: ExtractorPolicy,
    ) -> Extractor:
        suffix, media_type = _artifact_hints(artifact)
        required = policy.required_fidelity
        candidates = []
        for extractor in self._extractors.values():
            capability = extractor.describe()
            if capability.status not in {"available", "disabled"}:
                continue
            if suffix not in capability.supports and media_type not in capability.supports:
                continue
            if required not in capability.fidelity and required != "text-fallback":
                continue
            candidates.append((capability, extractor))
        if not candidates:
            raise ExtractorError("unsupported", "no extractor can satisfy the requested artifact and fidelity")
        candidates.sort(
            key=lambda item: (
                item[0].execution != "local",
                "structured-native" not in item[0].fidelity,
                item[0].name,
            )
        )
        capability, extractor = candidates[0]
        if capability.execution != "local":
            if not policy.allow_remote or capability.name not in set(policy.authorized_extractors):
                raise ExtractorError(
                    "permission_required",
                    "remote or third-party extractor requires explicit project authorization",
                    details={"extractor": capability.name},
                )
        return extractor

    def extract(
        self,
        artifact: Path | str | Mapping[str, Any],
        *,
        policy: ExtractorPolicy,
        budget: Mapping[str, Any] | None = None,
    ) -> ExtractionResult:
        if not policy.rights_ref:
            raise ExtractorError("rights_required", "rights_ref is required before extraction")
        chosen = self.choose(artifact, policy=policy)
        return chosen.extract(artifact, policy, dict(budget or {}))


def default_registry() -> ExtractorRegistry:
    """Build the locally available registry without importing optional parsers eagerly.

    Optional format libraries are discovered by the adapter at extraction time;
    importing the registry therefore remains safe in a minimal installation.
    The legacy adapter is last so a native adapter wins whenever the requested
    fidelity and artifact suffix permit it.
    """

    from .legacy_text import LegacyTextExtractor
    from .office_ebook import OfficeEbookExtractor
    from .pdf import DoclingOcrAdapter, PdfExtractor
    from .repository import RepositoryExtractor
    from .text_web import TextWebExtractor

    return ExtractorRegistry(
        [
            TextWebExtractor(),
            PdfExtractor(ocr=DoclingOcrAdapter()),
            OfficeEbookExtractor(),
            RepositoryExtractor(),
            LegacyTextExtractor(),
        ]
    )


def _artifact_hints(artifact: Path | str | Mapping[str, Any]) -> tuple[str, str | None]:
    kind: str | None = None
    if isinstance(artifact, Mapping):
        raw_path = artifact.get("path") or artifact.get("local_path") or ""
        media_type = artifact.get("media_type") if isinstance(artifact.get("media_type"), str) else None
        raw_kind = artifact.get("kind") or artifact.get("source_kind")
        if isinstance(raw_kind, str):
            kind = raw_kind.casefold()
        path = Path(str(raw_path))
    else:
        path = Path(artifact)
        media_type = None
    if kind:
        return kind, media_type
    if path.is_dir():
        return "directory", media_type
    return path.suffix.casefold(), media_type
