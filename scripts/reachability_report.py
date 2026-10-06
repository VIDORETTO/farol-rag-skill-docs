"""Which code does the everyday journey actually run? (TK-216, input for D-307)

Runs the user journey in-process on a small generated project — ``add``,
``build``, ``status``, ``task plan/next``, ``sync``, ``connect --dry-run``,
``library`` and the MCP tools — while recording every function that executes.
Then compares that with every function defined under ``docops/``.

The result is *observed* reachability for one representative journey, not a
proof that unexecuted code is dead: error paths, optional extras (media, OCR,
semantic, RAGFlow) and advanced commands are expected to appear as unexecuted.
Use it to decide what to deprecate, never to delete without review.

    python scripts/reachability_report.py --json
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stderr
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "docops"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_SOURCE = (
    "# Lighthouse Manual\n\n## Lens care\n\nClean the Fresnel lens every 12 hours with a soft cloth.\n\n"
    "## Lamp\n\nThe lamp burns paraffin and must be trimmed at dusk.\n"
)


def _defined_functions() -> dict[str, list[tuple[str, int, int]]]:
    """Every function and method under docops/: module -> [(qualname, first line, size in lines)]."""

    functions: dict[str, list[tuple[str, int, int]]] = {}
    for path in sorted(PACKAGE.rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        found: list[tuple[str, int, int]] = []

        def visit(node: ast.AST, prefix: str) -> None:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    first = child.decorator_list[0].lineno if child.decorator_list else child.lineno
                    found.append((prefix + child.name, child.lineno, (child.end_lineno or child.lineno) - first + 1))
                    visit(child, f"{prefix}{child.name}.")
                elif isinstance(child, ast.ClassDef):
                    visit(child, f"{prefix}{child.name}.")

        visit(tree, "")
        functions[relative] = found
    return functions


def _run_journey(work: Path) -> None:
    """The everyday journey of the README, with every external effect kept inside ``work``."""

    from docops import agent_tasks, connect, journey, library
    from docops.mcp_server import KnowledgeServer

    source = work / "manual"
    source.mkdir()
    (source / "manual.md").write_text(_SOURCE, encoding="utf-8")
    project = work / "project"
    journey.add_source(project, str(source), license="MIT")
    journey.build(project)
    journey.status(project)
    package = journey.project_packages(project)["manual"]
    agent_tasks.plan_synthesis(package)
    agent_tasks.next_task(package)
    journey.sync(project)
    journey.project_health(project)
    target = work / "repo"
    target.mkdir()
    for harness in ("claude-code", "codex", "cursor", "opencode", "generic"):
        connect.connect(project, harness, target=target, dry_run=True)
    library.add_project(project)
    library.list_projects()
    server = KnowledgeServer(packages=library.library_packages())
    hits = server.search_knowledge("how often is the lens cleaned")["hits"]
    server.list_skills()
    server.get_skill("manual")
    if hits:
        server.get_context(hits[0]["block_id"])
        server.get_document(hits[0]["document_id"], offset=0, limit=5)


def observe() -> dict[str, Any]:
    executed: set[tuple[str, int]] = set()
    prefix = str(PACKAGE) + os.sep

    def profiler(frame: Any, event: str, _arg: Any) -> None:
        if event == "call":
            code = frame.f_code
            if code.co_filename.startswith(prefix):
                executed.add((Path(code.co_filename).relative_to(ROOT).as_posix(), code.co_firstlineno))

    with tempfile.TemporaryDirectory(prefix="farol-reach-") as directory:
        work = Path(directory)
        saved = {key: os.environ.get(key) for key in ("FAROL_HOME", "FAROL_CACHE_DIR", "FAROL_SEMANTIC")}
        os.environ.update(
            {"FAROL_HOME": str(work / "home"), "FAROL_CACHE_DIR": str(work / "cache"), "FAROL_SEMANTIC": "0"}
        )
        sys.setprofile(profiler)
        try:
            with redirect_stderr(io.StringIO()):
                _run_journey(work)
        finally:
            sys.setprofile(None)
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    return _report(_defined_functions(), executed)


def _report(defined: dict[str, list[tuple[str, int, int]]], executed: set[tuple[str, int]]) -> dict[str, Any]:
    modules = []
    for module, functions in defined.items():
        lines = len((ROOT / module).read_text(encoding="utf-8").splitlines())
        ran = [item for item in functions if (module, item[1]) in executed]
        unexecuted_lines = sum(size for _name, line, size in functions if (module, line) not in executed)
        modules.append(
            {
                "module": module,
                "lines": lines,
                "functions": len(functions),
                "executed_functions": len(ran),
                "unexecuted_function_lines": unexecuted_lines,
            }
        )
    modules.sort(key=lambda item: (-item["unexecuted_function_lines"], item["module"]))
    unused = [item["module"] for item in modules if item["functions"] and not item["executed_functions"]]
    return {
        "schema_version": 1,
        "method": "observed-journey",
        "journey": [
            "add",
            "build",
            "status",
            "task plan",
            "task next",
            "sync",
            "doctor",
            "connect --dry-run",
            "library",
            "mcp tools",
        ],
        "totals": {
            "modules": len(modules),
            "lines": sum(item["lines"] for item in modules),
            "functions": sum(item["functions"] for item in modules),
            "executed_functions": sum(item["executed_functions"] for item in modules),
            "unexecuted_function_lines": sum(item["unexecuted_function_lines"] for item in modules),
        },
        "modules_unused_by_journey": sorted(unused),
        "modules": modules,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true", help="print the full JSON report")
    args = parser.parse_args(argv)
    report = observe()
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    totals = report["totals"]
    print(
        f"{totals['executed_functions']}/{totals['functions']} functions ran in the journey; "
        f"{totals['unexecuted_function_lines']} of {totals['lines']} lines are in functions it never ran."
    )
    print("Modules the journey never entered:")
    for module in report["modules_unused_by_journey"]:
        print(f"  {module}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
