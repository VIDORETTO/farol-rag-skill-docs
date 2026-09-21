"""Independently verify a local, unpublished DOCOPS candidate bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.candidate_identity import (  # noqa: E402
    candidate_digest,
    git_commit,
    git_files,
    inspect_identity,
)
from scripts.verify_supply_chain import verify as verify_supply_chain  # noqa: E402

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[A-Za-z0-9.+-]*)?$")
_REQUIRED_ASSETS = {
    ".github/CODEOWNERS",
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "docs/DEPENDENCIES.md",
    "docs/RELEASE.md",
    "docs/RELEASE-NOTES-1.1.0.md",
    "docs/SUPPORT-MATRIX.json",
    "community/CODE_OF_CONDUCT.md",
    "community/CODEOWNERS",
    "community/GOVERNANCE.md",
    "community/MAINTAINERS.md",
    "community/PULL_REQUEST_TEMPLATE.md",
    "community/SUPPORT.md",
    "community/GITHUB-SETTINGS-CHECKLIST.md",
    "community/issue-templates/bug_report.yml",
    "community/issue-templates/feature_request.yml",
    "evidence/SHA256SUMS",
    "evidence/locks.json",
    "evidence/sbom.json",
    "evidence/supply-chain.json",
    "metadata/repository.json",
    "candidate-audit.json",
    "candidate-identity.json",
}
_IDENTITY_STATES = {"working-tree-candidate", "local-commit-candidate", "commit-candidate", "unversioned-clean-clone"}
_LOCAL_SOURCE_FILES = {".rag_state.json"}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_relative(value: Any) -> Path | None:
    if not isinstance(value, str) or not value or "\\" in value:
        return None
    path = Path(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None
    return path


def _wheel_version(path: Path) -> str | None:
    try:
        with zipfile.ZipFile(path) as archive:
            metadata_name = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
            metadata = archive.read(metadata_name).decode("utf-8")
    except (OSError, UnicodeError, StopIteration, zipfile.BadZipFile):
        return None
    match = re.search(r"^Version:\s*(\S+)\s*$", metadata, re.MULTILINE)
    return match.group(1) if match else None


def _wheel_code_version(path: Path) -> str | None:
    try:
        with zipfile.ZipFile(path) as archive:
            source = archive.read("docops/__init__.py").decode("utf-8")
    except (KeyError, OSError, UnicodeError, zipfile.BadZipFile):
        return None
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']\s*$', source, re.MULTILINE)
    return match.group(1) if match else None


def _checksum_errors(root: Path) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    checksum_path = root / "SHA256SUMS"
    try:
        lines = checksum_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return [{"code": "checksums_missing", "message": "SHA256SUMS is missing or unreadable"}]
    listed: set[str] = set()
    for line in lines:
        expected, separator, filename = line.partition("  ")
        relative = _safe_relative(filename) if separator else None
        if not separator or not _SHA256.fullmatch(expected) or relative is None:
            errors.append({"code": "checksum_invalid", "message": "SHA256SUMS contains an invalid entry"})
            continue
        relative_name = relative.as_posix()
        listed.add(relative_name)
        target = root / relative
        if not target.is_file() or target.is_symlink():
            errors.append(
                {"code": "checksum_target_missing", "message": f"checksum target is missing: {relative_name}"}
            )
        elif _sha256_file(target) != expected:
            errors.append({"code": "digest_mismatch", "message": f"digest mismatch for {relative_name}"})
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink() and path.relative_to(root).as_posix() != "SHA256SUMS"
    }
    if listed != actual:
        errors.append(
            {"code": "checksum_incomplete", "message": "SHA256SUMS must cover every bundle file except itself"}
        )
    return errors


def _identity_errors(bundle_root: Path, manifest: dict[str, Any]) -> tuple[list[dict[str, str]], dict[str, Any] | None]:
    errors: list[dict[str, str]] = []
    identity = manifest.get("identity")
    if not isinstance(identity, dict):
        return [{"code": "identity_missing", "message": "candidate identity is missing"}], None
    try:
        identity_path = bundle_root / "candidate-identity.json"
        disk_identity = json.loads(identity_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        disk_identity = None
    if disk_identity != identity:
        errors.append(
            {"code": "identity_evidence_mismatch", "message": "candidate identity evidence differs from manifest"}
        )
    state = identity.get("state")
    if state not in _IDENTITY_STATES:
        errors.append({"code": "identity_state_invalid", "message": "candidate identity state is invalid"})
    if manifest.get("source_state") != state:
        errors.append({"code": "identity_state_mismatch", "message": "manifest source state differs from identity"})
    if identity.get("source_commit") != manifest.get("source_commit"):
        errors.append({"code": "identity_commit_mismatch", "message": "candidate source commit differs from identity"})
    if identity.get("candidate_digest") != manifest.get("source_candidate_digest"):
        errors.append({"code": "identity_digest_mismatch", "message": "candidate digest differs from identity"})
    files = identity.get("files")
    source_files = manifest.get("source_files")
    if not isinstance(files, list) or not all(isinstance(item, str) for item in files) or files != sorted(set(files)):
        errors.append(
            {"code": "identity_files_invalid", "message": "candidate identity files must be sorted and unique"}
        )
    elif any(_safe_relative(item) is None for item in files):
        errors.append({"code": "identity_files_invalid", "message": "candidate identity contains an unsafe file path"})
    if files != source_files:
        errors.append({"code": "identity_files_mismatch", "message": "candidate identity files differ from manifest"})
    ci = identity.get("ci")
    if not isinstance(ci, dict):
        errors.append({"code": "ci_evidence_missing", "message": "CI identity evidence is missing"})
    elif ci.get("status") == "mismatch":
        errors.append({"code": "ci_identity_mismatch", "message": "CI commit does not match the candidate commit"})
    if manifest.get("ci") != ci:
        errors.append({"code": "ci_identity_mismatch", "message": "manifest CI evidence differs from identity"})
    return errors, identity


def _unversioned_files(root: Path) -> list[str]:
    ignored = {
        ".git",
        ".venv",
        ".venv-rag",
        ".venv-posix",
        ".venv-windows",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        ".docops",
        "artifacts",
        "build",
        "data",
        "dist",
        "models_cache",
        ".scratch",
    }
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
        and not path.is_symlink()
        and path.relative_to(root).as_posix() not in _LOCAL_SOURCE_FILES
        and not any(part in ignored for part in path.relative_to(root).parts)
    )


def _source_errors(
    source_root: Path,
    manifest: dict[str, Any],
    identity: dict[str, Any],
    *,
    release: bool,
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    source_files = manifest.get("source_files")
    if not isinstance(source_files, list) or not all(isinstance(item, str) for item in source_files):
        return [{"code": "source_files_invalid", "message": "candidate source files are missing or invalid"}]
    try:
        actual_digest = candidate_digest(source_root, source_files)
    except (OSError, UnicodeError, ValueError):
        errors.append({"code": "source_files_invalid", "message": "candidate source files are missing or unsafe"})
        actual_digest = None
    if actual_digest is not None and actual_digest != manifest.get("source_candidate_digest"):
        errors.append({"code": "source_digest_mismatch", "message": "source files changed after candidate digest"})
    actual_files = git_files(source_root) or _unversioned_files(source_root)
    if sorted(set(source_files)) != actual_files:
        errors.append({"code": "source_files_mismatch", "message": "source file set differs from candidate identity"})
    source_commit = git_commit(source_root)
    if identity.get("state") != "unversioned-clean-clone" and source_commit != identity.get("source_commit"):
        errors.append({"code": "source_commit_mismatch", "message": "source HEAD differs from candidate identity"})
    if release:
        live_identity = inspect_identity(
            source_root,
            source_files,
            actual_digest or "",
            verify_remote=True,
        )
        if live_identity.get("state") != "commit-candidate" or live_identity.get("remote_evidence") != "verified":
            errors.append(
                {
                    "code": "release_identity_unverified",
                    "message": "release verification requires a clean commit reachable from a remote ref",
                }
            )
        ci = identity.get("ci") if isinstance(identity.get("ci"), dict) else {}
        if (
            ci.get("status") != "observed"
            or ci.get("commit") != identity.get("source_commit")
            or ci.get("candidate_digest") != identity.get("candidate_digest")
        ):
            errors.append(
                {
                    "code": "ci_evidence_missing",
                    "message": "release verification requires matching CI commit and candidate digest evidence",
                }
            )
    return errors


def _candidate_audit_errors(bundle_root: Path, manifest: dict[str, Any]) -> list[dict[str, str]]:
    path = bundle_root / "candidate-audit.json"
    try:
        audit = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return [{"code": "candidate_audit_missing", "message": "candidate-audit.json is missing or invalid"}]
    if not isinstance(audit, dict):
        return [{"code": "candidate_audit_invalid", "message": "candidate-audit.json must contain an object"}]
    errors: list[dict[str, str]] = []
    if audit.get("ok") is not True or audit.get("mode") != "candidate" or audit.get("candidate") is not True:
        errors.append({"code": "candidate_audit_failed", "message": "candidate audit evidence is not green"})
    if audit.get("source_commit") != manifest.get("source_commit"):
        errors.append(
            {"code": "candidate_audit_commit_mismatch", "message": "candidate audit commit differs from manifest"}
        )
    if audit.get("source_candidate_digest") != manifest.get("source_candidate_digest"):
        errors.append(
            {"code": "candidate_audit_digest_mismatch", "message": "candidate audit digest differs from manifest"}
        )
    source_files = audit.get("source_files")
    manifest_files = manifest.get("source_files")
    if (
        not isinstance(source_files, list)
        or not all(isinstance(item, str) for item in source_files)
        or source_files != sorted(set(source_files))
        or source_files != manifest_files
    ):
        errors.append(
            {"code": "candidate_audit_files_mismatch", "message": "candidate audit file set differs from manifest"}
        )
    elif audit.get("scanned_files") != len(source_files):
        errors.append(
            {"code": "candidate_audit_count_mismatch", "message": "candidate audit count differs from file set"}
        )
    identity = audit.get("identity")
    if not isinstance(identity, dict) or identity != manifest.get("identity"):
        errors.append(
            {"code": "candidate_audit_identity_mismatch", "message": "candidate audit identity differs from manifest"}
        )
    return errors


def _metadata_errors(bundle_root: Path, manifest: dict[str, Any], version: str) -> list[dict[str, str]]:
    path = bundle_root / "metadata" / "repository.json"
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return [{"code": "metadata_missing", "message": "repository metadata is missing or invalid"}]
    if not isinstance(metadata, dict):
        return [{"code": "metadata_invalid", "message": "repository metadata must be an object"}]
    errors: list[dict[str, str]] = []
    # The published v1.1.0 wheel keeps this distribution identifier for
    # compatibility; Farol is the current public product name.
    if metadata.get("name") != "consulta-documentacao":
        errors.append({"code": "metadata_name_mismatch", "message": "repository metadata name is inconsistent"})
    if metadata.get("version") != version or metadata.get("version") != manifest.get("version"):
        errors.append(
            {"code": "metadata_version_mismatch", "message": "repository metadata version differs from candidate"}
        )
    if metadata.get("license") != "MIT":
        errors.append({"code": "metadata_license_invalid", "message": "repository metadata license is invalid"})
    for field in ("description", "repository", "homepage", "documentation", "issues"):
        if not isinstance(metadata.get(field), str) or not metadata[field].strip():
            errors.append(
                {"code": "metadata_field_missing", "message": f"repository metadata field is missing: {field}"}
            )
    if not isinstance(metadata.get("topics"), list) or not metadata["topics"]:
        errors.append({"code": "metadata_topics_missing", "message": "repository metadata topics are missing"})
    release = metadata.get("release")
    if not isinstance(release, dict) or release.get("publication_automated") is not False:
        errors.append(
            {"code": "metadata_publication_not_blocked", "message": "metadata must prove publication is manual"}
        )
    ownership = metadata.get("ownership")
    if not isinstance(ownership, dict):
        errors.append({"code": "metadata_ownership_missing", "message": "repository ownership metadata is missing"})
    else:
        for field in ("codeowners", "maintainers"):
            relative = _safe_relative(ownership.get(field))
            if relative is None or not (bundle_root / relative).is_file():
                errors.append({"code": "metadata_ownership_missing", "message": f"ownership asset is missing: {field}"})
    try:
        readme = (bundle_root / "README.md").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        readme = ""
    readme_version = re.search(
        r"(?m)^\*\*Versão do pacote:\*\*\s+\[v?([0-9]+\.[0-9]+\.[0-9]+(?:[A-Za-z0-9.+-]*))\]",
        readme,
    )
    if readme_version is None or readme_version.group(1) != version:
        errors.append({"code": "readme_version_mismatch", "message": "README product version differs from candidate"})
    try:
        changelog = (bundle_root / "CHANGELOG.md").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        changelog = ""
    changelog_version = re.search(
        r"(?m)^##\s+([0-9]+\.[0-9]+\.[0-9]+(?:[A-Za-z0-9.+-]*))\b",
        changelog,
    )
    if changelog_version is None or changelog_version.group(1) != version:
        errors.append(
            {
                "code": "changelog_version_mismatch",
                "message": "CHANGELOG candidate version differs from candidate",
            }
        )
    for marker in ("docs/RELEASE.md", "SECURITY.md", "community/", "docs/SUPPORT-MATRIX.json"):
        if marker not in readme:
            errors.append({"code": "readme_link_missing", "message": f"README does not reference {marker}"})
    return errors


def verify(
    root: Path | str,
    *,
    source_root: Path | str | None = None,
    release: bool = False,
) -> dict[str, Any]:
    """Verify every public claim needed before a human may publish a bundle."""

    bundle_root = Path(root).expanduser().resolve()
    errors: list[dict[str, str]] = []
    if any(
        part.casefold() in {"models_cache", "model-cache"}
        for path in bundle_root.rglob("*")
        for part in path.relative_to(bundle_root).parts
    ):
        errors.append(
            {
                "code": "prohibited_model_cache",
                "message": "candidate must contain model provenance only, never model cache bytes",
            }
        )
    manifest_path = bundle_root / "candidate-manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {
            "schema_version": 1,
            "ok": False,
            "errors": [{"code": "manifest_unreadable", "message": "candidate-manifest.json is unreadable"}],
        }
    if not isinstance(manifest, dict):
        return {
            "schema_version": 1,
            "ok": False,
            "errors": [{"code": "manifest_invalid", "message": "candidate manifest must be an object"}],
        }

    version = manifest.get("version")
    if not isinstance(version, str) or not _VERSION.fullmatch(version) or version == "1.0.0":
        errors.append(
            {"code": "version_invalid", "message": "candidate version must be a valid version different from 1.0.0"}
        )
    source_commit = manifest.get("source_commit")
    if not isinstance(source_commit, str) or not source_commit:
        errors.append({"code": "source_commit_missing", "message": "candidate source commit is missing"})
    source_digest = manifest.get("source_candidate_digest")
    if not isinstance(source_digest, str) or not _SHA256.fullmatch(source_digest):
        errors.append({"code": "source_digest_invalid", "message": "candidate source digest must be SHA-256"})
    candidate_audit = manifest.get("candidate_audit")
    if not isinstance(candidate_audit, dict) or candidate_audit.get("ok") is not True:
        errors.append({"code": "candidate_audit_failed", "message": "candidate audit is not green"})
    publication = manifest.get("publication")
    if not isinstance(publication, dict) or publication.get("performed") is not False:
        errors.append(
            {
                "code": "publication_not_blocked",
                "message": "candidate metadata must prove that publication was not performed",
            }
        )

    identity_errors, identity = _identity_errors(bundle_root, manifest)
    errors.extend(identity_errors)
    errors.extend(_candidate_audit_errors(bundle_root, manifest))
    if release and source_root is None:
        errors.append(
            {
                "code": "source_root_required",
                "message": "release verification requires an independent source checkout",
            }
        )
    elif identity is not None and source_root is not None:
        source_path = Path(source_root).expanduser().resolve()
        errors.extend(_source_errors(source_path, manifest, identity, release=release))

    assets_value = manifest.get("assets")
    assets = (
        assets_value if isinstance(assets_value, list) and all(isinstance(item, str) for item in assets_value) else []
    )
    if not assets:
        errors.append({"code": "assets_missing", "message": "candidate assets are missing"})
    safe_assets: set[str] = set()
    for value in assets:
        relative = _safe_relative(value)
        if relative is None:
            errors.append({"code": "asset_path_invalid", "message": "candidate asset path is unsafe"})
            continue
        name = relative.as_posix()
        if name in safe_assets:
            errors.append({"code": "asset_duplicate", "message": f"candidate asset is listed twice: {name}"})
        safe_assets.add(name)
        target = bundle_root / relative
        if not target.is_file() or target.is_symlink():
            errors.append({"code": "asset_missing", "message": f"candidate asset is missing: {name}"})
    missing_assets = sorted(_REQUIRED_ASSETS - safe_assets)
    errors.extend(
        {"code": "asset_required", "message": f"required candidate asset is missing: {name}"} for name in missing_assets
    )
    errors.extend(_metadata_errors(bundle_root, manifest, str(version)))

    wheel_value = manifest.get("wheel")
    wheel_name = wheel_value.get("path") if isinstance(wheel_value, dict) else None
    wheel_relative = _safe_relative(wheel_name)
    wheel_path = bundle_root / wheel_relative if wheel_relative is not None else None
    wheel_version = _wheel_version(wheel_path) if wheel_path is not None and wheel_path.is_file() else None
    code_version = _wheel_code_version(wheel_path) if wheel_path is not None and wheel_path.is_file() else None
    if wheel_path is None or not wheel_path.is_file() or wheel_path.suffix != ".whl":
        errors.append({"code": "wheel_missing", "message": "candidate wheel is missing or unsafe"})
    elif wheel_version != version:
        errors.append({"code": "wheel_version_mismatch", "message": "wheel metadata does not match candidate version"})
    if wheel_path is not None and wheel_path.is_file() and code_version != version:
        errors.append({"code": "code_version_mismatch", "message": "wheel code version does not match candidate"})
    if isinstance(wheel_value, dict) and wheel_path is not None and wheel_path.is_file():
        if wheel_value.get("sha256") != _sha256_file(wheel_path):
            errors.append(
                {"code": "wheel_digest_mismatch", "message": "candidate wheel digest does not match manifest"}
            )

    evidence_dir = bundle_root / "evidence"
    supply_result = verify_supply_chain(
        root=bundle_root,
        evidence_dir=evidence_dir,
        wheel_override=wheel_path,
        require_human_decision=release,
    )
    if not supply_result.get("ok"):
        errors.append({"code": "supply_chain_failed", "message": "independent supply-chain verification failed"})
    errors.extend(_checksum_errors(bundle_root))
    return {
        "schema_version": 1,
        "ok": not errors,
        "version": version,
        "source_commit": source_commit,
        "source_candidate_digest": source_digest,
        "source_state": manifest.get("source_state"),
        "identity": identity,
        "supply_chain": supply_result,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, help="source checkout used to remeasure the candidate identity")
    parser.add_argument(
        "--release",
        action="store_true",
        help="require a clean remotely reachable commit and matching GitHub Actions evidence",
    )
    args = parser.parse_args(argv)
    try:
        result = verify(args.root, source_root=args.source_root, release=args.release)
    except (OSError, UnicodeError, ValueError, KeyError) as exc:
        result = {"schema_version": 1, "ok": False, "errors": [{"code": "verification_failed", "message": str(exc)}]}
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
