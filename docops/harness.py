"""Portable hand-off metadata for external Agent Skills and RAGFlow."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any, Mapping

from .contracts import validate_artifact
from .revisions import package_revisions, tree_hash
from .storage import write_json_atomic


def build_harness_manifest(package_root: Path | str) -> dict[str, Any]:
    """Describe how a harness can load artifacts without author paths."""

    root = Path(package_root).resolve()
    revisions = package_revisions(root)
    generation = {
        "schema_version": 1,
        "release_id": str(revisions["release_id"]),
        "composition_hash": str(revisions["composition_hash"]),
        "corpus_revision": str(revisions["corpus_revision"]),
        "index_revision": str(revisions["index_revision"]),
        "skill_revision": str(revisions["skill_revision"]),
        "router_revision": str(revisions["router_revision"]),
        "policy_revision": str(revisions["policy_revision"]),
    }
    payload = {
        "schema_version": 1,
        "package_root": ".",
        "generation": generation,
        "skills": ["skill", "router"],
        "operator_skill": {"name": "docops-agent", "discovery": "docops skill path"},
        "backend": {
            "name": "ragflow",
            "version": "0.27.2",
            "adapter": "docops.backends.ragflow.RagFlowAdapter",
            "transport": "https-or-loopback-development",
            "cwd": ".",
            "config": "config.yaml",
            "capabilities": ["probe", "prepare", "apply", "query", "snapshot", "discard", "close"],
            "external": True,
        },
        "notes": [
            "Pin the reader to generation.release_id and reopen it if the package composition changes.",
            "Resolve command=python through the clone's prepared environment on the target machine.",
            "Copy or mount skill/ and router/ into the harness skill directory; the package never selects a model.",
            f"Generated for package basename {root.name!r}; no absolute path is persisted.",
        ],
    }
    contract = validate_artifact("harness", payload)
    if not contract.ok:
        details = "; ".join(f"{error.get('path', '$')}: {error['message']}" for error in contract.errors)
        raise RuntimeError(f"generated harness contract is invalid: {details}")
    return payload


def write_harness_manifest(package_root: Path | str) -> Path:
    """Write the portable hand-off file and return its path."""

    root = Path(package_root).resolve()
    path = root / "harness.json"
    write_json_atomic(path, build_harness_manifest(root))
    return path


def read_harness_manifest(path: Path | str) -> dict[str, Any]:
    """Read and minimally validate a hand-off file."""

    value = json.loads(Path(path).read_text(encoding="utf-8"))
    contract = validate_artifact("harness", value)
    if not contract.ok:
        details = "; ".join(f"{error.get('path', '$')}: {error['message']}" for error in contract.errors)
        raise ValueError(f"invalid harness contract: {details}")
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("unsupported harness manifest")
    generation = value.get("generation")
    if not isinstance(generation, Mapping):
        raise ValueError("harness generation is required")
    generation_fields = (
        "release_id",
        "composition_hash",
        "corpus_revision",
        "index_revision",
        "skill_revision",
        "router_revision",
        "policy_revision",
    )
    if generation.get("schema_version") != 1 or any(
        not isinstance(generation.get(field), str) or not generation[field] for field in generation_fields
    ):
        raise ValueError("harness generation is invalid")
    operator_skill = value.get("operator_skill")
    if operator_skill != {"name": "docops-agent", "discovery": "docops skill path"}:
        raise ValueError("harness operator skill is invalid")
    backend = value.get("backend")
    if not isinstance(backend, Mapping) or backend.get("name") != "ragflow" or backend.get("cwd") != ".":
        raise ValueError("harness RAGFlow backend configuration is invalid")
    if backend.get("version") != "0.27.2" or backend.get("config") != "config.yaml":
        raise ValueError("harness RAGFlow backend version/configuration is invalid")
    try:
        current = package_revisions(Path(path).resolve().parent)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise ValueError("harness generation could not be checked") from exc
    for field in generation_fields:
        if str(current.get(field)) != str(generation.get(field)):
            raise ValueError("harness generation does not match package")
    capabilities = backend.get("capabilities", [])
    if not isinstance(capabilities, list) or any(not isinstance(item, str) for item in capabilities):
        raise ValueError("harness backend capabilities must be a string array")
    return value


def _raw_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _read_object(path: Path, description: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{description} must be a regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{description} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{description} must be a JSON object")
    return value


def export_enrichment_request(
    package_root: Path | str,
    candidate_id: str,
    *,
    language: str | None = None,
    budget: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Freeze a candidate hand-off for an external enrichment harness.

    The request is portable: it contains only candidate identities, relative
    artifact roots and hashes. It never stores an absolute checkout path or
    model credentials.
    """

    from .candidates import CandidateError, candidate_path

    try:
        root = candidate_path(package_root, candidate_id)
    except CandidateError as exc:
        raise ValueError(str(exc)) from exc
    if root.is_symlink() or not root.is_dir():
        raise ValueError("candidate must be a regular directory")

    metadata = root / ".docops"
    candidate_receipt_path = metadata / "candidate.json"
    candidate_receipt = _read_object(candidate_receipt_path, "candidate receipt")
    if candidate_receipt.get("candidate_id") != candidate_id:
        raise ValueError("candidate receipt does not match candidate id")
    manifest = _read_object(root / "manifest.json", "candidate manifest")
    declared_revisions = candidate_receipt.get("revisions")
    if not isinstance(declared_revisions, Mapping):
        raise ValueError("candidate receipt has no revision evidence")
    current_revisions = package_revisions(
        root,
        golden_revision=str(declared_revisions.get("golden_revision", "unknown")),
    )
    expected_composition = declared_revisions.get("composition_hash")
    if current_revisions.get("composition_hash") != expected_composition:
        raise ValueError("candidate_changed_before_enrichment_request")

    request_path = metadata / "enrichment-request.json"
    if request_path.is_file() and not request_path.is_symlink():
        existing = _read_object(request_path, "enrichment request")
        existing_contract = validate_artifact("enrichment-request", existing)
        if existing_contract.ok and (
            existing.get("candidate_id") == candidate_id
            and existing.get("snapshot", {}).get("candidate_revisions", {}).get("composition_hash")
            == current_revisions.get("composition_hash")
        ):
            return existing

    source = manifest.get("source")
    source_language = source.get("language") if isinstance(source, Mapping) else None
    resolved_language = language or (source_language if isinstance(source_language, str) else None) or "unknown"
    base_release_id = candidate_receipt.get("base_release_id")
    base_composition_hash = candidate_receipt.get("base_composition_hash")
    if not isinstance(base_release_id, str) or not base_release_id:
        raise ValueError("candidate receipt has no base release id")
    if not isinstance(base_composition_hash, str) or not base_composition_hash:
        raise ValueError("candidate receipt has no base composition hash")

    payload: dict[str, Any] = {
        "schema_version": 1,
        "request_id": f"enrichment-request-{uuid.uuid4().hex}",
        "candidate_id": candidate_id,
        "base_release_id": base_release_id,
        "base_composition_hash": base_composition_hash,
        "snapshot": {
            "candidate_revisions": dict(current_revisions),
            "input_hashes": {
                "skill": tree_hash(root / "skill"),
                "router": tree_hash(root / "router"),
            },
        },
        "diff": {
            "kind": "conceptual_enrichment",
            "layers": ["conceptual"],
        },
        "allowed_artifacts": ["skill", "router"],
        "policy_revision": str(current_revisions["policy_revision"]),
        "language": resolved_language,
        "budget": dict(
            budget
            or {
                "max_files": 128,
                "max_bytes": 2_000_000,
            }
        ),
    }
    contract = validate_artifact("enrichment-request", payload)
    if not contract.ok:
        details = "; ".join(error["message"] for error in contract.errors)
        raise ValueError(f"enrichment request violates its contract: {details}")
    write_json_atomic(request_path, payload)

    candidate_receipt["status"] = "awaiting_enrichment"
    candidate_receipt["enrichment_request_id"] = payload["request_id"]
    candidate_receipt["enrichment_request"] = ".docops/enrichment-request.json"
    write_json_atomic(candidate_receipt_path, candidate_receipt)
    return payload
