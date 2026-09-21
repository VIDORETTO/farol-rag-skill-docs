"""Knowledge backend seams and adapters."""

from .base import (
    BackendCandidate,
    BackendError,
    BackendReceipt,
    BackendUnavailable,
    EvidenceResult,
    IndexRevision,
    KnowledgeBackend,
    ProbeResult,
    QueryRequest,
    SnapshotIdentity,
)
from .ragflow import RagFlowAdapter

__all__ = [
    "BackendCandidate",
    "BackendError",
    "BackendReceipt",
    "BackendUnavailable",
    "EvidenceResult",
    "IndexRevision",
    "KnowledgeBackend",
    "ProbeResult",
    "QueryRequest",
    "RagFlowAdapter",
    "SnapshotIdentity",
]
