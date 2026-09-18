"""Public plan/apply operation seam for DOCOPS.

The implementation keeps acquisition and normalization deterministic while
making mutation a transaction over a complete staged package.  Callers only
need :func:`plan`, :func:`apply` and :func:`inspect`; the older
``run_pipeline`` adapter lives in :mod:`docops.pipeline`.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from .api_types import PipelineOptions, PipelineResult, normalize_layers
from .candidates import (
    CandidateError,
    candidate_locator,
    candidate_path,
    finalize_candidate,
    list_candidates,
)
from .contracts import validate_artifact
from .generation import check_generated_artifacts, write_generated_artifact_inventory, write_router, write_skill
from .harness import build_harness_manifest
from .learning import admitted_learning_documents, copy_learning_state, rollback_learning_guard
from .lease import LeaseBusyError, PackageLease
from .manifest import build_manifest, read_manifest, redact_entry, redact_metadata, redact_url, utc_now, write_manifest
from .normalizer import normalize_file
from .observability import redact_report, redact_text
from .package_validator import ValidationResult, validate_package
from .primitives import (
    destination_for_file as _destination_for_file,
)
from .primitives import (
    local_record_canonical as _local_record_canonical,
)
from .primitives import (
    output_inside_source as _output_inside_source,
)
from .primitives import (
    path_from_file_uri as _path_from_file_uri,
)
from .primitives import (
    safe_relpath as _safe_relpath,
)
from .primitives import (
    skill_name as _skill_name,
)
from .primitives import (
    unique_destination as _unique_destination,
)
from .primitives import (
    write_if_changed as _write_if_changed,
)
from .rag_sync import RagSynchronizer, embedding_configuration, package_rag_config_text
from .readiness import assess_readiness
from .repository_acquirer import RepositoryAcquirer
from .revisions import evidence_matches_package, file_hash, package_revisions
from .runtime import runtime_provenance
from .source_resolver import SourceResolution, SourceResolver, canonicalize_url
from .state import CheckpointStore, SourceRecord, StateStore
from .storage import write_json_atomic, write_text_atomic
from .web_acquirer import CrawlOptions, FetchPolicy, WebAcquirer

PLAN_VERSION = 1
_ARTIFACTS = {"skill": "skill", "router": "router", "rag": "rag", "harness": "harness.json", "config": "config.yaml"}
_GENERATED_ROOTS = {"skill", "router", "rag", "harness.json", "manifest.json", "config.yaml", ".docops"}
_PRESERVED_CONCEPTUAL_METADATA = (
    ".docops/generated-artifacts.json",
    ".docops/generated-skill.json",
    ".docops/skill-enrichment.json",
    ".docops/evaluation.json",
    ".docops/release-evidence.json",
    ".docops/policy.json",
    ".docops/approval.json",
    ".docops/publication.json",
)


class OperationFailure(RuntimeError):
    """An expected, reportable failure in one apply phase."""

    def __init__(self, code: str, message: str, *, phase: str, details: Mapping[str, Any] | None = None) -> None:
        self.code = code
        self.phase = phase
        self.details = dict(details or {})
        super().__init__(message)


class CandidatePublicationError(ValueError):
    """Raised when candidate approval or publication cannot proceed safely."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        phase: str = "approval",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.phase = phase
        self.details = dict(details or {})
        super().__init__(message)


@dataclass(frozen=True)
class OperationOptions:
    """Defensive, immutable options used by the supported Python interface."""

    output_dir: Path
    catalog: Path | None = None
    slug: str | None = None
    version: str | None = None
    scope: str | None = None
    language: str | None = None
    mode: str = "run"
    layers: tuple[str, ...] = ("conceptual", "factual")
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
        object.__setattr__(self, "output_dir", Path(os.path.abspath(os.fspath(self.output_dir))))
        if self.catalog is not None:
            object.__setattr__(self, "catalog", Path(self.catalog).expanduser())
        if self.runtime_root is not None:
            object.__setattr__(self, "runtime_root", Path(self.runtime_root).expanduser().resolve())
        if self.source_root is not None:
            object.__setattr__(self, "source_root", Path(self.source_root).expanduser().resolve())
        object.__setattr__(self, "include_patterns", tuple(self.include_patterns))
        object.__setattr__(self, "exclude_patterns", tuple(self.exclude_patterns))
        object.__setattr__(self, "layers", normalize_layers(self.layers))
        if self.mode not in {"create", "update", "run", "dry-run"}:
            raise ValueError("mode must be create, update, run or dry-run")
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
        if self.lease_policy not in {"fail", "wait"}:
            raise ValueError("lease_policy must be fail or wait")
        if self.lease_timeout_seconds < 0 or self.stale_lease_seconds <= 0:
            raise ValueError("lease timeouts must be non-negative and stale_lease_seconds must be positive")

    @classmethod
    def from_pipeline_options(cls, options: PipelineOptions) -> "OperationOptions":
        return cls(
            output_dir=Path(options.output_dir),
            catalog=Path(options.catalog) if options.catalog else None,
            slug=options.slug,
            version=options.version,
            scope=options.scope,
            language=options.language,
            mode=options.mode,
            layers=tuple(options.layers),
            publication_policy=options.publication_policy,
            license=options.license,
            redistribution=options.redistribution,
            index_rag=options.index_rag,
            max_pages=options.max_pages,
            max_depth=options.max_depth,
            include_patterns=tuple(options.include_patterns),
            exclude_patterns=tuple(options.exclude_patterns),
            allow_private_network=options.allow_private_network,
            runtime_root=Path(options.runtime_root) if options.runtime_root else None,
            source_root=Path(options.source_root) if options.source_root else None,
            lease_policy=options.lease_policy,
            lease_timeout_seconds=options.lease_timeout_seconds,
            stale_lease_seconds=options.stale_lease_seconds,
        )


@dataclass(frozen=True)
class OperationRequest:
    """Immutable request captured by a plan."""

    source: str
    options: PipelineOptions | OperationOptions

    def __post_init__(self) -> None:
        object.__setattr__(self, "source", str(self.source))
        if isinstance(self.options, PipelineOptions):
            object.__setattr__(self, "options", OperationOptions.from_pipeline_options(self.options))
        elif not isinstance(self.options, OperationOptions):
            raise TypeError("OperationRequest.options must be OperationOptions or PipelineOptions")

    def to_dict(self) -> dict[str, Any]:
        options = self.options
        return {
            "source": redact_url(self.source),
            "output_dir": "<local-output>",
            "catalog": "<local-catalog>" if options.catalog else None,
            "slug": options.slug,
            "version": options.version,
            "scope": options.scope,
            "language": options.language,
            "mode": options.mode,
            "layers": list(options.layers),
            "publication_policy": options.publication_policy,
            "license": options.license or "unknown",
            "redistribution": options.redistribution,
            "index_rag": options.index_rag,
            "max_pages": options.max_pages,
            "max_depth": options.max_depth,
            "include_patterns": list(options.include_patterns),
            "exclude_patterns": list(options.exclude_patterns),
            "allow_private_network": options.allow_private_network,
            "lease_policy": options.lease_policy,
            "lease_timeout_seconds": options.lease_timeout_seconds,
            "stale_lease_seconds": options.stale_lease_seconds,
        }

    def identity(self) -> dict[str, Any]:
        options = self.options
        return {
            "source": self.source,
            "output_dir": str(options.output_dir),
            "catalog": str(options.catalog) if options.catalog else None,
            "slug": options.slug,
            "version": options.version,
            "scope": options.scope,
            "language": options.language,
            "mode": options.mode,
            "layers": list(options.layers),
            "publication_policy": options.publication_policy,
            "license": options.license,
            "redistribution": options.redistribution,
            "index_rag": options.index_rag,
            "max_pages": options.max_pages,
            "max_depth": options.max_depth,
            "include_patterns": list(options.include_patterns),
            "exclude_patterns": list(options.exclude_patterns),
            "allow_private_network": options.allow_private_network,
            "runtime_root": str(options.runtime_root) if options.runtime_root else None,
            "source_root": str(options.source_root) if options.source_root else None,
            "lease_timeout_seconds": options.lease_timeout_seconds,
            "stale_lease_seconds": options.stale_lease_seconds,
        }


@dataclass(frozen=True)
class PlanAction:
    """One material source action that apply is allowed to perform."""

    kind: str
    destination: str
    identity: str
    content_hash: str | None = None
    previous_hash: str | None = None
    canonical: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "destination": self.destination,
            "identity": self.identity,
            "content_hash": self.content_hash,
            "previous_hash": self.previous_hash,
            "canonical": redact_url(self.canonical) if self.canonical else None,
        }


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True)
class OperationPlan:
    """Immutable, reviewable decision that can be passed to :func:`apply`."""

    request: OperationRequest
    resolution: SourceResolution
    mode: str
    actions: tuple[PlanAction, ...]
    blockers: tuple[Mapping[str, Any], ...]
    warnings: tuple[str, ...]
    expected_readiness: Mapping[str, str]
    source_fingerprint: str
    destination_fingerprint: str
    request_fingerprint: str
    entries: tuple[Mapping[str, Any], ...]
    records: tuple[SourceRecord, ...]
    provenance: Mapping[str, Any]
    state_diff: Mapping[str, int]
    config_content: str | None
    plan_hash: str

    @property
    def ok(self) -> bool:
        return not self.blockers

    @property
    def plan_id(self) -> str:
        return f"plan-{self.plan_hash[:16]}"

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": 1,
            "plan_version": PLAN_VERSION,
            "plan_hash": self.plan_hash,
            "mode": self.request.options.mode,
            "effective_mode": self.mode,
            "request": self.request.to_dict(),
            "resolution": redact_report(redact_metadata(self.resolution.to_dict())),
            "actions": [action.to_dict() for action in self.actions],
            "blockers": [redact_report(redact_metadata(dict(blocker))) for blocker in self.blockers],
            "warnings": [redact_text(warning) for warning in self.warnings],
            "expected_readiness": dict(self.expected_readiness),
            "source_fingerprint": self.source_fingerprint,
            "destination_fingerprint": self.destination_fingerprint,
            "request_fingerprint": self.request_fingerprint,
            "state_diff": dict(self.state_diff),
        }
        return payload

    def json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"


@dataclass(frozen=True)
class _Collection:
    resolution: SourceResolution
    entries: tuple[Mapping[str, Any], ...]
    records: tuple[SourceRecord, ...]
    warnings: tuple[str, ...]
    errors: tuple[dict[str, str], ...]
    provenance: Mapping[str, Any]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash_payload(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        if path.is_symlink():
            digest.update(b"symlink:")
            digest.update(os.readlink(path).encode("utf-8", errors="replace"))
            return digest.hexdigest()
        if path.is_file():
            digest.update(b"file:")
            digest.update(path.read_bytes())
            return digest.hexdigest()
        if path.is_dir():
            digest.update(b"dir:")
            for child in sorted(path.rglob("*")):
                relative = child.relative_to(path).as_posix().encode("utf-8")
                digest.update(relative)
                digest.update(_file_digest(child).encode("ascii"))
            return digest.hexdigest()
    except OSError:
        digest.update(b"unreadable")
    digest.update(b"missing")
    return digest.hexdigest()


def _tree_snapshot(root: Path) -> dict[str, str]:
    if not root.is_dir() or root.is_symlink():
        return {}
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_dir() or path.is_symlink() and not path.is_file():
            continue
        if ".docops" in path.relative_to(root).parts and path.name.startswith("."):
            continue
        result[path.relative_to(root).as_posix()] = _file_digest(path)
    return result


def _destination_fingerprint(root: Path) -> str:
    if not root.exists():
        return "absent"
    return _hash_payload(_tree_snapshot(root))


def _source_fingerprint(entries: Iterable[Mapping[str, Any]], resolution: SourceResolution) -> str:
    values = []
    for entry in entries:
        values.append(
            {
                "source": entry.get("source"),
                "canonical": entry.get("canonical"),
                "status": entry.get("status"),
                "destination": entry.get("destination"),
                "content_hash": entry.get("content_hash"),
                "code": entry.get("code"),
            }
        )
    return _hash_payload({"resolution": resolution.to_dict(), "entries": values})


def _runtime_root(options: PipelineOptions) -> Path:
    return options.runtime_root or Path(__file__).resolve().parents[1]


def _resolver(options: PipelineOptions) -> SourceResolver:
    root = options.source_root or Path.cwd()
    if options.catalog:
        catalog = Path(options.catalog)
        if not catalog.is_absolute():
            catalog = root / catalog
        return SourceResolver.from_catalog_file(catalog, root=root)
    return SourceResolver(root=root)


def _resolution_with_options(resolution: SourceResolution, options: PipelineOptions) -> SourceResolution:
    if not resolution.selected:
        return resolution
    selected = resolution.selected
    selected = selected.__class__(
        kind=selected.kind,
        slug=_skill_name(options.slug or selected.slug),
        canonical=selected.canonical,
        url=selected.url,
        repo_url=selected.repo_url,
        docs_url=selected.docs_url,
        version=options.version or selected.version,
        scope=options.scope or selected.scope,
        language=options.language or selected.language,
        license=selected.license,
        official=selected.official,
        confidence=selected.confidence,
        evidence=selected.evidence,
        aliases=selected.aliases,
        provider=selected.provider,
    )
    return SourceResolution(
        resolution.input,
        resolution.kind,
        selected,
        resolution.candidates,
        resolution.requires_decision,
        resolution.decision_reason,
        resolution.error,
    )


def _collect(source: str | Path, resolution: SourceResolution, options: PipelineOptions) -> _Collection:
    entries: list[dict[str, Any]] = []
    records: list[SourceRecord] = []
    warnings: list[str] = []
    errors: list[dict[str, str]] = []
    repository_metadata: dict[str, Any] = {}
    local_path: Path | None = None
    repo_result: Any = None
    license_value = options.license or (resolution.selected.license if resolution.selected else None) or "unknown"

    try:
        if resolution.kind == "local":
            local_path = _path_from_file_uri(resolution.selected.canonical)
            if local_path.is_dir() and (local_path / ".git").exists():
                repo_result = RepositoryAcquirer(allow_private_network=options.allow_private_network).acquire(
                    local_path, version=options.version, scope=options.scope, language=options.language
                )
                if not repo_result.ok or not repo_result.docs_path:
                    errors.extend(repo_result.errors)
                    return _Collection(resolution, (), (), tuple(warnings), tuple(errors), {"license": license_value})
                local_path = repo_result.docs_path
                if not options.license:
                    license_value = str(repo_result.license.get("identifier") or license_value)
                resolution = SourceResolution(
                    resolution.input,
                    resolution.kind,
                    resolution.selected.__class__(
                        **{
                            **resolution.selected.__dict__,
                            "version": repo_result.version or resolution.selected.version,
                            "scope": repo_result.docs_relative or resolution.selected.scope,
                        }
                    ),
                    resolution.candidates,
                    resolution.requires_decision,
                    resolution.decision_reason,
                    resolution.error,
                )
                repository_metadata = {"commit": repo_result.commit, "docs_relative": repo_result.docs_relative}
                warnings.extend(repo_result.warnings)
        elif resolution.kind == "repository":
            repo_result = RepositoryAcquirer(allow_private_network=options.allow_private_network).acquire(
                resolution, version=options.version, scope=options.scope, language=options.language
            )
            if not repo_result.ok or not repo_result.root or not repo_result.docs_path:
                errors.extend(repo_result.errors)
                return _Collection(resolution, (), (), tuple(warnings), tuple(errors), {"license": license_value})
            local_path = repo_result.docs_path
            if not options.license:
                license_value = str(repo_result.license.get("identifier") or license_value)
            resolution = SourceResolution(
                resolution.input,
                resolution.kind,
                resolution.selected.__class__(
                    **{
                        **resolution.selected.__dict__,
                        "version": repo_result.version or resolution.selected.version,
                        "scope": repo_result.docs_relative or resolution.selected.scope,
                        "language": options.language or resolution.selected.language,
                    }
                ),
                resolution.candidates,
                resolution.requires_decision,
                resolution.decision_reason,
                resolution.error,
            )
            repository_metadata = {"commit": repo_result.commit, "docs_relative": repo_result.docs_relative}
            warnings.extend(repo_result.warnings)

        if local_path is not None:
            base = local_path if local_path.is_dir() else local_path.parent
            files = [local_path] if local_path.is_file() else _source_files_for_plan(local_path, options.output_dir)
            used_destinations: set[str] = set()
            for file_path in files:
                normalized = normalize_file(file_path)
                effective_status = normalized.status
                if normalized.status == "accepted" and normalized.quality_status == "quarantine":
                    effective_status = "quarantined"
                relative_destination = (
                    _unique_destination(
                        _destination_for_file(file_path, base, normalized), file_path, used_destinations
                    )
                    if effective_status == "accepted"
                    else None
                )
                if relative_destination:
                    used_destinations.add(relative_destination)
                entry: dict[str, Any] = {
                    "source": normalized.origin,
                    "canonical": canonicalize_url(normalized.origin),
                    "status": effective_status if effective_status != "dependency_missing" else "error",
                    "destination": relative_destination,
                    "title": normalized.title,
                    "format": normalized.format,
                    "warnings": normalized.warnings,
                    "untrusted": normalized.untrusted,
                    "locators": normalized.locators,
                    "quality_status": normalized.quality_status,
                    "quality_reason": normalized.quality_reason,
                }
                if effective_status == "accepted" and relative_destination:
                    entry["content"] = normalized.content
                    entry["content_hash"] = hashlib.sha256(normalized.content.encode("utf-8")).hexdigest()
                    record_canonical = _local_record_canonical(resolution.selected.canonical, relative_destination)
                    records.append(
                        SourceRecord(
                            record_canonical,
                            options.version or resolution.selected.version,
                            entry["content_hash"],
                            relative_destination,
                        )
                    )
                else:
                    entry["code"] = normalized.error_code or (
                        "quality_quarantine" if effective_status == "quarantined" else None
                    )
                    entry["reason"] = normalized.error or normalized.quality_reason
                    if normalized.status in {"ocr_required", "dependency_missing", "error"}:
                        errors.append(
                            {
                                "code": normalized.error_code or "normalization_failed",
                                "message": normalized.error or "normalization failed",
                            }
                        )
                entries.append(entry)
        elif resolution.kind == "web":
            web_result = WebAcquirer(policy=FetchPolicy(allow_private=options.allow_private_network)).acquire(
                resolution.selected.url or resolution.selected.canonical,
                options=CrawlOptions(
                    max_pages=options.max_pages,
                    max_depth=options.max_depth,
                    include_patterns=options.include_patterns,
                    exclude_patterns=options.exclude_patterns,
                ),
            )
            entries = web_result.entries
            warnings.extend(web_result.warnings)
            used_destinations: set[str] = set()
            for entry in entries:
                if entry.get("status") == "accepted":
                    destination = _unique_destination(
                        str(entry["destination"]), str(entry["canonical"]), used_destinations
                    )
                    entry["destination"] = destination
                    used_destinations.add(destination)
                    records.append(
                        SourceRecord(
                            str(entry["canonical"]),
                            options.version or resolution.selected.version,
                            str(entry["content_hash"]),
                            destination,
                        )
                    )
                elif entry.get("status") in {"error", "failed"}:
                    errors.append(
                        {
                            "code": str(entry.get("code") or "acquisition_failed"),
                            "message": str(entry.get("reason") or "acquisition failed"),
                        }
                    )
    finally:
        if repo_result is not None:
            repo_result.cleanup()

    if not records:
        errors.append(
            {"code": "no_accepted_documents", "message": "source produced no supported, non-empty documentation"}
        )
    if license_value.casefold() == "unknown":
        warnings.append("source license is unknown; keep redistribution private-only until reviewed")
        if options.redistribution == "public":
            errors.append(
                {"code": "license_required", "message": "public redistribution requires a declared source license"}
            )
    provenance: dict[str, Any] = {
        "license": license_value,
        "license_status": "declared" if license_value.casefold() != "unknown" else "unknown",
        "redistribution": options.redistribution,
        "content_trust": "untrusted",
        "method": "local-normalizer" if local_path else "bounded-web-acquisition",
    }
    if repository_metadata:
        provenance["repository"] = repository_metadata
    provenance["runtime"] = runtime_provenance(_runtime_root(options))
    return _Collection(
        resolution,
        tuple(_freeze(entry) for entry in entries),
        tuple(records),
        tuple(warnings),
        tuple(errors),
        _freeze(provenance),
    )


def _source_files_for_plan(root: Path, output_dir: Path) -> list[Path]:
    output_resolved = output_dir.resolve()
    files: list[Path] = []
    iterator = [root] if root.is_file() else sorted(root.rglob("*"))
    ignored_parts = {
        ".git",
        ".venv",
        ".venv-rag",
        "node_modules",
        "__pycache__",
        "data",
        "models_cache",
        ".docops",
        "artifacts",
        "build",
        "dist",
    }
    for path in iterator:
        if path.is_symlink() or not path.is_file():
            continue
        try:
            path.resolve().relative_to(output_resolved)
        except ValueError:
            pass
        else:
            continue
        relative_parts = path.relative_to(root).parts if root.is_dir() else path.parts
        if any(part.casefold() in ignored_parts for part in relative_parts):
            continue
        files.append(path)
    return files


def _managed_package(root: Path) -> tuple[bool, str | None]:
    if root.is_symlink():
        return False, "destination_symlink"
    if not root.exists():
        return False, None
    if not root.is_dir():
        return False, "destination_not_directory"
    manifest_path = root / "manifest.json"
    metadata_dir = root / ".docops"
    state_path = metadata_dir / "state.json"
    if metadata_dir.is_symlink() or manifest_path.is_symlink() or state_path.is_symlink():
        return False, "destination_incompatible"
    if not manifest_path.is_file() or not state_path.is_file():
        return False, "destination_not_managed"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False, "destination_incompatible"
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        return False, "destination_incompatible"
    if "contract_version" in manifest:
        if not validate_artifact("manifest", manifest).ok:
            return False, "destination_incompatible"
    if not isinstance(state, dict) or state.get("schema_version") != 1 or not isinstance(state.get("records"), list):
        return False, "destination_incompatible"
    return True, None


def _effective_mode(options: PipelineOptions, root: Path, managed: bool) -> str:
    if options.mode == "create":
        return "create"
    if options.mode == "update":
        return "update"
    return "update" if managed else "create"


def _lifecycle_blockers(
    options: PipelineOptions, root: Path, managed: bool, reason: str | None
) -> list[dict[str, str]]:
    exists = root.exists()
    nonempty = exists and root.is_dir() and any(root.iterdir())
    blockers: list[dict[str, str]] = []
    lifecycle_mode = "run" if options.mode == "dry-run" else options.mode
    if reason == "destination_symlink":
        blockers.append({"code": "unsafe_output_path", "message": "output directory must not be a symbolic link"})
        return blockers
    if lifecycle_mode == "create":
        if managed:
            blockers.append(
                {"code": "destination_exists", "message": "create refuses to replace an existing managed package"}
            )
        elif nonempty:
            blockers.append({"code": "destination_not_empty", "message": "create requires a new or empty destination"})
    elif lifecycle_mode == "update":
        if not managed:
            code = "destination_incompatible" if reason == "destination_incompatible" else "destination_not_managed"
            blockers.append({"code": code, "message": "update requires a compatible DOCOPS-managed package"})
    elif lifecycle_mode == "run" and nonempty and not managed:
        code = "destination_incompatible" if reason == "destination_incompatible" else "destination_not_managed"
        blockers.append({"code": code, "message": "run cannot replace an unmanaged non-empty destination"})
    return blockers


def _state_for(root: Path) -> tuple[StateStore | None, list[dict[str, str]]]:
    if not root.is_dir():
        return None, []
    path = root / ".docops" / "state.json"
    try:
        return StateStore(path), []
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        return None, [{"code": "state_invalid", "message": f"could not read managed package state: {exc}"}]


def _plan_payload_without_hash(
    request: OperationRequest,
    resolution: SourceResolution,
    mode: str,
    actions: tuple[PlanAction, ...],
    blockers: tuple[Mapping[str, Any], ...],
    warnings: tuple[str, ...],
    expected_readiness: Mapping[str, str],
    source_fingerprint: str,
    destination_fingerprint: str,
    state_diff: Mapping[str, int],
    request_fingerprint: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "plan_version": PLAN_VERSION,
        "plan_hash": "",
        "mode": request.options.mode,
        "effective_mode": mode,
        "request": request.to_dict(),
        "resolution": redact_metadata(resolution.to_dict()),
        "actions": [action.to_dict() for action in actions],
        "blockers": [redact_metadata(dict(blocker)) for blocker in blockers],
        "warnings": list(warnings),
        "expected_readiness": dict(expected_readiness),
        "source_fingerprint": source_fingerprint,
        "destination_fingerprint": destination_fingerprint,
        "request_fingerprint": request_fingerprint,
        "state_diff": dict(state_diff),
    }


def plan(source: str | Path | OperationRequest, *, options: PipelineOptions | None = None) -> OperationPlan:
    """Resolve and acquire a complete operation plan without mutating its destination."""

    request = (
        source if isinstance(source, OperationRequest) else OperationRequest(str(source), options or _missing_options())
    )
    options = request.options
    root = options.output_dir
    resolver = _resolver(options)
    resolution = _resolution_with_options(
        resolver.resolve(str(request.source), version=options.version, scope=options.scope, language=options.language),
        options,
    )
    managed, reason = _managed_package(root)
    blockers: list[dict[str, Any]] = _lifecycle_blockers(options, root, managed, reason)
    warnings: list[str] = []
    if resolution.error or resolution.requires_decision or not resolution.selected:
        blockers.append(resolution.error or {"code": "source_unresolved", "message": "source could not be resolved"})
    if resolution.selected and resolution.kind == "local":
        local_source = _path_from_file_uri(resolution.selected.canonical)
        if _output_inside_source(local_source, root):
            blockers.append(
                {"code": "output_inside_source", "message": "output directory must be outside the local source"}
            )
    effective = _effective_mode(options, root, managed)
    if managed and effective in {"update", "run"} and "conceptual" in options.layers:
        blockers.extend(check_generated_artifacts(root))
    expected_readiness = {
        "skill": "scaffold-ready",
        "enrichment": "awaiting_enrichment",
        "rag": "indexed" if options.index_rag else "corpus-ready",
        "evaluation": "pending",
        "package": "indexed" if options.index_rag else "corpus-ready",
        "release": "pending",
    }
    entries: tuple[Mapping[str, Any], ...] = ()
    records: tuple[SourceRecord, ...] = ()
    provenance: Mapping[str, Any] = _freeze(
        {
            "license": options.license or "unknown",
            "redistribution": options.redistribution,
            "content_trust": "untrusted",
            "runtime": runtime_provenance(_runtime_root(options)),
        }
    )
    config_content: str | None = None
    state_diff = {"added": 0, "updated": 0, "removed": 0}
    acquisition_blocked = False
    if not blockers and resolution.selected:
        collection = _collect(request.source, resolution, options)
        resolution = collection.resolution
        entries = collection.entries
        records = collection.records
        warnings.extend(collection.warnings)
        blockers.extend(collection.errors)
        acquisition_blocked = bool(collection.errors)
        provenance = collection.provenance
    if root.is_dir() and (root / "config.yaml").is_symlink():
        blockers.append({"code": "unsafe_config_path", "message": "package config.yaml must not be a symbolic link"})
    if root.is_file():
        blockers.append({"code": "destination_not_directory", "message": "output destination must be a directory"})
    state, state_errors = _state_for(root)
    blockers.extend(state_errors)
    desired: dict[str, SourceRecord] = {}
    for record in records:
        try:
            _safe_relpath(record.destination)
        except ValueError:
            blockers.append({"code": "unsafe_state_path", "message": "normalized destination is not safely relative"})
        desired.setdefault(record.logical_key, record)
    if state is not None and not acquisition_blocked:
        diff = state.plan(desired.values())
        state_diff = {"added": len(diff.added), "updated": len(diff.updated), "removed": len(diff.removed)}
    elif desired:
        state_diff = {"added": len(desired), "updated": 0, "removed": 0}
    actions: list[PlanAction] = []
    if not blockers:
        if effective == "create":
            actions.extend(
                PlanAction("add", record.destination, record.identity, record.content_hash, canonical=record.canonical)
                for record in desired.values()
            )
        elif state is not None:
            diff = state.plan(desired.values())
            actions.extend(
                PlanAction("add", record.destination, record.identity, record.content_hash, canonical=record.canonical)
                for record in diff.added
            )
            actions.extend(
                PlanAction(
                    "update",
                    new.destination,
                    new.identity,
                    new.content_hash,
                    previous_hash=old.content_hash,
                    canonical=new.canonical,
                )
                for old, new in diff.updated
            )
            actions.extend(
                PlanAction(
                    "remove", old.destination, old.identity, previous_hash=old.content_hash, canonical=old.canonical
                )
                for old in diff.removed
            )
    actions_tuple = tuple(sorted(actions, key=lambda action: (action.destination, action.kind)))
    source_fp = (
        _source_fingerprint(entries, resolution)
        if entries
        else _hash_payload({"resolution": resolution.to_dict(), "entries": []})
    )
    destination_fp = _destination_fingerprint(root)
    request = OperationRequest(str(request.source), options)
    request_fp = _hash_payload(request.identity())
    payload = _plan_payload_without_hash(
        request,
        resolution,
        effective,
        actions_tuple,
        tuple(_freeze(blocker) for blocker in blockers),
        tuple(warnings),
        expected_readiness,
        source_fp,
        destination_fp,
        state_diff,
        request_fp,
    )
    plan_hash = _hash_payload(payload)
    operation = OperationPlan(
        request,
        resolution,
        effective,
        actions_tuple,
        tuple(_freeze(blocker) for blocker in blockers),
        tuple(warnings),
        MappingProxyType(dict(expected_readiness)),
        source_fp,
        destination_fp,
        request_fp,
        tuple(entries),
        tuple(desired.values()),
        provenance,
        MappingProxyType(dict(state_diff)),
        config_content,
        plan_hash,
    )
    contract = validate_artifact("plan", operation.to_dict())
    if not contract.ok:
        raise RuntimeError(
            "internal plan contract is invalid: " + "; ".join(error["message"] for error in contract.errors)
        )
    return operation


def preview(operation: OperationPlan) -> PipelineResult:
    """Adapt a public plan to a terminal result without mutating its destination."""

    options = operation.request.options
    if operation.blockers:
        first = operation.blockers[0]
        outcome = {
            "status": "blocked",
            "code": str(first.get("code", "plan_blocked")),
            "phase": "plan",
            "message": "operation plan contains blockers",
            "exit_code": 2,
        }
        errors = [
            {
                "code": str(blocker.get("code", "plan_blocked")),
                "message": str(blocker.get("message", "operation plan contains blockers")),
            }
            for blocker in operation.blockers
        ]
        manifest = build_manifest(
            operation.resolution,
            entries=[],
            provenance={"license": options.license or "unknown", "redistribution": options.redistribution},
            artifacts=_ARTIFACTS,
            errors=errors,
            outcome=outcome,
            readiness=dict(operation.expected_readiness),
        )
        return PipelineResult(
            False,
            options.output_dir,
            manifest,
            state_diff=dict(operation.state_diff),
            errors=errors,
            warnings=list(operation.warnings),
            outcome=outcome,
            exit_code=2,
        )

    outcome = _outcome("succeeded", "planned", "plan", "plan created without mutating the destination", exit_code=0)
    warnings = [*operation.warnings, "dry-run is an alias for plan; no artifacts were written"]
    manifest = build_manifest(
        operation.resolution,
        entries=[],
        provenance={"license": options.license or "unknown", "redistribution": options.redistribution},
        artifacts=_ARTIFACTS,
        warnings=warnings,
        metrics={"plan": redact_report(operation.to_dict()), "state_diff": dict(operation.state_diff)},
        outcome=outcome,
        readiness=dict(operation.expected_readiness),
    )
    return PipelineResult(
        True,
        options.output_dir,
        manifest,
        state_diff=dict(operation.state_diff),
        warnings=warnings,
        outcome=outcome,
        exit_code=0,
    )


def _missing_options() -> PipelineOptions:
    raise TypeError("plan requires PipelineOptions when source is not an OperationRequest")


def _attempt_root(output: Path) -> Path:
    return output.parent / f".{output.name}.docops-attempts"


def _record_attempt(
    output: Path,
    plan_value: OperationPlan,
    outcome: Mapping[str, Any],
    *,
    phase: str,
    errors: Iterable[Mapping[str, Any]] = (),
    staging: Path | None = None,
) -> None:
    try:
        attempt_dir = _attempt_root(output)
        if attempt_dir.is_symlink():
            return
        attempt_dir.mkdir(parents=True, exist_ok=True)
        attempt_id = f"attempt-{uuid.uuid4().hex}"
        payload = {
            "schema_version": 1,
            "attempt_id": attempt_id,
            "plan_hash": plan_value.plan_hash,
            "phase": phase,
            "outcome": redact_metadata({**dict(outcome), "message": redact_text(outcome.get("message", ""))}),
            "errors": redact_metadata(
                [{**dict(error), "message": redact_text(error.get("message", ""))} for error in errors]
            ),
            "staging": {"present": bool(staging and staging.exists())},
            "recorded_at": utc_now(),
        }
        write_json_atomic(attempt_dir / f"{attempt_id}.json", payload)
    except (OSError, TypeError, UnicodeError, ValueError):
        # Failure reporting must never mask the primary operation result.
        return


def _resume_stage(output: Path, plan_value: OperationPlan) -> Path | None:
    if not output.parent.is_dir():
        return None
    prefix = f".{output.name}.staging-"
    for candidate in sorted(output.parent.iterdir()):
        if not candidate.name.startswith(prefix) or candidate.is_symlink() or not candidate.is_dir():
            continue
        if _contains_symlink(candidate):
            continue
        plan_path = candidate / ".docops" / "plan.json"
        try:
            saved = json.loads(plan_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if isinstance(saved, dict) and saved.get("plan_hash") == plan_value.plan_hash:
            return candidate
    return None


def _contains_symlink(root: Path) -> bool:
    """Detect links in a resumable tree before any generated write occurs."""

    if root.is_symlink():
        return True
    try:
        return any(path.is_symlink() for path in root.rglob("*"))
    except OSError:
        return True


def _reject_stage_symlinks(stage: Path) -> None:
    if _contains_symlink(stage):
        raise OperationFailure(
            "unsafe_staging_path",
            "staging generation contains a symbolic link and cannot be resumed",
            phase="prepare",
        )


def _paths_digest(root: Path, paths: Iterable[str]) -> str:
    selected = sorted(set(paths))
    if "*" in selected:
        return _hash_payload(_tree_snapshot(root))
    return _hash_payload({path: _file_digest(root / path) for path in selected})


def _receipt_valid(
    checkpoint: CheckpointStore, phase: str, plan_hash: str, input_hash: str, stage: Path, paths: Iterable[str]
) -> bool:
    receipt = checkpoint.load(phase)
    receipt_paths = receipt.get("paths") if isinstance(receipt, dict) else None
    if not isinstance(receipt_paths, list) or not all(isinstance(path, str) for path in receipt_paths):
        receipt_paths = list(paths)
    return bool(
        receipt
        and receipt.get("status") == "completed"
        and receipt.get("schema_version") == 1
        and receipt.get("phase") == phase
        and receipt.get("plan_version") == PLAN_VERSION
        and receipt.get("plan_hash") == plan_hash
        and receipt.get("input_hash") == input_hash
        and receipt.get("output_hash") == _paths_digest(stage, receipt_paths)
    )


def _phase_duration_ms(started: float) -> float:
    """Return a positive serialized duration even on coarse monotonic clocks."""

    return max(round((time.monotonic() - started) * 1000, 3), 0.001)


def _run_phase(
    checkpoint: CheckpointStore,
    phase: str,
    plan_value: OperationPlan,
    stage: Path,
    paths: tuple[str, ...],
    callback: Any,
) -> bool:
    input_hash = _hash_payload({"plan_hash": plan_value.plan_hash, "phase": phase})
    if _receipt_valid(checkpoint, phase, plan_value.plan_hash, input_hash, stage, paths):
        return True
    started = time.monotonic()
    callback_result = callback()
    effective_paths = tuple(callback_result) if isinstance(callback_result, (list, tuple, set)) else paths
    checkpoint.save(
        phase,
        {
            "schema_version": 1,
            "phase": phase,
            "plan_version": PLAN_VERSION,
            "status": "completed",
            "plan_hash": plan_value.plan_hash,
            "input_hash": input_hash,
            "output_hash": _paths_digest(stage, effective_paths),
            "paths": list(effective_paths),
            "duration_ms": _phase_duration_ms(started),
            "completed_at": utc_now(),
        },
    )
    return False


def _copy_preserved_user_files(source: Path, stage: Path) -> list[str]:
    copied: list[str] = ["config.yaml"]
    if not source.is_dir():
        return copied
    for child in source.iterdir():
        if child.name in _GENERATED_ROOTS:
            continue
        destination = stage / child.name
        if child.is_symlink():
            raise OperationFailure(
                "unsafe_user_artifact",
                "unmanaged symbolic links cannot be copied into a generated package",
                phase="prepare",
            )
        if child.is_dir():
            if any(path.is_symlink() for path in child.rglob("*")):
                raise OperationFailure(
                    "unsafe_user_artifact",
                    "unmanaged symbolic links cannot be copied into a generated package",
                    phase="prepare",
                )
            shutil.copytree(child, destination, dirs_exist_ok=True)
            copied.extend(path.relative_to(stage).as_posix() for path in destination.rglob("*") if path.is_file())
        elif child.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(child, destination)
            copied.append(destination.relative_to(stage).as_posix())
    return sorted(set(copied))


def _copy_preserved_conceptual_layer(source: Path, stage: Path) -> list[str]:
    """Copy conceptual artifacts byte-for-byte for an explicit factual update."""

    required = ("skill", "router")
    copied: list[str] = []
    for relative_name in (*required, *_PRESERVED_CONCEPTUAL_METADATA):
        origin = source / relative_name
        if not (origin.exists() or origin.is_symlink()):
            if relative_name in required:
                raise OperationFailure(
                    "conceptual_layer_unavailable",
                    "factual update requires an existing skill and router to preserve",
                    phase="artifacts",
                )
            continue
        if origin.is_symlink():
            raise OperationFailure(
                "unsafe_user_artifact",
                "conceptual artifacts must not be symbolic links",
                phase="artifacts",
            )
        destination = stage / relative_name
        if origin.is_dir():
            if any(path.is_symlink() for path in origin.rglob("*")):
                raise OperationFailure(
                    "unsafe_user_artifact",
                    "conceptual artifacts must not contain symbolic links",
                    phase="artifacts",
                )
            shutil.copytree(origin, destination, dirs_exist_ok=True)
            copied.extend(path.relative_to(stage).as_posix() for path in destination.rglob("*") if path.is_file())
        elif origin.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origin, destination)
            copied.append(relative_name)
        else:
            raise OperationFailure(
                "conceptual_layer_unavailable",
                "conceptual artifact path is not a regular file or directory",
                phase="artifacts",
            )
    return sorted(set(copied))


def _write_acquisition(stage: Path, plan_value: OperationPlan) -> None:
    documents = stage / "rag" / "documents"
    if documents.is_symlink():
        raise OperationFailure(
            "unsafe_staging_path",
            "staging RAG documents path must not be a symbolic link",
            phase="acquisition",
        )
    if documents.exists() and not documents.is_dir():
        raise OperationFailure(
            "unsafe_staging_path",
            "staging RAG documents path must be a directory",
            phase="acquisition",
        )
    if documents.exists():
        shutil.rmtree(documents)
    documents.mkdir(parents=True, exist_ok=True)
    entries = [_thaw(entry) for entry in plan_value.entries]
    by_destination = {
        str(entry["destination"]): entry
        for entry in entries
        if entry.get("status") == "accepted" and entry.get("destination")
    }
    for record in plan_value.records:
        entry = by_destination.get(record.destination)
        if not entry:
            continue
        destination = documents / _safe_relpath(record.destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        _write_if_changed(destination, str(entry.get("content", "")) + "\n")
    source_entries = []
    for entry in entries:
        if entry.get("status") != "accepted":
            continue
        payload = {key: value for key, value in entry.items() if key != "content"}
        payload["version"] = plan_value.resolution.selected.version if plan_value.resolution.selected else None
        source_entries.append(redact_entry(payload))
    for learning_document in admitted_learning_documents(plan_value.request.options.output_dir):
        destination = documents / _safe_relpath(str(learning_document["destination"]))
        destination.parent.mkdir(parents=True, exist_ok=True)
        _write_if_changed(destination, str(learning_document["content"]))
        source_entries.append(redact_entry(dict(learning_document["source"])))
    write_json_atomic(stage / "rag" / "sources.json", {"schema_version": 1, "sources": source_entries})


def _write_artifacts(stage: Path, plan_value: OperationPlan) -> None:
    options = plan_value.request.options
    existing_managed, _reason = _managed_package(options.output_dir)
    preserve_conceptual = "conceptual" not in options.layers and existing_managed
    if preserve_conceptual:
        _copy_preserved_conceptual_layer(options.output_dir, stage)
    else:
        selected = plan_value.resolution.selected
        source = selected.to_dict() if selected else {}
        source["input"] = plan_value.request.source
        source["license"] = plan_value.provenance.get("license", "unknown")
        accepted = [
            entry for entry in (_thaw(item) for item in plan_value.entries) if entry.get("status") == "accepted"
        ]
        write_skill(stage, selected.slug if selected else "documentation", accepted, source)
        write_router(stage, selected.slug if selected else "documentation")
    harness_text = json.dumps(build_harness_manifest(stage), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    _write_if_changed(stage / "harness.json", harness_text)
    if not preserve_conceptual:
        write_generated_artifact_inventory(stage)


def _write_index(stage: Path, plan_value: OperationPlan) -> dict[str, Any]:
    document_paths = [
        path for path in (stage / "rag" / "documents").rglob("*") if path.is_file() and not path.is_symlink()
    ]
    corpus_documents = len(document_paths)
    operator_chunks = sum(
        max(1, (len(str(entry.get("content", ""))) + 949) // 950)
        for entry in (_thaw(item) for item in plan_value.entries)
        if entry.get("status") == "accepted" and entry.get("content")
    )
    operator_chunks += sum(
        max(1, (len(path.read_text(encoding="utf-8")) + 949) // 950)
        for path in document_paths
        if path.relative_to(stage / "rag" / "documents").parts[:1] == ("learning",)
    )
    rag_sync_result = None
    if plan_value.request.options.index_rag:
        full_rebuild = False
        active_index = plan_value.request.options.output_dir / "rag" / "index.json"
        if active_index.is_file() and not active_index.is_symlink():
            try:
                previous_index = json.loads(active_index.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                previous_index = {}
            if previous_index.get("mode") == "indexed":
                previous_configuration = previous_index.get("configuration")
                previous_fingerprint = (
                    previous_configuration.get("embedding_fingerprint")
                    if isinstance(previous_configuration, Mapping)
                    else None
                )
                current_configuration = embedding_configuration(stage)
                full_rebuild = not isinstance(previous_fingerprint, str) or (
                    previous_fingerprint != current_configuration.get("embedding_fingerprint")
                )
        rag_sync_result = RagSynchronizer(runtime_root=_runtime_root(plan_value.request.options)).sync(
            stage,
            full_rebuild=full_rebuild,
        )
        if not rag_sync_result.ok:
            raise OperationFailure(
                (rag_sync_result.error or {}).get("code", "rag_integration_failed"),
                (rag_sync_result.error or {}).get("message", "knowledge-rag indexing failed"),
                phase="index",
            )
    backend_stats = rag_sync_result.stats if rag_sync_result is not None else {}
    backend_total_chunks = (
        backend_stats.get("total_chunks") if isinstance(backend_stats.get("total_chunks"), int) else None
    )
    backend_total_documents = (
        backend_stats.get("total_documents") if isinstance(backend_stats.get("total_documents"), int) else None
    )
    index_payload: dict[str, Any] = {
        "schema_version": 1,
        "status": "ready" if plan_value.records else "empty",
        "backend": "knowledge-rag",
        "mode": "indexed" if rag_sync_result is not None and rag_sync_result.ok else "corpus-ready",
        "profile": "compact",
        "corpus_documents": corpus_documents,
        "operator_chunks": operator_chunks,
        "backend_total_documents": backend_total_documents,
        "backend_total_chunks": backend_total_chunks,
        "metrics": {
            "corpus_documents": corpus_documents,
            "operator_chunks": operator_chunks,
            "backend_total_documents": backend_total_documents,
            "backend_total_chunks": backend_total_chunks,
        },
        "source_version": plan_value.resolution.selected.version if plan_value.resolution.selected else None,
        "language": plan_value.resolution.selected.language if plan_value.resolution.selected else None,
        "source_state": ".docops/state.json",
    }
    if rag_sync_result is not None:
        safe_sync = rag_sync_result.to_dict()
        index_payload["server_stats"] = safe_sync["stats"]
        index_payload["reindex"] = safe_sync["reindex"]
        index_payload["smoke"] = safe_sync["smoke"]
        index_payload["configuration"] = safe_sync["configuration"]
        index_payload["profile"] = safe_sync["configuration"].get("profile", "unknown")
        index_payload["provenance"] = safe_sync["provenance"]
        index_payload["diagnostics"] = safe_sync["diagnostics"]
    else:
        index_payload["smoke"] = {"status": "not-run", "hint": "run with --index-rag or scripts/mcp_smoke.py"}
    write_json_atomic(stage / "rag" / "index.json", index_payload)
    return index_payload


def _write_state(stage: Path, plan_value: OperationPlan) -> None:
    state = StateStore(stage / ".docops" / "state.json")
    state.commit(plan_value.records)


def _outcome(status: str, code: str, phase: str, message: str, *, exit_code: int) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": status,
        "code": code,
        "phase": phase,
        "message": message,
        "exit_code": exit_code,
    }


def _timed_outcome(outcome: Mapping[str, Any], started: float) -> dict[str, Any]:
    value = dict(outcome)
    value["duration_ms"] = round((time.monotonic() - started) * 1000, 3)
    return value


def _failure_result(
    plan_value: OperationPlan,
    outcome: Mapping[str, Any],
    errors: list[dict[str, str]],
    *,
    validation: ValidationResult | None = None,
    warnings: Iterable[str] = (),
) -> PipelineResult:
    safe_errors = [{**error, "message": redact_text(error.get("message", ""))} for error in errors]
    safe_warnings = [redact_text(warning) for warning in [*plan_value.warnings, *warnings]]
    safe_outcome = {**dict(outcome), "message": redact_text(outcome.get("message", ""))}
    manifest = build_manifest(
        plan_value.resolution,
        entries=[
            {key: value for key, value in _thaw(entry).items() if key != "content"} for entry in plan_value.entries
        ],
        provenance=_thaw(plan_value.provenance),
        artifacts=_ARTIFACTS,
        checkpoints={},
        warnings=safe_warnings,
        errors=safe_errors,
        metrics={"state_diff": dict(plan_value.state_diff), "readiness": dict(plan_value.expected_readiness)},
        outcome=safe_outcome,
        readiness=dict(plan_value.expected_readiness),
    )
    manifest["outcome"] = safe_outcome
    if validation is not None:
        manifest["validation"] = validation.to_dict()
    return PipelineResult(
        False,
        plan_value.request.options.output_dir,
        manifest,
        validation,
        dict(plan_value.state_diff),
        0,
        safe_errors,
        safe_warnings,
        safe_outcome,
        int(safe_outcome.get("exit_code", 1)),
    )


def _no_op_result(plan_value: OperationPlan, validation: ValidationResult) -> PipelineResult:
    try:
        manifest = read_manifest(plan_value.request.options.output_dir / "manifest.json")
    except (OSError, ValueError, json.JSONDecodeError):
        outcome = _outcome(
            "failed", "active_manifest_unreadable", "inspect", "active manifest could not be read", exit_code=1
        )
        return _failure_result(
            plan_value, outcome, [{"code": outcome["code"], "message": outcome["message"]}], validation=validation
        )
    outcome = (
        manifest.get("outcome")
        if isinstance(manifest.get("outcome"), dict)
        else _outcome("succeeded", "noop", "inspect", "package is already current", exit_code=0)
    )
    if outcome.get("status") != "succeeded" or not validation.ok:
        failure = _outcome(
            "failed",
            "active_package_invalid",
            "validate",
            "active package does not satisfy its terminal contract",
            exit_code=1,
        )
        return _failure_result(
            plan_value, failure, [{"code": failure["code"], "message": failure["message"]}], validation=validation
        )
    return PipelineResult(
        True,
        plan_value.request.options.output_dir,
        manifest,
        validation,
        dict(plan_value.state_diff),
        0,
        [],
        list(plan_value.warnings),
        dict(outcome),
        0,
    )


def _build_stage(plan_value: OperationPlan, stage: Path) -> tuple[dict[str, Any], ValidationResult]:
    if stage.is_symlink() or (stage.exists() and not stage.is_dir()):
        raise OperationFailure(
            "unsafe_staging_path",
            "staging generation must be a regular directory",
            phase="prepare",
        )
    stage.mkdir(parents=True, exist_ok=True)
    _reject_stage_symlinks(stage)
    metadata = stage / ".docops"
    if metadata.is_symlink() or (metadata.exists() and not metadata.is_dir()):
        raise OperationFailure(
            "unsafe_staging_path",
            "staging metadata path must be a regular directory",
            phase="prepare",
        )
    metadata.mkdir(parents=True, exist_ok=True)
    write_json_atomic(metadata / "plan.json", plan_value.to_dict())
    checkpoint = CheckpointStore(metadata / "checkpoints.json")
    existing_output = plan_value.request.options.output_dir
    if (
        (stage / "config.yaml").is_symlink()
        or (stage / "config.yaml").exists()
        and not (stage / "config.yaml").is_file()
    ):
        raise OperationFailure(
            "unsafe_staging_path",
            "staging config path must be a regular file",
            phase="prepare",
        )
    if not (stage / "config.yaml").exists():
        if (
            existing_output.is_dir()
            and (existing_output / "config.yaml").is_file()
            and not (existing_output / "config.yaml").is_symlink()
        ):
            write_text_atomic(stage / "config.yaml", (existing_output / "config.yaml").read_text(encoding="utf-8"))
        else:
            write_text_atomic(stage / "config.yaml", package_rag_config_text())

    def preserve_user_state() -> list[str]:
        copied = _copy_preserved_user_files(existing_output, stage)
        if existing_output.is_dir():
            copy_learning_state(existing_output, stage)
        return copied

    _run_phase(
        checkpoint,
        "prepare",
        plan_value,
        stage,
        ("config.yaml",),
        preserve_user_state,
    )
    rag_dir = stage / "rag"
    if rag_dir.is_symlink() or (rag_dir.exists() and not rag_dir.is_dir()):
        raise OperationFailure(
            "unsafe_staging_path",
            "staging RAG path must be a regular directory",
            phase="prepare",
        )
    rag_dir.mkdir(parents=True, exist_ok=True)
    documents_dir = rag_dir / "documents"
    if documents_dir.is_symlink() or (documents_dir.exists() and not documents_dir.is_dir()):
        raise OperationFailure(
            "unsafe_staging_path",
            "staging RAG documents path must be a regular directory",
            phase="prepare",
        )
    documents_dir.mkdir(parents=True, exist_ok=True)
    _run_phase(
        checkpoint,
        "acquisition",
        plan_value,
        stage,
        ("rag/documents", "rag/sources.json"),
        lambda: _write_acquisition(stage, plan_value),
    )
    _run_phase(
        checkpoint,
        "artifacts",
        plan_value,
        stage,
        ("skill", "router", "harness.json", ".docops/generated-artifacts.json"),
        lambda: _write_artifacts(stage, plan_value),
    )
    index_payload: dict[str, Any] = {}

    def index_callback() -> None:
        nonlocal index_payload
        index_payload = _write_index(stage, plan_value)

    index_done = _run_phase(checkpoint, "index", plan_value, stage, ("rag/index.json", "rag/data"), index_callback)
    if index_done:
        try:
            index_payload = json.loads((stage / "rag" / "index.json").read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise OperationFailure("invalid_rag_index", str(exc), phase="index") from exc
    _run_phase(checkpoint, "state", plan_value, stage, (".docops/state.json",), lambda: _write_state(stage, plan_value))
    readiness = assess_readiness(stage)
    layers = {
        "updated": list(plan_value.request.options.layers),
        "conceptual": "updated" if "conceptual" in plan_value.request.options.layers else "preserved",
        "factual": "updated" if "factual" in plan_value.request.options.layers else "preserved",
    }
    conceptual_lag = (
        {
            "status": "pending_review",
            "coverage": "unknown",
            "reason": "factual_update_preserved_conceptual_layer",
        }
        if "conceptual" not in plan_value.request.options.layers
        else {
            "status": "none",
            "coverage": "generated",
            "reason": "conceptual_layer_updated",
        }
    )
    metrics = {
        "rag": index_payload,
        "state_diff": dict(plan_value.state_diff),
        "readiness": readiness,
        "layers": layers,
        "conceptual_lag": conceptual_lag,
    }

    def validate_callback() -> None:
        selected = plan_value.resolution.selected
        source = selected.to_dict() if selected else {}
        source["input"] = plan_value.request.source
        source["license"] = plan_value.provenance.get("license", "unknown")
        manifest_entries = [
            {key: value for key, value in _thaw(entry).items() if key != "content"} for entry in plan_value.entries
        ]
        for learning_document in admitted_learning_documents(stage):
            source_metadata = dict(learning_document["source"])
            manifest_entries.append(
                {
                    "status": "accepted",
                    "canonical": source_metadata["source_id"],
                    "version": "admitted",
                    "title": source_metadata["title"],
                    "format": source_metadata["format"],
                    "privacy": source_metadata["privacy"],
                    "destination": f"rag/documents/{source_metadata['destination']}",
                    "source_id": source_metadata["source_id"],
                }
            )
        manifest = build_manifest(
            plan_value.resolution,
            entries=manifest_entries,
            provenance=_thaw(plan_value.provenance),
            artifacts=_ARTIFACTS,
            checkpoints=checkpoint.all(),
            warnings=plan_value.warnings,
            errors=(),
            metrics=metrics,
            outcome=_outcome("succeeded", "completed", "validate", "operation completed", exit_code=0),
            readiness=readiness,
        )
        manifest["layers"] = layers
        manifest["conceptual_lag"] = conceptual_lag
        manifest["revisions"] = package_revisions(stage)
        write_manifest(stage / "manifest.json", manifest)

    validate_done = _run_phase(checkpoint, "validate", plan_value, stage, ("manifest.json",), validate_callback)
    try:
        validation = validate_package(stage)
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise OperationFailure("validation_failed", str(exc), phase="validate") from exc
    if not validation.ok:
        raise OperationFailure(
            "validation_failed",
            "staged package failed validation",
            phase="validate",
            details={"errors": validation.errors},
        )
    if not validate_done:
        manifest = read_manifest(stage / "manifest.json")
        manifest["validation"] = validation.to_dict()
        manifest["outcome"] = _outcome("succeeded", "completed", "validate", "operation completed", exit_code=0)
        manifest["warnings"] = [
            *dict.fromkeys([*plan_value.warnings, *(warning["message"] for warning in validation.warnings)])
        ]
        write_manifest(stage / "manifest.json", manifest)
        # The validation receipt intentionally covers the final manifest, not
        # the pre-validation draft. Preserve the measured phase timing while
        # refreshing only the output hash after this final manifest write.
        previous_receipt = checkpoint.load("validate") or {}
        duration_ms = previous_receipt.get("duration_ms", 0.0)
        if not isinstance(duration_ms, (int, float)) or isinstance(duration_ms, bool) or duration_ms < 0:
            duration_ms = 0.0
        checkpoint.save(
            "validate",
            {
                "schema_version": 1,
                "phase": "validate",
                "plan_version": PLAN_VERSION,
                "status": "completed",
                "plan_hash": plan_value.plan_hash,
                "input_hash": _hash_payload({"plan_hash": plan_value.plan_hash, "phase": "validate"}),
                "output_hash": _paths_digest(stage, ("manifest.json",)),
                "paths": ["manifest.json"],
                "duration_ms": duration_ms,
                "completed_at": previous_receipt.get("completed_at") or utc_now(),
            },
        )
    else:
        manifest = read_manifest(stage / "manifest.json")
        if manifest.get("validation", {}).get("ok") is not True:
            manifest["validation"] = validation.to_dict()
            write_manifest(stage / "manifest.json", manifest)
    return index_payload, validation


_PROMOTION_RETRY_ATTEMPTS = 80
_PROMOTION_JOURNAL_VERSION = 1
_PROMOTION_FAILPOINT_EXIT_CODE = 86
_CANDIDATE_FAILPOINT_EXIT_CODE = 87


def _replace_with_retry(source: Path, destination: Path) -> None:
    """Retry Windows directory replacement while a public reader closes files."""

    for attempt in range(_PROMOTION_RETRY_ATTEMPTS):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if attempt + 1 == _PROMOTION_RETRY_ATTEMPTS:
                raise
            time.sleep(0.025)


def _promotion_journal_path(output: Path) -> Path:
    return output.parent / f".{output.name}.docops.promotion.json"


def _clear_promotion_journal(output: Path) -> None:
    journal = _promotion_journal_path(output)
    if journal.is_symlink():
        raise OperationFailure(
            "unsafe_promotion_journal",
            "promotion journal must not be a symbolic link",
            phase="promote",
        )
    if journal.exists():
        journal.unlink()


def _write_promotion_journal(
    output: Path,
    *,
    stage: Path,
    backup: Path | None,
    plan_hash: str,
    phase: str,
    had_active: bool,
    active_generation_valid: bool,
    stage_generation_valid: bool,
) -> None:
    journal = _promotion_journal_path(output)
    if journal.is_symlink() or (journal.exists() and not journal.is_file()):
        raise OperationFailure(
            "unsafe_promotion_journal",
            "promotion journal must be a regular file",
            phase="promote",
        )
    write_json_atomic(
        journal,
        {
            "schema_version": _PROMOTION_JOURNAL_VERSION,
            "output_name": output.name,
            "stage_name": stage.name,
            "backup_name": backup.name if backup is not None else None,
            "plan_hash": plan_hash,
            "phase": phase,
            "had_active": had_active,
            "active_generation_valid": active_generation_valid,
            "stage_generation_valid": stage_generation_valid,
            "updated_at": utc_now(),
        },
    )


def _promotion_failpoint(name: str) -> None:
    """Exit only at an explicit test seam used to reproduce crash windows."""

    if os.environ.get("DOCOPS_TEST_PROMOTION_FAILPOINT") == name:
        os._exit(_PROMOTION_FAILPOINT_EXIT_CODE)


def _candidate_failpoint(name: str) -> None:
    """Exit only at an explicit test seam used to reproduce candidate crashes."""

    if os.environ.get("DOCOPS_TEST_CANDIDATE_FAILPOINT") == name:
        os._exit(_CANDIDATE_FAILPOINT_EXIT_CODE)


def _opaque_residue_id(path: Path) -> str:
    """Return a stable public identifier without exposing a private basename."""

    digest = hashlib.sha256(path.name.encode("utf-8", errors="replace")).hexdigest()
    return f"residue-{digest[:12]}"


def _public_recovery_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Remove filesystem member names needed only by internal recovery."""

    return {key: value for key, value in snapshot.items() if key not in {"stage_name", "backup_name"}}


def _read_promotion_journal(output: Path) -> dict[str, Any] | None:
    journal = _promotion_journal_path(output)
    if not journal.exists() and not journal.is_symlink():
        return None
    if journal.is_symlink() or not journal.is_file():
        return {"_invalid": "promotion journal is not a regular file"}
    try:
        value = json.loads(journal.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {"_invalid": f"promotion journal could not be read: {exc}"}
    if not isinstance(value, dict):
        return {"_invalid": "promotion journal must contain an object"}
    return value


def _promotion_member(output: Path, name: Any, prefix: str) -> Path | None:
    if not isinstance(name, str) or not name or Path(name).name != name or not name.startswith(prefix):
        return None
    return output.parent / name


def _valid_generation(root: Path | None) -> bool:
    if root is None or root.is_symlink() or not root.is_dir():
        return False
    try:
        return validate_package(root).ok
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError):
        return False


def _promotion_recovery_snapshot(root: Path, *, now: float | None = None) -> dict[str, Any]:
    """Describe a journaled or legacy promotion without mutating the tree."""

    timestamp = now if now is not None else time.time()
    journal = _read_promotion_journal(root)
    if journal is not None and "_invalid" in journal:
        return {"status": "incomplete", "phase": None, "error": redact_text(journal["_invalid"])}
    if journal is not None:
        phase = journal.get("phase")
        stage = _promotion_member(root, journal.get("stage_name"), f".{root.name}.staging-")
        backup_name = journal.get("backup_name")
        backup = _promotion_member(root, backup_name, f".{root.name}.backup-") if backup_name else None
        if (
            journal.get("schema_version") != _PROMOTION_JOURNAL_VERSION
            or journal.get("output_name") != root.name
            or not isinstance(journal.get("plan_hash"), str)
            or not journal.get("plan_hash")
            or phase not in {"prepared", "active-moved", "active-installed"}
            or stage is None
            or (backup_name is not None and backup is None)
        ):
            return {"status": "incomplete", "phase": phase, "error": "promotion journal fields are invalid"}
        stage_exists = bool(stage and stage.is_dir() and not stage.is_symlink())
        backup_exists = bool(backup and backup.is_dir() and not backup.is_symlink())
        if phase in {"prepared", "active-moved"} and journal.get("stage_generation_valid") is True:
            # The writer validated the staged generation before recording this
            # journal.  Avoid reopening it on every reader inspection while
            # the next rename is waiting; Windows may deny a directory move
            # while another process has a file open inside that tree.
            stage_valid = stage_exists
        else:
            stage_valid = _valid_generation(stage)
        if phase == "active-moved" and journal.get("active_generation_valid") is True:
            # The backup is the exact directory that was validated before the
            # first rename.  Its validity is a journaled fact for this phase;
            # recovery still revalidates it before restoring it.
            backup_valid = backup_exists
        else:
            backup_valid = _valid_generation(backup)
        active_valid = _valid_generation(root)
        if active_valid and phase == "active-installed":
            status = "recoverable"
        elif stage_valid or backup_valid or active_valid:
            status = "recoverable"
        else:
            status = "incomplete"
        return {
            "status": status,
            "phase": phase,
            "plan_hash": journal["plan_hash"],
            "had_active": bool(journal.get("had_active")),
            "stage_name": stage.name,
            "backup_name": backup.name if backup is not None else None,
            "stage": {
                "present": bool(stage and (stage.exists() or stage.is_symlink())),
                "valid": stage_valid,
                "age_seconds": _residue_age(stage, timestamp) if stage is not None else None,
            },
            "backup": {
                "present": bool(backup and (backup.exists() or backup.is_symlink())),
                "valid": backup_valid,
                "age_seconds": _residue_age(backup, timestamp) if backup is not None else None,
            },
            "active_valid": active_valid,
        }

    # Versions before the journal fix could leave a valid backup with no
    # active directory.  Recognise only generated-name backups and valid
    # packages, keeping arbitrary user directories out of recovery.
    if not root.exists() and root.parent.is_dir():
        prefix = f".{root.name}.backup-"
        candidates = [
            path
            for path in root.parent.iterdir()
            if path.name.startswith(prefix) and not path.is_symlink() and _valid_generation(path)
        ]
        if candidates:
            candidate = max(candidates, key=lambda path: path.stat().st_mtime)
            return {
                "status": "recoverable",
                "phase": "legacy-backup",
                "backup": {
                    "present": True,
                    "valid": True,
                    "age_seconds": _residue_age(candidate, timestamp),
                },
                "backup_name": candidate.name,
                "active_valid": False,
            }
    return {"status": "stable" if _valid_generation(root) else "none", "phase": None}


def _recover_interrupted_promotion(output: Path) -> dict[str, Any]:
    """Restore a valid generation and leave a valid staged generation resumable."""

    snapshot = _promotion_recovery_snapshot(output)
    if snapshot.get("status") != "recoverable":
        return {"ok": snapshot.get("status") != "incomplete", "recovered": False, **snapshot}

    journal = _read_promotion_journal(output)
    stage: Path | None = None
    backup: Path | None = None
    if journal is not None and "_invalid" not in journal:
        stage = _promotion_member(output, journal.get("stage_name"), f".{output.name}.staging-")
        backup_name = journal.get("backup_name")
        backup = _promotion_member(output, backup_name, f".{output.name}.backup-") if backup_name else None
    elif snapshot.get("backup_name"):
        backup = output.parent / str(snapshot["backup_name"])

    try:
        if _valid_generation(output):
            if backup is not None and backup.exists() and not backup.is_symlink():
                _remove_generated_path(backup)
            _clear_promotion_journal(output)
            return {"ok": True, "recovered": True, "action": "active-preserved", **snapshot}
        if _valid_generation(backup):
            if output.exists() or output.is_symlink():
                _remove_generated_path(output)
            _replace_with_retry(backup, output)
            if not _valid_generation(output):
                raise OperationFailure(
                    "promotion_recovery_validation_failed",
                    "restored generation failed validation",
                    phase="promote",
                )
            _clear_promotion_journal(output)
            return {"ok": True, "recovered": True, "action": "previous-generation-restored", **snapshot}
        if _valid_generation(stage):
            if output.exists() or output.is_symlink():
                _remove_generated_path(output)
            _replace_with_retry(stage, output)
            if not _valid_generation(output):
                raise OperationFailure(
                    "promotion_recovery_validation_failed",
                    "staged generation failed validation",
                    phase="promote",
                )
            _clear_promotion_journal(output)
            return {"ok": True, "recovered": True, "action": "staged-generation-installed", **snapshot}
    except (OSError, OperationFailure) as exc:
        return {
            "ok": False,
            "recovered": False,
            "code": getattr(exc, "code", "promotion_recovery_failed"),
            "error": redact_text(str(exc)),
            **snapshot,
        }
    return {
        "ok": False,
        "recovered": False,
        "code": "promotion_recovery_incomplete",
        "error": "no valid generation was available for promotion recovery",
        **snapshot,
    }


def _promote(stage: Path, output: Path, backup_name: str, *, plan_hash: str) -> Path | None:
    if output.is_symlink():
        raise OperationFailure("unsafe_output_path", "output directory must not be a symbolic link", phase="promote")
    backup: Path | None = None
    had_active = output.exists()
    active_generation_valid = _valid_generation(output) if had_active else False
    stage_generation_valid = _valid_generation(stage)
    if had_active:
        backup = output.parent / backup_name
        if backup.exists():
            _remove_generated_path(backup)
    _write_promotion_journal(
        output,
        stage=stage,
        backup=backup,
        plan_hash=plan_hash,
        phase="prepared",
        had_active=had_active,
        active_generation_valid=active_generation_valid,
        stage_generation_valid=stage_generation_valid,
    )
    _promotion_failpoint("before-active-to-backup")
    if had_active:
        _replace_with_retry(output, backup)
        _promotion_failpoint("after-active-to-backup-before-journal")
        _write_promotion_journal(
            output,
            stage=stage,
            backup=backup,
            plan_hash=plan_hash,
            phase="active-moved",
            had_active=had_active,
            active_generation_valid=active_generation_valid,
            stage_generation_valid=stage_generation_valid,
        )
        _promotion_failpoint("after-active-to-backup")
    try:
        _replace_with_retry(stage, output)
        _promotion_failpoint("after-stage-to-active-before-journal")
        _write_promotion_journal(
            output,
            stage=stage,
            backup=backup,
            plan_hash=plan_hash,
            phase="active-installed",
            had_active=had_active,
            active_generation_valid=active_generation_valid,
            stage_generation_valid=stage_generation_valid,
        )
        _promotion_failpoint("after-stage-to-active")
    except Exception:
        try:
            if backup is not None and backup.exists() and not output.exists():
                _replace_with_retry(backup, output)
        except OSError:
            # Keep the journal when rollback itself cannot complete.  The
            # next public operation can still diagnose or recover it.
            pass
        try:
            _clear_promotion_journal(output)
        except (OSError, OperationFailure):
            pass
        raise
    return backup


def _remove_generated_path(path: Path) -> None:
    """Remove only a known generated path after a failed promotion."""

    if path.is_symlink():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _restore_after_failed_promotion(output: Path, backup: Path | None, *, promoted: bool) -> None:
    if not promoted:
        return
    try:
        if backup is not None and backup.exists():
            if output.exists() or output.is_symlink():
                _remove_generated_path(output)
            os.replace(backup, output)
        elif output.exists() or output.is_symlink():
            _remove_generated_path(output)
    except OSError:
        # Do not mask the original apply failure.  The journal remains as a
        # recovery receipt and the next public operation can retry safely.
        return
    try:
        _clear_promotion_journal(output)
    except (OSError, OperationFailure):
        # A leftover journal is safer than claiming that rollback completed.
        return


_CANDIDATE_REVISION_KEYS = (
    "corpus_revision",
    "index_revision",
    "skill_revision",
    "router_revision",
    "policy_revision",
    "golden_revision",
    "composition_hash",
    "release_id",
)
_APPROVAL_ROLES = {"human_approver", "delegated_policy"}
_APPROVAL_KINDS = {"conceptual_manual", "delegated_factual"}


def _read_candidate_json(path: Path, label: str, *, code: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise CandidatePublicationError(code, f"{label} must be a regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CandidatePublicationError(code, f"{label} is unreadable") from exc
    if not isinstance(value, dict):
        raise CandidatePublicationError(code, f"{label} must contain a JSON object")
    return value


def _candidate_contract_or_raise(artifact: str, payload: Mapping[str, Any], *, code: str) -> None:
    contract = validate_artifact(artifact, payload)
    if contract.ok:
        return
    raise CandidatePublicationError(code, f"{artifact} receipt violates its contract")


def _read_optional_revocation_file(path: Path) -> dict[str, Any] | None:
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        raise CandidatePublicationError("revocation_state_invalid", "revocation state must be a regular file")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CandidatePublicationError("revocation_state_invalid", "revocation state is unreadable") from exc
    if not isinstance(payload, dict):
        raise CandidatePublicationError("revocation_state_invalid", "revocation state must be a JSON object")
    return payload


def _candidate_dependency_keys(manifest: Mapping[str, Any]) -> tuple[set[str], set[str]]:
    source_keys: set[str] = set()
    destinations: set[str] = set()
    source = manifest.get("source")
    if isinstance(source, Mapping):
        for key in ("source_id", "canonical", "input"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                source_keys.add(value.strip())
    entries = manifest.get("entries")
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            for key in ("source_id", "canonical", "source"):
                value = entry.get(key)
                if isinstance(value, str) and value.strip():
                    source_keys.add(value.strip())
            destination = entry.get("destination")
            if isinstance(destination, str) and destination.strip():
                normalized = destination.strip().replace("\\", "/").lstrip("/")
                destinations.add(normalized)
                if normalized.startswith("rag/documents/"):
                    destinations.add(normalized.removeprefix("rag/documents/"))
                else:
                    destinations.add(f"rag/documents/{normalized}")
    return source_keys, destinations


def _revocation_matches(record: Mapping[str, Any], *, source_keys: set[str], destinations: set[str]) -> bool:
    record_keys = {
        str(record.get(key)).strip()
        for key in ("source_id", "canonical", "source")
        if isinstance(record.get(key), str) and str(record.get(key)).strip()
    }
    if record_keys & source_keys:
        return True
    record_destinations: set[str] = set()
    raw_destinations = record.get("destinations")
    if isinstance(raw_destinations, str):
        raw_destinations = [raw_destinations]
    if isinstance(raw_destinations, list):
        for value in raw_destinations:
            if not isinstance(value, str) or not value.strip():
                continue
            normalized = value.strip().replace("\\", "/").lstrip("/")
            record_destinations.add(normalized)
            if normalized.startswith("rag/documents/"):
                record_destinations.add(normalized.removeprefix("rag/documents/"))
            else:
                record_destinations.add(f"rag/documents/{normalized}")
    return bool(record_destinations & destinations)


def _candidate_revocation_conflict(
    package_root: Path, manifest: Mapping[str, Any], candidate_root: Path | None = None
) -> dict[str, Any] | None:
    """Fail closed when a candidate depends on withdrawn or revoked source data."""

    source_keys, destinations = _candidate_dependency_keys(manifest)
    roots = [package_root]
    if candidate_root is not None and candidate_root != package_root:
        roots.append(candidate_root)
    for root in roots:
        registry = _read_optional_revocation_file(root / ".docops" / "source-registry.json")
        if registry is not None:
            registrations = registry.get("registrations")
            if not isinstance(registrations, list):
                raise CandidatePublicationError("revocation_state_invalid", "source registry registrations are invalid")
            for registration in registrations:
                if not isinstance(registration, Mapping):
                    raise CandidatePublicationError("revocation_state_invalid", "source registry entry is invalid")
                if registration.get("status") in {"withdrawn", "revoked"} and _revocation_matches(
                    registration,
                    source_keys=source_keys,
                    destinations=destinations,
                ):
                    return {
                        "source_id": registration.get("source_id"),
                        "canonical": registration.get("canonical"),
                        "status": registration.get("status"),
                    }
        revocations = _read_optional_revocation_file(root / ".docops" / "revocations.json")
        if revocations is not None:
            records = revocations.get("sources")
            if not isinstance(records, list):
                raise CandidatePublicationError("revocation_state_invalid", "revocation sources are invalid")
            for record in records:
                if not isinstance(record, Mapping):
                    raise CandidatePublicationError("revocation_state_invalid", "revocation entry is invalid")
                if record.get("revoked", True) is not False and _revocation_matches(
                    record,
                    source_keys=source_keys,
                    destinations=destinations,
                ):
                    return {
                        "source_id": record.get("source_id"),
                        "canonical": record.get("canonical"),
                        "status": "revoked",
                    }
        rag_sources = _read_optional_revocation_file(root / "rag" / "sources.json")
        if rag_sources is not None:
            records = rag_sources.get("sources")
            if not isinstance(records, list):
                raise CandidatePublicationError("revocation_state_invalid", "RAG source entries are invalid")
            for record in records:
                if (
                    isinstance(record, Mapping)
                    and record.get("revoked") is True
                    and _revocation_matches(
                        record,
                        source_keys=source_keys,
                        destinations=destinations,
                    )
                ):
                    return {
                        "source_id": record.get("source_id"),
                        "canonical": record.get("canonical"),
                        "status": "revoked",
                    }
        learning_tombstones = _read_optional_revocation_file(root / ".docops" / "learning" / "tombstones.json")
        if learning_tombstones is not None:
            records = learning_tombstones.get("tombstones")
            if not isinstance(records, list):
                raise CandidatePublicationError(
                    "revocation_state_invalid",
                    "learning tombstones are invalid",
                )
            for tombstone in records:
                if not isinstance(tombstone, Mapping):
                    raise CandidatePublicationError(
                        "revocation_state_invalid",
                        "learning tombstone entry is invalid",
                    )
                raw_path = tombstone.get("path")
                if not isinstance(raw_path, str) or not raw_path.strip():
                    raise CandidatePublicationError(
                        "revocation_state_invalid",
                        "learning tombstone path is required",
                    )
                normalized = raw_path.strip().replace("\\", "/").lstrip("/")
                if not normalized or ".." in normalized.split("/"):
                    raise CandidatePublicationError(
                        "revocation_state_invalid",
                        "learning tombstone path is unsafe",
                    )
                tombstone_destinations = {normalized}
                if normalized.startswith("rag/documents/"):
                    tombstone_destinations.add(normalized.removeprefix("rag/documents/"))
                else:
                    tombstone_destinations.add(f"rag/documents/{normalized}")
                if tombstone_destinations & destinations:
                    return {
                        "proposal_id": tombstone.get("proposal_id"),
                        "path": normalized,
                        "status": "revoked_learning_derivative",
                    }
    return None


def _approval_authority(actor: str, role: str, authority: Mapping[str, Any] | None) -> dict[str, Any]:
    """Normalize an authenticated adapter attestation without storing proof."""

    if authority is None:
        # The compatibility CLI has always received the actor at a process
        # boundary.  Preserve that interface while making the boundary
        # explicit in the receipt; real harnesses should pass their own
        # attestation through --authority-json.
        proof = f"local-process-adapter:{actor}:{role}"
        return {
            "authenticated": True,
            "source": "local-process-adapter",
            "subject": actor,
            "role": role,
            "proof_hash": hashlib.sha256(proof.encode("utf-8")).hexdigest(),
        }
    if not isinstance(authority, Mapping) or authority.get("authenticated") is not True:
        raise CandidatePublicationError(
            "approval_authority_invalid",
            "approval requires an authenticated authority attestation",
        )
    source = authority.get("source")
    subject = authority.get("subject")
    if not isinstance(source, str) or not source.strip():
        raise CandidatePublicationError("approval_authority_invalid", "authority source is required")
    if not isinstance(subject, str) or subject.strip() != actor:
        raise CandidatePublicationError("approval_authority_invalid", "authority subject does not match the actor")
    roles = authority.get("roles")
    if isinstance(roles, str):
        roles = [roles]
    if not isinstance(roles, list) or role not in roles:
        raise CandidatePublicationError("approval_authority_invalid", "authority does not grant the approval role")
    proof = authority.get("proof") or authority.get("signature")
    if not isinstance(proof, str) or not proof.strip():
        raise CandidatePublicationError("approval_authority_invalid", "authority proof is required")
    return {
        "authenticated": True,
        "source": redact_text(source.strip()),
        "subject": redact_text(subject.strip()),
        "role": role,
        "proof_hash": hashlib.sha256(proof.encode("utf-8")).hexdigest(),
    }


def _candidate_scope_kind(manifest: Mapping[str, Any]) -> tuple[str, str]:
    layers = manifest.get("layers")
    if not isinstance(layers, Mapping):
        raise CandidatePublicationError(
            "approval_scope_unknown",
            "candidate manifest does not declare its update scope",
        )
    updated = layers.get("updated")
    if not isinstance(updated, list) or not all(isinstance(item, str) for item in updated):
        raise CandidatePublicationError(
            "approval_scope_unknown",
            "candidate manifest has no valid updated layer list",
        )
    normalized = set(updated)
    if normalized == {"factual"} and layers.get("conceptual") == "preserved":
        return "delegated_factual", "delegated_policy"
    if "conceptual" in normalized:
        return "conceptual_manual", "human_approver"
    raise CandidatePublicationError(
        "approval_scope_unknown",
        "candidate update scope is neither conceptual nor factual-only",
    )


def _candidate_context(package_root: Path | str, candidate_id: str) -> dict[str, Any]:
    output = Path(os.path.abspath(os.fspath(Path(package_root).expanduser())))
    if output.is_symlink():
        raise CandidatePublicationError(
            "unsafe_output_path",
            "output directory must not be a symbolic link",
        )
    try:
        candidate = candidate_path(output, candidate_id)
    except CandidateError as exc:
        raise CandidatePublicationError("candidate_not_found", str(exc)) from exc
    if candidate.is_symlink() or not candidate.is_dir():
        raise CandidatePublicationError("candidate_not_found", "candidate is missing or unsafe")
    if _contains_symlink(candidate):
        raise CandidatePublicationError("unsafe_candidate_path", "candidate contains a symbolic link")

    candidate_receipt = _read_candidate_json(
        candidate / ".docops" / "candidate.json",
        "candidate receipt",
        code="candidate_receipt_invalid",
    )
    if candidate_receipt.get("candidate_id") != candidate_id:
        raise CandidatePublicationError(
            "candidate_receipt_invalid",
            "candidate receipt does not identify the requested candidate",
        )

    active_manifest_path = output / "manifest.json"
    if output.is_symlink() or not output.is_dir() or not active_manifest_path.is_file():
        raise CandidatePublicationError(
            "active_generation_missing",
            "candidate publication requires an existing active generation",
        )
    try:
        active_manifest = read_manifest(active_manifest_path)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise CandidatePublicationError(
            "active_generation_invalid",
            "active generation manifest is invalid",
        ) from exc
    active_validation = validate_package(output)
    if not active_validation.ok:
        raise CandidatePublicationError(
            "active_generation_invalid",
            "active generation must validate before candidate publication",
        )

    try:
        candidate_manifest = read_manifest(candidate / "manifest.json")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise CandidatePublicationError(
            "candidate_validation_failed",
            "candidate manifest is invalid",
        ) from exc
    candidate_validation = validate_package(candidate)
    if not candidate_validation.ok:
        raise CandidatePublicationError(
            "candidate_validation_failed",
            "candidate package failed validation",
            details={"errors": candidate_validation.errors},
        )
    revocation = _candidate_revocation_conflict(output, candidate_manifest, candidate)
    if revocation is not None:
        raise CandidatePublicationError(
            "source_revoked",
            "candidate depends on withdrawn or revoked source content",
            details=revocation,
        )

    active_revisions = active_manifest.get("revisions")
    candidate_revisions = candidate_manifest.get("revisions")
    if not isinstance(active_revisions, Mapping) or any(
        not isinstance(active_revisions.get(key), str) or not active_revisions.get(key)
        for key in _CANDIDATE_REVISION_KEYS
    ):
        raise CandidatePublicationError(
            "active_revision_evidence_missing",
            "active generation has incomplete revision evidence",
        )
    if not isinstance(candidate_revisions, Mapping) or any(
        not isinstance(candidate_revisions.get(key), str) or not candidate_revisions.get(key)
        for key in _CANDIDATE_REVISION_KEYS
    ):
        raise CandidatePublicationError(
            "candidate_revision_evidence_missing",
            "candidate has incomplete revision evidence",
        )

    base_release_id = candidate_receipt.get("base_release_id")
    base_composition_hash = candidate_receipt.get("base_composition_hash")
    if not isinstance(base_release_id, str) or not isinstance(base_composition_hash, str):
        raise CandidatePublicationError(
            "stale_base",
            "candidate has no complete active-base evidence",
        )
    if (
        active_revisions.get("release_id") != base_release_id
        or active_revisions.get("composition_hash") != base_composition_hash
    ):
        raise CandidatePublicationError(
            "stale_base",
            "active generation advanced after candidate preparation",
        )

    evaluation_path = candidate / ".docops" / "evaluation.json"
    evaluation = _read_candidate_json(
        evaluation_path,
        "candidate evaluation",
        code="evaluation_missing",
    )
    if (
        evaluation.get("schema_version") != 1
        or evaluation.get("ok") is not True
        or not isinstance(evaluation.get("revisions"), Mapping)
        or not isinstance(evaluation.get("metrics"), Mapping)
    ):
        raise CandidatePublicationError(
            "evaluation_invalidated",
            "candidate evaluation did not pass",
        )
    matches, reason = evidence_matches_package(candidate, evaluation)
    if not matches:
        raise CandidatePublicationError(
            "evaluation_invalidated",
            f"candidate evaluation evidence is {reason}",
        )
    evaluated_revisions = evaluation.get("revisions")
    if not isinstance(evaluated_revisions, Mapping) or any(
        evaluated_revisions.get(key) != candidate_revisions.get(key) for key in _CANDIDATE_REVISION_KEYS
    ):
        raise CandidatePublicationError(
            "evaluation_invalidated",
            "candidate evaluation does not match current candidate revisions",
        )

    approval_kind, expected_role = _candidate_scope_kind(candidate_manifest)
    return {
        "output": output,
        "candidate": candidate,
        "candidate_receipt": candidate_receipt,
        "candidate_manifest": candidate_manifest,
        "active_manifest": active_manifest,
        "active_revisions": dict(active_revisions),
        "candidate_revisions": dict(candidate_revisions),
        "evaluation": evaluation,
        "evaluation_hash": file_hash(evaluation_path),
        "approval_kind": approval_kind,
        "expected_role": expected_role,
    }


def _candidate_lease(package_root: Path | str) -> tuple[Path, PackageLease]:
    output = Path(os.path.abspath(os.fspath(Path(package_root).expanduser())))
    lease = PackageLease(output, policy="fail", wait_seconds=0.0, stale_after_seconds=300.0)
    try:
        lease.acquire()
    except LeaseBusyError as exc:
        raise CandidatePublicationError("writer_busy", redact_text(str(exc)), phase="lease") from exc
    except OSError as exc:
        raise CandidatePublicationError(
            "lease_unavailable",
            "could not acquire the package writer lease",
            phase="lease",
        ) from exc
    return output, lease


def _recover_candidate_promotion(output: Path) -> dict[str, Any]:
    """Make candidate publish/rollback retryable after a journaled crash."""

    recovery = _recover_interrupted_promotion(output)
    if recovery.get("ok") is not True:
        raise CandidatePublicationError(
            str(recovery.get("code", "promotion_recovery_failed")),
            str(recovery.get("error", "interrupted promotion could not be recovered")),
            phase="recover",
            details={key: value for key, value in recovery.items() if key not in {"error", "code"}},
        )
    if recovery.get("status") == "stable" and _valid_generation(output):
        # A crash can happen after the active rename but before the journal is
        # written.  In that window the active directory is valid and the
        # generated backup is no longer needed; only remove names reserved
        # for this promotion protocol and only when they are valid packages.
        prefix = f".{output.name}.backup-"
        for residue in output.parent.glob(f"{prefix}*"):
            if not residue.is_symlink() and _valid_generation(residue):
                _remove_generated_path(residue)
    return recovery


def _recovered_candidate_publication(output: Path, candidate_id: str) -> dict[str, Any] | None:
    """Return an idempotent result when a crash already installed a candidate."""

    manifest_path = output / "manifest.json"
    publication_path = output / ".docops" / "publication.json"
    if output.is_symlink() or not output.is_dir() or not manifest_path.is_file():
        return None
    publication = (
        _read_candidate_json(
            publication_path,
            "recovered publication",
            code="publication_recovery_invalid",
        )
        if publication_path.exists() or publication_path.is_symlink()
        else None
    )
    if not isinstance(publication, dict) or publication.get("candidate_id") != candidate_id:
        return None
    _candidate_contract_or_raise("publication", publication, code="publication_recovery_invalid")
    validation = validate_package(output)
    if not validation.ok:
        raise CandidatePublicationError(
            "publication_recovery_invalid",
            "recovered candidate does not validate",
            phase="recover",
            details={"errors": validation.errors},
        )
    manifest = read_manifest(manifest_path)
    if manifest.get("publication") != publication:
        manifest["publication"] = dict(publication)
        manifest["outcome"] = _outcome(
            "succeeded",
            "candidate_published",
            "promote",
            "candidate publication recovered after a crash",
            exit_code=0,
        )
        manifest["validation"] = validation.to_dict()
        write_manifest(manifest_path, manifest)
    candidate = candidate_path(output, candidate_id)
    if candidate.is_dir() and not candidate.is_symlink():
        candidate_metadata = candidate / ".docops"
        candidate_metadata.mkdir(parents=True, exist_ok=True)
        write_json_atomic(candidate_metadata / "publication.json", publication)
        receipt_path = candidate_metadata / "candidate.json"
        if receipt_path.is_file() and not receipt_path.is_symlink():
            receipt = _read_candidate_json(receipt_path, "candidate receipt", code="candidate_receipt_invalid")
            receipt.update(
                {
                    "status": "published",
                    "publication": ".docops/publication.json",
                    "published_release_id": publication.get("release_id"),
                }
            )
            write_json_atomic(receipt_path, receipt)
    return {
        "schema_version": 1,
        "ok": True,
        "status": "published",
        "code": "candidate_already_published",
        "candidate_id": candidate_id,
        "approval_id": publication.get("approval_id"),
        "release_id": publication.get("release_id"),
        "parent_release_id": publication.get("parent_release_id"),
        "candidate_locator": candidate_locator(output, candidate_id),
        "publication": ".docops/publication.json",
        "published": True,
        "recovered": True,
    }


def _history_root(output: Path) -> Path:
    """Return the editorial history directory kept beside the active package."""

    return output.parent / f".{output.name}.history"


def _safe_history_release_id(release_id: Any) -> str:
    if not isinstance(release_id, str) or not release_id:
        raise CandidatePublicationError(
            "history_release_invalid",
            "history release id must be a non-empty string",
            phase="history",
        )
    if Path(release_id).name != release_id or any(
        character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for character in release_id
    ):
        raise CandidatePublicationError(
            "history_release_invalid",
            "history release id contains unsafe path characters",
            phase="history",
        )
    return release_id


def _history_entry_path(output: Path, release_id: Any) -> Path:
    root = _history_root(output)
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise CandidatePublicationError(
            "history_unavailable",
            "editorial history root is not a regular directory",
            phase="history",
        )
    return root / _safe_history_release_id(release_id)


def _history_tree_size(root: Path) -> int:
    total = 0
    if not root.exists() or root.is_symlink():
        return total
    for path in root.rglob("*"):
        if path.is_symlink():
            raise CandidatePublicationError(
                "history_symlink",
                "editorial history cannot contain symbolic links",
                phase="history",
            )
        if path.is_file():
            total += path.stat().st_size
    return total


def _history_quota_bytes() -> int | None:
    for name in ("DOCOPS_HISTORY_QUOTA_BYTES", "DOCOPS_TEST_HISTORY_QUOTA_BYTES"):
        raw = os.environ.get(name)
        if raw is None:
            continue
        try:
            value = int(raw)
        except ValueError as exc:
            raise CandidatePublicationError(
                "history_quota_invalid",
                "history quota must be an integer number of bytes",
                phase="history",
            ) from exc
        if value < 0:
            raise CandidatePublicationError(
                "history_quota_invalid",
                "history quota cannot be negative",
                phase="history",
            )
        return value
    return None


def _history_quota_check(root: Path, staged: Path) -> None:
    quota = _history_quota_bytes()
    if quota is None:
        return
    required = _history_tree_size(root) + _history_tree_size(staged)
    if required > quota:
        raise CandidatePublicationError(
            "history_quota_exceeded",
            "editorial history quota would discard required prior generation",
            phase="history",
            details={"quota_bytes": quota, "required_bytes": required},
        )


def _history_receipt(entry: Path) -> dict[str, Any]:
    receipt_path = entry / ".docops" / "history.json"
    receipt = _read_candidate_json(receipt_path, "history receipt", code="history_invalidated")
    _candidate_contract_or_raise("history", receipt, code="history_invalidated")
    return receipt


def _prepare_history_snapshot(
    output: Path,
    *,
    active_manifest: Mapping[str, Any],
    active_revisions: Mapping[str, Any],
) -> tuple[Path | None, Path, dict[str, Any]]:
    release_id = _safe_history_release_id(active_revisions.get("release_id"))
    target = _history_entry_path(output, release_id)
    if target.is_symlink() or (target.exists() and not target.is_dir()):
        raise CandidatePublicationError(
            "history_conflict",
            "retained release path is not a regular directory",
            phase="history",
        )
    if target.is_dir():
        existing = _history_receipt(target)
        if existing.get("release_id") == release_id and existing.get("composition_hash") == active_revisions.get(
            "composition_hash"
        ):
            return None, target, existing
        raise CandidatePublicationError(
            "history_conflict",
            "retained release id already identifies different content",
            phase="history",
        )
    if _contains_symlink(output):
        raise CandidatePublicationError(
            "history_capture_failed",
            "active generation contains a symbolic link",
            phase="history",
        )
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.history-", dir=output.parent))
    try:
        shutil.copytree(output, stage, dirs_exist_ok=True, symlinks=False)
        publication = active_manifest.get("publication")
        source_candidate_id = publication.get("candidate_id") if isinstance(publication, Mapping) else None
        parent_release_id = publication.get("parent_release_id") if isinstance(publication, Mapping) else None
        receipt = {
            "schema_version": 1,
            "history_id": f"history-{uuid.uuid4().hex}",
            "release_id": release_id,
            "composition_hash": str(active_revisions["composition_hash"]),
            "index_revision": str(active_revisions["index_revision"]),
            "retained_at": utc_now(),
            "revoked": False,
            "index_compatible": True,
            "parent_release_id": parent_release_id if isinstance(parent_release_id, str) else None,
            "source_candidate_id": source_candidate_id if isinstance(source_candidate_id, str) else None,
        }
        _candidate_contract_or_raise("history", receipt, code="history_contract_invalid")
        write_json_atomic(stage / ".docops" / "history.json", receipt)
        validation = validate_package(stage)
        if not validation.ok:
            raise CandidatePublicationError(
                "history_capture_failed",
                "active generation could not be retained as a valid package",
                phase="history",
                details={"errors": validation.errors},
            )
        return stage, target, receipt
    except CandidatePublicationError:
        _remove_generated_path(stage)
        raise
    except (OSError, TypeError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        _remove_generated_path(stage)
        raise CandidatePublicationError(
            "history_capture_failed",
            "active generation could not be retained",
            phase="history",
        ) from exc


def _commit_history_snapshot(stage: Path | None, target: Path) -> None:
    if stage is None:
        return
    root = target.parent
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise CandidatePublicationError(
            "history_unavailable",
            "editorial history root is not a regular directory",
            phase="history",
        )
    root.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        raise CandidatePublicationError(
            "history_conflict",
            "retained release path appeared during publication",
            phase="history",
        )
    try:
        os.replace(stage, target)
    except OSError as exc:
        raise CandidatePublicationError(
            "history_retention_failed",
            "retained generation could not be committed",
            phase="history",
        ) from exc


def _inspect_history(root: Path) -> list[dict[str, Any]]:
    history = _history_root(root)
    if not history.exists() or history.is_symlink() or not history.is_dir():
        return []
    entries: list[dict[str, Any]] = []
    for entry in sorted(history.iterdir()):
        if entry.is_symlink() or not entry.is_dir():
            continue
        try:
            receipt = _history_receipt(entry)
            validation = validate_package(entry).to_dict()
        except (CandidatePublicationError, OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            entries.append(
                {
                    "status": "invalid",
                    "release_id": entry.name,
                    "error": redact_text(str(exc)),
                }
            )
            continue
        entries.append(
            {
                "status": "revoked" if receipt.get("revoked") is True else "retained",
                "release_id": receipt["release_id"],
                "composition_hash": receipt["composition_hash"],
                "index_revision": receipt["index_revision"],
                "retained_at": receipt["retained_at"],
                "revoked": receipt["revoked"],
                "index_compatible": receipt["index_compatible"],
                "validation": validation,
            }
        )
    return entries


def approve_candidate(
    package_root: Path | str,
    candidate_id: str,
    *,
    actor: str,
    role: str,
    authority: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Record explicit authority for one candidate without publishing it."""

    if not isinstance(actor, str) or not actor.strip():
        raise CandidatePublicationError("approval_actor_missing", "approval actor is required")
    if role not in _APPROVAL_ROLES:
        raise CandidatePublicationError("approval_role_invalid", "approval role is not supported")
    output, lease = _candidate_lease(package_root)
    try:
        context = _candidate_context(output, candidate_id)
        if context["candidate_receipt"].get("status") == "published":
            raise CandidatePublicationError("candidate_already_published", "candidate is already published")
        if role != context["expected_role"]:
            raise CandidatePublicationError(
                "approval_role_mismatch",
                "approval role does not match the candidate update scope",
            )
        authority_record = _approval_authority(actor.strip(), role, authority)
        approval_id = f"approval-{uuid.uuid4().hex}"
        approval = {
            "schema_version": 1,
            "approval_id": approval_id,
            "candidate_id": candidate_id,
            "status": "approved",
            "approval_kind": context["approval_kind"],
            "actor": {"id": redact_text(actor.strip()), "role": role},
            "base_release_id": context["active_revisions"]["release_id"],
            "base_composition_hash": context["active_revisions"]["composition_hash"],
            "candidate_revisions": dict(context["candidate_revisions"]),
            "evaluation_hash": context["evaluation_hash"],
            "policy_revision": context["candidate_revisions"]["policy_revision"],
            "approved_at": utc_now(),
            "authority": authority_record,
        }
        _candidate_contract_or_raise("approval", approval, code="approval_contract_invalid")
        write_json_atomic(context["candidate"] / ".docops" / "approval.json", approval)
        receipt = dict(context["candidate_receipt"])
        receipt.update(
            {
                "status": "approved",
                "approval_id": approval_id,
                "approval": ".docops/approval.json",
                "approval_kind": context["approval_kind"],
                "revisions": dict(context["candidate_revisions"]),
            }
        )
        write_json_atomic(context["candidate"] / ".docops" / "candidate.json", receipt)
        return {
            "schema_version": 1,
            "ok": True,
            "status": "approved",
            "code": "candidate_approved",
            "candidate_id": candidate_id,
            "approval_id": approval_id,
            "approval_kind": context["approval_kind"],
            "candidate_locator": candidate_locator(output, candidate_id),
            "published": False,
            "revisions": dict(context["candidate_revisions"]),
        }
    finally:
        lease.release()


def publish_candidate(package_root: Path | str, candidate_id: str) -> dict[str, Any]:
    """Promote an approved candidate after revalidating every bound receipt."""

    output, lease = _candidate_lease(package_root)
    stage: Path | None = None
    history_stage: Path | None = None
    history_target: Path | None = None
    backup: Path | None = None
    promoted = False
    try:
        _recover_candidate_promotion(output)
        recovered = _recovered_candidate_publication(output, candidate_id)
        if recovered is not None:
            return recovered
        try:
            early_candidate = candidate_path(output, candidate_id)
        except CandidateError as exc:
            raise CandidatePublicationError("candidate_not_found", str(exc)) from exc
        early_receipt = _read_candidate_json(
            early_candidate / ".docops" / "candidate.json",
            "candidate receipt",
            code="candidate_receipt_invalid",
        )
        if early_receipt.get("status") != "approved":
            raise CandidatePublicationError(
                "approval_missing",
                "candidate requires an explicit approval receipt",
            )
        early_approval_path = early_candidate / ".docops" / "approval.json"
        if early_approval_path.is_symlink() or not early_approval_path.is_file():
            raise CandidatePublicationError(
                "approval_missing",
                "candidate requires an explicit approval receipt",
            )
        context = _candidate_context(output, candidate_id)
        candidate_receipt = context["candidate_receipt"]
        approval_path = context["candidate"] / ".docops" / "approval.json"
        approval = _read_candidate_json(
            approval_path,
            "candidate approval",
            code="approval_missing",
        )
        _candidate_contract_or_raise("approval", approval, code="approval_invalidated")
        if (
            approval.get("candidate_id") != candidate_id
            or approval.get("status") != "approved"
            or approval.get("approval_id") != candidate_receipt.get("approval_id")
            or approval.get("approval_kind") != context["approval_kind"]
            or approval.get("actor", {}).get("role") != context["expected_role"]
        ):
            raise CandidatePublicationError(
                "approval_invalidated",
                "approval receipt does not match the candidate scope",
            )
        if (
            approval.get("base_release_id") != context["active_revisions"]["release_id"]
            or approval.get("base_composition_hash") != context["active_revisions"]["composition_hash"]
        ):
            raise CandidatePublicationError(
                "stale_base",
                "approval targets an active generation that is no longer current",
            )
        if (
            approval.get("candidate_revisions") != context["candidate_revisions"]
            or approval.get("evaluation_hash") != context["evaluation_hash"]
            or approval.get("policy_revision") != context["candidate_revisions"]["policy_revision"]
        ):
            raise CandidatePublicationError(
                "approval_invalidated",
                "approval evidence no longer matches the candidate",
            )

        publication = {
            "schema_version": 1,
            "release_id": context["candidate_revisions"]["release_id"],
            "candidate_id": candidate_id,
            "approval_id": approval["approval_id"],
            "composition_hash": context["candidate_revisions"]["composition_hash"],
            "parent_release_id": context["active_revisions"]["release_id"],
            "published_at": utc_now(),
        }
        _candidate_contract_or_raise("publication", publication, code="publication_contract_invalid")

        if _contains_symlink(context["candidate"]):
            raise CandidatePublicationError("unsafe_candidate_path", "candidate contains a symbolic link")
        stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent))
        shutil.copytree(context["candidate"], stage, dirs_exist_ok=True, symlinks=False)
        write_json_atomic(stage / ".docops" / "publication.json", publication)
        staged_receipt = _read_candidate_json(
            stage / ".docops" / "candidate.json",
            "staged candidate receipt",
            code="candidate_receipt_invalid",
        )
        staged_receipt.update(
            {
                "status": "published",
                "publication": ".docops/publication.json",
                "published_release_id": publication["release_id"],
            }
        )
        write_json_atomic(stage / ".docops" / "candidate.json", staged_receipt)
        staged_validation = validate_package(stage)
        if not staged_validation.ok:
            raise CandidatePublicationError(
                "candidate_validation_failed",
                "publication staging failed validation",
                phase="prepare",
                details={"errors": staged_validation.errors},
            )

        history_stage, history_target, _history = _prepare_history_snapshot(
            output,
            active_manifest=context["active_manifest"],
            active_revisions=context["active_revisions"],
        )
        if history_stage is not None:
            _history_quota_check(_history_root(output), history_stage)

        backup = _promote(
            stage,
            output,
            f".{output.name}.backup-publish-{uuid.uuid4().hex}",
            plan_hash=str(approval["approval_id"]),
        )
        promoted = True
        post_validation = validate_package(output)
        if not post_validation.ok:
            raise CandidatePublicationError(
                "promotion_validation_failed",
                "published package failed post-promotion validation",
                phase="promote",
                details={"errors": post_validation.errors},
            )
        manifest = read_manifest(output / "manifest.json")
        manifest["publication"] = dict(publication)
        manifest["outcome"] = _outcome(
            "succeeded",
            "candidate_published",
            "promote",
            "candidate published",
            exit_code=0,
        )
        manifest["validation"] = post_validation.to_dict()
        write_manifest(output / "manifest.json", manifest)
        final_validation = validate_package(output)
        if not final_validation.ok:
            raise CandidatePublicationError(
                "promotion_validation_failed",
                "published manifest failed final validation",
                phase="promote",
                details={"errors": final_validation.errors},
            )
        if history_target is not None:
            _commit_history_snapshot(history_stage, history_target)
            history_stage = None
        _clear_promotion_journal(output)
        if backup is not None and backup.exists():
            _remove_generated_path(backup)
            backup = None

        write_json_atomic(context["candidate"] / ".docops" / "publication.json", publication)
        candidate_receipt.update(
            {
                "status": "published",
                "publication": ".docops/publication.json",
                "published_release_id": publication["release_id"],
            }
        )
        write_json_atomic(context["candidate"] / ".docops" / "candidate.json", candidate_receipt)
        return {
            "schema_version": 1,
            "ok": True,
            "status": "published",
            "code": "candidate_published",
            "candidate_id": candidate_id,
            "approval_id": approval["approval_id"],
            "release_id": publication["release_id"],
            "parent_release_id": publication["parent_release_id"],
            "candidate_locator": candidate_locator(output, candidate_id),
            "publication": ".docops/publication.json",
            "history_release_id": context["active_revisions"]["release_id"],
            "history_locator": (
                f".{output.name}.history/{context['active_revisions']['release_id']}"
                if history_target is not None
                else None
            ),
            "published": True,
            "revisions": dict(context["candidate_revisions"]),
        }
    except CandidatePublicationError:
        _restore_after_failed_promotion(output, backup, promoted=promoted)
        raise
    except OperationFailure as exc:
        _restore_after_failed_promotion(output, backup, promoted=promoted)
        raise CandidatePublicationError(exc.code, str(exc), phase=exc.phase, details=exc.details) from exc
    except (OSError, TypeError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        _restore_after_failed_promotion(output, backup, promoted=promoted)
        raise CandidatePublicationError(
            "publication_failed",
            "candidate publication failed safely",
            phase="promote" if promoted else "prepare",
        ) from exc
    finally:
        if stage is not None and stage.exists() and not _promotion_journal_path(output).exists():
            try:
                _remove_generated_path(stage)
            except OSError:
                pass
        if history_stage is not None and history_stage.exists():
            try:
                _remove_generated_path(history_stage)
            except OSError:
                pass
        lease.release()


def rollback_candidate(package_root: Path | str, release_id: str) -> dict[str, Any]:
    """Restore one retained generation using the same recoverable promotion seam."""

    output, lease = _candidate_lease(package_root)
    stage: Path | None = None
    backup: Path | None = None
    promoted = False
    try:
        _recover_candidate_promotion(output)
        entry = _history_entry_path(output, release_id)
        if entry.is_symlink() or not entry.is_dir():
            raise CandidatePublicationError(
                "history_not_found",
                "requested release is not retained in editorial history",
                phase="rollback",
            )
        receipt = _history_receipt(entry)
        if receipt.get("revoked") is True:
            raise CandidatePublicationError(
                "source_revoked",
                "revoked source or derived generation cannot be restored",
                phase="rollback",
            )
        learning_conflict = rollback_learning_guard(output, entry)
        if learning_conflict:
            raise CandidatePublicationError(
                "revoked_learning_derivative",
                "rollback would resurrect a revoked learning derivative",
                phase="rollback",
                details=learning_conflict,
            )
        if receipt.get("index_compatible") is not True:
            raise CandidatePublicationError(
                "index_incompatible",
                "retained generation requires an index rebuild before restoration",
                phase="rollback",
            )
        if _contains_symlink(entry):
            raise CandidatePublicationError(
                "history_invalidated",
                "retained generation contains a symbolic link",
                phase="rollback",
            )
        historical_validation = validate_package(entry)
        if not historical_validation.ok:
            raise CandidatePublicationError(
                "history_invalidated",
                "retained generation no longer validates",
                phase="rollback",
                details={"errors": historical_validation.errors},
            )
        try:
            historical_manifest = read_manifest(entry / "manifest.json")
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            raise CandidatePublicationError(
                "history_invalidated",
                "retained generation manifest is invalid",
                phase="rollback",
            ) from exc
        revocation = _candidate_revocation_conflict(output, historical_manifest, entry)
        if revocation is not None:
            raise CandidatePublicationError(
                "source_revoked",
                "rollback would restore withdrawn or revoked source content",
                phase="rollback",
                details=revocation,
            )
        historical_revisions = historical_manifest.get("revisions")
        if not isinstance(historical_revisions, Mapping) or any(
            historical_revisions.get(key) != receipt.get(key)
            for key in ("release_id", "composition_hash", "index_revision")
        ):
            raise CandidatePublicationError(
                "history_invalidated",
                "retained generation evidence does not match its manifest",
                phase="rollback",
            )

        active_manifest_path = output / "manifest.json"
        if output.is_symlink() or not output.is_dir() or not active_manifest_path.is_file():
            raise CandidatePublicationError(
                "active_generation_missing",
                "rollback requires an existing active generation",
                phase="rollback",
            )
        active_validation = validate_package(output)
        if not active_validation.ok:
            raise CandidatePublicationError(
                "active_generation_invalid",
                "active generation must validate before rollback",
                phase="rollback",
                details={"errors": active_validation.errors},
            )
        active_manifest = read_manifest(active_manifest_path)
        active_revisions = active_manifest.get("revisions")
        if not isinstance(active_revisions, Mapping) or not isinstance(active_revisions.get("release_id"), str):
            raise CandidatePublicationError(
                "active_revision_evidence_missing",
                "active generation has no release identity",
                phase="rollback",
            )
        if active_revisions.get("release_id") == receipt["release_id"]:
            return {
                "schema_version": 1,
                "ok": True,
                "status": "already_active",
                "code": "candidate_already_active",
                "release_id": receipt["release_id"],
                "previous_release_id": active_revisions["release_id"],
                "rollback": None,
                "published": True,
            }

        rollback = {
            "schema_version": 1,
            "rollback_id": f"rollback-{uuid.uuid4().hex}",
            "target_release_id": receipt["release_id"],
            "previous_release_id": active_revisions["release_id"],
            "rolled_back_at": utc_now(),
        }
        _candidate_contract_or_raise("rollback", rollback, code="rollback_contract_invalid")
        stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent))
        shutil.copytree(entry, stage, dirs_exist_ok=True, symlinks=False)
        write_json_atomic(stage / ".docops" / "rollback.json", rollback)
        staged_manifest = read_manifest(stage / "manifest.json")
        staged_manifest["rollback"] = dict(rollback)
        staged_manifest["outcome"] = _outcome(
            "succeeded",
            "candidate_rolled_back",
            "promote",
            "retained candidate generation restored",
            exit_code=0,
        )
        staged_validation = validate_package(stage)
        staged_manifest["validation"] = staged_validation.to_dict()
        write_manifest(stage / "manifest.json", staged_manifest)
        staged_validation = validate_package(stage)
        if not staged_validation.ok:
            raise CandidatePublicationError(
                "rollback_validation_failed",
                "rollback staging failed validation",
                phase="prepare",
                details={"errors": staged_validation.errors},
            )

        backup = _promote(
            stage,
            output,
            f".{output.name}.backup-rollback-{uuid.uuid4().hex}",
            plan_hash=rollback["rollback_id"],
        )
        promoted = True
        post_validation = validate_package(output)
        if not post_validation.ok:
            raise CandidatePublicationError(
                "rollback_validation_failed",
                "rolled-back package failed post-promotion validation",
                phase="promote",
                details={"errors": post_validation.errors},
            )
        manifest = read_manifest(output / "manifest.json")
        manifest["rollback"] = dict(rollback)
        manifest["outcome"] = _outcome(
            "succeeded",
            "candidate_rolled_back",
            "promote",
            "retained candidate generation restored",
            exit_code=0,
        )
        manifest["validation"] = post_validation.to_dict()
        write_manifest(output / "manifest.json", manifest)
        final_validation = validate_package(output)
        if not final_validation.ok:
            raise CandidatePublicationError(
                "rollback_validation_failed",
                "rolled-back manifest failed final validation",
                phase="promote",
                details={"errors": final_validation.errors},
            )
        _clear_promotion_journal(output)
        if backup is not None and backup.exists():
            _remove_generated_path(backup)
            backup = None
        return {
            "schema_version": 1,
            "ok": True,
            "status": "rolled_back",
            "code": "candidate_rolled_back",
            "release_id": receipt["release_id"],
            "previous_release_id": rollback["previous_release_id"],
            "rollback_id": rollback["rollback_id"],
            "rollback": ".docops/rollback.json",
            "published": True,
        }
    except CandidatePublicationError:
        _restore_after_failed_promotion(output, backup, promoted=promoted)
        raise
    except OperationFailure as exc:
        _restore_after_failed_promotion(output, backup, promoted=promoted)
        raise CandidatePublicationError(exc.code, str(exc), phase=exc.phase, details=exc.details) from exc
    except (OSError, TypeError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        _restore_after_failed_promotion(output, backup, promoted=promoted)
        raise CandidatePublicationError(
            "rollback_failed",
            "candidate rollback failed safely",
            phase="promote" if promoted else "prepare",
        ) from exc
    finally:
        if stage is not None and stage.exists() and not _promotion_journal_path(output).exists():
            try:
                _remove_generated_path(stage)
            except OSError:
                pass
        lease.release()


def _recover_before_apply(plan_value: OperationPlan) -> dict[str, Any] | None:
    output = plan_value.request.options.output_dir
    try:
        snapshot = _promotion_recovery_snapshot(output)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "recovered": False,
            "code": "promotion_recovery_inspection_failed",
            "error": redact_text(str(exc)),
            "status": "incomplete",
            "phase": None,
        }
    if snapshot.get("status") != "recoverable":
        return None
    options = plan_value.request.options
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {
            "ok": False,
            "recovered": False,
            "code": "output_parent_unavailable",
            "error": redact_text(str(exc)),
            **snapshot,
        }
    lease = PackageLease(
        output,
        policy=options.lease_policy,
        wait_seconds=options.lease_timeout_seconds,
        stale_after_seconds=options.stale_lease_seconds,
    )
    try:
        lease.acquire()
    except LeaseBusyError as exc:
        return {
            "ok": False,
            "recovered": False,
            "code": "writer_busy",
            "error": redact_text(str(exc)),
            **snapshot,
        }
    except OSError as exc:
        return {
            "ok": False,
            "recovered": False,
            "code": "lease_unavailable",
            "error": redact_text(str(exc)),
            **snapshot,
        }
    try:
        try:
            return _recover_interrupted_promotion(output)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            return {
                "ok": False,
                "recovered": False,
                "code": "promotion_recovery_failed",
                "error": redact_text(str(exc)),
                **snapshot,
            }
    finally:
        lease.release()


def apply(plan_value: OperationPlan) -> PipelineResult:
    """Apply an immutable plan through staging and one recoverable promotion."""

    if not isinstance(plan_value, OperationPlan):
        raise TypeError("apply expects an OperationPlan returned by plan")
    operation_started = time.monotonic()
    output = plan_value.request.options.output_dir
    recovery = _recover_before_apply(plan_value)
    if recovery is not None and not recovery.get("ok"):
        code = str(recovery.get("code", "promotion_recovery_failed"))
        outcome = _timed_outcome(
            _outcome(
                "blocked" if code == "writer_busy" else "failed",
                code,
                "recover",
                "promotion recovery could not produce a valid generation",
                exit_code=3 if code == "writer_busy" else 1,
            ),
            operation_started,
        )
        errors = [{"code": code, "message": str(recovery.get("error", outcome["message"]))}]
        _record_attempt(output, plan_value, outcome, phase="recover", errors=errors)
        return _failure_result(plan_value, outcome, errors)
    if recovery is not None and recovery.get("recovered"):
        try:
            plan_value = plan(plan_value.request)
        except Exception as exc:
            outcome = _timed_outcome(
                _outcome(
                    "failed", "plan_refresh_failed", "recover", "could not refresh the plan after recovery", exit_code=1
                ),
                operation_started,
            )
            errors = [{"code": outcome["code"], "message": redact_text(exc)}]
            _record_attempt(output, plan_value, outcome, phase="recover", errors=errors)
            return _failure_result(plan_value, outcome, errors)
    if plan_value.blockers:
        outcome = _timed_outcome(
            _outcome(
                "blocked",
                str(plan_value.blockers[0].get("code", "plan_blocked")),
                "plan",
                "operation plan contains blockers",
                exit_code=2,
            ),
            operation_started,
        )
        errors = [
            {
                "code": str(blocker.get("code", "plan_blocked")),
                "message": str(blocker.get("message", "operation plan contains blockers")),
            }
            for blocker in plan_value.blockers
        ]
        _record_attempt(output, plan_value, outcome, phase="plan", errors=errors)
        return _failure_result(plan_value, outcome, errors)
    try:
        current = plan(plan_value.request)
    except Exception as exc:
        outcome = _timed_outcome(
            _outcome("failed", "plan_refresh_failed", "plan", "could not refresh the operation plan", exit_code=1),
            operation_started,
        )
        errors = [{"code": outcome["code"], "message": redact_text(exc)}]
        _record_attempt(output, plan_value, outcome, phase="plan", errors=errors)
        return _failure_result(plan_value, outcome, errors)
    if current.plan_hash != plan_value.plan_hash:
        outcome = _timed_outcome(
            _outcome(
                "blocked", "stale_plan", "plan", "operation plan is stale; source or destination changed", exit_code=3
            ),
            operation_started,
        )
        errors = [{"code": "stale_plan", "message": "source or destination changed after plan creation"}]
        _record_attempt(output, plan_value, outcome, phase="plan", errors=errors)
        return _failure_result(plan_value, outcome, errors)
    managed, _reason = _managed_package(output)
    if not plan_value.actions and managed and not plan_value.request.options.index_rag:
        try:
            validation = validate_package(output)
        except Exception as exc:
            outcome = _timed_outcome(
                _outcome(
                    "failed", "active_validation_failed", "validate", "active package validation failed", exit_code=1
                ),
                operation_started,
            )
            errors = [{"code": outcome["code"], "message": redact_text(exc)}]
            _record_attempt(output, plan_value, outcome, phase="validate", errors=errors)
            return _failure_result(plan_value, outcome, errors)
        result = _no_op_result(plan_value, validation)
        _record_attempt(output, plan_value, result.outcome, phase="inspect", errors=result.errors)
        return result
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        outcome = _timed_outcome(
            _outcome("failed", "output_parent_unavailable", "prepare", "output parent is not writable", exit_code=1),
            operation_started,
        )
        errors = [{"code": outcome["code"], "message": redact_text(exc)}]
        _record_attempt(output, plan_value, outcome, phase="prepare", errors=errors)
        return _failure_result(plan_value, outcome, errors)
    lease = PackageLease(
        output,
        policy=plan_value.request.options.lease_policy,
        wait_seconds=plan_value.request.options.lease_timeout_seconds,
        stale_after_seconds=plan_value.request.options.stale_lease_seconds,
    )
    try:
        lease.acquire()
    except LeaseBusyError as exc:
        outcome = _timed_outcome(_outcome("blocked", "writer_busy", "lease", str(exc), exit_code=3), operation_started)
        errors = [
            {
                "code": "writer_busy",
                "message": redact_text(exc),
                **{key: str(value) for key, value in exc.details.items() if key != "message"},
            }
        ]
        _record_attempt(output, plan_value, outcome, phase="lease", errors=errors)
        return _failure_result(plan_value, outcome, errors)
    except Exception as exc:
        outcome = _timed_outcome(
            _outcome("failed", "lease_unavailable", "lease", "could not acquire the package writer lease", exit_code=1),
            operation_started,
        )
        errors = [{"code": outcome["code"], "message": redact_text(exc)}]
        _record_attempt(output, plan_value, outcome, phase="lease", errors=errors)
        return _failure_result(plan_value, outcome, errors)
    # The optimistic refresh above is the only source revalidation.  A second
    # full acquisition here would hold the writer lease while crawling or
    # cloning the source, needlessly blocking readers and other writers.  The
    # destination fingerprint is cheap to recompute and detects a generation
    # promoted by another writer during the lease race without reacquiring the
    # source corpus.
    if _destination_fingerprint(output) != current.destination_fingerprint:
        lease.release()
        outcome = _timed_outcome(
            _outcome("blocked", "stale_plan", "lease", "operation plan became stale before promotion", exit_code=3),
            operation_started,
        )
        errors = [{"code": "stale_plan", "message": "source or destination changed before promotion"}]
        _record_attempt(output, plan_value, outcome, phase="lease", errors=errors)
        return _failure_result(plan_value, outcome, errors)
    stage = _resume_stage(output, plan_value)
    if stage is None:
        stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent))
    phase = "prepare"
    before = _tree_snapshot(output)
    backup: Path | None = None
    promoted = False
    try:
        phase = "prepare"
        _build_stage(plan_value, stage)
        if plan_value.request.options.publication_policy == "candidate":
            phase = "candidate"
            _candidate_failpoint("after-stage")
            try:
                base_manifest = read_manifest(output / "manifest.json") if managed else {}
                candidate_manifest = read_manifest(stage / "manifest.json")
                candidate_id, _candidate_path, _receipt = finalize_candidate(
                    output,
                    stage,
                    base_manifest=base_manifest,
                    plan_hash=plan_value.plan_hash,
                    manifest=candidate_manifest,
                )
            except CandidateError as exc:
                raise OperationFailure("unsafe_candidate_path", str(exc), phase="candidate") from exc
            validation = validate_package(_candidate_path)
            if not validation.ok:
                raise OperationFailure(
                    "candidate_validation_failed",
                    "prepared candidate failed validation",
                    phase="candidate",
                    details={"errors": validation.errors},
                )
            outcome = _timed_outcome(
                _outcome(
                    "succeeded",
                    "candidate_prepared",
                    "candidate",
                    "candidate package prepared without changing the active generation",
                    exit_code=0,
                ),
                operation_started,
            )
            outcome["candidate_id"] = candidate_id
            outcome["candidate_locator"] = candidate_locator(output, candidate_id)
            after = _tree_snapshot(output)
            written = sum(1 for path in set(before) | set(after) if before.get(path) != after.get(path))
            _record_attempt(output, plan_value, outcome, phase="candidate")
            return PipelineResult(
                True,
                output,
                candidate_manifest,
                validation,
                dict(plan_value.state_diff),
                written,
                [],
                list(plan_value.warnings),
                outcome,
                0,
            )
        phase = "promote"
        backup = _promote(stage, output, f".{output.name}.backup-{plan_value.plan_id}", plan_hash=plan_value.plan_hash)
        promoted = True
        validation = validate_package(output)
        if not validation.ok:
            raise OperationFailure(
                "promotion_validation_failed",
                "promoted package failed validation",
                phase="promote",
                details={"errors": validation.errors},
            )
        manifest = read_manifest(output / "manifest.json")
        outcome = _timed_outcome(
            _outcome("succeeded", "completed", "promote", "operation completed", exit_code=0), operation_started
        )
        manifest["outcome"] = outcome
        manifest_metrics = manifest.setdefault("metrics", {})
        if isinstance(manifest_metrics, dict):
            try:
                checkpoint_data = json.loads((output / ".docops" / "checkpoints.json").read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                checkpoint_data = {}
            manifest_metrics["operation"] = {
                "duration_ms": outcome["duration_ms"],
                "phases": sorted(checkpoint_data.get("phases", {})) if isinstance(checkpoint_data, dict) else [],
            }
        write_manifest(output / "manifest.json", manifest)
        validation = validate_package(output)
        if not validation.ok:
            raise OperationFailure(
                "promotion_validation_failed",
                "promoted package failed validation",
                phase="promote",
                details={"errors": validation.errors},
            )
        manifest["validation"] = validation.to_dict()
        write_manifest(output / "manifest.json", manifest)
        after = _tree_snapshot(output)
        written = sum(1 for path in set(before) | set(after) if before.get(path) != after.get(path))
        warnings = list(
            dict.fromkeys([*manifest.get("warnings", []), *(warning["message"] for warning in validation.warnings)])
        )
        _clear_promotion_journal(output)
        if backup is not None and backup.exists():
            _remove_generated_path(backup)
            backup = None
        result = PipelineResult(
            True,
            output,
            manifest,
            validation,
            dict(plan_value.state_diff),
            written,
            [],
            warnings,
            dict(outcome),
            0,
        )
        _record_attempt(output, plan_value, outcome, phase="promote")
        return result
    except KeyboardInterrupt:
        _restore_after_failed_promotion(output, backup, promoted=promoted)
        outcome = _timed_outcome(
            _outcome(
                "cancelled",
                "operation_interrupted",
                phase,
                "operation interrupted; staged work is resumable",
                exit_code=4,
            ),
            operation_started,
        )
        errors = [{"code": outcome["code"], "message": outcome["message"]}]
        _record_attempt(output, plan_value, outcome, phase=phase, errors=errors, staging=stage)
        return _failure_result(plan_value, outcome, errors)
    except OperationFailure as exc:
        _restore_after_failed_promotion(output, backup, promoted=promoted)
        outcome = _timed_outcome(_outcome("failed", exc.code, exc.phase, str(exc), exit_code=1), operation_started)
        errors = [{"code": exc.code, "message": redact_text(exc)}]
        if exc.details.get("errors") and isinstance(exc.details["errors"], list):
            errors.extend(dict(error) for error in exc.details["errors"] if isinstance(error, Mapping))
        _record_attempt(output, plan_value, outcome, phase=exc.phase, errors=errors, staging=stage)
        return _failure_result(plan_value, outcome, errors)
    except Exception as exc:
        _restore_after_failed_promotion(output, backup, promoted=promoted)
        outcome = _timed_outcome(_outcome("failed", "apply_failed", phase, str(exc), exit_code=1), operation_started)
        errors = [{"code": outcome["code"], "message": redact_text(exc)}]
        _record_attempt(output, plan_value, outcome, phase=phase, errors=errors, staging=stage)
        return _failure_result(plan_value, outcome, errors)
    finally:
        lease.release()


def _inspect_once(package_root: Path | str) -> dict[str, Any]:
    """Inspect active generation, readiness and recoverable attempt residue."""

    root = Path(os.path.abspath(os.fspath(Path(package_root).expanduser())))
    now = time.time()
    lease = _lease_summary(root)
    lease_active = lease["status"] == "active" and lease.get("owner_alive") is not False
    try:
        recovery = _promotion_recovery_snapshot(root, now=now)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        recovery = {
            "status": "incomplete",
            "phase": None,
            "error": redact_text(str(exc)),
        }
    managed, reason = _managed_package(root)
    inspection_root = root
    if not managed and recovery.get("status") == "recoverable":
        # A directory promotion cannot replace a non-empty destination on
        # every supported filesystem.  During the short rename window the
        # last valid generation lives at the journaled backup path.  Inspect
        # that generation as the logical active view so public readers never
        # receive a false "unmanaged"/invalid result.
        if recovery.get("active_valid"):
            managed, reason = _managed_package(root)
        if not managed:
            backup = _promotion_member(root, recovery.get("backup_name"), f".{root.name}.backup-")
            backup_evidence = recovery.get("backup")
            backup_valid = isinstance(backup_evidence, Mapping) and backup_evidence.get("valid") is True
            if backup_valid:
                managed = True
                reason = "promotion_recoverable"
                inspection_root = backup
    manifest: dict[str, Any] = {}
    validation: dict[str, Any] | None = None
    if managed:
        try:
            manifest = read_manifest(inspection_root / "manifest.json")
            validation = validate_package(inspection_root).to_dict()
        except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
            validation = {
                "schema_version": 1,
                "ok": False,
                "errors": [{"code": "inspect_failed", "message": redact_text(exc)}],
                "warnings": [],
                "checks": {},
            }
    stages: list[dict[str, Any]] = []
    prefix = f".{root.name}.staging-"
    if root.parent.is_dir():
        for candidate in sorted(root.parent.iterdir()):
            if candidate.name.startswith(prefix) and candidate.is_dir() and not candidate.is_symlink():
                plan_path = candidate / ".docops" / "plan.json"
                try:
                    saved = json.loads(plan_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError):
                    saved = {}
                age_seconds = _residue_age(candidate, now)
                valid_plan = (
                    isinstance(saved, dict) and isinstance(saved.get("plan_hash"), str) and bool(saved["plan_hash"])
                )
                if lease_active:
                    status = "active"
                elif valid_plan and age_seconds <= _RESIDUE_RETENTION_SECONDS:
                    status = "resumable"
                elif valid_plan:
                    status = "expired"
                else:
                    status = "orphan"
                stages.append(
                    {
                        "plan_hash": saved.get("plan_hash") if valid_plan else None,
                        "status": status,
                        "age_seconds": age_seconds,
                    }
                )
    attempts: list[dict[str, Any]] = []
    attempt_root = _attempt_root(root)
    if attempt_root.is_dir():
        for path in sorted(attempt_root.glob("*.json")):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            if isinstance(value, dict):
                safe_attempt = redact_report(redact_metadata(value))
                age_seconds = _residue_age(path, now)
                staging_value = value.get("staging")
                staging_present = isinstance(staging_value, Mapping) and staging_value.get("present") is True
                safe_attempt["status"] = (
                    "active"
                    if lease_active and staging_present
                    else "retained"
                    if age_seconds <= _RESIDUE_RETENTION_SECONDS
                    else "expired"
                )
                safe_attempt["age_seconds"] = age_seconds
                attempts.append(safe_attempt)
    backups: list[dict[str, Any]] = []
    backup_prefix = f".{root.name}.backup-"
    if root.parent.is_dir():
        for candidate in sorted(root.parent.iterdir()):
            if not candidate.name.startswith(backup_prefix) or not (candidate.is_dir() or candidate.is_symlink()):
                continue
            age_seconds = _residue_age(candidate, now)
            backups.append(
                {
                    "status": "active"
                    if lease_active
                    else "recoverable"
                    if age_seconds <= _RESIDUE_RETENTION_SECONDS
                    else "expired",
                    "age_seconds": age_seconds,
                }
            )
    readiness = assess_readiness(inspection_root) if managed else {}
    if lease_active and recovery.get("status") == "recoverable":
        recovery = {**recovery, "status": "writer_busy"}
    return {
        "schema_version": 1,
        "managed": managed,
        "reason": reason,
        "active": {
            "source": "active" if inspection_root == root else "recovery-backup",
            "status": manifest.get("status") if manifest else None,
            "outcome": manifest.get("outcome") if manifest else None,
            "readiness": readiness,
            "layers": manifest.get("layers") if manifest else None,
            "conceptual_lag": manifest.get("conceptual_lag") if manifest else None,
            "revisions": manifest.get("revisions") if manifest else None,
            "validation": validation,
        },
        "history": _inspect_history(root),
        "candidates": _inspect_candidates(root),
        "lease": lease,
        "staging": stages,
        "backups": backups,
        "attempts": attempts,
        "recovery": recovery,
        "residues": {"staging": stages, "backups": backups, "attempts": attempts},
    }


def _inspect_candidates(root: Path) -> list[dict[str, Any]]:
    reports = list_candidates(root)
    for report in reports:
        candidate_id = report.get("candidate_id")
        if report.get("status") != "review_required" or not isinstance(candidate_id, str):
            continue
        try:
            candidate_path = root.parent / f".{root.name}.candidates" / candidate_id
            validation = validate_package(candidate_path)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            report["status"] = "rejected"
            report["code"] = "candidate_validation_failed"
            report["message"] = redact_text(str(exc))
        else:
            report["validation"] = validation.to_dict()
            if not validation.ok:
                report["status"] = "rejected"
                report["code"] = "candidate_validation_failed"
    return reports


_INSPECTION_SETTLE_SECONDS = 5.0
_RESIDUE_RETENTION_SECONDS = 7 * 24 * 60 * 60


def _residue_age(path: Path, now: float | None = None) -> float:
    try:
        return round(max(0.0, (now if now is not None else time.time()) - path.stat().st_mtime), 3)
    except OSError:
        return _RESIDUE_RETENTION_SECONDS + 1.0


def _lease_summary(root: Path) -> dict[str, Any]:
    lock = root.parent / f".{root.name}.docops.writer.lock"
    if not (lock.is_symlink() or lock.is_file()):
        return {"status": "absent", "owner": None, "age_seconds": None}
    owner = "unknown"
    started_at = 0.0
    pid = 0
    try:
        raw = json.loads(lock.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            pid = int(raw.get("pid", 0))
            hostname = str(raw.get("hostname", "unknown"))
            started_at = float(raw.get("started_at", 0.0))
            if pid > 0 and hostname:
                owner = (
                    f"owner-{hashlib.sha256(f'{hostname}:{pid}'.encode('utf-8', errors='replace')).hexdigest()[:12]}"
                )
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        pass
    return {
        "status": "active",
        "owner": owner,
        "age_seconds": round(max(0.0, time.time() - started_at), 3) if started_at > 0 else None,
        "owner_alive": PackageLease._pid_alive(pid) if pid > 0 else None,
    }


def _writer_lock_present(root: Path) -> bool:
    lock = root.parent / f".{root.name}.docops.writer.lock"
    return lock.is_symlink() or lock.is_file()


def inspect(package_root: Path | str) -> dict[str, Any]:
    """Inspect a stable generation, settling transient promotion states.

    The public reader seam waits while the package writer lease is present if
    a promotion has made the active directory temporarily incomplete.  This
    keeps readers from observing the rename gap on filesystems where a
    directory cannot be replaced atomically in place.  If the writer does not
    settle within the bounded window, the diagnostic is returned as-is.
    """

    root = Path(os.path.abspath(os.fspath(Path(package_root).expanduser())))
    started = time.monotonic()
    deadline = started + _INSPECTION_SETTLE_SECONDS

    def finish(report: dict[str, Any], *, timed_out: bool) -> dict[str, Any]:
        recovery = report.get("recovery")
        if isinstance(recovery, Mapping):
            report["recovery"] = _public_recovery_snapshot(recovery)
        report["inspection"] = {
            "status": "timed_out" if timed_out else "completed",
            "code": "reader_busy" if timed_out else "completed",
            "waited_seconds": round(max(0.0, time.monotonic() - started), 3),
        }
        return report

    while True:
        # Do not open the active generation while a live writer is preparing
        # or promoting it.  On Windows even a short-lived read handle can
        # deny the directory rename; the writer lease is the public
        # read/write coordination seam, so wait before validating files.
        lease = _lease_summary(root)
        writer_active = lease.get("status") == "active" and lease.get("owner_alive") is not False
        if writer_active and time.monotonic() < deadline:
            time.sleep(0.01)
            continue
        report = _inspect_once(root)
        active = report.get("active", {})
        validation = active.get("validation") if isinstance(active, Mapping) else None
        stable = report.get("managed") is True and isinstance(validation, Mapping) and validation.get("ok") is True
        recovery = report.get("recovery")
        report_lease = report.get("lease")
        report_writer_active = (
            isinstance(report_lease, Mapping)
            and report_lease.get("status") == "active"
            and report_lease.get("owner_alive") is not False
        )
        if (stable and not report_writer_active) or (
            not report_writer_active
            and isinstance(recovery, Mapping)
            and recovery.get("status") in {"recoverable", "incomplete"}
        ):
            return finish(report, timed_out=False)
        if time.monotonic() >= deadline:
            return finish(report, timed_out=report_writer_active)
        if not _writer_lock_present(root) and report.get("managed") is not True:
            return finish(report, timed_out=False)
        time.sleep(0.01)


def cleanup(
    package_root: Path | str,
    *,
    retention_seconds: float = _RESIDUE_RETENTION_SECONDS,
    keep_attempts: int = 20,
) -> dict[str, Any]:
    """Remove only expired, non-resumable operation residue.

    Cleanup obtains the same writer lease as ``apply``.  A live writer makes
    cleanup a no-op with a structured ``writer_busy`` result; no active
    generation, valid resumable staging tree or live lease is removed.
    """

    root = Path(os.path.abspath(os.fspath(Path(package_root).expanduser())))
    if isinstance(retention_seconds, bool) or not isinstance(retention_seconds, (int, float)) or retention_seconds < 0:
        raise ValueError("retention_seconds must be a non-negative number")
    if isinstance(keep_attempts, bool) or not isinstance(keep_attempts, int) or keep_attempts < 0:
        raise ValueError("keep_attempts must be a non-negative integer")
    if root.is_symlink():
        return {
            "schema_version": 1,
            "ok": False,
            "code": "unsafe_output_path",
            "removed": [],
            "preserved": [],
            "errors": [{"code": "unsafe_output_path", "message": "output directory must not be a symbolic link"}],
        }
    lease = PackageLease(root, policy="fail")
    try:
        lease.acquire()
    except LeaseBusyError as exc:
        return {
            "schema_version": 1,
            "ok": False,
            "code": "writer_busy",
            "removed": [],
            "preserved": [{"type": "writer-lease", "status": "active"}],
            "errors": [{"code": "writer_busy", "message": redact_text(str(exc))}],
        }

    removed: list[dict[str, str]] = []
    preserved: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    now = time.time()
    try:
        recovery = _promotion_recovery_snapshot(root, now=now)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        lease.release()
        return {
            "schema_version": 1,
            "ok": False,
            "code": "cleanup_failed",
            "removed": [],
            "preserved": [{"type": "promotion-journal", "status": "inspection-failed"}],
            "errors": [{"code": "cleanup_failed", "message": redact_text(str(exc))}],
        }
    promotion_journal = _promotion_journal_path(root)
    journal_present = promotion_journal.exists() or promotion_journal.is_symlink()
    protected_residue_names = {
        name for name in (recovery.get("stage_name"), recovery.get("backup_name")) if isinstance(name, str) and name
    }

    def remove(path: Path, residue_type: str, status: str) -> None:
        try:
            _remove_generated_path(path)
            removed.append({"type": residue_type, "id": _opaque_residue_id(path), "status": status})
        except OSError as exc:
            errors.append({"code": "cleanup_failed", "message": redact_text(str(exc))})
            preserved.append({"type": residue_type, "id": _opaque_residue_id(path), "status": "error"})

    try:
        parent = root.parent
        if parent.is_dir():
            staging_prefix = f".{root.name}.staging-"
            staging_candidates = [
                candidate
                for candidate in sorted(parent.iterdir())
                if candidate.name.startswith(staging_prefix) and (candidate.is_dir() or candidate.is_symlink())
            ]
            backup_prefix = f".{root.name}.backup-"
            backup_candidates = [
                candidate
                for candidate in sorted(parent.iterdir())
                if candidate.name.startswith(backup_prefix) and (candidate.is_dir() or candidate.is_symlink())
            ]
            journal_incomplete = recovery.get("status") == "incomplete" and journal_present

            def best_candidate(candidates: list[Path], *, staging: bool) -> Path | None:
                safe = [candidate for candidate in candidates if candidate.is_dir() and not candidate.is_symlink()]
                if not safe:
                    return None
                recoverable: list[Path] = []
                for candidate in safe:
                    if _valid_generation(candidate):
                        recoverable.append(candidate)
                        continue
                    if staging:
                        plan_path = candidate / ".docops" / "plan.json"
                        try:
                            saved = json.loads(plan_path.read_text(encoding="utf-8"))
                        except (OSError, UnicodeError, json.JSONDecodeError):
                            saved = {}
                        if (
                            not _contains_symlink(candidate)
                            and isinstance(saved, dict)
                            and isinstance(saved.get("plan_hash"), str)
                            and bool(saved["plan_hash"])
                        ):
                            recoverable.append(candidate)
                pool = recoverable or safe
                return min(pool, key=lambda candidate: _residue_age(candidate, now))

            incomplete_stage = best_candidate(staging_candidates, staging=True) if journal_incomplete else None
            incomplete_backup = best_candidate(backup_candidates, staging=False) if journal_incomplete else None

            for candidate in staging_candidates:
                if candidate == incomplete_stage:
                    preserved.append(
                        {
                            "type": "staging",
                            "id": _opaque_residue_id(candidate),
                            "status": "journal-incomplete-recovery-candidate",
                        }
                    )
                    continue
                if candidate.name in protected_residue_names:
                    preserved.append({"type": "staging", "id": _opaque_residue_id(candidate), "status": "recoverable"})
                    continue
                age_seconds = _residue_age(candidate, now)
                plan_path = candidate / ".docops" / "plan.json"
                try:
                    saved = json.loads(plan_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError):
                    saved = {}
                valid_plan = (
                    not candidate.is_symlink()
                    and not _contains_symlink(candidate)
                    and isinstance(saved, dict)
                    and isinstance(saved.get("plan_hash"), str)
                    and bool(saved["plan_hash"])
                )
                if valid_plan and age_seconds <= retention_seconds:
                    preserved.append({"type": "staging", "id": _opaque_residue_id(candidate), "status": "resumable"})
                elif valid_plan:
                    remove(candidate, "staging", "expired")
                else:
                    remove(candidate, "staging", "orphan")

            for candidate in backup_candidates:
                if candidate == incomplete_backup:
                    preserved.append(
                        {
                            "type": "backup",
                            "id": _opaque_residue_id(candidate),
                            "status": "journal-incomplete-recovery-candidate",
                        }
                    )
                    continue
                if candidate.name in protected_residue_names:
                    preserved.append({"type": "backup", "id": _opaque_residue_id(candidate), "status": "recoverable"})
                    continue
                age_seconds = _residue_age(candidate, now)
                if age_seconds <= retention_seconds:
                    preserved.append({"type": "backup", "id": _opaque_residue_id(candidate), "status": "recoverable"})
                else:
                    remove(candidate, "backup", "expired")

            attempt_dir = _attempt_root(root)
            if attempt_dir.is_dir() and not attempt_dir.is_symlink():
                attempt_files = sorted(
                    (path for path in attempt_dir.glob("*.json") if path.is_file() and not path.is_symlink()),
                    key=lambda path: path.stat().st_mtime,
                    reverse=True,
                )
                for index, candidate in enumerate(attempt_files):
                    age_seconds = _residue_age(candidate, now)
                    if age_seconds <= retention_seconds and index < keep_attempts:
                        preserved.append({"type": "attempt", "id": _opaque_residue_id(candidate), "status": "retained"})
                    else:
                        remove(candidate, "attempt", "expired" if age_seconds > retention_seconds else "over-limit")
                if not any(attempt_dir.iterdir()):
                    attempt_dir.rmdir()
            if recovery.get("status") in {"recoverable", "incomplete"}:
                preserved.append({"type": "promotion-journal", "status": str(recovery["status"])})
    except OSError as exc:
        errors.append({"code": "cleanup_failed", "message": redact_text(str(exc))})
    finally:
        lease.release()

    return {
        "schema_version": 1,
        "ok": not errors,
        "code": "completed" if not errors else "cleanup_failed",
        "removed": removed,
        "preserved": preserved,
        "errors": errors,
    }
