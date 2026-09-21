# seam-scope: implementation-infrastructure (public project v2 boundary fixtures)
from __future__ import annotations

import json

import pytest

from docops.__main__ import main
from docops.project import ProjectError, ProjectService


def _source() -> dict[str, str]:
    return {
        "source_id": "source-guide",
        "canonical": "file:///private/guide.md",
        "source_revision": "rev-1",
        "rights": "MIT",
        "privacy": "private",
        "language": "en",
        "purpose": "knowledge",
        "status": "proposed",
    }


def test_project_start_is_resumable_and_idempotent(tmp_path) -> None:
    service = ProjectService(tmp_path)
    first = service.start("Guide", "Operate the service", [_source()], idempotency_key="start-1")
    resumed = service.start("Guide", "Operate the service", [_source()], idempotency_key="start-1")

    assert first.to_dict() == resumed.to_dict()
    assert first.status == "needs_input"
    assert first.pending
    assert service.inspect().project_id == first.project_id


def test_project_rejects_stale_apply_and_conflicting_idempotency(tmp_path) -> None:
    service = ProjectService(tmp_path)
    service.start("Guide", "Goal", [_source()], idempotency_key="start")
    with pytest.raises(ProjectError) as stale:
        service.apply("start", {}, expected_revision=99, idempotency_key="apply")
    assert stale.value.code == "revision_conflict"
    with pytest.raises(ProjectError) as conflict:
        service.start("Other", "Different", [_source()], idempotency_key="start")
    assert conflict.value.code == "idempotency_conflict"
    with pytest.raises(ProjectError) as missing:
        service.apply("plan", {}, expected_revision=1, idempotency_key="")
    assert missing.value.code == "idempotency_required"


def test_project_v2_cli_uses_canonical_v2_hierarchy(tmp_path, capsys) -> None:
    sources = tmp_path / "sources.json"
    sources.write_text(json.dumps({"sources": [_source()]}), encoding="utf-8")
    project = tmp_path / "project"

    assert (
        main(
            [
                "v2",
                "start",
                "--project",
                str(project),
                "--name",
                "Guide",
                "--objective",
                "Goal",
                "--sources",
                str(sources),
                "--idempotency-key",
                "start-1",
                "--json",
            ]
        )
        == 2
    )
    started = json.loads(capsys.readouterr().out)
    assert started["kind"] == "operation_result"

    assert main(["v2", "inspect", "--project", str(project), "--json"]) == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["kind"] == "knowledge_project"
