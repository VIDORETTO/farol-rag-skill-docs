"""Build and open the default local factual index of a generated package.

The index is derived from the package's normalized corpus (``rag/documents``)
through the governed extractor registry, so hits carry canonical IR blocks and
locators. It lives under ``rag/local-index/`` and is always rebuildable; the
``ACTIVE.json`` pointer is replaced atomically after the new revision exists.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .backends.base import BackendUnavailable, IndexRevision
from .backends.local_fts import LocalFtsBackend
from .extractors import ExtractorError, ExtractorPolicy, default_registry
from .revisions import content_hash
from .safety import classify
from .storage import write_json_atomic

INDEX_DIR = Path("rag") / "local-index"
ACTIVE_POINTER = "ACTIVE.json"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _page_ranges(locators: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A page spans from its heading to the next page heading (not the next section)."""

    pages = sorted(
        (item for item in locators if item.get("kind") == "page" and "number" in item),
        key=lambda item: int(item.get("line_start", 0)),
    )
    ranges = []
    for index, page in enumerate(pages):
        end = int(pages[index + 1]["line_start"]) - 1 if index + 1 < len(pages) else 10**9
        ranges.append({**page, "line_end": end})
    return ranges


def _relative_locators(
    locators: list[dict[str, Any]],
    relative: str,
    pages: list[dict[str, Any]] | None = None,
    timestamps: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    # Extractors record the absolute origin of the file they read; published
    # evidence must only cite the package-relative path.
    cleaned = []
    for locator in locators:
        value = {key: item for key, item in locator.items() if key != "origin"}
        value["path"] = relative
        cleaned.append(value)
    line = next((item.get("line") for item in cleaned if item.get("kind") == "line"), None)
    if isinstance(line, int):
        for stamp in timestamps or []:
            if int(stamp.get("line_start", 0)) == line:
                cleaned.append({"kind": "timestamp", "start": stamp.get("start"), "label": stamp.get("label")})
                break
        for page in pages or []:
            if int(page.get("line_start", 0)) <= line <= int(page.get("line_end", -1)):
                cleaned.append({"kind": "page", "page": int(page["number"]), "label": str(page.get("label"))})
                break
    return cleaned


def package_documents(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    manifest = _read_json(root / "manifest.json")
    rights = str((manifest.get("source") or {}).get("license") or "")
    sources = _read_json(root / "rag" / "sources.json").get("sources", [])
    registry = default_registry()
    documents: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for entry in sources:
        destination = str(entry.get("destination") or "")
        path = root / "rag" / "documents" / destination
        relative = f"rag/documents/{destination}"
        if not destination or not path.is_file() or path.is_symlink():
            skipped.append({"path": relative, "code": "document_missing"})
            continue
        source_id = f"src-{content_hash(str(entry.get('canonical') or destination))[:16]}"
        revision = str(entry.get("content_hash") or content_hash(path.read_bytes().hex()))
        try:
            result = registry.extract(
                path,
                policy=ExtractorPolicy(
                    rights_ref=rights or "unspecified",
                    source_id=source_id,
                    source_revision_id=revision,
                    purpose="local-factual-index",
                ),
            )
        except ExtractorError as exc:
            skipped.append({"path": relative, "code": exc.code})
            continue
        if result.document is None:
            skipped.append({"path": relative, "code": "extraction_empty"})
            continue
        pages = _page_ranges(entry.get("locators") or [])
        timestamps = [item for item in entry.get("locators") or [] if item.get("kind") == "timestamp"]
        documents.append(
            {
                "document_id": result.document.document_id,
                "source_id": source_id,
                "source_revision_id": revision,
                "path": relative,
                "status": str(entry.get("status") or "active"),
                "blocks": [
                    {
                        **block.to_dict(),
                        "locators": _relative_locators(block.to_dict()["locators"], relative, pages, timestamps),
                        "risk": classify(block.text or "").risk,
                    }
                    for block in result.document.blocks
                ],
            }
        )
    return _as_course(root, documents), skipped


def _as_course(root: Path, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Order a course's lessons and name its modules (``.docops/course.json``, written by the journey)."""

    path = root / ".docops" / "course.json"
    if not path.is_file():
        return documents
    course = _read_json(path)
    order = {f"rag/documents/{item}": position for position, item in enumerate(course.get("order") or [])}
    modules = {f"rag/documents/{key}": value for key, value in (course.get("modules") or {}).items()}
    titles = {f"rag/documents/{key}": value for key, value in (course.get("titles") or {}).items()}
    for document in documents:
        title = titles.get(document["path"])
        module = modules.get(document["path"])
        for block in document["blocks"]:
            heading = list(block.get("heading_path") or [])
            # Titles derived from file names lose their dashes ("Aula 1 - Intro" -> "Aula 1   Intro").
            if title and heading and _loose(heading[0]) == _loose(title):
                heading[0] = title
            if module:
                heading = [module, *heading]
            block["heading_path"] = heading
    return sorted(documents, key=lambda document: order.get(document["path"], len(order)))


def _loose(value: str) -> str:
    return " ".join(value.replace("-", " ").replace("_", " ").split())


_AUTO = "auto"
_EMBEDDER_CACHE: dict[str, Any] = {}


def _resolve_embedder(embedder: Any) -> Any:
    """``"auto"`` loads the ``semantic`` extra's model once per process, if installed."""

    if embedder != _AUTO:
        return embedder
    if "default" not in _EMBEDDER_CACHE:
        from .backends.semantic import load_embedder

        _EMBEDDER_CACHE["default"] = load_embedder()
    return _EMBEDDER_CACHE["default"]


def build_package_index(package_root: Path | str, *, embedder: Any = _AUTO) -> dict[str, Any]:
    """Index the package corpus with the local backend (hybrid when embeddings exist) and activate it."""

    root = Path(package_root).resolve()
    documents, skipped = package_documents(root)
    ir_revision = content_hash([document["document_id"] for document in documents])
    pointer = root / INDEX_DIR / ACTIVE_POINTER
    replaced = str(_read_json(pointer).get("index_revision") or "") if pointer.is_file() else ""
    embedder = _resolve_embedder(embedder)
    backend = LocalFtsBackend(root / INDEX_DIR, embedder=embedder)
    try:
        candidate = backend.prepare("package", ir_revision, metadata={"documents": documents})
        index = backend.apply(candidate)
    finally:
        backend.close()
    blocks = sum(len(document["blocks"]) for document in documents)
    write_json_atomic(
        pointer,
        {"schema_version": 1, "backend": index.backend, "index_revision": index.index_revision},
    )
    _prune_indexes(root / INDEX_DIR, keep={index.index_revision, replaced})
    return {
        "status": index.state,
        "backend": index.backend,
        "index_revision": index.index_revision,
        "documents": len(documents),
        "blocks": blocks,
        "skipped": skipped,
        "retrieval_mode": "hybrid" if embedder is not None else "bm25",
    }


def _prune_indexes(index_dir: Path, *, keep: set[str]) -> None:
    """Remove superseded index files, keeping the active one and the one it replaced.

    The replaced index stays because a running reader (``farol mcp``) may still
    have it open; anything older is disk the user never gets back otherwise.
    """

    for path in index_dir.glob("index-*.sqlite"):
        if path.stem in keep:
            continue
        try:
            path.unlink()
        except OSError:
            continue  # in use on Windows; the next build removes it


def open_package_index(package_root: Path | str, *, embedder: Any = _AUTO) -> tuple[LocalFtsBackend, IndexRevision]:
    """Open the active local index of a package for read-only queries."""

    root = Path(package_root).resolve()
    pointer = root / INDEX_DIR / ACTIVE_POINTER
    if not pointer.is_file():
        raise BackendUnavailable("index_missing", "package has no local index; run the build step first")
    revision = str(_read_json(pointer).get("index_revision") or "")
    index = LocalFtsBackend(root / INDEX_DIR).open(revision)
    # Only an index built with embeddings needs the model; plain BM25 stays light.
    chosen = _resolve_embedder(embedder) if index.fingerprints.get("embedding") else None
    backend = LocalFtsBackend(root / INDEX_DIR, embedder=chosen)
    return backend, index
