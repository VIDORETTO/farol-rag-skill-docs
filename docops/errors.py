"""Catalog of public error codes: what happened and what to do next.

Every code raised by the everyday surfaces (journey, connect, tasks, MCP,
transcripts, local index) must appear here; ``scripts/check_error_catalog.py``
enforces it and generates ``docs/ERRORS.md``.
"""

from __future__ import annotations

from typing import NamedTuple


class ErrorInfo(NamedTuple):
    title: str
    next_action: str


CATALOG: dict[str, ErrorInfo] = {
    # Project and sources
    "project_missing": ErrorInfo("No Farol project here", "farol add <source>"),
    "project_version_unsupported": ErrorInfo("farol.json comes from a newer Farol", "pipx upgrade farol-kit"),
    "no_sources": ErrorInfo("The project has no sources", "farol add <source>"),
    "source_not_found": ErrorInfo("The source path does not exist", "check the path, then farol add <source>"),
    "source_id_taken": ErrorInfo("Another source already uses that id", "farol add <source> --name <new-id>"),
    "source_inside_packages": ErrorInfo(
        "Sources cannot live inside the project's packages folder", "add a folder outside packages/"
    ),
    "download_failed": ErrorInfo("A download failed", "check the network and retry farol build"),
    "extra_required": ErrorInfo("An optional extra is not installed", "pip install farol-kit[media]"),
    "transcript_unavailable": ErrorInfo(
        "The video has no captions in your languages", "download the audio and farol add the file (local ASR)"
    ),
    "youtube_blocked": ErrorInfo(
        "YouTube asked to sign in", "set FAROL_YTDLP_COOKIES=<cookies.txt> or farol add the downloaded .vtt/audio"
    ),
    "youtube_unavailable": ErrorInfo("YouTube metadata could not be read", "check the URL and retry farol build"),
    "asr_unavailable": ErrorInfo("Local speech recognition is not installed", "pip install farol-kit[media]"),
    "media_unreadable": ErrorInfo("The audio or video could not be decoded", "convert it to mp3/wav and add it again"),
    "transcript_empty": ErrorInfo("No speech was recognized", "check the audio or provide a .vtt/.srt file"),
    "schedule_unknown": ErrorInfo("Unknown scheduler", "farol sync --schedule cron"),
    "library_unknown": ErrorInfo("No such project in the library", "farol library list"),
    # Connect
    "harness_unknown": ErrorInfo("Unknown AI agent", "farol connect claude-code"),
    "nothing_to_connect": ErrorInfo("No source has been built yet", "farol build"),
    # Skill synthesis tasks
    "package_invalid": ErrorInfo("Not a Farol package", "run the command inside a project or pass --package"),
    "plan_missing": ErrorInfo("No synthesis plan yet", "farol task plan"),
    "task_unknown": ErrorInfo("Unknown task id", "farol task status"),
    "outline_invalid": ErrorInfo(
        "The outline is not valid JSON of the expected shape", "fix outline.json and resubmit"
    ),
    "output_invalid": ErrorInfo(
        "The answer directory is unsafe or too large", "submit a regular folder with the files"
    ),
    "install_invalid": ErrorInfo("The installed skill failed package validation", "farol doctor --fix"),
    "already_accepted": ErrorInfo("The task was already accepted with other content", "farol task next"),
    "dependencies_pending": ErrorInfo("Earlier tasks must be accepted first", "farol task next"),
    "missing_file": ErrorInfo("An expected answer file is missing", "add the file listed in the task and resubmit"),
    "missing_section": ErrorInfo("A required section is missing", "add the section named in the message"),
    "missing_citations": ErrorInfo("Factual statements lack block references", "cite blocks like [b12] and resubmit"),
    "unknown_reference": ErrorInfo("A cited block is not part of this task", "cite only blocks listed in the task"),
    "budget_exceeded": ErrorInfo("The answer is longer than its token budget", "shorten it and resubmit"),
    "verbatim_copy": ErrorInfo("Too much text is copied from the source", "paraphrase and resubmit"),
    "unsafe_content": ErrorInfo("The answer contains instructions aimed at AI agents", "remove them and resubmit"),
    "frontmatter_invalid": ErrorInfo("SKILL.md frontmatter is incomplete", "set name and a when-to-use description"),
    "chapter_links_missing": ErrorInfo("SKILL.md does not link every chapter", "link each chapter under ## Chapters"),
    "empty_reference_file": ErrorInfo("glossary/patterns/cheatsheet has no items", "add list items and resubmit"),
    "unknown_sections": ErrorInfo("The outline uses unknown section ids", "use only the listed section ids"),
    "duplicate_sections": ErrorInfo("A section appears in two chapters", "assign each section once"),
    "orphan_sections": ErrorInfo("Some sections are not in any chapter", "assign every section to a chapter"),
    "chapter_too_large": ErrorInfo("A chapter covers too much source", "split it into smaller chapters"),
    # MCP tools
    "invalid_query": ErrorInfo("The search query is empty", "ask with words describing the fact you need"),
    "index_missing": ErrorInfo("No factual index yet", "farol build"),
    "package_unknown": ErrorInfo("No package with that name", "call list_skills to see packages"),
    "document_unknown": ErrorInfo("The document is not indexed", "use a document_id returned by search_knowledge"),
    "block_unknown": ErrorInfo("The block is not indexed", "use a block_id returned by search_knowledge"),
    "scope_invalid": ErrorInfo("Unknown context scope", "use scope blocks or section"),
    "skill_unknown": ErrorInfo("No skill with that name", "call list_skills"),
    "chapter_invalid": ErrorInfo("Invalid chapter name", "use a chapter file listed by list_skills"),
    "chapter_unknown": ErrorInfo("Chapter not found", "use a chapter file listed by list_skills"),
    # Local index backend
    "index_unknown": ErrorInfo("The index revision does not exist", "farol doctor --fix"),
    "index_unreadable": ErrorInfo("The index file is damaged", "farol doctor --fix"),
    "revision_mismatch": ErrorInfo("The query targets another project revision", "reopen the reader"),
    "embedding_profile_changed": ErrorInfo("The index was built with another embedding model", "farol build"),
    "embedding_model_unavailable": ErrorInfo(
        "The embedding model could not be loaded", "check the network, or set FAROL_SEMANTIC=0 for BM25"
    ),
    "backend_closed": ErrorInfo("The backend was closed", "reopen the reader"),
    "candidate_unknown": ErrorInfo("The index candidate was not prepared", "farol build"),
    "documents_invalid": ErrorInfo("Index input is malformed", "farol build"),
    "document_invalid": ErrorInfo("An index document is malformed", "farol build"),
    "block_duplicate": ErrorInfo("Duplicate block ids in the index input", "farol build"),
    "document_missing": ErrorInfo("A corpus document listed in the package is missing", "farol build"),
    "extraction_empty": ErrorInfo("A document produced no text blocks", "check the file, then farol build"),
    "mapping_empty": ErrorInfo("The source produced no indexable text", "check the source content, then farol build"),
}


def describe(code: str) -> ErrorInfo | None:
    return CATALOG.get(code)


def next_action(code: str, fallback: str | None = None) -> str | None:
    info = CATALOG.get(code)
    return info.next_action if info else fallback
