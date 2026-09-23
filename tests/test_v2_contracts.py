# seam-scope: implementation-infrastructure (public JSON contract fixtures)
from __future__ import annotations

from docops.api_types import (
    CapabilityV2,
    KnowledgeProjectV2,
    MigrationPlanV2,
    OperationRequestV2,
    OperationResultV2,
)
from docops.contracts import validate_artifact, validate_contract


def _project_payload() -> dict[str, object]:
    return KnowledgeProjectV2(
        project_id="project-v2-fixture",
        session_id="session-v2-fixture",
        revision=0,
        name="Fixture project",
        objective="Preserve structured knowledge",
        sources=[
            {
                "source_id": "source-v2-fixture",
                "canonical": "fixture://source-v2",
                "source_revision": "source-revision-v2",
                "status": "proposed",
                "rights": "MIT",
                "privacy": "private",
                "language": "en",
                "purpose": "knowledge",
            }
        ],
    ).to_dict()


def test_v2_public_envelopes_validate_and_are_strict_outside_extensions() -> None:
    project = _project_payload()
    assert validate_artifact("knowledge-project-v2", project).ok

    request = OperationRequestV2(
        operation_id="operation-v2-fixture",
        project_id="project-v2-fixture",
        session_id="session-v2-fixture",
        operation="start",
        idempotency_key="idem-v2-fixture",
        expected_revision=0,
        inputs={"objective": "Preserve structured knowledge"},
    ).to_dict()
    result = OperationResultV2(
        operation_id=request["operation_id"],
        project_id=request["project_id"],
        idempotency_key=request["idempotency_key"],
        status="needs_input",
        revision=0,
        pending=[{"key": "rights", "required": True}],
        next_action="confirm source rights",
    ).to_dict()
    capability = CapabilityV2(
        name="fixture-extractor",
        version="1.0.0",
        status="available",
        supports=["text/markdown"],
        fidelity=["structured-native"],
        execution="local",
        permissions=[],
        dependencies=[],
    ).to_dict()

    assert validate_artifact("operation-v2", request).ok
    assert validate_artifact("operation-result-v2", result).ok
    assert validate_artifact("capability", capability).ok

    invalid = dict(request)
    invalid["unscoped_field"] = "must fail"
    contract = validate_artifact("operation-v2", invalid)
    assert not contract.ok
    assert any(error["code"] == "contract_additional_property" for error in contract.errors)


def test_validate_contract_distinguishes_version_revision_and_idempotency_conflicts() -> None:
    request = OperationRequestV2(
        operation_id="operation-v2-conflicts",
        project_id="project-v2-fixture",
        session_id="session-v2-fixture",
        operation="resume",
        idempotency_key="idem-v2-conflicts",
        expected_revision=3,
        inputs={"checkpoint": "checkpoint-1"},
    ).to_dict()

    version = validate_contract("operation-v2", {**request, "schema_version": 1})
    revision = validate_contract("operation-v2", request, expected_revision=4)
    idempotency = validate_contract(
        "operation-v2",
        {**request, "inputs": {"checkpoint": "checkpoint-2"}},
        existing_payload=request,
    )

    assert {error["code"] for error in version.errors} == {"schema_version_conflict"}
    assert {error["code"] for error in revision.errors} == {"revision_conflict"}
    assert {error["code"] for error in idempotency.errors} == {"idempotency_conflict"}


def test_migration_plan_requires_source_identity_and_reports_excluded_data() -> None:
    plan = MigrationPlanV2(
        migration_id="migration-v2-fixture",
        source_version="1.x",
        source_identity={"package_id": "legacy-fixture", "content_hash": "a" * 64},
        destination_project_id="project-v2-fixture",
        plan_hash="b" * 64,
        mode="dry-run",
        imported=[{"kind": "source", "id": "source-1", "target": "source-v2"}],
        excluded=[{"kind": "course", "id": "course-1", "reason": "editorial contract excluded"}],
        status="planned",
    ).to_dict()

    assert validate_artifact("migration-v2", plan).ok
    assert plan["source_identity"]["package_id"] == "legacy-fixture"
    assert plan["excluded"][0]["kind"] == "course"


def test_v2_dataclass_payloads_are_immutable() -> None:
    project = KnowledgeProjectV2(
        project_id="project-v2-fixture",
        session_id="session-v2-fixture",
        revision=0,
        name="Fixture",
        objective="Goal",
        sources=[],
    )
    try:
        project.project_id = "changed"  # type: ignore[misc]
    except AttributeError:
        pass
    else:
        raise AssertionError("v2 project envelope must be immutable")
