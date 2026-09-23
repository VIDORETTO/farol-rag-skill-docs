# seam-scope: implementation-infrastructure (public migration boundary fixtures)
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from docops.contracts import validate_artifact
from docops.migration import MigrationError, apply_migration, inspect_legacy_package, plan_migration, rollback_migration


def _legacy(tmp_path: Path) -> Path:
    root = tmp_path / "legacy"
    (root / "skill" / "chapters").mkdir(parents=True)
    (root / "rag" / "documents").mkdir(parents=True)
    (root / "skill" / "SKILL.md").write_text("# Legacy skill\n", encoding="utf-8")
    (root / "skill" / "chapters" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (root / "rag" / "documents" / "guide.md").write_text("literal", encoding="utf-8")
    (root / "manifest.json").write_text(
        json.dumps({"schema_version": 1, "version": "1.1.0", "slug": "legacy"}), encoding="utf-8"
    )
    (root / "project.json").write_text(json.dumps({"project_id": "legacy-project", "name": "Legacy"}), encoding="utf-8")
    (root / "course.json").write_text("excluded", encoding="utf-8")
    (root / "page.json").write_text("excluded", encoding="utf-8")
    (root / "offer.json").write_text("excluded", encoding="utf-8")
    return root


def test_migration_inspect_plan_and_apply_preserve_origin_and_exclusions(tmp_path: Path) -> None:
    source = _legacy(tmp_path)
    report = inspect_legacy_package(source)
    plan = plan_migration(report, destination_project_id="project-v2")

    assert {item["path"] for item in plan.imported} >= {"skill/SKILL.md", "manifest.json"}
    assert {item["reason"] for item in plan.excluded} >= {"editorial_surface_excluded", "legacy_index_not_authority"}
    before = hashlib.sha256((source / "manifest.json").read_bytes()).hexdigest()
    destination = tmp_path / "v2"
    result = apply_migration(plan, destination)

    assert result.status == "promoted"
    assert (destination / "skills" / "project-v2" / "SKILL.md").is_file()
    assert not (destination / "rag").exists()
    project = json.loads((destination / "project.json").read_text(encoding="utf-8"))
    assert validate_artifact("knowledge-project-v2", project).ok
    assert hashlib.sha256((source / "manifest.json").read_bytes()).hexdigest() == before
    assert (destination / ".docops" / "migration.json").is_file()


def test_migration_dry_run_and_stale_plan_are_safe(tmp_path: Path) -> None:
    source = _legacy(tmp_path)
    plan = plan_migration(inspect_legacy_package(source), destination_project_id="project-v2", mode="dry-run")
    destination = tmp_path / "dry"
    result = apply_migration(plan, destination)
    assert result.status == "planned"
    assert not destination.exists()

    (source / "manifest.json").write_text("changed", encoding="utf-8")
    stale_plan = plan_migration(inspect_legacy_package(_legacy(tmp_path / "other")), destination_project_id="other")
    # Use the old source with a deliberately stale identity.
    stale_plan = type(plan)(**{**stale_plan.__dict__, "source_identity": plan.source_identity})
    with pytest.raises(MigrationError) as caught:
        apply_migration(stale_plan, tmp_path / "stale")
    assert caught.value.code == "source_changed"


def test_migration_rollback_moves_candidate_to_recoverable_backup(tmp_path: Path) -> None:
    source = _legacy(tmp_path)
    plan = plan_migration(inspect_legacy_package(source), destination_project_id="project-v2")
    destination = tmp_path / "v2"
    apply_migration(plan, destination)
    receipt = rollback_migration(destination)
    assert receipt.status == "rolled_back"
    assert not destination.exists()
    assert Path(receipt.rollback_ref).is_dir()
