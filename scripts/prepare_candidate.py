"""Build a reproducible, unpublished release-candidate bundle."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from docops.release_audit import audit_release  # noqa: E402
from docops.runtime import venv_directory  # noqa: E402
from scripts.candidate_identity import (  # noqa: E402
    candidate_digest,
    git_commit,
    git_files,
    inspect_identity,
    sha256_file,
)
from scripts.generate_supply_chain import generate as generate_supply_chain  # noqa: E402
from scripts.verify_candidate import verify as verify_candidate  # noqa: E402
from scripts.verify_supply_chain import verify as verify_supply_chain  # noqa: E402

_BUNDLE_FILES = (
    ("README.md", "README.md"),
    ("CHANGELOG.md", "CHANGELOG.md"),
    ("LICENSE", "LICENSE"),
    ("SECURITY.md", "SECURITY.md"),
    ("CODE_OF_CONDUCT.md", "CODE_OF_CONDUCT.md"),
    ("CONTRIBUTING.md", "CONTRIBUTING.md"),
    ("docs/DEPENDENCIES.md", "docs/DEPENDENCIES.md"),
    ("docs/RELEASE.md", "docs/RELEASE.md"),
    ("docs/RELEASE-NOTES-1.1.0.md", "docs/RELEASE-NOTES-1.1.0.md"),
    ("docs/SUPPORT-MATRIX.json", "docs/SUPPORT-MATRIX.json"),
    ("docs/REPOSITORY-METADATA.json", "metadata/repository.json"),
    ("community/CODE_OF_CONDUCT.md", "community/CODE_OF_CONDUCT.md"),
    ("community/GOVERNANCE.md", "community/GOVERNANCE.md"),
    ("community/MAINTAINERS.md", "community/MAINTAINERS.md"),
    ("community/SUPPORT.md", "community/SUPPORT.md"),
    ("community/GITHUB-SETTINGS-CHECKLIST.md", "community/GITHUB-SETTINGS-CHECKLIST.md"),
    (".github/CODEOWNERS", ".github/CODEOWNERS"),
    (".github/CODEOWNERS", "community/CODEOWNERS"),
    (".github/ISSUE_TEMPLATE/bug_report.yml", "community/issue-templates/bug_report.yml"),
    (".github/ISSUE_TEMPLATE/feature_request.yml", "community/issue-templates/feature_request.yml"),
    (".github/PULL_REQUEST_TEMPLATE.md", "community/PULL_REQUEST_TEMPLATE.md"),
)
_LOCAL_SOURCE_DIRS = {
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
_LOCAL_SOURCE_FILES = {".rag_state.json"}
# ZIP archives cannot encode timestamps before 1980.  Using the first valid
# ZIP timestamp keeps isolated pip builds reproducible on Windows as well as
# POSIX platforms.
_REPRODUCIBLE_SOURCE_DATE_EPOCH = "315532800"


def _sha256_file(path: Path) -> str:
    return sha256_file(path)


def _git_files(root: Path) -> list[str]:
    values = git_files(root)
    if values is None:
        raise RuntimeError("Git could not enumerate the candidate files")
    if not values:
        raise RuntimeError("the candidate must contain at least one Git file")
    return values


def _distributable_files(root: Path) -> list[str]:
    files: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        if relative.as_posix() in _LOCAL_SOURCE_FILES:
            continue
        if any(part in _LOCAL_SOURCE_DIRS or part.endswith(".egg-info") for part in relative.parts):
            continue
        files.append(relative.as_posix())
    if not files:
        raise RuntimeError("the clean source tree has no distributable files")
    # ``Path`` ordering is platform-specific (and Windows uses separators
    # that do not match the POSIX paths written to the manifest).  Sort the
    # serialized representation so a clean clone and a Git worktree produce
    # the same identity order.
    return sorted(files)


def _source_files(root: Path) -> tuple[list[str], str]:
    if (root / ".git").exists():
        return _git_files(root), _git_commit(root)
    return _distributable_files(root), "unversioned-clean-clone"


def _git_commit(root: Path) -> str:
    commit = git_commit(root)
    if not commit:
        raise RuntimeError("the candidate must have a readable Git HEAD")
    return commit


def _assert_output_is_external_or_ignored(root: Path, output: Path) -> None:
    try:
        relative = output.relative_to(root)
    except ValueError:
        return
    if not relative.parts:
        raise RuntimeError("candidate output cannot be the repository root")
    if not (root / ".git").exists():
        raise RuntimeError("candidate output inside a clean clone cannot be checked against Git ignores")
    completed = subprocess.run(
        ["git", "-C", str(root), "check-ignore", "--quiet", "--no-index", "--", relative.as_posix()],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise RuntimeError("candidate output inside the repository must be ignored")


def _candidate_digest(root: Path, relative_files: Iterable[str]) -> str:
    try:
        return candidate_digest(root, relative_files)
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc


def _copy_file(source: Path, destination: Path) -> None:
    if not source.is_file() or source.is_symlink():
        raise RuntimeError("a required candidate asset is missing or is a symbolic link")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _wheel_version(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        metadata_name = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
        metadata = archive.read(metadata_name).decode("utf-8")
    for line in metadata.splitlines():
        if line.startswith("Version:"):
            return line.partition(":")[2].strip()
    raise RuntimeError("the candidate wheel has no version metadata")


def _build_wheel(root: Path, python: Path, destination: Path) -> Path:
    with tempfile.TemporaryDirectory(prefix="docops-candidate-wheel-") as temporary:
        wheel_dir = Path(temporary)
        completed = subprocess.run(
            [str(python), "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(wheel_dir), str(root)],
            cwd=str(root),
            check=False,
            capture_output=True,
            env={**os.environ, "SOURCE_DATE_EPOCH": _REPRODUCIBLE_SOURCE_DATE_EPOCH},
            text=True,
            timeout=180,
        )
        wheels = sorted(wheel_dir.glob("*.whl"))
        if completed.returncode or len(wheels) != 1:

            def redacted_tail(value: str) -> str:
                return value[-4000:].replace(str(root), "<project-root>").replace(str(wheel_dir), "<wheel-dir>")

            details = {
                "returncode": completed.returncode,
                "stderr_tail": redacted_tail(completed.stderr),
                "stdout_tail": redacted_tail(completed.stdout),
                "wheel_count": len(wheels),
                "wheel_names": [wheel.name for wheel in wheels],
            }
            raise RuntimeError(
                "candidate wheel build failed or produced an unexpected number of wheels: "
                + json.dumps(details, ensure_ascii=False, sort_keys=True)
            )
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(wheels[0], destination / wheels[0].name)
        return destination / wheels[0].name


def _bundle_files(root: Path) -> list[str]:
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink() and path.relative_to(root).as_posix() != "SHA256SUMS"
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_checksums(root: Path) -> None:
    lines = [f"{_sha256_file(root / relative)}  {relative}" for relative in _bundle_files(root)]
    (root / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _display_output(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _has_pip(python: Path) -> bool:
    try:
        completed = subprocess.run(
            [str(python), "-c", "import pip"],
            check=False,
            capture_output=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def _candidate_python(root: Path, explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.absolute()
    relative = Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    project_python = venv_directory(root) / relative
    if project_python.is_file() and _has_pip(project_python):
        return project_python.absolute()
    return Path(sys.executable).absolute()


def _attestation_status() -> dict[str, Any]:
    cosign = shutil.which("cosign")
    if cosign:
        return {
            "status": "available-human-action",
            "tool": "cosign",
            "automated": False,
            "reason": "signing requires an explicit human key and authorization",
        }
    return {
        "status": "not-configured",
        "tool": None,
        "automated": False,
        "reason": "no signing provider is configured; attach an attestation during the human release step if required",
    }


def build_candidate(
    *,
    root: Path,
    output: Path,
    python: Path,
    model_cache: Path | None = None,
    require_model: bool = False,
    profile: str = "core",
    release: bool = False,
) -> dict[str, Any]:
    root = root.expanduser().resolve()
    output = output.expanduser().resolve()
    # A POSIX venv commonly exposes ``bin/python`` as a symlink.  Resolving it
    # here escapes the venv and makes pip inspect the base interpreter instead
    # of the environment selected by the caller.
    python = python.expanduser().absolute()
    _assert_output_is_external_or_ignored(root, output)
    if output.exists():
        if not output.is_dir() or any(output.iterdir()):
            raise RuntimeError("candidate output must be a new or empty directory")
    output.mkdir(parents=True, exist_ok=True)

    relative_files, source_commit = _source_files(root)
    source_candidate_digest = _candidate_digest(root, relative_files)
    identity = inspect_identity(root, relative_files, source_candidate_digest, verify_remote=release)
    if release and (
        identity["state"] != "commit-candidate"
        or identity["remote_evidence"] != "verified"
        or identity["ci"].get("status") != "observed"
        or identity["ci"].get("commit") != source_commit
        or identity["ci"].get("candidate_digest") != source_candidate_digest
    ):
        raise RuntimeError("release candidate requires a clean remote commit and matching CI evidence")
    candidate_audit = audit_release(root, candidate_files=relative_files)
    if not candidate_audit.ok:
        _write_json(output / "candidate-audit.json", candidate_audit.to_dict())
        raise RuntimeError("candidate audit rejected the source tree")

    missing_assets = [source for source, _ in _BUNDLE_FILES if not (root / source).is_file()]
    if missing_assets:
        raise RuntimeError("required repository metadata or community files are missing")
    for source, target in _BUNDLE_FILES:
        _copy_file(root / source, output / target)

    lock_source = root / "requirements.lock"
    lock_destination = output / "provenance" / "requirements.lock"
    _copy_file(lock_source, lock_destination)
    model_source: Path | None = None
    if model_cache is not None:
        model_source = model_cache.expanduser().resolve()
        if not model_source.is_dir() or model_source.is_symlink():
            raise RuntimeError("the requested model cache is missing or is a symbolic link")
        for path in model_source.rglob("*"):
            if path.is_symlink():
                raise RuntimeError("model snapshots containing symbolic links are not reproducible")

    wheel_destination = output / "wheel"
    wheel = _build_wheel(root, python, wheel_destination)
    version = _wheel_version(wheel)
    if version == "1.0.0":
        raise RuntimeError("candidate version must be different from the published 1.0.0")

    evidence = generate_supply_chain(
        root=output,
        wheel=wheel,
        output=output / "evidence",
        model_cache=model_source,
        python=python,
        require_model=require_model,
        profile=profile,
        lock_path=lock_destination,
        source_commit=source_commit,
        source_candidate_digest=source_candidate_digest,
    )
    if not evidence.get("ok"):
        raise RuntimeError("candidate supply-chain evidence contains errors")
    supply_verification = verify_supply_chain(root=output, evidence_dir=output / "evidence", wheel_override=wheel)
    if not supply_verification.get("ok"):
        raise RuntimeError("candidate supply-chain evidence failed independent verification")

    _write_json(
        output / "candidate-audit.json",
        {
            **candidate_audit.to_dict(),
            "source_commit": source_commit,
            "source_candidate_digest": source_candidate_digest,
            "source_files": relative_files,
            "identity": identity,
        },
    )
    _write_json(output / "candidate-identity.json", identity)
    assets = [relative for relative in _bundle_files(output) if relative != "candidate-manifest.json"]
    manifest = {
        "schema_version": 1,
        "kind": "docops-release-candidate",
        "status": "candidate",
        "profile": profile,
        "version": version,
        "source_commit": source_commit,
        "source_state": identity["state"],
        "source_candidate_digest": source_candidate_digest,
        "source_files": relative_files,
        "identity": identity,
        "ci": identity["ci"],
        "candidate_audit": candidate_audit.to_dict(),
        "wheel": {
            "path": _display_output(wheel, output),
            "sha256": _sha256_file(wheel),
            "version": version,
        },
        "evidence": {
            "path": "evidence/supply-chain.json",
            "sha256": _sha256_file(output / "evidence" / "supply-chain.json"),
            "supply_chain_verified": True,
        },
        "gates": {
            "candidate_audit": {"ok": True, "candidate_digest": source_candidate_digest},
            "supply_chain": {"ok": True, "candidate_digest": source_candidate_digest},
            "wheel": {"ok": True, "version": version},
        },
        "assets": assets,
        "attestation": _attestation_status(),
        "repository": {
            "metadata": "metadata/repository.json",
            "ownership": "community/MAINTAINERS.md",
            "protections": "human-review-required",
        },
        "publication": {
            "performed": False,
            "automated": False,
            "human_authorization_required": True,
            "actions": [],
        },
    }
    _write_json(output / "candidate-manifest.json", manifest)
    _write_checksums(output)
    verification = verify_candidate(output)
    if not verification.get("ok"):
        raise RuntimeError("candidate bundle failed independent verification")
    return {
        "schema_version": 1,
        "ok": True,
        "version": version,
        "profile": profile,
        "source_commit": source_commit,
        "source_candidate_digest": source_candidate_digest,
        "identity": identity,
        "candidate_audit": candidate_audit.to_dict(),
        "bundle_verification": verification,
        "output": _display_output(output, root),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--python", type=Path, help="interpreter used for wheel and resolver evidence")
    parser.add_argument("--model-cache", type=Path)
    parser.add_argument("--profile", choices=("core", "rag"), default="core")
    parser.add_argument("--require-model", action="store_true")
    parser.add_argument(
        "--release",
        action="store_true",
        help="require a clean remotely reachable commit and matching GitHub Actions evidence",
    )
    args = parser.parse_args(argv)
    try:
        report = build_candidate(
            root=args.root,
            output=args.output,
            python=_candidate_python(args.root.expanduser().resolve(), args.python),
            model_cache=args.model_cache,
            require_model=args.require_model,
            profile=args.profile,
            release=args.release,
        )
    except (OSError, UnicodeError, ValueError, RuntimeError, subprocess.SubprocessError, zipfile.BadZipFile) as exc:
        print(
            json.dumps(
                {"schema_version": 1, "ok": False, "errors": [{"code": "candidate_failed", "message": str(exc)}]},
                ensure_ascii=False,
            )
        )
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
