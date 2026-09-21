"""Governed repository selection and extraction into the canonical IR."""

from __future__ import annotations

import ast
import hashlib
import re
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

from ..api_types import CapabilityV2
from ..ir import ExtractionReceipt, IRBlock, IRDocument
from ..revisions import content_hash
from .base import ExtractionResult, ExtractorError, ExtractorPolicy
from .text_web import _parse_markdown

_DOCUMENT_SUFFIXES = {
    ".md",
    ".markdown",
    ".rst",
    ".adoc",
    ".txt",
    ".html",
    ".htm",
    ".pdf",
    ".docx",
    ".epub",
    ".json",
    ".yaml",
    ".yml",
    ".xml",
    ".csv",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
}
_CODE_SUFFIXES = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".go",
    ".rs",
    ".c",
    ".h",
    ".cpp",
    ".cc",
    ".hpp",
    ".rb",
    ".php",
}
_IGNORED_DIRS = {".git", ".hg", ".svn", ".tox", ".venv", "node_modules", "dist", "build", "__pycache__"}


class RepositoryExtractor:
    name = "repository"
    version = "2.0"

    def describe(self) -> CapabilityV2:
        return CapabilityV2(
            name=self.name,
            version=self.version,
            status="available",
            supports=["repository", "directory"],
            fidelity=["structured-native", "text-fallback", "metadata-only"],
            execution="local",
            permissions=["read-private-staging", "explicit-code-scope"],
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
        root, metadata = _repository_root(artifact)
        if not root.is_dir() or root.is_symlink():
            raise ExtractorError("repository_unavailable", "repository artifact must be a regular directory")
        if (root / ".gitmodules").exists() and not bool(metadata.get("allow_submodules", False)):
            return _failed_result(root, policy, "submodule_not_allowed", "submodule_not_allowed")
        try:
            commit = _git_commit(root)
            selected, ignored = _select_files(root, metadata, budget)
            blocks: list[IRBlock] = []
            total_bytes = 0
            for relative in selected:
                path = root / relative
                if path.is_symlink() or not path.is_file():
                    ignored[relative] = "symlink_or_non_file"
                    continue
                raw = path.read_bytes()
                total_bytes += len(raw)
                if total_bytes > int(budget.get("max_bytes", policy.max_bytes)):
                    raise ExtractorError("budget_exceeded", "repository exceeds the byte budget")
                for block in _file_blocks(relative, raw, commit, metadata):
                    blocks.append(replace(block, ordinal=len(blocks)))
                    if len(blocks) > int(budget.get("max_blocks", policy.max_blocks)):
                        raise ExtractorError("budget_exceeded", "repository exceeds the block budget")
            if not blocks:
                raise ExtractorError("empty_document", "repository selection produced no readable blocks")
        except (OSError, UnicodeError, ExtractorError) as exc:
            code = exc.code if isinstance(exc, ExtractorError) else "repository_read_failed"
            return _failed_result(root, policy, code, str(exc))
        input_hash = hashlib.sha256(
            "\n".join(
                f"{relative}:{hashlib.sha256((root / relative).read_bytes()).hexdigest()}" for relative in selected
            ).encode()
        ).hexdigest()
        document = IRDocument(
            document_id=str(metadata.get("document_id") or f"ir-{input_hash[:24]}"),
            source_id=policy.source_id,
            source_revision_id=policy.source_revision_id,
            artifact_id=str(metadata.get("artifact_id") or root.name),
            content_hash=input_hash,
            media_type="application/repository",
            language=str(metadata.get("language") or "und"),
            extractor={"name": self.name, "version": self.version, "execution": "local", "commit": commit},
            fidelity={
                "level": "structured-native",
                "capabilities": ["path", "line", "symbol", "headings", "contracts"],
                "degradations": [],
            },
            rights_ref=policy.rights_ref,
            captured_at=str(metadata.get("captured_at") or "1970-01-01T00:00:00Z"),
            effective_at=None,
            region=None,
            blocks=blocks,
            origin=str(metadata.get("canonical") or root.resolve().as_uri()),
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
            warnings=["code files require explicit code_include scope"] if ignored else [],
            metadata={"commit": commit, "selected": selected, "ignored": ignored},
        )
        return ExtractionResult(document, receipt)


def _repository_root(artifact: Path | str | Mapping[str, Any]) -> tuple[Path, dict[str, Any]]:
    if isinstance(artifact, Mapping):
        value = artifact.get("path") or artifact.get("root") or artifact.get("local_path")
        if not isinstance(value, str):
            raise ExtractorError("artifact_invalid", "repository path is required")
        return Path(value).expanduser().resolve(), dict(artifact)
    return Path(artifact).expanduser().resolve(), {}


def _git_commit(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ExtractorError("ref_unavailable", "repository commit/ref could not be resolved") from exc
    commit = result.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ExtractorError("ref_unavailable", "repository returned an invalid commit identity")
    return commit


def _select_files(
    root: Path, metadata: Mapping[str, Any], budget: Mapping[str, Any]
) -> tuple[list[str], dict[str, str]]:
    include_code = _patterns(metadata.get("code_include") or metadata.get("include_code"))
    exclude = _patterns(metadata.get("exclude") or metadata.get("exclude_patterns"))
    max_files = int(budget.get("max_files", 10_000))
    selected: list[str] = []
    ignored: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        if any(part in _IGNORED_DIRS for part in Path(relative).parts):
            ignored[relative] = "ignored_directory"
            continue
        suffix = path.suffix.casefold()
        if suffix in _CODE_SUFFIXES and not _matches(relative, include_code):
            ignored[relative] = "code_scope_required"
            continue
        if suffix not in _DOCUMENT_SUFFIXES and suffix not in _CODE_SUFFIXES:
            ignored[relative] = "unsupported_format"
            continue
        if _matches(relative, exclude):
            ignored[relative] = "excluded_by_policy"
            continue
        selected.append(relative)
        if len(selected) > max_files:
            raise ExtractorError("budget_exceeded", "repository exceeds the file budget")
    return selected, ignored


def _patterns(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item) for item in value if str(item).strip())
    return ()


def _matches(relative: str, patterns: tuple[str, ...]) -> bool:
    from fnmatch import fnmatch

    return any(
        fnmatch(relative, candidate)
        or fnmatch(relative, candidate.lstrip("./"))
        or fnmatch(relative, candidate.replace("**/", ""))
        for candidate in patterns
    )


def _file_blocks(relative: str, raw: bytes, commit: str, metadata: Mapping[str, Any]) -> list[IRBlock]:
    text = raw.decode("utf-8", errors="replace")
    suffix = Path(relative).suffix.casefold()
    origin = f"repo://{commit}/{relative}"
    if suffix in {".md", ".markdown"}:
        source, _ = _parse_markdown(text, origin)
        values = source or [{"kind": "paragraph", "text": text, "line": 1, "heading_path": []}]
        return [_block(relative, value, commit, index) for index, value in enumerate(values)]
    if suffix in {".html", ".htm"}:
        return [_plain_block(relative, text, commit, 1, "paragraph")]
    if suffix in _CODE_SUFFIXES:
        return _code_blocks(relative, text, commit)
    kind = "metadata" if suffix in {".json", ".yaml", ".yml", ".toml", ".xml"} else "paragraph"
    return [_plain_block(relative, text, commit, 1, kind)]


def _block(relative: str, value: Mapping[str, Any], commit: str, ordinal: int) -> IRBlock:
    text = str(value.get("text") or "").strip()
    line = int(value.get("line") or ordinal + 1)
    kind = str(value.get("kind") or "paragraph")
    if kind not in {"heading", "paragraph", "list", "table", "code", "quote", "caption", "metadata"}:
        kind = "paragraph"
    return IRBlock(
        block_id=hashlib.sha256(f"{commit}:{relative}:{ordinal}:{text}".encode()).hexdigest()[:24],
        parent_id=None,
        ordinal=ordinal,
        kind=kind,
        text=text,
        structured=value.get("structured") if isinstance(value.get("structured"), Mapping) else None,
        heading_path=[str(item) for item in value.get("heading_path", [])],
        locators=[
            {
                "kind": "section" if kind == "heading" else "line",
                "label": f"{relative}:{line}",
                "path": relative,
                "line": line,
            }
        ],
        source_fragment_hash=content_hash({"path": relative, "line": line, "text": text}),
    )


def _plain_block(relative: str, text: str, commit: str, line: int, kind: str) -> IRBlock:
    return _block(relative, {"text": text, "kind": kind, "line": line, "heading_path": []}, commit, 0)


def _code_blocks(relative: str, text: str, commit: str) -> list[IRBlock]:
    symbols: list[tuple[str, int, int]] = []
    if Path(relative).suffix.casefold() == ".py":
        try:
            tree = ast.parse(text, filename=relative)
        except SyntaxError:
            tree = None
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    end = getattr(node, "end_lineno", node.lineno)
                    symbols.append((node.name, node.lineno, end))
    if not symbols:
        pattern = re.compile(
            r"^\s*(?:export\s+)?(?:async\s+)?(?:function|class|def|fn|func)\s+([A-Za-z_][\w]*)", re.MULTILINE
        )
        symbols = [
            (match.group(1), text.count("\n", 0, match.start()) + 1, text.count("\n", 0, match.end()) + 1)
            for match in pattern.finditer(text)
        ]
    if not symbols:
        return [_plain_block(relative, text, commit, 1, "code")]
    lines = text.splitlines()
    blocks: list[IRBlock] = []
    for ordinal, (symbol, start, end) in enumerate(sorted(symbols, key=lambda item: item[1])):
        body = "\n".join(lines[max(start - 1, 0) : min(end, len(lines))]).strip()
        blocks.append(
            IRBlock(
                block_id=hashlib.sha256(f"{commit}:{relative}:{symbol}:{start}".encode()).hexdigest()[:24],
                parent_id=None,
                ordinal=ordinal,
                kind="code",
                text=body,
                symbol=symbol,
                language=Path(relative).suffix.lstrip(".") or None,
                heading_path=[relative],
                locators=[
                    {
                        "kind": "symbol",
                        "label": f"{relative}:{symbol}",
                        "path": relative,
                        "symbol": symbol,
                        "line": start,
                        "end_line": end,
                    }
                ],
                source_fragment_hash=content_hash({"path": relative, "symbol": symbol, "line": start, "text": body}),
            )
        )
    return blocks


def _failed_result(root: Path, policy: ExtractorPolicy, code: str, message: str) -> ExtractionResult:
    raw = str(root).encode("utf-8", errors="replace")
    receipt = ExtractionReceipt(
        artifact_id=root.name,
        source_id=policy.source_id,
        source_revision_id=policy.source_revision_id,
        extractor={"name": "repository", "version": "2.0", "execution": "local"},
        fidelity="metadata-only",
        status="failed",
        input_hash=hashlib.sha256(raw).hexdigest(),
        errors=[{"code": code, "message": message}],
        metadata={"root": root.name},
    )
    return ExtractionResult(None, receipt, {"code": code})
