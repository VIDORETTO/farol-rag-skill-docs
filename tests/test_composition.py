# seam-scope: implementation-infrastructure (public composition boundary fixtures)
from __future__ import annotations

import pytest

from docops.composition import CompositionError, CompositionManager


def _components() -> dict[str, object]:
    return {
        "project_revision": "project-1",
        "ir_revision": "ir-1",
        "taxonomy_revision": "taxonomy-1",
        "skill_revisions": ["skill-auth"],
        "router_revision": "router-1",
        "index_revision": "index-1",
    }


def test_factual_composition_promotes_atomically_and_rolls_back(tmp_path) -> None:
    manager = CompositionManager(tmp_path)
    candidate = manager.prepare(_components(), impact="factual")
    manager.evaluate(candidate, gates={"lineage": True, "citations": True})
    promoted = manager.promote(candidate)

    assert promoted.status == "active"
    assert manager.active_revision == promoted.composition_id
    rollback = manager.rollback()
    assert rollback.status == "rolled_back"
    assert manager.active_revision is None


def test_conceptual_change_requires_approval_and_cas(tmp_path) -> None:
    manager = CompositionManager(tmp_path)
    candidate = manager.prepare(_components(), impact="conceptual")
    manager.evaluate(candidate, gates={"lineage": True})
    with pytest.raises(CompositionError) as missing:
        manager.promote(candidate)
    assert missing.value.code == "approval_required"
    with pytest.raises(CompositionError) as stale:
        manager.promote(candidate, approval={"approved": True}, expected_active="other")
    assert stale.value.code == "stale_revision"
    assert manager.promote(candidate, approval={"approved": True}).status == "active"


def test_interrupted_promotion_recovers_previous_whole_composition(tmp_path) -> None:
    manager = CompositionManager(tmp_path)
    first = manager.prepare(_components(), impact="factual")
    manager.evaluate(first, gates={"lineage": True})
    manager.promote(first)
    second_parts = {**_components(), "ir_revision": "ir-2", "index_revision": "index-2"}
    second = manager.prepare(second_parts, impact="factual")
    manager.evaluate(second, gates={"lineage": True})
    with pytest.raises(CompositionError) as interrupted:
        manager.promote(second, fail_after_journal=True)
    assert interrupted.value.code == "promotion_interrupted"
    recovered = manager.recover()
    assert recovered.status == "recovered"
    assert manager.active_revision == first.composition_id
