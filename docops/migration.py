"""Read-only inspection and staged migration from Farol 1.x packages."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .api_types import KnowledgeProjectV2, MigrationPlanV2
from .revisions import content_hash
from .storage import write_json_atomic


class MigrationError(RuntimeError):
    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(message)


@dataclass(frozen=True)
class LegacyInspection:
    source_path: str
    source_identity: dict[str, Any]
    version: str
    entries: list[dict[str, Any]]
    errors: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "kind": "legacy_inspection",
            "source_path": self.source_path,
            "source_identity": self.source_identity,
            "version": self.version,
            "entries": self.entries,
            "errors": self.errors,
        }


@dataclass(frozen=True)
class MigrationReceipt:
    status: str
    migration_id: str
    destination: str | None = None
    plan_hash: str | None = None
    rollback_ref: str | None = None
    imported: list[str] | None = None
    excluded: list[dict[str, Any]] | None = None
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "kind": "migration_receipt",
            "status": self.status,
            "migration_id": self.migration_id,
            "destination": self.destination,
            "plan_hash": self.plan_hash,
            "rollback_ref": self.rollback_ref,
            "imported": list(self.imported or []),
            "excluded": list(self.excluded or []),
            "message": self.message,
        }


def inspect_legacy_package(source: Path | str) -> LegacyInspection:
    root = Path(source).expanduser().resolve()
    if not root.is_dir() or root.is_symlink():
        raise MigrationError("invalid_source", "legacy package must be a regular directory")
    manifest = _read_json(root / "manifest.json")
    version = str(manifest.get("version") or manifest.get("package_version") or manifest.get("schema_version") or "1.x")
    entries: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        category, reason = _classify(relative)
        entries.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "category": category,
                "rights": "unknown",
                "reason": reason,
            }
        )
    source_identity = {
        "path_name": root.name,
        "manifest_hash": hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest()
        if (root / "manifest.json").is_file()
        else None,
        "tree_hash": content_hash({entry["path"]: entry["sha256"] for entry in entries}),
    }
    return LegacyInspection(root.as_posix(), source_identity, version, entries, [])


def plan_migration(
    inspection: LegacyInspection,
    *,
    destination_project_id: str,
    mode: str = "plan",
    migration_id: str | None = None,
) -> MigrationPlanV2:
    if mode not in {"plan", "dry-run", "apply"}:
        raise MigrationError("mode_invalid", "migration mode must be plan, dry-run or apply")
    imported: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for entry in inspection.entries:
        if entry["category"] == "import":
            imported.append({"path": entry["path"], "sha256": entry["sha256"], "rights": entry["rights"]})
        else:
            excluded.append(
                {
                    "path": entry["path"],
                    "reason": entry["reason"],
                    "sha256": entry["sha256"],
                }
            )
    payload = {
        "source_identity": inspection.source_identity,
        "source_version": inspection.version,
        "destination_project_id": destination_project_id,
        "mode": mode,
        "imported": imported,
        "excluded": excluded,
    }
    plan_hash = content_hash(payload)
    return MigrationPlanV2(
        migration_id=migration_id or f"migration-{plan_hash[:24]}",
        source_version=inspection.version,
        source_identity={**inspection.source_identity, "source_path": inspection.source_path},
        destination_project_id=destination_project_id,
        plan_hash=plan_hash,
        mode=mode,
        imported=imported,
        excluded=excluded,
        status="planned",
        warnings=["rights unknown remains unknown until an operator authorizes the source"],
    )


def apply_migration(plan: MigrationPlanV2, destination: Path | str) -> MigrationReceipt:
    if plan.mode == "dry-run":
        return MigrationReceipt(
            "planned",
            plan.migration_id,
            plan_hash=plan.plan_hash,
            imported=[item["path"] for item in plan.imported],
            excluded=plan.excluded,
        )
    source_value = plan.source_identity.get("source_path")
    if not isinstance(source_value, str):
        raise MigrationError("invalid_plan", "migration plan has no source path")
    source = Path(source_value)
    if not source.is_dir() or source.is_symlink():
        raise MigrationError("invalid_source", "migration source is unavailable")
    try:
        current = inspect_legacy_package(source)
    except MigrationError as exc:
        raise MigrationError("source_changed", "legacy source can no longer be inspected") from exc
    if current.source_identity.get("tree_hash") != plan.source_identity.get("tree_hash"):
        raise MigrationError("source_changed", "legacy source changed after the migration plan")
    destination_path = Path(destination).expanduser().resolve()
    if destination_path.exists():
        existing = destination_path / ".docops" / "migration.json"
        try:
            payload = json.loads(existing.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            payload = {}
        if payload.get("plan_hash") == plan.plan_hash:
            return MigrationReceipt("promoted", plan.migration_id, destination_path.as_posix(), plan.plan_hash)
        raise MigrationError("destination_exists", "migration destination already exists")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination_path.name}.migration-", dir=destination_path.parent))
    try:
        _write_staging(plan, source, staging)
        staging_docops = staging / ".docops"
        staging_docops.mkdir(exist_ok=True)
        write_json_atomic(staging_docops / "migration.json", {**plan.to_dict(), "source_path": source.as_posix()})
        staging.rename(destination_path)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return MigrationReceipt(
        "promoted",
        plan.migration_id,
        destination_path.as_posix(),
        plan.plan_hash,
        imported=[item["path"] for item in plan.imported],
        excluded=plan.excluded,
    )


def rollback_migration(destination: Path | str) -> MigrationReceipt:
    root = Path(destination).expanduser().resolve()
    if not root.is_dir() or root.is_symlink():
        raise MigrationError("destination_missing", "migration destination is unavailable")
    migration = root / ".docops" / "migration.json"
    try:
        payload = json.loads(migration.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MigrationError("receipt_missing", "migration receipt is unavailable") from exc
    backup = root.with_name(f"{root.name}.rollback-{content_hash(payload)[:12]}")
    if backup.exists():
        raise MigrationError("rollback_exists", "rollback backup already exists")
    root.rename(backup)
    return MigrationReceipt(
        "rolled_back",
        str(payload.get("migration_id") or "migration-unknown"),
        destination=root.as_posix(),
        plan_hash=payload.get("plan_hash") if isinstance(payload.get("plan_hash"), str) else None,
        rollback_ref=backup.as_posix(),
    )


def _classify(relative: str) -> tuple[str, str | None]:
    first = relative.split("/", 1)[0].casefold()
    if first in {"course", "courses", "page", "pages", "offer", "offers"} or Path(relative).name.casefold() in {
        "course.json",
        "page.json",
        "offer.json",
    }:
        return "exclude", "editorial_surface_excluded"
    if relative.startswith("rag/") or relative.startswith("data/") or "chroma" in relative.casefold():
        return "exclude", "legacy_index_not_authority"
    if (
        relative.startswith("skill/")
        or relative.startswith("router/")
        or relative
        in {
            "manifest.json",
            "project.json",
        }
        or relative.startswith("sources/")
    ):
        return "import", None
    return "exclude", "unmapped_legacy_artifact"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MigrationError("invalid_source", f"could not read {path.name}") from exc
    return dict(value) if isinstance(value, Mapping) else {}


def _write_staging(plan: MigrationPlanV2, source: Path, staging: Path) -> None:
    slug = _safe_slug(plan.destination_project_id)
    for item in plan.imported:
        relative = str(item["path"])
        original = source / relative
        if original.is_symlink() or not original.is_file():
            raise MigrationError("source_changed", f"imported source disappeared: {relative}")
        if relative.startswith("skill/"):
            destination = staging / "skills" / slug / Path(relative).relative_to("skill")
        elif relative.startswith("router/"):
            destination = staging / "router" / Path(relative).relative_to("router")
        else:
            destination = staging / "sources" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, destination)
    sources = [
        {
            "source_id": f"migrated-{content_hash(item['path'])[:16]}",
            "canonical": f"legacy://{item['path']}",
            "source_revision": str(item.get("sha256") or "unknown"),
            "status": "proposed",
            "rights": str(item.get("rights") or "unknown"),
            "privacy": "unknown",
            "language": "und",
            "purpose": "knowledge",
            "version": None,
            "region": None,
        }
        for item in plan.imported
        if str(item.get("path", "")).startswith("sources/")
    ]
    project = KnowledgeProjectV2(
        project_id=plan.destination_project_id,
        session_id=f"migration:{plan.migration_id}",
        revision=1,
        name=plan.destination_project_id,
        objective="migrated from Farol 1.x",
        sources=sources,
        status="staging",
        extensions={"migration_id": plan.migration_id, "source_version": plan.source_version},
    )
    write_json_atomic(staging / "project.json", project.to_dict())


def _safe_slug(value: str) -> str:
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "migrated-project"
