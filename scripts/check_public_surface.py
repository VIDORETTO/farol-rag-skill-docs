"""Check (or, after a reviewed change, rewrite) docs/PUBLIC-SURFACE-3.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from docops.contract_surface import surface_document  # noqa: E402

BASELINE = ROOT / "docs" / "PUBLIC-SURFACE-3.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="record the current surface (after review)")
    args = parser.parse_args(argv)
    previous = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.is_file() else None
    current = surface_document(previous)
    if args.write:
        BASELINE.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    deprecated = {(item["kind"], item["name"]) for item in current["deprecations"]}
    removed = [
        f"{kind}: {name}"
        for kind, names in (previous or {}).get("surface", {}).items()
        for name in names
        if name not in current["surface"].get(kind, []) and (kind, name) not in deprecated
    ]
    added = [
        f"{kind}: {name}"
        for kind, names in current["surface"].items()
        for name in names
        if name not in (previous or {}).get("surface", {}).get(kind, [])
    ]
    print(json.dumps({"ok": not removed and (args.write or not added), "removed": removed, "added": added}, indent=2))
    return 0 if not removed and (args.write or not added) else 1


if __name__ == "__main__":
    raise SystemExit(main())
