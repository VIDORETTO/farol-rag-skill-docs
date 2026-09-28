# seam-scope: implementation-infrastructure (harness unit tests)
from __future__ import annotations

import json
from pathlib import Path

from docops.harness import build_harness_manifest, write_harness_manifest


def test_harness_manifest_uses_only_relative_paths_and_no_author_machine_path(tmp_path: Path) -> None:
    payload = build_harness_manifest(tmp_path)

    assert payload["schema_version"] == 1
    assert payload["skills"] == ["skill", "router"]
    assert payload["backend"]["name"] == "ragflow"
    assert payload["backend"]["config"] == "config.yaml"
    assert payload["backend"]["cwd"] == "."
    assert "Users" not in json.dumps(payload)

    path = write_harness_manifest(tmp_path)
    assert path == tmp_path / "harness.json"
    assert json.loads(path.read_text(encoding="utf-8")) == payload


def test_harness_manifest_tells_the_agent_how_to_start_the_mcp_server(tmp_path: Path) -> None:
    from docops.contracts import validate_artifact
    from docops.mcp_server import TOOLS

    payload = build_harness_manifest(tmp_path)

    assert payload["mcp"] == {
        "name": "farol",
        "transport": "stdio",
        "command": "farol",
        "args": ["mcp", "--package", "."],
        "cwd": ".",
        "tools": sorted(tool["name"] for tool in TOOLS),
        "prerequisite": "farol index .",
    }
    assert validate_artifact("harness", payload).ok
    broken = {**payload, "mcp": {**payload["mcp"], "transport": "http"}}
    assert not validate_artifact("harness", broken).ok
