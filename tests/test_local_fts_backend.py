# seam-scope: public-seam (KnowledgeBackend contract, local-fts adapter)
from __future__ import annotations

from pathlib import Path
from typing import Any

from docops.backends import QueryRequest
from docops.backends.local_fts import LocalFtsBackend


def _block(block_id: str, text: str, heading: list[str], *, line: int, kind: str = "paragraph") -> dict[str, Any]:
    return {
        "block_id": block_id,
        "kind": kind,
        "text": text,
        "heading_path": heading,
        "locators": [{"kind": "line", "label": str(line), "line": line}],
    }


GUIDE = {
    "document_id": "doc-guide",
    "source_id": "acme-guide",
    "source_revision_id": "rev-1",
    "path": "guide.md",
    "blocks": [
        _block("b-auth", "Send the API key in the X-Acme-Key header.", ["Guide", "Authentication"], line=9),
        _block(
            "b-retry", "Retries use exponential backoff with a maximum of 5 attempts.", ["Guide", "Retries"], line=14
        ),
    ],
}
RELEASE = {
    "document_id": "doc-release",
    "source_id": "acme-release",
    "source_revision_id": "rev-1",
    "path": "release.md",
    "blocks": [
        _block("b-v2", "Version 2.0 removed the legacy /v1/orders endpoint.", ["Release notes", "2.0"], line=5),
    ],
}


def _index(tmp_path: Path, documents: list[dict[str, Any]]) -> tuple[LocalFtsBackend, Any]:
    backend = LocalFtsBackend(tmp_path / "index")
    candidate = backend.prepare("project-1", "ir-1", metadata={"documents": documents})
    return backend, backend.apply(candidate)


def test_indexed_block_is_retrieved_with_its_locator_by_a_fresh_reader(tmp_path: Path) -> None:
    writer, index = _index(tmp_path, [GUIDE, RELEASE])
    writer.close()

    reader = LocalFtsBackend(tmp_path / "index")
    reopened = reader.open(index.index_revision)
    result = reader.query(reopened, QueryRequest(query="how many retry attempts", top_k=3))

    assert index.state == "queryable"
    assert result.outcome == "ok"
    top = result.hits[0]
    assert top["block_id"] == "b-retry"
    assert top["source_id"] == "acme-guide"
    assert top["path"] == "guide.md"
    assert top["heading_path"] == ["Guide", "Retries"]
    assert top["locators"] == [{"kind": "line", "label": "14", "line": 14}]
    assert "5 attempts" in top["text"]


def test_ineligible_sources_never_displace_eligible_evidence(tmp_path: Path) -> None:
    # Both documents mention "endpoint"; with top_k=1 the excluded source must not
    # take the only slot, and a revoked document must not be indexed at all.
    revoked = {
        **RELEASE,
        "document_id": "doc-old",
        "source_id": "acme-old",
        "status": "revoked",
        "blocks": [_block("b-old", "The endpoint endpoint endpoint is /v0/legacy.", ["Old"], line=1)],
    }
    guide = {
        **GUIDE,
        "blocks": [
            *GUIDE["blocks"],
            _block("b-base", "The base endpoint is https://api.acme.test.", ["Guide"], line=3),
        ],
    }
    backend, index = _index(tmp_path, [guide, RELEASE, revoked])

    excluded = backend.query(
        index, QueryRequest(query="endpoint", top_k=1, filters={"exclude_source_ids": ["acme-release"]})
    )
    allowed = backend.query(index, QueryRequest(query="endpoint", top_k=5, filters={"source_ids": ["acme-release"]}))
    everything = backend.query(index, QueryRequest(query="endpoint legacy", top_k=10))

    assert [hit["block_id"] for hit in excluded.hits] == ["b-base"]
    assert [hit["block_id"] for hit in allowed.hits] == ["b-v2"]
    assert "b-old" not in {hit["block_id"] for hit in everything.hits}


def test_query_without_supporting_evidence_abstains(tmp_path: Path) -> None:
    backend, index = _index(tmp_path, [GUIDE])

    result = backend.query(index, QueryRequest(query="kubernetes helm chart", top_k=3))

    assert result.outcome == "insufficient_evidence"
    assert result.hits == []


def test_query_text_cannot_inject_fts_syntax(tmp_path: Path) -> None:
    backend, index = _index(tmp_path, [GUIDE])

    result = backend.query(index, QueryRequest(query='header" OR NEAR(* ) -- key', top_k=3))

    assert result.hits[0]["block_id"] == "b-auth"


def test_headings_are_context_not_evidence(tmp_path: Path) -> None:
    document = {
        **GUIDE,
        "blocks": [
            _block("h-retries", "Retries", ["Guide", "Retries"], line=12, kind="heading"),
            _block("p-retries", "The client tries 5 times.", ["Guide", "Retries"], line=14),
        ],
    }
    backend, index = _index(tmp_path, [document])

    result = backend.query(index, QueryRequest(query="retries", top_k=5))

    assert [hit["block_id"] for hit in result.hits] == ["p-retries"]


def test_function_words_do_not_decide_the_ranking(tmp_path: Path) -> None:
    chatty = {
        **RELEASE,
        "blocks": [
            _block("b-chatty", "What is it that the one in the middle is? It is what it is.", ["Notes"], line=1)
        ],
    }
    backend, index = _index(tmp_path, [GUIDE, chatty])

    result = backend.query(index, QueryRequest(query="what is the maximum of attempts", top_k=1))
    only_function_words = backend.query(index, QueryRequest(query="what is it", top_k=1))
    unknown_subject = backend.query(index, QueryRequest(query="what is the kubernetes setting", top_k=3))

    assert result.hits[0]["block_id"] == "b-retry"
    assert only_function_words.hits[0]["block_id"] == "b-chatty"
    assert unknown_subject.outcome == "insufficient_evidence"
