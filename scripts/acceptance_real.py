"""Acceptance suite over a real, licensed corpus (TK-101).

Each source in the manifest is downloaded (https or file URLs only), verified by
SHA-256, turned into a Farol package, indexed with the default local backend and
questioned with reviewed golden cases. Acquired material stays in the work
directory (ignored by Git) and is never redistributed.

Besides recall@5/MRR@5 per source, the report measures (Farol 3.1, TK-201):
context cost (tokens of the top-5 hits, of ``get_context`` around the right hit
and of the whole document), splits (English, Portuguese, validation, broad
questions) and a library mode where every measured source is served by one
MCP server, as `farol mcp --library` does.

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
DEFAULT_VALIDATION_CASES = PROJECT_ROOT / "golden-set" / "real" / "validation-cases.json"
DEFAULT_WORK_DIR = PROJECT_ROOT / "data" / "acceptance"
RECALL_TARGET = 0.9
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024
_REQUIRED = ("id", "kind", "license", "license_url", "purpose", "redistribution", "files")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_PENDING = {"pending_extractor": "extractor_unavailable", "pending_source": "source_pending"}
TOP_K = 5


def validate_manifest(manifest: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for index, source in enumerate(manifest.get("sources") or []):
        where = f"sources[{index}]"
        pending = source.get("status") in _PENDING
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


def _measure(
    source: dict[str, Any], cases: list[dict[str, Any]], work: Path, validation: list[dict[str, Any]] = ()
) -> dict[str, Any]:
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
    factual = [case for case in cases if case.get("kind") == "factual"]
    retrieval, ranked = _retrieval(backend, index, factual)
    splits = {
        name: {key: value for key, value in _retrieval(backend, index, members)[0].items() if key != "locator_coverage"}
        for name, members in (
            ("en", [case for case in factual if case.get("language", "en") == "en"]),
            ("pt", [case for case in factual if case.get("language") == "pt"]),
            ("validation", [case for case in validation if case.get("kind") == "factual"]),
        )
        if members
    }
    broad = [case for case in cases if case.get("kind") == "broad"]
    if broad:
        splits["broad"] = _broad(backend, index, broad)
    return {
        "status": "measured",
        "package": str(package),
        "index": {key: index_report[key] for key in ("documents", "blocks")},
        "retrieval": retrieval,
        "splits": splits,
        "context": _context_cost(backend, index, ranked),
        "skill": _skill_quality(package),
    }


def _tokens(text: str) -> int:
    return len(text) // 4


def _rank(hits: list[dict[str, Any]], expected: str) -> int | None:
    wanted = _normalize(expected)
    return next((position for position, hit in enumerate(hits, 1) if wanted in _normalize(hit["text"])), None)


def _retrieval(backend: Any, index: Any, cases: list[dict[str, Any]]) -> tuple[dict[str, Any], list[tuple]]:
    """recall@5, MRR@5 and locator coverage; also returns (hits, rank) per case for the context cost."""

    reciprocal: list[float] = []
    ranked: list[tuple[list[dict[str, Any]], int | None]] = []
    returned = located = 0
    for case in cases:
        hits = backend.query(index, QueryRequest(query=case["question"], top_k=TOP_K)).hits
        rank = _rank(hits, case["expected_text"])
        reciprocal.append(1.0 / rank if rank else 0.0)
        ranked.append((hits, rank))
        returned += len(hits)
        located += sum(1 for hit in hits if hit.get("locators"))
    total = len(cases)
    result = {
        "cases": total,
        "recall_at_5": round(sum(1 for value in reciprocal if value) / total, 4) if total else 0.0,
        "mrr_at_5": round(sum(reciprocal) / total, 4) if total else 0.0,
        "locator_coverage": round(located / returned, 4) if returned else 0.0,
    }
    return result, ranked


def _broad(backend: Any, index: Any, cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Broad questions: answered when any expected passage appears in the top 5."""

    found = 0
    for case in cases:
        hits = backend.query(index, QueryRequest(query=case["question"], top_k=TOP_K)).hits
        found += any(_rank(hits, expected) for expected in case.get("expected_any") or [])
    return {"cases": len(cases), "recall_at_5": round(found / len(cases), 4)}


def _context_cost(backend: Any, index: Any, ranked: list[tuple]) -> dict[str, Any]:
    """Tokens an agent reads: the top-5 hits, the context around the right hit, or its whole document."""

    hit_tokens = [sum(_tokens(hit["text"]) for hit in hits) for hits, _rank_ in ranked]
    context_tokens: list[int] = []
    document_tokens: list[int] = []
    for hits, rank in ranked:
        if not rank:
            continue
        hit = hits[rank - 1]
        around = backend.get_context(index, hit["block_id"], before=2, after=2)
        document = backend.get_document(index, hit["document_id"])
        context_tokens.append(sum(_tokens(block["text"]) for block in around["blocks"]))
        document_tokens.append(sum(_tokens(block["text"]) for block in document["blocks"]))

    def mean(values: list[int]) -> float:
        return round(sum(values) / len(values), 1) if values else 0.0

    reduction = 1 - sum(context_tokens) / sum(document_tokens) if sum(document_tokens) else 0.0
    return {
        "cases_found": len(context_tokens),
        "hit_tokens_mean": mean(hit_tokens),
        "context_tokens_mean": mean(context_tokens),
        "document_tokens_mean": mean(document_tokens),
        "context_reduction": round(reduction, 4),
    }


def _library(measured: dict[str, Path], cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Every measured source behind one MCP server, ranked together as `farol mcp --library` does."""

    from docops.mcp_server import KnowledgeServer

    server = KnowledgeServer(packages=measured)
    reciprocal: list[float] = []
    returned = foreign = 0
    selected = [case for case in cases if case.get("kind") == "factual" and case.get("source") in measured]
    for case in selected:
        hits = server.search_knowledge(case["question"], top_k=TOP_K)["hits"]
        own = [hit for hit in hits if hit["package"] == case["source"]]
        rank = next(
            (
                position
                for position, hit in enumerate(hits, 1)
                if hit["package"] == case["source"] and _normalize(case["expected_text"]) in _normalize(hit["text"])
            ),
            None,
        )
        reciprocal.append(1.0 / rank if rank else 0.0)
        returned += len(hits)
        foreign += len(hits) - len(own)
    total = len(selected)
    return {
        "sources": sorted(measured),
        "cases": total,
        "recall_at_5": round(sum(1 for value in reciprocal if value) / total, 4) if total else 0.0,
        "mrr_at_5": round(sum(reciprocal) / total, 4) if total else 0.0,
        "foreign_hit_share": round(foreign / returned, 4) if returned else 0.0,
    }


def run(
    manifest_path: Path,
    cases_path: Path,
    work: Path,
    only: set[str] | None = None,
    validation_path: Path | None = None,
) -> tuple[int, dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = validate_manifest(manifest)
    if errors:
        return 2, {"passed": False, "errors": errors}
    all_cases = json.loads(cases_path.read_text(encoding="utf-8")).get("cases", [])
    validation_cases = (
        json.loads(validation_path.read_text(encoding="utf-8")).get("cases", [])
        if validation_path is not None and validation_path.is_file()
        else []
    )
    report: dict[str, Any] = {"schema_version": 1, "recall_target": RECALL_TARGET, "sources": {}}
    for source in manifest["sources"]:
        if only and source["id"] not in only:
            continue
        if source.get("status") in _PENDING:
            report["sources"][source["id"]] = {
                "status": "not_run",
                "code": source.get("not_run_code", _PENDING[source["status"]]),
                **({"note": source["note"]} if source.get("note") else {}),
            }
            continue
        cases = [case for case in all_cases if case.get("source") == source["id"]]
        validation = [case for case in validation_cases if case.get("source") == source["id"]]
        report["sources"][source["id"]] = _measure(source, cases, work, validation)
    measured = [value for value in report["sources"].values() if value["status"] == "measured"]
    packages = {
        source_id: Path(value.pop("package"))
        for source_id, value in report["sources"].items()
        if value["status"] == "measured"
    }
    if len(packages) > 1:
        report["library"] = _library(packages, all_cases)
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
    parser.add_argument("--validation-cases", type=Path, default=DEFAULT_VALIDATION_CASES)
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--only", action="append", help="measure only this source id (repeatable)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    code, report = run(args.manifest, args.cases, args.work_dir, set(args.only or []) or None, args.validation_cases)
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
