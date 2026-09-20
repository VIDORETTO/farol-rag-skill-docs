"""RAGFlow lifecycle adapter with fail-closed transport and injectable client."""

from __future__ import annotations

import json
import math
import os
import time
from typing import Any, Mapping, Protocol
from urllib.parse import urlsplit

from ..ir import BackendMapping
from ..revisions import content_hash
from .base import (
    BackendCandidate,
    BackendError,
    BackendReceipt,
    BackendUnavailable,
    EvidenceResult,
    IndexRevision,
    ProbeResult,
    QueryRequest,
    SnapshotIdentity,
)

MAX_RAGFLOW_CHUNK_PAGES = 4096
MIN_RAGFLOW_TIMEOUT_SECONDS = 0.1


class RagFlowClient(Protocol):
    def health(self) -> Mapping[str, Any]: ...


class _RagFlowSdkClient:
    """Normalize the pinned ``ragflow_sdk`` surface behind the backend seam.

    The SDK deliberately stays an optional integration dependency.  The rest
    of Farol only sees the small client protocol used by ``RagFlowAdapter``;
    SDK objects and opaque provider IDs never escape this wrapper.
    """

    def __init__(
        self,
        sdk: Any,
        *,
        version: str = "0.27.2",
        timeout_seconds: float = 30.0,
        max_chunk_pages: int = 256,
    ) -> None:
        self.sdk = sdk
        self.version = version
        self.timeout_seconds = _positive_finite_timeout(timeout_seconds)
        self.max_chunk_pages = _chunk_page_limit(max_chunk_pages)
        self._datasets: dict[str, Any] = {}
        self._documents: dict[tuple[str, str], Any] = {}

    def health(self) -> Mapping[str, Any]:
        # v0.27.2 has no dedicated health method.  A bounded dataset listing
        # proves authentication and API reachability without reading corpus.
        self.sdk.list_datasets(page=1, page_size=1)
        return {"ok": True, "version": self.version}

    def create_dataset(self, name: str) -> Mapping[str, Any]:
        dataset = self.sdk.create_dataset(name=name)
        dataset_id = _sdk_attr(dataset, "id")
        if not dataset_id:
            raise BackendError("dataset_invalid", "RAGFlow SDK returned a dataset without an id")
        self._datasets[str(dataset_id)] = dataset
        return {"id": str(dataset_id), "name": str(_sdk_attr(dataset, "name", name))}

    def upload_document(self, dataset_id: str, content: str, metadata: Mapping[str, Any]) -> Mapping[str, Any]:
        dataset = self._dataset(dataset_id)
        document_id = str(metadata.get("document_id") or "document")
        display_name = str(metadata.get("display_name") or f"{document_id}.txt")
        blob = content if isinstance(content, bytes) else str(content).encode("utf-8")
        documents = dataset.upload_documents([{"display_name": display_name, "blob": blob}])
        if not documents:
            raise BackendError("document_invalid", "RAGFlow SDK returned no uploaded document")
        document = documents[0]
        external_id = _sdk_attr(document, "id")
        if not external_id:
            raise BackendError("document_invalid", "RAGFlow SDK returned a document without an id")
        self._documents[(dataset_id, str(external_id))] = document
        return {"id": str(external_id), "name": str(_sdk_attr(document, "name", display_name))}

    def parse_document(self, dataset_id: str, document_id: str) -> Mapping[str, Any]:
        dataset = self._dataset(dataset_id)
        dataset.async_parse_documents([document_id])
        return {"status": "pending", "dataset_id": dataset_id, "document_id": document_id}

    def wait_for_parse(self, dataset_id: str, document_id: str, timeout_seconds: float) -> Mapping[str, Any]:
        dataset = self._dataset(dataset_id)
        requested_timeout = _positive_finite_timeout(timeout_seconds)
        deadline = time.monotonic() + min(requested_timeout, self.timeout_seconds)
        while True:
            if time.monotonic() >= deadline:
                raise BackendUnavailable("parse_timeout", "RAGFlow parsing did not finish before the deadline")
            documents = dataset.list_documents(id=document_id, page=1, page_size=1)
            document = documents[0] if documents else None
            status = str(_sdk_attr(document, "run", _sdk_attr(document, "status", ""))).casefold()
            if status in {"fail", "failed", "cancel", "cancelled", "canceled", "error"}:
                return {"status": "failed", "document_id": document_id}
            if (
                status in {"done", "success", "succeeded", "completed"}
                or float(_sdk_attr(document, "progress", 0.0) or 0.0) >= 1.0
            ):
                return {"status": "done", "document_id": document_id}
            if time.monotonic() >= deadline:
                raise BackendUnavailable("parse_timeout", "RAGFlow parsing did not finish before the deadline")
            time.sleep(min(1.0, max(deadline - time.monotonic(), 0.01)))

    def list_chunks(self, dataset_id: str, document_id: str) -> list[Mapping[str, Any]]:
        document = self._document(dataset_id, document_id)
        result: list[Mapping[str, Any]] = []
        # RAGFlow v0.27.2 validates this API at a hard maximum of 100.
        page_size = 100
        for page in range(1, self.max_chunk_pages + 1):
            chunks = document.list_chunks(page=page, page_size=page_size)
            for chunk in chunks if isinstance(chunks, list) else []:
                result.append(_sdk_chunk(chunk, document_id))
            if not isinstance(chunks, list) or len(chunks) < page_size:
                return result
        raise BackendUnavailable(
            "chunks_pagination_limit",
            "RAGFlow chunk pagination exceeded the configured page limit",
        )

    def search(self, dataset_id: str, query: str, top_k: int) -> list[Mapping[str, Any]]:
        chunks = self.sdk.retrieve(
            dataset_ids=[dataset_id],
            question=query,
            page_size=top_k,
            top_k=top_k,
        )
        return [_sdk_chunk(chunk, str(_sdk_attr(chunk, "document_id", ""))) for chunk in chunks or []]

    def get_document(self, dataset_id: str, document_id: str) -> Mapping[str, Any]:
        document = self._document(dataset_id, document_id)
        return {
            "id": document_id,
            "name": str(_sdk_attr(document, "name", "")),
            "status": str(_sdk_attr(document, "run", _sdk_attr(document, "status", ""))),
            "progress": _sdk_attr(document, "progress", None),
            "chunk_count": _sdk_attr(document, "chunk_count", None),
        }

    def dataset_stats(self, dataset_id: str) -> Mapping[str, Any]:
        dataset = self._dataset(dataset_id)
        return {
            "documents": int(_sdk_attr(dataset, "document_count", 0) or 0),
            "chunks": int(_sdk_attr(dataset, "chunk_count", 0) or 0),
        }

    def delete_dataset(self, dataset_id: str) -> None:
        self.sdk.delete_datasets(ids=[dataset_id])
        self._datasets.pop(dataset_id, None)
        for key in [key for key in self._documents if key[0] == dataset_id]:
            self._documents.pop(key, None)

    def close(self) -> None:
        # v0.27.2 owns requests at module level and has no close operation.
        return None

    def _dataset(self, dataset_id: str) -> Any:
        dataset = self._datasets.get(dataset_id)
        if dataset is None:
            datasets = self.sdk.list_datasets(id=dataset_id, page=1, page_size=1)
            if not datasets:
                raise BackendUnavailable("dataset_unknown", "RAGFlow dataset is not available")
            dataset = datasets[0]
            self._datasets[dataset_id] = dataset
        return dataset

    def _document(self, dataset_id: str, document_id: str) -> Any:
        document = self._documents.get((dataset_id, document_id))
        if document is None:
            dataset = self._dataset(dataset_id)
            documents = dataset.list_documents(id=document_id, page=1, page_size=1)
            if not documents:
                raise BackendUnavailable("document_unknown", "RAGFlow document is not available")
            document = documents[0]
            self._documents[(dataset_id, document_id)] = document
        return document


def _sdk_attr(value: Any, name: str, default: Any = "") -> Any:
    return getattr(value, name, default)


def _sdk_chunk(chunk: Any, document_id: str) -> dict[str, Any]:
    chunk_id = str(_sdk_attr(chunk, "id", ""))
    content = str(_sdk_attr(chunk, "content", ""))
    positions = _json_safe(_sdk_attr(chunk, "positions", []))
    return {
        "id": chunk_id,
        "content": content,
        "document_id": str(_sdk_attr(chunk, "document_id", document_id)),
        "score": _sdk_attr(chunk, "similarity", _sdk_attr(chunk, "score", 0.0)),
        "metadata": {"positions": positions, "document_id": str(_sdk_attr(chunk, "document_id", document_id))},
        "positions": positions,
    }


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False))
    except (TypeError, ValueError):
        return str(value)


class RagFlowAdapter:
    backend_name = "ragflow"
    expected_version = "0.27.2"

    def __init__(self, *, client: Any | None = None, config: Mapping[str, Any] | None = None) -> None:
        self.client = client
        self.config = dict(config or {})
        self._closed = False
        self._candidates: dict[str, BackendCandidate] = {}
        self._indexes: dict[str, dict[str, Any]] = {}
        self._candidate_indexes: dict[str, IndexRevision] = {}

    def probe(self, config: Mapping[str, Any] | None = None) -> ProbeResult:
        self._ensure_open()
        settings = {**self.config, **dict(config or {})}
        endpoint = str(settings.get("endpoint") or "")
        self._validate_endpoint(endpoint, settings)
        if self.client is None:
            token_ref = str(settings.get("token_env") or "DOCOPS_RAGFLOW_TOKEN")
            token = os.environ.get(token_ref)
            if not token:
                return ProbeResult(
                    self.backend_name,
                    "unavailable",
                    version=self.expected_version,
                    diagnostics={"reason": "token_missing", "endpoint": _safe_endpoint(endpoint)},
                )
            try:
                self.client = _build_sdk_client(endpoint, token, settings)
            except BackendUnavailable as exc:
                return ProbeResult(
                    self.backend_name,
                    "unavailable",
                    version=self.expected_version,
                    diagnostics={"reason": exc.code, "endpoint": _safe_endpoint(endpoint)},
                )
        try:
            health = self._call("health", default={})
        except BackendUnavailable as exc:
            return ProbeResult(
                self.backend_name,
                "unavailable",
                version=self.expected_version,
                diagnostics={"reason": exc.code, "endpoint": _safe_endpoint(endpoint)},
            )
        if not isinstance(health, Mapping) or health.get("ok") is False:
            return ProbeResult(
                self.backend_name, "unavailable", version=self.expected_version, health=dict(health or {})
            )
        version = str(health.get("version") or getattr(self.client, "version", self.expected_version))
        if version != self.expected_version:
            return ProbeResult(
                self.backend_name,
                "incompatible",
                version=version,
                diagnostics={"expected_version": self.expected_version},
            )
        return ProbeResult(
            self.backend_name,
            "healthy",
            version=version,
            capabilities=("dataset", "upload", "parse", "chunks", "retrieval", "snapshot", "discard"),
            health={"ok": True},
            diagnostics={"endpoint": _safe_endpoint(endpoint)},
        )

    def prepare(
        self,
        project_revision: str,
        ir_revision: str,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> BackendCandidate:
        self._ensure_open()
        if not project_revision or not ir_revision:
            raise ValueError("project_revision and ir_revision are required")
        identity = content_hash(
            {"backend": self.backend_name, "project_revision": project_revision, "ir_revision": ir_revision}
        )
        candidate_id = f"backend-candidate-{identity[:24]}"
        existing = self._candidates.get(candidate_id)
        if existing is not None:
            return existing
        dataset_id = self._create_dataset(candidate_id)
        candidate = BackendCandidate(
            candidate_id=candidate_id,
            project_revision=project_revision,
            ir_revision=ir_revision,
            backend=self.backend_name,
            state="prepared",
            metadata={**dict(metadata or {}), "dataset_id": dataset_id, "owned": True},
        )
        self._candidates[candidate_id] = candidate
        return candidate

    def apply(self, candidate: BackendCandidate) -> IndexRevision:
        self._ensure_open()
        owned = self._assert_owned_candidate(candidate)
        existing = self._candidate_indexes.get(candidate.candidate_id)
        if existing is not None:
            return existing
        documents = owned.metadata.get("documents", [])
        if not isinstance(documents, list):
            raise BackendError("documents_invalid", "RAGFlow candidate documents must be a list")
        dataset_id = str(owned.metadata.get("dataset_id") or "")
        if not dataset_id:
            raise BackendError("dataset_missing", "RAGFlow candidate has no owned dataset")
        mapping: dict[str, dict[str, Any]] = {}
        external_ids: dict[str, str] = {}
        document_ids: set[str] = set()
        for document in documents:
            if not isinstance(document, Mapping):
                raise BackendError("document_invalid", "candidate document must be an object")
            document_id = str(document.get("document_id") or "")
            content = str(document.get("content") or "")
            blocks = document.get("blocks")
            if not document_id or not content or not isinstance(blocks, list):
                raise BackendError("document_invalid", "candidate documents require id, content and blocks")
            block_index = {
                str(block["block_id"]): block
                for block in blocks
                if isinstance(block, Mapping) and isinstance(block.get("block_id"), str) and block["block_id"]
            }
            uploaded = self._call(
                "upload_document", dataset_id, content, {"blocks": blocks, "document_id": document_id}
            )
            external_document_id = _external_id(uploaded, fallback=f"doc-{content_hash(document)[:16]}")
            document_ids.add(external_document_id)
            parse_result = self._call("parse_document", dataset_id, external_document_id)
            self._wait_for_parse(dataset_id, external_document_id, parse_result)
            chunks = self._call("list_chunks", dataset_id, external_document_id, default=[])
            for chunk in chunks if isinstance(chunks, list) else []:
                if not isinstance(chunk, Mapping):
                    continue
                chunk_id = _external_id(chunk, fallback=f"chunk-{content_hash(chunk)[:16]}")
                chunk_metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), Mapping) else {}
                block_id = str(chunk_metadata.get("block_id") or "")
                matched_block = block_index.get(block_id) if block_id else None
                if block_id and matched_block is None:
                    raise BackendError(
                        "mapping_unknown_block",
                        "RAGFlow chunk references a block outside the canonical IR document",
                    )
                if not block_id:
                    block_id, matched_block = _match_block(chunk, blocks)
                if not block_id:
                    continue
                # Provider metadata is untrusted transport data.  The public
                # mapping is rebuilt from the canonical IR block so secrets,
                # stale locators or forged source identities cannot cross the
                # backend seam.
                canonical_metadata = {"block_id": block_id}
                if isinstance(matched_block, Mapping):
                    canonical_metadata.update(
                        {
                            key: matched_block[key]
                            for key in (
                                "source_id",
                                "source_revision_id",
                                "locators",
                                "heading_path",
                                "kind",
                                "source_fragment_hash",
                            )
                            if key in matched_block
                        }
                    )
                mapping[chunk_id] = canonical_metadata
                external_ids[block_id] = chunk_id
        if not mapping:
            raise BackendError("mapping_empty", "RAGFlow returned no canonical chunk mappings")
        mapping_hash = content_hash(mapping)
        index_identity = content_hash(
            {
                "candidate": candidate.candidate_id,
                "mapping": mapping_hash,
                "parser": self.config.get("parser_fingerprint", "ragflow-0.27.2"),
            }
        )
        index = IndexRevision(
            index_revision=f"index-{index_identity[:24]}",
            project_revision=owned.project_revision,
            ir_revision=owned.ir_revision,
            backend=self.backend_name,
            backend_version=self.expected_version,
            state="queryable",
            mapping_hash=mapping_hash,
            external_ids=external_ids,
            fingerprints={
                "parser": str(self.config.get("parser_fingerprint", "ragflow-0.27.2")),
                "mapping": mapping_hash,
            },
        )
        self._indexes[index.index_revision] = {
            "index": index,
            "dataset_id": dataset_id,
            "mapping": mapping,
            "document_ids": document_ids,
        }
        self._candidate_indexes[candidate.candidate_id] = index
        return index

    def query(self, index_revision: IndexRevision, query_request: QueryRequest) -> EvidenceResult:
        self._ensure_open()
        state = self._indexes.get(index_revision.index_revision)
        if state is None or index_revision.backend != self.backend_name:
            raise BackendUnavailable("index_unknown", "RAGFlow index revision is not owned by this adapter")
        if query_request.project_revision and query_request.project_revision != index_revision.project_revision:
            raise BackendUnavailable("revision_mismatch", "query project revision does not match the index revision")
        # RAGFlow ranks opaque chunks before the Farol seam can apply source,
        # rights and revocation eligibility.  Over-fetch so the canonical
        # filter can refill the requested top-k without promoting an ineligible
        # first hit.
        raw_hits = self._call(
            "search",
            state["dataset_id"],
            query_request.query,
            max(query_request.top_k * 4, query_request.top_k),
            default=[],
        )
        hits: list[dict[str, Any]] = []
        mapping = state["mapping"]
        for raw in raw_hits if isinstance(raw_hits, list) else []:
            if not isinstance(raw, Mapping):
                continue
            external_id = str(raw.get("id") or raw.get("chunk_id") or "")
            canonical = dict(mapping.get(external_id, {}))
            # A provider hit is evidence only when the adapter created and
            # retained a canonical mapping for that exact external chunk.
            # Never trust provider-supplied metadata as a substitute: it may
            # contain a plausible block_id for a different revision or source.
            if not canonical.get("block_id"):
                continue
            hits.append({**dict(raw), **canonical, "external_chunk_id": external_id})
        return EvidenceResult(
            index_revision=index_revision.index_revision,
            query=query_request,
            hits=hits[: query_request.top_k],
            outcome="ok" if hits else "insufficient_evidence",
            metadata={"backend": self.backend_name, "version": self.expected_version},
        )

    def mapping(self, index_revision: IndexRevision) -> BackendMapping:
        """Return the reconstructible canonical-to-external mapping for an index."""

        state = self._indexes.get(index_revision.index_revision)
        if state is None:
            raise BackendUnavailable("index_unknown", "RAGFlow index revision is not owned by this adapter")
        entries = [{"chunk_id": chunk_id, **dict(metadata)} for chunk_id, metadata in sorted(state["mapping"].items())]
        return BackendMapping(
            project_revision=index_revision.project_revision,
            ir_revision=index_revision.ir_revision,
            backend=self.backend_name,
            backend_version=self.expected_version,
            dataset_id=str(state["dataset_id"]),
            entries=entries,
            parser_fingerprint=index_revision.fingerprints.get("parser"),
        )

    def get_document(self, index_revision: IndexRevision, document_id: str) -> Mapping[str, Any]:
        """Read one owned document through the adapter, never by raw dataset ID."""

        self._ensure_open()
        state = self._indexes.get(index_revision.index_revision)
        if state is None or document_id not in state.get("document_ids", set()):
            raise BackendUnavailable("document_unknown", "RAGFlow document is not owned by this index")
        value = self._call("get_document", state["dataset_id"], document_id, default={})
        return dict(value) if isinstance(value, Mapping) else {}

    def stats(self, index_revision: IndexRevision) -> dict[str, Any]:
        """Return bounded dataset statistics without exposing content."""

        self._ensure_open()
        state = self._indexes.get(index_revision.index_revision)
        if state is None:
            raise BackendUnavailable("index_unknown", "RAGFlow index revision is not owned by this adapter")
        value = self._call("dataset_stats", state["dataset_id"], default={})
        if isinstance(value, Mapping) and value:
            return {"backend": self.backend_name, "index_revision": index_revision.index_revision, **dict(value)}
        return {
            "backend": self.backend_name,
            "index_revision": index_revision.index_revision,
            "documents": len(state.get("document_ids", set())),
            "mapped_chunks": len(state["mapping"]),
        }

    def snapshot(self, index_revision: IndexRevision) -> SnapshotIdentity:
        self._ensure_open()
        if index_revision.index_revision not in self._indexes:
            raise BackendUnavailable("index_unknown", "cannot snapshot an unknown RAGFlow index")
        return SnapshotIdentity(
            snapshot_id=f"snapshot-{index_revision.index_revision}",
            index_revision=index_revision.index_revision,
            content_hash=content_hash(index_revision.to_dict()),
        )

    def discard(self, candidate: BackendCandidate) -> BackendReceipt:
        self._ensure_open()
        owned = self._assert_owned_candidate(candidate)
        dataset_id = str(owned.metadata.get("dataset_id") or "")
        if dataset_id:
            self._call("delete_dataset", dataset_id)
        index = self._candidate_indexes.pop(candidate.candidate_id, None)
        if index is not None:
            self._indexes.pop(index.index_revision, None)
        self._candidates.pop(candidate.candidate_id, None)
        return BackendReceipt("discarded", "discard", candidate_id=candidate.candidate_id)

    def close(self) -> BackendReceipt:
        if not self._closed:
            close = getattr(self.client, "close", None)
            if callable(close):
                close()
            self._closed = True
        return BackendReceipt("closed", "close")

    @staticmethod
    def query_request(query: str, *, top_k: int = 5, project_revision: str | None = None) -> QueryRequest:
        return QueryRequest(query=query, top_k=top_k, project_revision=project_revision)

    def _create_dataset(self, candidate_id: str) -> str:
        if self.client is None:
            raise BackendUnavailable("client_missing", "RAGFlow client is not configured")
        response = self._call("create_dataset", f"farol-candidate-{candidate_id[-12:]}")
        dataset_id = _external_id(response, fallback="")
        if not dataset_id:
            raise BackendError("dataset_invalid", "RAGFlow did not return a dataset identity")
        return dataset_id

    def _wait_for_parse(self, dataset_id: str, document_id: str, result: Any) -> None:
        if not isinstance(result, Mapping):
            return
        status = str(result.get("status") or result.get("state") or "").casefold()
        if status in {"failed", "error", "cancelled", "canceled"}:
            raise BackendError("parse_failed", "RAGFlow document parsing failed")
        if status in {"done", "parsed", "success", "succeeded", "completed", ""}:
            return
        waiter = getattr(self.client, "wait_for_parse", None)
        if not callable(waiter):
            raise BackendError("parse_pending", "RAGFlow parsing did not reach a terminal state")
        try:
            timeout_seconds = _positive_finite_timeout(self.config.get("timeout_seconds", 30))
        except ValueError as exc:
            raise BackendError("timeout_invalid", "RAGFlow timeout_seconds must be finite and positive") from exc
        try:
            waited = waiter(dataset_id, document_id, timeout_seconds)
        except BackendUnavailable:
            raise
        except (TimeoutError, ConnectionError, OSError) as exc:
            raise BackendUnavailable("parse_timeout", "RAGFlow parsing did not finish before the deadline") from exc
        except Exception as exc:
            raise BackendError("parse_protocol_error", "RAGFlow parse waiter failed") from exc
        waited_status = (
            str(waited.get("status") or waited.get("state") or "").casefold() if isinstance(waited, Mapping) else ""
        )
        if waited_status in {"failed", "error", "cancelled", "canceled"}:
            raise BackendError("parse_failed", "RAGFlow document parsing failed")
        if waited_status not in {"done", "parsed", "success", "succeeded", "completed"}:
            raise BackendError("parse_pending", "RAGFlow parsing did not reach a terminal state")

    def _call(self, method: str, *args: Any, default: Any = None) -> Any:
        if self.client is None:
            raise BackendUnavailable("client_missing", "RAGFlow client is not configured")
        operation = getattr(self.client, method, None)
        if not callable(operation):
            if default is not None:
                return default
            raise BackendUnavailable("protocol_missing", f"RAGFlow client lacks {method}")
        retryable = method in {"health", "list_chunks", "search", "get_document", "dataset_stats"}
        try:
            configured_limit = int(self.config.get("retry_limit", 0))
        except (TypeError, ValueError):
            configured_limit = 0
        attempts = 1 + min(max(configured_limit, 0), 3) if retryable else 1
        for attempt in range(attempts):
            try:
                return operation(*args)
            except BackendError:
                raise
            except Exception as exc:
                if attempt + 1 >= attempts:
                    raise BackendUnavailable("protocol_error", f"RAGFlow operation {method} failed") from exc
        raise BackendUnavailable("protocol_error", f"RAGFlow operation {method} failed")

    def _assert_owned_candidate(self, candidate: BackendCandidate) -> BackendCandidate:
        owned = self._candidates.get(candidate.candidate_id)
        if owned != candidate or candidate.backend != self.backend_name or candidate.metadata.get("owned") is not True:
            raise BackendUnavailable("candidate_unknown", "RAGFlow candidate is not owned by this adapter")
        return owned

    def _ensure_open(self) -> None:
        if self._closed:
            raise BackendUnavailable("backend_closed", "backend is closed")

    @staticmethod
    def _validate_endpoint(endpoint: str, settings: Mapping[str, Any]) -> None:
        if not endpoint:
            raise BackendUnavailable("endpoint_missing", "RAGFlow endpoint is required")
        parsed = urlsplit(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise BackendUnavailable("endpoint_invalid", "RAGFlow endpoint must be an HTTP(S) URL")
        try:
            parsed.port
        except ValueError as exc:
            raise BackendUnavailable("endpoint_invalid", "RAGFlow endpoint port is invalid") from exc
        if parsed.username is not None or parsed.password is not None:
            raise BackendUnavailable(
                "endpoint_credentials_forbidden",
                "RAGFlow credentials must be supplied through a secret environment reference",
            )
        if parsed.query or parsed.fragment:
            raise BackendUnavailable(
                "endpoint_metadata_forbidden",
                "RAGFlow endpoint must not contain query or fragment data",
            )
        localhost = parsed.hostname.casefold() in {"localhost", "127.0.0.1", "::1"}
        if parsed.scheme != "https" and not (localhost and settings.get("allow_insecure_localhost") is True):
            raise BackendUnavailable("tls_required", "remote RAGFlow endpoints require HTTPS")


def _external_id(value: Any, *, fallback: str) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        for key in ("id", "dataset_id", "document_id", "chunk_id"):
            if isinstance(value.get(key), str) and value[key]:
                return str(value[key])
    return fallback


def _positive_finite_timeout(value: Any) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("timeout_seconds must be finite and positive") from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout_seconds must be finite and positive")
    return max(timeout, MIN_RAGFLOW_TIMEOUT_SECONDS)


def _chunk_page_limit(value: Any) -> int:
    try:
        pages = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("max_chunk_pages must be a positive bounded integer") from exc
    if pages < 1 or pages > MAX_RAGFLOW_CHUNK_PAGES:
        raise ValueError(f"max_chunk_pages must be between 1 and {MAX_RAGFLOW_CHUNK_PAGES}")
    return pages


def _match_block(chunk: Mapping[str, Any], blocks: list[Any]) -> tuple[str, Mapping[str, Any] | None]:
    """Map a provider chunk to a canonical block when the SDK omits metadata."""

    content = str(chunk.get("content") or "").strip()
    if not content:
        return "", None
    matches: list[tuple[str, Mapping[str, Any]]] = []
    for block in blocks:
        if not isinstance(block, Mapping):
            continue
        block_text = str(block.get("text") or block.get("content") or "").strip()
        block_id = str(block.get("block_id") or "")
        if block_id and block_text and (content == block_text or content in block_text or block_text in content):
            matches.append((block_id, block))
    if len(matches) > 1:
        raise BackendError(
            "mapping_ambiguous",
            "RAGFlow chunk content matches more than one canonical IR block",
        )
    if matches:
        return matches[0]
    return "", None


def _build_sdk_client(endpoint: str, token: str, settings: Mapping[str, Any]) -> _RagFlowSdkClient:
    try:
        import ragflow_sdk  # type: ignore[import-not-found]
        import requests  # type: ignore[import-not-found]
        from ragflow_sdk import RAGFlow  # type: ignore[import-not-found]
    except ImportError as exc:
        raise BackendUnavailable(
            "dependency_missing", "ragflow_sdk 0.27.2 is required for the RAGFlow adapter"
        ) from exc
    version = str(getattr(ragflow_sdk, "__version__", ""))
    if version != RagFlowAdapter.expected_version:
        raise BackendUnavailable("sdk_version_mismatch", "RAGFlow SDK version does not match the pinned contract")
    base_url = endpoint.rstrip("/")
    try:
        timeout_seconds = _positive_finite_timeout(settings.get("timeout_seconds", 30))
        max_chunk_pages = _chunk_page_limit(settings.get("max_chunk_pages", 256))
    except ValueError as exc:
        raise BackendUnavailable("config_invalid", str(exc)) from exc

    class _ConfiguredRAGFlow(RAGFlow):
        def __init__(self, api_key: str, base_url: str, version: str) -> None:
            super().__init__(api_key=api_key, base_url=base_url, version=version)
            self._farol_timeout = timeout_seconds

        def post(self, path: str, json: Any = None, stream: bool = False, files: Any = None) -> Any:
            return requests.post(
                url=self.api_url + path,
                json=json,
                headers=self.authorization_header,
                stream=stream,
                files=files,
                timeout=self._farol_timeout,
            )

        def get(self, path: str, params: Any = None, json: Any = None) -> Any:
            return requests.get(
                url=self.api_url + path,
                params=params,
                headers=self.authorization_header,
                json=json,
                timeout=self._farol_timeout,
            )

        def delete(self, path: str, json: Any) -> Any:
            return requests.delete(
                url=self.api_url + path,
                json=json,
                headers=self.authorization_header,
                timeout=self._farol_timeout,
            )

        def put(self, path: str, json: Any) -> Any:
            return requests.put(
                url=self.api_url + path,
                json=json,
                headers=self.authorization_header,
                timeout=self._farol_timeout,
            )

        def patch(self, path: str, json: Any) -> Any:
            return requests.patch(
                url=self.api_url + path,
                json=json,
                headers=self.authorization_header,
                timeout=self._farol_timeout,
            )

    sdk = _ConfiguredRAGFlow(
        api_key=token,
        base_url=base_url,
        version=str(settings.get("api_version") or "v1"),
    )
    return _RagFlowSdkClient(
        sdk,
        version=version,
        timeout_seconds=timeout_seconds,
        max_chunk_pages=max_chunk_pages,
    )


def _safe_endpoint(endpoint: str) -> str:
    parsed = urlsplit(endpoint)
    if not parsed.scheme or not parsed.hostname:
        return "<unconfigured>"
    return f"{parsed.scheme}://{parsed.hostname}{':' + str(parsed.port) if parsed.port else ''}"
