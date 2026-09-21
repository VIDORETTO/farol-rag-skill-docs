"""Deterministic validation of the package produced by the operator."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config_audit import audit_config_file
from .contracts import validate_artifact
from .divergence import inspect_package_divergence
from .observability import redact_report
from .readiness import READINESS_ORDER, assess_readiness
from .revisions import package_revisions


@dataclass
class ValidationResult:
    """Result of validating a knowledge package."""

    ok: bool
    errors: list[dict[str, str]] = field(default_factory=list)
    warnings: list[dict[str, str]] = field(default_factory=list)
    checks: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return redact_report(
            {
                "schema_version": 1,
                "ok": self.ok,
                "errors": self.errors,
                "warnings": self.warnings,
                "checks": self.checks,
            }
        )


def _error(errors: list[dict[str, str]], code: str, message: str) -> None:
    errors.append({"code": code, "message": message})


def _safe_relative(root: Path, raw: Any, errors: list[dict[str, str]], code: str) -> Path | None:
    if not isinstance(raw, str) or not raw.strip():
        _error(errors, code, "artifact path must be a non-empty relative string")
        return None
    candidate = Path(raw.replace("\\", "/"))
    if candidate.is_absolute() or re.match(r"^[A-Za-z]:", raw.replace("\\", "/")) or ".." in candidate.parts:
        _error(errors, code, f"artifact path must remain inside package: {raw!r}")
        return None
    current = root
    for part in candidate.parts:
        current = current / part
        if current.is_symlink():
            _error(errors, "symlink_artifact", "artifact path must be a regular package path")
            return None
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        _error(errors, code, f"artifact path escapes package: {raw!r}")
        return None
    return resolved


def _reject_nested_symlinks(root: Path, directory: Path, errors: list[dict[str, str]]) -> None:
    """Reject links anywhere inside a package artifact directory."""

    if not directory.is_dir() or directory.is_symlink():
        return
    for path in directory.rglob("*"):
        if path.is_symlink():
            _error(
                errors,
                "symlink_artifact",
                f"package artifact must be a regular file or directory: {path.relative_to(root).as_posix()}",
            )


def _frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    fields: dict[str, str] = {}
    for line in text[3:end].splitlines():
        match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*)\s*:\s*(.*?)\s*$", line)
        if match:
            fields[match.group(1)] = match.group(2).strip("\"'")
    return fields


def validate_package(package_root: Path | str) -> ValidationResult:
    """Validate skill, router, RAG metadata, manifest and provenance.

    The checks use only files and JSON metadata. They never start an external
    server, download a model, execute a skill, or call an LLM.
    """

    root = Path(os.path.abspath(os.fspath(Path(package_root).expanduser())))
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    checks: dict[str, dict[str, Any]] = {}
    if root.is_symlink():
        return ValidationResult(
            False,
            [{"code": "symlink_artifact", "message": "package root must not be a symbolic link"}],
            [],
            {"root": {"ok": False, "reason": "symlink_artifact"}},
        )
    manifest_path = root / "manifest.json"
    manifest: dict[str, Any] = {}

    if manifest_path.is_symlink():
        _error(errors, "symlink_artifact", "manifest.json must be a regular file")
    elif not manifest_path.is_file():
        _error(errors, "missing_manifest", "manifest.json is required")
    else:
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            _error(errors, "invalid_manifest", f"could not read manifest.json: {exc}")
        else:
            if isinstance(loaded, dict):
                manifest = loaded
            else:
                _error(errors, "invalid_manifest", "manifest.json must contain an object")

    # Packages produced by the current operator carry the complete public
    # manifest envelope.  Validate that envelope through the same normative
    # contract used by callers.  A small legacy compatibility path remains for
    # hand-written 1.0 fixture packages that predate the complete envelope.
    if manifest and "contract_version" in manifest:
        contract = validate_artifact("manifest", manifest)
        checks["contract"] = contract.to_dict()
        for contract_error in contract.errors:
            _error(
                errors,
                contract_error["code"],
                f"manifest contract {contract_error.get('path', '$')}: {contract_error['message']}",
            )

    if manifest.get("schema_version") != 1:
        _error(errors, "manifest_schema", "manifest schema_version must be 1")
    if not isinstance(manifest.get("run_id"), str) or not manifest["run_id"].strip():
        _error(errors, "manifest_run_id", "manifest run_id is required")
    outcome = manifest.get("outcome")
    if isinstance(outcome, dict):
        if outcome.get("status") != manifest.get("status"):
            _error(errors, "outcome_status_mismatch", "manifest status and terminal outcome status must agree")
        if outcome.get("status") == "succeeded" and outcome.get("exit_code") != 0:
            _error(errors, "outcome_exit_code_mismatch", "a succeeded outcome must have exit_code=0")
    validation_payload = manifest.get("validation")
    if isinstance(validation_payload, dict) and isinstance(validation_payload.get("ok"), bool):
        expected_ok = manifest.get("status") == "succeeded"
        if validation_payload["ok"] != expected_ok:
            _error(errors, "manifest_validation_mismatch", "manifest status and validation.ok must agree")

    source = manifest.get("source")
    if not isinstance(source, dict) or not source.get("canonical") or not source.get("input"):
        _error(errors, "source_provenance", "source.input and source.canonical are required")
    provenance = manifest.get("provenance")
    if not isinstance(provenance, dict) or not provenance.get("license"):
        _error(errors, "license_provenance", "provenance.license is required")
    elif provenance.get("redistribution") == "public" and str(provenance.get("license")).casefold() == "unknown":
        _error(errors, "license_required", "public packages require a declared source license")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        _error(errors, "artifact_map", "manifest artifacts must map skill, router and rag")
        artifacts = {}

    paths: dict[str, Path] = {}
    for name in ("skill", "router", "rag"):
        path = _safe_relative(root, artifacts.get(name), errors, f"{name}_path")
        if path is not None:
            paths[name] = path
            _reject_nested_symlinks(root, path, errors)

    harness_config_target: Path | None = None
    config_targets: list[Path] = []
    if "harness" in artifacts:
        harness_path = _safe_relative(root, artifacts.get("harness"), errors, "harness_path")
        if harness_path is not None and not harness_path.is_file():
            _error(errors, "missing_harness_manifest", "manifest harness artifact does not exist")
        elif harness_path is not None:
            try:
                harness = json.loads(harness_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                _error(errors, "invalid_harness_manifest", f"could not read harness manifest: {exc}")
            else:
                if not isinstance(harness, dict) or harness.get("schema_version") != 1:
                    _error(errors, "harness_schema", "harness manifest schema_version must be 1")
                elif (
                    harness.get("package_root") != "."
                    or not isinstance(harness.get("backend"), dict)
                    or harness["backend"].get("cwd") != "."
                ):
                    _error(errors, "harness_paths", "harness manifest must use relative package paths")
                else:
                    harness_config_target = _safe_relative(
                        root, harness["backend"].get("config"), errors, "harness_config_path"
                    )
                    if harness_config_target is not None and not harness_config_target.is_file():
                        _error(errors, "missing_config", "harness backend config does not exist in the package")
                    elif harness_config_target is not None:
                        config_targets.append(harness_config_target)

    config_artifact = artifacts.get("config")
    if config_artifact is not None:
        config_target = _safe_relative(root, config_artifact, errors, "config_path")
        if config_target is not None and not config_target.is_file():
            _error(errors, "missing_config", "manifest config artifact does not exist")
        elif config_target is not None:
            config_targets.append(config_target)

    skill_dir = paths.get("skill")
    skill_file = skill_dir / "SKILL.md" if skill_dir else None
    if skill_file and skill_file.is_symlink():
        pass
    elif not skill_file or not skill_file.is_file():
        _error(errors, "missing_skill", "skill/SKILL.md (or the manifest skill path) is required")
    else:
        fields = _frontmatter(skill_file)
        checks["skill"] = {"ok": True, "path": "skill/SKILL.md", "name": fields.get("name")}
        if not fields.get("name") or not fields.get("description"):
            _error(errors, "skill_frontmatter", "skill SKILL.md needs name and description frontmatter")

    router_dir = paths.get("router")
    router_file = router_dir / "SKILL.md" if router_dir else None
    if router_file and router_file.is_symlink():
        pass
    elif not router_file or not router_file.is_file():
        _error(errors, "missing_router", "router/SKILL.md (or the manifest router path) is required")
    else:
        router_text = router_file.read_text(encoding="utf-8", errors="replace")
        checks["router"] = {"ok": True, "path": "router/SKILL.md"}
        if "search_knowledge" not in router_text:
            _error(errors, "router_rag_reference", "router must reference search_knowledge")
        if not re.search(r"cit(?:e|ation)", router_text, re.IGNORECASE):
            _error(errors, "router_citation_rule", "router must state a citation rule")
        if skill_file and skill_file.is_file():
            skill_name = _frontmatter(skill_file).get("name", "")
            if skill_name and skill_name not in router_text:
                _error(errors, "router_skill_reference", "router must reference the generated skill name")

    rag_dir = paths.get("rag")
    rag_docs = rag_dir / "documents" if rag_dir else None
    rag_index = rag_dir / "index.json" if rag_dir else None
    if not rag_dir or not rag_dir.is_dir():
        _error(errors, "missing_rag", "rag artifact directory is required")
    elif rag_docs and rag_docs.is_symlink():
        pass
    elif not rag_docs or not rag_docs.is_dir():
        _error(errors, "missing_rag_documents", "rag/documents directory is required")
    elif rag_index and rag_index.is_symlink():
        pass
    elif not rag_index or not rag_index.is_file():
        _error(errors, "missing_rag_index", "rag/index.json readiness metadata is required")
    else:
        try:
            index = json.loads(rag_index.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            _error(errors, "invalid_rag_index", f"could not read rag/index.json: {exc}")
        else:
            if not isinstance(index, dict) or index.get("status") != "ready":
                _error(errors, "rag_not_ready", "rag/index.json must have status=ready")
            else:
                docs = list(rag_docs.rglob("*"))
                symlinks = [path for path in docs if path.is_symlink()]
                for path in symlinks:
                    _error(
                        errors,
                        "symlink_artifact",
                        f"RAG document must be a regular file: {path.relative_to(root).as_posix()}",
                    )
                file_count = sum(1 for path in docs if path.is_file() and not path.is_symlink())
                if file_count < 1:
                    _error(errors, "empty_rag", "rag/documents must contain at least one source")
                metric_names = {
                    "corpus_documents",
                    "operator_chunks",
                    "backend_total_documents",
                    "backend_total_chunks",
                }
                uses_named_metrics = "corpus_documents" in index or isinstance(index.get("metrics"), dict)
                if uses_named_metrics:
                    metrics = index.get("metrics") if isinstance(index.get("metrics"), dict) else {}
                    for name in metric_names:
                        if name not in index or name not in metrics or index[name] != metrics[name]:
                            _error(
                                errors,
                                "rag_metrics_invalid",
                                f"rag/index.json metric is missing or inconsistent: {name}",
                            )
                    if index.get("corpus_documents") != file_count:
                        _error(
                            errors, "rag_document_count", "rag/index.json corpus_documents does not match rag/documents"
                        )
                    if (
                        isinstance(index.get("corpus_documents"), bool)
                        or not isinstance(index.get("corpus_documents"), int)
                        or index["corpus_documents"] < 1
                    ):
                        _error(errors, "rag_document_count_invalid", "rag/index.json corpus_documents must be positive")
                    if (
                        isinstance(index.get("operator_chunks"), bool)
                        or not isinstance(index.get("operator_chunks"), int)
                        or index["operator_chunks"] < 1
                    ):
                        _error(errors, "rag_operator_chunks_invalid", "rag/index.json operator_chunks must be positive")
                    for name in ("backend_total_documents", "backend_total_chunks"):
                        value = index.get(name)
                        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                            _error(
                                errors,
                                "rag_backend_metric_invalid",
                                f"rag/index.json {name} must be a non-negative integer or null",
                            )
                    if "chunks" in index or "documents" in index:
                        _error(
                            errors, "rag_ambiguous_metrics", "named RAG metrics must not use legacy ambiguous aliases"
                        )
                    rag_documents_count = index.get("corpus_documents")
                    rag_operator_chunks = index.get("operator_chunks")
                else:
                    rag_documents_count = index.get("documents", file_count)
                    rag_operator_chunks = index.get("chunks", 0)
                checks["rag"] = {
                    "ok": file_count > 0,
                    "path": "rag",
                    "corpus_documents": rag_documents_count,
                    "operator_chunks": rag_operator_chunks,
                    "backend_total_documents": index.get("backend_total_documents"),
                    "backend_total_chunks": index.get("backend_total_chunks"),
                }
                if (
                    not uses_named_metrics
                    and isinstance(index.get("documents"), int)
                    and index["documents"] != file_count
                ):
                    _error(errors, "rag_document_count", "rag/index.json documents count does not match rag/documents")
                if isinstance(manifest.get("entries"), list) and not (rag_dir / "sources.json").is_file():
                    _error(errors, "missing_sources_manifest", "rag/sources.json is required for generated packages")

    manifest_entries = manifest.get("entries")
    if isinstance(manifest_entries, list):
        accepted_entries = [
            entry for entry in manifest_entries if isinstance(entry, dict) and entry.get("status") == "accepted"
        ]
        identities = [
            (str(entry.get("canonical")), str(entry.get("version") or manifest.get("source", {}).get("version") or ""))
            for entry in accepted_entries
        ]
        if len(identities) != len(set(identities)):
            _error(errors, "duplicate_source", "manifest contains duplicate canonical source/version entries")
        rag_documents = root / "rag" / "documents"
        if rag_documents.is_dir() and accepted_entries:
            file_count = sum(1 for path in rag_documents.rglob("*") if path.is_file())
            if file_count != len(accepted_entries):
                _error(errors, "manifest_document_count", "accepted manifest entries do not match rag/documents")

    checks["manifest"] = {"ok": not any(error["code"].startswith("manifest") for error in errors)}
    declared_revisions = manifest.get("revisions")
    if isinstance(declared_revisions, dict):
        golden_revision = declared_revisions.get("golden_revision")
        observed_revisions = package_revisions(
            root, golden_revision=golden_revision if isinstance(golden_revision, str) else None
        )
        revision_keys = {
            "corpus_revision",
            "index_revision",
            "skill_revision",
            "router_revision",
            "policy_revision",
            "golden_revision",
            "composition_hash",
            "release_id",
        }
        mismatches = sorted(key for key in revision_keys if declared_revisions.get(key) != observed_revisions.get(key))
        checks["revisions"] = {"ok": not mismatches, "mismatches": mismatches}
        if mismatches:
            _error(errors, "revision_mismatch", "manifest revision evidence does not match package content")
    if not config_targets:
        config_targets = [root / "config.yaml"]
    unique_config_targets = list(dict.fromkeys(config_targets))
    config_results: list[tuple[Path, Any]] = []
    for config_path in unique_config_targets:
        if config_path.is_symlink():
            _error(errors, "symlink_artifact", "referenced backend config must be a regular file")
        elif config_path.is_file():
            config_result = audit_config_file(config_path)
            config_results.append((config_path, config_result))
            for error in config_result.errors:
                _error(errors, error["code"], error["message"])
    if config_results:
        if len(config_results) == 1:
            checks["config"] = config_results[0][1].to_dict()
        else:
            checks["config"] = {
                "schema_version": 1,
                "ok": all(result.ok for _, result in config_results),
                "transport": "multiple",
                "errors": [error for _, result in config_results for error in result.errors],
                "warnings": [warning for _, result in config_results for warning in result.warnings],
                "paths": [path.relative_to(root).as_posix() for path, _ in config_results],
            }
    divergence = inspect_package_divergence(root)
    checks["synchronization"] = divergence.to_dict()
    for warning in divergence.warnings:
        _error(errors, warning["code"], warning["message"])
    declared_readiness = manifest.get("readiness")
    if isinstance(declared_readiness, dict):
        derived_readiness = assess_readiness(root)
        checks["readiness"] = derived_readiness
        for field_name in ("state", "skill", "rag"):
            declared = declared_readiness.get(field_name)
            derived = derived_readiness.get(field_name)
            if isinstance(declared, str) and isinstance(derived, str):
                if READINESS_ORDER.get(declared, -1) > READINESS_ORDER.get(derived, -1):
                    _error(
                        errors,
                        "readiness_overclaim",
                        f"manifest readiness.{field_name} claims {declared!r} without matching evidence",
                    )
                elif READINESS_ORDER.get(declared, -1) < READINESS_ORDER.get(derived, -1):
                    warnings.append(
                        {
                            "code": "readiness_stale",
                            "message": f"manifest readiness.{field_name} is behind observed evidence",
                        }
                    )
    result = ValidationResult(not errors, errors, warnings, checks)
    contract = validate_artifact("validation", result.to_dict())
    if not contract.ok:
        result.errors.extend(
            {
                "code": error["code"],
                "message": f"validation contract {error.get('path', '$')}: {error['message']}",
            }
            for error in contract.errors
        )
        result.ok = False
    result.checks.setdefault("validation_contract", contract.to_dict())
    return result
