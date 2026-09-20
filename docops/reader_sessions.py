"""Pinned, read-only reader sessions for one published package generation."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from .contracts import validate_artifact
from .rag_snapshots import (
    RagSnapshotError,
    build_rag_snapshot,
    rag_snapshot_identity,
    read_rag_snapshot,
    validate_rag_snapshot,
)
from .retrieval import RetrievalError, adapter_for_package
from .revisions import content_hash, package_revisions
from .storage import write_json_atomic

READER_SCHEMA_VERSION = 1
DEFAULT_SESSION_SECONDS = 3600
READ_ONLY_TOOLS = ("search_knowledge", "get_document")
WRITER_TOOLS = frozenset(
    {
        "add_document",
        "update_document",
        "delete_document",
        "reindex_documents",
        "update_source",
    }
)
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class ReaderSessionError(ValueError):
    """A closed failure at the reader-session boundary."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _parse_time(value: str | datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        current = value
    else:
        current = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path, description: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ReaderSessionError("reader_state_missing", f"{description} must be a regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReaderSessionError("reader_state_invalid", f"{description} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise ReaderSessionError("reader_state_invalid", f"{description} must be an object")
    return value


def _root(package_root: Path | str) -> Path:
    root = Path(package_root).expanduser().resolve()
    if root.is_symlink() or not root.is_dir():
        raise ReaderSessionError("package_invalid", "reader package must be a regular directory")
    return root


def _safe_id(value: str, *, field: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
        raise ReaderSessionError("reader_id_invalid", f"{field} contains unsafe characters")
    return value


def _state_root(root: Path) -> Path:
    metadata = root.parent / f".{root.name}.readers"
    if metadata.is_symlink() or (metadata.exists() and not metadata.is_dir()):
        raise ReaderSessionError("reader_state_unavailable", "reader state root must be a regular directory")
    metadata.mkdir(parents=True, exist_ok=True)
    return metadata


def _session_path(root: Path, session_id: str) -> Path:
    return _state_root(root) / "reader-sessions" / f"{_safe_id(session_id, field='session_id')}.json"


def _snapshot_path(root: Path, snapshot_id: str) -> Path:
    return _state_root(root) / "snapshots" / f"{_safe_id(snapshot_id, field='snapshot_id')}.json"


def _revocation_path(root: Path) -> Path:
    return _state_root(root) / "reader-revocations.json"


def _load_revocations(root: Path) -> dict[str, dict[str, Any]]:
    path = _revocation_path(root)
    if not path.exists():
        return {}
    value = _read_json(path, "reader revocations")
    raw = value.get("sessions", {})
    if not isinstance(raw, Mapping):
        raise ReaderSessionError("reader_state_invalid", "reader revocations sessions must be an object")
    return {str(key): dict(item) for key, item in raw.items() if isinstance(item, Mapping)}


def _write_revocation(root: Path, session_id: str, *, now: datetime, reason: str | None) -> None:
    payload = {
        "schema_version": READER_SCHEMA_VERSION,
        "sessions": _load_revocations(root),
    }
    payload["sessions"][session_id] = {
        "revoked_at": _iso(now),
        "reason": reason or "operator_revoked",
    }
    write_json_atomic(_revocation_path(root), payload)


def _package_id(root: Path) -> str:
    manifest_path = root / "manifest.json"
    if manifest_path.is_file() and not manifest_path.is_symlink():
        try:
            value = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            value = {}
        if isinstance(value, Mapping):
            for key in ("package_id", "run_id"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate
    return root.name


def _generation(root: Path) -> dict[str, str]:
    revisions = package_revisions(root)
    return {
        "release_id": str(revisions["release_id"]),
        "composition_hash": str(revisions["composition_hash"]),
    }


def _history_root(root: Path) -> Path:
    return root.parent / f".{root.name}.history"


def _history_generation(root: Path, generation: Mapping[str, Any]) -> Path:
    release_id = _safe_id(str(generation.get("release_id") or ""), field="release_id")
    entry = _history_root(root) / release_id
    if entry.is_symlink() or not entry.is_dir():
        raise ReaderSessionError(
            "reader_generation_unavailable",
            "the pinned reader generation is no longer available",
        )
    receipt = _read_json(entry / ".docops" / "history.json", "history receipt")
    if receipt.get("revoked") is True:
        raise ReaderSessionError("reader_generation_revoked", "the pinned reader generation was revoked")
    if receipt.get("release_id") != generation.get("release_id") or receipt.get("composition_hash") != generation.get(
        "composition_hash"
    ):
        raise ReaderSessionError("reader_generation_mismatch", "history does not match the pinned generation")
    return entry


def _resolve_generation(root: Path, generation: Mapping[str, Any]) -> Path:
    current = _generation(root)
    if current["release_id"] == generation.get("release_id") and current["composition_hash"] == generation.get(
        "composition_hash"
    ):
        return root
    return _history_generation(root, generation)


def _validate_session(value: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(value)
    contract = validate_artifact("reader-session", payload)
    if not contract.ok:
        raise ReaderSessionError("reader_session_invalid", "reader session violates its public contract")
    return payload


def _load_session(root: Path, session_id: str) -> dict[str, Any]:
    payload = _validate_session(_read_json(_session_path(root, session_id), "reader session"))
    if payload["session_id"] != session_id:
        raise ReaderSessionError("reader_session_mismatch", "reader session id does not match its path")
    return payload


def _load_pinned_snapshot(root: Path, session: Mapping[str, Any]) -> dict[str, Any]:
    identity = session.get("snapshot")
    if not isinstance(identity, Mapping):
        raise ReaderSessionError("reader_snapshot_invalid", "reader session has no pinned snapshot")
    try:
        snapshot_id = _safe_id(str(identity.get("snapshot_id") or ""), field="snapshot_id")
        snapshot = read_rag_snapshot(_snapshot_path(root, snapshot_id))
    except (RagSnapshotError, OSError, ValueError) as exc:
        code = (
            "reader_snapshot_revoked"
            if getattr(exc, "code", "") == "rag_snapshot_revoked"
            else "reader_snapshot_invalid"
        )
        raise ReaderSessionError(code, "pinned reader snapshot is unavailable") from exc
    if rag_snapshot_identity(snapshot) != dict(identity):
        raise ReaderSessionError("reader_snapshot_mismatch", "reader session snapshot identity does not match its file")
    return snapshot


def _validate_pinned_snapshot(root: Path, session: Mapping[str, Any], generation_root: Path) -> dict[str, Any]:
    snapshot = _load_pinned_snapshot(root, session)
    try:
        validate_rag_snapshot(root, snapshot, generation_root=generation_root)
    except RagSnapshotError as exc:
        if exc.code in {"rag_snapshot_revoked", "rag_snapshot_revocation_invalid"}:
            code = "reader_snapshot_revoked"
        elif exc.code == "rag_snapshot_incompatible":
            code = "reader_snapshot_incompatible"
        else:
            code = "reader_snapshot_invalid"
        raise ReaderSessionError(code, "pinned reader snapshot is no longer valid") from exc
    return snapshot


def _assert_session_active(root: Path, session: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    if session.get("status") != "active":
        raise ReaderSessionError("reader_session_revoked", "reader session is not active")
    if _parse_time(str(session.get("expires_at"))) <= now:
        raise ReaderSessionError("reader_session_expired", "reader session has expired")
    if session["session_id"] in _load_revocations(root):
        raise ReaderSessionError("reader_session_revoked", "reader session was revoked")
    generation_root = _resolve_generation(root, session["generation"])
    return _validate_pinned_snapshot(root, session, generation_root)


def _reader_capability(root: Path, adapter: str) -> dict[str, Any]:
    del root
    if adapter != "memory":
        raise ReaderSessionError("reader_adapter_invalid", "reader adapter must be memory after legacy contraction")
    return {
        "adapter": "memory",
        "concurrent_publication_allowed": False,
        "capability_source": "local-read-only-adapter",
    }


def create_reader_session(
    package_root: Path | str,
    *,
    adapter: str = "memory",
    session_id: str | None = None,
    snapshot: Path | str | Mapping[str, Any] | None = None,
    now: str | datetime | None = None,
    expires_at: str | datetime | None = None,
) -> dict[str, Any]:
    """Create a session pinned to the package's current generation."""

    root = _root(package_root)
    current = _parse_time(now)
    capability = _reader_capability(root, adapter)
    generation = _generation(root)
    generation_root = _resolve_generation(root, generation)
    expected_backend = "memory"
    try:
        pinned_snapshot = (
            build_rag_snapshot(
                generation_root,
                backend=expected_backend,
                supports_incremental=False,
            )
            if snapshot is None
            else read_rag_snapshot(snapshot)
        )
        backend = pinned_snapshot.get("backend")
        if not isinstance(backend, Mapping) or backend.get("name") != expected_backend:
            raise RagSnapshotError(
                "rag_snapshot_adapter_mismatch", "snapshot backend does not match the reader adapter"
            )
        validate_rag_snapshot(root, pinned_snapshot, generation_root=generation_root)
        snapshot_identity = rag_snapshot_identity(pinned_snapshot)
    except RagSnapshotError as exc:
        if exc.code in {"rag_snapshot_revoked", "rag_snapshot_revocation_invalid"}:
            code = "reader_snapshot_revoked"
        elif exc.code == "rag_snapshot_adapter_mismatch":
            code = "reader_snapshot_adapter_mismatch"
        elif exc.code == "rag_snapshot_incompatible":
            code = "reader_snapshot_incompatible"
        else:
            code = "reader_snapshot_invalid"
        raise ReaderSessionError(code, "reader snapshot cannot be pinned") from exc
    identifier = _safe_id(session_id, field="session_id") if session_id else f"reader-{uuid.uuid4().hex}"
    expiration = (
        _parse_time(expires_at) if expires_at is not None else current + timedelta(seconds=DEFAULT_SESSION_SECONDS)
    )
    if expiration <= current:
        raise ReaderSessionError("reader_expiry_invalid", "reader session expiry must be in the future")
    payload = {
        "schema_version": READER_SCHEMA_VERSION,
        "session_id": identifier,
        "package_id": _package_id(root),
        "generation": generation,
        "snapshot": snapshot_identity,
        "created_at": _iso(current),
        "expires_at": _iso(expiration),
        "status": "active",
        "permissions": {
            "profile": "reader",
            "read_only": True,
            "allowed_tools": list(READ_ONLY_TOOLS),
            "denied_tools": sorted(WRITER_TOOLS),
        },
        "backend": capability,
    }
    _validate_session(payload)
    write_json_atomic(_snapshot_path(root, str(snapshot_identity["snapshot_id"])), pinned_snapshot)
    write_json_atomic(_session_path(root, identifier), payload)
    return {"schema_version": READER_SCHEMA_VERSION, "ok": True, **payload}


def revoke_reader_session(
    package_root: Path | str,
    session_id: str,
    *,
    now: str | datetime | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Revoke one reader session without changing package content."""

    root = _root(package_root)
    identifier = _safe_id(session_id, field="session_id")
    session = _load_session(root, identifier)
    current = _parse_time(now)
    _write_revocation(root, identifier, now=current, reason=reason)
    session["status"] = "revoked"
    write_json_atomic(_session_path(root, identifier), session)
    return {
        "schema_version": READER_SCHEMA_VERSION,
        "ok": True,
        "session_id": identifier,
        "status": "revoked",
        "revoked_at": _iso(current),
    }


def _cache_path(root: Path, session_id: str, key: str) -> Path:
    return _state_root(root) / "reader-cache" / _safe_id(session_id, field="session_id") / f"{key}.json"


def _get_document(generation_root: Path, query: str) -> list[dict[str, Any]]:
    relative = Path(query.replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts:
        raise ReaderSessionError("reader_document_invalid", "document path must remain inside rag/documents")
    document = generation_root / "rag" / "documents" / relative
    documents_root = (generation_root / "rag" / "documents").resolve()
    try:
        resolved = document.resolve()
        resolved.relative_to(documents_root)
    except ValueError as exc:
        raise ReaderSessionError("reader_document_invalid", "document path escapes rag/documents") from exc
    if resolved.is_symlink() or not resolved.is_file():
        raise ReaderSessionError("reader_document_missing", "requested document is not available")
    return [
        {
            "source": resolved.relative_to(documents_root).as_posix(),
            "content": resolved.read_text(encoding="utf-8", errors="replace"),
            "score": 1.0,
        }
    ]


def query_reader_session(
    package_root: Path | str,
    session_id: str,
    *,
    tool: str,
    query: str,
    adapter: str | None = None,
    max_results: int = 5,
    now: str | datetime | None = None,
    runtime_root: Path | str | None = None,
) -> dict[str, Any]:
    """Execute only a read tool against the generation pinned by a session."""

    root = _root(package_root)
    session = _load_session(root, _safe_id(session_id, field="session_id"))
    current = _parse_time(now)
    _assert_session_active(root, session, current)
    if tool in WRITER_TOOLS or tool not in READ_ONLY_TOOLS:
        raise ReaderSessionError("reader_tool_denied", "reader sessions cannot call writer or unknown tools")
    if not isinstance(query, str) or not query.strip():
        raise ReaderSessionError("reader_query_invalid", "reader query must be non-empty")
    if isinstance(max_results, bool) or not isinstance(max_results, int) or not 1 <= max_results <= 100:
        raise ReaderSessionError("reader_limit_invalid", "max_results must be between 1 and 100")

    generation_root = _resolve_generation(root, session["generation"])
    selected_adapter = adapter or str(session["backend"]["adapter"])
    if selected_adapter != session["backend"]["adapter"]:
        raise ReaderSessionError("reader_adapter_mismatch", "query adapter does not match the pinned session")
    cache_key = content_hash(
        {
            "session_id": session["session_id"],
            "generation": session["generation"],
            "tool": tool,
            "query": query,
            "max_results": max_results,
        }
    )
    cache = _cache_path(root, session["session_id"], cache_key)
    if cache.is_file() and not cache.is_symlink():
        cached = _read_json(cache, "reader cache")
        if (
            cached.get("session_id") == session["session_id"]
            and cached.get("generation") == session["generation"]
            and cached.get("snapshot") == session["snapshot"]
            and cached.get("tool") == tool
        ):
            return {**cached, "cache_hit": True}

    if tool == "get_document":
        results = _get_document(generation_root, query)
        metadata = {"backend": "local-snapshot", "adapter": "read_only_document"}
    else:
        try:
            retrieval = adapter_for_package(generation_root, selected_adapter)
            try:
                results = retrieval.search(query, max_results=max_results)
                metadata = retrieval.metadata()
            finally:
                retrieval.close()
        except RetrievalError as exc:
            raise ReaderSessionError(exc.code, str(exc)) from exc
    payload = {
        "schema_version": READER_SCHEMA_VERSION,
        "ok": True,
        "session_id": session["session_id"],
        "generation": dict(session["generation"]),
        "snapshot": dict(session["snapshot"]),
        "tool": tool,
        "query": query,
        "results": results[:max_results],
        "cache_hit": False,
        "metadata": metadata,
    }
    contract = validate_artifact("reader-query", payload)
    if not contract.ok:
        raise ReaderSessionError("reader_query_invalid", "reader query violates its public contract")
    write_json_atomic(cache, payload)
    return payload


__all__ = [
    "ReaderSessionError",
    "create_reader_session",
    "query_reader_session",
    "revoke_reader_session",
]
