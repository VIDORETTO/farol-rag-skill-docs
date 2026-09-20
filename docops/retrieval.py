"""Local retrieval adapters used by factual, skill and router evaluation seams."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Protocol

_TOKEN = re.compile(r"[\wÀ-ÿ][\wÀ-ÿ./:-]*", re.UNICODE)


class RetrievalError(RuntimeError):
    """A reportable failure at a retrieval adapter boundary."""

    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(message)


class RetrievalAdapter(Protocol):
    """Minimal public seam shared by local diagnostic retrieval backends."""

    def search(self, query: str, *, max_results: int) -> list[dict[str, Any]]: ...

    def metadata(self) -> dict[str, Any]: ...

    def close(self) -> None: ...


def _tokens(value: str) -> set[str]:
    return {token.casefold() for token in _TOKEN.findall(value)}


def _load_source_metadata(package_root: Path | str) -> dict[str, dict[str, Any]]:
    path = Path(package_root).resolve() / "rag" / "sources.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    entries = payload.get("sources") if isinstance(payload, Mapping) else None
    if not isinstance(entries, list):
        return {}
    metadata: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, Mapping) or not entry.get("destination"):
            continue
        destination = str(entry["destination"]).replace("\\", "/").lstrip("./")
        metadata[destination] = dict(entry)
    return metadata


def _citation_fragment(locator: Mapping[str, Any]) -> str | None:
    kind = str(locator.get("kind") or "").strip()
    label = str(locator.get("label") or "").strip().replace("#", "%23").replace("\n", " ")
    if not kind or not label:
        return None
    return f"{kind}={label}"


def _citations_for(source: str, locators: list[Mapping[str, Any]]) -> list[str]:
    citations: list[str] = []
    for locator in locators:
        fragment = _citation_fragment(locator)
        if fragment:
            citation = f"{source}#{fragment}"
            if citation not in citations:
                citations.append(citation)
    return citations


def _rank(
    documents: Mapping[str, str],
    query: str,
    max_results: int,
    metadata: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    query_tokens = _tokens(query)
    ranked: list[dict[str, Any]] = []
    for path, content in documents.items():
        content_tokens = _tokens(content)
        path_tokens = _tokens(path)
        overlap = len(query_tokens & content_tokens) / len(query_tokens) if query_tokens else 0.0
        path_overlap = len(query_tokens & path_tokens) / len(query_tokens) if query_tokens else 0.0
        phrase = 1.0 if query and query.casefold() in content.casefold() else 0.0
        source_metadata = dict((metadata or {}).get(path, {}))
        locators = source_metadata.get("locators")
        if not isinstance(locators, list):
            locators = []
        hit: dict[str, Any] = {
            "source": path,
            "content": content,
            "score": overlap + path_overlap * 0.5 + phrase * 0.5,
            "locators": [dict(locator) for locator in locators if isinstance(locator, Mapping)],
        }
        hit["citations"] = _citations_for(path, hit["locators"])
        for key in (
            "source_id",
            "observed_revision",
            "canonical",
            "destination",
            "format",
            "title",
            "quality_status",
            "quality_reason",
        ):
            if key in source_metadata:
                hit[key] = source_metadata[key]
        ranked.append(hit)
    ranked.sort(key=lambda item: (-float(item["score"]), str(item["source"])))
    return ranked[:max_results]


class InMemoryRetrievalAdapter:
    """A deterministic adapter for tests without mocking DOCOPS internals."""

    def __init__(
        self,
        documents: Mapping[str, str],
        *,
        profile: str = "memory-v1",
        document_metadata: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        self.documents = {str(path).replace("\\", "/"): str(content) for path, content in documents.items()}
        self.profile = profile
        self.document_metadata = {
            str(path).replace("\\", "/").lstrip("./"): dict(value)
            for path, value in (document_metadata or {}).items()
            if isinstance(value, Mapping)
        }

    @classmethod
    def from_package(cls, package_root: Path | str) -> "InMemoryRetrievalAdapter":
        root = Path(package_root).resolve() / "rag" / "documents"
        documents = {
            path.relative_to(root).as_posix(): path.read_text(encoding="utf-8", errors="replace")
            for path in sorted(root.rglob("*"))
            if path.is_file() and not path.is_symlink()
        }
        return cls(documents, document_metadata=_load_source_metadata(package_root))

    def search(self, query: str, *, max_results: int) -> list[dict[str, Any]]:
        return _rank(self.documents, query, max_results, self.document_metadata)

    def metadata(self) -> dict[str, Any]:
        return {
            "backend": "memory",
            "adapter": "memory",
            "mode": "gate",
            "profile": self.profile,
            "corpus": {
                "corpus_documents": len(self.documents),
                "operator_chunks": None,
                "backend_total_documents": None,
                "backend_total_chunks": None,
            },
        }

    def close(self) -> None:
        return


class LexicalDiagnosticAdapter(InMemoryRetrievalAdapter):
    """The fast token-overlap scorer retained as a named diagnostic."""

    def __init__(self, package_root: Path | str) -> None:
        loaded = InMemoryRetrievalAdapter.from_package(package_root)
        super().__init__(
            loaded.documents,
            profile="token-overlap-v1",
            document_metadata=loaded.document_metadata,
        )

    def metadata(self) -> dict[str, Any]:
        value = super().metadata()
        value.update({"backend": "lexical", "adapter": "lexical-diagnostic", "mode": "diagnostic"})
        return value


class SkillRetrievalAdapter(InMemoryRetrievalAdapter):
    """Search the generated skill artifacts for conceptual cases."""

    def __init__(self, package_root: Path | str) -> None:
        root = Path(package_root).resolve() / "skill"
        documents = {
            path.relative_to(root).as_posix(): path.read_text(encoding="utf-8", errors="replace")
            for path in sorted(root.rglob("*.md"))
            if path.is_file() and not path.is_symlink()
        }
        super().__init__(documents, profile="skill-markdown-v1")

    def metadata(self) -> dict[str, Any]:
        value = super().metadata()
        value.update({"backend": "skill", "adapter": "skill-conceptual", "mode": "gate"})
        return value


def route_query(query: str) -> str:
    """Classify a query using the documented skill/RAG routing policy."""

    persistent = re.compile(
        r"\b(add|approve|change|delete|index|ingest|modify|publish|reconcile|register|remove|revoke|rollback|update)\b",
        re.I,
    )
    literal = re.compile(
        r"\b(default|defaults|signature|endpoint|version|changelog|exact|literal|parameter|config(?:uration)?)\b", re.I
    )
    conceptual = re.compile(r"\b(how|why|pattern|concept|conceptual|guide|best practice|trade-?off|design)\b", re.I)
    if persistent.search(query):
        return "lifecycle"
    has_literal = bool(literal.search(query))
    has_conceptual = bool(conceptual.search(query))
    if has_literal and has_conceptual:
        return "both"
    if has_literal:
        return "rag"
    return "skill"


def _safe_source_reference(raw_source: str, documents_root: Path) -> str:
    normalized = raw_source.strip().replace("\\", "/")
    if not normalized or "://" in normalized:
        return "<external-source>" if normalized else "<unknown-source>"
    source_path = Path(raw_source)
    is_absolute = source_path.is_absolute() or bool(re.match(r"^[A-Za-z]:/", normalized))
    if is_absolute:
        try:
            return source_path.resolve().relative_to(documents_root.resolve()).as_posix()
        except (ValueError, OSError):
            marker = "/rag/documents/"
            if marker in normalized:
                candidate = normalized.split(marker, 1)[1]
                parts = tuple(part for part in candidate.split("/") if part not in {"", "."})
                if parts and ".." not in parts:
                    return "/".join(parts)
            return "<external-source>"
    for prefix in ("./", "documents/", "rag/documents/"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
            break
    parts = tuple(part for part in normalized.split("/") if part not in {"", "."})
    if not parts or ".." in parts:
        return "<external-source>"
    return "/".join(parts)


def adapter_for_package(
    package_root: Path | str,
    adapter: str | RetrievalAdapter | None,
) -> RetrievalAdapter:
    """Resolve the remaining local retrieval seams after legacy contraction."""

    if adapter is None or adapter == "lexical":
        return LexicalDiagnosticAdapter(package_root)
    if adapter == "memory":
        return InMemoryRetrievalAdapter.from_package(package_root)
    if hasattr(adapter, "search") and hasattr(adapter, "metadata"):
        return adapter
    raise ValueError("adapter must be lexical, memory or a RetrievalAdapter")
