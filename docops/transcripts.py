"""Transcripts as cited evidence: subtitle files, YouTube captions and local audio.

Every transcript is rendered as Markdown paragraphs that start with a
``[HH:MM:SS]`` marker (the normalizer turns them into ``timestamp`` locators)
and, when the video has chapters, ``## Chapter`` headings. Captions keep their
provenance: manual captions, automatic captions and local speech recognition
are labelled in the document metadata so readers know the fidelity.

Network acquisition (YouTube via ``yt-dlp``) and speech recognition
(``faster-whisper``) belong to the optional ``media`` extra; without it the
error is typed and tells the user how to install it — never a silent fallback.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any, Iterable

MEDIA_SUFFIXES = {".mp3", ".m4a", ".wav", ".ogg", ".flac", ".mp4", ".webm", ".mkv", ".mov"}
_PARAGRAPH_SECONDS = 30.0
_PAUSE_SECONDS = 4.0
_CUE = re.compile(
    r"(?P<start>\d{1,2}:\d{2}(?::\d{2})?[.,]\d{1,3})\s*-->\s*(?P<end>\d{1,2}:\d{2}(?::\d{2})?[.,]\d{1,3})"
)
_TAG = re.compile(r"<[^>]+>")
_YOUTUBE = re.compile(
    r"^https?://(?:www\.|m\.)?(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|live/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)
_INSTALL_MEDIA = "install the media extra: pip install farol-kit[media]"


class TranscriptError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str


def youtube_id(value: str) -> str | None:
    match = _YOUTUBE.match(value.strip())
    return match.group(1) if match else None


def _seconds(value: str) -> float:
    parts = value.replace(",", ".").split(":")
    seconds = 0.0
    for part in parts:
        seconds = seconds * 60 + float(part)
    return seconds


def clock(seconds: float) -> str:
    whole = int(seconds)
    return f"{whole // 3600:02d}:{whole % 3600 // 60:02d}:{whole % 60:02d}"


def parse_subtitles(text: str) -> list[Segment]:
    """Parse WebVTT or SRT cues; strips markup and merges rolling duplicates."""

    segments: list[Segment] = []
    lines = text.replace("\r\n", "\n").split("\n")
    index = 0
    while index < len(lines):
        match = _CUE.search(lines[index])
        if not match:
            index += 1
            continue
        index += 1
        body: list[str] = []
        while index < len(lines) and lines[index].strip():
            body.append(lines[index])
            index += 1
        spoken = html.unescape(_TAG.sub("", " ".join(body))).strip()
        spoken = " ".join(spoken.split())
        if not spoken:
            continue
        start, end = _seconds(match.group("start")), _seconds(match.group("end"))
        if segments and (spoken == segments[-1].text or segments[-1].text.endswith(spoken)):
            continue
        if segments and spoken.startswith(segments[-1].text):
            # Auto-captions repeat the previous line and append new words.
            previous = segments.pop()
            spoken_new = spoken[len(previous.text) :].strip()
            segments.append(Segment(previous.start, end, f"{previous.text} {spoken_new}".strip()))
            continue
        segments.append(Segment(start, end, spoken))
    return segments


def transcript_markdown(
    segments: Iterable[Segment],
    *,
    title: str,
    metadata: list[str],
    chapters: list[dict[str, Any]] | None = None,
) -> str:
    """Timestamped paragraphs (at most 30 s, split at pauses), grouped under chapter headings."""

    marks = sorted(
        (float(chapter.get("start_time") or 0), str(chapter.get("title") or "").strip())
        for chapter in chapters or []
        if str(chapter.get("title") or "").strip()
    )
    parts = [f"# {title}"]
    chapter_index = -1
    paragraph: list[Segment] = []

    def flush() -> None:
        if paragraph:
            parts.append(f"[{clock(paragraph[0].start)}] " + " ".join(item.text for item in paragraph))
            paragraph.clear()

    for segment in segments:
        while chapter_index + 1 < len(marks) and segment.start >= marks[chapter_index + 1][0]:
            flush()
            chapter_index += 1
            parts.append(f"## {marks[chapter_index][1]}")
        # A pause or a long paragraph starts a new one, so each fact cites a precise moment.
        if paragraph and (
            segment.start - paragraph[0].start >= _PARAGRAPH_SECONDS
            or segment.start - paragraph[-1].end >= _PAUSE_SECONDS
        ):
            flush()
        paragraph.append(segment)
    flush()
    parts.append("## Metadata\n\n" + "\n".join(metadata))
    return "\n\n".join(parts) + "\n"


def youtube_license(value: str | None) -> str | None:
    text = (value or "").casefold()
    if "creative commons" in text:
        return "CC-BY-3.0"  # YouTube's only Creative Commons option is CC BY 3.0
    if text:
        return "YouTube-Standard"
    return None


def fetch_youtube(url: str, *, languages: list[str]) -> dict[str, Any]:
    """Metadata and the best caption track of a YouTube video (requires yt-dlp)."""

    try:
        import yt_dlp  # type: ignore[import-not-found]
    except ImportError as exc:
        raise TranscriptError("extra_required", f"YouTube sources need yt-dlp; {_INSTALL_MEDIA}") from exc
    import os

    options: dict[str, Any] = {"skip_download": True, "quiet": True, "no_warnings": True, "noprogress": True}
    if cookies := os.environ.get("FAROL_YTDLP_COOKIES"):
        options["cookiefile"] = cookies
    with yt_dlp.YoutubeDL(options) as client:
        try:
            info = client.extract_info(url, download=False)
        except Exception as exc:  # yt-dlp raises DownloadError subclasses
            message = str(exc)
            if "confirm you" in message and "bot" in message or "Sign in" in message:
                raise TranscriptError(
                    "youtube_blocked",
                    "YouTube asked to sign in (common on servers and VPNs). Export browser cookies to a file and set"
                    " FAROL_YTDLP_COOKIES=<cookies.txt>, run from a regular connection, or download the subtitle"
                    " (.vtt/.srt) or audio yourself and `farol add` the file.",
                ) from exc
            raise TranscriptError(
                "youtube_unavailable", f"YouTube metadata could not be read: {message[:200]}"
            ) from exc
        captions = None
        for kind, tracks in (
            ("manual", info.get("subtitles") or {}),
            ("automatic", info.get("automatic_captions") or {}),
        ):
            wanted = [lang for lang in languages if lang in tracks] or (list(tracks)[:1] if kind == "manual" else [])
            for language in wanted:
                formats = [item for item in tracks[language] if item.get("ext") == "vtt"]
                if formats:
                    vtt = client.urlopen(formats[0]["url"]).read().decode("utf-8", errors="replace")
                    captions = {"kind": kind, "language": language, "vtt": vtt}
                    break
            if captions:
                break
    if captions is None:
        raise TranscriptError(
            "transcript_unavailable",
            "the video has no captions in the requested languages; download the audio and add it to use local ASR",
        )
    return {
        "id": info.get("id"),
        "title": info.get("title") or info.get("id"),
        "channel": info.get("channel") or info.get("uploader"),
        "license": info.get("license"),
        "duration": info.get("duration"),
        "upload_date": info.get("upload_date"),
        "chapters": info.get("chapters") or [],
        "captions": captions,
    }


def youtube_markdown(url: str, video: dict[str, Any]) -> str:
    captions = video["captions"]
    metadata = [
        f"- Video: {url}",
        f"- Channel: {video.get('channel') or 'unknown'}",
        f"- Captions: {captions['kind']} ({captions['language']})",
        f"- License declared on YouTube: {video.get('license') or 'not stated'}",
    ]
    if video.get("duration"):
        metadata.append(f"- Duration: {clock(float(video['duration']))}")
    if captions["kind"] == "automatic":
        metadata.append("- Quality: automatic captions may contain recognition errors")
    return transcript_markdown(
        parse_subtitles(captions["vtt"]), title=str(video["title"]), metadata=metadata, chapters=video.get("chapters")
    )


def transcribe_media(path: Any) -> list[Segment]:
    """Local speech recognition with faster-whisper (CPU, no network after model download)."""

    try:
        from faster_whisper import WhisperModel  # type: ignore[import-not-found]
    except ImportError as exc:
        raise TranscriptError(
            "asr_unavailable", f"audio/video needs local speech recognition; {_INSTALL_MEDIA}"
        ) from exc
    import os

    model = WhisperModel(os.environ.get("FAROL_ASR_MODEL", "base"), device="cpu", compute_type="int8")
    try:
        segments, _info = model.transcribe(str(path), vad_filter=True)
        return [
            Segment(float(item.start), float(item.end), item.text.strip()) for item in segments if item.text.strip()
        ]
    except Exception as exc:  # decoder errors surface as library-specific types
        raise TranscriptError("media_unreadable", f"the audio/video could not be decoded: {str(exc)[:160]}") from exc
