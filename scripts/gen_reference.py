"""Generate docs/reference/cli.md and docs/reference/mcp.md from the code (--check verifies)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from docops.__main__ import _JOURNEY_COMMANDS, build_parser  # noqa: E402
from docops.mcp_server import TOOLS  # noqa: E402

OUTPUT = ROOT / "docs" / "reference"


COMMON_HELP = {
    "--project": "project directory (default: current directory)",
    "--package": "a package directory, or a project directory",
    "--json": "print machine-readable JSON",
    "--root": "directory to inspect (default: current directory)",
    "source": "folder, file, URL, Git repository, arXiv:<id> or YouTube link",
    "--redistribution": "how derived content may be shared",
    "task_id": "task id shown by farol task next",
    "output_dir": "directory with the answer files",
    "name": "project name in the library",
    "project": "project directory (default: current directory)",
    "harness": "the AI agent to configure",
    "--language": "language of the generated skills, e.g. en or pt-BR",
}


def _arguments(parser: argparse.ArgumentParser) -> list[str]:
    lines = []
    for action in parser._actions:
        if isinstance(action, (argparse._HelpAction, argparse._SubParsersAction)):
            continue
        name = ", ".join(action.option_strings) if action.option_strings else f"<{action.dest}>"
        key = action.option_strings[0] if action.option_strings else action.dest
        text = action.help or COMMON_HELP.get(key, "")
        choices = f" (one of: {', '.join(map(str, action.choices))})" if action.choices else ""
        lines.append(f"| `{name}` | {text.replace('|', '/')}{choices} |")
    return lines


def cli_markdown() -> str:
    parser = build_parser()
    action = next(item for item in parser._actions if isinstance(item, argparse._SubParsersAction))
    helps = parser.get_default("_command_help")
    out = [
        "# CLI reference",
        "",
        "Generated from the code by `python scripts/gen_reference.py`. `docops` is an alias of `farol`;",
        "run `farol advanced` for lifecycle and compatibility commands.",
        "",
    ]
    for name in _JOURNEY_COMMANDS:
        sub = action.choices[name]
        out += [f"## farol {name}", "", helps.get(name, ""), ""]
        nested = next((item for item in sub._actions if isinstance(item, argparse._SubParsersAction)), None)
        targets = [(f"farol {name} {child}", parser_) for child, parser_ in nested.choices.items()] if nested else []
        rows = _arguments(sub)
        if rows:
            out += ["| Argument | Description |", "|---|---|", *rows, ""]
        for label, target in targets:
            out += [f"### {label}", ""]
            child_rows = _arguments(target)
            out += ["| Argument | Description |", "|---|---|", *child_rows, ""] if child_rows else ["No arguments.", ""]
    return "\n".join(out).rstrip() + "\n"


def mcp_markdown() -> str:
    out = [
        "# MCP tools reference",
        "",
        "Generated from the code by `python scripts/gen_reference.py`. The `farol` server speaks MCP over",
        "stdio (protocol versions 2025-06-18, 2025-03-26 and 2024-11-05) and is read-only.",
        "",
    ]
    for tool in TOOLS:
        out += [f"## {tool['name']}", "", tool["description"], ""]
        properties = tool["inputSchema"].get("properties", {})
        required = set(tool["inputSchema"].get("required", []))
        if properties:
            out += ["| Parameter | Type | Required | Description |", "|---|---|---|---|"]
            for key, spec in properties.items():
                out.append(
                    f"| `{key}` | {spec.get('type', '')} | {'yes' if key in required else 'no'} | {spec.get('description', '')} |"
                )
            out.append("")
        else:
            out += ["No parameters.", ""]
    return "\n".join(out).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    expected = {OUTPUT / "cli.md": cli_markdown(), OUTPUT / "mcp.md": mcp_markdown()}
    stale = [
        str(path.relative_to(ROOT))
        for path, text in expected.items()
        if not path.is_file() or path.read_text(encoding="utf-8") != text
    ]
    if args.check:
        print("ok" if not stale else "stale: " + ", ".join(stale) + " (run scripts/gen_reference.py)")
        return 0 if not stale else 1
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for path, text in expected.items():
        path.write_text(text, encoding="utf-8")
    print("written: " + ", ".join(str(path.relative_to(ROOT)) for path in expected))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
