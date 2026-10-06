"""Small cross-platform atomic file helpers."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

_REPLACE_ATTEMPTS = 50


def _replace(source: Path, destination: Path) -> None:
    """``os.replace`` that tolerates Windows' transient sharing violations.

    On Windows another process briefly reading the destination (a parallel
    agent, an indexer, an antivirus) makes the rename fail with
    PermissionError; the rename itself stays atomic, so retrying is safe.
    """

    import time

    for attempt in range(_REPLACE_ATTEMPTS):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if os.name != "nt" or attempt == _REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(0.02)


def write_json_atomic(path: Path | str, payload: Any) -> None:
    """Write JSON beside the destination and replace it atomically."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        _replace(temporary, destination)
    finally:
        if temporary and temporary.exists():
            temporary.unlink(missing_ok=True)


def write_text_atomic(path: Path | str, content: str) -> None:
    """Write UTF-8 text using the same atomic replacement contract."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        _replace(temporary, destination)
    finally:
        if temporary and temporary.exists():
            temporary.unlink(missing_ok=True)
