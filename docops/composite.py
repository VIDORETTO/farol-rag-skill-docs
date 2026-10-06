"""Thematic skills distilled from several sources (TK-211, decision D-304).

A composite skill lives in ``packages/@<name>/``: a ``manifest.json`` of kind
``composite`` naming its member sources, the synthesis plan and, once
accepted, ``skill/``. It has no index of its own; evidence stays in the
members. Its synthesis tasks read the members' blocks, so every statement is
traced to a member package and block.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .storage import write_json_atomic

PREFIX = "@"


def composite_dir(project_root: Path, name: str) -> Path:
    return project_root / "packages" / f"{PREFIX}{name}"


def is_composite(package: Path) -> bool:
    manifest = package / "manifest.json"
    try:
        return json.loads(manifest.read_text(encoding="utf-8")).get("kind") == "composite"
    except (OSError, ValueError):
        return False


def compose_skill(
    project_root: Path | str, name: str, members: list[str], *, language: str | None = None
) -> dict[str, Any]:
    """Register (or update) a composite skill over ``members`` and create its folder."""

    from .journey import JourneyError, load_project

    project = load_project(project_root)
    slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")[:48]
    if not slug:
        raise JourneyError("skill_name_invalid", "give the skill a name with letters or digits")
    known = {source["id"] for source in project.config["sources"]}
    unknown = [member for member in members if member not in known]
    if unknown or len(members) < 2:
        raise JourneyError(
            "composite_member_unknown",
            f"a composite skill needs at least two added sources; unknown: {', '.join(unknown) or 'none'}",
            next_action="farol add <source>, then farol skill compose <name> --from <id> <id>",
        )
    entry = {"name": slug, "sources": list(dict.fromkeys(members)), "language": language or project.config["language"]}
    skills = [item for item in project.config.get("skills", []) if item.get("name") != slug]
    project.config["skills"] = [*skills, entry]
    write_json_atomic(project.root / "farol.json", project.config)
    folder = composite_dir(project.root, slug)
    folder.mkdir(parents=True, exist_ok=True)
    write_json_atomic(
        folder / "manifest.json",
        {
            "schema_version": 1,
            "kind": "composite",
            "source": {"slug": slug, "language": entry["language"]},
            "members": entry["sources"],
        },
    )
    return {"status": "composed", "skill": entry, "package": folder.relative_to(project.root).as_posix()}


def member_packages(package: Path) -> dict[str, Path]:
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    return {member: package.parent / member for member in manifest.get("members", [])}


def member_documents(package: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The members' documents, with paths prefixed by the member id and blocks tagged with it."""

    from .package_index import package_documents

    documents: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for member, root in member_packages(package).items():
        if not (root / "manifest.json").is_file():
            skipped.append({"path": member, "code": "member_not_built"})
            continue
        found, missing = package_documents(root)
        skipped.extend({**item, "path": f"{member}/{item['path']}"} for item in missing)
        for document in found:
            documents.append(
                {
                    **document,
                    "path": f"{member}/{document['path']}",
                    "blocks": [{**block, "package": member} for block in document["blocks"]],
                }
            )
    return documents, skipped
