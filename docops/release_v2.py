"""Explicit Farol 2.0 release and RAGFlow cutover gates."""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .contracts import validate_artifact
from .revisions import content_hash

# The editorial surface is the removed Farol 1.x contract, not the English
# words. ``page`` in particular remains a valid IR locator kind, so the pattern
# matches only explicit contract symbols and the withdrawn brand.
EDITORIAL_TERMS = re.compile(
    r"mercado[ -]?livre"
    r"|mercadolivre"
    r"|\b(?:course|page)_(?:id|edit|intent)\b"
    r"|\b(?:course|page)\.schema\.json\b"
    r"|\boffer\.json\b"
    r"|\bpage\.offer\b"
    r"|\bcommercial_authorization\b"
    r"|\b_is_valid_price\b"
    r"|\bdeliverables\b[^\n]{0,40}[\"'](?:course|page|offer)[\"']"
    r"|[\"'](?:course|offer)[\"']",
    re.IGNORECASE,
)
LEGACY_TERMS = re.compile(r"knowledge-rag|chromadb|\bchroma\b", re.IGNORECASE)

# Only the product surface can carry a real residual: implementation, schemas,
# fixtures, package data and the distribution. Documentation prose and the
# migration/test seams that must keep naming the excluded contracts are
# allowlisted explicitly.
_NORMATIVE_PREFIXES = ("docops/", "schemas/", "scripts/", "tests/", "presets/")
_NORMATIVE_FILES = {
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements.lock",
    "config.yaml",
}
_SURFACE_ALLOWLIST = {
    "docops/release_v2.py",
    "docops/migration.py",
    # AC-027 requires the migrator and its contract tests to keep naming the
    # excluded editorial contracts so a 1.x package can be reported, never
    # loaded. Those seams are the only place the names may survive.
    "tests/test_migration_v2.py",
    "tests/test_v2_contracts.py",
    "tests/test_release_v2_surface.py",
    "tests/test_farol_v2_gates.py",
    "scripts/check_contracts.py",
    "tests/test_master_evolution.py",
    "specs/farol-2/",
}
_SKIPPED_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache"}


@dataclass(frozen=True)
class SurfaceAudit:
    surface: str
    ok: bool
    findings: list[dict[str, Any]]
    scanned_files: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "kind": "farol_v2_surface_audit",
            "surface": self.surface,
            "ok": self.ok,
            "scanned_files": self.scanned_files,
            "findings": self.findings,
        }


def audit_release_surface(
    root: Path | str,
    *,
    surface: str = "editorial",
    wheel: Path | str | None = None,
    allow_paths: set[str] | None = None,
) -> SurfaceAudit:
    """Find forbidden 1.x surfaces without exposing source content."""

    if surface not in {"editorial", "legacy", "all"}:
        raise ValueError("surface must be editorial, legacy or all")
    patterns: list[tuple[str, re.Pattern[str]]] = []
    if surface in {"editorial", "all"}:
        patterns.append(("editorial", EDITORIAL_TERMS))
    if surface in {"legacy", "all"}:
        patterns.append(("legacy", LEGACY_TERMS))
    allowed = set(_SURFACE_ALLOWLIST) | set(allow_paths or set())
    findings: list[dict[str, Any]] = []
    scanned = 0
    if wheel is not None:
        wheel_path = Path(wheel).expanduser().resolve()
        with zipfile.ZipFile(wheel_path) as archive:
            for name in sorted(archive.namelist()):
                if name.endswith("/") or _is_allowlisted(name, allowed) or not _in_normative_scope(name):
                    continue
                try:
                    text = archive.read(name).decode("utf-8")
                except (UnicodeDecodeError, KeyError):
                    continue
                scanned += 1
                findings.extend(_find_terms(name, text, patterns))
    else:
        root_path = Path(root).expanduser().resolve()
        for relative, path in _tracked_surface_files(root_path):
            if _is_allowlisted(relative, allowed):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            scanned += 1
            findings.extend(_find_terms(relative, text, patterns))
    return SurfaceAudit(surface, not findings, findings, scanned)


def _tracked_surface_files(root: Path) -> list[tuple[str, Path]]:
    """Enumerate the product surface without re-reading gitignored trees.

    A checkout is enumerated from ``git ls-files`` so caches, virtualenvs,
    acquired corpora and generated artifacts can never pollute the oracle. A
    directory without git metadata (for example a temporary fixture) falls back
    to a bounded walk that still ignores the same cache directories.
    """

    tracked = _git_tracked_paths(root)
    if tracked is not None:
        candidates = [(relative, root / relative) for relative in tracked]
    else:
        candidates = []
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            if any(part in _SKIPPED_DIRS or part.startswith(".venv") for part in path.parts):
                continue
            candidates.append((path.relative_to(root).as_posix(), path))
    return [
        (relative, path)
        for relative, path in candidates
        if _in_normative_scope(relative) and path.is_file() and not path.is_symlink()
    ]


def _git_tracked_paths(root: Path) -> list[str] | None:
    if not (root / ".git").exists():
        return None
    import subprocess

    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True,
            check=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return [item for item in completed.stdout.decode("utf-8", "replace").split("\0") if item]


def _in_normative_scope(relative: str) -> bool:
    return relative.startswith(_NORMATIVE_PREFIXES) or relative in _NORMATIVE_FILES


_ARM_ROLES = ("legacy", "ragflow")
_IDENTITY_KEYS = ("candidate", "ir_revision", "golden_revision", "corpus_digest", "environment")
_ARM_METRIC_KEYS = ("recall_at_5", "mrr_at_5", "citation_coverage", "lineage_coverage", "id_parity")
_EXPECTED_BACKENDS = {
    "legacy": {"name": "knowledge-rag", "version": "4.8.5"},
    "ragflow": {"name": "ragflow", "version": "0.27.2"},
}
_CUTOVER_GATE_NAMES = (
    "legacy_arm",
    "ragflow_arm",
    "candidate",
    "ir_revision",
    "golden_revision",
    "corpus_digest",
    "environment",
    "backend",
    "mappings",
    "recall_at_5",
    "mrr_at_5",
    "citation_coverage",
    "lineage_coverage",
    "id_parity",
    "lifecycle",
    "recovery",
    "rollback",
    "cleanup",
    "arm_hashes",
)
_RECEIPT_FIELDS = (
    "schema_version",
    "kind",
    "status",
    "ok",
    "legacy_preserved",
    "gates",
    "blockers",
    "candidate",
    "ir_revision",
    "golden_revision",
    "corpus_digest",
    "environment",
    "metrics",
    "backends",
    "arm_statuses",
    "arm_identities",
    "arm_metrics",
    "arm_lifecycles",
    "mappings",
    "mapping_hashes",
    "arm_hashes",
    "lifecycle",
    "cleanup",
)
_CONTEXT_FIELDS = (
    "candidate",
    "ir_revision",
    "golden_revision",
    "corpus_digest",
    "environment",
    "backends",
    "arm_statuses",
    "arm_identities",
    "mapping_hashes",
    "arm_hashes",
)


def require_cutover_approved(
    decision: Mapping[str, Any] | "CutoverDecision",
    *,
    expected_context: Mapping[str, Any] | None = None,
) -> None:
    """Guard destructive contraction behind a complete, current decision.

    A cutover receipt is evidence for the *next* contraction step, not a
    capability token by itself.  The caller must provide the context observed
    at the point of contraction so a valid receipt from an older candidate,
    corpus, backend run or mapping cannot authorize deletion.
    """

    if expected_context is None:
        raise RuntimeError("legacy contraction requires the current cutover context")
    payload = build_cutover_receipt(decision)
    if not _context_matches(payload, expected_context):
        raise RuntimeError("legacy contraction requires a current, non-stale cutover receipt")
    if payload["status"] != "cutover_approved" or payload["ok"] is not True:
        raise RuntimeError("legacy contraction requires an approved Farol 2.0 cutover decision")
    if payload["legacy_preserved"] is not True:
        raise RuntimeError("legacy contraction requires explicit preservation of the legacy backend")


def _is_allowlisted(path: str, allowlist: set[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(normalized == item or normalized.startswith(item) for item in allowlist)


def _find_terms(path: str, text: str, patterns: list[tuple[str, re.Pattern[str]]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        for category, pattern in patterns:
            matches = sorted({match.group(0).casefold() for match in pattern.finditer(line)})
            if matches:
                findings.append({"category": category, "path": path, "line": line_number, "terms": matches})
    return findings


@dataclass(frozen=True)
class CutoverDecision:
    status: str
    ok: bool
    legacy_preserved: bool
    gates: dict[str, Any]
    blockers: list[str]
    candidate: str | None = None
    ir_revision: str | None = None
    golden_revision: str | None = None
    corpus_digest: str | None = None
    environment: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None
    backends: dict[str, Any] | None = None
    arm_statuses: dict[str, Any] | None = None
    arm_identities: dict[str, Any] | None = None
    arm_metrics: dict[str, Any] | None = None
    arm_lifecycles: dict[str, Any] | None = None
    mappings: dict[str, Any] | None = None
    mapping_hashes: dict[str, Any] | None = None
    arm_hashes: dict[str, Any] | None = None
    lifecycle: dict[str, Any] | None = None
    cleanup: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = self.to_dict_without_hash()
        payload["receipt_hash"] = self.receipt_hash()
        return payload

    def to_dict_without_hash(self) -> dict[str, Any]:
        """Return the stable receipt projection used to calculate its hash."""

        return {
            "schema_version": 2,
            "kind": "cutover_decision",
            "status": self.status,
            "ok": self.ok,
            "legacy_preserved": self.legacy_preserved,
            "gates": self.gates,
            "blockers": self.blockers,
            "candidate": self.candidate,
            "ir_revision": self.ir_revision,
            "golden_revision": self.golden_revision,
            "corpus_digest": self.corpus_digest,
            "environment": dict(self.environment or {}),
            "metrics": dict(self.metrics or {}),
            "backends": dict(self.backends or {}),
            "arm_statuses": dict(self.arm_statuses or {}),
            "arm_identities": dict(self.arm_identities or {}),
            "arm_metrics": dict(self.arm_metrics or {}),
            "arm_lifecycles": dict(self.arm_lifecycles or {}),
            "mappings": dict(self.mappings or {}),
            "mapping_hashes": dict(self.mapping_hashes or {}),
            "arm_hashes": dict(self.arm_hashes or {}),
            "lifecycle": dict(self.lifecycle or {}),
            "cleanup": self.cleanup or "not_run",
        }

    def receipt_hash(self) -> str:
        """Bind the receipt to its exact inputs, excluding volatile fields."""

        return _receipt_hash_for_payload(self.to_dict_without_hash())


def evaluate_cutover(metrics: Mapping[str, Any]) -> CutoverDecision:
    """Promote measured dual-run metrics into a cutover decision.

    The thresholds are fixed by the acceptance criteria and cannot be relaxed:
    Recall@5 must be 1.0, MRR@5 at least 0.86, citation and lineage coverage
    100%, and lifecycle/recovery/rollback must be observed together with a
    passed RAGFlow status. An absent external runtime yields ``not_run`` and
    never a promoted approval.
    """

    candidate = _optional_text(metrics.get("candidate"))
    ir_revision = _optional_text(metrics.get("ir_revision"))
    golden_revision = _optional_text(metrics.get("golden_revision"))
    corpus_digest = _optional_text(metrics.get("corpus_digest"))
    environment = _mapping_copy(metrics.get("environment")) or {}
    backends = _role_dict(metrics.get("backends"), default=_empty_roles())
    raw_arm_statuses = metrics.get("arm_statuses")
    if isinstance(raw_arm_statuses, Mapping):
        arm_statuses = _role_dict(raw_arm_statuses, default=_empty_roles("not_run"))
    else:
        # Keep the original flat evaluator seam useful for diagnostics while
        # making the new receipt fail closed. A measured legacy/RAGFlow status
        # without the dual-arm identity and mapping payload is rejected, not
        # approved; an absent or blocked external arm remains not_run.
        ragflow_status = metrics.get("ragflow_status")
        legacy_status = metrics.get("legacy_status")
        if legacy_status not in {"passed", "failed", "blocked", "not_run"}:
            legacy_status = "passed" if ragflow_status in {"passed", "failed"} else "not_run"
        if ragflow_status not in {"passed", "failed", "blocked", "not_run"}:
            ragflow_status = "not_run"
        arm_statuses = {"legacy": legacy_status, "ragflow": ragflow_status}
    arm_identities = _role_dict(metrics.get("arm_identities"), default=_empty_roles())
    arm_metrics = _role_dict(metrics.get("arm_metrics"), default=_empty_roles())
    arm_lifecycles = _role_dict(metrics.get("arm_lifecycles"), default=_empty_roles())
    mappings = _role_dict(metrics.get("mappings"), default=_empty_roles())
    mapping_hashes = _role_dict(metrics.get("mapping_hashes"), default=_empty_roles())
    arm_hashes = _role_dict(metrics.get("arm_hashes"), default=_empty_roles())
    lifecycle = _mapping_copy(metrics.get("lifecycle_detail")) or {
        "queryable": metrics.get("lifecycle") is True,
        "recovery": metrics.get("recovery") is True,
        "rollback": metrics.get("rollback") is True,
    }
    cleanup = _cleanup_status(metrics.get("cleanup"))
    payload = {
        "schema_version": 2,
        "kind": "cutover_decision",
        "status": "not_run",
        "ok": False,
        "legacy_preserved": True,
        "gates": {},
        "blockers": [],
        "candidate": candidate,
        "ir_revision": ir_revision,
        "golden_revision": golden_revision,
        "corpus_digest": corpus_digest,
        "environment": environment,
        "metrics": _decision_metrics(metrics),
        "backends": backends,
        "arm_statuses": arm_statuses,
        "arm_identities": arm_identities,
        "arm_metrics": arm_metrics,
        "arm_lifecycles": arm_lifecycles,
        "mappings": mappings,
        "mapping_hashes": mapping_hashes,
        "arm_hashes": arm_hashes,
        "lifecycle": lifecycle,
        "cleanup": cleanup,
    }
    if not isinstance(metrics.get("arm_hashes"), Mapping):
        # Flat compatibility inputs still receive a deterministic hash of the
        # incomplete arm projections. The hash gate can then validate the
        # receipt, while the missing identities/mappings keep it rejected.
        arm_hashes = _arm_hashes_from_payload(payload)
        payload["arm_hashes"] = arm_hashes
    gates = _derive_gates(payload)
    blockers = [name for name, passed in gates.items() if not passed]
    if any(arm_statuses.get(role) in {"not_run", "blocked"} for role in _ARM_ROLES):
        status = "not_run"
    elif blockers:
        status = "cutover_rejected"
    else:
        status = "cutover_approved"
    payload["status"] = status
    payload["ok"] = status == "cutover_approved"
    payload["gates"] = gates
    payload["blockers"] = blockers
    return CutoverDecision(
        status=status,
        ok=status == "cutover_approved",
        legacy_preserved=True,
        gates=gates,
        blockers=blockers,
        candidate=candidate,
        ir_revision=ir_revision,
        golden_revision=golden_revision,
        corpus_digest=corpus_digest,
        environment=environment,
        metrics=_decision_metrics(metrics),
        backends=backends,
        arm_statuses=arm_statuses,
        arm_identities=arm_identities,
        arm_metrics=arm_metrics,
        arm_lifecycles=arm_lifecycles,
        mappings=mappings,
        mapping_hashes=mapping_hashes,
        arm_hashes=arm_hashes,
        lifecycle=lifecycle,
        cleanup=cleanup,
    )


def build_cutover_receipt(decision: CutoverDecision | Mapping[str, Any]) -> dict[str, Any]:
    """Return a schema-validated cutover receipt, refusing malformed evidence.

    TK-019's contraction guard must consume an artifact, not an inferred in-memory
    flag. Validating the receipt against the canonical ``cutover-decision`` schema
    here means a partial or hand-built payload cannot unlock the destructive
    contraction: a missing gate or a forged ``ok`` fails closed.
    """

    payload = decision.to_dict() if isinstance(decision, CutoverDecision) else dict(decision)
    validation = validate_artifact("cutover-decision", payload)
    if not validation.ok:
        codes = ", ".join(sorted({error["code"] for error in validation.errors}))
        raise RuntimeError(f"cutover receipt does not satisfy the canonical contract: {codes}")
    expected_gates = _derive_gates(payload)
    if payload.get("gates") != expected_gates:
        raise RuntimeError("cutover receipt gates do not match its measured evidence")
    expected_blockers = [name for name, passed in expected_gates.items() if not passed]
    if payload.get("blockers") != expected_blockers:
        raise RuntimeError("cutover receipt blockers do not match its gates")
    expected_status = _decision_status(payload, expected_blockers)
    if payload.get("status") != expected_status:
        raise RuntimeError("cutover receipt status does not match its gates and arm status")
    if payload.get("ok") is not (expected_status == "cutover_approved"):
        raise RuntimeError("cutover receipt ok does not match its status")
    if payload.get("legacy_preserved") is not True:
        raise RuntimeError("cutover receipt must preserve the legacy backend")
    expected_mapping_hashes = _mapping_hashes(payload.get("mappings"))
    if payload.get("mapping_hashes") != expected_mapping_hashes:
        raise RuntimeError("cutover receipt mapping hashes do not match its mappings")
    expected_arm_hashes = _arm_hashes_from_payload(payload)
    if payload.get("arm_hashes") != expected_arm_hashes:
        raise RuntimeError("cutover receipt arm hashes do not match its measured arms")
    expected_receipt_hash = _receipt_hash_for_payload(payload)
    if payload.get("receipt_hash") != expected_receipt_hash:
        raise RuntimeError("cutover receipt hash does not match its canonical payload")
    return payload


def _optional_text(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def cutover_metrics_from_arms(
    legacy: Mapping[str, Any] | None,
    ragflow: Mapping[str, Any] | None,
    *,
    candidate: str | None = None,
    ir_revision: str | None = None,
    golden_revision: str | None = None,
    corpus_digest: str | None = None,
    environment: Mapping[str, Any] | None = None,
    cleanup: str | None = None,
) -> dict[str, Any]:
    """Compose two backend arm reports into ``evaluate_cutover`` input.

    TK-018's acceptance compares the same IR against the legacy backend and
    RAGFlow. This helper is deliberately fail-closed: a missing arm, a
    non-``passed`` RAGFlow arm, or an absent measured metric yields a
    ``ragflow_status`` that cannot be promoted to ``passed``. It never invents
    a metric the arms did not report.
    """

    expected_context = {
        "candidate": candidate,
        "ir_revision": ir_revision,
        "golden_revision": golden_revision,
        "corpus_digest": corpus_digest,
        "environment": dict(environment or {}),
    }
    legacy_status = _arm_status(legacy)
    ragflow_status = _arm_status(ragflow)
    arm_reports = {"legacy": legacy, "ragflow": ragflow}
    metrics: dict[str, Any] = {
        "candidate": candidate,
        "ir_revision": ir_revision,
        "golden_revision": golden_revision,
        "corpus_digest": corpus_digest,
        "environment": dict(environment or {}),
        "cleanup": _cleanup_status(cleanup),
        "legacy_status": legacy_status,
        "ragflow_status": ragflow_status,
        "arm_statuses": {"legacy": legacy_status, "ragflow": ragflow_status},
        "arm_identities": {role: _arm_field(arm, "identity") for role, arm in arm_reports.items()},
        "backends": {role: _arm_field(arm, "backend") for role, arm in arm_reports.items()},
        "arm_metrics": {role: _arm_measurements(arm) for role, arm in arm_reports.items()},
        "arm_lifecycles": {role: _arm_field(arm, "lifecycle") for role, arm in arm_reports.items()},
        "mappings": {role: _arm_field(arm, "mappings") for role, arm in arm_reports.items()},
        "mapping_hashes": {role: _reported_mapping_hash(arm) for role, arm in arm_reports.items()},
        "arm_hashes": {
            role: _arm_hash_for_report(role, arm, status)
            for role, arm, status in (
                ("legacy", legacy, legacy_status),
                ("ragflow", ragflow, ragflow_status),
            )
        },
        "lifecycle_detail": _mapping_copy(ragflow.get("lifecycle")) if isinstance(ragflow, Mapping) else {},
    }
    if not isinstance(legacy, Mapping) or not isinstance(ragflow, Mapping):
        return metrics

    legacy_metrics = _arm_measurements(legacy) or {}
    ragflow_metrics = _arm_measurements(ragflow) or {}
    for key in ("recall_at_5", "mrr_at_5"):
        if key in ragflow_metrics:
            metrics[key] = ragflow_metrics[key]
    for key in ("citation_coverage", "lineage_coverage"):
        if key in ragflow_metrics:
            metrics[key] = ragflow_metrics[key]
    legacy_id_parity = legacy_metrics.get("id_parity")
    ragflow_id_parity = ragflow_metrics.get("id_parity")
    if _is_number(legacy_id_parity) and _is_number(ragflow_id_parity) and legacy_id_parity == ragflow_id_parity:
        metrics["id_parity"] = ragflow_id_parity
    lifecycle = ragflow.get("lifecycle") if isinstance(ragflow.get("lifecycle"), Mapping) else {}
    metrics["lifecycle"] = lifecycle.get("queryable") is True
    metrics["recovery"] = lifecycle.get("recovery") is True
    metrics["rollback"] = lifecycle.get("rollback") is True
    metrics["legacy_arm_valid"] = _arm_projection_valid("legacy", legacy, expected_context)
    metrics["ragflow_arm_valid"] = _arm_projection_valid("ragflow", ragflow, expected_context)
    return metrics


def _empty_roles(value: Any = None) -> dict[str, Any]:
    return {role: value for role in _ARM_ROLES}


def _role_dict(value: Any, *, default: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return dict(default)
    return {role: value.get(role) for role in _ARM_ROLES}


def _mapping_copy(value: Any) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, Mapping) else None


def _arm_field(arm: Any, field: str) -> dict[str, Any] | None:
    return _mapping_copy(arm.get(field)) if isinstance(arm, Mapping) else None


def _arm_metrics(arm: Any) -> dict[str, Any] | None:
    if not isinstance(arm, Mapping):
        return None
    value = arm.get("metrics")
    return dict(value) if isinstance(value, Mapping) else None


def _arm_measurements(arm: Any) -> dict[str, Any] | None:
    """Return the fixed metric projection used by the receipt and arm hash."""

    if not isinstance(arm, Mapping):
        return None
    raw_metrics = _arm_metrics(arm) or {}
    coverage = arm.get("coverage") if isinstance(arm.get("coverage"), Mapping) else {}
    measurements: dict[str, Any] = {}
    for key in _ARM_METRIC_KEYS:
        value = raw_metrics.get(key)
        if key in coverage:
            coverage_value = coverage[key]
            # A report that repeats a metric in two places must agree.  Keeping
            # the projection null on conflict makes the arm fail the gate.
            value = coverage_value if value is None or value == coverage_value else None
        measurements[key] = value
    return measurements


def _reported_mapping_hash(arm: Any) -> str | None:
    if not isinstance(arm, Mapping):
        return None
    value = arm.get("mapping_hash")
    return value if isinstance(value, str) else None


def _arm_status(arm: Any) -> str:
    if not isinstance(arm, Mapping):
        return "not_run"
    status = arm.get("status")
    if status in {"passed", "blocked", "not_run", "failed"}:
        if status == "passed" and arm.get("ok") is not True:
            return "failed"
        return status
    return "failed"


def _cleanup_status(value: Any) -> str:
    return value if value in {"passed", "failed", "not_run", "not_required"} else "not_run"


def _decision_metrics(metrics: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: metrics.get(key)
        for key in ("recall_at_5", "mrr_at_5", "citation_coverage", "lineage_coverage", "id_parity")
    }


def _arm_projection_valid(role: str, arm: Mapping[str, Any], expected_context: Mapping[str, Any]) -> bool:
    if arm.get("ok") is not True or arm.get("status") != "passed":
        return False
    backend = arm.get("backend")
    if not _backend_valid(role, backend):
        return False
    identity = arm.get("identity")
    if not isinstance(identity, Mapping):
        return False
    for key in _IDENTITY_KEYS:
        expected = expected_context.get(key)
        if key == "corpus_digest":
            if not _valid_digest(expected) or identity.get(key) != expected:
                return False
        elif key == "environment":
            if not _valid_environment(expected) or identity.get(key) != expected:
                return False
        elif not _valid_text(expected) or identity.get(key) != expected:
            return False
    mappings = arm.get("mappings")
    if not isinstance(mappings, Mapping) or not mappings:
        return False
    if arm.get("mapping_hash") != content_hash(dict(mappings)):
        return False
    lifecycle = arm.get("lifecycle")
    if not _lifecycle_all_true(lifecycle):
        return False
    arm_metrics = _arm_measurements(arm)
    if not isinstance(arm_metrics, Mapping) or not _exact_one(arm_metrics.get("id_parity")):
        return False
    if role == "ragflow":
        if not _at_least(arm_metrics.get("recall_at_5"), 1.0):
            return False
        if not _at_least(arm_metrics.get("mrr_at_5"), 0.86):
            return False
        if not _at_least(arm_metrics.get("citation_coverage"), 1.0):
            return False
        if not _at_least(arm_metrics.get("lineage_coverage"), 1.0):
            return False
    return True


def _derive_gates(payload: Mapping[str, Any]) -> dict[str, bool]:
    backends = _role_dict(payload.get("backends"), default=_empty_roles())
    arm_statuses = _role_dict(payload.get("arm_statuses"), default=_empty_roles("not_run"))
    arm_identities = _role_dict(payload.get("arm_identities"), default=_empty_roles())
    arm_metrics = _role_dict(payload.get("arm_metrics"), default=_empty_roles())
    arm_lifecycles = _role_dict(payload.get("arm_lifecycles"), default=_empty_roles())
    mappings = _role_dict(payload.get("mappings"), default=_empty_roles())
    mapping_hashes = _role_dict(payload.get("mapping_hashes"), default=_empty_roles())
    arm_hashes = _role_dict(payload.get("arm_hashes"), default=_empty_roles())
    environment = payload.get("environment")
    identity = {
        "candidate": payload.get("candidate"),
        "ir_revision": payload.get("ir_revision"),
        "golden_revision": payload.get("golden_revision"),
        "corpus_digest": payload.get("corpus_digest"),
        "environment": environment,
    }
    arm_identity_ok = {role: _arm_identity_matches(arm_identities.get(role), identity) for role in _ARM_ROLES}
    role_valid = {}
    for role in _ARM_ROLES:
        role_valid[role] = (
            arm_statuses.get(role) == "passed"
            and _backend_valid(role, backends.get(role))
            and arm_identity_ok[role]
            and isinstance(mappings.get(role), Mapping)
            and bool(mappings.get(role))
            and mapping_hashes.get(role) == content_hash(dict(mappings[role]))
            and _lifecycle_all_true(arm_lifecycles.get(role))
            and isinstance(arm_metrics.get(role), Mapping)
            and _exact_one(arm_metrics[role].get("id_parity"))
        )
    ragflow_metrics = arm_metrics.get("ragflow")
    ragflow_valid = role_valid["ragflow"] and (
        isinstance(ragflow_metrics, Mapping)
        and _at_least(ragflow_metrics.get("recall_at_5"), 1.0)
        and _at_least(ragflow_metrics.get("mrr_at_5"), 0.86)
    )
    # The receipt stores the measured coverage in the top-level metrics.  The
    # arm itself remains the source for the arm-validity check.
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), Mapping) else {}
    lifecycle = payload.get("lifecycle")
    legacy_id = _arm_metric(arm_metrics.get("legacy"), "id_parity")
    ragflow_id = _arm_metric(arm_metrics.get("ragflow"), "id_parity")
    gates = {
        "legacy_arm": role_valid["legacy"],
        "ragflow_arm": ragflow_valid
        and _at_least(metrics.get("citation_coverage"), 1.0)
        and _at_least(metrics.get("lineage_coverage"), 1.0),
        "candidate": _valid_text(payload.get("candidate")),
        "ir_revision": _valid_text(payload.get("ir_revision")),
        "golden_revision": _valid_text(payload.get("golden_revision")),
        "corpus_digest": _valid_digest(payload.get("corpus_digest")),
        "environment": _valid_environment(environment) and all(arm_identity_ok.values()),
        "backend": all(_backend_valid(role, backends.get(role)) for role in _ARM_ROLES),
        "mappings": all(
            isinstance(mappings.get(role), Mapping)
            and bool(mappings.get(role))
            and mapping_hashes.get(role) == content_hash(dict(mappings[role]))
            for role in _ARM_ROLES
        ),
        "arm_hashes": arm_hashes == _arm_hashes_from_payload(payload),
        "recall_at_5": _at_least(metrics.get("recall_at_5"), 1.0),
        "mrr_at_5": _at_least(metrics.get("mrr_at_5"), 0.86),
        "citation_coverage": _at_least(metrics.get("citation_coverage"), 1.0),
        "lineage_coverage": _at_least(metrics.get("lineage_coverage"), 1.0),
        "id_parity": _exact_one(metrics.get("id_parity"))
        and _exact_one(legacy_id)
        and _exact_one(ragflow_id)
        and legacy_id == ragflow_id == metrics.get("id_parity"),
        "lifecycle": isinstance(lifecycle, Mapping) and lifecycle.get("queryable") is True,
        "recovery": isinstance(lifecycle, Mapping) and lifecycle.get("recovery") is True,
        "rollback": isinstance(lifecycle, Mapping) and lifecycle.get("rollback") is True,
        "cleanup": payload.get("cleanup") == "passed",
    }
    return gates


def _arm_identity_matches(identity: Any, expected: Mapping[str, Any]) -> bool:
    if not isinstance(identity, Mapping):
        return False
    if set(identity) != set(_IDENTITY_KEYS) or set(expected) != set(_IDENTITY_KEYS):
        return False
    for key in _IDENTITY_KEYS:
        if identity.get(key) != expected.get(key):
            return False
    return True


def _arm_metric(metrics: Any, key: str) -> Any:
    return metrics.get(key) if isinstance(metrics, Mapping) else None


def _backend_valid(role: str, backend: Any) -> bool:
    return isinstance(backend, Mapping) and dict(backend) == _EXPECTED_BACKENDS.get(role)


def _lifecycle_all_true(lifecycle: Any) -> bool:
    return (
        isinstance(lifecycle, Mapping)
        and lifecycle.get("queryable") is True
        and lifecycle.get("recovery") is True
        and lifecycle.get("rollback") is True
    )


def _valid_environment(value: Any) -> bool:
    return (
        isinstance(value, Mapping)
        and set(value) == {"profile", "runtime", "python"}
        and all(_valid_text(value.get(key)) for key in ("profile", "runtime", "python"))
    )


def _valid_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_digest(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _exact_one(value: Any) -> bool:
    return _is_number(value) and float(value) == 1.0


def _mapping_hashes(mappings: Any) -> dict[str, str | None]:
    roles = _role_dict(mappings, default=_empty_roles())
    return {role: content_hash(dict(roles[role])) if isinstance(roles[role], Mapping) else None for role in _ARM_ROLES}


def _canonical_metric_projection(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    return {key: value.get(key) for key in _ARM_METRIC_KEYS}


def _canonical_arm_projection(
    role: str,
    *,
    status: str,
    backend: Any,
    identity: Any,
    metrics: Any,
    lifecycle: Any,
    mappings: Any,
    mapping_hash: Any,
) -> dict[str, Any]:
    return {
        "role": role,
        "status": status,
        "backend": _mapping_copy(backend),
        "identity": _mapping_copy(identity),
        "metrics": _canonical_metric_projection(metrics),
        "lifecycle": _mapping_copy(lifecycle),
        "mappings": _mapping_copy(mappings),
        "mapping_hash": mapping_hash if isinstance(mapping_hash, str) else None,
    }


def _arm_hash_for_report(role: str, arm: Any, status: str) -> str:
    return content_hash(
        _canonical_arm_projection(
            role,
            status=status,
            backend=_arm_field(arm, "backend"),
            identity=_arm_field(arm, "identity"),
            metrics=_arm_measurements(arm),
            lifecycle=_arm_field(arm, "lifecycle"),
            mappings=_arm_field(arm, "mappings"),
            mapping_hash=_reported_mapping_hash(arm),
        )
    )


def _arm_hashes_from_payload(payload: Mapping[str, Any]) -> dict[str, str]:
    statuses = _role_dict(payload.get("arm_statuses"), default=_empty_roles("not_run"))
    backends = _role_dict(payload.get("backends"), default=_empty_roles())
    identities = _role_dict(payload.get("arm_identities"), default=_empty_roles())
    metrics = _role_dict(payload.get("arm_metrics"), default=_empty_roles())
    lifecycles = _role_dict(payload.get("arm_lifecycles"), default=_empty_roles())
    mappings = _role_dict(payload.get("mappings"), default=_empty_roles())
    mapping_hashes = _role_dict(payload.get("mapping_hashes"), default=_empty_roles())
    return {
        role: content_hash(
            _canonical_arm_projection(
                role,
                status=statuses.get(role) if isinstance(statuses.get(role), str) else "not_run",
                backend=backends.get(role),
                identity=identities.get(role),
                metrics=metrics.get(role),
                lifecycle=lifecycles.get(role),
                mappings=mappings.get(role),
                mapping_hash=mapping_hashes.get(role),
            )
        )
        for role in _ARM_ROLES
    }


def _receipt_hash_for_payload(payload: Mapping[str, Any]) -> str:
    projection = {key: payload.get(key) for key in _RECEIPT_FIELDS}
    return content_hash(projection)


def _decision_status(payload: Mapping[str, Any], blockers: list[str]) -> str:
    statuses = _role_dict(payload.get("arm_statuses"), default=_empty_roles("not_run"))
    if any(statuses.get(role) in {"not_run", "blocked"} for role in _ARM_ROLES):
        return "not_run"
    return "cutover_approved" if not blockers else "cutover_rejected"


def _context_matches(payload: Mapping[str, Any], expected_context: Mapping[str, Any]) -> bool:
    if not isinstance(expected_context, Mapping):
        return False
    return all(payload.get(key) == expected_context.get(key) for key in _CONTEXT_FIELDS)


def _at_least(value: Any, threshold: float) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and float(value) >= threshold
