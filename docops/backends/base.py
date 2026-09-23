"""Small, provider-neutral contract for Farol knowledge backends."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


def _copy(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))


class BackendError(RuntimeError):
    """Typed failure at the backend boundary without vendor payloads."""

    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        self.code = code
        self.details = {str(key): _copy(value) for key, value in (details or {}).items()}
        super().__init__(message)


class BackendUnavailable(BackendError):
    """The configured backend cannot service the requested operation."""


@dataclass(frozen=True)
class ProbeResult:
    backend: str
    status: str
    version: str | None = None
    capabilities: tuple[str, ...] = ()
    health: Mapping[str, Any] = field(default_factory=dict)
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _copy(
            {
                "backend": self.backend,
                "status": self.status,
                "version": self.version,
                "capabilities": list(self.capabilities),
                "health": dict(self.health),
                "diagnostics": dict(self.diagnostics),
            }
        )


@dataclass(frozen=True)
class BackendCandidate:
    candidate_id: str
    project_revision: str
    ir_revision: str
    backend: str
    state: str = "preparing"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _copy(
            {
                "schema_version": 2,
                "kind": "backend_candidate",
                "candidate_id": self.candidate_id,
                "project_revision": self.project_revision,
                "ir_revision": self.ir_revision,
                "backend": self.backend,
                "state": self.state,
                "metadata": dict(self.metadata),
            }
        )


@dataclass(frozen=True)
class QueryRequest:
    query: str
    top_k: int = 5
    project_revision: str | None = None
    filters: Mapping[str, Any] = field(default_factory=dict)
    as_of: str | None = None
    region: str | None = None

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError("query must not be empty")
        if self.top_k < 1:
            raise ValueError("top_k must be positive")

    def to_dict(self) -> dict[str, Any]:
        return _copy(
            {
                "schema_version": 2,
                "kind": "query_request",
                "query": self.query,
                "top_k": self.top_k,
                "project_revision": self.project_revision,
                "filters": dict(self.filters),
                "as_of": self.as_of,
                "region": self.region,
            }
        )


@dataclass(frozen=True)
class IndexRevision:
    index_revision: str
    project_revision: str
    ir_revision: str
    backend: str
    backend_version: str | None
    state: str
    mapping_hash: str
    external_ids: Mapping[str, str] = field(default_factory=dict)
    fingerprints: Mapping[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _copy(
            {
                "schema_version": 2,
                "kind": "index_revision",
                "index_revision": self.index_revision,
                "project_revision": self.project_revision,
                "ir_revision": self.ir_revision,
                "backend": self.backend,
                "backend_version": self.backend_version,
                "state": self.state,
                "mapping_hash": self.mapping_hash,
                "external_ids": dict(self.external_ids),
                "fingerprints": dict(self.fingerprints),
            }
        )


@dataclass(frozen=True)
class EvidenceResult:
    index_revision: str
    query: QueryRequest
    hits: list[dict[str, Any]]
    outcome: str = "ok"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _copy(
            {
                "schema_version": 2,
                "kind": "evidence_result",
                "index_revision": self.index_revision,
                "query": self.query.to_dict(),
                "hits": self.hits,
                "outcome": self.outcome,
                "metadata": dict(self.metadata),
            }
        )


@dataclass(frozen=True)
class SnapshotIdentity:
    snapshot_id: str
    index_revision: str
    content_hash: str

    def to_dict(self) -> dict[str, str]:
        return {
            "snapshot_id": self.snapshot_id,
            "index_revision": self.index_revision,
            "content_hash": self.content_hash,
        }


@dataclass(frozen=True)
class BackendReceipt:
    status: str
    operation: str
    candidate_id: str | None = None
    index_revision: str | None = None
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _copy(
            {
                "status": self.status,
                "operation": self.operation,
                "candidate_id": self.candidate_id,
                "index_revision": self.index_revision,
                "message": self.message,
            }
        )


class KnowledgeBackend(Protocol):
    """The only backend surface known by composition and reader modules."""

    def probe(self, config: Mapping[str, Any] | None = None) -> ProbeResult: ...

    def prepare(self, project_revision: str, ir_revision: str) -> BackendCandidate: ...

    def apply(self, candidate: BackendCandidate) -> IndexRevision: ...

    def query(self, index_revision: IndexRevision, query_request: QueryRequest) -> EvidenceResult: ...

    def snapshot(self, index_revision: IndexRevision) -> SnapshotIdentity: ...

    def discard(self, candidate: BackendCandidate) -> BackendReceipt: ...

    def close(self) -> BackendReceipt: ...
