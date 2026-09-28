"""Acceptance suite over a real, licensed corpus (TK-101).

Each source in the manifest is downloaded (https or file URLs only), verified by
SHA-256, turned into a Farol package, indexed with the default local backend and
questioned with reviewed golden cases. Acquired material stays in the work
directory (ignored by Git) and is never redistributed.

Exit codes: 0 all measured sources pass, 1 measured but below target or
not_run sources remain, 2 invalid manifest or cases.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import docops  # noqa: E402
from docops.agent_tasks import skill_rubric  # noqa: E402
from docops.backends import QueryRequest  # noqa: E402
from docops.package_index import build_package_index, open_package_index  # noqa: E402

DEFAULT_MANIFEST = PROJECT_ROOT / "golden-set" / "real" / "manifest.json"
DEFAULT_CASES = PROJECT_ROOT / "golden-set" / "real" / "cases.json"
DEFAULT_WORK_DIR = PROJECT_ROOT / "data" / "acceptance"
RECALL_TARGET = 0.9
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024
_REQUIRED = ("id", "kind", "license", "license_url", "purpose", "redistribution", "files")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def validate_manifest(manifest: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for index, source in enumerate(manifest.get("sources") or []):
        where = f"sources[{index}]"
        pending = source.get("status") == "pending_extractor"
        for key in _REQUIRED:
            if key == "files" and pending:
                continue
            if not source.get(key):
                code = "license_required" if key in {"license", "license_url"} else f"{key}_required"
                errors.append({"code": code, "path": f"{where}.{key}"})
        if source.get("redistribution") not in (None, "forbidden", "allowed"):
            errors.append({"code": "redistribution_invalid", "path": f"{where}.redistribution"})
        for position, item in enumerate(source.get("files") or []):
            if not _SHA256.fullmatch(str(item.get("sha256") or "")):
                errors.append({"code": "sha256_required", "path": f"{where}.files[{position}].sha256"})
            if not _SAFE_NAME.fullmatch(str(item.get("name") or "")):
                errors.append({"code": "file_name_invalid", "path": f"{where}.files[{position}].name"})
            if not str(item.get("url") or "").startswith(("https://", "file://")):
                errors.append({"code": "url_scheme_invalid", "path": f"{where}.files[{position}].url"})
    if not manifest.get("sources"):
        errors.append({"code": "sources_required", "path": "sources"})
    return errors


def _download(url: str, target: Path, expected: str) -> None:
    if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "farol-acceptance/1"})
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310 - scheme validated above
        payload = response.read(MAX_DOWNLOAD_BYTES + 1)
    if len(payload) > MAX_DOWNLOAD_BYTES:
        raise ValueError("download_too_large")
    if hashlib.sha256(payload).hexdigest() != expected:
        raise ValueError("sha256_mismatch")
    target.write_bytes(payload)


def _normalize(value: str) -> str:
    # Inline-code backticks are presentation, not evidence content.
    return " ".join(value.replace("`", "").casefold().split())


def _skill_quality(package: Path) -> dict[str, Any]:
    rubric = skill_rubric(package)
    return {"distilled": rubric["passed"], "generator": rubric["generator"], "checks": rubric["checks"]}


def _measure(source: dict[str, Any], cases: list[dict[str, Any]], work: Path) -> dict[str, Any]:
    source_dir = work / source["id"] / "source"
    for item in source["files"]:
        try:
            _download(item["url"], source_dir / item["name"], item["sha256"])
        except ValueError as exc:
            return {"status": "failed", "code": str(exc), "file": item["name"]}
        except OSError as exc:
            return {"status": "not_run", "code": "download_unavailable", "detail": type(exc).__name__}
    package = work / source["id"] / "package"
    # An existing package is refreshed with a factual update, which preserves a
    # distilled skill exactly as users' packages are preserved.
    existing = (package / "manifest.json").is_file()
    plan = docops.plan(
        docops.OperationRequest(
            source_dir,
            docops.OperationOptions(
                output_dir=package,
                source_root=source_dir.parent,
                slug=source["id"],
                license=source["license"],
                **({"mode": "update", "layers": ("factual",)} if existing else {}),
            ),
        )
    )
    result = docops.apply(plan)
    if not result.ok:
        codes = [str(error.get("code")) for error in result.errors] or ["apply_failed"]
        quarantined = [
            {"file": Path(str(entry.get("source") or "")).name, "reason": str(entry.get("quality_reason"))}
            for entry in plan.entries
            if entry.get("status") == "quarantined"
        ]
        return {"status": "blocked", "code": codes[0], "quarantined": quarantined}
    index_report = build_package_index(package)
    backend, index = open_package_index(package)
    reciprocal: list[float] = []
    returned = located = 0
    for case in cases:
        result = backend.query(index, QueryRequest(query=case["question"], top_k=5))
        expected = _normalize(case["expected_text"])
        rank = next(
            (position for position, hit in enumerate(result.hits, 1) if expected in _normalize(hit["text"])), None
        )
        reciprocal.append(1.0 / rank if rank else 0.0)
        returned += len(result.hits)
        located += sum(1 for hit in result.hits if hit.get("locators"))
    total = len(cases)
    return {
        "status": "measured",
        "index": {key: index_report[key] for key in ("documents", "blocks")},
        "retrieval": {
            "cases": total,
            "recall_at_5": round(sum(1 for value in reciprocal if value) / total, 4) if total else 0.0,
            "mrr_at_5": round(sum(reciprocal) / total, 4) if total else 0.0,
            "locator_coverage": round(located / returned, 4) if returned else 0.0,
        },
        "skill": _skill_quality(package),
    }


def run(manifest_path: Path, cases_path: Path, work: Path, only: set[str] | None = None) -> tuple[int, dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = validate_manifest(manifest)
    if errors:
        return 2, {"passed": False, "errors": errors}
    all_cases = json.loads(cases_path.read_text(encoding="utf-8")).get("cases", [])
    report: dict[str, Any] = {"schema_version": 1, "recall_target": RECALL_TARGET, "sources": {}}
    for source in manifest["sources"]:
        if only and source["id"] not in only:
            continue
        if source.get("status") == "pending_extractor":
            report["sources"][source["id"]] = {"status": "not_run", "code": "extractor_unavailable"}
            continue
        cases = [case for case in all_cases if case.get("source") == source["id"] and case.get("kind") == "factual"]
        report["sources"][source["id"]] = _measure(source, cases, work)
    measured = [value for value in report["sources"].values() if value["status"] == "measured"]
    report["passed"] = (
        bool(measured)
        and len(measured) == len(report["sources"])
        and all(
            value["retrieval"]["recall_at_5"] >= RECALL_TARGET and value["skill"]["distilled"] for value in measured
        )
    )
    return (0 if report["passed"] else 1), report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--only", action="append", help="measure only this source id (repeatable)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    code, report = run(args.manifest, args.cases, args.work_dir, set(args.only or []) or None)
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
