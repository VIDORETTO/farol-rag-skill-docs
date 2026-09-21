"""Stable serializable types shared by the public API and compatibility CLI."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .observability import redact_report, redact_text
from .package_validator import ValidationResult
from .primitives import absolute_path_without_resolving

SUPPORTED_LAYERS = ("conceptual", "factual")
V2_SCHEMA_VERSION = 2
V2_CONTRACT_VERSION = "2.0"


def _v2_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_copy(value: Any) -> Any:
    """Copy only JSON-compatible data at a public contract boundary."""

    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))


@dataclass(frozen=True)
class KnowledgeProjectV2:
    """Immutable public identity for a resumable Farol 2.0 project."""

    project_id: str
    session_id: str
    revision: int
    name: str
    objective: str
    sources: list[dict[str, Any]]
    taxonomy_revision: str | None = None
    active_composition_id: str | None = None
    status: str = "proposed"
    created_at: str = field(default_factory=_v2_now)
    extensions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _json_copy(
            {
                "schema_version": V2_SCHEMA_VERSION,
                "contract_version": V2_CONTRACT_VERSION,
                "kind": "knowledge_project",
                "project_id": self.project_id,
                "session_id": self.session_id,
                "revision": self.revision,
                "name": self.name,
                "objective": self.objective,
                "sources": self.sources,
                "taxonomy_revision": self.taxonomy_revision,
                "active_composition_id": self.active_composition_id,
                "status": self.status,
                "created_at": self.created_at,
                "extensions": self.extensions,
            }
        )


@dataclass(frozen=True)
class OperationRequestV2:
    """Idempotent request envelope for a project operation."""

    operation_id: str
    project_id: str
    session_id: str
    operation: str
    idempotency_key: str
    expected_revision: int
    inputs: dict[str, Any] = field(default_factory=dict)
    requested_at: str = field(default_factory=_v2_now)
    extensions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _json_copy(
            {
                "schema_version": V2_SCHEMA_VERSION,
                "contract_version": V2_CONTRACT_VERSION,
                "kind": "operation",
                "operation_id": self.operation_id,
                "project_id": self.project_id,
                "session_id": self.session_id,
                "operation": self.operation,
                "idempotency_key": self.idempotency_key,
                "expected_revision": self.expected_revision,
                "inputs": self.inputs,
                "requested_at": self.requested_at,
                "extensions": self.extensions,
            }
        )

    def request_fingerprint(self) -> str:
        from .revisions import content_hash

        payload = self.to_dict()
        payload.pop("requested_at", None)
        return content_hash(payload)


@dataclass(frozen=True)
class OperationResultV2:
    """Versioned terminal/resumable result returned by the v2 operation seam."""

    operation_id: str
    project_id: str
    idempotency_key: str
    status: str
    revision: int
    pending: list[dict[str, Any]] = field(default_factory=list)
    next_action: str = "inspect project state"
    blockers: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _json_copy(
            {
                "schema_version": V2_SCHEMA_VERSION,
                "contract_version": V2_CONTRACT_VERSION,
                "kind": "operation_result",
                "operation_id": self.operation_id,
                "project_id": self.project_id,
                "idempotency_key": self.idempotency_key,
                "status": self.status,
                "revision": self.revision,
                "pending": self.pending,
                "next_action": self.next_action,
                "blockers": self.blockers,
                "result": self.result,
                "extensions": self.extensions,
            }
        )


@dataclass(frozen=True)
class CapabilityV2:
    """Capability report for a parser or knowledge backend."""

    name: str
    version: str
    status: str
    supports: list[str]
    fidelity: list[str]
    execution: str
    permissions: list[str]
    dependencies: list[dict[str, Any]]
    extensions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _json_copy(
            {
                "schema_version": V2_SCHEMA_VERSION,
                "contract_version": V2_CONTRACT_VERSION,
                "kind": "capability",
                "name": self.name,
                "version": self.version,
                "status": self.status,
                "supports": self.supports,
                "fidelity": self.fidelity,
                "execution": self.execution,
                "permissions": self.permissions,
                "dependencies": self.dependencies,
                "extensions": self.extensions,
            }
        )


@dataclass(frozen=True)
class MigrationPlanV2:
    """Read-only plan describing a 1.x to 2.0 staging operation."""

    migration_id: str
    source_version: str
    source_identity: dict[str, Any]
    destination_project_id: str
    plan_hash: str
    mode: str
    imported: list[dict[str, Any]]
    excluded: list[dict[str, Any]]
    status: str = "planned"
    warnings: list[str] = field(default_factory=list)
    rollback_ref: str | None = None
    extensions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _json_copy(
            {
                "schema_version": V2_SCHEMA_VERSION,
                "contract_version": V2_CONTRACT_VERSION,
                "kind": "migration",
                "migration_id": self.migration_id,
                "source_version": self.source_version,
                "source_identity": self.source_identity,
                "destination_project_id": self.destination_project_id,
                "plan_hash": self.plan_hash,
                "mode": self.mode,
                "imported": self.imported,
                "excluded": self.excluded,
                "warnings": self.warnings,
                "status": self.status,
                "rollback_ref": self.rollback_ref,
                "extensions": self.extensions,
            }
        )


def normalize_layers(value: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    """Normalize the explicit conceptual/factual update selection."""

    if value is None:
        return SUPPORTED_LAYERS
    normalized = tuple(dict.fromkeys(str(item).strip().casefold() for item in value if str(item).strip()))
    if not normalized:
        raise ValueError("layers must include conceptual, factual or both")
    unsupported = sorted(set(normalized) - set(SUPPORTED_LAYERS))
    if unsupported:
        raise ValueError(f"unsupported layers: {', '.join(unsupported)}")
    return tuple(layer for layer in SUPPORTED_LAYERS if layer in normalized)


@dataclass
class PipelineOptions:
    """Mutable 1.0 CLI options retained as a compatibility input type."""

    output_dir: Path
    catalog: Path | None = None
    slug: str | None = None
    version: str | None = None
    scope: str | None = None
    language: str | None = None
    mode: str = "run"
    layers: tuple[str, ...] = SUPPORTED_LAYERS
    publication_policy: str = "direct"
    license: str | None = None
    redistribution: str = "private-only"
    index_rag: bool = False
    max_pages: int = 50
    max_depth: int = 2
    include_patterns: tuple[str, ...] = ()
    exclude_patterns: tuple[str, ...] = ()
    allow_private_network: bool = False
    runtime_root: Path | None = None
    source_root: Path | None = None
    lease_policy: str = "fail"
    lease_timeout_seconds: float = 0.0
    stale_lease_seconds: float = 300.0

    def __post_init__(self) -> None:
        self.output_dir = absolute_path_without_resolving(self.output_dir)
        if self.mode not in {"create", "update", "run", "dry-run"}:
            raise ValueError("mode must be create, update, run or dry-run")
        self.layers = normalize_layers(self.layers)
        if self.publication_policy not in {"direct", "candidate"}:
            raise ValueError("publication_policy must be direct or candidate")
        if self.redistribution not in {"private-only", "internal", "public"}:
            raise ValueError("redistribution must be private-only, internal or public")
        if (
            isinstance(self.max_pages, bool)
            or not isinstance(self.max_pages, int)
            or isinstance(self.max_depth, bool)
            or not isinstance(self.max_depth, int)
            or self.max_pages < 1
            or self.max_depth < 0
        ):
            raise ValueError("max_pages must be positive and max_depth cannot be negative")
        if self.runtime_root is not None:
            self.runtime_root = Path(self.runtime_root).expanduser().resolve()
        self.source_root = Path(self.source_root or Path.cwd()).expanduser().resolve()
        if self.lease_policy not in {"fail", "wait"}:
            raise ValueError("lease_policy must be fail or wait")
        if self.lease_timeout_seconds < 0 or self.stale_lease_seconds <= 0:
            raise ValueError("lease timeouts must be non-negative and stale_lease_seconds must be positive")


class _FrozenDict(dict[str, Any]):
    """JSON-compatible dictionary that rejects every mutation."""

    def __init__(self, value: Mapping[str, Any]) -> None:
        dict.__init__(self, value)

    @staticmethod
    def _blocked(*_args: Any, **_kwargs: Any) -> None:
        raise TypeError("immutable result mapping")

    __setitem__ = _blocked
    __delitem__ = _blocked
    clear = _blocked
    pop = _blocked
    popitem = _blocked
    setdefault = _blocked
    update = _blocked
    __ior__ = _blocked


class _FrozenList(list[Any]):
    """JSON-compatible list that rejects every mutation."""

    def __init__(self, value: Any) -> None:
        list.__init__(self, value)

    @staticmethod
    def _blocked(*_args: Any, **_kwargs: Any) -> None:
        raise AttributeError("immutable result sequence")

    __setitem__ = _blocked
    __delitem__ = _blocked
    __iadd__ = _blocked
    __imul__ = _blocked
    append = _blocked
    clear = _blocked
    extend = _blocked
    insert = _blocked
    pop = _blocked
    remove = _blocked
    reverse = _blocked
    sort = _blocked


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _FrozenDict({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return _FrozenList(_freeze(item) for item in value)
    if isinstance(value, set):
        return _FrozenList(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, frozenset)):
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True)
class _FrozenValidationResult:
    """Immutable snapshot of the mutable validator result at the API boundary."""

    ok: bool
    errors: tuple[Mapping[str, Any], ...]
    warnings: tuple[Mapping[str, Any], ...]
    checks: Mapping[str, Any]

    @classmethod
    def from_result(cls, result: ValidationResult) -> "_FrozenValidationResult":
        return cls(
            result.ok,
            tuple(_freeze(error) for error in result.errors),
            tuple(_freeze(warning) for warning in result.warnings),
            _freeze(result.checks),
        )

    def to_dict(self) -> dict[str, Any]:
        return redact_report(
            {
                "schema_version": 1,
                "ok": self.ok,
                "errors": _thaw(self.errors),
                "warnings": _thaw(self.warnings),
                "checks": _thaw(self.checks),
            }
        )


@dataclass(frozen=True)
class PipelineResult:
    """Immutable terminal result shared by the API and legacy CLI adapter."""

    ok: bool
    output_dir: Path
    manifest: Mapping[str, Any]
    validation: ValidationResult | _FrozenValidationResult | None = None
    state_diff: Mapping[str, int] = field(default_factory=lambda: {"added": 0, "updated": 0, "removed": 0})
    written_files: int = 0
    errors: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    outcome: Mapping[str, Any] = field(
        default_factory=lambda: {
            "status": "failed",
            "code": "unknown",
            "phase": "unknown",
            "message": "operation did not produce an outcome",
            "exit_code": 1,
        }
    )
    exit_code: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "manifest", _freeze(self.manifest))
        if self.validation is not None and not isinstance(self.validation, _FrozenValidationResult):
            object.__setattr__(self, "validation", _FrozenValidationResult.from_result(self.validation))
        object.__setattr__(self, "state_diff", _freeze(self.state_diff))
        object.__setattr__(self, "errors", _freeze(self.errors))
        object.__setattr__(self, "warnings", _freeze(self.warnings))
        object.__setattr__(self, "outcome", _freeze(self.outcome))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "ok": self.ok,
            "output_dir": redact_text(self.output_dir),
            "manifest": redact_report(self.manifest),
            "validation": self.validation.to_dict() if self.validation else None,
            "state_diff": _thaw(self.state_diff),
            "written_files": self.written_files,
            "errors": redact_report(_thaw(self.errors)),
            "warnings": [redact_text(warning) for warning in self.warnings],
            "outcome": redact_report(_thaw(self.outcome)),
            "exit_code": self.exit_code,
        }

    def json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
