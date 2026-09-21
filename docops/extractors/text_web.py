"""High-fidelity local Markdown/HTML to canonical IR extraction."""

from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping

from ..api_types import CapabilityV2
from ..ir import ExtractionReceipt, IRBlock, IRDocument
from ..revisions import content_hash
from .base import ExtractionResult, ExtractorError, ExtractorPolicy


class TextWebExtractor:
    name = "text-web"
    version = "2.0"

    def describe(self) -> CapabilityV2:
        return CapabilityV2(
            name=self.name,
            version=self.version,
            status="available",
            supports=["text/markdown", "text/html", "application/xhtml+xml", ".md", ".markdown", ".html", ".htm"],
            fidelity=["structured-native", "text-fallback"],
            execution="local",
            permissions=["read-private-staging"],
            dependencies=[],
        )

    def extract(
        self,
        artifact: Path | str | Mapping[str, Any],
        policy: ExtractorPolicy,
        budget: Mapping[str, Any],
    ) -> ExtractionResult:
        if not policy.rights_ref:
            raise ExtractorError("rights_required", "rights_ref is required before extraction")
        path, metadata = _artifact_path(artifact)
        if not path.is_file() or path.is_symlink():
            raise ExtractorError("artifact_unavailable", "artifact must be a regular file")
        maximum = int(budget.get("max_bytes", policy.max_bytes))
        raw = path.read_bytes()
        if len(raw) > maximum:
            raise ExtractorError("budget_exceeded", "artifact exceeds extractor byte budget")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ExtractorError("invalid_encoding", "Markdown/HTML must be valid UTF-8") from exc
        suffix = path.suffix.casefold()
        media_type = str(
            metadata.get("media_type") or ("text/html" if suffix in {".html", ".htm"} else "text/markdown")
        )
        origin = str(metadata.get("canonical") or path.resolve().as_uri())
        if suffix in {".html", ".htm"} or media_type in {"text/html", "application/xhtml+xml"}:
            parser = _HTMLStructureParser(origin)
            parser.feed(text)
            parser.close()
            source_blocks = parser.blocks
            links = parser.links
        else:
            source_blocks, links = _parse_markdown(text, origin)
        if not source_blocks:
            raise ExtractorError("empty_document", "Markdown/HTML contains no structured content")
        input_hash = hashlib.sha256(raw).hexdigest()
        blocks = _materialize_blocks(source_blocks, links, policy.source_id, origin)
        if len(blocks) > int(budget.get("max_blocks", policy.max_blocks)):
            raise ExtractorError("budget_exceeded", "extracted block count exceeds budget")
        document = IRDocument(
            document_id=str(metadata.get("document_id") or f"ir-{input_hash[:24]}"),
            source_id=policy.source_id,
            source_revision_id=policy.source_revision_id,
            artifact_id=str(metadata.get("artifact_id") or path.name),
            content_hash=input_hash,
            media_type=media_type,
            language=str(metadata.get("language") or "und"),
            extractor={"name": self.name, "version": self.version, "execution": "local"},
            fidelity={
                "level": "structured-native",
                "capabilities": ["hierarchy", "lists", "tables", "code", "links", "origin"],
                "degradations": [],
            },
            rights_ref=policy.rights_ref,
            captured_at=str(metadata.get("captured_at") or "1970-01-01T00:00:00Z"),
            effective_at=metadata.get("effective_at") if isinstance(metadata.get("effective_at"), str) else None,
            region=metadata.get("region") if isinstance(metadata.get("region"), str) else None,
            blocks=blocks,
            origin=origin,
        )
        receipt = ExtractionReceipt(
            artifact_id=document.artifact_id,
            source_id=policy.source_id,
            source_revision_id=policy.source_revision_id,
            extractor=document.extractor,
            fidelity="structured-native",
            status="extracted",
            input_hash=input_hash,
            ir_revision=document.revision_hash(),
        )
        return ExtractionResult(document, receipt)


def _artifact_path(artifact: Path | str | Mapping[str, Any]) -> tuple[Path, dict[str, Any]]:
    if isinstance(artifact, Mapping):
        raw = artifact.get("path") or artifact.get("local_path")
        if not isinstance(raw, str):
            raise ExtractorError("artifact_invalid", "artifact path is required")
        return Path(raw).expanduser().resolve(), dict(artifact)
    return Path(artifact).expanduser().resolve(), {}


def _parse_markdown(text: str, origin: str) -> tuple[list[dict[str, Any]], list[str]]:
    lines = text.splitlines()
    blocks: list[dict[str, Any]] = []
    links = re.findall(r"\[[^\]]+\]\((https?://[^)\s]+)", text)
    heading_path: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", stripped)
        if heading:
            level = len(heading.group(1))
            label = heading.group(2).strip()
            heading_path = heading_path[: max(level - 1, 0)] + [label]
            blocks.append({"kind": "heading", "text": label, "heading_path": list(heading_path), "line": index + 1})
            index += 1
            continue
        if stripped.startswith("```"):
            language = stripped[3:].strip() or None
            start = index + 1
            code_lines: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index])
                index += 1
            if index < len(lines):
                index += 1
            blocks.append(
                {
                    "kind": "code",
                    "text": "\n".join(code_lines),
                    "structured": {"language": language, "code": "\n".join(code_lines)},
                    "heading_path": list(heading_path),
                    "line": start,
                }
            )
            continue
        if _is_table_line(stripped) and index + 1 < len(lines) and _is_table_separator(lines[index + 1].strip()):
            start = index + 1
            table_lines = [stripped]
            index += 2
            while index < len(lines) and _is_table_line(lines[index].strip()):
                table_lines.append(lines[index].strip())
                index += 1
            rows = [_table_cells(row) for row in table_lines]
            blocks.append(
                {
                    "kind": "table",
                    "text": "\n".join(table_lines),
                    "structured": {"rows": rows},
                    "heading_path": list(heading_path),
                    "line": start,
                }
            )
            continue
        if re.match(r"^(?:[-*+] |\d+[.)] )", stripped):
            start = index + 1
            items: list[str] = []
            while index < len(lines) and re.match(r"^(?:[-*+] |\d+[.)] )", lines[index].strip()):
                items.append(re.sub(r"^(?:[-*+] |\d+[.)] )", "", lines[index].strip()))
                index += 1
            blocks.append(
                {
                    "kind": "list",
                    "text": "\n".join(items),
                    "structured": {"items": items},
                    "heading_path": list(heading_path),
                    "line": start,
                }
            )
            continue
        start = index + 1
        paragraphs = [stripped]
        index += 1
        while (
            index < len(lines)
            and lines[index].strip()
            and not re.match(r"^(#{1,6})\s+|^```|^(?:[-*+] |\d+[.)] )", lines[index].strip())
        ):
            paragraphs.append(lines[index].strip())
            index += 1
        blocks.append(
            {"kind": "paragraph", "text": "\n".join(paragraphs), "heading_path": list(heading_path), "line": start}
        )
    return blocks, list(dict.fromkeys(links))


def _is_table_line(value: str) -> bool:
    return value.startswith("|") and value.endswith("|") and value.count("|") >= 3


def _is_table_separator(value: str) -> bool:
    cells = _table_cells(value)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells)


def _table_cells(value: str) -> list[str]:
    return [cell.strip() for cell in value.strip().strip("|").split("|")]


class _HTMLStructureParser(HTMLParser):
    def __init__(self, origin: str) -> None:
        super().__init__(convert_charrefs=True)
        self.origin = origin
        self.blocks: list[dict[str, Any]] = []
        self.links: list[str] = []
        self.heading_path: list[str] = []
        self._active: dict[str, Any] | None = None
        self._row: list[str] | None = None
        self._rows: list[list[str]] | None = None
        self._cell: list[str] | None = None
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        attributes = {key.casefold(): value or "" for key, value in attrs}
        if tag in {"script", "style", "noscript", "template", "svg"}:
            self._skip += 1
            return
        if self._skip:
            return
        if tag == "a":
            href = attributes.get("href", "")
            if href.startswith(("http://", "https://")):
                self.links.append(href)
        if tag == "table":
            self._rows = []
        elif tag == "tr" and self._rows is not None:
            self._row = []
        elif tag in {"th", "td"} and self._row is not None:
            self._cell = []
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._active = {"kind": "heading", "level": int(tag[1]), "text": []}
        elif tag in {"p", "blockquote", "caption"}:
            self._active = {"kind": "quote" if tag == "blockquote" else "paragraph", "text": []}
        elif tag == "li":
            self._active = {"kind": "list", "text": []}
        elif tag == "pre":
            self._active = {"kind": "code", "text": [], "structured": {"language": attributes.get("data-language")}}

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag in {"script", "style", "noscript", "template", "svg"} and self._skip:
            self._skip -= 1
            return
        if self._skip:
            return
        if tag in {"th", "td"} and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None and self._rows is not None:
            self._rows.append(self._row)
            self._row = None
        elif tag == "table" and self._rows is not None:
            if self._rows:
                self.blocks.append(
                    {
                        "kind": "table",
                        "text": "\n".join(" | ".join(row) for row in self._rows),
                        "structured": {"rows": self._rows},
                    }
                )
            self._rows = None
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6", "p", "blockquote", "caption", "li", "pre"}:
            if self._active is not None:
                text = " ".join("".join(self._active["text"]).split())
                if text:
                    if self._active["kind"] == "heading":
                        level = int(self._active["level"])
                        self.heading_path = self.heading_path[: max(level - 1, 0)] + [text]
                        self._active["heading_path"] = list(self.heading_path)
                    else:
                        self._active["heading_path"] = list(self.heading_path)
                    self.blocks.append(dict(self._active, text=text))
                self._active = None

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._cell is not None:
            self._cell.append(data)
        elif self._active is not None:
            self._active["text"].append(data)


def _materialize_blocks(
    source_blocks: list[dict[str, Any]], links: list[str], source_id: str, origin: str
) -> list[IRBlock]:
    blocks: list[IRBlock] = []
    for ordinal, value in enumerate(source_blocks):
        text = str(value.get("text") or "").strip()
        if not text:
            continue
        line = value.get("line") if isinstance(value.get("line"), int) else None
        locator = {"kind": "line", "label": str(line or ordinal + 1), "line": line or ordinal + 1, "origin": origin}
        if value.get("kind") == "heading":
            locator = {
                "kind": "section",
                "label": text,
                "level": value.get("level", len(value.get("heading_path", []))),
                "origin": origin,
            }
        structured = dict(value.get("structured", {})) if isinstance(value.get("structured"), Mapping) else None
        if structured is None and links and value.get("kind") == "paragraph":
            structured = {"links": links}
        fragment_hash = content_hash({"source": source_id, "ordinal": ordinal, "text": text, "structured": structured})
        blocks.append(
            IRBlock(
                block_id=hashlib.sha256(f"{source_id}:{ordinal}:{text}".encode("utf-8")).hexdigest()[:24],
                parent_id=None,
                ordinal=len(blocks),
                kind=str(value.get("kind") or "paragraph"),
                text=text,
                structured=structured,
                heading_path=[str(item) for item in value.get("heading_path", [])],
                locators=[locator],
                source_fragment_hash=fragment_hash,
            )
        )
    return blocks
