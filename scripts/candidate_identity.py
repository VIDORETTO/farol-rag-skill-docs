"""Portable identity helpers for an exact DOCOPS candidate file set."""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path
from typing import Any, Iterable


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def candidate_digest(root: Path, relative_files: Iterable[str]) -> str:
    """Hash sorted relative names and file digests, never file contents in output."""

    digest = hashlib.sha256()
    for value in sorted(set(relative_files)):
        relative = Path(value)
        path = root / relative
        if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
            raise ValueError("candidate contains an unsafe relative path")
        if path.is_symlink() or not path.is_file():
            raise ValueError("candidate contains a missing or symbolic-link file")
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def git_files(root: Path) -> list[str] | None:
    """Return the exact tracked plus non-ignored candidate paths when Git exists."""

    if not (root / ".git").exists():
        return None
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            check=False,
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode:
        return None
    return sorted(
        item
        for item in {item for item in completed.stdout.decode("utf-8", errors="replace").split("\0") if item}
        if (root / item).is_file() or (root / item).is_symlink()
    )


def git_commit(root: Path) -> str | None:
    if not (root / ".git").exists():
        return None
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = completed.stdout.strip()
    return value if completed.returncode == 0 and value else None


def worktree_status(root: Path) -> list[str] | None:
    if not (root / ".git").exists():
        return None
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode:
        return None
    return [line for line in completed.stdout.splitlines() if line.strip()]


def _local_remote_ref(root: Path, commit: str | None) -> str | None:
    if not commit:
        return None
    try:
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "for-each-ref",
                "--format=%(refname) %(objectname)",
                "refs/remotes",
                "refs/tags",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode:
        return None
    for line in completed.stdout.splitlines():
        ref, _, object_name = line.partition(" ")
        if object_name == commit:
            return ref
        try:
            ancestor = subprocess.run(
                ["git", "-C", str(root), "merge-base", "--is-ancestor", commit, ref],
                check=False,
                capture_output=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if ancestor.returncode == 0:
            return ref
    return None


def _remote_ref_from_network(root: Path, commit: str | None) -> str | None:
    if not commit:
        return None
    try:
        remotes = subprocess.run(
            ["git", "-C", str(root), "remote"], check=False, capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if remotes.returncode:
        return None
    for remote in (item.strip() for item in remotes.stdout.splitlines()):
        if not remote:
            continue
        try:
            completed = subprocess.run(
                ["git", "-C", str(root), "ls-remote", "--heads", "--tags", remote],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if completed.returncode:
            continue
        for line in completed.stdout.splitlines():
            object_name, _, ref = line.partition("\t")
            if object_name == commit:
                return ref
    return None


def ci_identity(source_commit: str, digest: str) -> dict[str, Any]:
    """Capture GitHub Actions identity without inventing evidence locally."""

    github_sha = os.environ.get("GITHUB_SHA")
    # A clean clone deliberately has no commit to bind to the workflow SHA.
    # Treat that as absent evidence; calling it a mismatch would make the
    # ordinary clean-clone verification fail merely because it runs in CI.
    if not github_sha or source_commit == "unversioned-clean-clone":
        return {
            "status": "not-observed",
            "commit": None,
            "candidate_digest": None,
            "workflow": None,
            "run_id": None,
            "url": None,
        }
    status = "observed" if github_sha == source_commit else "mismatch"
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    repository = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    url = f"{server}/{repository}/actions/runs/{run_id}" if repository and run_id else None
    return {
        "status": status,
        "commit": github_sha,
        "candidate_digest": digest,
        "workflow": os.environ.get("GITHUB_WORKFLOW"),
        "run_id": run_id,
        "url": url,
    }


def inspect_identity(
    root: Path,
    relative_files: Iterable[str],
    digest: str,
    *,
    verify_remote: bool = False,
) -> dict[str, Any]:
    """Describe source state and optionally verify a reachable remote ref."""

    commit = git_commit(root)
    files = sorted(set(relative_files))
    status = worktree_status(root)
    clean = status is None or not status
    local_ref = _local_remote_ref(root, commit)
    network_ref = _remote_ref_from_network(root, commit) if verify_remote else None
    remote_ref = network_ref or local_ref
    remote_status = "verified" if network_ref else "local-ref" if local_ref else "unverified"
    if commit is None:
        state = "unversioned-clean-clone"
        source_commit = "unversioned-clean-clone"
    elif not clean:
        state = "working-tree-candidate"
        source_commit = commit
    elif remote_ref:
        state = "commit-candidate"
        source_commit = commit
    else:
        state = "local-commit-candidate"
        source_commit = commit
    return {
        "schema_version": 1,
        "state": state,
        "source_commit": source_commit,
        "worktree_clean": clean,
        "remote_ref": remote_ref,
        "remote_reachable": bool(remote_ref),
        "remote_evidence": remote_status,
        "candidate_digest": digest,
        "files": files,
        "ci": ci_identity(source_commit, digest),
    }
