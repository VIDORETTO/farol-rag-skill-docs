"""Default local knowledge backend: SQLite FTS5 (BM25) over canonical IR blocks.

The index is a rebuildable projection of IR blocks, never an authority. Each
index revision is one immutable SQLite file written atomically, so a separate
reader process (for example the MCP server) can open it by revision.

Supported ``QueryRequest.filters``:

- ``source_ids``: allowlist of eligible sources;
- ``exclude_source_ids``: sources withdrawn or revoked after indexing;
- ``include_high_risk``: opt-in for local inspection of blocks classified as
  ``high`` risk (prompt-injection directives); they are excluded by default.

Filters are applied inside the ranking query, before ``top_k`` is cut, so an
ineligible block can never displace an eligible one. Sources whose document
``status`` is ``revoked`` or ``withdrawn`` are not indexed at all.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from typing import Any, Mapping

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

BACKEND_NAME = "local-fts"
BACKEND_VERSION = "2"
TOKENIZER = "unicode61 remove_diacritics 2"
_INACTIVE_STATUSES = frozenset({"revoked", "withdrawn"})
# Titles and headings are context carried by every child block (``heading``
# column); indexing them as evidence lets a bare title outrank the fact.
_CONTEXT_ONLY_KINDS = frozenset({"title", "heading"})
_TOKEN = re.compile(r"\w+", re.UNICODE)
# Measured on the real acceptance corpus with the default model: answers score
# 0.40-0.64 (median), queries without an answer up to 0.54.
VECTOR_FLOOR = 0.35
VECTOR_ONLY_MIN = 0.55
_INDEX_FILE = re.compile(r"^index-[0-9a-f]{24}$")


def fts5_available() -> bool:
    try:
        with closing(sqlite3.connect(":memory:")) as connection:
            connection.execute("CREATE VIRTUAL TABLE probe USING fts5(text)")
        return True
    except sqlite3.Error:
        return False


# Function words (English and Portuguese) carry no evidence; they are dropped
# from queries unless the query has nothing else.
_STOPWORDS = frozenset(
    """a about after all also an and any are as at be been before but by can could did do does
    for from had has have how i if in into is it its just me more most my no not of on only or
    our out over should so some than that the their them then there these they this those to
    under up very was we were what when where which while who why will with within would you your
    à ao aos as até com como da das de do dos e é ela ele em entre essa esse esta este eu foi
    há isso já la mais mas me meu minha na nas no nos não o os ou para pela pelo por qual quando
    que quem se sem ser seu sua são também tem um uma umas uns""".split()
)


def _match_expression(query: str) -> str:
    # Quote every token so user text can never inject FTS5 query syntax.
    tokens = [token for token in _TOKEN.findall(query) if token.strip("_")]
    content = [token for token in tokens if token.casefold() not in _STOPWORDS]
    return " OR ".join(f'"{token}"' for token in (content or tokens))


class LocalFtsBackend:
    backend_name = BACKEND_NAME
    expected_version = BACKEND_VERSION

    def __init__(self, index_dir: Path | str, *, embedder: Any | None = None) -> None:
        self.index_dir = Path(index_dir)
        self.embedder = embedder
        self._candidates: dict[str, BackendCandidate] = {}
        self._closed = False
        self._vectors: dict[str, tuple[Any, Any]] = {}

    def probe(self, config: Mapping[str, Any] | None = None) -> ProbeResult:
        self._ensure_open()
        if not fts5_available():
            return ProbeResult(
                BACKEND_NAME, "unavailable", version=BACKEND_VERSION, diagnostics={"reason": "fts5_missing"}
            )
        return ProbeResult(
            BACKEND_NAME,
            "healthy",
            version=BACKEND_VERSION,
            capabilities=("ingest", "retrieval", "get_document", "snapshot", "discard"),
            health={"ok": True, "sqlite": sqlite3.sqlite_version},
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
        documents = (metadata or {}).get("documents", [])
        if not isinstance(documents, list):
            raise BackendError("documents_invalid", "local-fts candidate documents must be a list")
        identity = content_hash(
            {
                "backend": BACKEND_NAME,
                "version": BACKEND_VERSION,
                "tokenizer": TOKENIZER,
                "project_revision": project_revision,
                "ir_revision": ir_revision,
                "documents": documents,
                "embedding": self.embedder.profile if self.embedder is not None else None,
            }
        )
        candidate = BackendCandidate(
            candidate_id=f"backend-candidate-{identity[:24]}",
            project_revision=project_revision,
            ir_revision=ir_revision,
            backend=BACKEND_NAME,
            state="prepared",
            metadata={"documents": documents, "identity": identity},
        )
        self._candidates[candidate.candidate_id] = candidate
        return candidate

    def apply(self, candidate: BackendCandidate) -> IndexRevision:
        self._ensure_open()
        owned = self._candidates.get(candidate.candidate_id)
        if owned is None:
            raise BackendError("candidate_unknown", "local-fts candidate was not prepared by this adapter")
        identity = str(owned.metadata["identity"])
        rows = list(_rows(owned.metadata["documents"]))
        if not rows:
            raise BackendError("mapping_empty", "local-fts candidate has no indexable blocks")
        index = IndexRevision(
            index_revision=f"index-{identity[:24]}",
            project_revision=owned.project_revision,
            ir_revision=owned.ir_revision,
            backend=BACKEND_NAME,
            backend_version=BACKEND_VERSION,
            state="queryable",
            mapping_hash=content_hash([row["block_id"] for row in rows]),
            fingerprints={
                "tokenizer": TOKENIZER,
                "sqlite": sqlite3.sqlite_version,
                **({"embedding": json.dumps(self.embedder.profile, sort_keys=True)} if self.embedder else {}),
            },
        )
        target = self._path(index.index_revision)
        if not _index_intact(target):
            _write_index(target, index, rows, self.embedder)
        return index

    def open(self, index_revision: str) -> IndexRevision:
        self._ensure_open()
        with self._connect(index_revision) as connection:
            (raw,) = connection.execute("SELECT value FROM meta WHERE key = 'index'").fetchone()
        value = json.loads(raw)
        return IndexRevision(
            index_revision=value["index_revision"],
            project_revision=value["project_revision"],
            ir_revision=value["ir_revision"],
            backend=value["backend"],
            backend_version=value["backend_version"],
            state=value["state"],
            mapping_hash=value["mapping_hash"],
            external_ids=value.get("external_ids", {}),
            fingerprints=value.get("fingerprints", {}),
        )

    def query(self, index_revision: IndexRevision, query_request: QueryRequest) -> EvidenceResult:
        self._ensure_open()
        if index_revision.backend != BACKEND_NAME:
            raise BackendUnavailable("index_unknown", "index revision does not belong to local-fts")
        if query_request.project_revision and query_request.project_revision != index_revision.project_revision:
            raise BackendUnavailable("revision_mismatch", "query project revision does not match the index revision")
        stored = index_revision.fingerprints.get("embedding")
        mode, degraded = "bm25", []
        if stored:
            if self.embedder is None:
                degraded.append("semantic extra unavailable: install farol-kit[semantic] for hybrid retrieval")
            elif json.dumps(self.embedder.profile, sort_keys=True) != stored:
                raise BackendError(
                    "embedding_profile_changed",
                    "the index was built with another embedding model; rebuild it (farol build or farol index)",
                )
            else:
                mode = "hybrid"
        eligibility, parameters = _eligibility(dict(query_request.filters))
        expression = _match_expression(query_request.query)
        pool = query_request.top_k if mode == "bm25" else max(50, query_request.top_k)
        with self._connect(index_revision.index_revision) as connection:
            lexical: list[int] = []
            if expression:
                lexical = [
                    rowid
                    for (rowid,) in connection.execute(
                        "SELECT b.rowid FROM blocks_fts JOIN blocks b ON b.rowid = blocks_fts.rowid"
                        f" WHERE blocks_fts MATCH ? AND {eligibility}"
                        " ORDER BY bm25(blocks_fts, 1.0, 0.5), b.rowid LIMIT ?",
                        [expression, *parameters, pool],
                    )
                ]
            if mode == "hybrid":
                similarity = self._vector_ranking(
                    connection, index_revision, query_request.query, eligibility, parameters
                )
                floor = float(self.embedder.profile.get("min_similarity", VECTOR_FLOOR))
                alone = float(self.embedder.profile.get("min_similarity_alone", VECTOR_ONLY_MIN))
                vector = [rowid for rowid, score in similarity if score >= floor][:pool]
                # Without any lexical evidence a vector neighbour must be clearly
                # relevant; otherwise the backend abstains instead of guessing.
                if not lexical and not (similarity and similarity[0][1] >= alone):
                    vector = []
                fused = _reciprocal_rank_fusion(lexical, vector)
                ranked = sorted(fused, key=lambda rowid: (-fused[rowid], rowid))
                scores = fused
            else:
                ranked = lexical
                scores = {rowid: 1.0 / (61 + position) for position, rowid in enumerate(ranked)}
            selected = ranked[: query_request.top_k]
            rows = {
                row[0]: row[1:]
                for row in connection.execute(
                    "SELECT rowid, block_id, document_id, source_id, source_revision_id, path, kind, heading_path,"
                    f" locators, text, risk, 0.0 FROM blocks WHERE rowid IN ({','.join('?' * len(selected)) or 'NULL'})",
                    selected,
                )
            }
        hits = []
        for rowid in selected:
            hit = _hit(rows[rowid])
            hit["score"] = round(scores[rowid] * 1000, 6)
            hits.append(hit)
        metadata: dict[str, Any] = {"backend": BACKEND_NAME, "version": BACKEND_VERSION, "retrieval_mode": mode}
        if degraded:
            metadata["degraded"] = degraded
        return EvidenceResult(
            index_revision=index_revision.index_revision,
            query=query_request,
            hits=hits,
            outcome="ok" if hits else "insufficient_evidence",
            metadata=metadata,
        )

    def _vector_ranking(
        self, connection: sqlite3.Connection, index: IndexRevision, query: str, eligibility: str, parameters: list[Any]
    ) -> list[tuple[int, float]]:
        import numpy as np

        cached = self._vectors.get(index.index_revision)
        if cached is None:
            owners, blobs = [], []
            for owner, blob in connection.execute("SELECT owner, vector FROM vectors ORDER BY rowid"):
                owners.append(owner)
                blobs.append(np.frombuffer(blob, dtype=np.float32))
            cached = (np.array(owners), np.stack(blobs) if blobs else np.zeros((0, 1), dtype=np.float32))
            self._vectors[index.index_revision] = cached
        owners, matrix = cached
        if not len(owners):
            return []
        eligible = {
            rowid for (rowid,) in connection.execute(f"SELECT b.rowid FROM blocks b WHERE {eligibility}", parameters)
        }
        query_vector = _normalized(np, self.embedder.embed_query(query))
        similarities = matrix @ query_vector
        best: dict[int, float] = {}
        for owner, similarity in zip(owners.tolist(), similarities.tolist()):
            if owner in eligible and similarity > best.get(owner, -2.0):
                best[owner] = similarity
        return sorted(best.items(), key=lambda item: (-item[1], item[0]))

    def get_document(self, index_revision: IndexRevision, document_id: str) -> dict[str, Any]:
        self._ensure_open()
        with self._connect(index_revision.index_revision) as connection:
            rows = connection.execute(
                "SELECT block_id, document_id, source_id, source_revision_id, path, kind, heading_path, locators, text,"
                " risk, 0.0 FROM blocks WHERE document_id = ? ORDER BY rowid",
                (document_id,),
            ).fetchall()
        if not rows:
            raise BackendError("document_unknown", "document is not part of this index revision")
        blocks = [_hit(row) for row in rows]
        for block in blocks:
            block.pop("score", None)
        return {
            "document_id": document_id,
            "source_id": blocks[0]["source_id"],
            "path": blocks[0]["path"],
            "blocks": blocks,
        }

    def snapshot(self, index_revision: IndexRevision) -> SnapshotIdentity:
        self._ensure_open()
        path = self._path(index_revision.index_revision)
        if not path.is_file():
            raise BackendUnavailable("index_unknown", "local-fts index revision does not exist")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return SnapshotIdentity(
            snapshot_id=f"snapshot-{digest[:24]}", index_revision=index_revision.index_revision, content_hash=digest
        )

    def discard(self, candidate: BackendCandidate) -> BackendReceipt:
        self._ensure_open()
        self._candidates.pop(candidate.candidate_id, None)
        return BackendReceipt(status="discarded", operation="discard", candidate_id=candidate.candidate_id)

    def close(self) -> BackendReceipt:
        self._closed = True
        self._candidates.clear()
        return BackendReceipt(status="closed", operation="close")

    def _path(self, index_revision: str) -> Path:
        if not _INDEX_FILE.fullmatch(index_revision):
            raise BackendUnavailable("index_unknown", "invalid local-fts index revision")
        return self.index_dir / f"{index_revision}.sqlite"

    def _connect(self, index_revision: str) -> closing[sqlite3.Connection]:
        path = self._path(index_revision)
        if not path.is_file():
            raise BackendUnavailable("index_unknown", "local-fts index revision does not exist")
        # closing(): a sqlite3 context manager only commits; readers must release
        # the file handle so Windows can replace or remove the index later.
        return closing(sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True))

    def _ensure_open(self) -> None:
        if self._closed:
            raise BackendUnavailable("backend_closed", "local-fts backend is closed")


def _index_intact(path: Path) -> bool:
    """Reuse an existing immutable index only if it is a readable SQLite index."""

    if not path.is_file():
        return False
    try:
        with closing(sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)) as connection:
            return connection.execute("SELECT 1 FROM meta WHERE key = 'index'").fetchone() is not None
    except sqlite3.Error:
        return False


def _eligibility(filters: Mapping[str, Any]) -> tuple[str, list[Any]]:
    """SQL applied to lexical and vector candidates alike, before any ranking cut."""

    clauses = ["1 = 1"]
    parameters: list[Any] = []
    if filters.get("include_high_risk") is not True:
        clauses.append("b.risk != 'high'")
    allowed = filters.get("source_ids")
    if allowed is not None:
        allowed = [str(item) for item in allowed]
        clauses.append(f"b.source_id IN ({','.join('?' * len(allowed)) or 'NULL'})")
        parameters.extend(allowed)
    excluded = [str(item) for item in filters.get("exclude_source_ids") or []]
    if excluded:
        clauses.append(f"b.source_id NOT IN ({','.join('?' * len(excluded))})")
        parameters.extend(excluded)
    return " AND ".join(clauses), parameters


def _reciprocal_rank_fusion(*rankings: list[int], k: int = 60) -> dict[int, float]:
    fused: dict[int, float] = {}
    for ranking in rankings:
        for position, rowid in enumerate(ranking, 1):
            fused[rowid] = fused.get(rowid, 0.0) + 1.0 / (k + position)
    return fused


def _normalized(np: Any, vector: Any) -> Any:
    vector = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm else vector


def _rows(documents: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for document in documents:
        if not isinstance(document, Mapping):
            raise BackendError("document_invalid", "candidate document must be an object")
        if str(document.get("status") or "active") in _INACTIVE_STATUSES:
            continue
        document_id = str(document.get("document_id") or "")
        blocks = document.get("blocks")
        if not document_id or not isinstance(blocks, list):
            raise BackendError("document_invalid", "candidate documents require document_id and blocks")
        for block in blocks:
            if not isinstance(block, Mapping):
                continue
            block_id = str(block.get("block_id") or "")
            text = block.get("text")
            if not block_id or not isinstance(text, str) or not text.strip():
                continue
            if str(block.get("kind") or "") in _CONTEXT_ONLY_KINDS:
                continue
            if block_id in seen:
                raise BackendError("block_duplicate", "block ids must be unique within an index revision")
            seen.add(block_id)
            rows.append(
                {
                    "block_id": block_id,
                    "document_id": document_id,
                    "source_id": str(document.get("source_id") or ""),
                    "source_revision_id": str(document.get("source_revision_id") or ""),
                    "path": str(document.get("path") or ""),
                    "kind": str(block.get("kind") or ""),
                    "heading_path": [str(item) for item in block.get("heading_path") or []],
                    "locators": [dict(item) for item in block.get("locators") or [] if isinstance(item, Mapping)],
                    "text": text,
                    "risk": str(block.get("risk") or "none"),
                }
            )
    return rows


def _write_index(target: Path, index: IndexRevision, rows: list[dict[str, Any]], embedder: Any | None = None) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{target.stem}.", suffix=".tmp", dir=target.parent)
    os.close(handle)
    try:
        connection = sqlite3.connect(temporary)
        try:
            connection.executescript(
                "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);"
                "CREATE TABLE blocks (block_id TEXT UNIQUE NOT NULL, document_id TEXT NOT NULL,"
                " source_id TEXT NOT NULL, source_revision_id TEXT NOT NULL, path TEXT NOT NULL, kind TEXT NOT NULL,"
                " heading_path TEXT NOT NULL, locators TEXT NOT NULL, text TEXT NOT NULL, risk TEXT NOT NULL);"
                f"CREATE VIRTUAL TABLE blocks_fts USING fts5(text, heading, tokenize='{TOKENIZER}');"
                "CREATE TABLE vectors (owner INTEGER NOT NULL, vector BLOB NOT NULL);"
            )
            connection.execute("INSERT INTO meta VALUES ('index', ?)", (json.dumps(index.to_dict(), sort_keys=True),))
            for row in rows:
                cursor = connection.execute(
                    "INSERT INTO blocks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        row["block_id"],
                        row["document_id"],
                        row["source_id"],
                        row["source_revision_id"],
                        row["path"],
                        row["kind"],
                        json.dumps(row["heading_path"], ensure_ascii=False),
                        json.dumps(row["locators"], ensure_ascii=False, sort_keys=True),
                        row["text"],
                        row["risk"],
                    ),
                )
                connection.execute(
                    "INSERT INTO blocks_fts (rowid, text, heading) VALUES (?, ?, ?)",
                    (cursor.lastrowid, row["text"], " ".join(row["heading_path"])),
                )
            if embedder is not None:
                _write_vectors(connection, embedder)
            connection.commit()
        finally:
            connection.close()
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def _write_vectors(connection: sqlite3.Connection, embedder: Any) -> None:
    import numpy as np

    from .semantic import windows

    owners: list[int] = []
    texts: list[str] = []
    for rowid, heading_path, text in connection.execute("SELECT rowid, heading_path, text FROM blocks ORDER BY rowid"):
        for window in windows(text, " / ".join(json.loads(heading_path))):
            owners.append(rowid)
            texts.append(window)
    for start in range(0, len(texts), 256):
        batch = np.asarray(embedder.embed_documents(texts[start : start + 256]), dtype=np.float32)
        for owner, vector in zip(owners[start : start + 256], batch):
            connection.execute(
                "INSERT INTO vectors VALUES (?, ?)", (owner, _normalized(np, vector).astype(np.float32).tobytes())
            )


def _hit(row: tuple[Any, ...]) -> dict[str, Any]:
    block_id, document_id, source_id, source_revision_id, path, kind, heading_path, locators, text, risk, score = row
    return {
        "block_id": block_id,
        "document_id": document_id,
        "source_id": source_id,
        "source_revision_id": source_revision_id,
        "path": path,
        "kind": kind,
        "heading_path": json.loads(heading_path),
        "locators": json.loads(locators),
        "text": text,
        "risk": risk,
        "score": round(-float(score), 6),
    }
