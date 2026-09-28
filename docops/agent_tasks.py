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
) -> dict[str, Any]:
    """Create (or keep) the task plan for distilling the package into a skill."""

    root = _root(package)
    manifest = _manifest(root)
    slug = str((manifest.get("source") or {}).get("slug") or root.name)
    language = language or str((manifest.get("source") or {}).get("language") or "en")
    documents, _skipped = package_documents(root)
    corpus = content_hash([document["document_id"] for document in documents])
    plan_id = "synthesis-" + content_hash({"corpus": corpus, "language": language, "budget": task_source_tokens})[:16]
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
    counter = 0
    for index, blocks in enumerate(_slices(documents, task_source_tokens), 1):
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
        title = _title(blocks)
        task_id = f"chapter-{index:02d}"
        tasks.append(
            {
                "schema_version": 1,
                "task_id": task_id,
                "kind": "chapter",
                "status": "pending",
                "requires": [],
                "language": language,
                "budget": {"output_tokens": CHAPTER_OUTPUT_TOKENS},
                "inputs": {"title": title, "file": f"{index:02d}-{_slugify(title)}.md", "blocks": items},
                "output": {"files": ["chapter.md"]},
            }
        )
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
    if not re.fullmatch(r"(?:chapter-\d{2,4}|core)", task_id):
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
    return {"state": plan["state"], "plan_id": plan["plan_id"], "counts": counts, "tasks": plan["tasks"]}


def _render(root: Path, task: dict[str, Any], plan: Mapping[str, Any]) -> dict[str, Any]:
    rendered = dict(task)
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
    if task["kind"] == "chapter":
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
    installed = False
    if task["kind"] == "core":
        _install(root, _load_plan(root))
        installed = True
    return {"status": "accepted", "task_id": task_id, "installed": installed}


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
