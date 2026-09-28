"""Conceptual synthesis as tasks executed by the user's own AI agent.

Farol never calls a model. It turns the package's canonical blocks into
bounded tasks (map: one chapter per slice of content; reduce: the core skill),
hands them to whatever agent the user runs, validates each answer and, once
everything is accepted, installs a distilled skill atomically with lineage.

Task state lives in ``<package>/.docops/synthesis/``. Every operation is
idempotent: re-planning an unchanged corpus keeps accepted work, and
re-submitting identical output returns the same result.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping

from .mcp_server import citation
from .package_index import package_documents
from .revisions import content_hash, package_revisions
from .safety import classify
from .storage import write_json_atomic

SYNTHESIS_DIR = Path(".docops") / "synthesis"
GENERATOR = "farol-synthesis"
GENERATOR_VERSION = "1"
DEFAULT_TASK_SOURCE_TOKENS = 6_000
CHAPTER_OUTPUT_TOKENS = 2_500
CORE_OUTPUT_TOKENS = 4_000
MAX_OUTPUT_BYTES = 256 * 1024
_CONTEXT_KINDS = frozenset({"title", "heading"})
_PAGE_HEADING = re.compile(r"Page \d+", re.I)
_REF = re.compile(r"\[(b\d+(?:\s*,\s*b\d+)*)\]")
_CHAPTER_SECTIONS: dict[str, tuple[str, ...]] = {
    "Core idea": ("core idea", "ideia central"),
    "Key concepts": ("key concepts", "conceitos-chave", "conceitos chave"),
    "How to apply": ("how to apply", "como aplicar"),
    "Pitfalls": ("pitfalls", "armadilhas"),
    "Takeaways": ("takeaways", "conclusões", "conclusoes"),
}
_CORE_SECTIONS: dict[str, tuple[str, ...]] = {
    "When to use": ("when to use", "quando usar"),
    "Mental models": ("mental models", "core frameworks", "modelos mentais"),
    "Decision rules": ("decision rules", "regras de decisão", "regras de decisao"),
    "Chapters": ("chapters", "capítulos", "capitulos"),
}
_CORE_FILES = ("SKILL.md", "glossary.md", "patterns.md", "cheatsheet.md")


class SynthesisTaskError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")[:48] or "chapter"


def _root(package: Path | str) -> Path:
    root = Path(package).resolve()
    if not (root / "manifest.json").is_file():
        raise SynthesisTaskError("package_invalid", "not a Farol package (manifest.json missing)")
    return root


def _dir(root: Path) -> Path:
    return root / SYNTHESIS_DIR


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _template(name: str) -> str:
    return (Path(__file__).with_name("templates") / name).read_text(encoding="utf-8")


def _manifest(root: Path) -> dict[str, Any]:
    return _read(root / "manifest.json")


def _slices(documents: list[dict[str, Any]], budget: int) -> list[list[dict[str, Any]]]:
    """Group evidence blocks into chapter-sized slices along section boundaries."""

    slices: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    size = 0
    for document in documents:
        previous_section: tuple[str, ...] | None = None
        for block in document["blocks"]:
            if block.get("kind") in _CONTEXT_KINDS or not (block.get("text") or "").strip():
                continue
            if block.get("risk") == "high":
                continue  # hostile directives never reach the agent
            section = tuple(block.get("heading_path") or [])[:2]
            cost = _tokens(block["text"])
            boundary = previous_section is not None and section != previous_section
            new_document = previous_section is None and bool(current)
            if current and ((size + cost > budget and (boundary or new_document)) or size + cost > budget * 1.5):
                slices.append(current)
                current, size = [], 0
            current.append({**block, "path": document["path"], "document_id": document["document_id"]})
            size += cost
            previous_section = section
    if current:
        slices.append(current)
    return slices


def _sections(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Evidence grouped by document and second-level heading, in source order."""

    sections: list[dict[str, Any]] = []
    index: dict[tuple[str, tuple[str, ...]], dict[str, Any]] = {}
    for document in documents:
        for block in document["blocks"]:
            if block.get("kind") in _CONTEXT_KINDS or not (block.get("text") or "").strip():
                continue
            if block.get("risk") == "high":
                continue
            # Page headings of PDFs are locators, not subjects: group by the outline.
            topical = tuple(part for part in block.get("heading_path") or [] if not _PAGE_HEADING.fullmatch(part))
            key = (document["path"], topical[:2] or tuple(block.get("heading_path") or [])[:1])
            section = index.get(key)
            if section is None:
                title = " › ".join(key[1]) or Path(document["path"]).stem
                section = {"id": f"s{len(sections) + 1}", "title": title, "path": document["path"], "blocks": []}
                index[key] = section
                sections.append(section)
            section["blocks"].append({**block, "path": document["path"], "document_id": document["document_id"]})
    for section in sections:
        text = " ".join(block["text"] for block in section["blocks"])
        section["tokens"] = sum(_tokens(block["text"]) for block in section["blocks"])
        section["first_sentence"] = re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0][:200]
    return sections


def _chapter_task(
    index: int, title: str, blocks: list[dict[str, Any]], counter: int, language: str
) -> tuple[dict, int]:
    items = []
    for block in blocks:
        counter += 1
        items.append(
            {
                "ref": f"b{counter}",
                "block_id": block["block_id"],
                "citation": citation(block),
                "heading_path": block.get("heading_path") or [],
                "text": block["text"],
                "risk": block.get("risk", "none"),
            }
        )
    task = {
        "schema_version": 1,
        "task_id": f"chapter-{index:02d}",
        "kind": "chapter",
        "status": "pending",
        "requires": [],
        "language": language,
        "budget": {"output_tokens": CHAPTER_OUTPUT_TOKENS},
        "inputs": {"title": title, "file": f"{index:02d}-{_slugify(title)}.md", "blocks": items},
        "output": {"files": ["chapter.md"]},
    }
    return task, counter


def _title(blocks: list[dict[str, Any]]) -> str:
    """Provisional chapter title naming what the slice covers; the agent may refine it."""

    tops: list[str] = []
    for block in blocks:
        path = block.get("heading_path") or []
        name = path[0] if path else Path(block["path"]).stem.replace("-", " ").title()
        if name not in tops:
            tops.append(name)
    if len(tops) == 1:
        seconds = []
        for block in blocks:
            path = block.get("heading_path") or []
            if len(path) > 1 and path[1] not in seconds:
                seconds.append(path[1])
        if 0 < len(seconds) <= 3 and len(blocks) > 3:
            return f"{tops[0]}: {', '.join(seconds)}"
        return tops[0]
    return ", ".join(tops[:3]) + (f" and {len(tops) - 3} more" if len(tops) > 3 else "")


def plan_synthesis(
    package: Path | str,
    *,
    language: str | None = None,
    task_source_tokens: int = DEFAULT_TASK_SOURCE_TOKENS,
    outline: str | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    """Create (or keep) the task plan for distilling the package into a skill.

    ``outline="agent"`` (default for sources that need three or more chapters)
    starts with an outline task in which the agent groups sections into
    chapters by subject; ``"heuristic"`` slices the source along its sections.
    """

    root = _root(package)
    if refresh:
        return _refresh(root)
    manifest = _manifest(root)
    slug = str((manifest.get("source") or {}).get("slug") or root.name)
    language = language or str((manifest.get("source") or {}).get("language") or "en")
    documents, _skipped = package_documents(root)
    corpus = content_hash([document["document_id"] for document in documents])
    slices = _slices(documents, task_source_tokens)
    if outline not in (None, "agent", "heuristic"):
        raise SynthesisTaskError("outline_invalid", "outline must be 'agent' or 'heuristic'")
    mode = outline or ("agent" if len(slices) >= 3 else "heuristic")
    plan_id = (
        "synthesis-"
        + content_hash({"corpus": corpus, "language": language, "budget": task_source_tokens, "outline": mode})[:16]
    )
    directory = _dir(root)
    plan_path = directory / "plan.json"
    if plan_path.is_file():
        existing = _read(plan_path)
        if existing.get("plan_id") == plan_id:
            return existing
    if directory.exists():
        shutil.rmtree(directory / "tasks", ignore_errors=True)
        shutil.rmtree(directory / "accepted", ignore_errors=True)
    tasks: list[dict[str, Any]] = []
    if mode == "agent":
        sections = _sections(documents)
        tasks.append(
            {
                "schema_version": 1,
                "task_id": "outline",
                "kind": "outline",
                "status": "pending",
                "requires": [],
                "language": language,
                "budget": {"chapter_source_tokens": task_source_tokens},
                "inputs": {
                    "title": "Skill outline",
                    "sections": [
                        {key: section[key] for key in ("id", "title", "path", "tokens", "first_sentence")}
                        | {"block_ids": [block["block_id"] for block in section["blocks"]]}
                        for section in sections
                    ],
                },
                "output": {"files": ["outline.json"]},
            }
        )
        chapter_ids = ["outline"]
    else:
        counter = 0
        for index, blocks in enumerate(slices, 1):
            task, counter = _chapter_task(index, _title(blocks), blocks, counter, language)
            tasks.append(task)
        chapter_ids = sorted(task["task_id"] for task in tasks)
    tasks.append(
        {
            "schema_version": 1,
            "task_id": "core",
            "kind": "core",
            "status": "pending",
            "requires": chapter_ids,
            "language": language,
            "budget": {"output_tokens": CORE_OUTPUT_TOKENS},
            "inputs": {"slug": slug},
            "output": {"files": list(_CORE_FILES)},
        }
    )
    for task in tasks:
        task["request_hash"] = content_hash({key: value for key, value in task.items() if key != "status"})
        write_json_atomic(directory / "tasks" / f"{task['task_id']}.json", task)
    plan = {
        "schema_version": 1,
        "plan_id": plan_id,
        "slug": slug,
        "language": language,
        "corpus": corpus,
        "outline": mode,
        "state": "awaiting_agent",
        "tasks": [_summary(task) for task in tasks],
    }
    write_json_atomic(plan_path, plan)
    return plan


def _summary(task: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task["task_id"],
        "kind": task["kind"],
        "status": task["status"],
        "requires": list(task["requires"]),
        "title": task["inputs"].get("title", "Core skill"),
    }


def _load_plan(root: Path) -> dict[str, Any]:
    path = _dir(root) / "plan.json"
    if not path.is_file():
        raise SynthesisTaskError("plan_missing", "no synthesis plan; run `farol task plan` first")
    return _read(path)


def _load_task(root: Path, task_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"(?:chapter-\d{2,4}|core|outline)", task_id):
        raise SynthesisTaskError("task_unknown", "unknown task id")
    path = _dir(root) / "tasks" / f"{task_id}.json"
    if not path.is_file():
        raise SynthesisTaskError("task_unknown", "unknown task id")
    return _read(path)


def _save_task(root: Path, task: dict[str, Any]) -> None:
    write_json_atomic(_dir(root) / "tasks" / f"{task['task_id']}.json", task)
    plan = _load_plan(root)
    plan["tasks"] = [_summary(task) if item["task_id"] == task["task_id"] else item for item in plan["tasks"]]
    write_json_atomic(_dir(root) / "plan.json", plan)


def synthesis_status(package: Path | str) -> dict[str, Any]:
    root = _root(package)
    path = _dir(root) / "plan.json"
    if not path.is_file():
        return {"state": "not_planned", "tasks": []}
    plan = _read(path)
    counts: dict[str, int] = {}
    for task in plan["tasks"]:
        counts[task["status"]] = counts.get(task["status"], 0) + 1
    return {
        "state": plan["state"],
        "plan_id": plan["plan_id"],
        "counts": counts,
        "tasks": plan["tasks"],
        "stale_chapters": list(plan.get("stale_chapters", [])),
    }


def mark_stale(package: Path | str, removed_block_ids: set[str]) -> list[str]:
    """Record chapters whose cited blocks disappeared from the corpus."""

    root = _root(package)
    path = _dir(root) / "plan.json"
    if not path.is_file():
        return []
    plan = _read(path)
    stale = set(plan.get("stale_chapters", []))
    for summary in plan["tasks"]:
        if summary["kind"] != "chapter":
            continue
        task = _load_task(root, summary["task_id"])
        if {item["block_id"] for item in task["inputs"]["blocks"]} & set(removed_block_ids):
            stale.add(summary["task_id"])
    plan["stale_chapters"] = sorted(stale)
    write_json_atomic(path, plan)
    return plan["stale_chapters"]


def _refresh(root: Path) -> dict[str, Any]:
    """Reopen only stale chapters (with the current text of their sections) and the core."""

    plan = _load_plan(root)
    stale = list(plan.get("stale_chapters", []))
    if not stale:
        return plan
    documents, _skipped = package_documents(root)
    current = {
        block["block_id"]: {**block, "path": document["path"], "document_id": document["document_id"]}
        for document in documents
        for block in document["blocks"]
        if block.get("kind") not in _CONTEXT_KINDS and (block.get("text") or "").strip() and block.get("risk") != "high"
    }
    claimed = {
        item["block_id"]
        for summary in plan["tasks"]
        if summary["kind"] == "chapter" and summary["task_id"] not in stale
        for item in _load_task(root, summary["task_id"])["inputs"]["blocks"]
    }
    counter = max(
        (
            int(item["ref"][1:])
            for summary in plan["tasks"]
            if summary["kind"] == "chapter"
            for item in _load_task(root, summary["task_id"])["inputs"]["blocks"]
        ),
        default=0,
    )
    for task_id in stale:
        task = _load_task(root, task_id)
        sections = {
            (item.get("citation", "").split(":")[0], tuple(item["heading_path"])) for item in task["inputs"]["blocks"]
        }
        kept = [block_id for block_id in (item["block_id"] for item in task["inputs"]["blocks"]) if block_id in current]
        extra = [
            block_id
            for block_id, block in current.items()
            if block_id not in claimed
            and block_id not in kept
            and (block["path"], tuple(block.get("heading_path") or [])) in sections
        ]
        blocks = [current[block_id] for block_id in kept + extra]
        rebuilt, counter = _chapter_task(
            int(task_id.split("-")[1]), task["inputs"]["title"], blocks, counter, task["language"]
        )
        rebuilt["inputs"]["file"] = task["inputs"]["file"]
        rebuilt["request_hash"] = content_hash({key: value for key, value in rebuilt.items() if key != "status"})
        write_json_atomic(_dir(root) / "tasks" / f"{task_id}.json", rebuilt)
        claimed.update(item["block_id"] for item in rebuilt["inputs"]["blocks"])
    core = _load_task(root, "core")
    core["status"] = "pending"
    core.pop("output_hash", None)
    write_json_atomic(_dir(root) / "tasks" / "core.json", core)
    plan = _load_plan(root)
    plan["tasks"] = [_summary(_load_task(root, item["task_id"])) for item in plan["tasks"]]
    plan["stale_chapters"] = []
    plan["state"] = "awaiting_agent"
    write_json_atomic(_dir(root) / "plan.json", plan)
    return plan


def _render(root: Path, task: dict[str, Any], plan: Mapping[str, Any]) -> dict[str, Any]:
    rendered = dict(task)
    if task["kind"] == "outline":
        listing = "\n".join(
            f"- {item['id']} ({item['tokens']} tokens) {item['title']} — {item['first_sentence']}"
            for item in task["inputs"]["sections"]
        )
        instructions = (
            _template("synthesis-outline.md")
            .replace("{{SLUG}}", plan["slug"])
            .replace("{{CHAPTER_TOKENS}}", str(task["budget"]["chapter_source_tokens"]))
            + "\n"
            + listing
            + "\n"
        )
        rendered["instructions"] = instructions.replace("{{LANGUAGE}}", task["language"])
        return rendered
    if task["kind"] == "chapter":
        body = _template("synthesis-chapter.md")
        blocks = "\n\n".join(
            f"[{item['ref']}] ({item['citation']}){' — flagged suspicious' if item['risk'] == 'suspicious' else ''}\n"
            f"{item['text']}"
            for item in task["inputs"]["blocks"]
        )
        instructions = body + "\n" + blocks + "\n"
    else:
        chapters = []
        for summary in plan["tasks"]:
            if summary["kind"] != "chapter":
                continue
            chapter_task = _load_task(root, summary["task_id"])
            accepted = _dir(root) / "accepted" / summary["task_id"] / "chapter.md"
            text = accepted.read_text(encoding="utf-8") if accepted.is_file() else ""
            chapters.append(
                {
                    "task_id": summary["task_id"],
                    "title": chapter_task["inputs"]["title"],
                    "file": chapter_task["inputs"]["file"],
                    "summary": _section(text, _CHAPTER_SECTIONS["Core idea"])
                    + "\n"
                    + _section(text, _CHAPTER_SECTIONS["Takeaways"]),
                }
            )
        rendered["inputs"] = {**task["inputs"], "chapters": chapters}
        listing = "\n\n".join(f"### {item['title']} (chapters/{item['file']})\n{item['summary']}" for item in chapters)
        instructions = _template("synthesis-core.md").replace("{{SLUG}}", plan["slug"]) + "\n" + listing + "\n"
    rendered["instructions"] = (
        instructions.replace("{{TASK_ID}}", task["task_id"])
        .replace("{{LANGUAGE}}", task["language"])
        .replace("{{OUTPUT_TOKENS}}", str(task["budget"]["output_tokens"]))
    )
    return rendered


def next_task(package: Path | str) -> dict[str, Any] | None:
    """Return the next task the agent should do, with full instructions, or None."""

    root = _root(package)
    plan = _load_plan(root)
    accepted = {task["task_id"] for task in plan["tasks"] if task["status"] == "accepted"}
    for summary in plan["tasks"]:
        if summary["status"] == "accepted":
            continue
        if all(requirement in accepted for requirement in summary["requires"]):
            return _render(root, _load_task(root, summary["task_id"]), plan)
    return None


def _headings(text: str) -> set[str]:
    return {match.group(1).strip().casefold() for match in re.finditer(r"^#{2,3}\s+(.+?)\s*$", text, re.M)}


def _section(text: str, names: Iterable[str]) -> str:
    wanted = {name.casefold() for name in names}
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"^#{2,3}\s+(.+?)\s*$", line)
        if match and match.group(1).strip().casefold() in wanted:
            body = []
            for following in lines[index + 1 :]:
                if re.match(r"^#{1,3}\s", following):
                    break
                body.append(following)
            return "\n".join(body).strip()
    return ""


def _reason(code: str, message: str, **details: Any) -> dict[str, Any]:
    return {"code": code, "message": message, **details}


def _missing_sections(text: str, sections: Mapping[str, tuple[str, ...]]) -> list[dict[str, Any]]:
    present = _headings(text)
    return [
        _reason("missing_section", f"add a '## {name}' section", section=name)
        for name, aliases in sections.items()
        if not present & set(aliases)
    ]


def _unsafe(text: str) -> list[dict[str, Any]]:
    risky = [paragraph for paragraph in re.split(r"\n\s*\n", text) if classify(paragraph).risk == "high"]
    if not risky:
        return []
    return [
        _reason(
            "unsafe_content",
            "remove text that gives instructions to AI agents (source directives must never be copied into skills)",
            excerpt=risky[0][:120],
        )
    ]


def _shingles(text: str, size: int = 12) -> set[str]:
    words = re.findall(r"\w+", text.casefold())
    return {" ".join(words[index : index + size]) for index in range(max(0, len(words) - size + 1))}


def _validate_chapter(task: Mapping[str, Any], text: str) -> list[dict[str, Any]]:
    reasons = _missing_sections(text, _CHAPTER_SECTIONS)
    known = {item["ref"] for item in task["inputs"]["blocks"]}
    cited = [ref.strip() for group in _REF.findall(text) for ref in group.split(",")]
    unknown = sorted(set(cited) - known, key=lambda ref: int(ref[1:]))
    if unknown:
        reasons.append(
            _reason("unknown_reference", "cite only the block references listed in the task", references=unknown)
        )
    words = len(re.findall(r"\w+", text))
    required = max(2, words // 250)
    if len([ref for ref in cited if ref in known]) < required:
        reasons.append(
            _reason(
                "missing_citations",
                f"end factual statements with block references like [b1]; need at least {required}",
                required=required,
            )
        )
    budget = int(task["budget"]["output_tokens"])
    if _tokens(text) > budget:
        reasons.append(_reason("budget_exceeded", f"shorten the chapter to at most {budget} tokens", budget=budget))
    source = "\n".join(item["text"] for item in task["inputs"]["blocks"])
    produced = _shingles(_REF.sub("", text))
    if produced and len(produced & _shingles(source)) / len(produced) > 0.35:
        reasons.append(_reason("verbatim_copy", "paraphrase: too much of the chapter copies the source verbatim"))
    return reasons + _unsafe(text)


def _frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n") or "\n---" not in text[4:]:
        return {}
    block = text[4 : text.index("\n---", 4)]
    values: dict[str, str] = {}
    for line in block.splitlines():
        key, separator, value = line.partition(":")
        if separator and not line.startswith((" ", "\t")):
            values[key.strip()] = value.strip()
    return values


def _validate_core(root: Path, task: Mapping[str, Any], plan: Mapping[str, Any], files: Mapping[str, str]) -> list:
    reasons: list[dict[str, Any]] = []
    for name in _CORE_FILES:
        if not files.get(name, "").strip():
            reasons.append(_reason("missing_file", f"provide {name}", file=name))
    skill = files.get("SKILL.md", "")
    if skill:
        meta = _frontmatter(skill)
        if meta.get("name") != plan["slug"]:
            reasons.append(_reason("frontmatter_invalid", f"frontmatter must contain 'name: {plan['slug']}'"))
        description = meta.get("description", "")
        if not 20 <= len(description) <= 1024:
            reasons.append(
                _reason(
                    "frontmatter_invalid", "frontmatter 'description' must say when to use the skill (20-1024 chars)"
                )
            )
        reasons.extend(_missing_sections(skill, _CORE_SECTIONS))
        rendered = _render(root, dict(task), plan)
        missing = [item["file"] for item in rendered["inputs"]["chapters"] if f"chapters/{item['file']}" not in skill]
        if missing:
            reasons.append(_reason("chapter_links_missing", "link every chapter in '## Chapters'", files=missing))
        budget = int(task["budget"]["output_tokens"])
        if _tokens(skill) > budget:
            reasons.append(_reason("budget_exceeded", f"shorten SKILL.md to at most {budget} tokens", budget=budget))
    for name in ("glossary.md", "patterns.md", "cheatsheet.md"):
        if files.get(name) and not re.search(r"^\s*[-*]\s+\S", files[name], re.M):
            reasons.append(_reason("empty_reference_file", f"{name} needs at least one list item", file=name))
    for content in files.values():
        reasons.extend(_unsafe(content))
    return reasons


def _read_outputs(directory: Path, names: Iterable[str]) -> dict[str, str]:
    base = Path(directory)
    if base.is_symlink() or not base.is_dir():
        raise SynthesisTaskError("output_invalid", "output must be a regular directory")
    files: dict[str, str] = {}
    for name in names:
        path = base / name
        if path.is_symlink():
            raise SynthesisTaskError("output_invalid", f"{name} must not be a symbolic link")
        if path.is_file():
            if path.stat().st_size > MAX_OUTPUT_BYTES:
                raise SynthesisTaskError("output_invalid", f"{name} is larger than {MAX_OUTPUT_BYTES} bytes")
            files[name] = path.read_text(encoding="utf-8")
    return files


def submit_task(package: Path | str, task_id: str, output_dir: Path | str) -> dict[str, Any]:
    """Validate an agent's answer for one task; accept it or explain the rejection."""

    root = _root(package)
    plan = _load_plan(root)
    task = _load_task(root, task_id)
    files = _read_outputs(Path(output_dir), task["output"]["files"])
    digest = content_hash(files)
    if task["status"] == "accepted":
        if task.get("output_hash") == digest:
            return {"status": "accepted", "task_id": task_id, "installed": plan["state"] == "installed"}
        return {
            "status": "rejected",
            "task_id": task_id,
            "reasons": [_reason("already_accepted", "this task was already accepted with different content")],
        }
    accepted = {item["task_id"] for item in plan["tasks"] if item["status"] == "accepted"}
    pending = [requirement for requirement in task["requires"] if requirement not in accepted]
    if pending:
        return {
            "status": "rejected",
            "task_id": task_id,
            "reasons": [_reason("dependencies_pending", "finish the chapter tasks first", pending=pending)],
        }
    if task["kind"] == "outline":
        reasons, chapters = _validate_outline(task, files.get("outline.json"))
    elif task["kind"] == "chapter":
        if "chapter.md" not in files:
            reasons = [_reason("missing_file", "provide chapter.md", file="chapter.md")]
        else:
            reasons = _validate_chapter(task, files["chapter.md"])
    else:
        reasons = _validate_core(root, task, plan, files)
    if reasons:
        return {"status": "rejected", "task_id": task_id, "reasons": reasons}
    target = _dir(root) / "accepted" / task_id
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True)
    for name, content in files.items():
        (target / name).write_text(content, encoding="utf-8")
    task["status"] = "accepted"
    task["output_hash"] = digest
    if task["kind"] == "chapter":
        heading = re.search(r"^#\s+(.+?)\s*$", files["chapter.md"], re.M)
        if heading:
            # The agent's title describes the chapter better than the provisional one.
            number = task["inputs"]["file"].split("-", 1)[0]
            task["inputs"]["title"] = heading.group(1).strip()
            task["inputs"]["file"] = f"{number}-{_slugify(task['inputs']['title'])}.md"
    _save_task(root, task)
    if task["kind"] == "outline":
        _expand_outline(root, task, chapters)
    installed = False
    if task["kind"] == "core":
        _install(root, _load_plan(root))
        installed = True
    return {"status": "accepted", "task_id": task_id, "installed": installed}


def _validate_outline(task: Mapping[str, Any], raw: str | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if raw is None:
        return [_reason("missing_file", "provide outline.json", file="outline.json")], []
    try:
        value = json.loads(raw)
    except ValueError:
        return [_reason("outline_invalid", "outline.json must be valid JSON")], []
    chapters = value.get("chapters") if isinstance(value, dict) else None
    if (
        not isinstance(chapters, list)
        or not chapters
        or not all(
            isinstance(item, dict) and str(item.get("title") or "").strip() and isinstance(item.get("sections"), list)
            for item in chapters
        )
    ):
        return [_reason("outline_invalid", 'use {"chapters": [{"title": "...", "sections": ["s1"]}]}')], []
    known = [item["id"] for item in task["inputs"]["sections"]]
    listed = [str(section) for item in chapters for section in item["sections"]]
    unknown = sorted(set(listed) - set(known), key=listed.index)
    if unknown:
        return [_reason("unknown_sections", "use only the section ids listed in the task", sections=unknown)], []
    duplicates = sorted({section for section in listed if listed.count(section) > 1}, key=listed.index)
    if duplicates:
        return [_reason("duplicate_sections", "each section belongs to exactly one chapter", sections=duplicates)], []
    orphans = [section for section in known if section not in set(listed)]
    if orphans:
        return [_reason("orphan_sections", "assign every section to a chapter", sections=orphans)], []
    sizes = {item["id"]: item["tokens"] for item in task["inputs"]["sections"]}
    limit = int(task["budget"]["chapter_source_tokens"]) * 2
    oversized = [
        item["title"]
        for item in chapters
        if len(item["sections"]) > 1 and sum(sizes[section] for section in item["sections"]) > limit
    ]
    if oversized:
        return [_reason("chapter_too_large", f"split chapters above {limit} source tokens", chapters=oversized)], []
    return [], chapters


def _expand_outline(root: Path, outline: Mapping[str, Any], chapters: list[dict[str, Any]]) -> None:
    documents, _skipped = package_documents(root)
    blocks = {
        block["block_id"]: {**block, "path": document["path"], "document_id": document["document_id"]}
        for document in documents
        for block in document["blocks"]
    }
    sections = {item["id"]: item for item in outline["inputs"]["sections"]}
    plan = _load_plan(root)
    counter = 0
    created: list[dict[str, Any]] = []
    for index, chapter in enumerate(chapters, 1):
        chapter_blocks = [
            blocks[block_id]
            for section in chapter["sections"]
            for block_id in sections[section]["block_ids"]
            if block_id in blocks
        ]
        task, counter = _chapter_task(
            index, str(chapter["title"]).strip(), chapter_blocks, counter, outline["language"]
        )
        task["request_hash"] = content_hash({key: value for key, value in task.items() if key != "status"})
        write_json_atomic(_dir(root) / "tasks" / f"{task['task_id']}.json", task)
        created.append(task)
    core = _load_task(root, "core")
    core["requires"] = [task["task_id"] for task in created]
    write_json_atomic(_dir(root) / "tasks" / "core.json", core)
    summaries = [item for item in plan["tasks"] if item["kind"] == "outline"]
    plan["tasks"] = summaries + [_summary(task) for task in created] + [_summary(core)]
    write_json_atomic(_dir(root) / "plan.json", plan)


def _resolve_refs(text: str, refs: Mapping[str, Mapping[str, Any]]) -> str:
    def replace(match: re.Match[str]) -> str:
        cites = [refs[ref.strip()]["citation"] for ref in match.group(1).split(",") if ref.strip() in refs]
        return "[" + "; ".join(dict.fromkeys(cites)) + "]" if cites else ""

    return _REF.sub(replace, text)


def _claims(text: str, refs: Mapping[str, Mapping[str, Any]], chapter: str) -> list[dict[str, Any]]:
    claims = []
    for piece in re.split(r"(?<=[.!?])\s+|\n", text):
        found = [ref.strip() for group in _REF.findall(piece) for ref in group.split(",") if ref.strip() in refs]
        if found:
            claims.append(
                {
                    "chapter": chapter,
                    "text": _REF.sub("", piece).strip(" -*"),
                    "block_ids": sorted({refs[ref]["block_id"] for ref in found}),
                }
            )
    return claims


def _with_generator(skill: str, slug: str, source: Mapping[str, Any]) -> str:
    meta = _frontmatter(skill)
    body = skill[skill.index("\n---", 4) + 4 :].lstrip("\n") if skill.startswith("---\n") else skill
    description = meta.get("description", "").replace("\n", " ")
    version = source.get("version") or "unspecified"
    header = (
        f"---\nname: {slug}\ndescription: {description}\nmetadata:\n  type: knowledge\n"
        f'  generated_by: {GENERATOR}\n  generator_version: "{GENERATOR_VERSION}"\n---\n\n'
    )
    footer = (
        "\n\n## Source\n\n"
        f"- Version: `{version}`\n"
        f"- License: `{source.get('license') or 'unspecified'}`\n"
        "- Chapter citations point to `rag/documents/...`; use the router and the "
        "`search_knowledge` MCP tool for literal, current facts.\n"
    )
    return header + body.rstrip() + footer


def _install(root: Path, plan: Mapping[str, Any]) -> None:
    manifest = _manifest(root)
    source = manifest.get("source") or {}
    accepted = _dir(root) / "accepted"
    staging_parent = Path(tempfile.mkdtemp(prefix=".skill-", dir=root))
    staging = staging_parent / "skill"
    lineage: list[dict[str, Any]] = []
    try:
        (staging / "chapters").mkdir(parents=True)
        for summary in plan["tasks"]:
            if summary["kind"] != "chapter":
                continue
            task = _load_task(root, summary["task_id"])
            refs = {item["ref"]: item for item in task["inputs"]["blocks"]}
            text = (accepted / summary["task_id"] / "chapter.md").read_text(encoding="utf-8")
            chapter_file = task["inputs"]["file"]
            lineage.extend(_claims(text, refs, chapter_file))
            (staging / "chapters" / chapter_file).write_text(_resolve_refs(text, refs), encoding="utf-8")
        core = accepted / "core"
        (staging / "SKILL.md").write_text(
            _with_generator((core / "SKILL.md").read_text(encoding="utf-8"), plan["slug"], source), encoding="utf-8"
        )
        for name in ("glossary.md", "patterns.md", "cheatsheet.md"):
            shutil.copyfile(core / name, staging / name)
        previous = root / SYNTHESIS_DIR / "previous-skill"
        shutil.rmtree(previous, ignore_errors=True)
        os.replace(root / "skill", previous)
        try:
            os.replace(staging, root / "skill")
            _record_installation(root, plan, lineage)
        except BaseException:
            shutil.rmtree(root / "skill", ignore_errors=True)
            os.replace(previous, root / "skill")
            raise
    finally:
        shutil.rmtree(staging_parent, ignore_errors=True)


def _record_installation(root: Path, plan: Mapping[str, Any], lineage: list[dict[str, Any]]) -> None:
    from .harness import write_harness_manifest
    from .package_validator import validate_package
    from .readiness import skill_fingerprint

    write_json_atomic(
        root / SYNTHESIS_DIR / "lineage.json",
        {"schema_version": 1, "plan_id": plan["plan_id"], "claims": lineage},
    )
    write_json_atomic(
        root / ".docops" / "skill-enrichment.json",
        {
            "schema_version": 1,
            "tool": GENERATOR,
            "version": GENERATOR_VERSION,
            "validated": True,
            "skill_hash": skill_fingerprint(root),
            "plan_id": plan["plan_id"],
            "claims": len(lineage),
        },
    )
    manifest = _manifest(root)
    declared = manifest.get("revisions") if isinstance(manifest.get("revisions"), dict) else {}
    golden = declared.get("golden_revision")
    manifest["revisions"] = {
        **declared,
        **package_revisions(root, golden_revision=golden if isinstance(golden, str) else None),
    }
    readiness = manifest.get("readiness")
    if isinstance(readiness, dict):
        readiness["skill"] = "skill-enriched"
        if "enrichment" in readiness:
            readiness["enrichment"] = "skill-enriched"
    write_json_atomic(root / "manifest.json", manifest)
    write_harness_manifest(root)
    result = validate_package(root)
    if not result.ok:
        codes = ", ".join(sorted({error["code"] for error in result.errors}))
        raise SynthesisTaskError("install_invalid", f"installed skill failed package validation: {codes}")
    plan_path = root / SYNTHESIS_DIR / "plan.json"
    stored = _read(plan_path)
    stored["state"] = "installed"
    stored["skill_hash"] = skill_fingerprint(root)
    write_json_atomic(plan_path, stored)


def skill_rubric(package: Path | str) -> dict[str, Any]:
    """Structural quality rubric R-01 for the package skill."""

    root = _root(package)
    skill_path = root / "skill" / "SKILL.md"
    text = skill_path.read_text(encoding="utf-8") if skill_path.is_file() else ""
    generator = (
        "distilled"
        if f"generated_by: {GENERATOR}" in text
        else "scaffold"
        if "generated_by: docops-structural-generator" in text
        else "external"
    )
    chapters = sorted((root / "skill" / "chapters").glob("*.md"))
    checks = {
        "distilled": generator != "scaffold",
        "frontmatter": bool(_frontmatter(text).get("name") and _frontmatter(text).get("description")),
        "core_sections": not _missing_sections(text, _CORE_SECTIONS),
        "core_budget": _tokens(text) <= CORE_OUTPUT_TOKENS + 200,
        "chapters": bool(chapters)
        and all(not _missing_sections(path.read_text(encoding="utf-8"), _CHAPTER_SECTIONS) for path in chapters),
        "chapter_index": bool(chapters) and all(f"chapters/{path.name}" in text for path in chapters),
        "reference_files": all(
            (root / "skill" / name).is_file()
            and re.search(r"^\s*[-*]\s+\S", (root / "skill" / name).read_text(encoding="utf-8"), re.M)
            for name in ("glossary.md", "patterns.md", "cheatsheet.md")
        ),
        "lineage": (root / SYNTHESIS_DIR / "lineage.json").is_file()
        and bool(_read(root / SYNTHESIS_DIR / "lineage.json").get("claims")),
    }
    return {"passed": all(checks.values()), "generator": generator, "checks": checks}
