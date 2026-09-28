"""Normalize supported documentation formats without executing their content."""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from .safety import classify, dominated_by_high_risk
from .transcripts import MEDIA_SUFFIXES, parse_subtitles, transcript_markdown
from .web_acquirer import normalize_html

SUPPORTED_SUFFIXES = {
    ".vtt",
    ".srt",
    ".mp3",
    ".m4a",
    ".wav",
    ".ogg",
    ".flac",
    ".mp4",
    ".webm",
    ".mkv",
    ".mov",
    ".md",
    ".markdown",
    ".rst",
    ".adoc",
    ".txt",
    ".html",
    ".htm",
    ".pdf",
    ".docx",
    ".py",
    ".c",
    ".h",
    ".cpp",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".json",
    ".yaml",
    ".yml",
    ".xml",
    ".csv",
    ".ipynb",
    ".xlsx",
    ".pptx",
}
TRANSCRIPTION_SUFFIXES = {".ass", ".srt", ".ssa", ".vtt"}
MAX_DOCUMENT_BYTES = 25 * 1024 * 1024

_INJECTION_PATTERNS = (
    re.compile(r"\bignore\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|above)\s+instructions?\b", re.I),
    re.compile(r"\b(reveal|show|print|leak)\s+(?:the\s+)?(?:secret|credential|api\s*key|password)", re.I),
    re.compile(r"\bsystem\s+message\b", re.I),
    re.compile(r"\bdo\s+not\s+(?:tell|mention|disclose)", re.I),
)


@dataclass
class NormalizationResult:
    status: str
    content: str
    origin: str
    format: str
    title: str | None = None
    warnings: list[str] = field(default_factory=list)
    error_code: str | None = None
    error: str | None = None
    untrusted: bool = False
    locators: list[dict[str, Any]] = field(default_factory=list)
    quality_status: str = "accepted"
    quality_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "content": self.content,
            "origin": self.origin,
            "format": self.format,
            "title": self.title,
            "warnings": self.warnings,
            "error_code": self.error_code,
            "error": self.error,
            "untrusted": self.untrusted,
            "locators": self.locators,
            "quality_status": self.quality_status,
            "quality_reason": self.quality_reason,
        }


_FENCE = re.compile(r"^\s*(```|~~~)")
_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")


def markdown_headings(content: str) -> list[tuple[int, str]]:
    """Return ``(level, text)`` of Markdown headings, ignoring fenced code blocks."""

    headings: list[tuple[int, str]] = []
    fence: str | None = None
    for line in content.splitlines():
        marker = _FENCE.match(line)
        if marker:
            if fence is None:
                fence = marker.group(1)
            elif marker.group(1) == fence:
                fence = None
            continue
        if fence is None:
            match = _HEADING.match(line)
            if match:
                headings.append((len(match.group(1)), match.group(2).strip()))
    return headings


def _title_from_markdown(content: str, fallback: str) -> str:
    headings = markdown_headings(content)
    top = next((text for level, text in headings if level == 1), None)
    return top or (headings[0][1] if headings else fallback)


def _untrusted_warnings(content: str) -> tuple[bool, list[str]]:
    flagged = any(pattern.search(content) for pattern in _INJECTION_PATTERNS) or classify(content).risk != "none"
    if flagged:
        return True, ["possible prompt injection detected; content is untrusted and was not executed"]
    return False, []


def _paragraphs(content: str) -> list[str]:
    return [paragraph for paragraph in re.split(r"\n\s*\n", content) if paragraph.strip()]


_TIME_TOKEN = r"\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?"
_TIMESTAMP_RANGE = re.compile(rf"^\s*(?P<start>{_TIME_TOKEN})\s*-->\s*(?P<end>{_TIME_TOKEN})(?:\s+.*)?$")
_BRACKET_TIMESTAMP = re.compile(rf"\[(?P<start>{_TIME_TOKEN})(?:\s*[-–—]\s*(?P<end>{_TIME_TOKEN}))?\]")
_CODE_IDENTIFIER = re.compile(
    r"^\s*(?:(?:async)\s+)?(?:def|class)\s+(?P<definition>[A-Za-z_]\w*)"
    r"|^\s*(?:(?:export)\s+)?(?:(?:async)\s+)?function\s+(?P<function>[A-Za-z_$][\w$]*)"
    r"|^\s*(?:const|let|var)\s+(?P<variable>[A-Za-z_$][\w$]*)\s*="
)
_CODE_FORMATS = {"py", "c", "h", "cpp", "js", "jsx", "ts", "tsx"}


def _locator_line_end(lines: list[str], start: int) -> int:
    for index in range(start, len(lines)):
        if re.match(r"^\s*#{1,6}\s+\S", lines[index]):
            return index
    return len(lines)


def _extract_locators(content: str, fmt: str) -> list[dict[str, Any]]:
    """Extract stable, human-readable evidence locators from normalized text."""

    lines = content.splitlines()
    locators: list[dict[str, Any]] = []
    heading_pattern = re.compile(r"^\s*(?P<marks>#{1,6})\s+(?P<label>.+?)\s*#*\s*$")
    for line_number, line in enumerate(lines, 1):
        heading = heading_pattern.match(line)
        if heading:
            level = len(heading.group("marks"))
            label = heading.group("label").strip()
            if level < 2 or not label:
                continue
            special = re.match(r"^(Page|Slide|Sheet|Cell)\s+(\d+)$", label, re.I)
            if special:
                kind = special.group(1).casefold()
                locator: dict[str, Any] = {
                    "kind": kind,
                    "label": label,
                    "number": int(special.group(2)),
                    "line_start": line_number,
                    "line_end": _locator_line_end(lines, line_number),
                    "available": True,
                }
            else:
                locator = {
                    "kind": "section",
                    "label": label,
                    "level": level,
                    "line_start": line_number,
                    "line_end": _locator_line_end(lines, line_number),
                    "available": True,
                }
            locators.append(locator)

        timestamp = _TIMESTAMP_RANGE.match(line) or _BRACKET_TIMESTAMP.search(line)
        if timestamp:
            start = timestamp.group("start")
            end = timestamp.groupdict().get("end")
            label = f"{start} - {end}" if end else start
            locators.append(
                {
                    "kind": "timestamp",
                    "label": label,
                    "start": start,
                    "end": end,
                    "line_start": line_number,
                    "line_end": line_number,
                    "available": True,
                }
            )

        if fmt.casefold() in _CODE_FORMATS:
            identifier_match = _CODE_IDENTIFIER.match(line)
            if identifier_match:
                identifier = next(
                    (value for value in identifier_match.groupdict().values() if value),
                    None,
                )
                if identifier:
                    locators.append(
                        {
                            "kind": "identifier",
                            "label": identifier,
                            "identifier": identifier,
                            "line_start": line_number,
                            "line_end": line_number,
                            "available": True,
                        }
                    )

    if locators:
        return locators
    return [
        {
            "kind": "normalized_section",
            "label": "normalized-content",
            "line_start": 1,
            "line_end": max(len(lines), 1),
            "available": False,
            "limitation": "source did not expose a stable structural locator",
        }
    ]


def _quality_assessment(content: str, untrusted: bool) -> tuple[str, str | None]:
    # Quoting an attack (security guides, papers about prompts) keeps the
    # document; its risky blocks are excluded later, per block. Only a
    # document dominated by high-risk directives is quarantined whole.
    if untrusted and dominated_by_high_risk(_paragraphs(content)):
        return "quarantine", "untrusted_content"
    replacement_ratio = content.count("\ufffd") / max(len(content), 1)
    if replacement_ratio > 0.01:
        return "quarantine", "excessive_replacement_characters"
    control_count = sum(1 for char in content if ord(char) < 32 and char not in "\n\r\t")
    if control_count / max(len(content), 1) > 0.02:
        return "quarantine", "excessive_control_characters"
    if not re.search(r"\w", content, re.UNICODE):
        return "quarantine", "no_word_characters"
    return "accepted", None


def _openapi_markdown(document: dict[str, Any]) -> str:
    info = document.get("info") if isinstance(document.get("info"), dict) else {}
    title = str(info.get("title") or "OpenAPI document")
    version = info.get("version")
    lines = [f"# {title}"]
    if version:
        lines.append(f"\nVersion: `{version}`")
    if document.get("openapi"):
        lines.append(f"\nOpenAPI: `{document['openapi']}`")
    elif document.get("swagger"):
        lines.append(f"\nSwagger: `{document['swagger']}`")
    servers = document.get("servers")
    if isinstance(servers, list) and servers:
        lines.append("\n## Servers")
        for server in servers:
            if isinstance(server, dict) and server.get("url"):
                lines.append(f"- `{server['url']}`")
    paths = document.get("paths")
    if isinstance(paths, dict):
        lines.append("\n## Endpoints")
        for path, operations in paths.items():
            if not isinstance(operations, dict):
                continue
            for method, operation in operations.items():
                if method.casefold() not in {"get", "post", "put", "patch", "delete", "head", "options", "trace"}:
                    continue
                operation = operation if isinstance(operation, dict) else {}
                lines.append(f"\n### {method.upper()} `{path}`")
                if operation.get("summary"):
                    lines.append(str(operation["summary"]))
                if operation.get("description"):
                    lines.append(str(operation["description"]))
                responses = operation.get("responses")
                if isinstance(responses, dict):
                    lines.append("\nResponses:")
                    for code, response in responses.items():
                        description = response.get("description", "") if isinstance(response, dict) else ""
                        lines.append(f"- `{code}`: {description}")
    return "\n".join(lines).strip() + "\n"


def _load_yaml(path: Path) -> Any:
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("PyYAML is required to normalize YAML/OpenAPI files") from exc
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        raise ValueError(f"invalid YAML: {exc}") from exc


_ARXIV_ID = re.compile(r"\barXiv:\s*(\d{4}\.\d{4,5}(?:v\d+)?)", re.I)
_DOI = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+[^\s\"<>.,;])")


def _pdf_outline(reader: Any) -> dict[int, list[str]]:
    """Map page index → titles of outline entries (two levels) that start on it."""

    starts: dict[int, list[str]] = {}

    def walk(items: Any, depth: int) -> None:
        for item in items:
            if isinstance(item, list):
                if depth < 2:
                    walk(item, depth + 1)
                continue
            try:
                page = reader.get_destination_page_number(item)
            except Exception:
                continue
            title = " ".join(str(getattr(item, "title", "") or "").split())
            if title and page is not None and page >= 0:
                starts.setdefault(page, []).append(title)

    try:
        walk(reader.outline, 1)
    except Exception:
        return {}
    return starts


def _split_at_titles(text: str, titles: list[str]) -> list[tuple[str | None, str]]:
    """Split one page's text where each outline title appears as a line."""

    segments: list[tuple[str | None, str]] = []
    remaining = text
    current: str | None = None
    for title in titles:
        pattern = re.compile(rf"^[\s\dA-Z.]{{0,8}}{re.escape(title)}\s*$", re.I | re.M)
        match = pattern.search(remaining)
        if match:
            segments.append((current, remaining[: match.start()]))
            remaining = remaining[match.end() :]
        else:
            segments.append((current, ""))
        current = title
    segments.append((current, remaining))
    return [(title, body.strip()) for title, body in segments if body.strip() or title is not None]


_MARKDOWN_SYNTAX = re.compile(r"^\s*(?:#|```|~~~|>|\|)|^\s*([=\-_*])\1{2,}\s*$")


def _pdf_page_markdown(text: str) -> str:
    """Render extracted PDF text as Markdown without accidental syntax.

    PDF text is not Markdown: shell prompts (``# ...``), fences, quotes, tables or
    rules must stay text, so such lines are escaped and kept in their paragraph.
    Paragraph boundaries are left as extracted (measured: splitting pages into
    short paragraphs lowered recall on the real acceptance corpus).
    """

    return "\n".join("\\" + line.lstrip() if _MARKDOWN_SYNTAX.match(line) else line for line in text.splitlines())


def _pdf_markdown(reader: Any) -> str:
    """Pages as ``## Page N`` with the document outline as ``### section`` headings."""

    outline = _pdf_outline(reader)
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    head = " ".join(pages[:2])
    metadata = [f"- Pages: {len(pages)}"]
    title = str(getattr(reader.metadata, "title", None) or "").strip() if reader.metadata else ""
    if title:
        metadata.insert(0, f"- Title: {title}")
    if arxiv := _ARXIV_ID.search(head):
        metadata.append(f"- arXiv: {arxiv.group(1)}")
    if doi := _DOI.search(head):
        metadata.append(f"- DOI: {doi.group(1)}")
    parts: list[str] = []
    current: str | None = None
    for index, text in enumerate(pages, 1):
        if not text:
            continue
        lines = [f"## Page {index}"]
        for section, body in _split_at_titles(text, outline.get(index - 1, [])):
            section = section or current
            if section:
                lines.append(f"### {section}")
            if body:
                lines.append(_pdf_page_markdown(body))
            current = section
        parts.append("\n\n".join(lines))
    # Metadata goes last so it never becomes the parent section of the content.
    parts.append("## Metadata\n\n" + "\n".join(metadata))
    return "\n\n".join(parts) if any(pages) else ""


def _extract_pdf(path: Path) -> str:
    text_parts: list[str] = []
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]

        reader = PdfReader(str(path))
        text_parts = [_pdf_markdown(reader)]
    except ImportError:
        try:
            import fitz  # type: ignore[import-not-found]

            document = fitz.open(str(path))
            text_parts = [
                f"## Page {index}\n\n{text.strip()}"
                for index, page in enumerate(document, 1)
                if (text := (page.get_text() or "").strip())
            ]
        except ImportError as exc:
            raise RuntimeError("pypdf or PyMuPDF is required to normalize PDFs") from exc
        except Exception:
            text_parts = []
    except Exception:
        # A scanned or malformed PDF is never silently treated as text.
        text_parts = []
    return "\n\n".join(part.strip() for part in text_parts if part and part.strip()).strip()


def _normalize_media(file_path: Path, origin: str, suffix: str) -> "NormalizationResult":
    """Audio/video through local speech recognition; typed error when unavailable."""

    from . import transcripts

    try:
        segments = transcripts.transcribe_media(file_path)
    except transcripts.TranscriptError as exc:
        return NormalizationResult("error", "", origin, suffix.lstrip("."), error_code=exc.code, error=str(exc))
    if not segments:
        return NormalizationResult(
            "error", "", origin, suffix.lstrip("."), error_code="transcript_empty", error="no speech was recognized"
        )
    title = file_path.stem.replace("-", " ").replace("_", " ").strip() or file_path.stem
    content = transcripts.transcript_markdown(
        segments,
        title=title,
        metadata=["- Transcript: local speech recognition (quality depends on audio and model)"],
    )
    untrusted, warnings = _untrusted_warnings(content)
    quality_status, quality_reason = _quality_assessment(content, untrusted)
    return NormalizationResult(
        "accepted",
        content,
        origin,
        "transcript",
        title=title,
        warnings=warnings,
        untrusted=untrusted,
        locators=_extract_locators(content, "transcript"),
        quality_status=quality_status,
        quality_reason=quality_reason,
    )


def _cell_source(value: Any) -> str:
    if isinstance(value, list):
        return "".join(str(item) for item in value)
    return str(value or "")


def _notebook_markdown(document: Any, fallback: str) -> str:
    if not isinstance(document, dict) or not isinstance(document.get("cells"), list):
        raise ValueError("invalid notebook: cells must be a list")
    lines = [f"# {fallback}"]
    for index, cell in enumerate(document["cells"], 1):
        if not isinstance(cell, dict):
            continue
        content = _cell_source(cell.get("source", "")).strip()
        if not content:
            continue
        cell_type = str(cell.get("cell_type") or "raw").casefold()
        lines.append(f"## Cell {index}")
        if cell_type == "markdown":
            lines.append(content)
        elif cell_type == "code":
            language = "python"
            metadata = cell.get("metadata")
            if isinstance(metadata, dict):
                language_info = metadata.get("language_info")
                if isinstance(language_info, dict) and language_info.get("name"):
                    language = str(language_info["name"])
            lines.extend([f"{chr(96) * 3}{language}", content, chr(96) * 3])
        else:
            lines.append(content)
    return "\n\n".join(lines) + "\n"


def _xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _xml_text(element: ElementTree.Element | None) -> str:
    return "".join(element.itertext()).strip() if element is not None else ""


def _ooxml_text(path: Path, suffix: str) -> str:
    if not zipfile.is_zipfile(path):
        raise ValueError(f"invalid {suffix.lstrip('.')} document: expected an OOXML archive")
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise ValueError(f"invalid {suffix.lstrip('.')} document: {exc}") from exc
    with archive:
        members = archive.namelist()
        total_size = sum(info.file_size for info in archive.infolist())
        if total_size > 100 * 1024 * 1024:
            raise ValueError("OOXML archive expands beyond the 100 MiB safety limit")
        if suffix == ".xlsx":
            return _xlsx_markdown(archive, members, path.stem)
        return _pptx_markdown(archive, members, path.stem)


def _xlsx_markdown(archive: zipfile.ZipFile, members: list[str], fallback: str) -> str:
    shared_strings: list[str] = []
    if "xl/sharedStrings.xml" in members:
        root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
        for item in root:
            if _xml_local_name(item.tag) == "si":
                shared_strings.append(_xml_text(item))
    worksheets = sorted(
        (name for name in members if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)),
        key=lambda name: int(re.search(r"sheet(\d+)", name).group(1)),  # type: ignore[union-attr]
    )
    if not worksheets:
        raise ValueError("invalid xlsx document: no worksheets found")
    lines = [f"# {fallback}"]
    for index, name in enumerate(worksheets, 1):
        root = ElementTree.fromstring(archive.read(name))
        rows: list[str] = []
        for row in root.iter():
            if _xml_local_name(row.tag) != "row":
                continue
            values: list[str] = []
            for cell in row:
                if _xml_local_name(cell.tag) != "c":
                    continue
                value_node = next((child for child in cell if _xml_local_name(child.tag) == "v"), None)
                value = _xml_text(value_node)
                if cell.attrib.get("t") == "s" and value.isdigit() and int(value) < len(shared_strings):
                    value = shared_strings[int(value)]
                elif cell.attrib.get("t") == "inlineStr":
                    inline = next((child for child in cell if _xml_local_name(child.tag) == "is"), None)
                    value = _xml_text(inline)
                formula = next((child for child in cell if _xml_local_name(child.tag) == "f"), None)
                if not value and formula is not None:
                    value = f"={_xml_text(formula)}"
                coordinate = str(cell.attrib.get("r") or "").strip()
                values.append(f"{coordinate}={value}" if coordinate else value)
            if values:
                rows.append("\t".join(values))
        if rows:
            lines.extend([f"\n## Sheet {index}", "", *rows])
    return "\n".join(lines) + "\n"


def _pptx_markdown(archive: zipfile.ZipFile, members: list[str], fallback: str) -> str:
    slides = sorted(
        (name for name in members if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
        key=lambda name: int(re.search(r"slide(\d+)", name).group(1)),  # type: ignore[union-attr]
    )
    if not slides:
        raise ValueError("invalid pptx document: no slides found")
    lines = [f"# {fallback}"]
    for index, name in enumerate(slides, 1):
        root = ElementTree.fromstring(archive.read(name))
        text = "\n".join(
            value for element in root.iter() if _xml_local_name(element.tag) == "t" if (value := _xml_text(element))
        )
        if text:
            lines.extend([f"\n## Slide {index}", "", text])
    return "\n".join(lines) + "\n"


def normalize_file(
    path: Path | str,
    *,
    source_url: str | None = None,
    max_bytes: int = MAX_DOCUMENT_BYTES,
) -> NormalizationResult:
    """Normalize one file and return an explicit status for unsupported inputs."""

    input_path = Path(path).expanduser()
    file_path = input_path.resolve()
    origin = source_url or file_path.as_uri()
    suffix = file_path.suffix.casefold()
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
        raise ValueError("max_bytes must be a positive integer")
    if input_path.is_symlink():
        return NormalizationResult(
            "error",
            "",
            origin,
            suffix.lstrip("."),
            error_code="symlink_not_allowed",
            error="symbolic links are not ingested",
        )
    if not file_path.is_file():
        return NormalizationResult(
            "error", "", origin, suffix.lstrip("."), error_code="not_found", error="file does not exist"
        )
    if suffix in MEDIA_SUFFIXES:
        return _normalize_media(file_path, origin, suffix)
    if suffix in TRANSCRIPTION_SUFFIXES - {".vtt", ".srt"}:
        return NormalizationResult(
            "ignored",
            "",
            origin,
            suffix.lstrip("."),
            error_code="external_transcription_required",
            error="transcriptions must be supplied as external Markdown; native ASR/VTT ingestion is not supported",
        )
    if suffix not in SUPPORTED_SUFFIXES:
        return NormalizationResult(
            "ignored", "", origin, suffix.lstrip("."), error_code="unsupported_format", error="format is not supported"
        )
    try:
        if file_path.stat().st_size > max_bytes:
            return NormalizationResult(
                "error",
                "",
                origin,
                suffix.lstrip("."),
                error_code="document_too_large",
                error=f"document exceeds the {max_bytes} byte limit",
            )
    except OSError as exc:
        return NormalizationResult("error", "", origin, suffix.lstrip("."), error_code="read_failed", error=str(exc))

    warnings: list[str] = []
    title: str | None = None
    fmt = suffix.lstrip(".")
    try:
        if suffix in {".vtt", ".srt"}:
            title = file_path.stem.replace("-", " ").replace("_", " ").strip() or file_path.stem
            content = transcript_markdown(
                parse_subtitles(file_path.read_text(encoding="utf-8", errors="replace")),
                title=title,
                metadata=[f"- Captions: subtitle file ({suffix.lstrip('.')})"],
            )
            fmt = "transcript"
        elif suffix in {".html", ".htm"}:
            document = normalize_html(file_path.read_bytes(), source_url or origin)
            content = document.content
            title = document.title or _title_from_markdown(content, file_path.stem)
            fmt = "html"
        elif suffix == ".pdf":
            content = _extract_pdf(file_path)
            fmt = "pdf"
            if not content:
                return NormalizationResult(
                    "ocr_required",
                    "",
                    origin,
                    fmt,
                    error_code="ocr_required",
                    error="no extractable text; run OCR before ingestion",
                )
            title = file_path.stem
        elif suffix == ".docx":
            try:
                from docx import Document  # type: ignore[import-not-found]
            except ImportError:
                return NormalizationResult(
                    "dependency_missing",
                    "",
                    origin,
                    "docx",
                    error_code="dependency_missing",
                    error="python-docx is required",
                )
            document = Document(str(file_path))
            content = "\n\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip())
            title = _title_from_markdown(content, file_path.stem)
        elif suffix == ".ipynb":
            try:
                document = json.loads(file_path.read_text(encoding="utf-8"))
                content = _notebook_markdown(document, file_path.stem)
            except (json.JSONDecodeError, UnicodeError, ValueError) as exc:
                return NormalizationResult("error", "", origin, "ipynb", error_code="invalid_document", error=str(exc))
            title = _title_from_markdown(content, file_path.stem)
        elif suffix in {".xlsx", ".pptx"}:
            try:
                content = _ooxml_text(file_path, suffix)
            except (ElementTree.ParseError, OSError, ValueError, zipfile.BadZipFile) as exc:
                return NormalizationResult("error", "", origin, fmt, error_code="invalid_document", error=str(exc))
            title = file_path.stem
        elif suffix == ".json":
            raw = file_path.read_text(encoding="utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                content = raw
                warnings.append("invalid JSON preserved as text")
            else:
                if (
                    isinstance(parsed, dict)
                    and ("openapi" in parsed or "swagger" in parsed)
                    and isinstance(parsed.get("paths"), dict)
                ):
                    content = _openapi_markdown(parsed)
                    fmt = "openapi"
                    title = _title_from_markdown(content, file_path.stem)
                else:
                    content = json.dumps(parsed, ensure_ascii=False, indent=2)
                    title = file_path.stem
        elif suffix in {".yaml", ".yml"}:
            try:
                parsed = _load_yaml(file_path)
            except RuntimeError as exc:
                return NormalizationResult(
                    "dependency_missing", "", origin, "yaml", error_code="dependency_missing", error=str(exc)
                )
            except ValueError as exc:
                return NormalizationResult("error", "", origin, "yaml", error_code="invalid_document", error=str(exc))
            if (
                isinstance(parsed, dict)
                and ("openapi" in parsed or "swagger" in parsed)
                and isinstance(parsed.get("paths"), dict)
            ):
                content = _openapi_markdown(parsed)
                fmt = "openapi"
                title = _title_from_markdown(content, file_path.stem)
            else:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                title = file_path.stem
        else:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            title = _title_from_markdown(content, file_path.stem)
    except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
        return NormalizationResult("error", "", origin, fmt, error_code="read_failed", error=str(exc))

    content = content.strip()
    if not content:
        return NormalizationResult(
            "error", "", origin, fmt, title=title, error_code="empty_document", error="document has no text"
        )
    untrusted, injection_warnings = _untrusted_warnings(content)
    warnings.extend(injection_warnings)
    quality_status, quality_reason = _quality_assessment(content, untrusted)
    return NormalizationResult(
        "accepted",
        content,
        origin,
        fmt,
        title=title,
        warnings=warnings,
        untrusted=untrusted,
        locators=_extract_locators(content, fmt),
        quality_status=quality_status,
        quality_reason=quality_reason,
    )
