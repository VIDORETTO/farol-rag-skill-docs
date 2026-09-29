# seam-scope: implementation-infrastructure (Farol 3 public CLI seam: text encoding of stdio on legacy Windows code pages)
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(args: list[str], cwd: Path, stdin: str = "") -> subprocess.CompletedProcess[bytes]:
    # A legacy Windows code page on pipes, as GitHub's Windows runners and old consoles use.
    env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "cp1252", "FAROL_SEMANTIC": "0"}
    return subprocess.run(
        [sys.executable, "-m", "docops", *args],
        cwd=cwd,
        env=env,
        input=stdin.encode("utf-8"),
        capture_output=True,
        timeout=120,
    )


def test_cli_and_mcp_speak_utf8_whatever_the_code_page(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("# Guide — basics\n\nThe client retries 5 times → safely.\n", encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()

    added = _run(["add", str(docs), "--license", "MIT"], project)
    built = _run(["build"], project)
    handshake = [
        {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "t", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "search_knowledge", "arguments": {"query": "retries"}},
        },
    ]
    served = _run(["mcp", "--project", str(project)], project, "".join(json.dumps(m) + "\n" for m in handshake))

    assert added.returncode == 0, added.stdout.decode("utf-8", "replace")
    assert built.returncode == 0, built.stderr.decode("utf-8", "replace")
    responses = [json.loads(line) for line in served.stdout.decode("utf-8").splitlines() if line.strip()]
    assert "→" in json.dumps(responses[-1], ensure_ascii=False)
