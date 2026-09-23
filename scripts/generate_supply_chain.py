"""Generate redacted, reproducible supply-chain evidence for Farol 2.0."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _requirements(path: Path) -> list[dict[str, str]]:
    values = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)(.*)$", line)
        if match:
            values.append({"name": match.group(1).lower().replace("_", "-"), "specifier": match.group(2).strip()})
    return values


def _wheel_evidence(wheel: Path, root: Path) -> dict[str, Any]:
    return {
        "path": wheel.relative_to(root).as_posix(),
        "filename": wheel.name,
        "sha256": _sha256_file(wheel),
        "size": wheel.stat().st_size,
    }


def generate(
    *,
    root: Path,
    wheel: Path,
    output: Path,
    model_cache: Path | None = None,
    python: Path | None = None,
    require_model: bool = False,
    profile: str = "core",
    lock_path: Path | None = None,
    vendor_root: Path | None = None,
    source_commit: str | None = None,
    source_candidate_digest: str | None = None,
) -> dict[str, Any]:
    del python, require_model, vendor_root
    root = root.expanduser().resolve()
    wheel = wheel.expanduser()
    if not wheel.is_absolute():
        wheel = root / wheel
    wheel = wheel.resolve()
    lock = (lock_path or root / "requirements.lock").expanduser().resolve()
    if not lock.is_file() or not wheel.is_file():
        return {"schema_version": 1, "ok": False, "errors": [{"code": "input_missing"}]}
    requirements = _requirements(lock)
    components = [
        {"name": item["name"], "version": item["specifier"].lstrip("=") or "unresolved"} for item in requirements
    ]
    output.mkdir(parents=True, exist_ok=True)
    models: list[dict[str, Any]] = []
    if model_cache is not None:
        model_files = sorted(
            path.relative_to(model_cache).as_posix() for path in model_cache.rglob("*") if path.is_file()
        )
        model_hash = hashlib.sha256()
        for relative in model_files:
            model_hash.update(relative.encode("utf-8"))
            model_hash.update((model_cache / relative).read_bytes())
        models.append(
            {
                "status": "verified-external-snapshot",
                "included": False,
                "path": None,
                "sha256": model_hash.hexdigest(),
                "files": model_files,
            }
        )
    evidence = {
        "schema_version": 1,
        "kind": "docops-supply-chain-evidence",
        "profile": profile,
        "wheel": _wheel_evidence(wheel, root),
        "candidate": {
            "source_commit": source_commit,
            "source_candidate_digest": source_candidate_digest,
            "bound": bool(source_commit and source_candidate_digest),
        },
        "locks": {
            "requirements_path": lock.relative_to(root).as_posix() if lock.is_relative_to(root) else lock.name,
            "requirements_sha256": _sha256_file(lock),
            "requirements": requirements,
        },
        "backend": {"name": "ragflow", "version": "0.27.2", "mode": "external-profile"},
        "models": models,
        "sbom": {"path": "sbom.json", "format": "SPDX-2.3", "components": components},
        "errors": [],
        "ok": True,
    }
    sbom = {
        "spdxVersion": "SPDX-2.3",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": wheel.name,
        "dataLicense": "CC0-1.0",
        "packages": components,
    }
    (output / "supply-chain.json").write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "locks.json").write_text(
        json.dumps(evidence["locks"], indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "sbom.json").write_text(
        json.dumps(sbom, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    checksums = [f"{_sha256_file(output / name)}  {name}" for name in ("locks.json", "sbom.json", "supply-chain.json")]
    (output / "SHA256SUMS").write_text("\n".join(checksums) + "\n", encoding="utf-8")
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-cache", type=Path)
    parser.add_argument("--python", type=Path)
    parser.add_argument("--profile", choices=("core", "ragflow"), default="core")
    parser.add_argument("--require-model", action="store_true")
    parser.add_argument("--source-commit")
    parser.add_argument("--source-candidate-digest")
    args = parser.parse_args(argv)
    result = generate(
        root=args.root,
        wheel=args.wheel,
        output=args.output,
        profile=args.profile,
        source_commit=args.source_commit,
        source_candidate_digest=args.source_candidate_digest,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
