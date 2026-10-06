"""Text shown on lecture slides, from video key frames (TK-213, opt-in ``--slides``).

Key frames are taken where the picture changes (``ffmpeg`` scene detection, at
most one every few seconds) and read with local OCR (extra ``ocr``). Repeated
slides are kept once. Only the text is extracted; images, diagrams and
rendered equations are not interpreted.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .transcripts import TranscriptError

VIDEO_SUFFIXES = {".mp4", ".webm", ".mkv", ".mov"}
SCENE_THRESHOLD = 0.3
MIN_SECONDS_BETWEEN_FRAMES = 10.0
SAME_SLIDE = 0.9


def slide_texts(path: Path) -> list[tuple[float, str]]:
    """``(second, text)`` for each distinct slide of a video, in order."""

    if shutil.which("ffmpeg") is None:
        raise TranscriptError("ffmpeg_missing", "--slides needs ffmpeg on the PATH (https://ffmpeg.org)")
    kept: list[tuple[float, str]] = []
    for second, text in _frames_with_text(path):
        text = " ".join(text.split())
        if not text:
            continue
        if kept and SequenceMatcher(None, kept[-1][1], text).ratio() >= SAME_SLIDE:
            continue
        kept.append((second, text))
    return kept


def _frames_with_text(path: Path) -> list[tuple[float, str]]:
    """Scene-change key frames read by local OCR (seam for tests)."""

    ocr = _ocr_engine()
    with tempfile.TemporaryDirectory(prefix="farol-slides-") as directory:
        command = [
            "ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-i",
            str(path),
            "-vf",
            f"select='gt(scene,{SCENE_THRESHOLD})+eq(n,0)',showinfo",
            "-vsync",
            "vfr",
            str(Path(directory) / "%05d.png"),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603
        if completed.returncode != 0:
            raise TranscriptError("media_unreadable", "ffmpeg could not read the video frames")
        times = [float(match) for match in re.findall(r"pts_time:([0-9.]+)", completed.stderr)]
        frames = sorted(Path(directory).glob("*.png"))
        results: list[tuple[float, str]] = []
        last = -MIN_SECONDS_BETWEEN_FRAMES
        for second, frame in zip(times, frames):
            if second - last < MIN_SECONDS_BETWEEN_FRAMES:
                continue
            last = second
            results.append((second, ocr(frame)))
        return results


def _ocr_engine() -> Any:
    try:
        from rapidocr_onnxruntime import RapidOCR  # type: ignore[import-not-found]
    except ImportError as exc:
        raise TranscriptError("ocr_unavailable", "--slides needs local OCR: pip install farol-kit[ocr]") from exc
    engine = RapidOCR()

    def read(frame: Path) -> str:
        result, _elapsed = engine(str(frame))
        return " ".join(item[1] for item in result or [])

    return read
