"""Small, dependency-free validator for the public DOCOPS contracts.

The JSON files in ``schemas/`` are the normative source in a checkout.  This
module deliberately implements only the JSON-Schema vocabulary used by those
files so the operator remains usable from a wheel without adding a validation
dependency or contacting a network service.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

_SCHEMA_FILES = {
    "manifest": "manifest.schema.json",
    "harness": "harness.schema.json",
    "golden": "golden.schema.json",
    "validation": "validation.schema.json",
    "plan": "plan.schema.json",
    "result": "result.schema.json",
    "outcome": "outcome.schema.json",
    "evaluation": "evaluation.schema.json",
    "golden-candidates": "golden-candidates.schema.json",
    "enrichment-request": "enrichment-request.schema.json",
    "enrichment-receipt": "enrichment-receipt.schema.json",
    "evaluation-receipt": "evaluation-receipt.schema.json",
    "approval": "approval.schema.json",
    "publication": "publication.schema.json",
    "history": "history.schema.json",
    "rollback": "rollback.schema.json",
    "source-registration": "source-registration.schema.json",
    "acquisition-snapshot": "acquisition-snapshot.schema.json",
    "event": "event.schema.json",
    "job": "job.schema.json",
    "rag-authorization": "rag-authorization.schema.json",
    "job-receipt": "job-receipt.schema.json",
    "conceptual-impact": "conceptual-impact.schema.json",
    "reader-session": "reader-session.schema.json",
    "reader-query": "reader-query.schema.json",
    "rag-snapshot": "rag-snapshot.schema.json",
    "rag-reuse-plan": "rag-reuse-plan.schema.json",
    "rag-profile-comparison": "rag-profile-comparison.schema.json",
    "learning-proposal": "learning-proposal.schema.json",
    "learning-review": "learning-review.schema.json",
    "feedback": "feedback.schema.json",
    "feedback-report": "feedback-report.schema.json",
    "investigation": "investigation.schema.json",
    "lifecycle-status": "lifecycle-status.schema.json",
    "project": "project.schema.json",
    "init-session": "init-session.schema.json",
    "project-revision": "project-revision.schema.json",
    "brief": "brief.schema.json",
    "decisions": "decisions.schema.json",
    "policy": "policy.schema.json",
    "dependencies": "dependencies.schema.json",
    "source-governance": "source-governance.schema.json",
    "claim": "claim.schema.json",
    "conflict": "conflict.schema.json",
    "change-proposal": "change-proposal.schema.json",
    "impact-report": "impact-report.schema.json",
    "dependency-graph": "dependency-graph.schema.json",
    "backup-manifest": "backup-manifest.schema.json",
    "project-enrichment-request": "project-enrichment-request.schema.json",
    "delegated-authorization": "delegated-authorization.schema.json",
    "supervisor-status": "supervisor-status.schema.json",
    "project-rag-candidate-receipt": "project-rag-candidate-receipt.schema.json",
    # Farol 2.0 contracts are additive.  Keep the 1.x names above intact
    # while giving the new public envelopes explicit identities.
    "knowledge-project-v2": "knowledge-project-v2.schema.json",
    "operation-v2": "operation-v2.schema.json",
    "operation-result-v2": "operation-result-v2.schema.json",
    "capability": "capability.schema.json",
    "migration-v2": "migration-v2.schema.json",
    "ir-document": "ir-document.schema.json",
    "ir-block": "ir-block.schema.json",
    "extraction-receipt": "extraction-receipt.schema.json",
    "backend-mapping": "backend-mapping.schema.json",
    "taxonomy-proposal": "taxonomy-proposal.schema.json",
    "taxonomy": "taxonomy.schema.json",
    "taxonomy-approval": "taxonomy-approval.schema.json",
    "skill-lineage": "skill-lineage.schema.json",
    "synthesis-request": "synthesis-request.schema.json",
    "synthesis-receipt": "synthesis-receipt.schema.json",
    "route-plan": "route-plan.schema.json",
    "query-request-v2": "query-request-v2.schema.json",
    "evidence-result-v2": "evidence-result-v2.schema.json",
    "backend-config": "backend-config.schema.json",
    "backend-candidate": "backend-candidate.schema.json",
    "index-revision": "index-revision.schema.json",
    "composition-v2": "composition-v2.schema.json",
    "migration-receipt": "migration-receipt.schema.json",
    "project-operation-v2": "project-operation-v2.schema.json",
    "cutover-decision": "cutover-decision.schema.json",
}


@dataclass(frozen=True)
class ContractResult:
    """A serializable result for one normative artifact contract."""

    ok: bool
    artifact: str
    errors: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": 1, "ok": self.ok, "artifact": self.artifact, "errors": self.errors}


def _schema_roots() -> tuple[Path, ...]:
    module_root = Path(__file__).resolve()
    return (
        module_root.parents[1] / "schemas",
        module_root.parent / "schemas",
    )


def schema_path(artifact: str) -> Path | None:
    """Return the installed or checkout schema path for ``artifact``."""

    filename = _SCHEMA_FILES.get(artifact)
    if filename is None:
        return None
    for root in _schema_roots():
        candidate = root / filename
        if candidate.is_file():
            return candidate
    return None


def load_schema(artifact: str) -> dict[str, Any]:
    """Load one public schema, raising a useful error when it is unavailable."""

    path = schema_path(artifact)
    if path is None:
        raise FileNotFoundError(f"schema not found for artifact {artifact!r}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"schema for {artifact!r} must be an object")
    return value


def _json_type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, Mapping)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def _error(errors: list[dict[str, str]], code: str, path: str, message: str) -> None:
    errors.append({"code": code, "path": path or "$", "message": message})


def _resolve_ref(schema: Mapping[str, Any], reference: str) -> Mapping[str, Any] | None:
    if not reference.startswith("#/"):
        return None
    value: Any = schema
    for part in reference[2:].split("/"):
        if not isinstance(value, Mapping):
            return None
        value = value.get(part)
    return value if isinstance(value, Mapping) else None


def _validate(
    value: Any, rule: Mapping[str, Any], root_schema: Mapping[str, Any], path: str, errors: list[dict[str, str]]
) -> None:
    for combinator in ("oneOf", "anyOf"):
        choices = rule.get(combinator)
        if isinstance(choices, list) and choices:
            valid = 0
            choice_errors: list[list[dict[str, str]]] = []
            for choice in choices:
                if not isinstance(choice, Mapping):
                    continue
                local: list[dict[str, str]] = []
                _validate(value, choice, root_schema, path, local)
                if not local:
                    valid += 1
                choice_errors.append(local)
            required_valid = 1
            combinator_ok = valid == required_valid if combinator == "oneOf" else valid >= required_valid
            if not combinator_ok:
                _error(errors, "contract_combinator", path, f"value does not satisfy {combinator}")
            return

    reference = rule.get("$ref")
    if isinstance(reference, str):
        target = _resolve_ref(root_schema, reference)
        if target is None:
            _error(errors, "contract_ref", path, f"unsupported schema reference {reference!r}")
        else:
            _validate(value, target, root_schema, path, errors)
        return

    if "const" in rule and value != rule["const"]:
        _error(errors, "contract_const", path, f"value must equal {rule['const']!r}")
    enum = rule.get("enum")
    if isinstance(enum, list) and value not in enum:
        _error(errors, "contract_enum", path, f"value must be one of {enum!r}")

    expected = rule.get("type")
    if isinstance(expected, str) and not _json_type_matches(value, expected):
        _error(errors, "contract_type", path, f"expected JSON type {expected}")
        return
    if isinstance(expected, list) and not any(
        isinstance(item, str) and _json_type_matches(value, item) for item in expected
    ):
        _error(errors, "contract_type", path, f"expected one of JSON types {expected!r}")
        return

    if isinstance(value, Mapping):
        required = rule.get("required", [])
        if isinstance(required, list):
            for name in required:
                if isinstance(name, str) and name not in value:
                    _error(errors, "contract_required", f"{path}.{name}" if path else name, "required field is missing")
        properties = rule.get("properties", {})
        if isinstance(properties, Mapping):
            for name, child_rule in properties.items():
                if name in value and isinstance(child_rule, Mapping):
                    _validate(value[name], child_rule, root_schema, f"{path}.{name}" if path else str(name), errors)
            if rule.get("additionalProperties") is False:
                allowed = {str(name) for name in properties}
                for name in value:
                    if str(name) not in allowed:
                        _error(
                            errors,
                            "contract_additional_property",
                            f"{path}.{name}" if path else str(name),
                            "field is not declared by the contract; put namespaced data under extensions",
                        )
    if isinstance(value, list) and isinstance(rule.get("items"), Mapping):
        for index, item in enumerate(value):
            _validate(item, rule["items"], root_schema, f"{path}[{index}]", errors)
    if isinstance(value, str) and isinstance(rule.get("minLength"), int) and len(value) < rule["minLength"]:
        _error(errors, "contract_min_length", path, "string is shorter than the minimum length")
    if isinstance(value, list) and isinstance(rule.get("minItems"), int) and len(value) < rule["minItems"]:
        _error(errors, "contract_min_items", path, "array has fewer items than the minimum")
    if isinstance(value, list) and isinstance(rule.get("maxItems"), int) and len(value) > rule["maxItems"]:
        _error(errors, "contract_max_items", path, "array has more items than the maximum")
    if isinstance(value, list) and rule.get("uniqueItems") is True:
        canonical = [json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for item in value]
        if len(canonical) != len(set(canonical)):
            _error(errors, "contract_unique_items", path, "array items must be unique")
    if isinstance(value, str) and isinstance(rule.get("maxLength"), int) and len(value) > rule["maxLength"]:
        _error(errors, "contract_max_length", path, "string is longer than the maximum length")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = rule.get("minimum")
        if isinstance(minimum, (int, float)) and value < minimum:
            _error(errors, "contract_minimum", path, "number is below the minimum")
        maximum = rule.get("maximum")
        if isinstance(maximum, (int, float)) and value > maximum:
            _error(errors, "contract_maximum", path, "number is above the maximum")
    pattern = rule.get("pattern")
    if isinstance(value, str) and isinstance(pattern, str):
        import re

        if re.search(pattern, value) is None:
            _error(errors, "contract_pattern", path, "string does not match the required pattern")


def validate_artifact(artifact: str, payload: Any) -> ContractResult:
    """Validate a public artifact against its checked-in JSON schema."""

    if artifact not in _SCHEMA_FILES:
        return ContractResult(
            False, artifact, [{"code": "contract_unknown", "path": "$", "message": "unknown public artifact"}]
        )
    try:
        schema = load_schema(artifact)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return ContractResult(
            False, artifact, [{"code": "contract_schema_unavailable", "path": "$", "message": str(exc)}]
        )
    errors: list[dict[str, str]] = []
    _validate(payload, schema, schema, "$", errors)
    return ContractResult(not errors, artifact, errors)


def validate_contract(
    artifact: str,
    payload: Any,
    *,
    expected_revision: int | None = None,
    existing_payload: Mapping[str, Any] | None = None,
) -> ContractResult:
    """Validate a public envelope and classify optimistic-concurrency conflicts.

    ``validate_artifact`` remains the low-level schema check used by 1.x.  V2
    callers use this wrapper so a stale schema, compare-and-swap revision, and
    reused idempotency key cannot collapse into one generic validation error.
    The function is deliberately stateless: persistence and single-writer
    coordination belong to the project module.
    """

    if not isinstance(payload, Mapping):
        return ContractResult(
            False,
            artifact,
            [{"code": "schema_invalid", "path": "$", "message": "contract payload must be an object"}],
        )

    try:
        schema = load_schema(artifact)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return ContractResult(
            False,
            artifact,
            [{"code": "contract_schema_unavailable", "path": "$", "message": str(exc)}],
        )

    schema_properties = schema.get("properties") if isinstance(schema, Mapping) else None
    version_rule = schema_properties.get("schema_version") if isinstance(schema_properties, Mapping) else None
    expected_schema_version = version_rule.get("const") if isinstance(version_rule, Mapping) else None
    if expected_schema_version is not None and payload.get("schema_version") != expected_schema_version:
        return ContractResult(
            False,
            artifact,
            [
                {
                    "code": "schema_version_conflict",
                    "path": "$.schema_version",
                    "message": f"expected schema version {expected_schema_version}",
                }
            ],
        )

    validation = validate_artifact(artifact, payload)
    if not validation.ok:
        return validation

    if expected_revision is not None and payload.get("expected_revision") != expected_revision:
        return ContractResult(
            False,
            artifact,
            [
                {
                    "code": "revision_conflict",
                    "path": "$.expected_revision",
                    "message": "expected revision does not match the current project revision",
                }
            ],
        )

    if existing_payload is not None:
        current_key = payload.get("idempotency_key")
        previous_key = existing_payload.get("idempotency_key")
        if isinstance(current_key, str) and current_key and current_key == previous_key:
            current_canonical = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            previous_canonical = json.dumps(
                dict(existing_payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            if current_canonical != previous_canonical:
                return ContractResult(
                    False,
                    artifact,
                    [
                        {
                            "code": "idempotency_conflict",
                            "path": "$.idempotency_key",
                            "message": "idempotency key was already used with a different payload",
                        }
                    ],
                )

    return validation


def contract_names() -> tuple[str, ...]:
    """Return the public artifact names covered by this validator."""

    return tuple(_SCHEMA_FILES)
