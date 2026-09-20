"""Audit normative Markdown links, commands, lifecycle claims and skill metadata."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
import unicodedata
from pathlib import Path
from typing import Iterable

# Keep the documented direct invocation (`python scripts/check_documentation.py`)
# equivalent to the module invocation from a checkout root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from docops.__main__ import CLI_COMPATIBILITY_MAP, _expand_canonical_argv, build_parser  # noqa: E402

_LINK_RE = re.compile(r"\[[^]]*\]\(([^)]+)\)")
_COMMAND_RE = re.compile(
    r"^\s*(?:(?:python(?:\.exe)?|py)\s+-m\s+docops|docops|farol)\s+"
    r"((?:[a-z][a-z0-9_-]*\s+){0,3}[a-z][a-z0-9_-]*)",
    re.IGNORECASE | re.MULTILINE,
)
_SCRIPT_RE = re.compile(r"(?:python(?:\.exe)?|py)\s+(scripts/[A-Za-z0-9_.-]+\.(?:py|ps1|sh))")
_MOJIBAKE_RE = re.compile(r"(?:Ã[\u0080-\u00bf]|Â[\u0080-\u00bf]|â.{0,2}[\u0080-\u009f]|�)")
_HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
_STATUS_RE = re.compile(r"^\|\s*(T\d{2})\s*\|\s*([^|]+?)\s*\|", re.MULTILINE)
_DONE_STATUS = {"done", "concluido", "concluído", "completed", "concluído"}
_DOCOPS_START_RE = re.compile(
    r"^\s*(?:(?:python(?:\.exe)?|py)\s+-m\s+docops|docops|farol)(?:\s+(?P<args>.*))?$",
    re.IGNORECASE,
)
_PROPOSAL_CONTEXT_RE = re.compile(
    r"\b(?:future|proposal|proposed|planned|not available|not yet|futuro|proposta|proposto|planejado|não disponível)\b",
    re.IGNORECASE,
)


def _finding(code: str, path: Path, message: str) -> dict[str, str]:
    return {"code": code, "path": path.as_posix(), "message": message}


def _markdown_files(root: Path) -> Iterable[Path]:
    # `specs/` holds the normative effort (spec, plan, tickets, evidence) and the
    # citation locators those documents rely on, so it belongs to the same gate.
    roots = [root / "README.md", root / "AGENTS.md", root / "docs", root / "skills", root / "specs"]
    for value in roots:
        if value.is_file() and value.suffix.casefold() == ".md":
            yield value
        elif value.is_dir():
            yield from sorted(
                path
                for path in value.rglob("*.md")
                if not path.is_symlink()
                and "vendor" not in path.relative_to(root).parts
                and "continuous-knowledge" not in path.relative_to(root).parts
            )


def _check_skill(path: Path, root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [_finding("skill_unreadable", path.relative_to(root), str(exc))]
    if not content.startswith("---\n") or "\n---\n" not in content[4:]:
        return [_finding("skill_frontmatter_missing", path.relative_to(root), "SKILL.md needs YAML frontmatter")]
    frontmatter, _body = content[4:].split("\n---\n", 1)
    fields = {}
    for line in frontmatter.splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    for required in ("name", "description"):
        if not fields.get(required):
            findings.append(_finding("skill_frontmatter_field", path.relative_to(root), f"missing {required}"))
    return findings


def _heading_anchor(value: str) -> str:
    text = re.sub(r"[`*_~]", "", value)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9 -]", "", text).strip().casefold()
    return re.sub(r"\s+", "-", text)


def _anchors(content: str) -> set[str]:
    anchors = {_heading_anchor(match.group(1)) for match in _HEADING_RE.finditer(content)}
    anchors.update(re.findall(r"(?:id|name)=['\"]([^'\"]+)['\"]", content, flags=re.IGNORECASE))
    return {anchor for anchor in anchors if anchor}


def _check_link(source: Path, raw_target: str, root: Path, content: str) -> dict[str, str] | None:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    path_part, _, fragment = target.partition("#")
    if not path_part and fragment:
        if fragment not in _anchors(content):
            return _finding("broken_local_anchor", source.relative_to(root), f"anchor does not exist: {raw_target}")
        return None
    if not path_part or path_part.startswith(("http://", "https://", "mailto:", "app://")):
        return None
    resolved = (source.parent / path_part).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return _finding("link_outside_root", source.relative_to(root), f"link escapes project: {raw_target}")
    if not resolved.exists():
        return _finding("broken_local_link", source.relative_to(root), f"target does not exist: {raw_target}")
    if fragment:
        try:
            target_content = resolved.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return _finding("link_target_unreadable", source.relative_to(root), f"target is not readable: {raw_target}")
        if fragment not in _anchors(target_content):
            return _finding("broken_local_anchor", source.relative_to(root), f"anchor does not exist: {raw_target}")
    return None


def _known_docops_commands() -> tuple[set[str], set[tuple[str, ...]]]:
    flat = set(CLI_COMPATIBILITY_MAP)
    canonical_commands = {tuple(value.split()) for value in CLI_COMPATIBILITY_MAP.values()}
    canonical = {
        prefix
        for command in canonical_commands
        for length in range(1, len(command) + 1)
        for prefix in (command[:length],)
    }
    return flat, canonical


def _code_fragments(content: str) -> Iterable[str]:
    yield from _fenced_blocks(content)
    yield from (match.group(1) for match in re.finditer(r"`([^`\n]+)`", content))


# Markdown permits both backtick and tilde fences; the README in this repository
# uses tildes, so a backtick-only scanner silently skips documented commands.
_FENCED_BLOCK_RE = re.compile(r"^(?P<fence>`{3,}|~{3,})[^\n]*\n(?P<body>.*?)^(?P=fence)\s*$", re.DOTALL | re.MULTILINE)


def _fenced_blocks(content: str) -> Iterable[str]:
    for match in _FENCED_BLOCK_RE.finditer(content):
        yield match.group("body")


def _code_fragments_with_context(content: str) -> Iterable[tuple[str, str]]:
    """Yield code fragments together with nearby prose used for proposal markers."""

    for match in _FENCED_BLOCK_RE.finditer(content):
        yield match.group("body"), content[max(0, match.start() - 240) : match.start()]
    for match in re.finditer(r"`([^`\n]+)`", content):
        yield match.group(1), content[max(0, match.start() - 240) : match.start()]


def _command_option_names(argv: list[str]) -> set[str]:
    """Read the public option surface from the real CLI parser."""

    parser = build_parser()
    action = next(action for action in parser._actions if action.dest == "command")
    selected = action.choices.get(argv[0])
    if selected is None:
        return set()
    options = {option for item in selected._actions for option in item.option_strings if option.startswith("--")}
    subparser = next((item for item in selected._actions if isinstance(item, argparse._SubParsersAction)), None)
    for token in argv[1:]:
        if subparser is None or token.startswith("-"):
            continue
        child = subparser.choices.get(token)
        if child is None:
            break
        options.update(option for item in child._actions for option in item.option_strings if option.startswith("--"))
        subparser = next((item for item in child._actions if isinstance(item, argparse._SubParsersAction)), None)
    return options


def _docops_argv(line: str) -> list[str] | None:
    match = _DOCOPS_START_RE.match(line)
    if not match:
        return None
    args = match.group("args")
    if not args:
        return None
    try:
        return shlex.split(args, posix=True)
    except (TypeError, ValueError):
        return None


def _check_docops_fragment(fragment: str, context: str, path: Path, root: Path) -> list[dict[str, str]]:
    if _PROPOSAL_CONTEXT_RE.search(context):
        return []
    flat, canonical = _known_docops_commands()
    findings: list[dict[str, str]] = []
    lines = fragment.splitlines()
    for index, raw_line in enumerate(lines):
        line = raw_line.rstrip()
        argv = _docops_argv(line)
        if argv is None:
            continue
        # Markdown command blocks commonly wrap a command with a trailing slash.
        while argv and argv[-1] in {"\\", "`"} and index + 1 < len(lines):
            index += 1
            continuation = _docops_argv(lines[index])
            if continuation:
                argv.extend(continuation)
            else:
                try:
                    argv.extend(shlex.split(lines[index].strip(), posix=True))
                except ValueError:
                    pass
        # Documentation summarises a group as ``docops lifecycle rag {snapshot,profile-compare}``.
        # Expand each brace token so the real CLI map is checked per concrete command.
        for concrete in _expand_brace_groups(argv):
            findings.extend(_check_docops_argv(concrete, flat, canonical, path, root))
    return findings


def _expand_brace_groups(argv: list[str]) -> list[list[str]]:
    expanded: list[list[str]] = [[]]
    for token in argv:
        if token.startswith("{") and token.endswith("}"):
            choices = [choice.strip() for choice in token[1:-1].split(",") if choice.strip()]
        else:
            choices = [token]
        expanded = [prefix + [choice] for prefix in expanded for choice in choices]
    return expanded


def _check_docops_argv(
    argv: list[str],
    flat: set[str],
    canonical: set[tuple[str, ...]],
    path: Path,
    root: Path,
) -> list[dict[str, str]]:
    expanded = _expand_canonical_argv(argv)
    if not expanded:
        return []
    command = expanded[0].casefold()
    if command.startswith((".", "/", "-")) or command in {"...", "<command>"}:
        return []
    if command not in flat:
        tokens = tuple(token.casefold() for token in argv[:4])
        if "/" in command or any(token in {"...", "<command>", "{command}"} for token in tokens[1:]):
            return []
        if any(candidate[: len(tokens)] == tokens for candidate in canonical):
            return []
        return [
            _finding(
                "documented_command_unknown",
                path.relative_to(root),
                f"documented docops command is not in the CLI compatibility map: {' '.join(tokens)}",
            )
        ]
    findings: list[dict[str, str]] = []
    valid_options = _command_option_names(expanded)
    for token in expanded[1:]:
        if not token.startswith("--"):
            continue
        option = token.split("=", 1)[0].casefold()
        if option not in {value.casefold() for value in valid_options}:
            findings.append(
                _finding(
                    "documented_option_unknown",
                    path.relative_to(root),
                    f"documented option is not supported by docops {command}: {option}",
                )
            )
    return findings


def _check_documented_commands(path: Path, content: str, root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for fragment, context in _code_fragments_with_context(content):
        findings.extend(_check_docops_fragment(fragment, context, path, root))
        for match in _SCRIPT_RE.finditer(fragment):
            script = root / match.group(1)
            if not script.is_file():
                findings.append(
                    _finding(
                        "documented_script_missing",
                        path.relative_to(root),
                        f"documented script does not exist: {match.group(1)}",
                    )
                )
    return findings


def _check_ticket_evidence(root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    ticket_root = root / "docs" / "main-consolidation" / "tickets"
    if not ticket_root.is_dir():
        return findings
    status_file = root / "docs" / "main-consolidation" / "IMPLEMENTATION-STATUS.md"
    status_text = status_file.read_text(encoding="utf-8") if status_file.is_file() else ""
    for ticket in sorted(ticket_root.glob("[0-9][0-9]-*.md")):
        content = ticket.read_text(encoding="utf-8")
        status_match = re.search(r"^status:\s*([^\s]+)", content, flags=re.MULTILINE)
        status = status_match.group(1).casefold() if status_match else ""
        ticket_id = f"T{ticket.name[:2]}"
        if status in _DONE_STATUS:
            if not re.search(r"^## (?:Execution )?Evidence\b", content, flags=re.IGNORECASE | re.MULTILINE):
                findings.append(
                    _finding(
                        "implemented_claim_without_evidence",
                        ticket.relative_to(root),
                        "done ticket has no Evidence section",
                    )
                )
            if re.search(r"^- \[ \]", content, flags=re.MULTILINE):
                findings.append(
                    _finding(
                        "implemented_claim_incomplete",
                        ticket.relative_to(root),
                        "done ticket still has unchecked acceptance criteria",
                    )
                )
            if ticket_id not in status_text or not re.search(
                rf"\|\s*{ticket_id}\s*\|\s*(?:conclu[ií]do|done|completed)", status_text, flags=re.IGNORECASE
            ):
                findings.append(
                    _finding(
                        "status_drift",
                        ticket.relative_to(root),
                        "done ticket is not concluded in implementation status",
                    )
                )
    return findings


def check_documentation(root: Path | str) -> dict[str, object]:
    root = Path(root).expanduser().resolve()
    findings: list[dict[str, str]] = []
    checked = 0
    for markdown in _markdown_files(root):
        checked += 1
        try:
            content = markdown.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            findings.append(_finding("document_unreadable", markdown.relative_to(root), str(exc)))
            continue
        marker = _MOJIBAKE_RE.search(content)
        if marker:
            findings.append(_finding("encoding_mojibake", markdown.relative_to(root), f"contains {marker.group()!r}"))
        for match in _LINK_RE.finditer(content):
            finding = _check_link(markdown, match.group(1), root, content)
            if finding:
                findings.append(finding)
        findings.extend(_check_documented_commands(markdown, content, root))
    for skill_file in (
        sorted(
            path
            for path in (root / "skills").glob("*/SKILL.md")
            if not path.is_symlink() and "vendor" not in path.relative_to(root).parts
        )
        if (root / "skills").is_dir()
        else ()
    ):
        findings.extend(_check_skill(skill_file, root))
    findings.extend(_check_ticket_evidence(root))
    return {"schema_version": 1, "ok": not findings, "checked_markdown": checked, "findings": findings}


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    result = check_documentation(args.root)
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
