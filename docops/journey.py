"""The everyday Farol journey: ``init`` → ``add`` → ``build`` → ``status``.

A project is a directory with a ``farol.json`` listing its sources. Each source
becomes its own knowledge package under ``packages/<id>/`` (one skill per book,
site, paper or repository), built by the governed 2.0 pipeline, indexed by the
local backend and handed to the user's AI agent for skill synthesis. Later
builds are factual updates, so a distilled skill is never overwritten.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .storage import write_json_atomic

PROJECT_FILE = "farol.json"
STATE_FILE = Path(".farol") / "state.json"
PACKAGES_DIR = "packages"
DOWNLOADS_DIR = Path(".farol") / "downloads"
ARXIV_BASE = "https://arxiv.org"
_ARXIV = re.compile(r"^(?:arxiv:\s*|https?://(?:www\.)?arxiv\.org/(?:abs|pdf)/)(\d{4}\.\d{4,5}(?:v\d+)?)", re.I)
_CC_LICENSE = re.compile(r"creativecommons\.org/(licenses|publicdomain)/([a-z-]+)/(\d\.\d)", re.I)


class JourneyError(ValueError):
    def __init__(self, code: str, message: str, *, next_action: str | None = None) -> None:
        self.code = code
        self.next_action = next_action
        super().__init__(message)


@dataclass(frozen=True)
class Project:
    root: Path
    config: dict[str, Any]

    @property
    def packages(self) -> Path:
        return self.root / PACKAGES_DIR

    def package(self, source_id: str) -> Path:
        return self.packages / source_id


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")[:48] or "source"


def load_project(root: Path | str, *, create: bool = False, language: str | None = None) -> Project:
    root = Path(root).resolve()
    path = root / PROJECT_FILE
    if path.is_file():
        config = json.loads(path.read_text(encoding="utf-8"))
        if config.get("schema_version") != 1:
            raise JourneyError(
                "project_version_unsupported",
                f"{PROJECT_FILE} uses schema {config.get('schema_version')!r}; this Farol reads schema 1",
                next_action="upgrade Farol (pipx upgrade farol-kit)",
            )
        return Project(root, config)
    if not create:
        raise JourneyError("project_missing", f"no {PROJECT_FILE} in {root.name}", next_action="farol add <source>")
    config = {"schema_version": 1, "name": _slug(root.name), "language": language or "en", "sources": []}
    root.mkdir(parents=True, exist_ok=True)
    write_json_atomic(path, config)
    return Project(root, config)


def init_project(root: Path | str, *, language: str | None = None) -> dict[str, Any]:
    project = load_project(root, create=True, language=language)
    return {"status": "ok", "project": project.config["name"], "path": PROJECT_FILE}


def _source_id(value: str, taken: set[str]) -> str:
    parsed = urlsplit(value)
    if parsed.scheme in {"http", "https"}:
        parts = [parsed.hostname or "web", *[part for part in parsed.path.split("/") if part][-1:]]
        base = _slug("-".join(parts).removesuffix(".git"))
    else:
        base = _slug(Path(value).stem if Path(value).suffix else Path(value).name)
    candidate, counter = base, 2
    while candidate in taken:
        candidate, counter = f"{base}-{counter}", counter + 1
    return candidate


def add_source(
    root: Path | str,
    value: str,
    *,
    license: str | None = None,
    name: str | None = None,
    redistribution: str | None = None,
) -> dict[str, Any]:
    project = load_project(root, create=True)
    from .transcripts import youtube_id

    arxiv = _ARXIV.match(value.strip())
    video = youtube_id(value)
    parsed = urlsplit(value)
    if arxiv:
        value = f"arXiv:{arxiv.group(1)}"
    elif video:
        value = f"https://www.youtube.com/watch?v={video}"
    elif parsed.scheme not in {"http", "https"}:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        if not path.exists():
            raise JourneyError("source_not_found", f"{value} does not exist")
        if path == project.root or path.is_relative_to(project.packages):
            raise JourneyError("source_inside_packages", "add a source outside the project's packages folder")
        value = str(path)
    existing = next((source for source in project.config["sources"] if source["input"] == value), None)
    if existing:
        return {"status": "unchanged", "source": existing}
    taken = {source["id"] for source in project.config["sources"]}
    if name:
        source_id = _slug(name)
    elif arxiv:
        source_id = _slug(f"arxiv-{arxiv.group(1)}")
    elif video:
        source_id = _slug(f"youtube-{video}")
    else:
        source_id = _source_id(value, taken)
    if source_id in taken:
        raise JourneyError("source_id_taken", f"a source named {source_id!r} already exists")
    source = {
        "id": source_id,
        "kind": "arxiv" if arxiv else "youtube" if video else "url" if parsed.scheme in {"http", "https"} else "path",
        "input": value,
        "license": license,
        "redistribution": redistribution or "private-only",
        "added_at": _now(),
    }
    project.config["sources"].append(source)
    write_json_atomic(project.root / PROJECT_FILE, project.config)
    return {"status": "added", "source": source}


def _state(project: Project) -> dict[str, Any]:
    path = project.root / STATE_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"schema_version": 1, "sources": {}}


def _fetch(url: str) -> bytes:
    import urllib.request

    request = urllib.request.Request(
        url, headers={"User-Agent": "farol (+https://github.com/VIDORETTO/farol-rag-skill-docs)"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310 - https/file only
        return response.read(200 * 1024 * 1024)


def _acquire_arxiv(project: Project, source: dict[str, Any]) -> str:
    """Download an arXiv paper once and record its declared license and title."""

    import os

    identifier = source["input"].split(":", 1)[1]
    base = os.environ.get("FAROL_ARXIV_MIRROR", ARXIV_BASE).rstrip("/")
    folder = project.root / DOWNLOADS_DIR / source["id"]
    pdf = folder / f"{source['id']}.pdf"
    if not pdf.is_file():
        folder.mkdir(parents=True, exist_ok=True)
        page = _fetch(f"{base}/abs/{identifier}").decode("utf-8", errors="replace")
        pdf.write_bytes(_fetch(f"{base}/pdf/{identifier}"))
        license_match = _CC_LICENSE.search(page)
        if not source.get("license"):
            if license_match and license_match.group(1).lower() == "licenses":
                source["license"] = f"CC-{license_match.group(2).upper()}-{license_match.group(3)}"
            elif license_match:
                source["license"] = "CC0-1.0"
            elif "nonexclusive-distrib" in page:
                source["license"] = "arXiv-nonexclusive-distrib-1.0"
        title = re.search(r'<h1 class="title[^"]*">(?:<span[^>]*>)?\s*(?:Title:)?\s*(?:</span>)?(.*?)</h1>', page, re.S)
        if title:
            source["title"] = re.sub(r"<[^>]+>|\s+", " ", title.group(1)).strip()
        write_json_atomic(project.root / PROJECT_FILE, project.config)
    return str(folder)


def _acquire_youtube(project: Project, source: dict[str, Any]) -> str:
    """Fetch captions, chapters and the declared license once; store the transcript."""

    from . import transcripts

    folder = project.root / DOWNLOADS_DIR / source["id"]
    document = folder / f"{source['id']}.md"
    if not document.is_file():
        languages = list(dict.fromkeys([str(project.config.get("language") or "en").split("-")[0], "en"]))
        video = transcripts.fetch_youtube(source["input"], languages=languages)
        folder.mkdir(parents=True, exist_ok=True)
        document.write_text(transcripts.youtube_markdown(source["input"], video), encoding="utf-8")
        if not source.get("license"):
            source["license"] = transcripts.youtube_license(video.get("license"))
        source["title"] = video.get("title")
        write_json_atomic(project.root / PROJECT_FILE, project.config)
    return str(folder)


def _build_one(project: Project, source: dict[str, Any]) -> dict[str, Any]:
    import docops

    from .agent_tasks import plan_synthesis, synthesis_status
    from .package_index import build_package_index
    from .transcripts import TranscriptError

    package = project.package(source["id"])
    existing = (package / "manifest.json").is_file()
    input_value = source["input"]
    try:
        if source.get("kind") == "arxiv":
            input_value = _acquire_arxiv(project, source)
        elif source.get("kind") == "youtube":
            input_value = _acquire_youtube(project, source)
    except TranscriptError as exc:
        return {"ok": False, "errors": [{"code": exc.code, "message": str(exc)}]}
    except OSError as exc:
        return {"ok": False, "errors": [{"code": "download_failed", "message": f"download failed: {exc}"}]}
    source_root = Path(input_value).parent if not urlsplit(input_value).scheme else None
    options: dict[str, Any] = {
        "output_dir": package,
        "slug": source["id"],
        "license": source.get("license") or None,
        "redistribution": source.get("redistribution"),
        "language": project.config.get("language"),
    }
    if source_root is not None:
        options["source_root"] = source_root
    if existing:
        # Factual refresh: keeps a distilled (or scaffold) skill byte for byte.
        options.update(mode="update", layers=("factual",))
    request = docops.OperationRequest(input_value, docops.OperationOptions(**options))
    result = docops.apply(docops.plan(request))
    if not result.ok:
        return {
            "ok": False,
            "errors": [{"code": error.get("code"), "message": error.get("message")} for error in result.errors],
        }
    index = build_package_index(package)
    synthesis = synthesis_status(package)
    # Never discard accepted agent work: replan only when nothing was accepted yet.
    if synthesis["state"] == "not_planned" or (
        synthesis["state"] == "awaiting_agent" and not synthesis.get("counts", {}).get("accepted")
    ):
        plan_synthesis(package, language=project.config.get("language"))
    return {"ok": True, "index": {key: index[key] for key in ("documents", "blocks", "index_revision")}}


def _progress(message: str) -> None:
    """Human progress on stderr; stdout stays reserved for results (and --json)."""

    import sys

    print(message, file=sys.stderr, flush=True)


def build(root: Path | str, *, source_ids: list[str] | None = None) -> dict[str, Any]:
    import time

    project = load_project(root)
    if not project.config["sources"]:
        raise JourneyError("no_sources", "the project has no sources", next_action="farol add <source>")
    state = _state(project)
    results: dict[str, Any] = {}
    selected = [source for source in project.config["sources"] if not source_ids or source["id"] in source_ids]
    for position, source in enumerate(selected, 1):
        prefix = f"[{position}/{len(selected)}] {source['id']}"
        _progress(f"{prefix}: extracting and indexing")
        started = time.monotonic()
        outcome = _build_one(project, source)
        elapsed = time.monotonic() - started
        if outcome["ok"]:
            blocks = outcome["index"]["blocks"]
            _progress(f"{prefix}: done in {elapsed:.1f}s ({blocks} blocks)")
        else:
            _progress(f"{prefix}: failed ({outcome['errors'][0]['code']})")
        state["sources"][source["id"]] = {"last_build": _now(), **outcome}
        results[source["id"]] = outcome
    write_json_atomic(project.root / STATE_FILE, state)
    report = status(project.root)
    report["built"] = results
    report["ok"] = all(outcome["ok"] for outcome in results.values())
    return report


def _source_status(project: Project, source: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    from .agent_tasks import synthesis_status

    package = project.package(source["id"])
    warnings = []
    if not source.get("license"):
        warnings.append("license not declared: the package is for local, private use only")
    elif str(source["license"]).startswith("arXiv-nonexclusive"):
        warnings.append("arXiv non-exclusive license: keep the package private; do not redistribute")
    elif source["license"] == "YouTube-Standard":
        warnings.append("Standard YouTube license: personal use only; do not redistribute the transcript")
    last = state["sources"].get(source["id"])
    entry: dict[str, Any] = {"id": source["id"], "input": source["input"], "warnings": warnings}
    if last and not last.get("ok"):
        entry.update(state="failed", errors=last.get("errors", []), next_action="fix the source, then farol build")
        return entry
    if not (package / "rag" / "local-index" / "ACTIVE.json").is_file():
        entry.update(state="added", next_action="farol build")
        return entry
    synthesis = synthesis_status(package)
    relative = package.relative_to(project.root).as_posix()
    if synthesis["state"] == "installed" and synthesis.get("stale_chapters"):
        entry.update(
            state="stale",
            stale_chapters=synthesis["stale_chapters"],
            next_action=f"farol task plan --refresh --package {relative}",
        )
    elif synthesis["state"] == "installed":
        entry.update(state="ready", next_action=None)
    else:
        counts = synthesis.get("counts", {})
        entry.update(
            state="awaiting_agent",
            tasks={"accepted": counts.get("accepted", 0), "total": sum(counts.values())},
            next_action=f"farol task next --package {relative}",
        )
    return entry


def status(root: Path | str) -> dict[str, Any]:
    project = load_project(root)
    state = _state(project)
    sources = [_source_status(project, source, state) for source in project.config["sources"]]
    order = ("failed", "added", "awaiting_agent", "stale", "ready")
    overall = next((name for name in order if any(item["state"] == name for item in sources)), "empty")
    if not sources:
        next_action = "farol add <source>"
    elif overall in {"failed", "added"}:
        next_action = "farol build"
    elif overall in {"awaiting_agent", "stale"}:
        next_action = next(item["next_action"] for item in sources if item["state"] == overall)
    else:
        next_action = "farol mcp --project ."
    return {
        "schema_version": 1,
        "project": project.config["name"],
        "state": overall,
        "sources": sources,
        "next_action": next_action,
    }


def project_packages(root: Path | str) -> dict[str, Path]:
    """Packages of a project that have an active factual index, by source id."""

    project = load_project(root)
    return {
        source["id"]: project.package(source["id"])
        for source in project.config["sources"]
        if (project.package(source["id"]) / "rag" / "local-index" / "ACTIVE.json").is_file()
    }


def project_health(root: Path | str, *, fix: bool = False) -> dict[str, Any]:
    """Check each built source's factual index; optionally rebuild damaged ones."""

    from .backends.base import BackendError, QueryRequest
    from .package_index import build_package_index, open_package_index

    project = load_project(root)
    issues: list[dict[str, Any]] = []
    fixed: list[dict[str, Any]] = []
    for source in project.config["sources"]:
        package = project.package(source["id"])
        if not (package / "manifest.json").is_file():
            continue
        problem = None
        try:
            backend, index = open_package_index(package)
            backend.query(index, QueryRequest(query="health check", top_k=1))
        except BackendError as exc:
            problem = "index_missing" if exc.code == "index_missing" else "index_unreadable"
        except Exception:  # a damaged SQLite file surfaces as a database error
            problem = "index_unreadable"
        if problem is None:
            continue
        if fix:
            build_package_index(package)
            fixed.append({"source": source["id"], "action": "rebuilt_index"})
        else:
            issues.append({"source": source["id"], "code": problem, "next_action": "farol doctor --fix"})
    return {"ok": not issues, "issues": issues, "fixed": fixed}


def _indexed_blocks(package: Path) -> set[str]:
    import sqlite3
    from contextlib import closing

    pointer = package / "rag" / "local-index" / "ACTIVE.json"
    if not pointer.is_file():
        return set()
    revision = json.loads(pointer.read_text(encoding="utf-8")).get("index_revision")
    path = package / "rag" / "local-index" / f"{revision}.sqlite"
    try:
        with closing(sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)) as connection:
            return {row[0] for row in connection.execute("SELECT block_id FROM blocks")}
    except sqlite3.Error:
        return set()


def sync(root: Path | str, *, source_ids: list[str] | None = None) -> dict[str, Any]:
    """Refresh every source and report what changed and which skill chapters went stale."""

    from .agent_tasks import mark_stale

    project = load_project(root)
    before = {
        source["id"]: _indexed_blocks(project.package(source["id"]))
        for source in project.config["sources"]
        if not source_ids or source["id"] in source_ids
    }
    report = build(root, source_ids=source_ids)
    changes: dict[str, dict[str, Any]] = {}
    for source_id, previous in before.items():
        package = project.package(source_id)
        current = _indexed_blocks(package)
        removed = previous - current
        added = current - previous
        state = "no_change" if previous and not removed and not added else "changed" if previous else "new"
        changes[source_id] = {"state": state, "added": len(added), "removed": len(removed)}
        if removed:
            mark_stale(package, removed)
    refreshed = status(root)
    for entry in refreshed["sources"]:
        if entry["id"] in changes:
            entry["changes"] = changes[entry["id"]]
    refreshed["ok"] = report["ok"]
    refreshed["built"] = report["built"]
    return refreshed


def schedule_lines(root: Path | str, kind: str) -> str:
    """Exact scheduler configuration for a daily `farol sync` (printed, never installed)."""

    import sys

    project = Path(root).resolve()
    command = f"{sys.executable} -m docops sync --project {project}"
    if kind == "cron":
        return (
            "# Add with `crontab -e` (runs daily at 03:00):\n"
            f"0 3 * * * cd {project} && {command} >> {project / '.farol' / 'sync.log'} 2>&1\n"
        )
    if kind == "systemd":
        return (
            "# ~/.config/systemd/user/farol-sync.service\n[Unit]\nDescription=Farol sync\n\n[Service]\n"
            f"Type=oneshot\nWorkingDirectory={project}\nExecStart={command}\n\n"
            "# ~/.config/systemd/user/farol-sync.timer\n[Unit]\nDescription=Daily Farol sync\n\n[Timer]\n"
            "OnCalendar=daily\nPersistent=true\n\n[Install]\nWantedBy=timers.target\n\n"
            "# then: systemctl --user enable --now farol-sync.timer\n"
        )
    if kind == "windows":
        return f'schtasks /Create /SC DAILY /ST 03:00 /TN "Farol sync" /TR "{command}"\n'
    raise JourneyError("schedule_unknown", "choose cron, systemd or windows")
