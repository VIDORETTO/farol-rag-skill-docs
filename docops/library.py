"""A personal library of Farol projects served by one MCP server.

The registry lives in ``~/.farol/library.json`` (``FAROL_HOME`` overrides the
folder) and only stores project paths the user added; it is never shared.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .journey import JourneyError, load_project, project_packages
from .storage import write_json_atomic


def _registry() -> Path:
    return Path(os.environ.get("FAROL_HOME") or Path.home() / ".farol") / "library.json"


def _load() -> dict[str, Any]:
    path = _registry()
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"schema_version": 1, "projects": []}


def add_project(root: Path | str) -> dict[str, Any]:
    project = load_project(root)
    registry = _load()
    path = str(project.root)
    if any(item["path"] == path for item in registry["projects"]):
        return {"status": "unchanged", "name": project.config["name"]}
    names = {item["name"] for item in registry["projects"]}
    name, counter = project.config["name"], 2
    while name in names:
        name, counter = f"{project.config['name']}-{counter}", counter + 1
    registry["projects"].append({"name": name, "path": path})
    write_json_atomic(_registry(), registry)
    return {"status": "added", "name": name}


def remove_project(name: str) -> dict[str, Any]:
    registry = _load()
    kept = [item for item in registry["projects"] if item["name"] != name and item["path"] != name]
    if len(kept) == len(registry["projects"]):
        raise JourneyError("library_unknown", f"no project named {name!r} in the library")
    registry["projects"] = kept
    write_json_atomic(_registry(), registry)
    return {"status": "removed", "name": name}


def list_projects() -> dict[str, Any]:
    projects = []
    for item in _load()["projects"]:
        try:
            sources = len(load_project(item["path"]).config["sources"])
            state = "ok"
        except (JourneyError, OSError, ValueError):
            sources, state = 0, "missing"
        projects.append({**item, "sources": sources, "state": state})
    return {"projects": projects}


def library_packages() -> dict[str, Path]:
    """Every built package of every registered project, named ``project/source``."""

    packages: dict[str, Path] = {}
    for item in _load()["projects"]:
        try:
            for source_id, path in project_packages(item["path"]).items():
                packages[f"{item['name']}/{source_id}"] = path
        except (JourneyError, OSError, ValueError):
            continue
    return packages
