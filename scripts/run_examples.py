"""Run the documented recipes (docs/EXAMPLES.md) offline with synthetic fixtures."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from docops.journey import (  # noqa: E402
    add_source,
    build,
    project_packages,  # noqa: E402
)
from docops.mcp_server import KnowledgeServer  # noqa: E402

FIXTURES = ROOT / "documents" / "fixtures"
RECIPES = {
    "documentation-folder": ([FIXTURES / "acme-docs"], "retries", "rag/documents/"),
    "video-subtitles": ([FIXTURES / "lecture" / "lecture.vtt"], "how many retries", "(at 00:00:42)"),
    "several-sources": (
        [FIXTURES / "acme-docs", FIXTURES / "lecture" / "lecture.vtt"],
        "orders endpoint",
        "rag/documents/",
    ),
}


def run_recipe(name: str, workdir: Path) -> dict[str, object]:
    sources, question, expected = RECIPES[name]
    project = workdir / name
    for source in sources:
        add_source(project, str(source), license="MIT")
    report = build(project)
    packages = project_packages(project)
    hits = KnowledgeServer(packages=packages).search_knowledge(question)["hits"] if packages else []
    ok = bool(report["ok"] and hits and any(expected in hit["citation"] for hit in hits))
    return {"recipe": name, "ok": ok, "sources": len(sources), "first_citation": hits[0]["citation"] if hits else None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="farol-examples-") as temporary:
        results = [run_recipe(name, Path(temporary)) for name in RECIPES]
    print(json.dumps({"ok": all(item["ok"] for item in results), "recipes": results}, indent=2))
    return 0 if all(item["ok"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
