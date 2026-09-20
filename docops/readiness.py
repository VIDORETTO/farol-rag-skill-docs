"""Evidence-based capability and package readiness assessment."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .observability import redact_report, redact_text
from .revisions import evidence_matches_package, package_revisions
from .storage import write_json_atomic

READINESS_ORDER = {
    "not-ready": 0,
    "scaffold-ready": 1,
    "skill-enriched": 2,
    "corpus-ready": 3,
    "indexed": 4,
    "evaluated": 5,
    "release-ready": 6,
}


def _digest_tree(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists() or root.is_symlink():
        return digest.hexdigest()
    for path in sorted(root.rglob("*")):
        if path.is_dir() or path.is_symlink():
            continue
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        try:
            digest.update(path.read_bytes())
        except OSError:
            digest.update(b"<unreadable>")
    return digest.hexdigest()


def skill_fingerprint(package_root: Path | str) -> str:
    return _digest_tree(Path(package_root).resolve() / "skill")


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _enrichment_evidence(root: Path) -> dict[str, Any] | None:
    evidence = _read_json(root / ".docops" / "skill-enrichment.json")
    if not evidence:
        return None
    if evidence.get("schema_version") != 1 or not evidence.get("tool") or not evidence.get("version"):
        return None
    if evidence.get("validated") is not True or evidence.get("skill_hash") != skill_fingerprint(root):
        return None
    return evidence


def _mcp_evaluation_evidence(evidence: Mapping[str, Any] | None) -> bool:
    """Return whether evaluation evidence came from the real release backend."""

    return bool(
        evidence
        and evidence.get("ok") is True
        and evidence.get("adapter") == "mcp"
        and evidence.get("backend") in {"ragflow", "memory"}
        and evidence.get("mode") == "gate"
    )


def assess_readiness(package_root: Path | str) -> dict[str, Any]:
    """Recompute readiness from package files and signed-by-content evidence."""

    root = Path(package_root).resolve()
    skill_file = root / "skill" / "SKILL.md"
    scaffold = skill_file.is_file() and (root / "router" / "SKILL.md").is_file()
    enrichment = _enrichment_evidence(root) if scaffold else None
    skill_state = "skill-enriched" if enrichment else "scaffold-ready" if scaffold else "not-ready"
    enrichment_state = "skill-enriched" if enrichment else "awaiting_enrichment" if scaffold else "not-ready"
    index = _read_json(root / "rag" / "index.json")
    documents = root / "rag" / "documents"
    corpus_ready = bool(
        index
        and index.get("status") == "ready"
        and documents.is_dir()
        and any(path.is_file() and not path.is_symlink() for path in documents.rglob("*"))
    )
    rag_state = (
        "indexed"
        if corpus_ready and index.get("mode") == "indexed"
        else "corpus-ready"
        if corpus_ready
        else "not-ready"
    )
    evaluation = _read_json(root / ".docops" / "evaluation.json")
    evaluation_status = "absent"
    if evaluation and evaluation.get("schema_version") == 1 and evaluation.get("ok") is True:
        _matches, evaluation_status = evidence_matches_package(root, evaluation)
    elif evaluation:
        evaluation_status = "invalidated"
    evaluated = bool(
        evaluation
        and evaluation.get("schema_version") == 1
        and evaluation.get("ok") is True
        and evaluation_status == "valid"
    )
    release_evidence = _read_json(root / ".docops" / "release-evidence.json")
    release_ready = bool(
        release_evidence
        and release_evidence.get("schema_version") == 1
        and release_evidence.get("validated") is True
        and evaluated
        and _mcp_evaluation_evidence(evaluation)
        and enrichment
    )
    if release_ready:
        state = "release-ready"
    elif evaluated:
        state = "evaluated"
    elif rag_state == "indexed":
        state = "indexed"
    elif corpus_ready:
        state = "corpus-ready"
    elif enrichment:
        state = "skill-enriched"
    elif scaffold:
        state = "scaffold-ready"
    else:
        state = "not-ready"
    return {
        "schema_version": 1,
        "state": state,
        "skill": skill_state,
        "enrichment": enrichment_state,
        "rag": rag_state,
        "evaluation": "evaluated" if evaluated else "pending",
        "evaluation_status": evaluation_status,
        "release": "release-ready" if release_ready else "pending",
        "evidence": {
            "skill": "skill/SKILL.md" if scaffold else None,
            "enrichment_request": (
                ".docops/enrichment-request.json"
                if (root / ".docops" / "enrichment-request.json").is_file()
                and not (root / ".docops" / "enrichment-request.json").is_symlink()
                else None
            ),
            "skill_enrichment": ".docops/skill-enrichment.json" if enrichment else None,
            "rag_index": "rag/index.json" if corpus_ready else None,
            "evaluation": ".docops/evaluation.json" if evaluated else None,
            "release": ".docops/release-evidence.json" if release_ready else None,
        },
    }


def record_skill_enrichment(
    package_root: Path | str,
    *,
    tool: str,
    version: str,
    validated: bool = True,
    provenance: Mapping[str, Any] | None = None,
    artifacts: list[str] | None = None,
) -> Path:
    """Record an external fold-in only after its resulting skill is present."""

    if not tool.strip() or not version.strip():
        raise ValueError("skill enrichment requires tool and version")
    root = Path(package_root).resolve()
    skill_path = root / "skill" / "SKILL.md"
    if not skill_path.is_file():
        raise ValueError("skill/SKILL.md is required before enrichment")
    if "structural scaffold contains headings and provenance only" in skill_path.read_text(
        encoding="utf-8", errors="replace"
    ):
        raise ValueError("structural scaffold must be enriched before evidence is recorded")
    safe_tool = redact_text(tool)
    safe_version = redact_text(version)
    safe_artifacts = redact_report(sorted(artifacts or ["skill/SKILL.md"]))
    safe_provenance = redact_report(dict(provenance or {}))
    path = root / ".docops" / "skill-enrichment.json"
    payload = {
        "schema_version": 1,
        "tool": safe_tool,
        "version": safe_version,
        "validated": bool(validated),
        "skill_hash": skill_fingerprint(root),
        "artifacts": safe_artifacts,
        "provenance": safe_provenance,
    }
    write_json_atomic(path, payload)
    manifest_path = root / "manifest.json"
    if manifest_path.is_file() and not manifest_path.is_symlink():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            manifest = None
        if isinstance(manifest, dict):
            manifest["readiness"] = assess_readiness(root)
            previous_revisions = manifest.get("revisions")
            previous_golden = (
                previous_revisions.get("golden_revision")
                if isinstance(previous_revisions, Mapping)
                and isinstance(previous_revisions.get("golden_revision"), str)
                else None
            )
            manifest["revisions"] = package_revisions(root, golden_revision=previous_golden)
            provenance_value = manifest.setdefault("provenance", {})
            if isinstance(provenance_value, dict):
                provenance_value["skill_enrichment"] = {
                    "tool": safe_tool,
                    "version": safe_version,
                    "validated": bool(validated),
                    "artifacts": safe_artifacts,
                }
            write_json_atomic(manifest_path, manifest)
    return path


def record_release_evidence(
    package_root: Path | str,
    *,
    version: str,
    gates: Mapping[str, Any],
    provenance: Mapping[str, Any] | None = None,
) -> Path:
    """Record a release gate only after observed package capabilities are ready."""

    if not version.strip():
        raise ValueError("release evidence requires a version")
    root = Path(package_root).resolve()
    observed = assess_readiness(root)
    if observed.get("skill") != "skill-enriched":
        raise ValueError("release evidence requires skill-enriched readiness")
    if observed.get("evaluation") != "evaluated":
        raise ValueError("release evidence requires a passing evaluation")
    evaluation_evidence = _read_json(root / ".docops" / "evaluation.json")
    if not _mcp_evaluation_evidence(evaluation_evidence):
        raise ValueError("release evidence requires a passing RAGFlow evaluation")
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ValueError("release evidence requires a package manifest")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("release evidence requires a readable package manifest") from exc
    validation = manifest.get("validation") if isinstance(manifest, dict) else None
    if not isinstance(manifest, dict) or not isinstance(validation, dict) or validation.get("ok") is not True:
        raise ValueError("release evidence requires a validated package")
    if not isinstance(gates, Mapping) or not gates or any(value is not True for value in gates.values()):
        raise ValueError("release evidence gates must be non-empty and all true")
    safe_version = redact_text(version)
    safe_gates = redact_report(dict(gates))
    safe_provenance = redact_report(dict(provenance or {}))
    path = root / ".docops" / "release-evidence.json"
    payload = {
        "schema_version": 1,
        "validated": True,
        "version": safe_version,
        "gates": safe_gates,
        "skill_hash": skill_fingerprint(root),
        "evaluation": ".docops/evaluation.json",
        "provenance": safe_provenance,
    }
    write_json_atomic(path, payload)
    manifest["readiness"] = assess_readiness(root)
    manifest_provenance = manifest.setdefault("provenance", {})
    if isinstance(manifest_provenance, dict):
        manifest_provenance["release"] = {"version": safe_version, "gates": safe_gates}
    write_json_atomic(manifest_path, manifest)
    return path
