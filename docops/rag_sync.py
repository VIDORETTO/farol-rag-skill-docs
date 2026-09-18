"""Optional integration with the user's local knowledge-rag MCP server."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config_audit import audit_config_file, load_config
from .contracts import validate_artifact
from .mcp_client import first_json_payload, start_mcp_server
from .observability import redact_report
from .retrieval import RetrievalError, adapter_for_package
from .revisions import content_hash, package_revisions
from .runtime import discover_rag_python, runtime_environment, runtime_provenance
from .storage import write_json_atomic, write_text_atomic


class RagSyncError(RuntimeError):
    """A structured failure at the knowledge-rag boundary."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class RagSnapshotError(ValueError):
    """A closed failure while reading or comparing an immutable RAG snapshot."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


SUPPORTED_EMBEDDING_PROFILES = ("compact", "multilingual", "quality")
RAG_SNAPSHOT_SCHEMA_VERSION = 1


def _response_payload(response: Mapping[str, Any], operation: str) -> dict[str, Any]:
    """Require a structured MCP tool response before advancing a phase."""

    if response.get("error"):
        raise RagSyncError("mcp_rpc_error", f"{operation} returned an MCP error")
    result = response.get("result")
    if isinstance(result, Mapping) and result.get("isError") is True:
        raise RagSyncError("mcp_tool_error", f"{operation} returned an MCP tool error")
    payload = first_json_payload(response)
    if payload is None:
        raise RagSyncError("rag_invalid_payload", f"{operation} returned no JSON payload")
    return payload


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _document_count(root: Path) -> int:
    documents = root / "rag" / "documents"
    if not documents.is_dir() or documents.is_symlink():
        return 0
    try:
        return sum(1 for path in documents.rglob("*") if path.is_file() and not path.is_symlink())
    except OSError:
        return 0


def embedding_configuration(
    package_root: Path | str,
    *,
    stats: Mapping[str, Any] | None = None,
    server_version: str | None = None,
) -> dict[str, Any]:
    """Return non-secret configured and effective embedding identity."""

    root = Path(package_root).resolve()
    config = load_config(root / "config.yaml")
    models = _mapping(config.get("models"))
    embedding = _mapping(models.get("embedding"))
    configured = {
        "profile": embedding.get("profile") or "unknown",
        "model": embedding.get("model") or embedding.get("model_name"),
        "model_revision": embedding.get("model_revision") or embedding.get("revision"),
        "dimensions": embedding.get("dimensions") or embedding.get("dim") or embedding.get("embedding_dim"),
        "query_prefix": embedding.get("query_prefix"),
        "passage_prefix": embedding.get("passage_prefix"),
    }
    fingerprint = content_hash(configured)
    effective_stats = _mapping(stats)
    return {
        "profile": str(configured["profile"]),
        "embedding_fingerprint": fingerprint,
        "configured": configured,
        "effective": {
            "model": effective_stats.get("embedding_model"),
            "dimensions": effective_stats.get("embedding_dim"),
        },
        "backend_version": server_version,
    }


def compare_embedding_profiles(
    package_root: Path | str,
    *,
    profiles: tuple[str, ...] = ("compact", "multilingual"),
    language: str | None = None,
    selected_profile: str | None = None,
) -> dict[str, Any]:
    """Compare candidate embedding profiles without changing package state."""

    normalized_profiles = tuple(dict.fromkeys(profile.strip() for profile in profiles if profile.strip()))
    if not normalized_profiles:
        raise RagSnapshotError("embedding_profiles_invalid", "at least one embedding profile is required")
    unknown = sorted(set(normalized_profiles) - set(SUPPORTED_EMBEDDING_PROFILES))
    if unknown:
        raise RagSnapshotError(
            "embedding_profile_unknown",
            f"unsupported embedding profile(s): {', '.join(unknown)}",
        )
    current = embedding_configuration(package_root)
    current_profile = str(current.get("profile") or "unknown")
    selected = (
        selected_profile.strip() if isinstance(selected_profile, str) and selected_profile.strip() else current_profile
    )
    if selected not in normalized_profiles:
        raise RagSnapshotError(
            "embedding_selection_invalid",
            "selected profile must be one of the profiles being compared",
        )
    requires_full_rebuild = selected != current_profile
    payload = {
        "schema_version": 1,
        "ok": True,
        "language": language or "unknown",
        "current_profile": current_profile,
        "current_configuration": current,
        "profiles": [
            {
                "name": profile,
                "is_current": profile == current_profile,
                "comparison_status": "not_evaluated",
                "evaluation_required": True,
                "rebuild_required": profile != current_profile,
            }
            for profile in normalized_profiles
        ],
        "selected_profile": selected,
        "requires_full_rebuild": requires_full_rebuild,
        "publication_allowed": False,
        "evidence_status": "not_evaluated",
        "required_evaluation": "reviewed_golden_native_portuguese",
        "decision": "full_rebuild_required" if requires_full_rebuild else "no_profile_change",
    }
    contract = validate_artifact("rag-profile-comparison", payload)
    if not contract.ok:
        raise RagSnapshotError("embedding_comparison_invalid", "embedding profile comparison violated its contract")
    return payload


def _raw_file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _configuration_identity(root: Path) -> dict[str, Any]:
    path = root / "config.yaml"
    if path.is_symlink() or not path.is_file():
        raise RagSnapshotError("rag_snapshot_config_missing", "snapshot requires a regular package config.yaml")
    try:
        configured = load_config(path)
        raw = path.read_bytes()
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise RagSnapshotError("rag_snapshot_config_invalid", "snapshot configuration is unreadable") from exc
    if not isinstance(configured, Mapping):
        raise RagSnapshotError("rag_snapshot_config_invalid", "snapshot configuration must be an object")
    return {
        "path": "config.yaml",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "content_hash": content_hash(configured),
        "redacted": True,
    }


def _model_identity(embedding: Mapping[str, Any]) -> dict[str, Any]:
    configured = _mapping(embedding.get("configured"))
    effective = _mapping(embedding.get("effective"))
    return {
        "name": configured.get("model"),
        "revision": configured.get("model_revision"),
        "configured_dimensions": configured.get("dimensions"),
        "effective_name": effective.get("model"),
        "effective_dimensions": effective.get("dimensions"),
    }


def _artifact_file(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.exists() and not path.is_symlink():
        return {"path": relative, "present": False, "sha256": None, "size": 0}
    if path.is_symlink() or not path.is_file():
        raise RagSnapshotError("rag_snapshot_artifact_invalid", f"{relative} must be a regular file")
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise RagSnapshotError("rag_snapshot_artifact_read_failed", f"could not read {relative}") from exc
    return {"path": relative, "present": True, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}


def _artifact_inventory(root: Path, backend_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    files: dict[str, dict[str, Any]] = {}
    for relative in ("rag/index.json", "rag/sources.json"):
        entry = _artifact_file(root, relative)
        files[relative] = entry
    data = backend_snapshot.get("data")
    data_files = data.get("files") if isinstance(data, Mapping) else None
    if isinstance(data_files, Mapping):
        for relative, entry in data_files.items():
            if isinstance(entry, Mapping):
                files[f"rag/data/{relative}"] = {
                    "path": f"rag/data/{relative}",
                    "present": True,
                    "sha256": entry.get("sha256"),
                    "size": entry.get("size", 0),
                }
    entries = [
        (path, {key: value for key, value in item.items() if key != "path"}) for path, item in sorted(files.items())
    ]
    return {
        "content_hash": content_hash(entries),
        "file_count": len(files),
        "files": files,
    }


def _state_json(root: Path, relative: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    path = root / relative
    if not path.exists() and not path.is_symlink():
        return None, {"path": relative, "present": False, "sha256": None, "size": 0}
    if path.is_symlink() or not path.is_file():
        raise RagSnapshotError("rag_snapshot_revocation_invalid", f"{relative} must be a regular file")
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RagSnapshotError("rag_snapshot_revocation_invalid", f"{relative} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise RagSnapshotError("rag_snapshot_revocation_invalid", f"{relative} must contain an object")
    return value, {
        "path": relative,
        "present": True,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size": len(raw),
    }


def _normalize_document_destination(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("\\", "/").lstrip("./")
    if normalized.startswith("rag/documents/"):
        normalized = normalized.removeprefix("rag/documents/")
    if not normalized or ".." in normalized.split("/"):
        return None
    return normalized


def _record_destinations(record: Mapping[str, Any]) -> set[str]:
    raw = record.get("destinations")
    if raw is None and isinstance(record.get("destination"), str):
        raw = record["destination"]
    values = [raw] if isinstance(raw, str) else raw if isinstance(raw, list) else []
    return {destination for value in values if (destination := _normalize_document_destination(value))}


def _record_keys(record: Mapping[str, Any]) -> set[str]:
    return {
        str(record[key]).strip()
        for key in ("source_id", "canonical", "source")
        if isinstance(record.get(key), str) and str(record[key]).strip()
    }


def _revocation_state(root: Path, document_paths: set[str]) -> dict[str, Any]:
    registry, registry_file = _state_json(root, ".docops/source-registry.json")
    revocations, revocations_file = _state_json(root, ".docops/revocations.json")
    rag_sources, rag_sources_file = _state_json(root, "rag/sources.json")
    learning_tombstones, learning_tombstones_file = _state_json(root, ".docops/learning/tombstones.json")
    source_links: dict[str, set[str]] = {}
    if rag_sources is not None:
        records = rag_sources.get("sources")
        if not isinstance(records, list):
            raise RagSnapshotError("rag_snapshot_revocation_invalid", "rag/sources.json sources must be a list")
        for record in records:
            if not isinstance(record, Mapping):
                raise RagSnapshotError("rag_snapshot_revocation_invalid", "RAG source entry must be an object")
            destinations = _record_destinations(record)
            for destination in destinations:
                source_links.setdefault(destination, set()).update(_record_keys(record))

    blocked: set[str] = set()

    def add_record(record: Any, *, active: bool) -> None:
        if not isinstance(record, Mapping):
            raise RagSnapshotError("rag_snapshot_revocation_invalid", "revocation entry must be an object")
        if not active:
            return
        blocked.update(_record_destinations(record) & document_paths)
        keys = _record_keys(record)
        if keys:
            for destination, linked_keys in source_links.items():
                if keys & linked_keys and destination in document_paths:
                    blocked.add(destination)

    if registry is not None:
        records = registry.get("registrations")
        if not isinstance(records, list):
            raise RagSnapshotError("rag_snapshot_revocation_invalid", "source registry registrations must be a list")
        for record in records:
            add_record(record, active=isinstance(record, Mapping) and record.get("status") in {"withdrawn", "revoked"})
    if revocations is not None:
        records = revocations.get("sources")
        if not isinstance(records, list):
            raise RagSnapshotError("rag_snapshot_revocation_invalid", "revocation sources must be a list")
        for record in records:
            add_record(record, active=not (isinstance(record, Mapping) and record.get("revoked") is False))
    if rag_sources is not None:
        for record in rag_sources["sources"]:
            add_record(record, active=isinstance(record, Mapping) and record.get("revoked") is True)

    if learning_tombstones is not None:
        records = learning_tombstones.get("tombstones")
        if not isinstance(records, list):
            raise RagSnapshotError(
                "rag_snapshot_revocation_invalid",
                ".docops/learning/tombstones.json tombstones must be a list",
            )
        for record in records:
            if not isinstance(record, Mapping):
                raise RagSnapshotError(
                    "rag_snapshot_revocation_invalid",
                    "learning tombstone entry must be an object",
                )
            raw_path = record.get("path")
            if not isinstance(raw_path, str) or not raw_path.strip():
                raise RagSnapshotError(
                    "rag_snapshot_revocation_invalid",
                    "learning tombstone path is required",
                )
            destination = _normalize_document_destination(raw_path)
            if destination is None:
                raise RagSnapshotError(
                    "rag_snapshot_revocation_invalid",
                    "learning tombstone path is unsafe",
                )
            if destination in document_paths:
                blocked.add(destination)

    state_files = [registry_file, revocations_file, rag_sources_file, learning_tombstones_file]
    state_entries = [
        (entry["path"], {key: value for key, value in entry.items() if key != "path"}) for entry in state_files
    ]
    return {
        "content_hash": content_hash(state_entries),
        "files": state_files,
        "blocked_documents": sorted(blocked),
    }


def _snapshot_package_id(root: Path) -> str:
    manifest = root / "manifest.json"
    if manifest.is_file() and not manifest.is_symlink():
        try:
            value = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            value = {}
        if isinstance(value, Mapping):
            for key in ("package_id", "run_id"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate
    return root.name


def _snapshot_documents(root: Path) -> tuple[dict[str, dict[str, int | str]], int]:
    documents_root = root / "rag" / "documents"
    if documents_root.is_symlink() or not documents_root.is_dir():
        raise RagSnapshotError("rag_snapshot_documents_missing", "rag/documents must be a regular directory")
    documents: dict[str, dict[str, int | str]] = {}
    total_bytes = 0
    try:
        paths = sorted(documents_root.rglob("*"))
    except OSError as exc:
        raise RagSnapshotError("rag_snapshot_read_failed", "could not enumerate rag/documents") from exc
    for path in paths:
        if path.is_dir():
            if path.is_symlink():
                raise RagSnapshotError("rag_snapshot_symlink", "snapshot cannot include symbolic-link directories")
            continue
        if path.is_symlink() or not path.is_file():
            raise RagSnapshotError("rag_snapshot_symlink", "snapshot cannot include symbolic-link documents")
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise RagSnapshotError("rag_snapshot_read_failed", "could not read a package document") from exc
        relative = path.relative_to(documents_root).as_posix()
        documents[relative] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
        }
        total_bytes += len(data)
    return documents, total_bytes


def _snapshot_tree(root: Path, relative_root: str) -> dict[str, Any]:
    candidate = root / relative_root
    if not candidate.exists():
        return {
            "root": relative_root,
            "present": False,
            "files": {},
            "file_count": 0,
            "total_bytes": 0,
            "content_hash": content_hash([]),
        }
    if candidate.is_symlink() or not candidate.is_dir():
        raise RagSnapshotError("rag_snapshot_backend_invalid", f"{relative_root} must be a regular directory")
    files: dict[str, dict[str, int | str]] = {}
    try:
        paths = sorted(candidate.rglob("*"))
    except OSError as exc:
        raise RagSnapshotError("rag_snapshot_backend_read_failed", f"could not enumerate {relative_root}") from exc
    total_bytes = 0
    for path in paths:
        if path.is_dir():
            if path.is_symlink():
                raise RagSnapshotError(
                    "rag_snapshot_backend_symlink", "backend snapshot cannot include symlink directories"
                )
            continue
        if path.is_symlink() or not path.is_file():
            raise RagSnapshotError("rag_snapshot_backend_symlink", "backend snapshot cannot include symlink files")
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise RagSnapshotError("rag_snapshot_backend_read_failed", f"could not read {relative_root}") from exc
        relative = path.relative_to(candidate).as_posix()
        files[relative] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
        }
        total_bytes += len(data)
    entries = [(path, value["sha256"]) for path, value in sorted(files.items())]
    return {
        "root": relative_root,
        "present": True,
        "files": files,
        "file_count": len(files),
        "total_bytes": total_bytes,
        "content_hash": content_hash(entries),
    }


def _snapshot_index(root: Path) -> dict[str, Any]:
    path = root / "rag" / "index.json"
    if not path.exists():
        return {"present": False, "sha256": None, "size": 0}
    if path.is_symlink() or not path.is_file():
        raise RagSnapshotError("rag_snapshot_backend_invalid", "rag/index.json must be a regular file")
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise RagSnapshotError("rag_snapshot_backend_read_failed", "could not read rag/index.json") from exc
    return {
        "present": True,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
    }


def _snapshot_contract(payload: Mapping[str, Any]) -> None:
    contract = validate_artifact("rag-snapshot", dict(payload))
    if not contract.ok:
        details = "; ".join(error["message"] for error in contract.errors)
        raise RagSnapshotError("rag_snapshot_invalid", details)


def build_rag_snapshot(
    package_root: Path | str,
    *,
    backend: str = "knowledge-rag",
    supports_incremental: bool = False,
    server_version: str | None = None,
) -> dict[str, Any]:
    """Build a relocatable, content-addressed snapshot without mutating a package."""

    root = Path(package_root).expanduser().resolve()
    if root.is_symlink() or not root.is_dir():
        raise RagSnapshotError("rag_snapshot_package_invalid", "snapshot package must be a regular directory")
    config_path = root / "config.yaml"
    if config_path.is_symlink() or not config_path.is_file():
        raise RagSnapshotError("rag_snapshot_config_missing", "snapshot requires a regular package config.yaml")
    try:
        embedding = embedding_configuration(root)
        documents, total_bytes = _snapshot_documents(root)
        backend_snapshot = {
            "index": _snapshot_index(root),
            "data": _snapshot_tree(root, "rag/data"),
        }
        configuration = _configuration_identity(root)
        artifacts = _artifact_inventory(root, backend_snapshot)
        revocation = _revocation_state(root, set(documents))
    except RagSnapshotError:
        raise
    except (OSError, UnicodeError, ValueError) as exc:
        raise RagSnapshotError("rag_snapshot_config_invalid", "snapshot embedding configuration is unreadable") from exc
    if revocation["blocked_documents"]:
        raise RagSnapshotError(
            "rag_snapshot_revoked",
            "snapshot depends on revoked source documents",
        )
    revisions = package_revisions(root)
    model = _model_identity(embedding)
    payload: dict[str, Any] = {
        "schema_version": RAG_SNAPSHOT_SCHEMA_VERSION,
        "package_id": _snapshot_package_id(root),
        "release": {
            "release_id": revisions["release_id"],
            "composition_hash": revisions["composition_hash"],
            "corpus_revision": revisions["corpus_revision"],
            "index_revision": revisions["index_revision"],
        },
        "documents_root": "rag/documents",
        "documents": documents,
        "document_count": len(documents),
        "total_bytes": total_bytes,
        "corpus_hash": content_hash([(path, value["sha256"]) for path, value in sorted(documents.items())]),
        "embedding": {
            "profile": embedding.get("profile"),
            "embedding_fingerprint": embedding.get("embedding_fingerprint"),
            "configured": embedding.get("configured"),
            "effective": embedding.get("effective"),
        },
        "model": model,
        "configuration": configuration,
        "artifacts": artifacts,
        "backend": {
            "name": backend,
            "supports_incremental": bool(supports_incremental),
            "version": server_version,
        },
        "backend_snapshot": backend_snapshot,
        "revocation": revocation,
    }
    payload["snapshot_id"] = content_hash(payload)
    _snapshot_contract(payload)
    return payload


def _snapshot_id_matches(value: Mapping[str, Any]) -> bool:
    snapshot_id = value.get("snapshot_id")
    if not isinstance(snapshot_id, str) or not snapshot_id:
        return False
    identity_payload = {key: item for key, item in value.items() if key != "snapshot_id"}
    return snapshot_id == content_hash(identity_payload)


def _coerce_snapshot(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise RagSnapshotError("rag_snapshot_invalid", "snapshot must be an object")
    payload = dict(value)
    _snapshot_contract(payload)
    if not _snapshot_id_matches(payload):
        raise RagSnapshotError("rag_snapshot_identity_invalid", "snapshot identity does not match its contents")
    return payload


def _read_snapshot(path: Path | str) -> dict[str, Any]:
    candidate = Path(path).expanduser().resolve()
    if candidate.is_symlink() or not candidate.is_file():
        raise RagSnapshotError("rag_snapshot_missing", "previous snapshot must be a regular file")
    try:
        value = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RagSnapshotError("rag_snapshot_invalid", "previous snapshot is not valid JSON") from exc
    if not isinstance(value, Mapping):
        raise RagSnapshotError("rag_snapshot_invalid", "previous snapshot must be an object")
    return _coerce_snapshot(value)


def read_rag_snapshot(snapshot: Path | str | Mapping[str, Any]) -> dict[str, Any]:
    """Read and verify one relocatable snapshot from a path or JSON object."""

    if isinstance(snapshot, Mapping):
        return _coerce_snapshot(snapshot)
    return _read_snapshot(snapshot)


def rag_snapshot_identity(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Return the compact pinning identity exposed by reader sessions."""

    payload = _coerce_snapshot(snapshot)
    release = payload["release"]
    embedding = payload["embedding"]
    model = payload["model"]
    configuration = payload["configuration"]
    artifacts = payload["artifacts"]
    revocation = payload["revocation"]
    return {
        "snapshot_id": payload["snapshot_id"],
        "release_id": release["release_id"],
        "composition_hash": release["composition_hash"],
        "corpus_hash": payload["corpus_hash"],
        "profile": embedding["profile"],
        "embedding_fingerprint": embedding["embedding_fingerprint"],
        "model": {
            "name": model.get("name"),
            "revision": model.get("revision"),
        },
        "configuration_hash": configuration["content_hash"],
        "artifacts_hash": artifacts["content_hash"],
        "revocation_hash": revocation["content_hash"],
    }


def validate_rag_snapshot(
    package_root: Path | str,
    snapshot: Mapping[str, Any],
    *,
    generation_root: Path | str | None = None,
) -> dict[str, Any]:
    """Refuse a snapshot when its release, corpus, model or artifacts drift."""

    active_root = Path(package_root).expanduser().resolve()
    target_root = Path(generation_root or package_root).expanduser().resolve()
    payload = _coerce_snapshot(snapshot)
    backend = payload["backend"]
    current = build_rag_snapshot(
        target_root,
        backend=str(backend["name"]),
        supports_incremental=bool(backend["supports_incremental"]),
        server_version=backend.get("version"),
    )
    if current["snapshot_id"] != payload["snapshot_id"]:
        raise RagSnapshotError(
            "rag_snapshot_incompatible",
            "package content is incompatible with the pinned snapshot",
        )
    active_revocation = _revocation_state(active_root, set(payload["documents"]))
    if active_revocation["content_hash"] != payload["revocation"]["content_hash"]:
        raise RagSnapshotError(
            "rag_snapshot_revoked",
            "revocation state changed after the snapshot was created",
        )
    return payload


def _snapshot_docs(value: Mapping[str, Any]) -> Mapping[str, Any]:
    documents = value.get("documents")
    if not isinstance(documents, Mapping):
        raise RagSnapshotError("rag_snapshot_invalid", "snapshot documents must be an object")
    return documents


def _backend_snapshot_identity(value: Mapping[str, Any]) -> tuple[Any, Any]:
    backend_snapshot = value.get("backend_snapshot")
    if not isinstance(backend_snapshot, Mapping):
        return (None, None)
    index = backend_snapshot.get("index")
    data = backend_snapshot.get("data")
    index_hash = index.get("sha256") if isinstance(index, Mapping) else None
    data_hash = data.get("content_hash") if isinstance(data, Mapping) else None
    return index_hash, data_hash


def plan_rag_reuse(
    current: Mapping[str, Any],
    previous: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Plan safe document reuse; this function never writes or promotes an index."""

    current = _coerce_snapshot(current)
    current_docs = _snapshot_docs(current)
    current_backend = current.get("backend")
    if not isinstance(current_backend, Mapping):
        raise RagSnapshotError("rag_snapshot_invalid", "snapshot backend must be an object")
    current_embedding = current.get("embedding")
    if not isinstance(current_embedding, Mapping):
        raise RagSnapshotError("rag_snapshot_invalid", "snapshot embedding must be an object")

    changed_paths = sorted(str(path) for path in current_docs)
    removed_paths: list[str] = []
    unchanged_paths: list[str] = []
    reason = "no_previous_snapshot"
    mode = "full_rebuild"
    previous_docs: Mapping[str, Any] = {}
    if previous is not None:
        previous = _coerce_snapshot(previous)
        previous_docs = _snapshot_docs(previous)
        changed_paths = []
        removed_paths = sorted(str(path) for path in previous_docs if path not in current_docs)
        for path in sorted(str(path) for path in current_docs):
            previous_entry = previous_docs.get(path)
            current_entry = current_docs.get(path)
            if (
                isinstance(previous_entry, Mapping)
                and isinstance(current_entry, Mapping)
                and previous_entry.get("sha256") == current_entry.get("sha256")
            ):
                unchanged_paths.append(path)
            else:
                changed_paths.append(path)
        reason = "incremental_reuse"
        previous_embedding = previous.get("embedding")
        if not isinstance(previous_embedding, Mapping) or (
            previous_embedding.get("embedding_fingerprint") != current_embedding.get("embedding_fingerprint")
            or previous_embedding.get("profile") != current_embedding.get("profile")
        ):
            reason = "embedding_changed"
        elif previous.get("model") != current.get("model"):
            reason = "model_changed"
        elif previous.get("configuration") != current.get("configuration"):
            reason = "configuration_changed"
        elif previous.get("artifacts") != current.get("artifacts"):
            reason = "artifacts_changed"
        elif previous.get("revocation") != current.get("revocation"):
            reason = "revocation_changed"
        elif _backend_snapshot_identity(previous) != _backend_snapshot_identity(current):
            reason = "backend_snapshot_changed"
        elif previous.get("backend", {}).get("name") != current_backend.get("name"):
            reason = "backend_changed"
        elif previous.get("backend", {}).get("version") != current_backend.get("version"):
            reason = "backend_version_changed"
        elif not bool(current_backend.get("supports_incremental")):
            reason = "backend_incremental_unsupported"
        else:
            mode = "incremental"

    reused_count = len(unchanged_paths) if mode == "incremental" else 0
    plan = {
        "schema_version": 1,
        "ok": True,
        "snapshot_id": current["snapshot_id"],
        "mode": mode,
        "reason": reason,
        "reused_count": reused_count,
        "changed_count": len(changed_paths),
        "removed_count": len(removed_paths),
        "changed_paths": changed_paths,
        "removed_paths": removed_paths,
        "logical_stats": {
            "current_documents": len(current_docs),
            "previous_documents": len(previous_docs),
            "reused_documents": reused_count,
            "current_bytes": int(current.get("total_bytes", 0)),
        },
        "active_preserved": True,
        "publication_allowed": False,
    }
    contract = validate_artifact("rag-reuse-plan", plan)
    if not contract.ok:
        details = "; ".join(error["message"] for error in contract.errors)
        raise RagSnapshotError("rag_reuse_plan_invalid", details)
    return plan


def snapshot_rag_package(
    package_root: Path | str,
    *,
    previous: Path | str | None = None,
    snapshot_out: Path | str | None = None,
    backend: str = "knowledge-rag",
    supports_incremental: bool = False,
    server_version: str | None = None,
    verify_query: str | None = None,
    verify_adapter: str = "memory",
    runtime_root: Path | str | None = None,
) -> dict[str, Any]:
    """Return a snapshot and reuse plan while leaving the active package untouched."""

    current = build_rag_snapshot(
        package_root,
        backend=backend,
        supports_incremental=supports_incremental,
        server_version=server_version,
    )
    previous_snapshot = _read_snapshot(previous) if previous is not None else None
    plan = plan_rag_reuse(current, previous_snapshot)
    verification: dict[str, Any] | None = None
    if verify_query is not None:
        if not verify_query.strip():
            raise RagSnapshotError("rag_snapshot_query_invalid", "verification query must be non-empty")
        try:
            retrieval = adapter_for_package(package_root, verify_adapter, runtime_root=runtime_root)
            try:
                results = retrieval.search(verify_query, max_results=5)
                verification = {
                    "ok": True,
                    "query": verify_query,
                    "adapter": verify_adapter,
                    "result_count": len(results),
                    "top_sources": [str(item.get("source", "")) for item in results],
                    "metadata": retrieval.metadata(),
                }
            finally:
                retrieval.close()
        except RetrievalError as exc:
            raise RagSnapshotError(exc.code, str(exc)) from exc
    if snapshot_out is not None:
        write_json_atomic(Path(snapshot_out), current)
    report = {
        "schema_version": 1,
        "ok": True,
        "snapshot": current,
        "plan": plan,
        "active_preserved": True,
        "error": None,
    }
    if verification is not None:
        report["verification"] = verification
    return report


def _validate_reindex_start(payload: Mapping[str, Any], expected_operation: str) -> None:
    status = str(payload.get("status") or "").casefold()
    if status == "error":
        raise RagSyncError("rag_reindex_start_failed", "reindex_documents returned a terminal error")
    if status not in {"started", "already_running"}:
        raise RagSyncError("rag_reindex_invalid_start", "reindex_documents returned an invalid status")
    operation = payload.get("operation")
    progress = payload.get("progress")
    if not isinstance(operation, str) and isinstance(progress, Mapping):
        operation = progress.get("operation")
    if status == "already_running" and operation != expected_operation:
        raise RagSyncError(
            "rag_reindex_already_running_wrong_operation",
            "an already-running reindex could not be matched to the requested operation",
        )
    if status == "started" and operation is not None and operation != expected_operation:
        raise RagSyncError("rag_reindex_operation_mismatch", "reindex operation did not match the request")


def _validate_reindex_terminal(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    state_value = payload.get("reindex") if isinstance(payload.get("reindex"), Mapping) else payload
    if not isinstance(state_value, Mapping) or not isinstance(state_value.get("active"), bool):
        raise RagSyncError("rag_reindex_invalid_status", "get_reindex_status returned an invalid state")
    if state_value["active"]:
        return state_value

    if state_value.get("last_error") is not None or state_value.get("error") is not None:
        raise RagSyncError("rag_reindex_terminal_error", "reindex completed with an error")

    last_result = state_value.get("last_result")
    if last_result is not None:
        if not isinstance(last_result, Mapping):
            raise RagSyncError("rag_reindex_invalid_result", "reindex completion result was not an object")
        result_status = str(last_result.get("status") or "").casefold()
        if result_status in {"error", "failed", "failure"}:
            raise RagSyncError("rag_reindex_terminal_error", "reindex completion result reported failure")
        errors = last_result.get("errors", 0)
    else:
        errors = state_value.get("errors", 0)
    if isinstance(errors, bool) or not isinstance(errors, int):
        raise RagSyncError("rag_reindex_invalid_result", "reindex error count was not an integer")
    if errors > 0:
        raise RagSyncError("rag_reindex_partial_failure", "reindex completed with document errors")
    if last_result is None and "errors" not in state_value:
        raise RagSyncError("rag_reindex_incomplete", "reindex ended without completion evidence")
    return state_value


def _validate_stats(payload: Mapping[str, Any], expected_documents: int) -> dict[str, Any]:
    stats_value = payload.get("stats") if isinstance(payload.get("stats"), Mapping) else payload
    if not isinstance(stats_value, Mapping):
        raise RagSyncError("rag_stats_invalid_payload", "get_index_stats returned an invalid payload")
    result = dict(stats_value)
    status = str(result.get("status") or "").casefold()
    if status in {"error", "failed", "failure"}:
        raise RagSyncError("rag_stats_failed", "get_index_stats returned a terminal error")
    total_documents = result.get("total_documents")
    total_chunks = result.get("total_chunks")
    if (
        isinstance(total_documents, bool)
        or not isinstance(total_documents, int)
        or isinstance(total_chunks, bool)
        or not isinstance(total_chunks, int)
    ):
        raise RagSyncError("rag_stats_invalid_payload", "index totals were not integers")
    if expected_documents > 0 and (total_documents <= 0 or total_chunks <= 0):
        raise RagSyncError("rag_empty_backend", "index stats do not prove a non-empty indexed corpus")
    if total_documents < expected_documents:
        raise RagSyncError("rag_stats_mismatch", "index stats contain fewer documents than the package")
    return result


def _validate_smoke_results(results: Any) -> None:
    if not isinstance(results, list):
        raise RagSyncError("rag_smoke_invalid_payload", "search_knowledge did not return a results list")
    for result in results:
        if not isinstance(result, Mapping):
            raise RagSyncError("rag_smoke_invalid_result", "search_knowledge returned a non-object result")
        source = str(result.get("source") or result.get("path") or "").strip()
        if not source:
            raise RagSyncError("rag_smoke_invalid_result", "search_knowledge returned a result without a source")
        locators = result.get("locators")
        citations = result.get("citations")
        if locators is not None and not isinstance(locators, list):
            raise RagSyncError("rag_smoke_citation_invalid", "result locators were not an array")
        if citations is not None and not isinstance(citations, list):
            raise RagSyncError("rag_smoke_citation_invalid", "result citations were not an array")
        if (isinstance(locators, list) and locators) or "citations" in result:
            valid_citations = [
                citation
                for citation in citations or []
                if isinstance(citation, str)
                and citation.strip()
                and (citation.startswith(f"{source}#") or citation.startswith(f"{source}:"))
            ]
            if not valid_citations:
                raise RagSyncError("rag_smoke_citation_invalid", "result locators have no valid source citation")


def package_rag_config() -> dict[str, Any]:
    """Return a package-local, stdio-only knowledge-rag configuration."""

    return {
        "paths": {
            "documents_dir": "./rag/documents",
            "data_dir": "./rag/data",
            "models_cache_dir": "~/.cache/docops/models",
        },
        "documents": {
            "supported_formats": [
                ".md",
                ".markdown",
                ".txt",
                ".rst",
                ".adoc",
                ".html",
                ".htm",
                ".json",
                ".yaml",
                ".yml",
                ".xml",
                ".csv",
                ".py",
                ".c",
                ".h",
                ".cpp",
                ".js",
                ".jsx",
                ".ts",
                ".tsx",
                ".ipynb",
                ".xlsx",
                ".pptx",
                ".pdf",
                ".docx",
            ],
            "exclude_patterns": ["data", "models_cache", ".venv", ".git"],
            "chunking": {"chunk_size": 1000, "chunk_overlap": 200},
        },
        "models": {"embedding": {"profile": "compact", "gpu": False}, "reranker": {"enabled": False}},
        "search": {"default_results": 5, "max_results": 100, "collection_name": "knowledge_base"},
        "category_mappings": {},
        "keyword_routes": {},
        "query_expansions": {},
        "server": {
            "transport": "stdio",
            "host": "127.0.0.1",
            "port": 8179,
            "auth": {"bearer_token": ""},
            "rate_limit": {"enabled": False, "requests_per_minute": 60, "burst": 10},
            "metrics": {"enabled": False, "port": 9179},
            "logging": {"format": "text", "level": "INFO"},
        },
    }


def _yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if not text or any(character in text for character in ":#{}[]&,*!|>'\"%@`\n") or text.strip() != text:
        return json.dumps(text, ensure_ascii=False)
    return text


def _render_yaml(value: Any, indent: int = 0) -> list[str]:
    lines: list[str] = []
    prefix = " " * indent
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.extend(_render_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {_yaml_scalar(item)}")
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(_render_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}- {_yaml_scalar(item)}")
    return lines


def package_rag_config_text() -> str:
    """Render the portable stdio configuration shipped with each package."""

    return "\n".join(_render_yaml(package_rag_config())) + "\n"


@dataclass
class RagSyncResult:
    ok: bool
    stats: dict[str, Any] = field(default_factory=dict)
    reindex: dict[str, Any] = field(default_factory=dict)
    smoke: dict[str, Any] = field(default_factory=dict)
    configuration: dict[str, Any] = field(default_factory=dict)
    error: dict[str, str] | None = None
    provenance: dict[str, Any] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return redact_report(
            {
                "ok": self.ok,
                "stats": self.stats,
                "reindex": self.reindex,
                "smoke": self.smoke,
                "configuration": self.configuration,
                "error": self.error,
                "provenance": self.provenance,
                "diagnostics": self.diagnostics,
            }
        )


class RagSynchronizer:
    """Run the real knowledge-rag MCP reindex only when explicitly requested."""

    def __init__(
        self,
        *,
        python: Path | str | None = None,
        runtime_root: Path | str | None = None,
        timeout_seconds: float = 1800.0,
    ) -> None:
        self.python = Path(python) if python else None
        self.runtime_root = Path(runtime_root).resolve() if runtime_root else None
        self.timeout_seconds = timeout_seconds

    def sync(self, package_root: Path | str, *, full_rebuild: bool = False) -> RagSyncResult:
        root = Path(package_root).resolve()
        config_path = root / "config.yaml"
        if config_path.is_symlink():
            return RagSyncResult(
                False, error={"code": "unsafe_rag_config", "message": "package config.yaml must not be a symbolic link"}
            )
        if not config_path.exists():
            write_text_atomic(config_path, package_rag_config_text())
        config_audit = audit_config_file(config_path)
        if not config_audit.ok:
            return RagSyncResult(
                False,
                error={
                    "code": "unsafe_rag_config",
                    "message": "; ".join(error["message"] for error in config_audit.errors),
                },
            )
        try:
            configured_embedding = embedding_configuration(root)
        except (OSError, UnicodeError, ValueError) as exc:
            return RagSyncResult(
                False,
                error={"code": "rag_config_read_failed", "message": "knowledge-rag configuration could not be read"},
                diagnostics={"detail": str(exc)},
            )
        expected_documents = _document_count(root)
        if expected_documents == 0:
            return RagSyncResult(
                False,
                configuration=configured_embedding,
                error={"code": "rag_empty_corpus", "message": "indexing requires at least one package document"},
            )
        runtime_root = self.runtime_root or root
        executable = self.python or discover_rag_python(runtime_root).path
        if not executable.is_file():
            return RagSyncResult(
                False, error={"code": "rag_python_missing", "message": "knowledge-rag Python executable is unavailable"}
            )
        client = None
        reviewed_vendor = self.runtime_root / "skills" / "vendor" / "knowledge-rag" if self.runtime_root else None
        runtime_env = runtime_environment(root, vendor_root=reviewed_vendor, read_only=False)
        expected_provenance = runtime_provenance(
            runtime_root,
            python=executable,
            environ=runtime_env,
        )
        try:
            client = start_mcp_server(executable, root, env=runtime_env)
            server_info = getattr(client, "server_info", {})
            actual_version = server_info.get("version") if isinstance(server_info, dict) else None
            expected_version = expected_provenance.get("expected_version")
            if expected_version and actual_version != expected_version:
                return RagSyncResult(
                    False,
                    configuration={**configured_embedding, "backend_version": actual_version},
                    error={
                        "code": "rag_version_mismatch",
                        "message": "knowledge-rag server version does not match the selected runtime",
                    },
                    provenance={**expected_provenance, "server_version": actual_version},
                    diagnostics=client.diagnostics(status="failed") if hasattr(client, "diagnostics") else {},
                )
            arguments = {"full_rebuild": True} if full_rebuild else {"force": True}
            response = client.call(
                "tools/call", name="reindex_documents", arguments=arguments, timeout=self.timeout_seconds
            )
            reindex = _response_payload(response, "reindex_documents")
            expected_operation = "nuclear_rebuild" if full_rebuild else "smart_reindex"
            _validate_reindex_start(reindex, expected_operation)
            reindex_request = {
                "requested_operation": expected_operation,
                "full_rebuild": full_rebuild,
            }
            deadline = time.monotonic() + self.timeout_seconds
            while time.monotonic() < deadline:
                status_response = client.call("tools/call", name="get_reindex_status", arguments={}, timeout=120)
                status = _response_payload(status_response, "get_reindex_status")
                state = _validate_reindex_terminal(status)
                if not state["active"]:
                    reindex = {**dict(state), **reindex_request}
                    break
                time.sleep(1)
            else:
                return RagSyncResult(
                    False,
                    reindex={**reindex, **reindex_request},
                    configuration=configured_embedding,
                    error={"code": "rag_timeout", "message": "reindex timeout"},
                )
            stats_response = client.call("tools/call", name="get_index_stats", arguments={}, timeout=120)
            stats = _validate_stats(_response_payload(stats_response, "get_index_stats"), expected_documents)
            configuration = embedding_configuration(root, stats=stats, server_version=actual_version)
            smoke_response = client.call(
                "tools/call",
                name="search_knowledge",
                arguments={"query": "documentation", "max_results": 1},
                timeout=120,
            )
            smoke = _response_payload(smoke_response, "search_knowledge")
            results = smoke.get("results")
            if not results:
                raise RagSyncError("rag_smoke_empty", "search_knowledge returned no known-document result")
            _validate_smoke_results(results)
            return RagSyncResult(
                True,
                stats=stats,
                reindex=reindex,
                smoke={"ok": True, "query": "documentation", "result_count": len(results)},
                configuration=configuration,
                provenance={**expected_provenance, "server_version": actual_version},
                diagnostics=client.diagnostics(status="completed") if hasattr(client, "diagnostics") else {},
            )
        except (OSError, RuntimeError, TimeoutError) as exc:
            code = str(getattr(exc, "code", "rag_integration_failed"))
            diagnostics = (
                client.diagnostics(status="failed") if client is not None and hasattr(client, "diagnostics") else {}
            )
            return RagSyncResult(
                False,
                reindex=locals().get("reindex", {}),
                configuration=locals().get("configured_embedding", {}),
                error={"code": code, "message": "knowledge-rag integration failed"},
                diagnostics=diagnostics,
            )
        finally:
            if client is not None:
                try:
                    client.close()
                except OSError:
                    pass
