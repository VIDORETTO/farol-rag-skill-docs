# seam-scope: implementation-infrastructure (public router boundary fixtures)
from __future__ import annotations

from docops.backends import QueryRequest
from docops.ir import IRBlock
from docops.router import GlobalRouter, route_query_v2


def _router() -> GlobalRouter:
    nodes = [
        {"node_id": "auth", "title": "Authentication", "slug": "auth", "aliases": ["token"]},
        {"node_id": "deploy", "title": "Deployment", "slug": "deployment", "aliases": ["release"]},
    ]
    return GlobalRouter(nodes)


def test_router_distinguishes_conceptual_factual_and_hybrid_queries() -> None:
    assert route_query_v2("How should authentication be designed?") == "conceptual"
    assert route_query_v2("What is the default token endpoint?") == "factual"
    assert route_query_v2("How should authentication use the exact default?") == "hybrid"
    assert route_query_v2("Is this safe to deploy now?") == "hybrid"


def test_router_selects_topics_and_pins_backend_query() -> None:
    plan = _router().route("How should I configure authentication?", project_revision="project-2", top_k=4)

    assert plan.route == "conceptual"
    assert plan.skill_ids == ["auth"]
    assert plan.query_request == QueryRequest(
        query="How should I configure authentication?",
        top_k=4,
        project_revision="project-2",
        filters={"skill_ids": ["auth"]},
    )


def test_router_filters_ineligible_hits_before_top_k_and_cites_locators() -> None:
    blocks = [
        IRBlock(
            block_id="eligible",
            parent_id=None,
            ordinal=0,
            kind="paragraph",
            text="default token",
            locators=[{"kind": "page", "label": "Page 2", "page": 2}],
        ),
        IRBlock(
            block_id="revoked",
            parent_id=None,
            ordinal=1,
            kind="paragraph",
            text="default token",
            locators=[{"kind": "page", "label": "Page 1", "page": 1}],
        ),
        IRBlock(
            block_id="opaque",
            parent_id=None,
            ordinal=2,
            kind="paragraph",
            text="default token",
            locators=[],
        ),
    ]
    result = _router().filter_evidence(
        QueryRequest("default token", top_k=1, project_revision="project-2"),
        [
            {
                "block_id": "revoked",
                "score": 1.0,
                "source_id": "source",
                "source_revision_id": "rev-1",
                "revoked": True,
            },
            {"block_id": "opaque", "score": 0.99, "source_id": "source", "source_revision_id": "rev-1"},
            {"block_id": "eligible", "score": 0.5, "source_id": "source", "source_revision_id": "rev-2"},
        ],
        blocks,
    )

    assert result.outcome == "ok"
    assert result.hits[0]["block_id"] == "eligible"
    assert result.hits[0]["citations"] == ["source/source@rev-2#page=Page%202"]


def test_router_abstains_when_no_eligible_evidence_exists() -> None:
    result = _router().filter_evidence(QueryRequest("exact", top_k=2), [], [])
    assert result.outcome == "insufficient_evidence"
    assert result.hits == []
