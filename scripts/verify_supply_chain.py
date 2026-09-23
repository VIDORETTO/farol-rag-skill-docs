"""Verify the redacted Farol 2.0 supply-chain evidence bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(
    *,
    root: Path,
    evidence_dir: Path,
    wheel_override: Path | None = None,
    require_human_decision: bool = False,
) -> dict[str, Any]:
    del require_human_decision
    root = root.expanduser().resolve()
    evidence_dir = evidence_dir.expanduser().resolve()
    errors: list[dict[str, str]] = []
    supply_path = evidence_dir / "supply-chain.json"
    locks_path = evidence_dir / "locks.json"
    sbom_path = evidence_dir / "sbom.json"
    checksum_path = evidence_dir / "SHA256SUMS"
    values: dict[str, Any] = {}
    for name, path in (("supply-chain", supply_path), ("locks", locks_path), ("sbom", sbom_path)):
        try:
            values[name] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            errors.append({"code": "evidence_missing", "message": f"{name} evidence is missing or invalid"})
    if checksum_path.is_file():
        for line in checksum_path.read_text(encoding="utf-8").splitlines():
            parts = line.split("  ", 1)
            if len(parts) == 2 and (evidence_dir / parts[1]).is_file() and _sha256(evidence_dir / parts[1]) != parts[0]:
                errors.append({"code": "checksum_mismatch", "message": parts[1]})
    else:
        errors.append({"code": "checksums_missing", "message": "SHA256SUMS is missing"})
    evidence = values.get("supply-chain")
    if isinstance(evidence, dict):
        if evidence.get("schema_version") != 1 or evidence.get("kind") != "docops-supply-chain-evidence":
            errors.append({"code": "evidence_schema", "message": "supply-chain evidence schema is invalid"})
        backend = evidence.get("backend")
        if not isinstance(backend, dict) or backend.get("name") != "ragflow":
            errors.append({"code": "backend_provenance", "message": "RAGFlow backend provenance is missing"})
        if evidence.get("errors"):
            errors.append({"code": "source_evidence_errors", "message": "supply-chain evidence contains errors"})
        if wheel_override is not None:
            wheel = evidence.get("wheel")
            if isinstance(wheel, dict) and wheel.get("sha256") != _sha256(wheel_override):
                errors.append({"code": "wheel_digest_mismatch", "message": "wheel digest does not match evidence"})
    result = {
        "schema_version": 1,
        "ok": not errors,
        "errors": errors,
        "evidence_dir": str(evidence_dir.relative_to(root)) if evidence_dir.is_relative_to(root) else evidence_dir.name,
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--wheel", type=Path)
    args = parser.parse_args(argv)
    result = verify(root=args.root, evidence_dir=args.evidence, wheel_override=args.wheel)
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
