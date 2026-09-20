# seam-scope: implementation-infrastructure (public taxonomy boundary fixtures)
from __future__ import annotations

import pytest

from docops.ir import IRBlock
from docops.taxonomy import TaxonomyEngine, TaxonomyError


def _blocks() -> list[IRBlock]:
    return [
        IRBlock(
            block_id="auth-heading",
            parent_id=None,
            ordinal=0,
            kind="heading",
            text="Authentication",
            heading_path=["Authentication"],
            locators=[{"kind": "section", "label": "Authentication", "line": 1}],
        ),
        IRBlock(
            block_id="auth-body",
            parent_id="auth-heading",
            ordinal=1,
            kind="paragraph",
            text="Use a token for authentication.",
            heading_path=["Authentication"],
            locators=[{"kind": "line", "label": "2", "line": 2}],
        ),
        IRBlock(
            block_id="deploy-body",
            parent_id=None,
            ordinal=2,
            kind="paragraph",
            text="Deploy the service after authentication.",
            heading_path=["Deployment"],
            locators=[{"kind": "line", "label": "3", "line": 3}],
        ),
    ]


def test_taxonomy_proposal_reports_coverage_overlap_and_orphans() -> None:
    engine = TaxonomyEngine()
    proposal = engine.propose(_blocks(), goal="Operate the service")

    assert proposal.requires_approval is True
    assert proposal.metrics["covered_blocks"] == 3
    assert proposal.metrics["coverage_ratio"] == 1.0
    assert proposal.orphans == []
    assert proposal.proposal_hash


def test_taxonomy_rejects_dangling_refs_and_cycles() -> None:
    engine = TaxonomyEngine()
    with pytest.raises(TaxonomyError) as dangling:
        engine.propose(
            _blocks(),
            goal="goal",
            proposal={"nodes": [{"node_id": "auth", "concept_id": "auth", "owner": "auth", "coverage": ["missing"]}]},
        )
    assert dangling.value.code == "dangling_evidence"

    with pytest.raises(TaxonomyError) as cycle:
        engine.propose(
            _blocks(),
            goal="goal",
            proposal={
                "nodes": [
                    {"node_id": "a", "concept_id": "a", "owner": "a", "parent_id": "b", "coverage": ["auth-heading"]},
                    {"node_id": "b", "concept_id": "b", "owner": "b", "parent_id": "a", "coverage": ["auth-body"]},
                ]
            },
        )
    assert cycle.value.code == "cycle"


def test_taxonomy_rejects_two_nodes_with_the_same_owner() -> None:
    engine = TaxonomyEngine()
    with pytest.raises(TaxonomyError) as caught:
        engine.propose(
            _blocks(),
            goal="goal",
            proposal={
                "nodes": [
                    {"node_id": "a", "concept_id": "a", "owner": "same", "coverage": ["auth-heading"]},
                    {"node_id": "b", "concept_id": "b", "owner": "same", "coverage": ["auth-body"]},
                ]
            },
        )
    assert caught.value.code == "duplicate_owner"


def test_taxonomy_rejects_duplicate_skill_slugs_before_synthesis() -> None:
    engine = TaxonomyEngine()

    with pytest.raises(TaxonomyError) as caught:
        engine.propose(
            _blocks(),
            goal="goal",
            proposal={
                "nodes": [
                    {
                        "node_id": "auth-guide",
                        "concept_id": "auth-guide",
                        "owner": "auth-guide",
                        "title": "Authentication",
                        "slug": "authentication",
                        "coverage": ["auth-heading"],
                    },
                    {
                        "node_id": "auth-reference",
                        "concept_id": "auth-reference",
                        "owner": "auth-reference",
                        "title": "Authentication",
                        "slug": "authentication",
                        "coverage": ["auth-body"],
                    },
                ]
            },
        )

    assert caught.value.code == "duplicate_slug"


def test_taxonomy_approval_is_explicit_and_compare_and_swap_guarded() -> None:
    engine = TaxonomyEngine()
    proposal = engine.propose(_blocks(), goal="goal")
    with pytest.raises(TaxonomyError) as missing:
        engine.approve(proposal, {"approved": False})
    assert missing.value.code == "approval_required"

    revision = engine.approve(proposal, {"approved": True, "actor": "human-fixture"})
    assert revision.status == "active"
    assert engine.active_revision == revision.revision_id
    with pytest.raises(TaxonomyError) as stale:
        engine.approve(proposal, {"approved": True}, expected_revision="other")
    assert stale.value.code == "stale_revision"
