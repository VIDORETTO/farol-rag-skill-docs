# seam-scope: implementation-infrastructure (public backend contract fixtures)
from __future__ import annotations

from docops.backends import BackendCandidate, EvidenceResult, IndexRevision, QueryRequest, SnapshotIdentity
from docops.contracts import validate_artifact
from docops.revisions import content_hash


def test_backend_dtos_use_canonical_identity_not_external_ids() -> None:
    candidate = BackendCandidate(
        candidate_id="candidate-1",
        project_revision="project-1",
        ir_revision="ir-1",
        backend="ragflow",
        state="prepared",
    )
    index = IndexRevision(
        index_revision="index-1",
        project_revision="project-1",
        ir_revision="ir-1",
        backend="ragflow",
        backend_version="0.27.2",
        state="queryable",
        mapping_hash=content_hash({"canonical": "block-1"}),
        external_ids={"dataset": "opaque-dataset-id"},
    )
    evidence = EvidenceResult(
        index_revision=index.index_revision,
        query=QueryRequest(query="guide", top_k=1, project_revision="project-1"),
        hits=[{"block_id": "block-1", "source": "guide.md", "locator": {"kind": "line", "label": "1"}}],
    )
    snapshot = SnapshotIdentity(
        snapshot_id="snapshot-1",
        index_revision=index.index_revision,
        content_hash=content_hash(index.to_dict()),
    )

    assert candidate.to_dict()["candidate_id"] == "candidate-1"
    assert index.to_dict()["external_ids"] == {"dataset": "opaque-dataset-id"}
    assert evidence.to_dict()["hits"][0]["block_id"] == "block-1"
    assert snapshot.to_dict()["content_hash"] == content_hash(index.to_dict())
    assert validate_artifact("backend-candidate", candidate.to_dict()).ok
    assert validate_artifact("index-revision", index.to_dict()).ok
    assert validate_artifact("query-request-v2", evidence.query.to_dict()).ok
    assert validate_artifact("evidence-result-v2", evidence.to_dict()).ok
