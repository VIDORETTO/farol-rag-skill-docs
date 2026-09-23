# seam-scope: implementation-infrastructure (public synthesis boundary fixtures)
from __future__ import annotations

import pytest

from docops.ir import IRBlock
from docops.synthesis import SynthesisEngine, SynthesisError
from docops.taxonomy import TaxonomyEngine


def _blocks() -> list[IRBlock]:
    return [
        IRBlock(
            block_id="auth",
            parent_id=None,
            ordinal=0,
            kind="heading",
            text="Authentication",
            heading_path=["Authentication"],
            locators=[{"kind": "section", "label": "Authentication", "line": 1}],
            source_fragment_hash="a" * 64,
        ),
        IRBlock(
            block_id="auth-body",
            parent_id="auth",
            ordinal=1,
            kind="paragraph",
            text="Use the original token term.",
            heading_path=["Authentication"],
            locators=[{"kind": "line", "label": "2", "line": 2}],
            source_fragment_hash="b" * 64,
        ),
        IRBlock(
            block_id="deploy",
            parent_id=None,
            ordinal=2,
            kind="heading",
            text="Deployment",
            heading_path=["Deployment"],
            locators=[{"kind": "section", "label": "Deployment", "line": 3}],
            source_fragment_hash="c" * 64,
        ),
    ]


def _taxonomy(blocks: list[IRBlock]):
    engine = TaxonomyEngine()
    proposal = engine.propose(
        blocks,
        goal="Operate the service",
        project_revision="project-1",
        ir_revision="ir-1",
        proposal={
            "nodes": [
                {
                    "node_id": "auth",
                    "concept_id": "auth",
                    "owner": "auth",
                    "title": "Authentication",
                    "coverage": ["auth", "auth-body"],
                },
                {
                    "node_id": "deployment",
                    "concept_id": "deployment",
                    "owner": "deployment",
                    "title": "Deployment",
                    "coverage": ["deploy"],
                },
            ]
        },
    )
    return engine.approve(proposal, {"approved": True, "actor": "fixture"})


def test_synthesis_generates_multiple_budgeted_skills_with_lineage() -> None:
    blocks = _blocks()
    result = SynthesisEngine().generate(_taxonomy(blocks), blocks, language="pt-BR", budget={"max_tokens": 80})

    assert result.status == "ready"
    assert {skill.slug for skill in result.skills} == {"auth", "deployment"}
    assert all(skill.token_count <= 80 for skill in result.skills)
    assert all(skill.lineage for skill in result.skills)
    assert "token" in result.skills[0].markdown
    assert result.receipt.request_hash
    assert result.receipt.adapter["execution"] == "contract-fixture"


def test_synthesis_rejects_claim_without_supported_lineage() -> None:
    blocks = _blocks()
    taxonomy = _taxonomy(blocks)
    engine = SynthesisEngine()
    with pytest.raises(SynthesisError) as caught:
        engine.submit(
            request=engine.prepare(taxonomy, blocks, language="en"),
            output={
                "skills": [
                    {
                        "topic_id": "auth",
                        "slug": "auth",
                        "markdown": "# Authentication\n\nAn unsupported fact.",
                        "claims": [{"claim_id": "c1", "text": "An unsupported fact.", "lineage": []}],
                    },
                    {"topic_id": "deployment", "slug": "deployment", "markdown": "# Deployment", "claims": []},
                ]
            },
        )
    assert caught.value.code == "lineage_required"


def test_synthesis_rejects_lineage_outside_the_topic_projection() -> None:
    blocks = _blocks()
    taxonomy = _taxonomy(blocks)
    engine = SynthesisEngine()

    with pytest.raises(SynthesisError) as caught:
        engine.submit(
            request=engine.prepare(taxonomy, blocks, language="en"),
            output={
                "skills": [
                    {
                        "topic_id": "auth",
                        "slug": "auth",
                        "markdown": "# Authentication\n\nDeployment is automatic.",
                        "claims": [
                            {
                                "claim_id": "cross-topic",
                                "text": "Deployment is automatic.",
                                "lineage": [{"block_id": "deploy"}],
                            }
                        ],
                    },
                    {"topic_id": "deployment", "slug": "deployment", "markdown": "# Deployment", "claims": []},
                ]
            },
        )

    assert caught.value.code == "lineage_invalid"


def test_synthesis_rejects_an_unsafe_external_skill_slug() -> None:
    blocks = _blocks()
    taxonomy = _taxonomy(blocks)
    engine = SynthesisEngine()

    with pytest.raises(SynthesisError) as caught:
        engine.submit(
            request=engine.prepare(taxonomy, blocks, language="en"),
            output={
                "skills": [
                    {
                        "topic_id": "auth",
                        "slug": "../../escaped",
                        "markdown": "# Authentication",
                        "claims": [],
                    },
                    {"topic_id": "deployment", "slug": "deployment", "markdown": "# Deployment", "claims": []},
                ]
            },
        )

    assert caught.value.code == "output_invalid"


def test_synthesis_rejects_unsafe_external_chapter_paths() -> None:
    blocks = _blocks()
    taxonomy = _taxonomy(blocks)
    engine = SynthesisEngine()

    with pytest.raises(SynthesisError) as caught:
        engine.submit(
            request=engine.prepare(taxonomy, blocks, language="en"),
            output={
                "skills": [
                    {
                        "topic_id": "auth",
                        "slug": "auth",
                        "markdown": "# Authentication",
                        "chapters": {"../../outside.md": "unsafe"},
                        "claims": [],
                    },
                    {"topic_id": "deployment", "slug": "deployment", "markdown": "# Deployment", "claims": []},
                ]
            },
        )

    assert caught.value.code == "output_invalid"


def test_synthesis_retry_is_idempotent_and_conflicting_payload_fails() -> None:
    blocks = _blocks()
    taxonomy = _taxonomy(blocks)
    engine = SynthesisEngine()
    request = engine.prepare(taxonomy, blocks, language="en", request_id="synth-1")
    first = engine.submit(request)
    assert engine.submit(request).receipt.output_hash == first.receipt.output_hash
    with pytest.raises(SynthesisError) as caught:
        engine.submit(engine.prepare(taxonomy, blocks[:1], language="en", request_id="synth-1"))
    assert caught.value.code == "idempotency_conflict"
