"""Release-candidate checks for prohibited artifacts and credential leaks."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

_SKIP_DIRS = {
    ".git",
    ".venv",
    ".venv-rag",
    ".venv-posix",
    ".venv-windows",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "data",
    "models_cache",
    "artifacts",
    ".docops",
    "build",
    "dist",
    ".scratch",
}
_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    re.compile(
        r"(?ix)[\"']?(?:bearer[_ -]?token|access[_ -]?token|refresh[_ -]?token|"
        r"api[_ -]?key|client[_ -]?secret|private[_ -]?key)[\"']?\s*[:=]\s*[\"']?"
        r"(?!replace(?:\b|[_-])|<set|\$\{|your[_ -]?|change[_ -]?me|example\b|placeholder\b)"
        r"[A-Za-z0-9][A-Za-z0-9_./+=:@-]{19,}"
    ),
    re.compile(
        r"(?i)\b(?:api[_ -]?key|secret|password|token)\s*[:=]\s*[\"']?(?!REPLACE|<set|\$\{)[A-Za-z0-9_./+=-]{20,}"
    ),
)
_WIN_USERS = "Users"
_POSIX_USERS = "/" + _WIN_USERS + "/"
_POSIX_HOME = "/" + "home" + "/"
_ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?:[A-Za-z]:[\\/]+"
    + _WIN_USERS
    + r"[\\/]+[^\s`\"']+|"
    + _POSIX_USERS
    + r"[^\s`\"']+|"
    + _POSIX_HOME
    + r"[^\s`\"']+)"
)
_GENERIC_PATH_PARTS = {"seu_usuario", "your_user", "yourname", "user", "username", "you"}
_PROHIBITED_PATH_PARTS = _SKIP_DIRS - {".git", "__pycache__", ".pytest_cache"}


@dataclass
class ReleaseAuditResult:
    ok: bool
    findings: list[dict[str, str]] = field(default_factory=list)
    scanned_files: int = 0
    mode: str = "full"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "ok": self.ok,
            "mode": self.mode,
            "candidate": self.mode == "candidate",
            "scanned_files": self.scanned_files,
            "findings": self.findings,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False, sort_keys=True)


def _finding(findings: list[dict[str, str]], code: str, path: str, message: str) -> None:
    findings.append({"code": code, "path": path, "message": message})


def _contains_generic_path_part(value: str) -> bool:
    parts = [part.casefold() for part in re.split(r"[\\/]+", value) if part]
    return any(part in _GENERIC_PATH_PARTS for part in parts)


def _tracked_paths(root: Path) -> set[Path] | None:
    if not (root / ".git").exists():
        return None
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            check=True,
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    raw = completed.stdout.decode("utf-8", errors="replace")
    values = {root / item for item in raw.split("\0") if item}
    return values or None


def _candidate_paths(root: Path) -> set[Path] | None:
    """Return tracked plus non-ignored untracked files for a worktree candidate."""

    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            check=True,
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    raw = completed.stdout.decode("utf-8", errors="replace")
    return {root / item for item in raw.split("\0") if item}


def _explicit_candidate_paths(
    root: Path,
    values: Iterable[Path | str],
    findings: list[dict[str, str]],
) -> set[Path]:
    candidates: set[Path] = set()
    for value in values:
        raw = Path(value).expanduser()
        path = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            _finding(
                findings,
                "candidate_path_escape",
                "<outside-candidate>",
                "candidate files must stay inside the repository root",
            )
            continue
        if not path.is_file() and not path.is_symlink():
            _finding(
                findings, "candidate_file_missing", path.relative_to(root).as_posix(), "candidate file does not exist"
            )
            continue
        candidates.add(path)
    return candidates


def _load_candidate_manifest(path: Path, findings: list[dict[str, str]]) -> list[str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        _finding(findings, "candidate_manifest_unreadable", "<candidate-manifest>", "candidate manifest is unreadable")
        return []
    files = value.get("files") if isinstance(value, dict) else value
    if not isinstance(files, list) or not all(isinstance(item, str) for item in files):
        _finding(
            findings,
            "candidate_manifest_invalid",
            "<candidate-manifest>",
            "candidate manifest must contain a list of file paths",
        )
        return []
    return files


def _allowed_document(relative: Path) -> bool:
    parts = relative.parts
    return len(parts) >= 2 and parts[0] == "documents" and parts[1] in {"README.md", "examples", "fixtures"}


def _allowed_vendor_data(relative: Path) -> bool:
    """Allow only the reviewed vendor's static package resources under data/."""

    parts = tuple(part.casefold() for part in relative.parts)
    prefix = ("skills", "vendor", "mcp_server", "data")
    return len(parts) > len(prefix) and parts[: len(prefix)] == prefix


def _path_prohibition(relative: Path) -> tuple[str, str] | None:
    """Classify a release path before inspecting its bytes or text."""

    parts = tuple(part.casefold() for part in relative.parts)
    if any(part in {value.casefold() for value in _PROHIBITED_PATH_PARTS} for part in parts):
        if not _allowed_vendor_data(relative):
            return "prohibited_artifact", "runtime data or generated artifacts are not release artifacts"
    if any(part == ".rag_state.json" for part in parts):
        return "prohibited_artifact", "RAG state is not a release artifact"
    if any(part == "documents" for part in parts) and not _allowed_document(relative):
        return "prohibited_artifact", "acquired corpus files are not release artifacts"
    filename = parts[-1] if parts else ""
    if filename in {"network.yaml", "network.yml", "network.json", "network.toml"}:
        return "prohibited_artifact", "private network configuration must not be released"
    return None


def audit_release(
    root: Path | str,
    *,
    tracked_only: bool = False,
    candidate: bool = False,
    candidate_files: Iterable[Path | str] | None = None,
    candidate_manifest: Path | str | None = None,
) -> ReleaseAuditResult:
    """Audit a clone or an exact Git worktree candidate without echoing content."""

    project_root = Path(root).expanduser().resolve()
    findings: list[dict[str, str]] = []
    candidate = candidate or candidate_files is not None or candidate_manifest is not None
    tracked = _tracked_paths(project_root) if tracked_only and not candidate else None
    if tracked_only and tracked is None:
        _finding(findings, "git_index_unavailable", ".git", "tracked-only audit requires a readable Git index")
    reported_roots: set[str] = set()
    if not tracked_only and not candidate:
        for directory in sorted(_SKIP_DIRS - {".git", "__pycache__", ".pytest_cache"}):
            candidate_dir = project_root / directory
            if candidate_dir.is_dir():
                _finding(findings, "prohibited_artifact", directory, "runtime directory is not a release artifact")
                reported_roots.add(directory.casefold())
    if candidate:
        if candidate_manifest is not None:
            manifest_path = Path(candidate_manifest).expanduser()
            if not manifest_path.is_absolute():
                manifest_path = project_root / manifest_path
            selected = _load_candidate_manifest(manifest_path.resolve(), findings)
            candidates = sorted(_explicit_candidate_paths(project_root, selected, findings))
        elif candidate_files is not None:
            candidates = sorted(_explicit_candidate_paths(project_root, candidate_files, findings))
        else:
            selected = _candidate_paths(project_root)
            if selected is None:
                _finding(findings, "git_index_unavailable", ".git", "candidate audit requires a readable Git index")
                selected = set()
            candidates = sorted(selected)
    elif tracked_only and tracked is not None:
        candidates = sorted(tracked or set())
    else:
        candidates = sorted(path for path in project_root.rglob("*") if path.is_file() or path.is_symlink())
    scanned = 0
    nested_git_reported = False
    for path in candidates:
        try:
            relative = path.relative_to(project_root)
        except ValueError:
            continue
        parts = relative.parts
        if path.is_symlink():
            _finding(
                findings, "symlink_artifact", relative.as_posix(), "symbolic links are not portable release artifacts"
            )
            continue
        if ".git" in parts:
            if parts[0] != ".git" and not nested_git_reported:
                _finding(findings, "nested_git", relative.as_posix(), "nested Git metadata must not be shipped")
                nested_git_reported = True
            continue
        prohibition = _path_prohibition(relative)
        if prohibition:
            code, message = prohibition
            if not (not tracked_only and len(parts) == 2 and parts[0] in reported_roots):
                _finding(findings, code, relative.as_posix(), message)
            continue
        scanned += 1
        try:
            if path.stat().st_size > 25 * 1024 * 1024:
                _finding(
                    findings, "large_artifact", relative.as_posix(), "release file exceeds the 25 MiB source limit"
                )
                continue
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for pattern in _SECRET_PATTERNS:
            if pattern.search(text):
                _finding(
                    findings,
                    "secret_like_value",
                    relative.as_posix(),
                    "credential-like value detected; remove it before release",
                )
                break
        absolute_paths = [match.group(0) for match in _ABSOLUTE_PATH_PATTERN.finditer(text)]
        if any(not _contains_generic_path_part(match) for match in absolute_paths):
            _finding(
                findings, "author_path", relative.as_posix(), "release text contains an absolute user-machine path"
            )
    for requirements_name in ("requirements.txt", "requirements-dev.txt", "requirements.lock"):
        requirements_path = project_root / requirements_name
        if not requirements_path.is_file() or (
            tracked_only and tracked is not None and requirements_path not in tracked
        ):
            continue
        for line_number, line in enumerate(
            requirements_path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            value = line.strip()
            if not value or value.startswith("#") or value.startswith("-"):
                continue
            if "==" not in value:
                _finding(
                    findings,
                    "unpinned_dependency",
                    f"{requirements_name}:{line_number}",
                    "release dependencies must use exact versions",
                )
    mode = "candidate" if candidate else "tracked" if tracked_only else "full"
    return ReleaseAuditResult(not findings, findings, scanned, mode)
