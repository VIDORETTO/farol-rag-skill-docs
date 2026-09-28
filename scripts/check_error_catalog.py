"""Check that every public error code is catalogued and that docs/ERRORS.md is current."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from docops.errors import CATALOG  # noqa: E402

PUBLIC_MODULES = [
    "docops/journey.py",
    "docops/library.py",
    "docops/connect.py",
    "docops/agent_tasks.py",
    "docops/transcripts.py",
    "docops/mcp_server.py",
    "docops/package_index.py",
    "docops/backends/local_fts.py",
    "docops/backends/semantic.py",
    "docops/errors.py",
]
_RAISED = re.compile(
    r"(?:JourneyError|ConnectError|SynthesisTaskError|TranscriptError|ToolError|BackendError|BackendUnavailable"
    r"|_reason)\(\s*\"([a-z_]+)\"",
    re.S,
)
_ERROR_CODE = re.compile(r"\"code\":\s*\"([a-z_]+)\"")
DOC = ROOT / "docs" / "ERRORS.md"


def raised_codes(paths: Iterable[Path]) -> dict[str, str]:
    codes: dict[str, str] = {}
    for path in paths:
        text = Path(path).read_text(encoding="utf-8")
        if Path(path).name == "errors.py":
            continue
        for pattern in (_RAISED, _ERROR_CODE):
            for code in pattern.findall(text):
                codes.setdefault(code, Path(path).name)
    return codes


def check_catalog(paths: Iterable[Path] | None = None) -> dict[str, Any]:
    selected = [ROOT / path for path in PUBLIC_MODULES] if paths is None else list(paths)
    codes = raised_codes(selected)
    findings = [
        {"code": code, "path": where, "message": "error code is not in docops/errors.py CATALOG"}
        for code, where in sorted(codes.items())
        if code not in CATALOG
    ]
    return {"ok": not findings, "codes": len(codes), "findings": findings}


def render_markdown() -> str:
    lines = [
        "# Error reference",
        "",
        "Generated from `docops/errors.py` by `python scripts/check_error_catalog.py --write`.",
        "Every error printed by Farol carries one of these codes and a next step.",
        "",
        "| Code | What happened | What to do |",
        "|---|---|---|",
    ]
    for code, info in sorted(CATALOG.items()):
        lines.append(f"| `{code}` | {info.title} | `{info.next_action}` |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="regenerate docs/ERRORS.md")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = check_catalog()
    expected = render_markdown()
    if args.write:
        DOC.write_text(expected, encoding="utf-8")
    elif not DOC.is_file() or DOC.read_text(encoding="utf-8") != expected:
        report["ok"] = False
        report["findings"].append({"code": "errors_doc_stale", "path": "docs/ERRORS.md", "message": "run with --write"})
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
