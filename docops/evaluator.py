"""Lightweight, reproducible retrieval evaluation for a produced package."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

from .contracts import validate_artifact
from .manifest import redact_metadata
from .observability import redact_report, redact_text
from .package_validator import validate_package
from .readiness import assess_readiness
from .retrieval import RetrievalError, SkillRetrievalAdapter, adapter_for_package, route_query
from .revisions import content_hash, package_revisions
from .storage import write_json_atomic

_TOKEN = re.compile(r"[\wÀ-ÿ][\wÀ-ÿ./:-]*", re.UNICODE)
_WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[/\\]")


@dataclass
class EvaluationResult:
    ok: bool
    metrics: dict[str, Any]
    cases: list[dict[str, Any]]
    errors: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)
    thresholds: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "ok": self.ok,
            "metrics": self.metrics,
            "cases": redact_report(self.cases),
            "errors": redact_report(self.errors),
            "warnings": [redact_text(warning) for warning in self.warnings],
            "diagnostics": [redact_text(diagnostic) for diagnostic in self.diagnostics],
            "thresholds": self.thresholds,
            "metadata": redact_report(self.metadata),
        }


def _tokens(value: str) -> set[str]:
    return {token.casefold() for token in _TOKEN.findall(value)}


def _case_payload(
    cases: Mapping[str, Any] | Iterable[Mapping[str, Any]],
) -> tuple[bool, list[Mapping[str, Any]], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    if isinstance(cases, Mapping):
        contract = validate_artifact("golden", cases)
        if not contract.ok:
            errors.extend(
                {
                    "code": error["code"],
                    "message": f"golden contract {error.get('path', '$')}: {error['message']}",
                }
                for error in contract.errors
            )
        reviewed = cases.get("reviewed") is True
        if cases.get("schema_version") != 1 or type(cases.get("schema_version")) is not int:
            errors.append({"code": "golden_schema", "message": "golden set schema_version must be 1"})
        if "cases" not in cases:
            errors.append({"code": "golden_cases", "message": "golden set cases must be a list"})
        raw_cases = cases.get("cases", [])
    else:
        reviewed = False
        raw_cases = cases
        errors.append(
            {"code": "golden_schema", "message": "golden set must be an object with schema_version and cases"}
        )
    if not isinstance(raw_cases, list):
        return reviewed, [], [{"code": "golden_cases", "message": "golden set cases must be a list"}]
    case_list = [case for case in raw_cases if isinstance(case, Mapping)]
    if len(case_list) != len(raw_cases):
        errors.append({"code": "golden_case_shape", "message": "every golden case must be an object"})
    for index, case in enumerate(case_list, 1):
        for identifier_key in ("id", "case_id"):
            if identifier_key in case and (
                not isinstance(case.get(identifier_key), str) or not case[identifier_key].strip()
            ):
                errors.append(
                    {
                        "code": "golden_case_id",
                        "message": f"golden case {index} has an invalid {identifier_key}",
                    }
                )
        query = case.get("query")
        expected_filepath = case.get("expected_filepath")
        kind = case.get("kind", "factual")
        missing_filepath = kind != "router" and (
            not isinstance(expected_filepath, str) or not expected_filepath.strip()
        )
        if not isinstance(query, str) or not query.strip() or missing_filepath:
            errors.append(
                {"code": "golden_case_fields", "message": f"golden case {index} needs query and expected_filepath"}
            )
        if isinstance(expected_filepath, str):
            relative = Path(expected_filepath.replace("\\", "/"))
            if relative.is_absolute() or _WINDOWS_ABSOLUTE.match(expected_filepath) or ".." in relative.parts:
                errors.append(
                    {"code": "golden_case_path", "message": f"golden case {index} has an unsafe expected_filepath"}
                )
        if not isinstance(kind, str) or kind not in {"conceptual", "factual", "router"}:
            errors.append({"code": "golden_case_kind", "message": f"golden case {index} has an unsupported kind"})
        if kind == "router" and case.get("expected_route") not in {"skill", "rag", "both", "lifecycle"}:
            errors.append({"code": "golden_case_route", "message": f"golden case {index} needs expected_route"})
        if case.get("reviewed") is not True:
            errors.append(
                {"code": "golden_case_not_reviewed", "message": f"golden case {index} requires reviewed=true"}
            )
    reviewed = reviewed and bool(case_list) and not errors
    return reviewed, case_list, errors


def _case_identifier(case: Mapping[str, Any], index: int) -> str:
    for key in ("case_id", "id"):
        value = case.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return f"case-{index}"


def _load_response_receipt(
    receipt: Mapping[str, Any] | Path | str | None,
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    if receipt is None:
        return None, []
    if isinstance(receipt, Mapping):
        payload: Any = dict(receipt)
    elif isinstance(receipt, (Path, str)):
        try:
            payload = json.loads(Path(receipt).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            return None, [{"code": "response_receipt_unreadable", "message": redact_text(exc)}]
    else:
        return None, [
            {"code": "response_receipt_invalid", "message": "response receipt must be an object or JSON file"}
        ]
    if not isinstance(payload, dict):
        return None, [{"code": "response_receipt_invalid", "message": "response receipt must be a JSON object"}]
    contract = validate_artifact("evaluation-receipt", payload)
    if not contract.ok:
        return payload, [
            {
                "code": "response_receipt_schema",
                "message": f"response evaluation receipt violates its contract at {error.get('path', '$')}",
            }
            for error in contract.errors
        ]
    return payload, []


def _safe_response_citation(package_root: Path, raw: Any) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    normalized = raw.strip().replace("\\", "/")
    path_value, separator, fragment = normalized.partition("#")
    if separator and (not fragment or any(ord(char) < 32 for char in fragment)):
        return None
    relative = PurePosixPath(path_value)
    if (
        relative.is_absolute()
        or _WINDOWS_ABSOLUTE.match(path_value)
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        return None
    roots = (
        ("rag/documents/", package_root / "rag" / "documents"),
        ("documents/", package_root / "rag" / "documents"),
        ("skill/", package_root / "skill"),
        ("router/", package_root / "router"),
    )
    for prefix, root in roots:
        candidate_name = path_value[len(prefix) :] if path_value.startswith(prefix) else None
        if candidate_name:
            candidate = root / Path(*PurePosixPath(candidate_name).parts)
            try:
                candidate.relative_to(root)
            except ValueError:
                return None
            if candidate.is_file() and not candidate.is_symlink():
                return normalized
    for root in (package_root / "rag" / "documents", package_root / "skill", package_root / "router"):
        candidate = root / Path(*relative.parts)
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        if candidate.is_file() and not candidate.is_symlink():
            return normalized
    return None


def _evaluate_response_receipt(
    package_root: Path,
    receipt: Mapping[str, Any] | None,
    receipt_errors: list[dict[str, str]],
    golden_cases: list[Mapping[str, Any]],
    revisions: Mapping[str, Any],
    *,
    thresholds: Mapping[str, float] | None,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    list[dict[str, str]],
    dict[str, dict[str, Any]],
    dict[str, float],
]:
    if receipt is None and not receipt_errors:
        return {}, {}, [], {}, {}

    errors = list(receipt_errors)
    receipt_hash = content_hash(receipt) if receipt is not None else None
    if receipt is None:
        return (
            {},
            {
                "status": "failed",
                "receipt_hash": receipt_hash,
                "metric_status": {
                    "response_fidelity": "not_applicable",
                    "citation_coverage": "not_applicable",
                },
            },
            errors,
            {},
            {},
        )
    evaluator = receipt.get("evaluator") if isinstance(receipt.get("evaluator"), Mapping) else {}
    response_metadata: dict[str, Any] = {
        "status": "failed" if errors else "not_applicable",
        "generation_id": receipt.get("generation_id"),
        "candidate_id": receipt.get("candidate_id"),
        "evaluator": {
            "name": evaluator.get("name"),
            "version": evaluator.get("version"),
            "independent": evaluator.get("independent") is True,
        },
        "rubric_revision": receipt.get("rubric_revision"),
        "receipt_hash": receipt_hash,
        "case_count": 0,
        "claim_count": 0,
        "supported_claims": 0,
        "critical_failures": 0,
        "citation_required": 0,
        "citation_supported": 0,
        "metric_status": {
            "response_fidelity": "not_applicable",
            "citation_coverage": "not_applicable",
        },
    }
    metrics: dict[str, Any] = {}
    case_reports: dict[str, dict[str, Any]] = {}
    response_thresholds: dict[str, float] = {}

    expected_composition = revisions.get("composition_hash")
    expected_golden = revisions.get("golden_revision")
    if receipt.get("package_composition_hash") != expected_composition:
        errors.append(
            {
                "code": "response_receipt_stale",
                "message": "response evaluation receipt does not match the package composition",
            }
        )
    if receipt.get("golden_revision") != expected_golden:
        errors.append(
            {
                "code": "response_receipt_stale",
                "message": "response evaluation receipt does not match the reviewed Golden",
            }
        )
    candidate_receipt_path = package_root / ".docops" / "candidate.json"
    if candidate_receipt_path.is_file() and not candidate_receipt_path.is_symlink():
        try:
            candidate_receipt = json.loads(candidate_receipt_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            candidate_receipt = None
        if isinstance(candidate_receipt, Mapping) and candidate_receipt.get("candidate_id") != receipt.get(
            "candidate_id"
        ):
            errors.append(
                {
                    "code": "response_candidate_mismatch",
                    "message": "response evaluation receipt does not identify this candidate",
                }
            )

    golden_by_id = {_case_identifier(case, index): case for index, case in enumerate(golden_cases, 1)}
    raw_cases = receipt.get("cases")
    if not isinstance(raw_cases, list):
        errors.append({"code": "response_receipt_cases", "message": "response receipt cases must be a list"})
        raw_cases = []
    seen_cases: set[str] = set()
    total_claims = 0
    supported_claims = 0
    critical_failures = 0
    citation_required = 0
    citation_supported = 0

    for item in raw_cases:
        if not isinstance(item, Mapping):
            errors.append({"code": "response_case_invalid", "message": "response receipt case must be an object"})
            continue
        case_id = item.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip():
            errors.append({"code": "response_case_invalid", "message": "response receipt case_id is required"})
            continue
        case_id = case_id.strip()
        if case_id in seen_cases:
            errors.append({"code": "response_case_duplicate", "message": "response receipt repeats a case_id"})
            continue
        seen_cases.add(case_id)
        golden_case = golden_by_id.get(case_id)
        if golden_case is None:
            errors.append({"code": "response_case_unknown", "message": "response receipt references an unknown case"})
        claims = item.get("claims")
        if not isinstance(claims, list):
            errors.append({"code": "response_claims_invalid", "message": "response case claims must be a list"})
            claims = []
        case_critical = item.get("critical") is True or bool(
            golden_case.get("critical") if isinstance(golden_case, Mapping) else False
        )
        case_total = 0
        case_supported = 0
        case_critical_failures = 0
        case_citation_required = 0
        case_citation_supported = 0
        for claim in claims:
            if not isinstance(claim, Mapping):
                errors.append({"code": "response_claim_invalid", "message": "response receipt claim must be an object"})
                continue
            if not isinstance(claim.get("claim_id"), str) or not claim["claim_id"].strip():
                errors.append({"code": "response_claim_invalid", "message": "response claim_id is required"})
                continue
            if not isinstance(claim.get("supported"), bool):
                errors.append({"code": "response_claim_invalid", "message": "response supported must be boolean"})
                continue
            case_total += 1
            total_claims += 1
            supported = claim["supported"]
            if supported:
                case_supported += 1
                supported_claims += 1
            requires_citation = claim.get("requires_citation")
            if not isinstance(requires_citation, bool):
                requires_citation = str((golden_case or {}).get("kind", "factual")) != "conceptual"
            citations = claim.get("citations", [])
            if not isinstance(citations, list):
                errors.append({"code": "response_citations_invalid", "message": "response citations must be a list"})
                citations = []
            valid_citations = [
                citation
                for citation in (_safe_response_citation(package_root, value) for value in citations)
                if citation is not None
            ]
            if requires_citation:
                case_citation_required += 1
                citation_required += 1
                if valid_citations:
                    case_citation_supported += 1
                    citation_supported += 1
                elif supported:
                    errors.append(
                        {
                            "code": "response_citation_missing",
                            "message": "a supported response claim lacks a valid citation",
                        }
                    )
            claim_critical = case_critical or claim.get("critical") is True
            if claim_critical and not supported:
                case_critical_failures += 1
                critical_failures += 1
        response_metadata["case_count"] += 1
        case_reports[case_id] = {
            "response_claim_count": case_total,
            "response_supported_claims": case_supported,
            "response_critical_failures": case_critical_failures,
            "response_citation_required": case_citation_required,
            "response_citation_supported": case_citation_supported,
        }

    response_metadata.update(
        {
            "claim_count": total_claims,
            "supported_claims": supported_claims,
            "critical_failures": critical_failures,
            "citation_required": citation_required,
            "citation_supported": citation_supported,
        }
    )
    if total_claims:
        metrics["response_fidelity"] = supported_claims / total_claims
        response_metadata["metric_status"]["response_fidelity"] = "measured"
    else:
        metrics["response_fidelity"] = None
    if citation_required:
        metrics["citation_coverage"] = citation_supported / citation_required
        response_metadata["metric_status"]["citation_coverage"] = "measured"
    else:
        metrics["citation_coverage"] = None

    for key, default in (("response_fidelity", 0.98), ("citation_coverage", 0.98)):
        if metrics[key] is None:
            continue
        raw_threshold = thresholds.get(key, default) if thresholds else default
        try:
            numeric_threshold = float(raw_threshold)
        except (TypeError, ValueError, OverflowError):
            errors.append({"code": "response_threshold_invalid", "message": f"{key} threshold must be numeric"})
            continue
        if not math.isfinite(numeric_threshold) or not 0 <= numeric_threshold <= 1:
            errors.append(
                {"code": "response_threshold_invalid", "message": f"{key} threshold must be from 0 through 1"}
            )
            continue
        response_thresholds[key] = numeric_threshold
        if metrics[key] < numeric_threshold:
            errors.append(
                {
                    "code": f"{key}_below_threshold",
                    "message": f"{key} {metrics[key]:.4f} < {numeric_threshold:.4f}",
                }
            )
    if critical_failures:
        errors.append(
            {
                "code": "critical_response_claim_unsupported",
                "message": "a critical response claim is unsupported",
            }
        )
    if errors:
        response_metadata["status"] = "failed"
    elif total_claims:
        response_metadata["status"] = "passed"
    else:
        response_metadata["status"] = "not_applicable"
    response_metadata["thresholds"] = dict(response_thresholds)
    return metrics, response_metadata, errors, case_reports, response_thresholds


def _expected_relative(value: str, documents_dir: Path) -> str:
    candidate = Path(value)
    if candidate.is_absolute():
        try:
            return candidate.resolve().relative_to(documents_dir.resolve()).as_posix()
        except ValueError:
            return candidate.as_posix()
    normalized = value.replace("\\", "/")
    for prefix in ("documents/", "rag/documents/", "skill/"):
        if normalized.startswith(prefix):
            return normalized[len(prefix) :]
    return normalized.lstrip("./")


def _safe_adapter_metadata(adapter: Any, fallback: Mapping[str, Any]) -> dict[str, Any]:
    if adapter is None:
        return dict(fallback)
    try:
        value = adapter.metadata()
    except Exception:
        return dict(fallback)
    return redact_report(redact_metadata(dict(value))) if isinstance(value, Mapping) else dict(fallback)


def _score(query: str, path: str, content: str) -> float:
    query_tokens = _tokens(query)
    if not query_tokens:
        return 0.0
    path_tokens = _tokens(path)
    content_tokens = _tokens(content)
    overlap = len(query_tokens & content_tokens) / len(query_tokens)
    path_overlap = len(query_tokens & path_tokens) / len(query_tokens)
    phrase = 1.0 if query.casefold() in content.casefold() else 0.0
    return overlap + path_overlap * 0.5 + phrase * 0.5


def _corpus(documents_dir: Path) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for path in sorted(documents_dir.rglob("*")):
        if (
            not path.is_symlink()
            and path.is_file()
            and path.suffix.casefold()
            in {
                ".md",
                ".markdown",
                ".txt",
                ".rst",
                ".adoc",
                ".json",
                ".yaml",
                ".yml",
                ".html",
                ".htm",
                ".xml",
                ".csv",
                ".py",
                ".c",
                ".h",
                ".cpp",
                ".js",
                ".jsx",
                ".ts",
                ".tsx",
                ".ipynb",
                ".xlsx",
                ".pptx",
            }
        ):
            result.append(
                (path.relative_to(documents_dir).as_posix(), path.read_text(encoding="utf-8", errors="replace"))
            )
    return result


def generate_golden_candidates(package_root: Path | str, *, limit: int = 20) -> list[dict[str, Any]]:
    """Generate review-required candidates from headings; never marks them approved."""

    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise ValueError("limit must be an integer from 1 through 1000")
    documents_dir = Path(package_root).resolve() / "rag" / "documents"
    candidates: list[dict[str, Any]] = []
    for relative, content in _corpus(documents_dir):
        title = next(
            (match.group(1).strip() for line in content.splitlines() if (match := re.match(r"^#\s+(.+)$", line))),
            Path(relative).stem,
        )
        candidates.append(
            {
                "query": title,
                "expected_filepath": relative,
                "kind": "factual",
                "reviewed": False,
                "review_note": "Review query and expected source independently before approval.",
            }
        )
        if len(candidates) >= limit:
            break
    return candidates


def evaluate_package(
    package_root: Path | str,
    cases: Mapping[str, Any] | Iterable[Mapping[str, Any]] | Path | str,
    *,
    thresholds: Mapping[str, float] | None = None,
    top_k: int = 5,
    adapter: Any = None,
    runtime_root: Path | str | None = None,
    response_receipt: Mapping[str, Any] | Path | str | None = None,
) -> EvaluationResult:
    """Evaluate cases through a named retrieval/skill adapter.

    The default remains the fast lexical diagnostic for compatibility.  A
    release gate must pass ``adapter="mcp"`` so its metrics are produced by
    the same backend delivered to the harness.  When supplied, an external
    response-evaluation receipt adds an independent fidelity and citation gate
    without importing response text into the package report.
    """

    root = Path(package_root).resolve()
    valid_top_k = isinstance(top_k, int) and not isinstance(top_k, bool) and 1 <= top_k <= 100
    metric_top_k = top_k if valid_top_k else 5
    recall_key = f"recall_at_{metric_top_k}"
    mrr_key = f"mrr_at_{metric_top_k}"
    if isinstance(cases, (Path, str)):
        try:
            payload = json.loads(Path(cases).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            return EvaluationResult(
                False, {recall_key: 0.0, mrr_key: 0.0}, [], [{"code": "golden_unreadable", "message": redact_text(exc)}]
            )
    else:
        payload = cases
    reviewed, case_list, payload_errors = _case_payload(payload)
    errors: list[dict[str, str]] = list(payload_errors)
    response_payload, response_receipt_errors = _load_response_receipt(response_receipt)
    if not reviewed:
        errors.append(
            {"code": "golden_not_reviewed", "message": "golden cases require explicit review before evaluation"}
        )
    if not case_list:
        errors.append({"code": "golden_empty", "message": "golden set is empty"})
    validation = validate_package(root)
    if not validation.ok:
        errors.append({"code": "invalid_package", "message": "package must validate before retrieval evaluation"})
    if not valid_top_k:
        errors.append({"code": "top_k_out_of_range", "message": "top_k must be an integer from 1 through 100"})
    ranked_top_k = top_k if valid_top_k else 1
    try:
        retrieval = adapter_for_package(root, adapter)
    except (OSError, ValueError, RetrievalError) as exc:
        errors.append({"code": getattr(exc, "code", "adapter_unavailable"), "message": str(exc)})
        retrieval = None
    skill_adapter = SkillRetrievalAdapter(root)
    evaluated: list[dict[str, Any]] = []
    reciprocal_ranks: list[float] = []
    hits = 0
    route_total = 0
    route_hits = 0
    kind_totals: dict[str, int] = {"factual": 0, "conceptual": 0}
    kind_hits: dict[str, int] = {"factual": 0, "conceptual": 0}
    route_metadata = {
        "factual": _safe_adapter_metadata(retrieval, {"backend": "unavailable", "adapter": "unknown", "mode": "gate"}),
        "conceptual": _safe_adapter_metadata(
            skill_adapter, {"backend": "unavailable", "adapter": "unknown", "mode": "gate"}
        ),
        "router": {"backend": "policy", "adapter": "route_query", "mode": "gate", "profile": "documented-policy-v1"},
    }
    result: EvaluationResult | None = None
    try:
        for case in case_list:
            query = str(case.get("query") or "")
            kind = str(case.get("kind", "factual"))
            expected_root = root / "skill" if kind == "conceptual" else root / "rag" / "documents"
            expected = _expected_relative(str(case.get("expected_filepath") or ""), expected_root)
            safe_expected = redact_text(expected).replace("\\", "/")
            retrieved: list[dict[str, Any]] = []
            rank: int | None = None
            route = None
            selected_metadata: Mapping[str, Any] = route_metadata.get(kind, route_metadata["factual"])
            if kind == "router":
                route = route_query(query)
                expected_route = case.get("expected_route")
                if isinstance(expected_route, str):
                    route_total += 1
                    route_hits += int(route == expected_route)
                selected_metadata = route_metadata["router"]
            else:
                kind_totals[kind] = kind_totals.get(kind, 0) + 1
                selected_adapter = skill_adapter if kind == "conceptual" else retrieval
                if selected_adapter is None:
                    errors.append({"code": "adapter_unavailable", "message": "no adapter available for evaluation"})
                else:
                    try:
                        retrieved = selected_adapter.search(query, max_results=ranked_top_k)
                    except RetrievalError as exc:
                        error = {"code": exc.code, "message": redact_text(exc)}
                        if exc.details:
                            error.update(redact_report(exc.details))
                        errors.append(error)
                    except Exception as exc:
                        errors.append({"code": "retrieval_failed", "message": redact_text(exc)})
                paths = [str(item.get("source", "")).replace("\\", "/") for item in retrieved]
                try:
                    rank = paths.index(expected) + 1
                except ValueError:
                    rank = None
                if rank is not None:
                    hits += 1
                    kind_hits[kind] = kind_hits.get(kind, 0) + 1
                    reciprocal_ranks.append(1.0 / rank)
                else:
                    reciprocal_ranks.append(0.0)
            evaluated.append(
                {
                    "query": "<redacted-query>",
                    "expected_filepath": safe_expected,
                    "kind": kind,
                    "route": route,
                    "rank": rank,
                    "expected_found": rank is not None if kind != "router" else None,
                    "retrieved": [redact_text(str(item.get("source", ""))).replace("\\", "/") for item in retrieved],
                    "adapter": selected_metadata.get("adapter"),
                    "backend": selected_metadata.get("backend"),
                    "profile": selected_metadata.get("profile"),
                    "case_id": _case_identifier(case, len(evaluated) + 1),
                }
            )
        total = sum(1 for case in case_list if str(case.get("kind", "factual")) != "router")
        metrics: dict[str, float] = {
            recall_key: hits / total if total else 0.0,
            mrr_key: sum(reciprocal_ranks) / total if total else 0.0,
        }
        if route_total:
            metrics["route_accuracy"] = route_hits / route_total
        required = {recall_key: 0.85, mrr_key: 0.7}
        if thresholds:
            for key, value in thresholds.items():
                if key == "route_accuracy" and route_total:
                    try:
                        numeric = float(value)
                    except (TypeError, ValueError, OverflowError):
                        errors.append(
                            {
                                "code": "threshold_invalid",
                                "message": "route_accuracy must be a finite number from 0 through 1",
                            }
                        )
                        continue
                    if not math.isfinite(numeric) or not 0 <= numeric <= 1:
                        errors.append(
                            {
                                "code": "threshold_out_of_range",
                                "message": "route_accuracy must be a finite number from 0 through 1",
                            }
                        )
                    elif metrics["route_accuracy"] < numeric:
                        errors.append(
                            {"code": "route_below_threshold", "message": "router accuracy is below its threshold"}
                        )
                    continue
                if key not in required:
                    continue
                try:
                    numeric = float(value)
                except (TypeError, ValueError, OverflowError):
                    errors.append(
                        {"code": "threshold_invalid", "message": f"{key} must be a finite number from 0 through 1"}
                    )
                    continue
                if not math.isfinite(numeric) or not 0 <= numeric <= 1:
                    errors.append(
                        {"code": "threshold_out_of_range", "message": f"{key} must be a finite number from 0 through 1"}
                    )
                    continue
                required[key] = numeric
        if total and metrics[recall_key] < required[recall_key]:
            errors.append(
                {
                    "code": "recall_below_threshold",
                    "message": f"Recall@{metric_top_k} {metrics[recall_key]:.4f} < {required[recall_key]:.4f}",
                }
            )
        if total and metrics[mrr_key] < required[mrr_key]:
            errors.append(
                {
                    "code": "mrr_below_threshold",
                    "message": f"MRR@{metric_top_k} {metrics[mrr_key]:.4f} < {required[mrr_key]:.4f}",
                }
            )
        if thresholds and "route_accuracy" in thresholds and not route_total:
            errors.append(
                {"code": "route_cases_missing", "message": "route_accuracy requires at least one reviewed router case"}
            )
        metadata = redact_report(redact_metadata(dict(route_metadata["factual"])))
        golden_payload = (
            payload
            if isinstance(payload, Mapping)
            else {"schema_version": 1, "reviewed": reviewed, "cases": list(case_list)}
        )
        revisions = package_revisions(root, golden=golden_payload)
        metadata.update(
            {
                "top_k": metric_top_k,
                "case_count": len(case_list),
                "routes": redact_report(redact_metadata(route_metadata)),
                "package_readiness": assess_readiness(root).get("state"),
                "kind_counts": kind_totals,
                "kind_recall": {kind: kind_hits[kind] / count if count else 0.0 for kind, count in kind_totals.items()},
                "configuration": {
                    "top_k": metric_top_k,
                    "thresholds": dict(required),
                    "adapter": route_metadata["factual"].get("adapter"),
                    "backend": route_metadata["factual"].get("backend"),
                    "mode": route_metadata["factual"].get("mode"),
                },
                "revisions": revisions,
            }
        )
        response_metrics, response_metadata, response_errors, response_case_reports, response_thresholds = (
            _evaluate_response_receipt(
                root,
                response_payload,
                response_receipt_errors,
                case_list,
                revisions,
                thresholds=thresholds,
            )
        )
        errors.extend(response_errors)
        metrics.update(response_metrics)
        required.update(response_thresholds)
        configuration = metadata.get("configuration")
        if isinstance(configuration, dict):
            configuration["thresholds"] = dict(required)
        if response_metadata:
            metadata["response"] = response_metadata
        for case in evaluated:
            case_id = case.get("case_id")
            if isinstance(case_id, str) and case_id in response_case_reports:
                case["response"] = response_case_reports[case_id]
        diagnostics: list[str] = []
        if metadata.get("mode") == "diagnostic":
            diagnostics.append("Lexical retrieval is a diagnostic; use adapter=mcp for the release gate.")
        result = EvaluationResult(
            not errors, metrics, evaluated, errors, diagnostics=diagnostics, thresholds=required, metadata=metadata
        )
    except Exception as exc:
        errors.append({"code": "evaluation_failed", "message": "retrieval evaluation failed safely"})
        result = EvaluationResult(
            False, {recall_key: 0.0, mrr_key: 0.0}, evaluated, errors, diagnostics=[redact_text(exc)]
        )
    finally:
        if retrieval is not None:
            try:
                retrieval.close()
            except Exception:
                pass
    if result is None:
        result = EvaluationResult(False, {recall_key: 0.0, mrr_key: 0.0}, evaluated, errors)
    contract = validate_artifact("evaluation", result.to_dict())
    if not contract.ok:
        result.errors.extend(
            {"code": error["code"], "message": f"evaluation contract {error.get('path', '$')}: {error['message']}"}
            for error in contract.errors
        )
        result.ok = False
    golden_payload = (
        payload
        if isinstance(payload, Mapping)
        else {"schema_version": 1, "reviewed": reviewed, "cases": list(case_list)}
    )
    revisions = package_revisions(root, golden=golden_payload)
    result.metadata["revisions"] = revisions
    evidence = {
        "schema_version": 1,
        "ok": result.ok,
        "backend": result.metadata.get("backend"),
        "adapter": result.metadata.get("adapter"),
        "mode": result.metadata.get("mode"),
        "profile": result.metadata.get("profile"),
        "top_k": result.metadata.get("top_k"),
        "case_count": len(result.cases),
        "metrics": result.metrics,
        "revisions": revisions,
        "cases_hash": revisions["golden_revision"],
        "composition_hash": revisions["composition_hash"],
        "configuration": result.metadata.get("configuration"),
    }
    if "response" in result.metadata:
        evidence["response"] = result.metadata["response"]
    try:
        (root / ".docops").mkdir(parents=True, exist_ok=True)
        write_json_atomic(root / ".docops" / "evaluation.json", evidence)
        manifest_path = root / "manifest.json"
        if manifest_path.is_file() and not manifest_path.is_symlink():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(manifest, dict):
                manifest["readiness"] = assess_readiness(root)
                metrics_value = manifest.setdefault("metrics", {})
                if isinstance(metrics_value, dict):
                    metrics_value["evaluation"] = evidence
                manifest["revisions"] = revisions
                write_json_atomic(manifest_path, manifest)
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
        result.warnings.append("evaluation evidence could not be persisted")
    final_contract = validate_artifact("evaluation", result.to_dict())
    if not final_contract.ok:
        result.errors.extend(
            {"code": error["code"], "message": f"evaluation contract {error.get('path', '$')}: {error['message']}"}
            for error in final_contract.errors
        )
        result.ok = False
    return result
