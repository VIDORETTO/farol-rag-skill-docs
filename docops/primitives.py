"""Internal filesystem and naming primitives shared by DOCOPS engines."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from .normalizer import NormalizationResult
from .storage import write_text_atomic


def absolute_path_without_resolving(path: Path | str) -> Path:
    """Make a path absolute while preserving a symlink at its final component."""

    return Path(os.path.abspath(os.fspath(Path(path).expanduser())))


def safe_relpath(value: str) -> Path:
    normalized = value.replace("\\", "/")
    candidate = Path(normalized)
    if candidate.is_absolute() or re.match(r"^[A-Za-z]:", normalized):
        raise ValueError(f"unsafe relative path: {value!r}")
    parts = [part for part in normalized.split("/") if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        raise ValueError(f"unsafe relative path: {value!r}")
    return Path(*parts)


def path_from_file_uri(value: str) -> Path:
    parsed = urlsplit(value)
    raw_path = unquote(parsed.path)
    if os.name == "nt" and re.match(r"^/[A-Za-z]:/", raw_path):
        raw_path = raw_path[1:]
    if parsed.netloc and parsed.netloc.casefold() != "localhost":
        raw_path = f"//{parsed.netloc}{raw_path}"
    return Path(raw_path).resolve()


def output_inside_source(source: Path, output_dir: Path) -> bool:
    """Return whether generating the package could mutate the local source."""

    source_resolved = source.resolve()
    output_resolved = output_dir.resolve()
    if output_resolved == source_resolved:
        return True
    try:
        output_resolved.relative_to(source_resolved)
    except ValueError:
        return False
    return True


def destination_for_file(path: Path, base: Path, normalized: NormalizationResult) -> str:
    relative = path.name if base.is_file() else path.relative_to(base).as_posix()
    safe = safe_relpath(relative)
    if normalized.format in {"html", "pdf", "docx", "openapi", "ipynb", "xlsx", "pptx", "transcript"}:
        safe = safe.with_suffix(".md")
    return safe.as_posix()


def write_if_changed(path: Path, content: str) -> bool:
    if path.is_file():
        try:
            if path.read_text(encoding="utf-8") == content:
                return False
        except (OSError, UnicodeError):
            pass
    write_text_atomic(path, content)
    return True


def write_json_if_changed(path: Path, payload: Any) -> bool:
    """Persist JSON only when its serialized representation changed."""

    import json

    content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.is_file():
        try:
            if path.read_text(encoding="utf-8") == content:
                return False
        except (OSError, UnicodeError):
            pass
    from .storage import write_json_atomic

    write_json_atomic(path, payload)
    return True


def skill_name(slug: str) -> str:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ValueError("slug must contain lowercase letters, numbers and hyphens")
    return slug


def local_record_canonical(source_root: str, destination: str) -> str:
    source_id = hashlib.sha256(source_root.encode("utf-8")).hexdigest()[:16]
    normalized_destination = destination.replace("\\", "/")
    return f"file://local/{source_id}/{normalized_destination}"


def unique_destination(candidate: str, source_path: Path | str, used: set[str]) -> str:
    """Keep normalized files distinct when different inputs share a basename."""

    if candidate not in used:
        return candidate
    path = Path(candidate)
    source_value = source_path.as_posix() if isinstance(source_path, Path) else str(source_path)
    digest = hashlib.sha256(source_value.encode("utf-8")).hexdigest()[:10]
    stem = path.stem or "source"
    suffix = path.suffix
    alternative = f"{stem}--{digest}{suffix}"
    counter = 2
    while alternative in used:
        alternative = f"{stem}--{digest}-{counter}{suffix}"
        counter += 1
    return alternative
