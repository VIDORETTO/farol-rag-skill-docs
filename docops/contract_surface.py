"""The public surface of Farol 3, extracted from the code.

`docs/PUBLIC-SURFACE-3.json` records it; tests fail when an item disappears
without a deprecation entry or when a new public item is not recorded. See
docs/COMPATIBILITY.md for the semver policy.
"""

from __future__ import annotations

import argparse
from typing import Any

PACKAGE_LAYOUT = [
    "manifest.json",
    "harness.json",
    "skill/SKILL.md",
    "skill/chapters/",
    "router/SKILL.md",
    "rag/documents/",
    "rag/sources.json",
    "rag/local-index/ACTIVE.json",
    ".docops/synthesis/lineage.json",
]
PROJECT_FILE_KEYS = [
    "schema_version",
    "name",
    "language",
    "sources[].id",
    "sources[].kind",
    "sources[].input",
    "sources[].license",
    "sources[].redistribution",
]
SEARCH_HIT_FIELDS = [
    "package",
    "citation",
    "text",
    "document_id",
    "source_id",
    "source_revision_id",
    "path",
    "heading_path",
    "locators",
    "risk",
    "score",
]


def _parser_surface() -> tuple[list[str], list[str]]:
    from .__main__ import build_parser

    parser = build_parser()
    action = next(item for item in parser._actions if isinstance(item, argparse._SubParsersAction))
    commands = sorted(action.choices)
    options: list[str] = []
    for name, sub in action.choices.items():
        nested = next((item for item in sub._actions if isinstance(item, argparse._SubParsersAction)), None)
        targets = [(name, sub)] + (
            [(f"{name} {child}", parser_) for child, parser_ in nested.choices.items()] if nested else []
        )
        for label, target in targets:
            for item in target._actions:
                options.extend(f"{label} {flag}" for flag in item.option_strings if flag.startswith("--"))
    return commands, sorted(set(options) - {f"{name} --help" for name in commands})


def current_surface() -> dict[str, list[str]]:
    import docops

    from .mcp_server import TOOLS

    commands, options = _parser_surface()
    return {
        "cli_commands": commands,
        "cli_options": sorted(option for option in options if not option.endswith(" --help")),
        "mcp_tools": sorted(tool["name"] for tool in TOOLS),
        "mcp_tool_params": sorted(
            f"{tool['name']}.{param}" for tool in TOOLS for param in tool["inputSchema"].get("properties", {})
        ),
        "mcp_search_hit_fields": sorted(SEARCH_HIT_FIELDS),
        "package_layout": sorted(PACKAGE_LAYOUT),
        "project_file_keys": sorted(PROJECT_FILE_KEYS),
        "python_api": sorted(getattr(docops, "__all__", [])),
    }


def surface_document(previous: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "contract": "farol-3",
        "surface": current_surface(),
        "deprecations": list((previous or {}).get("deprecations", [])),
    }
