# seam-scope: public-seam (S1: `farol connect <harness>`)
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _cli(cwd: Path, *args: str) -> tuple[int, Any]:
    completed = subprocess.run(
        [sys.executable, "-m", "docops", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=cwd,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        timeout=120,
    )
    try:
        return completed.returncode, json.loads(completed.stdout)
    except json.JSONDecodeError:
        return completed.returncode, completed.stdout + completed.stderr


def _project(tmp_path: Path) -> Path:
    source = tmp_path / "acme-docs"
    source.mkdir()
    (source / "guide.md").write_text("# Acme\n\n## Retries\n\nThe client retries 5 times.\n", encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    _cli(project, "add", str(source), "--license", "MIT")
    code, built = _cli(project, "build", "--json")
    assert code == 0, built
    return project


def test_dry_run_shows_every_change_without_writing(tmp_path: Path) -> None:
    project = _project(tmp_path)
    target = tmp_path / "repo"
    target.mkdir()

    code, plan = _cli(project, "connect", "claude-code", "--target", str(target), "--dry-run", "--json")

    assert code == 0
    paths = {change["path"] for change in plan["changes"]}
    assert ".mcp.json" in paths and ".claude/skills/acme-docs/SKILL.md" in paths
    assert not (target / ".mcp.json").exists() and not (target / ".claude").exists()


def test_connect_is_idempotent_preserves_other_servers_and_removes_cleanly(tmp_path: Path) -> None:
    project = _project(tmp_path)
    target = tmp_path / "repo"
    target.mkdir()
    original = '{\n  "mcpServers": {"other": {"type": "stdio", "command": "other-server"}}\n}\n'
    (target / ".mcp.json").write_text(original, encoding="utf-8")

    code, first = _cli(project, "connect", "claude-code", "--target", str(target), "--json")
    _, second = _cli(project, "connect", "claude-code", "--target", str(target), "--json")
    config = json.loads((target / ".mcp.json").read_text(encoding="utf-8"))

    assert code == 0 and first["status"] == "connected" and second["status"] == "unchanged"
    assert config["mcpServers"]["other"]["command"] == "other-server"
    server = config["mcpServers"]["farol"]
    assert server["type"] == "stdio" and server["args"][-2:] == ["--project", str(project.resolve())]
    assert (target / ".claude" / "skills" / "acme-docs" / "SKILL.md").is_file()
    assert (target / ".claude" / "skills" / "acme-docs-router" / "SKILL.md").is_file()

    code, removed = _cli(project, "connect", "claude-code", "--target", str(target), "--remove", "--json")

    assert code == 0 and removed["status"] == "removed"
    assert (target / ".mcp.json").read_text(encoding="utf-8") == original
    assert not (target / ".claude" / "skills" / "acme-docs").exists()


def test_codex_gets_a_managed_toml_block_next_to_existing_settings(tmp_path: Path) -> None:
    project = _project(tmp_path)
    target = tmp_path / "repo"
    (target / ".codex").mkdir(parents=True)
    original = 'model = "gpt-5"\n\n[mcp_servers.other]\ncommand = "other"\n'
    (target / ".codex" / "config.toml").write_text(original, encoding="utf-8")

    code, _ = _cli(project, "connect", "codex", "--target", str(target), "--json")

    text = (target / ".codex" / "config.toml").read_text(encoding="utf-8")
    import tomllib

    parsed = tomllib.loads(text)
    assert code == 0 and parsed["model"] == "gpt-5" and parsed["mcp_servers"]["other"]["command"] == "other"
    assert parsed["mcp_servers"]["farol"]["args"][:3] == ["-m", "docops", "mcp"]
    assert (target / ".agents" / "skills" / "acme-docs" / "SKILL.md").is_file()
    _cli(project, "connect", "codex", "--target", str(target), "--remove", "--json")
    assert (target / ".codex" / "config.toml").read_text(encoding="utf-8") == original


def test_cursor_opencode_and_generic_targets(tmp_path: Path) -> None:
    project = _project(tmp_path)
    target = tmp_path / "repo"
    target.mkdir()

    _cli(project, "connect", "cursor", "--target", str(target), "--json")
    _cli(project, "connect", "opencode", "--target", str(target), "--json")
    code, generic = _cli(project, "connect", "generic", "--json")

    cursor = json.loads((target / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
    assert cursor["mcpServers"]["farol"]["type"] == "stdio"
    assert "farol" in (target / ".cursor" / "rules" / "farol.mdc").read_text(encoding="utf-8")
    opencode = json.loads((target / "opencode.json").read_text(encoding="utf-8"))
    assert opencode["mcp"]["farol"]["type"] == "local" and opencode["mcp"]["farol"]["command"][1:3] == ["-m", "docops"]
    assert (target / ".opencode" / "skills" / "acme-docs" / "SKILL.md").is_file()
    assert code == 0 and generic["mcpServers"]["farol"]["command"]
