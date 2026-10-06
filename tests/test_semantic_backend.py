# seam-scope: implementation-infrastructure (Farol 3 public module seam: S3: KnowledgeBackend hybrid retrieval with an embedder)
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from docops.backends import BackendError, QueryRequest
from docops.backends.local_fts import LocalFtsBackend

np = pytest.importorskip("numpy")

CONCEPTS = {
    "copy": ("cherry", "pick", "transplant", "apply", "single", "commit"),
    "status": ("states", "modified", "staged", "estados"),
    "proxy": ("proxy", "socks", "route"),
}


class ConceptEmbedder:
    """Deterministic bag-of-concepts embedder: synonyms share a dimension."""

    def __init__(self, name: str = "concepts-v1") -> None:
        self.profile = {"model": name, "dim": len(CONCEPTS), "window": 80, "stride": 60}

    def _vector(self, text: str) -> Any:
        words = text.casefold().replace("-", " ").split()
        vector = np.array(
            [sum(word.strip(".,?") in terms for word in words) for terms in CONCEPTS.values()], dtype=np.float32
        )
        return vector / (np.linalg.norm(vector) or 1.0)

    def embed_documents(self, texts: list[str]) -> Any:
        return np.stack([self._vector(text) for text in texts])

    def embed_query(self, text: str) -> Any:
        return self._vector(text)


def _block(block_id: str, text: str) -> dict[str, Any]:
    return {
        "block_id": block_id,
        "kind": "paragraph",
        "text": text,
        "heading_path": ["Guide"],
        "locators": [{"kind": "line", "line": 1}],
    }


DOCS = [
    {
        "document_id": "d1",
        "source_id": "book",
        "source_revision_id": "r1",
        "path": "book.md",
        "blocks": [
            _block("b-cherry", "Run git cherry-pick e43a6 to bring that fix over."),
            _block("b-noise", "Branches are cheap. Apply your judgement when naming them."),
        ],
    },
    {
        "document_id": "d2",
        "source_id": "other",
        "source_revision_id": "r1",
        "path": "other.md",
        "blocks": [_block("b-other", "Pick a single commit message style.")],
    },
]


def _hybrid(tmp_path: Path, embedder: Any) -> tuple[LocalFtsBackend, Any]:
    backend = LocalFtsBackend(tmp_path / "index", embedder=embedder)
    return backend, backend.apply(backend.prepare("p", "ir", metadata={"documents": DOCS}))


def test_hybrid_retrieval_bridges_vocabulary_gaps_that_bm25_misses(tmp_path: Path) -> None:
    lexical = LocalFtsBackend(tmp_path / "lexical")
    lexical_index = lexical.apply(lexical.prepare("p", "ir", metadata={"documents": DOCS}))
    backend, index = _hybrid(tmp_path, ConceptEmbedder())
    question = QueryRequest(query="how do I transplant work", top_k=1)

    bm25 = lexical.query(lexical_index, question)
    hybrid = backend.query(index, question)

    assert bm25.outcome == "insufficient_evidence" or bm25.hits[0]["block_id"] != "b-cherry"
    assert hybrid.hits[0]["block_id"] == "b-cherry"
    assert hybrid.metadata["retrieval_mode"] == "hybrid"


def test_vector_candidates_respect_eligibility_filters(tmp_path: Path) -> None:
    backend, index = _hybrid(tmp_path, ConceptEmbedder())

    result = backend.query(
        index, QueryRequest(query="apply a single commit", top_k=5, filters={"source_ids": ["other"]})
    )

    assert [hit["block_id"] for hit in result.hits] == ["b-other"]


def test_hybrid_index_without_the_semantic_extra_falls_back_to_bm25_declared(tmp_path: Path) -> None:
    _backend, index = _hybrid(tmp_path, ConceptEmbedder())
    reader = LocalFtsBackend(tmp_path / "index")

    result = reader.query(reader.open(index.index_revision), QueryRequest(query="cherry-pick", top_k=1))

    assert result.hits[0]["block_id"] == "b-cherry"
    assert result.metadata["retrieval_mode"] == "bm25"
    assert any("semantic" in note for note in result.metadata["degraded"])


def test_changing_the_embedding_model_requires_a_rebuild(tmp_path: Path) -> None:
    _backend, index = _hybrid(tmp_path, ConceptEmbedder("concepts-v1"))
    other = LocalFtsBackend(tmp_path / "index", embedder=ConceptEmbedder("concepts-v2"))

    with pytest.raises(BackendError) as error:
        other.query(other.open(index.index_revision), QueryRequest(query="cherry-pick", top_k=1))

    assert error.value.code == "embedding_profile_changed"


def test_package_index_uses_the_configured_embedder_end_to_end(tmp_path: Path) -> None:
    import docops
    from docops.package_index import build_package_index, open_package_index

    source = tmp_path / "source"
    source.mkdir()
    (source / "git.md").write_text(
        "# Git\n\n## Moving work\n\nRun git cherry-pick e43a6 to bring that fix over.\n\n"
        "## Naming\n\nBranches are cheap; name them well.\n",
        encoding="utf-8",
    )
    package = tmp_path / "package"
    docops.apply(
        docops.plan(
            docops.OperationRequest(
                source,
                docops.OperationOptions(output_dir=package, source_root=source.parent, slug="git", license="MIT"),
            )
        )
    )
    embedder = ConceptEmbedder()

    report = build_package_index(package, embedder=embedder)
    backend, index = open_package_index(package, embedder=embedder)
    result = backend.query(index, QueryRequest(query="how do I transplant work", top_k=1))

    assert report["retrieval_mode"] == "hybrid"
    assert "cherry-pick" in result.hits[0]["text"]


# -- Farol 3.1 TK-205: prefixes recorded in the profile; stale profiles repaired --


class _FakeTextEmbedding:
    seen: list[str] = []

    def __init__(self, model: str, cache_dir: str | None = None, threads: int | None = None) -> None:
        self.model = model

    def embed(self, texts: list[str], batch_size: int = 32) -> Any:
        _FakeTextEmbedding.seen.extend(texts)
        return iter([np.ones(4, dtype=np.float32) for _ in texts])

    def query_embed(self, texts: list[str]) -> Any:
        _FakeTextEmbedding.seen.extend(texts)
        return iter([np.ones(4, dtype=np.float32) for _ in texts])


def _fake_fastembed(monkeypatch) -> None:
    import sys
    import types

    module = types.ModuleType("fastembed")
    module.TextEmbedding = _FakeTextEmbedding
    monkeypatch.setitem(sys.modules, "fastembed", module)
    monkeypatch.setitem(sys.modules, "onnxruntime", types.SimpleNamespace(set_default_logger_severity=lambda _: None))
    _FakeTextEmbedding.seen = []


def test_embedding_profile_records_query_and_passage_prefixes(monkeypatch) -> None:
    from docops.backends.semantic import DEFAULT_MODEL, FastEmbedEmbedder

    _fake_fastembed(monkeypatch)
    e5 = FastEmbedEmbedder("intfloat/multilingual-e5-large")
    _FakeTextEmbedding.seen = []
    e5.embed_documents(["Branches are cheap."])
    e5.embed_query("what is a branch")

    assert e5.profile["passage_prefix"] == "passage: " and e5.profile["query_prefix"] == "query: "
    assert _FakeTextEmbedding.seen == ["passage: Branches are cheap.", "query: what is a branch"]
    # The 3.0 default keeps its exact profile, so existing indexes stay valid.
    assert set(FastEmbedEmbedder(DEFAULT_MODEL).profile) == {"model", "dim", "window", "stride"}


def test_build_rebuilds_the_index_when_the_embedding_model_changes(tmp_path: Path) -> None:
    import docops
    from docops.package_index import build_package_index, open_package_index

    source = tmp_path / "source"
    source.mkdir()
    (source / "git.md").write_text("# Git\n\n## Moving work\n\nRun git cherry-pick e43a6.\n", encoding="utf-8")
    package = tmp_path / "package"
    docops.apply(
        docops.plan(
            docops.OperationRequest(
                source,
                docops.OperationOptions(output_dir=package, source_root=source.parent, slug="git", license="MIT"),
            )
        )
    )
    build_package_index(package, embedder=ConceptEmbedder("concepts-v1"))

    build_package_index(package, embedder=ConceptEmbedder("concepts-v2"))
    backend, index = open_package_index(package, embedder=ConceptEmbedder("concepts-v2"))

    assert (
        backend.query(index, QueryRequest(query="transplant a commit", top_k=1)).metadata["retrieval_mode"] == "hybrid"
    )


def test_doctor_fix_rebuilds_an_index_with_a_stale_embedding_profile(tmp_path: Path, monkeypatch) -> None:
    from docops import journey, package_index

    source = tmp_path / "notes"
    source.mkdir()
    (source / "git.md").write_text("# Git\n\n## Moving work\n\nRun git cherry-pick e43a6.\n", encoding="utf-8")
    project = tmp_path / "project"
    journey.add_source(project, str(source), license="MIT")
    monkeypatch.setattr(package_index, "_EMBEDDER_CACHE", {"default": ConceptEmbedder("concepts-v1")})
    assert journey.build(project)["ok"]
    monkeypatch.setattr(package_index, "_EMBEDDER_CACHE", {"default": ConceptEmbedder("concepts-v2")})

    before = journey.project_health(project)
    repaired = journey.project_health(project, fix=True)
    after = journey.project_health(project)

    assert before["issues"] == [
        {"source": "notes", "code": "embedding_profile_changed", "next_action": "farol doctor --fix"}
    ]
    assert repaired["fixed"] == [{"source": "notes", "action": "rebuilt_index"}]
    assert after["ok"] is True
