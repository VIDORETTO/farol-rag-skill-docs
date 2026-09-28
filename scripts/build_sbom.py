"""Release artifacts: CycloneDX SBOM of an installed distribution and SHA256SUMS.

Usage in the release workflow (inside a clean environment with the wheel installed):

    python scripts/build_sbom.py sbom --distribution farol-kit --output dist/farol-kit.cdx.json
    python scripts/build_sbom.py checksums --directory dist
    python scripts/build_sbom.py verify --directory dist
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from typing import Any

CHECKSUMS = "SHA256SUMS"


def _requirement_name(requirement: str) -> str | None:
    if ";" in requirement and "extra ==" in requirement.split(";", 1)[1]:
        return None  # optional extras are included only when installed
    match = re.match(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)", requirement)
    return match.group(1) if match else None


def _closure(name: str, extras: tuple[str, ...]) -> dict[str, str]:
    """Installed distributions reachable from ``name`` (including installed extras)."""

    seen: dict[str, str] = {}
    pending = [name]
    root = True
    while pending:
        current = pending.pop()
        try:
            dist = distribution(current)
        except PackageNotFoundError:
            continue
        key = dist.metadata["Name"].casefold().replace("_", "-")
        if key in seen:
            continue
        seen[key] = dist.version
        for requirement in dist.requires or []:
            dependency = _requirement_name(requirement)
            extra = re.search(r"extra\s*==\s*['\"]([^'\"]+)['\"]", requirement)
            if dependency is None and root and extra and extra.group(1) in extras:
                dependency = re.match(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)", requirement).group(1)  # type: ignore[union-attr]
            if dependency:
                pending.append(dependency)
        root = False
    return seen


def build_sbom(name: str, extras: tuple[str, ...] = ("formats",)) -> dict[str, Any]:
    packages = _closure(name, extras)
    root_key = name.casefold()
    version = packages.pop(root_key, "0")
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "component": {
                "type": "application",
                "name": name,
                "version": version,
                "purl": f"pkg:pypi/{name}@{version}",
            },
        },
        "components": [
            {
                "type": "library",
                "name": package,
                "version": package_version,
                "purl": f"pkg:pypi/{package}@{package_version}",
            }
            for package, package_version in sorted(packages.items())
        ],
    }


def write_checksums(directory: Path) -> Path:
    lines = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        for path in sorted(directory.iterdir())
        if path.is_file() and path.name != CHECKSUMS
    ]
    target = directory / CHECKSUMS
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def verify_checksums(directory: Path) -> dict[str, Any]:
    mismatches = []
    for line in (directory / CHECKSUMS).read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        path = directory / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            mismatches.append(name)
    return {"ok": not mismatches, "mismatches": mismatches}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    sbom = commands.add_parser("sbom")
    sbom.add_argument("--distribution", default="farol-kit")
    sbom.add_argument("--extras", default="formats")
    sbom.add_argument("--output", type=Path, required=True)
    for name in ("checksums", "verify"):
        commands.add_parser(name).add_argument("--directory", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "sbom":
        document = build_sbom(args.distribution, tuple(filter(None, args.extras.split(","))))
        args.output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"ok": True, "components": len(document["components"])}))
        return 0
    if args.command == "checksums":
        print(json.dumps({"ok": True, "file": str(write_checksums(args.directory))}))
        return 0
    report = verify_checksums(args.directory)
    print(json.dumps(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
