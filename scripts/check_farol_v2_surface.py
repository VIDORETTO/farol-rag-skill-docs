"""Audit release surfaces before Farol 2.0 contraction."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from docops.release_v2 import audit_release_surface  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--surface", choices=("editorial", "legacy", "all"), default="all")
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--allow-path", action="append", default=[])
    args = parser.parse_args(argv)
    audit = audit_release_surface(
        args.root,
        surface=args.surface,
        wheel=args.wheel,
        allow_paths=set(args.allow_path),
    )
    print(json.dumps(audit.to_dict(), indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if audit.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
