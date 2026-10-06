# seam-scope: implementation-infrastructure (Farol 3 public module seam: transcripts: subtitle files, YouTube sources and audio → cited evidence)
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import docops
from docops.backends import QueryRequest
from docops.mcp_server import citation
from docops.package_index import build_package_index, open_package_index

VTT = """WEBVTT
Kind: captions
Language: en

00:00:01.000 --> 00:00:04.000
Welcome to the <c>channel</c>.

00:00:04.000 --> 00:00:09.500
Today we explain how retries work.

00:01:02.000 --> 00:01:06.000
The client retries five times with exponential backoff.

00:01:06.000 --> 00:01:06.010
The client retries five times with exponential backoff.
"""

SRT = """1
00:00:01,000 --> 00:00:03,000
Olá e bem-vindos.

2
00:02:10,500 --> 00:02:14,000
O tempo limite padrão é de cinco segundos.
"""


def _package(tmp_path: Path, name: str, content: str) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    (source / name).write_text(content, encoding="utf-8")
    output = tmp_path / "package"
    result = docops.apply(
        docops.plan(
            docops.OperationRequest(
                source,
                docops.OperationOptions(output_dir=output, source_root=source.parent, slug="talk", license="CC-BY-4.0"),
            )
        )
    )
    assert result.ok, result.errors
    build_package_index(output, embedder=None)
    return output


def test_vtt_captions_become_timestamped_evidence(tmp_path: Path) -> None:
    package = _package(tmp_path, "talk.vtt", VTT)
    backend, index = open_package_index(package, embedder=None)

    hit = backend.query(index, QueryRequest(query="how many retries exponential backoff", top_k=1)).hits[0]

    assert "retries five times" in hit["text"]
    assert hit["text"].count("retries five times") == 1  # rolling duplicate captions are merged
    assert any(item["kind"] == "timestamp" and item["start"] == "00:01:02" for item in hit["locators"])
    assert citation(hit).endswith("(at 00:01:02)")
    document = (package / "rag" / "documents" / "talk.md").read_text(encoding="utf-8")
    assert "<c>" not in document


def test_srt_subtitles_are_supported(tmp_path: Path) -> None:
    package = _package(tmp_path, "aula.srt", SRT)
    backend, index = open_package_index(package, embedder=None)

    hit = backend.query(index, QueryRequest(query="tempo limite padrão", top_k=1)).hits[0]

    assert "cinco segundos" in hit["text"] and citation(hit).endswith("(at 00:02:10)")


def test_youtube_source_uses_captions_chapters_and_declared_license(tmp_path: Path, monkeypatch) -> None:
    from docops import transcripts
    from docops.agent_tasks import next_task, plan_synthesis
    from docops.journey import add_source, build, status

    def fake_fetch(url: str, *, languages: list[str]) -> dict[str, Any]:
        assert url == "https://www.youtube.com/watch?v=abc123XYZ00"
        return {
            "id": "abc123XYZ00",
            "title": "Retries explained",
            "channel": "Acme",
            "license": "Creative Commons Attribution license (reuse allowed)",
            "duration": 400,
            "chapters": [{"start_time": 0, "title": "Intro"}, {"start_time": 60, "title": "Retries"}],
            "captions": {"kind": "manual", "language": "en", "vtt": VTT},
        }

    monkeypatch.setattr(transcripts, "fetch_youtube", fake_fetch)
    project = tmp_path / "project"

    added = add_source(project, "https://youtu.be/abc123XYZ00")
    built = build(project)
    report = status(project)

    assert added["source"]["kind"] == "youtube" and added["source"]["id"] == "youtube-abc123xyz00"
    assert built["ok"], built
    config = json.loads((project / "farol.json").read_text(encoding="utf-8"))
    assert config["sources"][0]["license"] == "CC-BY-3.0"
    assert config["sources"][0]["title"] == "Retries explained"
    assert report["sources"][0]["state"] == "awaiting_agent"
    package = project / "packages" / "youtube-abc123xyz00"
    document = next((package / "rag" / "documents").glob("*.md")).read_text(encoding="utf-8")
    assert "## Retries" in document and "- Captions: manual (en)" in document
    plan_synthesis(package, language="en", outline="agent")
    titles = [section["title"] for section in next_task(package)["inputs"]["sections"]]
    assert "Retries" in " ".join(titles)


def test_youtube_without_the_media_extra_fails_with_an_actionable_error(tmp_path: Path, monkeypatch) -> None:
    from docops import transcripts
    from docops.journey import add_source, build

    def missing(url: str, *, languages: list[str]) -> dict[str, Any]:
        raise transcripts.TranscriptError("extra_required", "install the media extra: pip install farol-kit[media]")

    monkeypatch.setattr(transcripts, "fetch_youtube", missing)
    project = tmp_path / "project"
    add_source(project, "https://www.youtube.com/watch?v=abc123XYZ00")

    built = build(project)

    assert not built["ok"]
    error = built["built"]["youtube-abc123xyz00"]["errors"][0]
    assert error["code"] == "extra_required" and "farol-kit[media]" in error["message"]


def test_audio_without_local_speech_recognition_is_a_typed_error(tmp_path: Path, monkeypatch) -> None:
    import sys

    from docops.normalizer import normalize_file

    monkeypatch.setitem(sys.modules, "faster_whisper", None)  # extra not installed
    audio = tmp_path / "episode.mp3"
    audio.write_bytes(b"ID3fake")

    result = normalize_file(audio)

    assert result.status == "error" and result.error_code == "asr_unavailable"
    assert "farol-kit[media]" in (result.error or "")


def test_unreadable_media_is_a_typed_error_not_a_crash(tmp_path: Path, monkeypatch) -> None:
    import sys
    import types

    from docops.normalizer import normalize_file

    class BrokenModel:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def transcribe(self, path: str, **kwargs: object) -> object:
            raise ValueError("Invalid data found when processing input")

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=BrokenModel))
    audio = tmp_path / "episode.mp3"
    audio.write_bytes(b"ID3fake")

    result = normalize_file(audio)

    assert result.status == "error" and result.error_code == "media_unreadable"


def test_audio_is_transcribed_by_the_local_asr_when_available(tmp_path: Path, monkeypatch) -> None:
    from docops import transcripts
    from docops.normalizer import normalize_file

    monkeypatch.setattr(
        transcripts,
        "transcribe_media",
        lambda path: [transcripts.Segment(3.0, 7.0, "Farol turns sources into skills.")],
    )
    audio = tmp_path / "episode.mp3"
    audio.write_bytes(b"ID3fake")

    result = normalize_file(audio)

    assert result.status == "accepted"
    assert "[00:00:03] Farol turns sources into skills." in result.content
    assert "- Transcript: local speech recognition" in result.content
    assert any(item["kind"] == "timestamp" for item in result.locators)


def test_youtube_bot_check_becomes_an_actionable_error(monkeypatch) -> None:
    import sys
    import types

    from docops import transcripts

    class DownloadError(Exception):
        pass

    class Client:
        def __init__(self, options: dict[str, Any]) -> None:
            Client.options = options

        def __enter__(self) -> Client:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def extract_info(self, url: str, download: bool) -> dict[str, Any]:
            raise DownloadError("ERROR: [youtube] abc: Sign in to confirm you're not a bot.")

    fake = types.SimpleNamespace(YoutubeDL=Client, utils=types.SimpleNamespace(DownloadError=DownloadError))
    monkeypatch.setitem(sys.modules, "yt_dlp", fake)
    monkeypatch.setitem(sys.modules, "yt_dlp.utils", fake.utils)
    monkeypatch.setenv("FAROL_YTDLP_COOKIES", "/tmp/cookies.txt")

    with pytest.raises(transcripts.TranscriptError) as error:
        transcripts.fetch_youtube("https://www.youtube.com/watch?v=abc123XYZ00", languages=["en"])

    assert error.value.code == "youtube_blocked"
    assert "cookies" in str(error.value) and "subtitle" in str(error.value)
    assert Client.options["cookiefile"] == "/tmp/cookies.txt"


def test_a_pause_starts_a_new_paragraph_so_facts_cite_their_moment() -> None:
    from docops import transcripts

    segments = [
        transcripts.Segment(1.0, 5.0, "Welcome."),
        transcripts.Segment(42.0, 48.0, "The client retries five times."),
    ]

    markdown = transcripts.transcript_markdown(segments, title="Talk", metadata=[])

    assert "[00:00:42] The client retries five times." in markdown


# -- Farol 3.1 TK-213: text shown on lecture slides (opt-in) -----------------


def test_slide_text_becomes_timestamped_slide_blocks(tmp_path: Path, monkeypatch) -> None:
    from docops import slides, transcripts
    from docops.normalizer import normalize_file

    monkeypatch.setenv("FAROL_SLIDES", "1")
    monkeypatch.setattr(slides.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        transcripts, "transcribe_media", lambda path: [transcripts.Segment(1.0, 4.0, "Hoje falamos de laços.")]
    )
    frames = [(5.0, "Loops: for x in range(3)"), (9.0, "Loops: for x in range(3)"), (65.0, "Funções e parâmetros")]
    monkeypatch.setattr(slides, "_frames_with_text", lambda path: frames)
    video = tmp_path / "aula.mp4"
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42")

    result = normalize_file(video)

    assert result.status == "accepted", result.error
    assert result.content.count("Slide: Loops: for x in range(3)") == 1
    assert "[00:00:05] Slide: Loops: for x in range(3)" in result.content
    assert "[00:01:05] Slide: Funções e parâmetros" in result.content
    assert "[00:00:01] Hoje falamos de laços." in result.content


def test_slides_without_ffmpeg_is_a_typed_error(tmp_path: Path, monkeypatch) -> None:
    from docops import slides, transcripts
    from docops.normalizer import normalize_file

    monkeypatch.setenv("FAROL_SLIDES", "1")
    monkeypatch.setattr(slides.shutil, "which", lambda name: None)
    monkeypatch.setattr(transcripts, "transcribe_media", lambda path: [transcripts.Segment(1.0, 4.0, "Oi.")])
    video = tmp_path / "aula.mp4"
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42")

    result = normalize_file(video)

    assert result.status == "error" and result.error_code == "ffmpeg_missing"
