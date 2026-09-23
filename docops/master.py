"""Deterministic project orchestration for the master-evolution contracts.

The project layer is deliberately small and provider-free.  It owns private
project state, immutable revisions, governance overlays and coordination
receipts; package generation, external RAGFlow and publication remain behind their existing
public seams.
"""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import sqlite3
import tempfile
import threading
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .contracts import validate_artifact
from .package_validator import validate_package
from .revisions import canonical_json, content_hash, file_hash, package_revisions, tree_hash
from .storage import write_json_atomic, write_text_atomic

SCHEMA_VERSION = 1
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_RFC3339 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")
_PURPOSES = (
    "acquisition",
    "storage",
    "indexing",
    "internal_query",
    "quotation",
    "derivatives",
    "redistribution",
)
_SOURCE_TYPES = {
    "official_documentation",
    "policy",
    "article",
    "study",
    "experiment",
    "video_transcript",
    "other",
    "unknown",
}
_AUTHORITY_CLASSES = {"official", "research", "practitioner", "community", "unknown"}
_CLAIM_TYPES = {
    "official_rule",
    "factual_observation",
    "opinion",
    "experience",
    "hypothesis",
    "recommendation",
}
_CHANGE_TYPES = {
    "source_add",
    "source_update",
    "source_withdraw",
    "source_revoke",
    "skill_request",
    "policy_change",
    "decision_correct",
    "conflict_record",
}
_NODE_KINDS = {
    "source_revision",
    "claim",
    "rag_document",
    "skill",
    "decision",
}
_VALIDITY_FIELDS = {"from", "until", "checked_at", "review_after"}
_MASTER_ROOT_LOCK = threading.RLock()
_PROJECT_LOCKS: dict[str, threading.RLock] = {}
_KIND_TO_CONTRACT = {
    "project": "project",
    "init_session": "init-session",
    "project_revision": "project-revision",
    "brief": "brief",
    "decisions": "decisions",
    "policy": "policy",
    "dependencies": "dependencies",
    "source_governance_registry": "source-governance",
    "claim": "claim",
    "conflict": "conflict",
    "change_proposal": "change-proposal",
    "impact_report": "impact-report",
    "backup_manifest": "backup-manifest",
    "enrichment_request": "project-enrichment-request",
    "delegated_authorization": "delegated-authorization",
    "supervisor_status": "supervisor-status",
    "rag_candidate_receipt": "project-rag-candidate-receipt",
}


class MasterProjectError(ValueError):
    """Structured error raised at the new project public seam."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        field: str | None = None,
        retryable: bool = False,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.field = field
        self.retryable = retryable
        self.details = dict(details or {})
        super().__init__(message)


def _iso(value: datetime | date | str | None = None) -> str:
    if value is None:
        current = datetime.now(timezone.utc)
    elif isinstance(value, datetime):
        current = value
    elif isinstance(value, date):
        current = datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    else:
        text = str(value).strip()
        if not text:
            raise MasterProjectError("INVALID_INPUT", "timestamp must not be empty")
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            current = datetime.fromisoformat(text)
        except ValueError as exc:
            raise MasterProjectError("INVALID_INPUT", "timestamp must be RFC3339", field="now") from exc
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _datetime(value: datetime | date | str | None = None) -> datetime:
    text = _iso(value)
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _root(value: Path | str) -> Path:
    root = Path(os.path.abspath(os.fspath(Path(value).expanduser())))
    if root.exists() and root.is_symlink():
        raise MasterProjectError("INVALID_INPUT", "project root must not be a symbolic link")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _package_root(root: Path) -> Path:
    candidate = root / "package"
    return candidate if candidate.is_dir() else root


def _meta(root: Path) -> Path:
    value = root / ".docops-project"
    value.mkdir(parents=True, exist_ok=True)
    return value


def _lock_for(root: Path) -> threading.RLock:
    key = str(root.resolve()).casefold()
    with _MASTER_ROOT_LOCK:
        return _PROJECT_LOCKS.setdefault(key, threading.RLock())


@contextmanager
def _project_lock(root: Path) -> Iterable[None]:
    lock = _lock_for(root)
    lock.acquire()
    try:
        yield
    finally:
        lock.release()


def _read_json(path: Path, *, required: bool = False) -> Any:
    if path.is_symlink():
        raise MasterProjectError("INVALID_INPUT", f"state file must not be a symbolic link: {path.name}")
    if not path.is_file():
        if required:
            raise MasterProjectError("INVALID_INPUT", f"state file is missing: {path.name}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MasterProjectError("INVALID_INPUT", f"state file is unreadable: {path.name}") from exc


def _doc(kind: str, identifier: str, payload: Mapping[str, Any], *, now: str | None = None) -> dict[str, Any]:
    if not _ID.fullmatch(identifier):
        raise MasterProjectError("INVALID_INPUT", f"invalid opaque identifier for {kind}")
    value: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "id": identifier,
        "created_at": _iso(now),
        **copy.deepcopy(dict(payload)),
    }
    value["content_hash"] = content_hash(value)
    return value


def _verify_doc(value: Any, *, expected_kind: str | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MasterProjectError("INVALID_INPUT", "persisted state must be a JSON object")
    if value.get("schema_version") != SCHEMA_VERSION:
        raise MasterProjectError("UNSUPPORTED_SCHEMA_VERSION", "persisted state schema version is not supported")
    if expected_kind and value.get("kind") != expected_kind:
        raise MasterProjectError("INVALID_INPUT", f"expected {expected_kind} state")
    stored = value.get("content_hash")
    candidate = dict(value)
    candidate.pop("content_hash", None)
    if not isinstance(stored, str) or not _HEX64.fullmatch(stored) or content_hash(candidate) != stored:
        raise MasterProjectError("INVALID_INPUT", "persisted state content hash is invalid")
    if expected_kind:
        contract_name = _KIND_TO_CONTRACT.get(expected_kind)
        if contract_name:
            contract = validate_artifact(contract_name, value)
            if not contract.ok:
                raise MasterProjectError(
                    "INVALID_INPUT",
                    f"persisted {expected_kind} state violates its contract",
                    details={"errors": contract.errors},
                )
    return value


def _write_doc(path: Path, value: Mapping[str, Any]) -> None:
    contract_name = _KIND_TO_CONTRACT.get(str(value.get("kind")))
    if contract_name:
        contract = validate_artifact(contract_name, dict(value))
        if not contract.ok:
            raise MasterProjectError(
                "INVALID_INPUT",
                f"{contract_name} document violates its contract",
                details={"errors": contract.errors},
            )
    write_json_atomic(path, dict(value))


def _project_file(root: Path) -> Path:
    return root / "project.json"


def _session_file(root: Path) -> Path:
    return root / "init" / "session.json"


def _load_project(root: Path) -> dict[str, Any]:
    return _verify_doc(_read_json(_project_file(root), required=True), expected_kind="project")


def _load_session(root: Path, session_id: str | None = None) -> dict[str, Any]:
    session = _verify_doc(_read_json(_session_file(root), required=True), expected_kind="init_session")
    if session_id is not None and session.get("session_id") != session_id:
        raise MasterProjectError("INVALID_INPUT", "session does not belong to this project", field="session_id")
    return session


def _request_hash(operation: str, payload: Mapping[str, Any]) -> str:
    return content_hash({"operation": operation, "payload": dict(payload)})


def _idempotency_path(root: Path) -> Path:
    # Reads must not create project metadata: dry-run and inspection are no-op
    # operations until a mutating receipt is actually persisted.
    return root / ".docops-project" / "idempotency.json"


def _idempotency_records(root: Path) -> dict[str, Any]:
    value = _read_json(_idempotency_path(root))
    if value is None:
        return {"schema_version": SCHEMA_VERSION, "records": {}}
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != SCHEMA_VERSION
        or not isinstance(value.get("records"), dict)
    ):
        raise MasterProjectError("INVALID_INPUT", "idempotency ledger is invalid")
    return value


def _idempotency_replay(root: Path, key: str | None, request_hash: str) -> dict[str, Any] | None:
    if key is None:
        return None
    if not isinstance(key, str) or not key.strip() or len(key) > 256:
        raise MasterProjectError("INVALID_INPUT", "idempotency_key must be a non-empty string", field="idempotency_key")
    records = _idempotency_records(root).get("records", {})
    prior = records.get(key)
    if prior is None:
        return None
    if not isinstance(prior, dict) or prior.get("request_hash") != request_hash:
        raise MasterProjectError("IDEMPOTENCY_CONFLICT", "idempotency key was already used with another payload")
    response = prior.get("response")
    if not isinstance(response, dict):
        raise MasterProjectError("INVALID_INPUT", "idempotency record has no response")
    return copy.deepcopy(response)


def _idempotency_store(root: Path, key: str | None, request_hash: str, response: Mapping[str, Any]) -> None:
    if key is None:
        return
    payload = _idempotency_records(root)
    records = payload.setdefault("records", {})
    records[key] = {"request_hash": request_hash, "response": copy.deepcopy(dict(response))}
    write_json_atomic(_idempotency_path(root), payload)


def _error(error: MasterProjectError | Exception, *, fallback: str = "INVALID_INPUT") -> dict[str, Any]:
    code = getattr(error, "code", fallback)
    return {
        "code": str(code),
        "message": str(error),
        "retryable": bool(getattr(error, "retryable", False)),
        "field": getattr(error, "field", None),
    }


def _envelope(
    *,
    ok: bool,
    outcome: str,
    project_id: str | None = None,
    session_revision: int | None = None,
    operation_id: str | None = None,
    data: Mapping[str, Any] | None = None,
    errors: Iterable[Mapping[str, Any]] = (),
    next_actions: Iterable[str] = (),
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": ok,
        "operation_id": operation_id or f"op-{uuid.uuid4().hex}",
        "project_id": project_id,
        "session_revision": session_revision,
        "outcome": outcome,
        "data": copy.deepcopy(dict(data)) if data is not None else None,
        "errors": [dict(value) for value in errors],
        "next_actions": list(next_actions),
    }


def _failure(exc: Exception, *, project_id: str | None = None, session_revision: int | None = None) -> dict[str, Any]:
    if isinstance(exc, MasterProjectError):
        code = exc.code
        outcome = (
            "blocked"
            if code
            in {
                "STALE_REVISION",
                "IDEMPOTENCY_CONFLICT",
                "LEASE_BUSY",
                "DECISION_REQUIRED",
                "RIGHTS_BLOCKED",
                "PRIVACY_BLOCKED",
                "DEPENDENCY_UNKNOWN",
                "EVIDENCE_STALE",
                "SOURCE_REVOKED",
                "RECOVERY_REQUIRED",
                "FEATURE_NOT_ENABLED",
                "UNSUPPORTED_SCHEMA_VERSION",
                "SOURCE_UNAVAILABLE",
            }
            else "failed"
        )
    else:
        code = "INVALID_INPUT"
        outcome = "failed"
    return _envelope(
        ok=False,
        outcome=outcome,
        project_id=project_id,
        session_revision=session_revision,
        errors=[_error(exc)],
    )


def _answer_values(session: Mapping[str, Any]) -> dict[str, Any]:
    raw = session.get("answers", [])
    if isinstance(raw, Mapping):
        return dict(raw)
    values: dict[str, Any] = {}
    if isinstance(raw, list):
        for answer in raw:
            if isinstance(answer, Mapping) and isinstance(answer.get("question_key"), str):
                values[answer["question_key"]] = answer.get("value")
    return values


def _answer_records(session: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = session.get("answers", [])
    if isinstance(raw, list):
        return [dict(item) for item in raw if isinstance(item, Mapping)]
    if isinstance(raw, Mapping):
        return [
            {
                "question_key": str(key),
                "value": value,
                "origin": "imported_confirmed",
                "evidence_ref": f"legacy-session:{session.get('session_id')}",
            }
            for key, value in raw.items()
        ]
    return []


def _answer_is_confirmed(session: Mapping[str, Any], answers: Mapping[str, Any], key: str) -> bool:
    """Return whether a product answer has an explicit confirmation origin."""

    if key not in answers:
        return False
    for record in reversed(_answer_records(session)):
        if record.get("question_key") == key:
            return record.get("origin") in {"user_explicit", "imported_confirmed"}
    return False


def _confirmed_answer_value(session: Mapping[str, Any], answers: Mapping[str, Any], key: str) -> Any:
    """Expose an answer to an artifact only after an explicit confirmation."""

    if not _answer_is_confirmed(session, answers, key):
        return None
    return copy.deepcopy(answers.get(key))


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _deliverables(session: Mapping[str, Any], answers: Mapping[str, Any]) -> list[str]:
    raw = answers.get("deliverables", session.get("requested_deliverables", ["knowledge"]))
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list) or not raw:
        return ["knowledge"]
    values = list(dict.fromkeys(str(item) for item in raw))
    # Farol 2.0 removed the editorial deliverables; ``knowledge`` is the only
    # deliverable the project contract carries.
    invalid = sorted(set(values) - {"knowledge"})
    if invalid:
        raise MasterProjectError("INVALID_INPUT", f"unknown deliverable(s): {', '.join(invalid)}", field="deliverables")
    return ["knowledge"]


def _question(key: str, prompt: str, reason: str, blocks: list[str], *, required: bool) -> dict[str, Any]:
    return {"key": key, "prompt": prompt, "reason": reason, "blocks": blocks, "required": required}


def _pending_questions(session: Mapping[str, Any], answers: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if not _is_text(answers.get("name")):
        result.append(_question("name", "Qual é o nome do projeto?", "missing_required", ["draft"], required=True))
    if not _is_text(answers.get("objective")):
        result.append(
            _question(
                "objective",
                "Qual objetivo este projeto deve atender?",
                "missing_required",
                ["draft", "activation"],
                required=True,
            )
        )
    # Farol 2.0 keeps a single ``knowledge`` deliverable; validating it here
    # surfaces an invalid deliverable list as a structured error.
    _deliverables(session, answers)
    return result


def _status_for(session: Mapping[str, Any], answers: Mapping[str, Any]) -> str:
    if session.get("status") in {"finalized", "cancelled"}:
        return str(session["status"])
    pending = _pending_questions(session, answers)
    return "collecting" if any(item.get("required") for item in pending) else "draft_ready"


def _session_projection(session: Mapping[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(dict(session))


def _project_projection(project: Mapping[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(dict(project))


def _check_expected_project_revision(project: Mapping[str, Any], expected_revision: int | None) -> None:
    """Apply the common compare-and-swap guard for project mutations."""

    if expected_revision is not None and project.get("write_revision") != expected_revision:
        raise MasterProjectError("STALE_REVISION", "project write revision does not match", field="expected_revision")


def _advance_project_revision(root: Path, project: Mapping[str, Any]) -> dict[str, Any]:
    """Persist one logical project mutation and return its new immutable projection."""

    updated = dict(project)
    updated["write_revision"] = int(project.get("write_revision", 0)) + 1
    updated.pop("content_hash", None)
    updated["content_hash"] = content_hash(updated)
    _write_doc(_project_file(root), updated)
    return updated


def _governance_path(root: Path) -> Path:
    return root / ".docops" / "source-governance.json"


def _revocations_path(root: Path) -> Path:
    return root / ".docops" / "revocations.json"


def _evidence_path(root: Path) -> Path:
    return root / ".docops" / "project-evidence.json"


def _changes_root(root: Path) -> Path:
    value = root / "changes"
    value.mkdir(parents=True, exist_ok=True)
    return value


def _package_ref(root: Path) -> dict[str, Any] | None:
    package = _package_root(root)
    manifest_path = package / "manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        return None
    manifest = _read_json(manifest_path)
    if not isinstance(manifest, Mapping):
        return None
    revisions = manifest.get("revisions") if isinstance(manifest.get("revisions"), Mapping) else {}
    try:
        observed = package_revisions(
            package, golden_revision=str(revisions.get("golden_revision")) if revisions.get("golden_revision") else None
        )
    except (OSError, TypeError, ValueError):
        observed = {}
    package_id = manifest.get("package_id") or manifest.get("run_id")
    release_id = revisions.get("release_id") or observed.get("release_id")
    composition = revisions.get("composition_hash") or observed.get("composition_hash")
    if not all(isinstance(value, str) and value for value in (package_id, release_id, composition)):
        return None
    return {
        "package_id": str(package_id),
        "release_id": str(release_id),
        "composition_hash": str(composition),
        "candidate_id": manifest.get("candidate_id") if isinstance(manifest.get("candidate_id"), str) else None,
        "locator": "package" if package != root else ".",
    }


def start_project_init(
    project_root: Path | str,
    input: Mapping[str, Any] | None = None,
    *,
    payload: Mapping[str, Any] | None = None,
    project_id: str | None = None,
    preset: Mapping[str, Any] | None = None,
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Create or resume one private, structured initialization session."""

    root = _root(project_root)
    request = dict(payload or input or {})
    request_hash = _request_hash(
        "init.start",
        {"input": request, "project_id": project_id, "preset": preset, "expected_revision": expected_revision},
    )
    try:
        with _project_lock(root):
            replay = _idempotency_replay(root, idempotency_key, request_hash)
            if replay is not None:
                return replay
            current = _iso(now)
            existing = _read_json(_project_file(root))
            if existing is not None:
                project = _verify_doc(existing, expected_kind="project")
                if expected_revision is not None and project.get("write_revision") != expected_revision:
                    raise MasterProjectError(
                        "STALE_REVISION", "project write revision does not match", field="expected_revision"
                    )
                session = _load_session(root)
                response = _envelope(
                    ok=True,
                    outcome="unchanged",
                    project_id=str(project["project_id"]),
                    session_revision=int(session["session_revision"]),
                    data={"project": _project_projection(project), "session": _session_projection(session)},
                    next_actions=["init status", "init answer"]
                    if session["status"] != "finalized"
                    else ["project change propose"],
                )
                _idempotency_store(root, idempotency_key, request_hash, response)
                return response
            if not isinstance(request, Mapping):
                raise MasterProjectError("INVALID_INPUT", "init input must be a JSON object", field="input")
            if expected_revision not in {None, 0}:
                raise MasterProjectError(
                    "STALE_REVISION", "new project has no matching expected revision", field="expected_revision"
                )
            chosen_id = str(project_id or f"project-{uuid.uuid4().hex}")
            if not _ID.fullmatch(chosen_id):
                raise MasterProjectError(
                    "INVALID_INPUT", "project_id must be an opaque non-empty string", field="project_id"
                )
            answers: dict[str, Any] = {}
            for key in (
                "name",
                "objective",
                "audience",
                "region",
                "language",
                "deliverables",
                "constraints",
            ):
                if key in request:
                    answers[key] = copy.deepcopy(request[key])
            if "deliverables" not in answers:
                answers["deliverables"] = ["knowledge"]
            session_id = f"session-{uuid.uuid4().hex}"
            session_seed = {
                "session_id": session_id,
                "project_id": chosen_id,
                "session_revision": 1,
                "status": "collecting",
                "preset": copy.deepcopy(preset) if isinstance(preset, Mapping) else None,
                "requested_deliverables": _deliverables({"requested_deliverables": answers["deliverables"]}, answers),
                "answers": [
                    {
                        "question_key": key,
                        "value": value,
                        "origin": "imported_confirmed" if key in request else "preset_default",
                        "evidence_ref": f"init:{session_id}:{key}" if key in request else None,
                    }
                    for key, value in answers.items()
                ],
                "decisions": [],
                "pending_questions": [],
                "finalized_revision_id": None,
            }
            pending = _pending_questions(session_seed, answers)
            session_seed["pending_questions"] = pending
            session_seed["status"] = _status_for(session_seed, answers)
            session = _doc("init_session", session_id, session_seed, now=current)
            project = _doc(
                "project",
                chosen_id,
                {
                    "project_id": chosen_id,
                    "name": answers.get("name") if _is_text(answers.get("name")) else "",
                    "active_project_revision_id": None,
                    "working_project_revision_id": None,
                    "package_locator": None,
                    "write_revision": 1,
                    "visibility": "private",
                },
                now=current,
            )
            _write_doc(_project_file(root), project)
            _write_doc(_session_file(root), session)
            outcome = "needs_input" if pending else "applied"
            response = _envelope(
                ok=True,
                outcome=outcome,
                project_id=chosen_id,
                session_revision=1,
                data={"project": _project_projection(project), "session": _session_projection(session)},
                next_actions=["init answer"] if pending else ["init finalize"],
            )
            _idempotency_store(root, idempotency_key, request_hash, response)
            return response
    except MasterProjectError as exc:
        return _failure(exc)
    except (OSError, TypeError, UnicodeError, ValueError) as exc:
        return _failure(MasterProjectError("INVALID_INPUT", str(exc)))


def inspect_project_init(project_root: Path | str, *, session_id: str | None = None) -> dict[str, Any]:
    """Read the minimized project/session state without changing it."""

    root = _root(project_root)
    try:
        project = _load_project(root)
        session = _load_session(root, session_id)
        pending = _pending_questions(session, _answer_values(session))
        data = {
            "project": _project_projection(project),
            "session": _session_projection(session),
            "pending_questions": pending,
            "blocked_deliverables": sorted({block for item in pending for block in item.get("blocks", [])}),
            "allowed_next_actions": ["init answer", "init finalize"]
            if session["status"] != "finalized"
            else ["project change propose"],
        }
        return _envelope(
            ok=True,
            outcome="unchanged",
            project_id=str(project["project_id"]),
            session_revision=int(session["session_revision"]),
            data=data,
        )
    except MasterProjectError as exc:
        return _failure(exc)
    except (OSError, TypeError, UnicodeError, ValueError) as exc:
        return _failure(MasterProjectError("INVALID_INPUT", str(exc)))


def answer_project_init(
    project_root: Path | str,
    input: Mapping[str, Any] | None = None,
    *,
    session_id: str | None = None,
    answers: Mapping[str, Any] | None = None,
    payload: Mapping[str, Any] | None = None,
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Apply structured answers using a compare-and-swap session revision."""

    root = _root(project_root)
    body = dict(payload or input or {})
    answer_values = dict(answers or body.get("answers") or body)
    if "session_id" in answer_values and session_id is None:
        session_id = str(answer_values.pop("session_id"))
    request_hash = _request_hash(
        "init.answer",
        {"session_id": session_id, "answers": answer_values, "expected_revision": expected_revision},
    )
    try:
        with _project_lock(root):
            project = _load_project(root)
            session = _load_session(root, session_id)
            replay = _idempotency_replay(root, idempotency_key, request_hash)
            if replay is not None:
                return replay
            if session["status"] in {"finalized", "cancelled"}:
                raise MasterProjectError("INVALID_INPUT", "terminal init session is read-only", field="session_id")
            expected = session["session_revision"] if expected_revision is None else expected_revision
            if expected != session["session_revision"]:
                raise MasterProjectError("STALE_REVISION", "session revision does not match", field="expected_revision")
            allowed = {
                "name",
                "objective",
                "audience",
                "region",
                "language",
                "deliverables",
                "constraints",
            }
            unknown = sorted(set(answer_values) - allowed - {"origin", "evidence_ref"})
            if unknown:
                raise MasterProjectError("INVALID_INPUT", f"unknown answer key: {unknown[0]}", field=unknown[0])
            values = _answer_values(session)
            records = _answer_records(session)
            decisions = [dict(item) for item in session.get("decisions", []) if isinstance(item, Mapping)]
            current = _iso(now)
            for key, raw in answer_values.items():
                origin = "user_explicit"
                evidence_ref = f"init:{session['session_id']}:{key}"
                value = raw
                if isinstance(raw, Mapping) and "value" in raw:
                    value = raw.get("value")
                    origin = str(raw.get("origin") or origin)
                    evidence_ref = raw.get("evidence_ref") or evidence_ref
                if origin not in {"user_explicit", "imported_confirmed", "agent_proposed", "preset_default"}:
                    raise MasterProjectError("INVALID_INPUT", f"invalid answer origin for {key}", field=key)
                if key == "deliverables":
                    _deliverables(session, {**values, key: value})
                previous = values.get(key)
                values[key] = copy.deepcopy(value)
                records = [record for record in records if record.get("question_key") != key]
                records.append(
                    {
                        "question_key": key,
                        "value": copy.deepcopy(value),
                        "origin": origin,
                        "evidence_ref": evidence_ref,
                    }
                )
                if previous is not None and previous != value:
                    decisions.append(
                        {
                            "decision_id": f"decision-{uuid.uuid4().hex}",
                            "key": key,
                            "value": copy.deepcopy(value),
                            "status": "confirmed" if origin in {"user_explicit", "imported_confirmed"} else "proposed",
                            "actor": "user" if origin == "user_explicit" else origin,
                            "evidence_ref": evidence_ref,
                            "supersedes": next(
                                (
                                    item.get("decision_id")
                                    for item in reversed(decisions)
                                    if item.get("key") == key and item.get("status") != "superseded"
                                ),
                                None,
                            ),
                            "created_at": current,
                        }
                    )
            next_session = dict(session)
            next_session["session_revision"] = int(session["session_revision"]) + 1
            next_session["answers"] = records
            next_session["decisions"] = decisions
            next_session["pending_questions"] = _pending_questions(next_session, values)
            next_session["status"] = _status_for(next_session, values)
            next_session.pop("content_hash", None)
            next_session["content_hash"] = content_hash(next_session)
            next_project = dict(project)
            next_project["write_revision"] = int(project["write_revision"]) + 1
            next_project["name"] = values.get("name") if _is_text(values.get("name")) else project.get("name", "")
            next_project.pop("content_hash", None)
            next_project["content_hash"] = content_hash(next_project)
            _write_doc(_session_file(root), next_session)
            _write_doc(_project_file(root), next_project)
            response = _envelope(
                ok=True,
                outcome="needs_input" if next_session["pending_questions"] else "applied",
                project_id=str(project["project_id"]),
                session_revision=int(next_session["session_revision"]),
                data={"project": _project_projection(next_project), "session": _session_projection(next_session)},
                next_actions=["init answer"] if next_session["pending_questions"] else ["init finalize"],
            )
            _idempotency_store(root, idempotency_key, request_hash, response)
            return response
    except MasterProjectError as exc:
        project_id = None
        try:
            project_id = str(_load_project(root).get("project_id"))
        except MasterProjectError:
            pass
        return _failure(exc, project_id=project_id)
    except (OSError, TypeError, UnicodeError, ValueError) as exc:
        return _failure(MasterProjectError("INVALID_INPUT", str(exc)))


def _relative_project_path(raw: str) -> str:
    value = str(raw).replace("\\", "/")
    candidate = Path(value)
    if candidate.is_absolute() or re.match(r"^[A-Za-z]:", value) or ".." in candidate.parts:
        raise MasterProjectError("INVALID_INPUT", "project artifact path must remain relative")
    return "/".join(part for part in candidate.parts if part not in {"", "."})


def _write_projection(path: Path, title: str, fields: Mapping[str, Any]) -> None:
    lines = [f"# {title}", ""]
    for key, value in fields.items():
        if value is None or value == "":
            continue
        if isinstance(value, list):
            lines.append(f"- {key}: {', '.join(str(item) for item in value)}")
        elif isinstance(value, Mapping):
            lines.append(f"- {key}: {canonical_json(value)}")
        else:
            lines.append(f"- {key}: {value}")
    write_text_atomic(path, "\n".join(lines) + "\n")


def _revision_artifact(
    kind: str, identifier: str, revision_id: str, payload: Mapping[str, Any], *, now: str
) -> dict[str, Any]:
    return _doc(kind, identifier, {"revision_id": revision_id, **dict(payload)}, now=now)


def _artifact_ref(kind: str, artifact: Mapping[str, Any], path: str) -> dict[str, Any]:
    path_parts = _relative_project_path(path).split("/")
    containing_revision = path_parts[1] if len(path_parts) > 1 and path_parts[0] == "revisions" else None
    return {
        "kind": kind,
        "artifact_id": artifact["id"],
        "revision_id": artifact.get("revision_id") or containing_revision,
        "path": _relative_project_path(path),
        "hash": artifact["content_hash"],
    }


def finalize_project_init(
    project_root: Path | str,
    input: Mapping[str, Any] | None = None,
    *,
    session_id: str | None = None,
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Materialize a private immutable project revision and its projections."""

    root = _root(project_root)
    body = dict(input or {})
    session_id = session_id or body.get("session_id")
    expected_revision = expected_revision if expected_revision is not None else body.get("expected_revision")
    request_hash = _request_hash(
        "init.finalize",
        {"session_id": session_id, "expected_revision": expected_revision, "input": body},
    )
    try:
        with _project_lock(root):
            project = _load_project(root)
            session = _load_session(root, str(session_id) if session_id else None)
            replay = _idempotency_replay(root, idempotency_key, request_hash)
            if replay is not None:
                return replay
            if session["status"] == "finalized":
                revision_id = session.get("finalized_revision_id")
                response = _envelope(
                    ok=True,
                    outcome="unchanged",
                    project_id=str(project["project_id"]),
                    session_revision=int(session["session_revision"]),
                    data={
                        "project": _project_projection(project),
                        "session": _session_projection(session),
                        "project_revision_id": revision_id,
                    },
                    next_actions=["project change propose"],
                )
                _idempotency_store(root, idempotency_key, request_hash, response)
                return response
            expected = session["session_revision"] if expected_revision is None else expected_revision
            if expected != session["session_revision"]:
                raise MasterProjectError("STALE_REVISION", "session revision does not match", field="expected_revision")
            values = _answer_values(session)
            pending = _pending_questions(session, values)
            required_pending = [item for item in pending if item.get("required")]
            if required_pending:
                response = _envelope(
                    ok=True,
                    outcome="needs_input",
                    project_id=str(project["project_id"]),
                    session_revision=int(session["session_revision"]),
                    data={"session": _session_projection(session), "pending_questions": pending},
                    next_actions=["init answer"],
                )
                _idempotency_store(root, idempotency_key, request_hash, response)
                return response
            current = _iso(now)
            revision_id = f"project-revision-{uuid.uuid4().hex}"
            revision_dir = root / "revisions" / revision_id
            revision_dir.parent.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix=f".{revision_id}.", dir=str(root / "revisions")))
            try:
                deliverables = _deliverables(session, values)
                open_decision_ids = [
                    str(item.get("decision_id"))
                    for item in session.get("decisions", [])
                    if isinstance(item, Mapping) and item.get("status") in {"pending", "proposed"}
                ]
                brief = _revision_artifact(
                    "brief",
                    f"brief-{uuid.uuid4().hex}",
                    revision_id,
                    {
                        "project_id": project["project_id"],
                        "goal": str(values["objective"]),
                        "audience": values.get("audience"),
                        "region": values.get("region"),
                        "language": values.get("language"),
                        "deliverables": deliverables,
                        "constraints": list(values.get("constraints") or [])
                        if isinstance(values.get("constraints"), list)
                        else [],
                        "open_decision_ids": open_decision_ids,
                    },
                    now=current,
                )
                decisions = _revision_artifact(
                    "decisions",
                    f"decisions-{uuid.uuid4().hex}",
                    revision_id,
                    {"project_id": project["project_id"], "items": copy.deepcopy(session.get("decisions", []))},
                    now=current,
                )
                policy = _revision_artifact(
                    "policy",
                    f"policy-{uuid.uuid4().hex}",
                    revision_id,
                    {
                        "project_id": project["project_id"],
                        "publication_mode": "manual",
                        "delegation_ref": None,
                        "private_draft_only": True,
                        "rights_policy_revision": "unknown",
                        "privacy_policy_revision": "unknown",
                    },
                    now=current,
                )
                dependencies = _revision_artifact(
                    "dependencies",
                    f"dependencies-{uuid.uuid4().hex}",
                    revision_id,
                    {"project_id": project["project_id"], "nodes": [], "edges": []},
                    now=current,
                )
                artifacts: dict[str, dict[str, Any]] = {
                    "brief": brief,
                    "decisions": decisions,
                    "policy": policy,
                    "dependencies": dependencies,
                }
                source_governance = _read_json(_governance_path(_package_root(root)))
                if isinstance(source_governance, dict):
                    governance = _doc(
                        "source_governance_registry",
                        f"source-governance-{uuid.uuid4().hex}",
                        {
                            "sources": copy.deepcopy(source_governance.get("sources", [])),
                            "policy_revision": str(source_governance.get("policy_revision") or "unknown"),
                            "updated_at": str(source_governance.get("updated_at") or current),
                            "extensions": {"project_id": project["project_id"], "revision_id": revision_id},
                        },
                        now=current,
                    )
                    artifacts["source-governance"] = governance
                for kind, artifact in artifacts.items():
                    filename = f"{kind}.json"
                    _write_doc(staging / filename, artifact)
                    if kind in {"brief"}:
                        _write_projection(
                            staging / f"{kind}.md",
                            kind.title(),
                            {
                                key: value
                                for key, value in artifact.items()
                                if key not in {"content_hash", "created_at"}
                            },
                        )
                revision = _doc(
                    "project_revision",
                    revision_id,
                    {
                        "project_revision_id": revision_id,
                        "project_id": project["project_id"],
                        "parent_project_revision_id": project.get("working_project_revision_id"),
                        "package_ref": _package_ref(root),
                        "artifacts": [
                            _artifact_ref(kind, artifact, f"revisions/{revision_id}/{kind}.json")
                            for kind, artifact in artifacts.items()
                        ],
                        "pending_decision_ids": open_decision_ids,
                        "change_id": None,
                        "status": "private_draft",
                    },
                    now=current,
                )
                _write_doc(staging / "revision.json", revision)
                _write_projection(
                    staging / "README.md",
                    "Project revision",
                    {"project_revision_id": revision_id, "status": revision["status"]},
                )
                revision_dir.parent.mkdir(parents=True, exist_ok=True)
                if revision_dir.exists():
                    raise MasterProjectError("INVALID_INPUT", "project revision id already exists")
                os.replace(staging, revision_dir)
            except Exception:
                shutil.rmtree(staging, ignore_errors=True)
                raise
            next_session = dict(session)
            next_session["status"] = "finalized"
            next_session["finalized_revision_id"] = revision_id
            next_session["session_revision"] = int(session["session_revision"]) + 1
            next_session.pop("content_hash", None)
            next_session["content_hash"] = content_hash(next_session)
            next_project = dict(project)
            next_project["name"] = values.get("name") if _is_text(values.get("name")) else project["name"]
            next_project["working_project_revision_id"] = revision_id
            next_project["write_revision"] = int(project["write_revision"]) + 1
            next_project.pop("content_hash", None)
            next_project["content_hash"] = content_hash(next_project)
            _write_doc(_session_file(root), next_session)
            _write_doc(_project_file(root), next_project)
            response = _envelope(
                ok=True,
                outcome="applied",
                project_id=str(project["project_id"]),
                session_revision=int(next_session["session_revision"]),
                data={
                    "project": _project_projection(next_project),
                    "session": _session_projection(next_session),
                    "project_revision_id": revision_id,
                    "revision_path": f"revisions/{revision_id}",
                    "pending_deliverables": [],
                },
                next_actions=["project change propose"],
            )
            _idempotency_store(root, idempotency_key, request_hash, response)
            return response
    except MasterProjectError as exc:
        project_id = None
        try:
            project_id = str(_load_project(root).get("project_id"))
        except MasterProjectError:
            pass
        return _failure(exc, project_id=project_id)
    except (OSError, TypeError, UnicodeError, ValueError) as exc:
        return _failure(MasterProjectError("INVALID_INPUT", str(exc)))


def _copy_tree_checked(source: Path, target: Path, *, exclude_sensitive: bool = False) -> None:
    if source.is_symlink() or not source.is_dir():
        raise MasterProjectError("INVALID_INPUT", "package source must be a regular directory")
    sensitive_names = {"models_cache", "secrets", "__pycache__", ".env", ".env.local"}
    sensitive_suffixes = {".key", ".pem", ".p12"}
    target.mkdir(parents=True, exist_ok=False)
    for source_child in sorted(source.iterdir(), key=lambda item: item.name.casefold()):
        if exclude_sensitive and (
            source_child.name.casefold() in sensitive_names or source_child.suffix.casefold() in sensitive_suffixes
        ):
            continue
        if source_child.is_symlink():
            raise MasterProjectError("INVALID_INPUT", "package migration rejects symbolic links")
        target_child = target / source_child.name
        if source_child.is_dir():
            _copy_tree_checked(source_child, target_child, exclude_sensitive=exclude_sensitive)
        elif source_child.is_file():
            shutil.copy2(source_child, target_child)


def _legacy_package_identity(package: Path) -> dict[str, Any]:
    manifest_path = package / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise MasterProjectError("INVALID_INPUT", "legacy package manifest is missing")
    manifest = _read_json(manifest_path, required=True)
    if not isinstance(manifest, Mapping):
        raise MasterProjectError("INVALID_INPUT", "legacy package manifest must be an object")
    schema_version = manifest.get("schema_version")
    if schema_version not in {1, "1", None}:
        raise MasterProjectError("UNSUPPORTED_SCHEMA_VERSION", "legacy package schema version is not supported")
    revisions = manifest.get("revisions") if isinstance(manifest.get("revisions"), Mapping) else {}
    observed = package_revisions(
        package, golden_revision=str(revisions.get("golden_revision")) if revisions.get("golden_revision") else None
    )
    return {
        "package_id": str(manifest.get("package_id") or manifest.get("run_id") or f"legacy-{tree_hash(package)[:16]}"),
        "release_id": str(revisions.get("release_id") or observed.get("release_id")),
        "composition_hash": str(revisions.get("composition_hash") or observed.get("composition_hash")),
        "source": copy.deepcopy(manifest.get("source") if isinstance(manifest.get("source"), Mapping) else {}),
        "schema_version": schema_version or 1,
    }


def adopt_project_package(
    project_root: Path | str,
    package: Path | str,
    *,
    dry_run: bool = False,
    backup: bool = True,
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Adopt a verified v1 package by reference, without rebuilding its index."""

    root = _root(project_root)
    source = Path(os.path.abspath(os.fspath(Path(package).expanduser())))
    request_hash = _request_hash(
        "project.adopt",
        {"package": str(source), "dry_run": dry_run, "backup": backup, "expected_revision": expected_revision},
    )
    try:
        with _project_lock(root):
            identity = _legacy_package_identity(source)
            validation = validate_package(source)
            if not validation.ok:
                raise MasterProjectError(
                    "INVALID_INPUT",
                    "legacy package failed validation before adoption",
                    details={"validation": validation.to_dict()},
                )
            existing_project_raw = _read_json(_project_file(root))
            if existing_project_raw is None:
                project_id = f"project-{uuid.uuid4().hex}"
                project = _doc(
                    "project",
                    project_id,
                    {
                        "project_id": project_id,
                        "name": identity["source"].get("canonical") or identity["package_id"],
                        "active_project_revision_id": None,
                        "working_project_revision_id": None,
                        "package_locator": None,
                        "write_revision": 0,
                        "visibility": "private",
                    },
                    now=_iso(now),
                )
            else:
                project = _verify_doc(existing_project_raw, expected_kind="project")
                project_id = str(project["project_id"])
            if expected_revision is not None and project.get("write_revision") != expected_revision:
                raise MasterProjectError(
                    "STALE_REVISION", "project write revision does not match", field="expected_revision"
                )
            replay = _idempotency_replay(root, idempotency_key, request_hash)
            if replay is not None:
                return replay
            destination = root / "package"
            source_tree_hash = tree_hash(source)
            destination_tree_hash = tree_hash(destination) if destination.is_dir() else None
            same = destination_tree_hash is not None and destination_tree_hash == source_tree_hash
            would_replace = not same
            backup_required = destination.exists() and would_replace
            if same:
                outcome = "unchanged"
                backup_path = None
            elif dry_run:
                outcome = "applied"
                backup_path = None
            else:
                staging = Path(tempfile.mkdtemp(prefix=".package-adopt-", dir=str(root)))
                staging_target = staging / "package"
                backup_path: Path | None = None
                old_destination: Path | None = None
                try:
                    _copy_tree_checked(source, staging_target)
                    staged_validation = validate_package(staging_target)
                    if not staged_validation.ok:
                        raise MasterProjectError(
                            "INVALID_INPUT",
                            "legacy package failed validation before adoption",
                            details={"validation": staged_validation.to_dict()},
                        )
                    if destination.exists():
                        if not backup:
                            raise MasterProjectError("INVALID_INPUT", "existing package requires backup=true")
                        backup_id = f"backup-{_iso(now).replace(':', '').replace('-', '')}-{uuid.uuid4().hex[:8]}"
                        backup_path = _meta(root) / "backups" / backup_id
                        backup_path.parent.mkdir(parents=True, exist_ok=True)
                        _copy_tree_checked(destination, backup_path)
                        old_destination = destination.with_name(f".package-adopt-old-{uuid.uuid4().hex[:8]}")
                        os.replace(destination, old_destination)
                    os.replace(staging_target, destination)
                    if os.environ.get("DOCOPS_TEST_ADOPTION_CRASH_AFTER_SWAP") == "1":
                        raise RuntimeError("synthetic adoption interruption after swap")
                    if old_destination is not None:
                        shutil.rmtree(old_destination, ignore_errors=True)
                        old_destination = None
                except Exception:
                    if old_destination is not None and old_destination.exists():
                        if destination.exists():
                            failed = destination.with_name(f".package-adopt-failed-{uuid.uuid4().hex[:8]}")
                            os.replace(destination, failed)
                            shutil.rmtree(failed, ignore_errors=True)
                        os.replace(old_destination, destination)
                    elif destination.exists() and backup_path is not None:
                        failed = destination.with_name(f".package-adopt-failed-{uuid.uuid4().hex[:8]}")
                        os.replace(destination, failed)
                        os.replace(backup_path, destination)
                        shutil.rmtree(failed, ignore_errors=True)
                    elif destination.exists() and os.environ.get("DOCOPS_TEST_ADOPTION_CRASH_AFTER_SWAP") == "1":
                        shutil.rmtree(destination, ignore_errors=True)
                    raise
                finally:
                    shutil.rmtree(staging, ignore_errors=True)
                outcome = "applied"
            next_project = dict(project)
            next_project["package_locator"] = "package"
            next_project["write_revision"] = int(project.get("write_revision", 0)) + (
                0 if outcome == "unchanged" else 1
            )
            next_project.pop("content_hash", None)
            next_project["content_hash"] = content_hash(next_project)
            if not dry_run:
                _write_doc(_project_file(root), next_project)
                migration = _doc(
                    "package_adoption",
                    f"adoption-{uuid.uuid4().hex}",
                    {
                        "project_id": project_id,
                        "source_path": source.name,
                        "source_locator": source.name,
                        "source_identity": identity,
                        "source_tree_hash": source_tree_hash,
                        "destination_tree_hash": destination_tree_hash,
                        "destination": "package",
                        "backup_path": str(backup_path.relative_to(root).as_posix()) if backup_path else None,
                        "dry_run": False,
                        "migration_version": 1,
                        "rights_policy": "unknown",
                        "privacy_policy": "unknown",
                        "would_replace": would_replace,
                        "backup_required": backup_required,
                        "index_rebuilt": False,
                    },
                    now=_iso(now),
                )
                _write_doc(_meta(root) / "last-adoption.json", migration)
            data = {
                "project": _project_projection(project if dry_run else next_project),
                "source_locator": source.name,
                "source_identity": identity,
                "source_tree_hash": source_tree_hash,
                "destination_tree_hash": destination_tree_hash,
                "package_locator": "package",
                "backup_path": str(backup_path.relative_to(root).as_posix()) if backup_path else None,
                "would_replace": would_replace,
                "backup_required": backup_required,
                "index_rebuilt": False,
                "pending_fields": ["rights_policy", "privacy_policy"],
                "dry_run": bool(dry_run),
            }
            response = _envelope(
                ok=True,
                outcome=outcome,
                project_id=project_id,
                data=data,
                next_actions=["project source govern", "project init status"],
            )
            if not dry_run:
                _idempotency_store(root, idempotency_key, request_hash, response)
            return response
    except MasterProjectError as exc:
        return _failure(exc)
    except RuntimeError:
        raise
    except (OSError, TypeError, UnicodeError, ValueError) as exc:
        return _failure(MasterProjectError("INVALID_INPUT", str(exc)))


def rollback_project_adoption(
    project_root: Path | str,
    backup_id: str,
    *,
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Restore an adoption backup while preserving the backup itself."""

    root = _root(project_root)
    request_hash = _request_hash(
        "project.adoption.rollback", {"backup_id": backup_id, "expected_revision": expected_revision}
    )
    try:
        with _project_lock(root):
            project = _load_project(root)
            replay = _idempotency_replay(root, idempotency_key, request_hash)
            if replay is not None:
                return replay
            _check_expected_project_revision(project, expected_revision)
            backup_path = _meta(root) / "backups" / backup_id
            if backup_path.is_symlink() or not backup_path.is_dir():
                raise MasterProjectError("INVALID_INPUT", "adoption backup is missing")
            current = root / "package"
            staging = Path(tempfile.mkdtemp(prefix=".package-rollback-", dir=str(root))) / "package"
            try:
                _copy_tree_checked(backup_path, staging)
                validation = validate_package(staging)
                if not validation.ok:
                    raise MasterProjectError("INVALID_INPUT", "adoption backup no longer validates")
                old = root / f".package-rollback-old-{uuid.uuid4().hex[:8]}"
                if current.exists():
                    os.replace(current, old)
                os.replace(staging, current)
                shutil.rmtree(old, ignore_errors=True)
            finally:
                shutil.rmtree(staging.parent, ignore_errors=True)
            updated = _advance_project_revision(root, project)
            response = _envelope(
                ok=True,
                outcome="applied",
                project_id=str(project["project_id"]),
                data={
                    "package_locator": "package",
                    "restored_backup": backup_id,
                    "project": _project_projection(updated),
                },
            )
            _idempotency_store(root, idempotency_key, request_hash, response)
            return response
    except MasterProjectError as exc:
        return _failure(exc)
    except (OSError, TypeError, UnicodeError, ValueError) as exc:
        return _failure(MasterProjectError("INVALID_INPUT", str(exc)))


def inspect_project(project_root: Path | str) -> dict[str, Any]:
    """Return project identity, revisions, package reference and recovery status."""

    root = _root(project_root)
    try:
        project = _load_project(root)
        revisions_dir = root / "revisions"
        revisions = (
            sorted(path.name for path in revisions_dir.iterdir() if path.is_dir() and not path.is_symlink())
            if revisions_dir.is_dir()
            else []
        )
        return _envelope(
            ok=True,
            outcome="unchanged",
            project_id=str(project["project_id"]),
            data={
                "project": _project_projection(project),
                "package_ref": _package_ref(root),
                "revisions": revisions,
                "recovery": inspect_project_recovery(root),
            },
        )
    except MasterProjectError as exc:
        return _failure(exc)


def _governance_root(value: Path | str) -> Path:
    root = _root(value)
    return _package_root(root)


def _load_governance(root: Path) -> dict[str, Any]:
    value = _read_json(_governance_path(root))
    if value is None:
        return {"schema_version": SCHEMA_VERSION, "sources": [], "policy_revision": "unknown"}
    if (
        not isinstance(value, Mapping)
        or value.get("schema_version") != SCHEMA_VERSION
        or not isinstance(value.get("sources"), list)
    ):
        raise MasterProjectError("INVALID_INPUT", "source governance overlay is invalid")
    return dict(value)


def _load_registry_source(root: Path, source_id: str) -> dict[str, Any] | None:
    try:
        from .source_policy import source_registry_path

        value = _read_json(source_registry_path(root))
    except (MasterProjectError, OSError, ValueError):
        return None
    records = value.get("sources") if isinstance(value, Mapping) else None
    if isinstance(records, list):
        for record in records:
            if isinstance(record, Mapping) and record.get("source_id") == source_id:
                return dict(record)
    return None


def _normalise_time_field(value: Any, field: str, *, allow_date: bool = False) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise MasterProjectError("INVALID_INPUT", f"{field} must be a timestamp string", field=field)
    if allow_date and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise MasterProjectError("INVALID_INPUT", f"{field} is not a valid date", field=field) from exc
        return value
    if not _RFC3339.fullmatch(value):
        raise MasterProjectError("INVALID_INPUT", f"{field} must be UTC RFC3339", field=field)
    return _iso(value)


def _normalise_grants(raw: Any) -> list[dict[str, Any]]:
    entries: list[Mapping[str, Any]] = []
    if isinstance(raw, Mapping):
        for purpose, decision in raw.items():
            if purpose in _PURPOSES or purpose == "capture":
                entries.append({"purpose": "acquisition" if purpose == "capture" else purpose, "decision": decision})
    elif isinstance(raw, list):
        entries = [item for item in raw if isinstance(item, Mapping)]
    by_purpose: dict[str, dict[str, Any]] = {}
    for entry in entries:
        purpose = str(entry.get("purpose") or "").strip()
        if purpose == "capture":
            purpose = "acquisition"
        if purpose not in _PURPOSES:
            raise MasterProjectError(
                "INVALID_INPUT", f"unknown source use purpose: {purpose}", field="use_policy.grants"
            )
        decision = str(entry.get("decision") or "unknown")
        if decision not in {"unknown", "allowed", "denied"}:
            raise MasterProjectError(
                "INVALID_INPUT", f"unknown source use decision: {decision}", field="use_policy.grants"
            )
        evidence_ref = entry.get("evidence_ref")
        actor = entry.get("actor")
        valid_from = _normalise_time_field(entry.get("valid_from"), "valid_from")
        valid_until = _normalise_time_field(entry.get("valid_until"), "valid_until")
        review_after = _normalise_time_field(entry.get("review_after"), "review_after")
        issues: list[str] = []
        if decision == "allowed" and (not isinstance(evidence_ref, str) or not evidence_ref.strip()):
            issues.append("allowed_requires_evidence_ref")
        if decision == "allowed" and (not isinstance(actor, str) or not actor.strip()):
            issues.append("allowed_requires_actor")
        if decision == "allowed" and valid_until is None and review_after is None:
            issues.append("allowed_requires_expiry_or_review")
        if valid_from and valid_until and _datetime(valid_until) < _datetime(valid_from):
            raise MasterProjectError("INVALID_INPUT", "grant valid_until precedes valid_from", field="valid_until")
        if issues:
            decision = "unknown"
        record = {
            "purpose": purpose,
            "decision": decision,
            "evidence_ref": evidence_ref if isinstance(evidence_ref, str) else None,
            "actor": actor if isinstance(actor, str) else None,
            "valid_from": valid_from,
            "valid_until": valid_until,
            "review_after": review_after,
            "regions": list(entry.get("regions") or []) if isinstance(entry.get("regions"), list) else [],
            "issues": issues,
        }
        by_purpose[purpose] = record
    return [
        by_purpose.get(
            purpose,
            {
                "purpose": purpose,
                "decision": "unknown",
                "evidence_ref": None,
                "actor": None,
                "valid_from": None,
                "valid_until": None,
                "review_after": None,
                "regions": [],
                "issues": [],
            },
        )
        for purpose in _PURPOSES
    ]


def _normalise_governance(record: Mapping[str, Any], *, root: Path, now: str) -> dict[str, Any]:
    source_id = str(record.get("source_id") or "").strip()
    if not source_id or not _ID.fullmatch(source_id):
        raise MasterProjectError("INVALID_INPUT", "source_id must be a stable non-empty identifier", field="source_id")
    legacy = _load_registry_source(root, source_id) or {}
    observed_revision = record.get("observed_revision") or legacy.get("revision") or legacy.get("content_hash")
    if not isinstance(observed_revision, str) or not observed_revision:
        observed_revision = "unknown"
    source_type = str(record.get("source_type") or "unknown")
    if source_type not in _SOURCE_TYPES:
        raise MasterProjectError("INVALID_INPUT", f"unknown source_type: {source_type}", field="source_type")
    precision = str(record.get("published_precision") or "unknown")
    published_at = _normalise_time_field(record.get("published_at"), "published_at", allow_date=True)
    if precision not in {"unknown", "date", "timestamp"}:
        raise MasterProjectError("INVALID_INPUT", "published_precision is invalid", field="published_precision")
    if precision == "unknown" and published_at is not None:
        raise MasterProjectError(
            "INVALID_INPUT", "published_precision=unknown requires published_at=null", field="published_at"
        )
    if precision == "date" and published_at is not None and len(published_at) != 10:
        raise MasterProjectError("INVALID_INPUT", "date precision requires YYYY-MM-DD", field="published_at")
    if precision == "timestamp" and published_at is not None and len(published_at) == 10:
        raise MasterProjectError("INVALID_INPUT", "timestamp precision requires RFC3339", field="published_at")
    validity_raw = record.get("validity") if isinstance(record.get("validity"), Mapping) else {}
    validity = {key: _normalise_time_field(validity_raw.get(key), f"validity.{key}") for key in _VALIDITY_FIELDS}
    if validity["from"] and validity["until"] and _datetime(validity["until"]) < _datetime(validity["from"]):
        raise MasterProjectError("INVALID_INPUT", "validity.until precedes validity.from", field="validity.until")
    privacy_raw = record.get("privacy") if isinstance(record.get("privacy"), Mapping) else {}
    privacy_class = str(privacy_raw.get("classification") or "unknown")
    if privacy_class not in {"public", "internal", "restricted", "unknown"}:
        raise MasterProjectError("INVALID_INPUT", "privacy classification is invalid", field="privacy.classification")
    lifecycle = str(record.get("lifecycle") or "active")
    if lifecycle not in {"active", "archived", "revoked"}:
        raise MasterProjectError("INVALID_INPUT", "source lifecycle is invalid", field="lifecycle")
    grants = _normalise_grants(
        record.get("use_policy", {}).get("grants")
        if isinstance(record.get("use_policy"), Mapping)
        else record.get("grants")
    )
    authority_class = str(record.get("authority_class") or "unknown")
    if authority_class not in _AUTHORITY_CLASSES:
        raise MasterProjectError("INVALID_INPUT", "authority_class is invalid", field="authority_class")
    return {
        "source_id": source_id,
        "observed_revision": observed_revision,
        "source_type": source_type,
        "author": record.get("author"),
        "organization": record.get("organization"),
        "published_at": published_at,
        "published_precision": precision,
        "captured_at": _normalise_time_field(record.get("captured_at"), "captured_at"),
        "language": record.get("language"),
        "region": record.get("region"),
        "authority_class": authority_class,
        "validity": validity,
        "use_policy": {
            "license_id": (
                record.get("use_policy", {}).get("license_id")
                if isinstance(record.get("use_policy"), Mapping)
                else record.get("license_id")
            ),
            "grants": grants,
            "restrictions": list(record.get("use_policy", {}).get("restrictions") or [])
            if isinstance(record.get("use_policy"), Mapping)
            else list(record.get("restrictions") or []),
        },
        "lifecycle": lifecycle,
        "privacy": {
            "classification": privacy_class,
            "retention_until": _normalise_time_field(privacy_raw.get("retention_until"), "privacy.retention_until"),
            "redaction_required": bool(privacy_raw.get("redaction_required", False)),
        },
        "transcript": copy.deepcopy(record.get("transcript"))
        if isinstance(record.get("transcript"), Mapping)
        else None,
        "derived_from": copy.deepcopy(record.get("derived_from") or [])
        if isinstance(record.get("derived_from"), list)
        else [],
        "updated_at": now,
        "extensions": copy.deepcopy(record.get("extensions")) if isinstance(record.get("extensions"), Mapping) else {},
    }


def register_source_governance(
    project_or_package: Path | str,
    governance: Mapping[str, Any],
    *,
    readmit: bool = False,
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Persist the conservative per-purpose source governance overlay."""

    project = _root(project_or_package)
    package = _governance_root(project)
    record_input = dict(governance)
    source_id = str(record_input.get("source_id") or "")
    request_hash = _request_hash(
        "source.govern", {"governance": record_input, "readmit": readmit, "expected_revision": expected_revision}
    )
    try:
        with _project_lock(project):
            project_doc = _read_json(_project_file(project))
            project_id = None
            if project_doc is not None:
                project_doc = _verify_doc(project_doc, expected_kind="project")
                project_id = str(project_doc["project_id"])
                if expected_revision is not None and project_doc.get("write_revision") != expected_revision:
                    raise MasterProjectError(
                        "STALE_REVISION", "project write revision does not match", field="expected_revision"
                    )
            replay = _idempotency_replay(project, idempotency_key, request_hash) if project_doc is not None else None
            if replay is not None:
                return replay
            now_text = _iso(now)
            current = _load_governance(package)
            old = next(
                (
                    item
                    for item in current["sources"]
                    if isinstance(item, Mapping) and item.get("source_id") == source_id
                ),
                None,
            )
            normalized = _normalise_governance(record_input, root=package, now=now_text)
            if old and old.get("lifecycle") == "revoked" and not readmit:
                normalized["lifecycle"] = "revoked"
                normalized.setdefault("extensions", {})["readmit_required"] = True
            sources = [
                item
                for item in current["sources"]
                if not (isinstance(item, Mapping) and item.get("source_id") == source_id)
            ]
            sources.append(normalized)
            sources.sort(key=lambda item: str(item.get("source_id")))
            overlay = _doc(
                "source_governance_registry",
                str(current.get("id") or f"governance-{uuid.uuid4().hex}"),
                {"sources": sources, "policy_revision": content_hash(sources), "updated_at": now_text},
                now=now_text,
            )
            if package == project and project_doc is None:
                # A package-only call intentionally stores only package state.
                pass
            _write_doc(_governance_path(package), overlay)
            if readmit:
                revocations = _read_json(_revocations_path(package))
                if isinstance(revocations, Mapping):
                    remaining = [
                        item
                        for item in revocations.get("sources", [])
                        if isinstance(item, Mapping) and item.get("source_id") != source_id
                    ]
                    write_json_atomic(
                        _revocations_path(package), {"schema_version": SCHEMA_VERSION, "sources": remaining}
                    )
            if project_doc is not None:
                project_doc = dict(project_doc)
                project_doc["write_revision"] = int(project_doc["write_revision"]) + 1
                project_doc.pop("content_hash", None)
                project_doc["content_hash"] = content_hash(project_doc)
                _write_doc(_project_file(project), project_doc)
            response = _envelope(
                ok=True,
                outcome="applied",
                project_id=project_id,
                data={
                    "source": normalized,
                    "policy_revision": overlay["policy_revision"],
                    "governance_path": str(_governance_path(package).relative_to(project).as_posix()),
                },
                next_actions=["project source query", "project change propose"],
            )
            if project_doc is not None:
                _idempotency_store(project, idempotency_key, request_hash, response)
            return response
    except MasterProjectError as exc:
        return _failure(exc)
    except (OSError, TypeError, UnicodeError, ValueError) as exc:
        return _failure(MasterProjectError("INVALID_INPUT", str(exc)))


def source_use_decision(
    project_or_package: Path | str,
    source_id: str,
    purpose: str,
    *,
    region: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Evaluate one use by intersection of registry, overlay, privacy and revocation."""

    root = _governance_root(project_or_package)
    purpose = "acquisition" if purpose == "capture" else purpose
    if purpose not in _PURPOSES:
        return {
            "schema_version": SCHEMA_VERSION,
            "allowed": False,
            "code": "INVALID_INPUT",
            "source_id": source_id,
            "purpose": purpose,
        }
    try:
        governance = _load_governance(root)
        record = next(
            (
                item
                for item in governance["sources"]
                if isinstance(item, Mapping) and item.get("source_id") == source_id
            ),
            None,
        )
        if record is None:
            return {
                "schema_version": SCHEMA_VERSION,
                "allowed": False,
                "code": "RIGHTS_BLOCKED",
                "reason": "governance_unknown",
                "source_id": source_id,
                "purpose": purpose,
            }
        current = _datetime(now)
        legacy = _load_registry_source(root, source_id)
        if isinstance(legacy, Mapping) and str(legacy.get("status") or "active") in {
            "withdrawn",
            "revoked",
            "archived",
            "inactive",
        }:
            return {
                "schema_version": SCHEMA_VERSION,
                "allowed": False,
                "code": "SOURCE_REVOKED",
                "reason": "registry_source_inactive",
                "source_id": source_id,
                "purpose": purpose,
            }
        revoked = _read_json(_revocations_path(root))
        if isinstance(revoked, Mapping) and any(
            item.get("source_id") == source_id for item in revoked.get("sources", []) if isinstance(item, Mapping)
        ):
            return {
                "schema_version": SCHEMA_VERSION,
                "allowed": False,
                "code": "SOURCE_REVOKED",
                "reason": "source_revoked",
                "source_id": source_id,
                "purpose": purpose,
            }
        if record.get("lifecycle") == "revoked":
            return {
                "schema_version": SCHEMA_VERSION,
                "allowed": False,
                "code": "SOURCE_REVOKED",
                "reason": "source_revoked",
                "source_id": source_id,
                "purpose": purpose,
            }
        if record.get("lifecycle") == "archived" and purpose in {
            "indexing",
            "internal_query",
            "quotation",
            "derivatives",
            "redistribution",
        }:
            return {
                "schema_version": SCHEMA_VERSION,
                "allowed": False,
                "code": "SOURCE_ARCHIVED",
                "reason": "source_archived",
                "source_id": source_id,
                "purpose": purpose,
            }
        if not _validity_active(record.get("validity"), now=current):
            return {
                "schema_version": SCHEMA_VERSION,
                "allowed": False,
                "code": "EVIDENCE_STALE",
                "reason": "source_validity_inactive",
                "source_id": source_id,
                "purpose": purpose,
            }
        grant = next(
            (item for item in record.get("use_policy", {}).get("grants", []) if item.get("purpose") == purpose), None
        )
        if not isinstance(grant, Mapping) or grant.get("decision") != "allowed":
            return {
                "schema_version": SCHEMA_VERSION,
                "allowed": False,
                "code": "RIGHTS_BLOCKED",
                "reason": "grant_unknown_or_denied",
                "source_id": source_id,
                "purpose": purpose,
            }
        if grant.get("valid_from") and current < _datetime(grant["valid_from"]):
            return {
                "schema_version": SCHEMA_VERSION,
                "allowed": False,
                "code": "RIGHTS_BLOCKED",
                "reason": "grant_not_yet_valid",
                "source_id": source_id,
                "purpose": purpose,
            }
        if grant.get("valid_until") and current >= _datetime(grant["valid_until"]):
            return {
                "schema_version": SCHEMA_VERSION,
                "allowed": False,
                "code": "RIGHTS_BLOCKED",
                "reason": "grant_expired",
                "source_id": source_id,
                "purpose": purpose,
            }
        if grant.get("review_after") and current >= _datetime(grant["review_after"]):
            return {
                "schema_version": SCHEMA_VERSION,
                "allowed": False,
                "code": "RIGHTS_BLOCKED",
                "reason": "grant_review_due",
                "source_id": source_id,
                "purpose": purpose,
            }
        allowed_regions = grant.get("regions") or []
        if region and allowed_regions and region not in allowed_regions:
            return {
                "schema_version": SCHEMA_VERSION,
                "allowed": False,
                "code": "RIGHTS_BLOCKED",
                "reason": "region_not_allowed",
                "source_id": source_id,
                "purpose": purpose,
            }
        if record.get("privacy", {}).get("classification") == "unknown" and purpose in {
            "storage",
            "indexing",
            "redistribution",
        }:
            return {
                "schema_version": SCHEMA_VERSION,
                "allowed": False,
                "code": "PRIVACY_BLOCKED",
                "reason": "privacy_unknown",
                "source_id": source_id,
                "purpose": purpose,
            }
        if record.get("privacy", {}).get("retention_until") and current >= _datetime(
            record["privacy"]["retention_until"]
        ):
            return {
                "schema_version": SCHEMA_VERSION,
                "allowed": False,
                "code": "PRIVACY_BLOCKED",
                "reason": "retention_expired",
                "source_id": source_id,
                "purpose": purpose,
            }
        return {
            "schema_version": SCHEMA_VERSION,
            "allowed": True,
            "code": "ALLOWED",
            "source_id": source_id,
            "purpose": purpose,
            "observed_revision": record.get("observed_revision"),
        }
    except MasterProjectError as exc:
        return {
            "schema_version": SCHEMA_VERSION,
            "allowed": False,
            "code": exc.code,
            "reason": str(exc),
            "source_id": source_id,
            "purpose": purpose,
        }


def _timestamp_ms(value: str) -> int:
    parts = value.replace(",", ".").split(":")
    try:
        if len(parts) == 2:
            minutes, seconds = int(parts[0]), float(parts[1])
            return int((minutes * 60 + seconds) * 1000)
        if len(parts) == 3:
            hours, minutes, seconds = int(parts[0]), int(parts[1]), float(parts[2])
            return int((hours * 3600 + minutes * 60 + seconds) * 1000)
    except ValueError as exc:
        raise MasterProjectError("INVALID_INPUT", f"invalid transcript timestamp: {value}") from exc
    raise MasterProjectError("INVALID_INPUT", f"invalid transcript timestamp: {value}")


def _timestamp_interval_ms(value: str, end: str | None) -> tuple[int, int | None]:
    """Accept human timestamps and the millisecond locator emitted for transcripts."""

    if end is not None and re.fullmatch(r"\d+(?:\.\d+)?", value) and re.fullmatch(r"\d+(?:\.\d+)?", end):
        return int(float(value)), int(float(end))
    range_match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)\s*", value)
    if range_match:
        return int(float(range_match.group(1))), int(float(range_match.group(2)))
    return _timestamp_ms(value), _timestamp_ms(end) if end is not None else None


_TRANSCRIPT_RANGE = re.compile(
    r"^\s*(?:[-*>]\s*)?(?:\[\s*)?(?P<start>\d{1,2}:\d{2}(?::\d{2})?(?:[\.,]\d{1,3})?)\s*(?:\]|\s)*(?:-->|-|–|—|to)\s*(?:\[\s*)?(?P<end>\d{1,2}:\d{2}(?::\d{2})?(?:[\.,]\d{1,3})?)(?:\s*\])?\s*(?P<text>.*)$",
    re.IGNORECASE,
)

_MAX_TRANSCRIPT_BYTES = 2_000_000
_MAX_TRANSCRIPT_SEGMENTS = 10_000


def _validate_transcript_limits(text: str, segments: list[Mapping[str, Any]]) -> None:
    if len(text.encode("utf-8")) > _MAX_TRANSCRIPT_BYTES:
        raise MasterProjectError("INVALID_INPUT", "transcript exceeds the input byte limit")
    if len(segments) > _MAX_TRANSCRIPT_SEGMENTS:
        raise MasterProjectError("INVALID_INPUT", "transcript exceeds the segment limit")


def _validate_transcript_order(segments: list[Mapping[str, Any]]) -> None:
    previous_start: int | None = None
    for segment in segments:
        start = segment.get("start_ms")
        if not isinstance(start, int) or isinstance(start, bool):
            raise MasterProjectError("INVALID_INPUT", "transcript segment start_ms is invalid")
        if previous_start is not None and start < previous_start:
            raise MasterProjectError("INVALID_INPUT", "transcript segments must be in chronological order")
        previous_start = start


def _transcript_segments(value: Mapping[str, Any] | str | Path) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    metadata: dict[str, Any] = {}
    if isinstance(value, Path):
        text = value.read_text(encoding="utf-8")
        metadata["input_path"] = value.name
    elif isinstance(value, Mapping):
        text = str(value.get("text") or value.get("markdown") or "")
        metadata = {
            key: copy.deepcopy(item) for key, item in value.items() if key not in {"text", "markdown", "segments"}
        }
        raw_segments = value.get("segments")
        if isinstance(raw_segments, list):
            segments: list[dict[str, Any]] = []
            for index, item in enumerate(raw_segments):
                if not isinstance(item, Mapping):
                    raise MasterProjectError("INVALID_INPUT", "transcript segment must be an object")
                start = item.get("start_ms")
                end = item.get("end_ms")
                if (
                    isinstance(start, bool)
                    or not isinstance(start, int)
                    or isinstance(end, bool)
                    or not isinstance(end, int)
                    or start < 0
                    or end <= start
                ):
                    raise MasterProjectError("INVALID_INPUT", "transcript segment interval is invalid")
                segments.append(
                    {
                        "segment_id": str(item.get("segment_id") or f"segment-{index + 1}"),
                        "start_ms": start,
                        "end_ms": end,
                        "text_ref": str(item.get("text_ref") or ""),
                    }
                )
            _validate_transcript_order(segments)
            _validate_transcript_limits(text, segments)
            return segments, text, metadata
    else:
        text = str(value)
    segments = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = _TRANSCRIPT_RANGE.match(line)
        if match is None:
            raise MasterProjectError(
                "INVALID_INPUT",
                "every transcript line must include an explicit timestamp interval",
                field=f"line:{line_number}",
            )
        start_ms = _timestamp_ms(match.group("start"))
        end_ms = _timestamp_ms(match.group("end"))
        if end_ms <= start_ms:
            raise MasterProjectError(
                "INVALID_INPUT", "transcript interval must end after it starts", field=f"line:{line_number}"
            )
        segments.append(
            {
                "segment_id": f"segment-{len(segments) + 1}",
                "start_ms": start_ms,
                "end_ms": end_ms,
                "text_ref": match.group("text"),
                "line": line_number,
            }
        )
    if not segments:
        raise MasterProjectError("INVALID_INPUT", "timestamped transcript has no segments")
    _validate_transcript_order(segments)
    _validate_transcript_limits(text, segments)
    return segments, text, metadata


def _write_rag_source_entry(
    package: Path, *, source_id: str, destination: str, source: Mapping[str, Any], locators: list[Mapping[str, Any]]
) -> None:
    path = package / "rag" / "sources.json"
    payload = _read_json(path)
    if not isinstance(payload, Mapping):
        payload = {"schema_version": SCHEMA_VERSION, "sources": []}
    records = [dict(item) for item in payload.get("sources", []) if isinstance(item, Mapping)]
    records = [
        item for item in records if item.get("source_id") != source_id and item.get("destination") != destination
    ]
    records.append(
        {
            "source_id": source_id,
            "destination": destination,
            "canonical": source.get("canonical") or source_id,
            "observed_revision": source.get("observed_revision"),
            "format": "markdown",
            "locators": [dict(item) for item in locators],
        }
    )
    records.sort(key=lambda item: str(item.get("source_id")))
    write_json_atomic(path, {**dict(payload), "schema_version": SCHEMA_VERSION, "sources": records})


def ingest_external_transcription(
    project_or_package: Path | str,
    source_id: str,
    transcript: Mapping[str, Any] | str | Path,
    *,
    video_url: str | None = None,
    provider: str | None = None,
    permission_ref: str | None = None,
    captured_at: datetime | date | str | None = None,
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Store a timestamped external transcript as private, traceable evidence."""

    project = _root(project_or_package)
    package = _governance_root(project)
    request_hash = _request_hash(
        "source.transcription",
        {
            "source_id": source_id,
            "transcript": str(transcript),
            "video_url": video_url,
            "provider": provider,
            "permission_ref": permission_ref,
            "expected_revision": expected_revision,
        },
    )
    try:
        with _project_lock(project):
            project_doc = _read_json(_project_file(project))
            project_id = None
            if project_doc is not None:
                project_doc = _verify_doc(project_doc, expected_kind="project")
                project_id = str(project_doc["project_id"])
            replay = _idempotency_replay(project, idempotency_key, request_hash) if project_doc is not None else None
            if replay is not None:
                return replay
            if project_doc is not None:
                _check_expected_project_revision(project_doc, expected_revision)
            source_record = next(
                (item for item in _load_governance(package)["sources"] if item.get("source_id") == source_id), None
            )
            if source_record is None:
                raise MasterProjectError(
                    "RIGHTS_BLOCKED", "transcription source has no governance observation", field="source_id"
                )
            acquisition = source_use_decision(package, source_id, "acquisition", now=now)
            storage = source_use_decision(package, source_id, "storage", now=now)
            if not acquisition.get("allowed") or not storage.get("allowed"):
                raise MasterProjectError(
                    "RIGHTS_BLOCKED",
                    "source is not authorized for transcript acquisition and storage",
                    field="source_id",
                )
            segments, text, metadata = _transcript_segments(transcript)
            current = _iso(now)
            capture_time = _iso(captured_at or current)
            slug = re.sub(r"[^A-Za-z0-9._-]+", "-", source_id).strip("-") or "source"
            transcript_dir = package / ".docops" / "transcripts"
            transcript_dir.mkdir(parents=True, exist_ok=True)
            destination = transcript_dir / f"{slug}.md"
            if destination.exists() and destination.is_symlink():
                raise MasterProjectError("INVALID_INPUT", "transcript destination must be a regular file")
            write_text_atomic(destination, text)
            locators = [
                {
                    "kind": "timestamp",
                    "label": f"{item['start_ms']}-{item['end_ms']}",
                    "value": f"{item['start_ms']}-{item['end_ms']}",
                    "end": str(item["end_ms"]),
                }
                for item in segments
            ]
            normalized_transcript = {
                "video_url": video_url
                or (metadata.get("video_url") if isinstance(metadata.get("video_url"), str) else ""),
                "provider": provider
                or (metadata.get("provider") if isinstance(metadata.get("provider"), str) else "unknown"),
                "permission_ref": permission_ref,
                "segments": [
                    {
                        "segment_id": item["segment_id"],
                        "start_ms": item["start_ms"],
                        "end_ms": item["end_ms"],
                        "text_ref": f".docops/transcripts/{destination.name}#timestamp={item['start_ms']}-{item['end_ms']}",
                    }
                    for item in segments
                ],
            }
            governance = _load_governance(package)
            updated_sources = []
            for item in governance["sources"]:
                if item.get("source_id") != source_id:
                    updated_sources.append(item)
                    continue
                updated = dict(item)
                updated["source_type"] = "video_transcript"
                updated["captured_at"] = capture_time
                updated["transcript"] = normalized_transcript
                updated["updated_at"] = current
                updated_sources.append(updated)
            overlay = _doc(
                "source_governance_registry",
                str(governance.get("id") or f"governance-{uuid.uuid4().hex}"),
                {"sources": updated_sources, "policy_revision": content_hash(updated_sources), "updated_at": current},
                now=current,
            )
            _write_doc(_governance_path(package), overlay)
            if (package / "rag").is_dir():
                indexing = source_use_decision(package, source_id, "indexing", now=now)
                if indexing.get("allowed"):
                    _write_rag_source_entry(
                        package,
                        source_id=source_id,
                        destination=f".docops/transcripts/{destination.name}",
                        source=source_record,
                        locators=locators,
                    )
            if project_doc is not None:
                project_doc = _advance_project_revision(project, project_doc)
            response = _envelope(
                ok=True,
                outcome="applied",
                project_id=project_id,
                data={
                    "source_id": source_id,
                    "transcript_path": str(destination.relative_to(project).as_posix()),
                    "segment_count": len(segments),
                    "captured_at": capture_time,
                    "redistribution_allowed": source_use_decision(package, source_id, "redistribution", now=now).get(
                        "allowed", False
                    ),
                    "permission_ref": permission_ref,
                },
                next_actions=["project source query"],
            )
            if project_doc is not None:
                _idempotency_store(project, idempotency_key, request_hash, response)
            return response
    except MasterProjectError as exc:
        return _failure(exc)
    except (OSError, TypeError, UnicodeError, ValueError) as exc:
        return _failure(MasterProjectError("INVALID_INPUT", str(exc)))


def _load_evidence(root: Path) -> dict[str, Any]:
    value = _read_json(_evidence_path(root))
    if value is None:
        return {"schema_version": SCHEMA_VERSION, "claims": [], "conflicts": [], "updated_at": None}
    if not isinstance(value, Mapping) or value.get("schema_version") != SCHEMA_VERSION:
        raise MasterProjectError("INVALID_INPUT", "project evidence store is invalid")
    return dict(value)


def _validity_active(validity: Mapping[str, Any] | None, *, now: datetime) -> bool:
    if not isinstance(validity, Mapping):
        return True
    try:
        start = _datetime(validity.get("from")) if validity.get("from") else None
        until = _datetime(validity.get("until")) if validity.get("until") else None
    except MasterProjectError:
        return False
    return not (start and now < start or until and now >= until)


def _normalise_validity(value: Any, *, field: str = "validity") -> dict[str, str | None]:
    raw = value if isinstance(value, Mapping) else {}
    result = {key: _normalise_time_field(raw.get(key), f"{field}.{key}") for key in _VALIDITY_FIELDS}
    if result["from"] and result["until"] and _datetime(result["until"]) < _datetime(result["from"]):
        raise MasterProjectError("INVALID_INPUT", f"{field}.until precedes {field}.from", field=f"{field}.until")
    return result


def _normalise_evidence_ref(ref: Mapping[str, Any]) -> dict[str, Any]:
    required = ("source_id", "observed_revision", "document_id", "content_hash", "locator")
    if any(not isinstance(ref.get(key), str) or not str(ref.get(key)).strip() for key in required[:-1]):
        raise MasterProjectError("INVALID_INPUT", "evidence reference is incomplete")
    if not _HEX64.fullmatch(str(ref.get("content_hash"))):
        raise MasterProjectError("INVALID_INPUT", "evidence content_hash must be SHA-256", field="content_hash")
    if not isinstance(ref.get("locator"), Mapping):
        raise MasterProjectError("INVALID_INPUT", "evidence locator must be an object")
    locator = dict(ref["locator"])
    if (
        locator.get("kind") not in {"section", "page", "timestamp", "line"}
        or not isinstance(locator.get("value"), str)
        or not locator["value"]
    ):
        raise MasterProjectError("INVALID_INPUT", "evidence locator is invalid")
    if "end" not in locator or locator.get("end") is not None and not isinstance(locator.get("end"), str):
        raise MasterProjectError("INVALID_INPUT", "evidence locator requires end=null|string")
    if locator.get("kind") == "timestamp":
        start, end = _timestamp_interval_ms(locator["value"], locator.get("end"))
        if end is None or end <= start:
            raise MasterProjectError("INVALID_INPUT", "timestamp evidence requires a verifiable interval")
    return {**dict(ref), "locator": locator}


def record_project_claim(
    project_or_package: Path | str,
    claim: Mapping[str, Any],
    *,
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Record a classified claim without turning it into an active answer."""

    project = _root(project_or_package)
    root = _governance_root(project)
    payload = dict(claim)
    request_hash = _request_hash("evidence.claim", {"payload": payload, "expected_revision": expected_revision})
    try:
        with _project_lock(project):
            project_doc = _read_json(_project_file(project))
            project_id = None
            if project_doc is not None:
                project_doc = _verify_doc(project_doc, expected_kind="project")
                project_id = str(project_doc["project_id"])
            replay = _idempotency_replay(project, idempotency_key, request_hash) if project_doc is not None else None
            if replay is not None:
                return replay
            if project_doc is not None:
                _check_expected_project_revision(project_doc, expected_revision)
            elif expected_revision is not None:
                raise MasterProjectError(
                    "INVALID_INPUT", "expected_revision requires a project locator", field="expected_revision"
                )
            classification = str(payload.get("classification") or "")
            if classification not in _CLAIM_TYPES or not _is_text(payload.get("text")):
                raise MasterProjectError("INVALID_INPUT", "claim text and classification are required")
            raw_evidence = payload.get("evidence_refs") or []
            if not isinstance(raw_evidence, list) or any(not isinstance(item, Mapping) for item in raw_evidence):
                raise MasterProjectError(
                    "INVALID_INPUT", "evidence_refs must be an array of objects", field="evidence_refs"
                )
            evidence = [_normalise_evidence_ref(item) for item in raw_evidence]
            review_status = str(payload.get("review_status") or "proposed")
            if review_status not in {"proposed", "reviewed"}:
                raise MasterProjectError("INVALID_INPUT", "claim review_status is invalid")
            reviewer = payload.get("reviewer_ref")
            if review_status == "reviewed" and not _is_text(reviewer):
                raise MasterProjectError("INVALID_INPUT", "reviewed claim requires reviewer_ref")
            if classification == "official_rule" and not evidence:
                raise MasterProjectError("INVALID_INPUT", "official_rule requires verification evidence")
            claim_id = str(payload.get("claim_id") or f"claim-{uuid.uuid4().hex}")
            claim_payload = {
                "claim_id": claim_id,
                "project_id": project_id,
                "text": str(payload["text"]),
                "classification": classification,
                "region": payload.get("region"),
                "validity": _normalise_validity(payload.get("validity")),
                "evidence_refs": evidence,
                "conflict_ids": list(payload.get("conflict_ids") or []),
                "review_status": review_status,
                "reviewer_ref": reviewer,
                "extensions": copy.deepcopy(payload.get("extensions"))
                if isinstance(payload.get("extensions"), Mapping)
                else {},
            }
            value = _doc("claim", claim_id, claim_payload, now=_iso(now))
            store = _load_evidence(root)
            claims = [item for item in store["claims"] if item.get("claim_id") != claim_id]
            claims.append(value)
            claims.sort(key=lambda item: str(item.get("claim_id")))
            store["claims"] = claims
            store["updated_at"] = _iso(now)
            write_json_atomic(_evidence_path(root), store)
            if project_doc is not None:
                _advance_project_revision(project, project_doc)
            response = _envelope(
                ok=True,
                outcome="applied",
                project_id=project_id,
                data={"claim": value},
                next_actions=["project source query", "project change propose"],
            )
            if project_doc is not None:
                _idempotency_store(project, idempotency_key, request_hash, response)
            return response
    except MasterProjectError as exc:
        return _failure(exc)
    except (OSError, TypeError, UnicodeError, ValueError) as exc:
        return _failure(MasterProjectError("INVALID_INPUT", str(exc)))


def record_project_conflict(
    project_or_package: Path | str,
    conflict: Mapping[str, Any],
    *,
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Record an explicit conflict relation; recency alone never resolves it."""

    project = _root(project_or_package)
    root = _governance_root(project)
    payload = dict(conflict)
    request_hash = _request_hash("evidence.conflict", {"payload": payload, "expected_revision": expected_revision})
    try:
        with _project_lock(project):
            project_doc = _read_json(_project_file(project))
            project_id = None
            if project_doc is not None:
                project_doc = _verify_doc(project_doc, expected_kind="project")
                project_id = str(project_doc["project_id"])
            replay = _idempotency_replay(project, idempotency_key, request_hash) if project_doc is not None else None
            if replay is not None:
                return replay
            if project_doc is not None:
                _check_expected_project_revision(project_doc, expected_revision)
            elif expected_revision is not None:
                raise MasterProjectError(
                    "INVALID_INPUT", "expected_revision requires a project locator", field="expected_revision"
                )
            raw_claim_ids = payload.get("claim_ids") or []
            if not isinstance(raw_claim_ids, list) or any(
                not isinstance(item, str) or not item.strip() for item in raw_claim_ids
            ):
                raise MasterProjectError("INVALID_INPUT", "claim_ids must be non-empty strings", field="claim_ids")
            claim_ids = list(dict.fromkeys(str(item) for item in raw_claim_ids))
            relation = str(payload.get("relation") or "")
            if len(claim_ids) < 2 or relation not in {"contradicts", "supersedes", "scope_difference"}:
                raise MasterProjectError("INVALID_INPUT", "conflict requires two claim IDs and a valid relation")
            status = str(payload.get("status") or "open")
            if status not in {"open", "resolved"}:
                raise MasterProjectError("INVALID_INPUT", "conflict status is invalid")
            if status == "resolved" and (
                not _is_text(payload.get("resolution")) or not _is_text(payload.get("reviewer_ref"))
            ):
                raise MasterProjectError("INVALID_INPUT", "resolved conflict requires resolution and reviewer_ref")
            store = _load_evidence(root)
            known = {item.get("claim_id") for item in store["claims"] if isinstance(item, Mapping)}
            if not set(claim_ids) <= known:
                raise MasterProjectError("INVALID_INPUT", "conflict references an unknown claim")
            conflict_id = str(payload.get("conflict_id") or f"conflict-{uuid.uuid4().hex}")
            conflict_payload = {
                "conflict_id": conflict_id,
                "project_id": project_id,
                "claim_ids": claim_ids,
                "relation": relation,
                "status": status,
                "resolution": payload.get("resolution"),
                "reviewer_ref": payload.get("reviewer_ref"),
                "extensions": copy.deepcopy(payload.get("extensions"))
                if isinstance(payload.get("extensions"), Mapping)
                else {},
            }
            value = _doc("conflict", conflict_id, conflict_payload, now=_iso(now))
            store["conflicts"] = [item for item in store["conflicts"] if item.get("conflict_id") != conflict_id] + [
                value
            ]
            updated_claims = []
            for claim in store["claims"]:
                if not isinstance(claim, Mapping) or claim.get("claim_id") not in claim_ids:
                    updated_claims.append(claim)
                    continue
                updated_claim = dict(claim)
                prior_conflict_ids = updated_claim.get("conflict_ids")
                if not isinstance(prior_conflict_ids, list):
                    prior_conflict_ids = []
                conflict_ids = list(dict.fromkeys([*prior_conflict_ids, conflict_id]))
                updated_claim["conflict_ids"] = conflict_ids
                updated_claim.pop("content_hash", None)
                updated_claim["content_hash"] = content_hash(updated_claim)
                updated_claims.append(updated_claim)
            store["claims"] = updated_claims
            store["updated_at"] = _iso(now)
            write_json_atomic(_evidence_path(root), store)
            if project_doc is not None:
                _advance_project_revision(project, project_doc)
            response = _envelope(
                ok=True,
                outcome="applied",
                project_id=value["project_id"],
                data={"conflict": value},
                next_actions=["project source query"],
            )
            if project_doc is not None:
                _idempotency_store(project, idempotency_key, request_hash, response)
            return response
    except MasterProjectError as exc:
        return _failure(exc)
    except (OSError, TypeError, UnicodeError, ValueError) as exc:
        return _failure(MasterProjectError("INVALID_INPUT", str(exc)))


def revoke_project_source(
    project_or_package: Path | str,
    source_id: str,
    *,
    reason: str = "revoked by operator",
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Revoke a source transitively while retaining audit data and tombstones."""

    project = _root(project_or_package)
    root = _governance_root(project)
    request_hash = _request_hash(
        "source.revoke", {"source_id": source_id, "reason": reason, "expected_revision": expected_revision}
    )
    try:
        with _project_lock(project):
            project_doc = _read_json(_project_file(project))
            project_id = None
            if project_doc is not None:
                project_doc = _verify_doc(project_doc, expected_kind="project")
                project_id = str(project_doc["project_id"])
            replay = _idempotency_replay(project, idempotency_key, request_hash) if project_doc is not None else None
            if replay is not None:
                return replay
            if project_doc is not None:
                _check_expected_project_revision(project_doc, expected_revision)
            elif expected_revision is not None:
                raise MasterProjectError(
                    "INVALID_INPUT", "expected_revision requires a project locator", field="expected_revision"
                )
            governance = _load_governance(root)
            found = False
            updated_sources = []
            for item in governance["sources"]:
                if item.get("source_id") == source_id:
                    updated = dict(item)
                    updated["lifecycle"] = "revoked"
                    updated["updated_at"] = _iso(now)
                    updated_sources.append(updated)
                    found = True
                else:
                    updated_sources.append(item)
            if not found:
                raise MasterProjectError("INVALID_INPUT", "cannot revoke an unknown source", field="source_id")
            current = _read_json(_revocations_path(root))
            records = (
                [dict(item) for item in current.get("sources", []) if isinstance(item, Mapping)]
                if isinstance(current, Mapping)
                else []
            )
            destinations: list[str] = []
            sources_path = root / "rag" / "sources.json"
            sources_payload = _read_json(sources_path)
            if isinstance(sources_payload, Mapping):
                destinations = [
                    str(item.get("destination"))
                    for item in sources_payload.get("sources", [])
                    if isinstance(item, Mapping) and item.get("source_id") == source_id and item.get("destination")
                ]
            record = {
                "source_id": source_id,
                "revoked_at": _iso(now),
                "reason": str(reason),
                "destinations": sorted(set(destinations)),
            }
            records = [item for item in records if item.get("source_id") != source_id] + [record]
            write_json_atomic(_revocations_path(root), {"schema_version": SCHEMA_VERSION, "sources": records})
            evidence = _load_evidence(root)
            claim_ids = [
                str(item.get("claim_id"))
                for item in evidence["claims"]
                if any(
                    ref.get("source_id") == source_id
                    for ref in item.get("evidence_refs", [])
                    if isinstance(ref, Mapping)
                )
            ]
            tombstones = _read_json(root / ".docops" / "tombstones.json")
            tombstone_items = (
                [dict(item) for item in tombstones.get("tombstones", []) if isinstance(item, Mapping)]
                if isinstance(tombstones, Mapping)
                else []
            )
            tombstone_items = [item for item in tombstone_items if item.get("source_id") != source_id]
            tombstone_items.append(
                {
                    "source_id": source_id,
                    "claim_ids": claim_ids,
                    "destinations": record["destinations"],
                    "revoked_at": record["revoked_at"],
                }
            )
            write_json_atomic(
                root / ".docops" / "tombstones.json", {"schema_version": SCHEMA_VERSION, "tombstones": tombstone_items}
            )
            overlay = _doc(
                "source_governance_registry",
                str(governance.get("id") or f"governance-{uuid.uuid4().hex}"),
                {"sources": updated_sources, "policy_revision": content_hash(updated_sources), "updated_at": _iso(now)},
                now=_iso(now),
            )
            _write_doc(_governance_path(root), overlay)
            if project_doc is not None:
                _advance_project_revision(project, project_doc)
            response = _envelope(
                ok=True,
                outcome="applied",
                project_id=project_id,
                data={
                    "source_id": source_id,
                    "claim_ids": claim_ids,
                    "destinations": record["destinations"],
                    "tombstone": record,
                },
                next_actions=["project source query", "project change propose"],
            )
            if project_doc is not None:
                _idempotency_store(project, idempotency_key, request_hash, response)
            return response
    except MasterProjectError as exc:
        return _failure(exc)
    except (OSError, TypeError, UnicodeError, ValueError) as exc:
        return _failure(MasterProjectError("INVALID_INPUT", str(exc)))


def _query_filters(filters: Mapping[str, Any] | None) -> dict[str, Any]:
    value = dict(filters or {})
    allowed = {
        "theme",
        "source_kind",
        "claim_type",
        "authority",
        "region",
        "as_of",
        "published_from",
        "published_until",
    }
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise MasterProjectError("INVALID_INPUT", f"unknown evidence filter: {unknown[0]}", field=unknown[0])
    for key in ("as_of", "published_from", "published_until"):
        if value.get(key) is not None:
            value[key] = _normalise_time_field(value[key], key, allow_date=True)
    if value.get("published_from") and value.get("published_until"):
        lower = value["published_from"]
        upper = value["published_until"]
        if _datetime(lower) > _datetime(upper):
            raise MasterProjectError("INVALID_INPUT", "published date range is inverted", field="published_until")
    if value.get("claim_type") and value["claim_type"] not in _CLAIM_TYPES:
        raise MasterProjectError("INVALID_INPUT", "claim_type filter is invalid", field="claim_type")
    if value.get("source_kind") and value["source_kind"] not in _SOURCE_TYPES:
        raise MasterProjectError("INVALID_INPUT", "source_kind filter is invalid", field="source_kind")
    if value.get("authority") and value["authority"] not in {
        "official",
        "research",
        "practitioner",
        "community",
        "unknown",
    }:
        raise MasterProjectError("INVALID_INPUT", "authority filter is invalid", field="authority")
    return value


def _claim_is_eligible(claim: Mapping[str, Any], *, root: Path, filters: Mapping[str, Any], now: datetime) -> bool:
    if filters.get("claim_type") and claim.get("classification") != filters["claim_type"]:
        return False
    if filters.get("region") and claim.get("region") not in {None, filters["region"]}:
        return False
    if not _validity_active(claim.get("validity"), now=now):
        return False
    for ref in claim.get("evidence_refs", []):
        if not isinstance(ref, Mapping):
            continue
        decision = source_use_decision(
            root, str(ref.get("source_id")), "internal_query", region=filters.get("region"), now=now
        )
        if decision.get("allowed"):
            source = next(
                (item for item in _load_governance(root)["sources"] if item.get("source_id") == ref.get("source_id")),
                {},
            )
            if (
                ref.get("observed_revision")
                and source.get("observed_revision")
                and ref.get("observed_revision") != source.get("observed_revision")
            ):
                continue
            if filters.get("source_kind") and source.get("source_type") != filters["source_kind"]:
                continue
            if filters.get("authority") and source.get("authority_class") != filters["authority"]:
                continue
            if filters.get("published_from") and (
                not source.get("published_at") or source.get("published_at") < filters["published_from"]
            ):
                continue
            if filters.get("published_until") and (
                not source.get("published_at") or source.get("published_at") > filters["published_until"]
            ):
                continue
            return True
    return False


def query_project_evidence(
    project_or_package: Path | str,
    query: str,
    *,
    filters: Mapping[str, Any] | None = None,
    session_id: str | None = None,
    adapter: Any = None,
    max_results: int = 5,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Query eligible project evidence with typed filters and explicit outcomes."""

    project = _root(project_or_package)
    try:
        if not _is_text(query):
            raise MasterProjectError("INVALID_INPUT", "query must be non-empty", field="query")
        if isinstance(max_results, bool) or not isinstance(max_results, int) or not 1 <= max_results <= 100:
            raise MasterProjectError("INVALID_INPUT", "max_results must be between 1 and 100", field="max_results")
        filter_value = _query_filters(filters)
        current = _datetime(filter_value.get("as_of") or now)
        root = _governance_root(project)
        project_doc = _read_json(_project_file(project))
        project_id = str(project_doc.get("project_id")) if isinstance(project_doc, Mapping) else None
        session = _load_session(project, session_id) if session_id and _session_file(project).is_file() else None
        if session and session.get("status") == "finalized":
            revision_id = session.get("finalized_revision_id")
        else:
            revision_id = project_doc.get("active_project_revision_id") if isinstance(project_doc, Mapping) else None
        owned = False
        retrieval = adapter
        if retrieval is None:
            from .retrieval import InMemoryRetrievalAdapter

            if (root / "rag" / "documents").is_dir():
                retrieval = InMemoryRetrievalAdapter.from_package(root)
            else:
                documents = {}
                transcript_root = root / ".docops" / "transcripts"
                if transcript_root.is_dir():
                    documents = {
                        path.name: path.read_text(encoding="utf-8", errors="replace")
                        for path in transcript_root.glob("*.md")
                        if path.is_file() and not path.is_symlink()
                    }
                retrieval = InMemoryRetrievalAdapter(documents)
            # A permitted transcript is private project evidence until a real
            # RAG rebuild is performed.  Make it queryable through this
            # evidence seam without writing it into the active index, and
            # carry its source identity so governance still filters the hit.
            transcript_root = root / ".docops" / "transcripts"
            if transcript_root.is_dir() and hasattr(retrieval, "documents"):
                governance = _load_governance(root)
                for transcript_path in sorted(transcript_root.glob("*.md")):
                    if not transcript_path.is_file() or transcript_path.is_symlink():
                        continue
                    document_key = f".docops/transcripts/{transcript_path.name}"
                    retrieval.documents.setdefault(
                        document_key,
                        transcript_path.read_text(encoding="utf-8", errors="replace"),
                    )
                    source_record = next(
                        (
                            item
                            for item in governance.get("sources", [])
                            if isinstance(item, Mapping)
                            and isinstance(item.get("transcript"), Mapping)
                            and any(
                                f".docops/transcripts/{transcript_path.name}" in str(segment.get("text_ref"))
                                for segment in item["transcript"].get("segments", [])
                                if isinstance(segment, Mapping)
                            )
                        ),
                        None,
                    )
                    if isinstance(source_record, Mapping):
                        segments = source_record.get("transcript", {}).get("segments", [])
                        retrieval.document_metadata[document_key] = {
                            "source_id": source_record.get("source_id"),
                            "observed_revision": source_record.get("observed_revision"),
                            "canonical": source_record.get("source_id"),
                            "destination": document_key,
                            "locators": [
                                {
                                    "kind": "timestamp",
                                    "label": f"{segment.get('start_ms')}-{segment.get('end_ms')}",
                                    "value": f"{segment.get('start_ms')}-{segment.get('end_ms')}",
                                    "end": str(segment.get("end_ms")),
                                }
                                for segment in segments
                                if isinstance(segment, Mapping)
                            ],
                        }
            owned = True
        # Refill above the requested page so revoked/foreign top hits do not
        # hide an eligible result immediately below them.
        hits = retrieval.search(query, max_results=min(100, max_results * 5))
        store = _load_evidence(root)
        claims = [
            dict(item)
            for item in store["claims"]
            if isinstance(item, Mapping) and _claim_is_eligible(item, root=root, filters=filter_value, now=current)
        ]
        tokens = set(re.findall(r"\w+", query.casefold(), flags=re.UNICODE))
        claims = [
            item
            for item in claims
            if not tokens or tokens & set(re.findall(r"\w+", str(item.get("text", "")).casefold(), flags=re.UNICODE))
        ]
        priority = {
            "official_rule": 5,
            "factual_observation": 4,
            "recommendation": 3,
            "experience": 2,
            "opinion": 1,
            "hypothesis": 1,
        }
        claims.sort(key=lambda item: (-priority.get(str(item.get("classification")), 0), str(item.get("claim_id"))))
        selected_claim_ids = {item.get("claim_id") for item in claims}
        conflicts = [
            dict(item)
            for item in store["conflicts"]
            if isinstance(item, Mapping)
            and item.get("status") == "open"
            and len(selected_claim_ids.intersection(item.get("claim_ids", []))) >= 2
        ]
        evidence: list[dict[str, Any]] = []
        for claim in claims:
            for ref in claim.get("evidence_refs", []):
                if isinstance(ref, Mapping) and ref not in evidence:
                    evidence.append(dict(ref))
        filtered_hits: list[dict[str, Any]] = []
        for hit in hits:
            if not isinstance(hit, Mapping):
                continue
            item = dict(hit)
            source = str(item.get("source") or "")
            metadata = item.get("metadata") if isinstance(item.get("metadata"), Mapping) else {}
            source_id = str(item.get("source_id") or metadata.get("source_id") or "")
            hit_project_id = str(item.get("project_id") or metadata.get("project_id") or "")
            if hit_project_id and hit_project_id != project_id:
                continue
            if not source_id:
                # An unbound hit cannot be proven to belong to this project or
                # to an eligible governed source, so fail closed.
                continue
            if source_id:
                decision = source_use_decision(
                    root, source_id, "internal_query", region=filter_value.get("region"), now=current
                )
                if not decision.get("allowed"):
                    continue
            locators = item.get("locators") if isinstance(item.get("locators"), list) else []
            if source_id and locators:
                observed = str(item.get("observed_revision") or metadata.get("observed_revision") or "unknown")
                for locator in locators[:3]:
                    if isinstance(locator, Mapping):
                        evidence_ref = {
                            "source_id": source_id,
                            "observed_revision": observed,
                            "document_id": source,
                            "content_hash": content_hash(str(item.get("content") or "")),
                            "locator": {
                                "kind": locator.get("kind") or "line",
                                "value": str(locator.get("label") or locator.get("value") or ""),
                                "end": locator.get("end"),
                            },
                        }
                        if evidence_ref["locator"]["value"]:
                            evidence.append(evidence_ref)
            item.pop("content", None)
            filtered_hits.append(item)
        if conflicts:
            evidence_outcome = "conflicting"
        elif claims or evidence:
            evidence_outcome = "supported"
        else:
            evidence_outcome = "insufficient_evidence"
        if owned:
            retrieval.close()
        governance = _load_governance(root)
        package_ref = _package_ref(project)
        result_data = {
            "outcome": evidence_outcome,
            "evidence": evidence[: max_results * 3],
            "claims": claims[:max_results],
            "conflicts": conflicts,
            "results": filtered_hits[:max_results],
            "applied_filters": filter_value,
            "limitations": []
            if evidence_outcome == "supported"
            else ["não há evidência elegível suficiente no snapshot solicitado"],
            "snapshot_identity": {
                "project_id": project_id,
                "project_revision_id": revision_id,
                "package_ref": package_ref,
                "governance_revision": governance.get("policy_revision", "unknown"),
            },
        }
        return _envelope(ok=True, outcome="applied", project_id=project_id, data=result_data, next_actions=[])
    except MasterProjectError as exc:
        return _failure(exc)
    except (OSError, TypeError, UnicodeError, ValueError) as exc:
        return _failure(MasterProjectError("INVALID_INPUT", str(exc)))


def _rag_candidate_root(root: Path) -> Path:
    value = _meta(root) / "rag-candidates"
    value.mkdir(parents=True, exist_ok=True)
    return value


def prepare_project_rag_candidate(
    project_root: Path | str,
    candidate_package: Path | str | None = None,
    *,
    profiles: tuple[str, ...] = ("compact", "multilingual"),
    selected_profile: str | None = None,
    language: str | None = "pt-BR",
    previous_snapshot: Path | str | None = None,
    verify_query: str | None = None,
    verify_adapter: str = "memory",
    runtime_root: Path | str | None = None,
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Prepare an isolated RAG candidate and pin its corpus/model/profile receipt.

    The active project package is only inspected.  A profile change is never
    applied in place; an external harness must provide a separately rebuilt
    candidate package, which keeps the old reader usable when that rebuild or
    model download fails.
    """

    root = _root(project_root)
    request_hash = _request_hash(
        "project.rag.prepare",
        {
            "candidate_package": str(candidate_package) if candidate_package is not None else None,
            "profiles": list(profiles),
            "selected_profile": selected_profile,
            "language": language,
            "previous_snapshot": str(previous_snapshot) if previous_snapshot is not None else None,
            "verify_query": verify_query,
            "verify_adapter": verify_adapter,
            "runtime_root": str(runtime_root) if runtime_root is not None else None,
            "expected_revision": expected_revision,
        },
    )
    try:
        project = _load_project(root)
        replay = _idempotency_replay(root, idempotency_key, request_hash)
        if replay is not None:
            return replay
        _check_expected_project_revision(project, expected_revision)
        active_package = _package_root(root)
        from .rag_snapshots import compare_embedding_profiles, snapshot_rag_package

        comparison = compare_embedding_profiles(
            active_package,
            profiles=profiles,
            language=language,
            selected_profile=selected_profile,
        )
        if candidate_package is None:
            response = _envelope(
                ok=True,
                outcome="needs_input",
                project_id=str(project["project_id"]),
                data={
                    "comparison": comparison,
                    "active_preserved": True,
                    "reason": "external full rebuild candidate is required",
                },
                next_actions=["provide isolated candidate package", "run project rag candidate prepare again"],
            )
            _idempotency_store(root, idempotency_key, request_hash, response)
            return response
        candidate = Path(os.path.abspath(os.fspath(Path(candidate_package).expanduser())))
        if candidate.is_symlink() or not candidate.is_dir():
            raise MasterProjectError("INVALID_INPUT", "candidate package must be a regular directory")
        candidate_root = _rag_candidate_root(root)
        snapshot_probe = snapshot_rag_package(
            candidate,
            previous=previous_snapshot,
            verify_query=verify_query,
            verify_adapter=verify_adapter,
            runtime_root=runtime_root,
        )
        snapshot = snapshot_probe["snapshot"]
        selected = comparison["selected_profile"]
        if snapshot.get("embedding", {}).get("profile") != selected:
            raise MasterProjectError("INVALID_INPUT", "candidate embedding profile does not match the selected profile")
        candidate_id = f"candidate-rag-{snapshot['snapshot_id'][:32]}"
        receipt_dir = candidate_root / candidate_id
        if receipt_dir.exists():
            prior_receipt = _read_json(receipt_dir / "receipt.json")
            prior_snapshot = _read_json(receipt_dir / "snapshot.json")
            if (
                isinstance(prior_receipt, Mapping)
                and isinstance(prior_snapshot, Mapping)
                and prior_receipt.get("snapshot_id") == snapshot.get("snapshot_id")
                and prior_snapshot.get("snapshot_id") == snapshot.get("snapshot_id")
            ):
                response = _envelope(
                    ok=True,
                    outcome="unchanged",
                    project_id=str(project["project_id"]),
                    data={
                        "candidate_id": candidate_id,
                        "comparison": comparison,
                        "snapshot": prior_snapshot,
                        "receipt": prior_receipt,
                        "active_preserved": True,
                    },
                    next_actions=["evaluate project candidate", "keep active reader on base until gate passes"],
                )
                _idempotency_store(root, idempotency_key, request_hash, response)
                return response
            raise MasterProjectError(
                "IDEMPOTENCY_CONFLICT", "RAG candidate identity already exists with different state"
            )
        receipt_dir.mkdir(parents=True, exist_ok=False)
        snapshot_path = receipt_dir / "snapshot.json"
        write_json_atomic(snapshot_path, snapshot)
        receipt = _doc(
            "rag_candidate_receipt",
            candidate_id,
            {
                "candidate_id": candidate_id,
                "project_id": project["project_id"],
                "candidate_package_ref": f"candidate:{candidate.name}",
                "base_package_ref": _package_ref(root),
                "snapshot_id": snapshot["snapshot_id"],
                "corpus_hash": snapshot["corpus_hash"],
                "profile": snapshot["embedding"]["profile"],
                "embedding_fingerprint": snapshot["embedding"]["embedding_fingerprint"],
                "model": copy.deepcopy(snapshot.get("model") or {}),
                "rebuild_required": bool(comparison["requires_full_rebuild"]),
                "active_preserved": True,
                "publication_allowed": False,
                "evaluation_status": "pending",
                "evaluation_hash": None,
                "extensions": {
                    "snapshot_path": f".docops-project/rag-candidates/{candidate_id}/snapshot.json",
                    "plan": snapshot_probe.get("plan"),
                },
            },
            now=_iso(now),
        )
        contract = validate_artifact("project-rag-candidate-receipt", receipt)
        if not contract.ok:
            raise MasterProjectError(
                "INVALID_INPUT", "RAG candidate receipt violates its contract", details={"errors": contract.errors}
            )
        _write_doc(receipt_dir / "receipt.json", receipt)
        _advance_project_revision(root, project)
        response = _envelope(
            ok=True,
            outcome="applied",
            project_id=str(project["project_id"]),
            data={
                "candidate_id": candidate_id,
                "comparison": comparison,
                "snapshot": snapshot,
                "plan": snapshot_probe.get("plan"),
                "receipt": receipt,
                "active_preserved": True,
            },
            next_actions=["evaluate project candidate", "keep active reader on base until gate passes"],
        )
        _idempotency_store(root, idempotency_key, request_hash, response)
        return response
    except MasterProjectError as exc:
        return _failure(exc)
    except Exception as exc:
        # RagSnapshotError is intentionally normalized at this seam so a
        # failed external download/rebuild never mutates the active package.
        return _failure(
            MasterProjectError(
                "FEATURE_NOT_ENABLED" if exc.__class__.__name__ == "RagSnapshotError" else "INVALID_INPUT", str(exc)
            )
        )


def evaluate_project_candidate(
    project_root: Path | str,
    candidate_package: Path | str,
    golden: Mapping[str, Any] | Path | str,
    *,
    candidate_id: str | None = None,
    snapshot: Mapping[str, Any] | Path | str | None = None,
    thresholds: Mapping[str, float] | None = None,
    top_k: int = 5,
    adapter: Any = None,
    runtime_root: Path | str | None = None,
    response_receipt: Mapping[str, Any] | Path | str | None = None,
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Run the existing evaluator against a pinned candidate, with critical gates."""

    root = _root(project_root)
    request_hash = _request_hash(
        "project.rag.evaluate",
        {
            "candidate_package": str(candidate_package),
            "golden": str(golden),
            "candidate_id": candidate_id,
            "snapshot": str(snapshot) if isinstance(snapshot, (Path, str)) else snapshot,
            "thresholds": dict(thresholds or {}),
            "top_k": top_k,
            "runtime_root": str(runtime_root) if runtime_root is not None else None,
            "response_receipt": str(response_receipt)
            if isinstance(response_receipt, (Path, str))
            else response_receipt,
            "expected_revision": expected_revision,
        },
    )
    try:
        project = _load_project(root)
        replay = _idempotency_replay(root, idempotency_key, request_hash)
        if replay is not None:
            return replay
        _check_expected_project_revision(project, expected_revision)
        candidate = Path(os.path.abspath(os.fspath(Path(candidate_package).expanduser())))
        if candidate.is_symlink() or not candidate.is_dir():
            raise MasterProjectError("INVALID_INPUT", "candidate package must be a regular directory")
        from .evaluator import evaluate_package
        from .rag_snapshots import build_rag_snapshot, read_rag_snapshot, validate_rag_snapshot

        resolved_candidate_id = candidate_id
        if resolved_candidate_id is None:
            raise MasterProjectError("DECISION_REQUIRED", "candidate must be prepared before evaluation")
        receipt_path = _rag_candidate_root(root) / resolved_candidate_id / "receipt.json"
        receipt = _read_json(receipt_path)
        if not isinstance(receipt, Mapping) or receipt.get("kind") != "rag_candidate_receipt":
            raise MasterProjectError("DECISION_REQUIRED", "candidate preparation receipt is missing")
        if snapshot is None:
            pinned = build_rag_snapshot(candidate)
        else:
            pinned = read_rag_snapshot(snapshot)
        if receipt.get("snapshot_id") != pinned.get("snapshot_id"):
            raise MasterProjectError("STALE_REVISION", "candidate snapshot differs from its preparation receipt")
        validate_rag_snapshot(candidate, pinned)
        report = evaluate_package(
            candidate,
            golden,
            thresholds=thresholds,
            top_k=top_k,
            adapter=adapter,
            runtime_root=runtime_root,
            response_receipt=response_receipt,
        ).to_dict()
        if adapter is None:
            report.setdefault("errors", []).append(
                {
                    "code": "harness_unavailable",
                    "message": "candidate evaluation requires an explicit retrieval harness adapter",
                }
            )
            report["ok"] = False
        report["snapshot_identity"] = {
            "snapshot_id": pinned["snapshot_id"],
            "corpus_hash": pinned["corpus_hash"],
            "profile": pinned["embedding"]["profile"],
            "embedding_fingerprint": pinned["embedding"]["embedding_fingerprint"],
            "model": copy.deepcopy(pinned.get("model") or {}),
        }
        report["golden_identity"] = content_hash(
            json.loads(Path(golden).read_text(encoding="utf-8")) if isinstance(golden, (Path, str)) else dict(golden)
        )
        report["denominators"] = {"cases": len(report.get("cases", [])), "critical_cases": 0}
        critical_errors: list[dict[str, Any]] = []
        raw_cases: Any = (
            json.loads(Path(golden).read_text(encoding="utf-8")) if isinstance(golden, (Path, str)) else golden
        )
        case_list = raw_cases.get("cases", []) if isinstance(raw_cases, Mapping) else []
        report_cases = report.get("cases", []) if isinstance(report.get("cases"), list) else []
        for index, case in enumerate(case_list):
            if not isinstance(case, Mapping):
                continue
            observed = (
                report_cases[index] if index < len(report_cases) and isinstance(report_cases[index], Mapping) else {}
            )
            case_id = case.get("case_id") or case.get("id") or f"case-{index + 1}"
            if case.get("critical") is True:
                report["denominators"]["critical_cases"] += 1
                if case.get("must_retrieve", True) is True and observed.get("expected_found") is not True:
                    critical_errors.append(
                        {
                            "code": "CRITICAL_CASE_FAILED",
                            "message": "critical Golden case was not retrieved",
                            "case_id": case_id,
                        }
                    )
            forbidden = (
                {str(item).replace("\\", "/") for item in case.get("forbidden_sources", [])}
                if isinstance(case.get("forbidden_sources"), list)
                else set()
            )
            retrieved = (
                {str(item).replace("\\", "/") for item in observed.get("retrieved", [])}
                if isinstance(observed.get("retrieved"), list)
                else set()
            )
            leaked = sorted(forbidden.intersection(retrieved))
            if leaked:
                critical_errors.append(
                    {
                        "code": "CRITICAL_SOURCE_LEAK" if case.get("critical") is True else "SOURCE_LEAK",
                        "message": "case retrieved a forbidden source",
                        "case_id": case_id,
                        "sources": leaked,
                    }
                )
        blocked_documents = (
            pinned.get("revocation", {}).get("blocked_documents", [])
            if isinstance(pinned.get("revocation"), Mapping)
            else []
        )
        if blocked_documents:
            critical_errors.append(
                {
                    "code": "CRITICAL_REVOCATION_LEAK",
                    "message": "candidate snapshot contains revoked documents",
                    "documents": [str(item) for item in blocked_documents],
                }
            )
        if critical_errors:
            report.setdefault("errors", []).extend(critical_errors)
            report["ok"] = False
        if isinstance(receipt, Mapping) and receipt.get("kind") == "rag_candidate_receipt":
            receipt = dict(receipt)
            receipt["evaluation_status"] = "passed" if report["ok"] else "blocked"
            receipt["evaluation_hash"] = content_hash(report)
            receipt.pop("content_hash", None)
            receipt["content_hash"] = content_hash(receipt)
            _write_doc(receipt_path, receipt)
        evaluation_path = _rag_candidate_root(root) / resolved_candidate_id / "evaluation.json"
        evaluation_path.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(evaluation_path, report)
        _advance_project_revision(root, project)
        errors = [
            {
                "code": str(item.get("code") or "EVALUATION_FAILED"),
                "message": str(item.get("message") or "candidate evaluation failed"),
                "retryable": False,
                "field": None,
            }
            for item in report.get("errors", [])
            if isinstance(item, Mapping)
        ]
        response = _envelope(
            ok=bool(report.get("ok")),
            outcome="applied" if report.get("ok") else "blocked",
            project_id=str(project["project_id"]),
            data={
                "candidate_id": resolved_candidate_id,
                "evaluation": report,
                "receipt": receipt,
                "active_preserved": True,
            },
            errors=errors,
            next_actions=["activate candidate after all gates"] if report.get("ok") else ["review evaluation errors"],
        )
        _idempotency_store(root, idempotency_key, request_hash, response)
        return response
    except MasterProjectError as exc:
        return _failure(exc)
    except Exception as exc:
        if exc.__class__.__name__ == "RagSnapshotError":
            code = "SOURCE_REVOKED" if "revok" in str(exc).casefold() else "FEATURE_NOT_ENABLED"
            return _failure(MasterProjectError(code, str(exc)))
        return _failure(MasterProjectError("INVALID_INPUT", str(exc)))


def _project_policy_revision(root: Path) -> str:
    revision_id = None
    project = _read_json(_project_file(root))
    if isinstance(project, Mapping):
        revision_id = project.get("working_project_revision_id") or project.get("active_project_revision_id")
    if revision_id:
        policy_path = root / "revisions" / str(revision_id) / "policy.json"
        if policy_path.is_file():
            policy = _read_json(policy_path)
            if isinstance(policy, Mapping) and isinstance(policy.get("content_hash"), str):
                return str(policy["content_hash"])
    governance = _load_governance(_governance_root(root))
    return str(governance.get("policy_revision") or "unknown")


def _effective_policy_revision(root: Path) -> str:
    """Return the policy identity used by external authorizations.

    A project revision can carry a policy artifact while the governance
    overlay changes independently (for example after a source revocation).
    Delegations therefore bind to both layers instead of trusting either one
    in isolation.
    """

    governance = _load_governance(_governance_root(root))
    return content_hash(
        {
            "project_policy_revision": _project_policy_revision(root),
            "governance_policy_revision": str(governance.get("policy_revision") or "unknown"),
        }
    )


def _graph_cycle(nodes: list[Mapping[str, Any]], edges: list[Mapping[str, Any]]) -> list[str] | None:
    node_ids = {str(node.get("id")) for node in nodes}
    adjacency: dict[str, list[str]] = {identifier: [] for identifier in node_ids}
    for edge in edges:
        source = str(edge.get("from"))
        target = str(edge.get("to"))
        if source not in node_ids or target not in node_ids:
            raise MasterProjectError("INVALID_INPUT", "dependency edge references an unknown node")
        if edge.get("relation") not in {"supports", "derived_from", "depends_on"}:
            raise MasterProjectError("INVALID_INPUT", "dependency relation is invalid")
        adjacency[source].append(target)
    visiting: set[str] = set()
    visited: set[str] = set()
    path: list[str] = []

    def visit(node: str) -> list[str] | None:
        if node in visiting:
            try:
                return path[path.index(node) :] + [node]
            except ValueError:
                return [node]
        if node in visited:
            return None
        visiting.add(node)
        path.append(node)
        for dependency in adjacency[node]:
            found = visit(dependency)
            if found:
                return found
        path.pop()
        visiting.remove(node)
        visited.add(node)
        return None

    for identifier in sorted(node_ids):
        found = visit(identifier)
        if found:
            return found
    return None


def _normalise_dependency_graph(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {"nodes": [], "edges": [], "unknown_dependencies": True}
    if not isinstance(raw, Mapping):
        raise MasterProjectError("INVALID_INPUT", "dependency_graph must be an object", field="dependency_graph")
    nodes = [dict(item) for item in raw.get("nodes", []) if isinstance(item, Mapping)]
    edges = [dict(item) for item in raw.get("edges", []) if isinstance(item, Mapping)]
    if len({str(item.get("id")) for item in nodes}) != len(nodes):
        raise MasterProjectError("INVALID_INPUT", "dependency graph node IDs must be unique")
    for node in nodes:
        if not all(isinstance(node.get(key), str) and node.get(key) for key in ("id", "kind", "revision", "hash")):
            raise MasterProjectError("INVALID_INPUT", "dependency graph nodes require id, kind, revision and hash")
        if node["kind"] not in _NODE_KINDS:
            raise MasterProjectError("INVALID_INPUT", "dependency graph node kind is invalid")
    cycle = _graph_cycle(nodes, edges)
    if cycle:
        raise MasterProjectError("INVALID_INPUT", "dependency graph contains a cycle", details={"cycle": cycle})
    return {"nodes": nodes, "edges": edges, "unknown_dependencies": bool(raw.get("unknown_dependencies", False))}


def _change_payload(body: Mapping[str, Any]) -> dict[str, Any]:
    nested = body.get("payload")
    if isinstance(nested, Mapping):
        return dict(nested)
    return dict(body)


_CHANGE_IDENTITY_FIELDS = (
    "change_id",
    "project_id",
    "base_project_revision_id",
    "base_package_ref",
    "operations",
    "requested_by",
    "reason",
    "policy_revision",
    "dependency_graph",
    "dependency_review_ack",
    "manual_reviewed",
)


def _change_identity_hash(proposal: Mapping[str, Any]) -> str:
    """Hash only the immutable semantics of a proposal, excluding lifecycle state."""

    return content_hash({key: copy.deepcopy(proposal.get(key)) for key in _CHANGE_IDENTITY_FIELDS})


def _normalise_operations(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        raise MasterProjectError(
            "INVALID_INPUT", "a change proposal requires at least one operation", field="operations"
        )
    result: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise MasterProjectError("INVALID_INPUT", "change operation must be an object")
        operation_type = str(item.get("type") or "")
        if operation_type not in _CHANGE_TYPES:
            raise MasterProjectError("INVALID_INPUT", f"unknown change operation: {operation_type}", field="operations")
        operation_payload = item.get("payload")
        if not isinstance(operation_payload, Mapping):
            raise MasterProjectError("INVALID_INPUT", "change operation payload must be an object", field="payload")
        target_id = item.get("target_id")
        if operation_type == "source_add" and not isinstance(target_id, str):
            target_id = operation_payload.get("source_id") or operation_payload.get("id")
        if not isinstance(target_id, str) or not target_id.strip():
            raise MasterProjectError(
                "INVALID_INPUT",
                "change operation target_id is required except source_add with payload.source_id",
                field="target_id",
            )
        expected_hash = item.get("expected_hash")
        if expected_hash is not None and (not isinstance(expected_hash, str) or not _HEX64.fullmatch(expected_hash)):
            raise MasterProjectError(
                "INVALID_INPUT", "expected_hash must be a SHA-256 hex string", field="expected_hash"
            )
        if operation_type != "source_add" and expected_hash is None:
            raise MasterProjectError(
                "INVALID_INPUT", "existing-entity change requires expected_hash", field="expected_hash"
            )
        result.append(
            {
                "type": operation_type,
                "target_id": target_id,
                "expected_hash": expected_hash,
                "payload": copy.deepcopy(dict(operation_payload)),
            }
        )
    return result


def _impact_for_change(
    change_id: str, base_revision: str, operations: list[Mapping[str, Any]], graph: Mapping[str, Any]
) -> dict[str, Any]:
    kinds = {str(item.get("type")) for item in operations}
    classifications = set()
    for kind in kinds:
        classifications.add(
            "factual"
            if kind.startswith("source_") or kind in {"conflict_record", "decision_correct"}
            else "conceptual"
            if kind == "skill_request"
            else "mixed"
            if kind == "policy_change"
            else "unknown"
        )
    classification = (
        "mixed"
        if len(classifications) > 1 or "mixed" in classifications
        else (next(iter(classifications)) if classifications else "unknown")
    )
    nodes = [str(item.get("target_id")) for item in operations]
    edges = [dict(item) for item in graph.get("edges", []) if isinstance(item, Mapping)]
    changed = set(nodes)
    expanded = True
    while expanded:
        expanded = False
        for edge in edges:
            if edge.get("to") in changed and edge.get("from") not in changed:
                changed.add(str(edge["from"]))
                expanded = True
    checks = {"contract", "dependency_graph"}
    if any(
        item.get("type") in {"source_add", "source_update", "source_withdraw", "source_revoke"} for item in operations
    ):
        checks.update({"rights", "privacy", "retrieval", "revocation"})
    if any(item.get("type") == "skill_request" for item in operations):
        checks.update({"derivatives", "golden", "editorial_review"})
    blockers: list[dict[str, Any]] = []
    if graph.get("unknown_dependencies"):
        blockers.append(
            {
                "code": "DEPENDENCY_UNKNOWN",
                "message": "dependency coverage is incomplete; review all dependent deliverables",
                "target_id": None,
            }
        )
    return {
        "change_id": change_id,
        "base_project_revision_id": base_revision,
        "classification": classification,
        "affected_nodes": sorted(changed),
        "required_checks": sorted(checks),
        "blockers": blockers,
        "existing_conceptual_report_ref": None,
        "unknown_dependencies": bool(graph.get("unknown_dependencies")),
    }


def _change_paths(root: Path, change_id: str) -> tuple[Path, Path, Path, Path]:
    directory = _changes_root(root) / change_id
    return directory, directory / "proposal.json", directory / "impact.json", directory / "receipts.json"


def _entity_hash_in_revision(root: Path, revision_id: str, target_id: str) -> str | None:
    revision_dir = root / "revisions" / revision_id
    for path in sorted(revision_dir.glob("*.json")):
        value = _read_json(path)
        if not isinstance(value, Mapping):
            continue
        if (
            value.get("id") == target_id
            or value.get("artifact_id") == target_id
            or value.get("decision_id") == target_id
        ):
            return str(value.get("content_hash")) if value.get("content_hash") else None
        for collection_key in ("sources", "items", "modules", "sections"):
            collection = value.get(collection_key)
            if not isinstance(collection, list):
                continue
            for item in collection:
                if isinstance(item, Mapping) and target_id in {
                    str(item.get("id")),
                    str(item.get("source_id")),
                    str(item.get("claim_id")),
                    str(item.get("decision_id")),
                    str(item.get("section_id")),
                    str(item.get("module_id")),
                }:
                    return content_hash(item)
    return None


def _load_change(root: Path, change_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    directory, proposal_path, impact_path, receipts_path = _change_paths(root, change_id)
    if not directory.is_dir():
        raise MasterProjectError("INVALID_INPUT", "change proposal is missing", field="change_id")
    proposal = _verify_doc(_read_json(proposal_path, required=True), expected_kind="change_proposal")
    stored_identity = proposal.get("change_hash")
    if stored_identity is not None and stored_identity != _change_identity_hash(proposal):
        raise MasterProjectError("INVALID_INPUT", "change proposal immutable hash is invalid")
    impact = _verify_doc(_read_json(impact_path, required=True), expected_kind="impact_report")
    receipts = _read_json(receipts_path)
    return (
        proposal,
        (dict(impact) if isinstance(impact, Mapping) else {}),
        (dict(receipts) if isinstance(receipts, Mapping) else {"receipts": []}),
    )


def propose_project_change(
    project_root: Path | str,
    change: Mapping[str, Any],
    *,
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Persist a validated change proposal and its transitive impact report."""

    root = _root(project_root)
    body = dict(change)
    payload = _change_payload(body)
    request_hash = _request_hash("project.change.propose", {"payload": payload, "expected_revision": expected_revision})
    try:
        with _project_lock(root):
            project = _load_project(root)
            replay = _idempotency_replay(root, idempotency_key, request_hash)
            if replay is not None:
                return replay
            expected = body.get("expected_revision") if expected_revision is None else expected_revision
            if expected is not None and expected != project["write_revision"]:
                raise MasterProjectError(
                    "STALE_REVISION", "project write revision does not match", field="expected_revision"
                )
            base_revision = (
                payload.get("base_project_revision_id")
                or project.get("working_project_revision_id")
                or project.get("active_project_revision_id")
            )
            if not isinstance(base_revision, str) or not base_revision:
                raise MasterProjectError(
                    "DECISION_REQUIRED", "a finalized project revision is required before a change"
                )
            if not (root / "revisions" / base_revision).is_dir():
                raise MasterProjectError(
                    "INVALID_INPUT", "base project revision does not exist", field="base_project_revision_id"
                )
            change_id = str(payload.get("change_id") or f"change-{uuid.uuid4().hex}")
            if not _ID.fullmatch(change_id):
                raise MasterProjectError("INVALID_INPUT", "change_id is invalid", field="change_id")
            operations = _normalise_operations(payload.get("operations"))
            graph = _normalise_dependency_graph(payload.get("dependency_graph"))
            requested_by = payload.get("requested_by") or "operator"
            reason = payload.get("reason")
            if not _is_text(requested_by) or not _is_text(reason):
                raise MasterProjectError("INVALID_INPUT", "requested_by and reason are required")
            policy_revision = str(payload.get("policy_revision") or _project_policy_revision(root))
            proposal = _doc(
                "change_proposal",
                change_id,
                {
                    "change_id": change_id,
                    "project_id": project["project_id"],
                    "base_project_revision_id": base_revision,
                    "base_package_ref": _package_ref(root),
                    "operations": operations,
                    "requested_by": str(requested_by),
                    "reason": str(reason),
                    "policy_revision": policy_revision,
                    "dependency_graph": graph,
                    "status": "proposed",
                },
                now=_iso(now),
            )
            proposal["change_hash"] = _change_identity_hash(
                {
                    **proposal,
                    "manual_reviewed": bool(payload.get("manual_reviewed", False)),
                    "dependency_review_ack": bool(payload.get("dependency_review_ack", False)),
                }
            )
            impact = _doc(
                "impact_report",
                f"impact-{change_id}",
                _impact_for_change(change_id, base_revision, operations, graph),
                now=_iso(now),
            )
            proposal["manual_reviewed"] = bool(payload.get("manual_reviewed", False))
            proposal["dependency_review_ack"] = bool(payload.get("dependency_review_ack", False))
            proposal.pop("content_hash", None)
            proposal["content_hash"] = content_hash(proposal)
            directory, proposal_path, impact_path, receipts_path = _change_paths(root, change_id)
            if directory.exists():
                existing = _read_json(proposal_path)
                if isinstance(existing, Mapping) and content_hash(
                    {key: value for key, value in existing.items() if key != "content_hash"}
                ) == content_hash({key: value for key, value in proposal.items() if key != "content_hash"}):
                    raise MasterProjectError("IDEMPOTENCY_CONFLICT", "change_id already exists with another proposal")
                raise MasterProjectError("IDEMPOTENCY_CONFLICT", "change_id already exists")
            directory.mkdir(parents=True, exist_ok=False)
            _write_doc(proposal_path, proposal)
            _write_doc(impact_path, impact)
            write_json_atomic(receipts_path, {"schema_version": SCHEMA_VERSION, "receipts": []})
            _advance_project_revision(root, project)
            response = _envelope(
                ok=True,
                outcome="applied",
                project_id=str(project["project_id"]),
                data={"change": proposal, "impact": impact},
                next_actions=["project change inspect", "project change prepare"],
            )
            _idempotency_store(root, idempotency_key, request_hash, response)
            return response
    except MasterProjectError as exc:
        return _failure(exc)
    except (OSError, TypeError, UnicodeError, ValueError) as exc:
        return _failure(MasterProjectError("INVALID_INPUT", str(exc)))


def inspect_project_change(project_root: Path | str, change_id: str) -> dict[str, Any]:
    """Read proposal, impact and append-only preparation/activation receipts."""

    root = _root(project_root)
    try:
        project = _load_project(root)
        proposal, impact, receipts = _load_change(root, change_id)
        return _envelope(
            ok=True,
            outcome="unchanged",
            project_id=str(project["project_id"]),
            data={"change": proposal, "impact": impact, "receipts": receipts.get("receipts", [])},
        )
    except MasterProjectError as exc:
        return _failure(exc)


def _clone_revision_for_change(
    root: Path, proposal: Mapping[str, Any], *, now: str
) -> tuple[str, Path, dict[str, Any]]:
    base_id = str(proposal["base_project_revision_id"])
    base_dir = root / "revisions" / base_id
    if not base_dir.is_dir() or base_dir.is_symlink():
        raise MasterProjectError("INVALID_INPUT", "base project revision is unavailable")
    target_id = f"project-revision-{uuid.uuid4().hex}"
    target_dir = root / "revisions" / target_id
    staging = Path(tempfile.mkdtemp(prefix=f".{target_id}.", dir=str(root / "revisions")))
    try:
        # _copy_tree_checked deliberately requires an unused destination so a
        # partial clone can never be mistaken for a complete revision.
        staging.rmdir()
        _copy_tree_checked(base_dir, staging)
        json_files = [path for path in staging.glob("*.json") if path.name != "revision.json"]
        artifacts: dict[str, dict[str, Any]] = {}
        for path in json_files:
            value = _read_json(path, required=True)
            if not isinstance(value, Mapping):
                continue
            artifact = dict(value)
            if artifact.get("revision_id") == base_id:
                artifact["revision_id"] = target_id
            artifacts[path.stem] = artifact
        operations = [dict(item) for item in proposal.get("operations", [])]
        changed_kinds: set[str] = set()
        for operation in operations:
            operation_type = operation["type"]
            payload = dict(operation.get("payload") or {})
            if operation_type == "decision_correct":
                decisions = artifacts.get("decisions")
                if decisions is None:
                    raise MasterProjectError("INVALID_INPUT", "decision artifact is missing")
                items = list(decisions.get("items") or [])
                target = operation.get("target_id")
                replaced = False
                corrected_key: str | None = None
                corrected_value: Any = None
                for item in items:
                    if isinstance(item, Mapping) and item.get("decision_id") == target:
                        replaced_item = dict(item)
                        replaced_item.update(payload)
                        replaced_item["status"] = (
                            "confirmed" if payload.get("value") is not None else replaced_item.get("status", "proposed")
                        )
                        items[items.index(item)] = replaced_item
                        corrected_key = str(item.get("key") or "")
                        corrected_value = copy.deepcopy(payload.get("value"))
                        replaced = True
                if not replaced:
                    raise MasterProjectError("INVALID_INPUT", "decision target does not exist")
                decisions["items"] = items
                changed_kinds.add("decisions")
                if corrected_key == "audience":
                    brief = artifacts.get("brief")
                    if brief is not None:
                        brief["audience"] = copy.deepcopy(corrected_value)
                        changed_kinds.add("brief")
            elif operation_type in {"source_add", "source_update", "source_withdraw", "source_revoke"}:
                governance = artifacts.get("source-governance")
                if governance is None:
                    if operation_type != "source_add":
                        raise MasterProjectError("INVALID_INPUT", "source governance artifact is missing")
                    governance = _doc(
                        "source_governance_registry",
                        f"source-governance-{uuid.uuid4().hex}",
                        {"sources": [], "policy_revision": "unknown", "updated_at": now},
                        now=now,
                    )
                    artifacts["source-governance"] = governance
                sources = [dict(item) for item in governance.get("sources", []) if isinstance(item, Mapping)]
                source_target_id = str(operation["target_id"])
                existing = next((item for item in sources if item.get("source_id") == source_target_id), None)
                if operation_type == "source_add":
                    if existing is not None:
                        raise MasterProjectError("INVALID_INPUT", "source_add target already exists")
                    source_payload = {**payload, "source_id": source_target_id}
                    source = _normalise_governance(source_payload, root=_governance_root(root), now=now)
                    sources.append(source)
                elif existing is None:
                    raise MasterProjectError("INVALID_INPUT", "source operation target does not exist")
                elif operation_type == "source_update":
                    source_payload = {**dict(existing), **payload, "source_id": source_target_id}
                    replacement = _normalise_governance(source_payload, root=_governance_root(root), now=now)
                    sources = [item for item in sources if item.get("source_id") != source_target_id]
                    sources.append(replacement)
                else:
                    replacement = dict(existing)
                    replacement["lifecycle"] = "revoked" if operation_type == "source_revoke" else "archived"
                    replacement["updated_at"] = now
                    sources = [item for item in sources if item.get("source_id") != source_target_id]
                    sources.append(replacement)
                sources.sort(key=lambda item: str(item.get("source_id")))
                governance["sources"] = sources
                governance["updated_at"] = now
                governance["policy_revision"] = content_hash(sources)
                changed_kinds.add("source-governance")
            elif operation_type == "policy_change":
                policy = artifacts.get("policy")
                if policy is None:
                    raise MasterProjectError("INVALID_INPUT", "policy artifact is missing")
                if payload.get("publication_mode") == "trusted_factual":
                    raise MasterProjectError(
                        "FEATURE_NOT_ENABLED", "trusted_factual policy is reserved for delegated authorization"
                    )
                for key, value in payload.items():
                    if key not in {"content_hash", "id", "kind", "revision_id"}:
                        policy[key] = copy.deepcopy(value)
                changed_kinds.add("policy")
        for kind, artifact in artifacts.items():
            if kind in changed_kinds:
                if isinstance(artifact.get("revision_id"), str):
                    artifact["revision_id"] = target_id
                artifact["created_at"] = now
                artifact.pop("content_hash", None)
                artifact["content_hash"] = content_hash(artifact)
                _write_doc(staging / f"{kind}.json", artifact)
                if kind in {"brief"}:
                    _write_projection(
                        staging / f"{kind}.md",
                        kind.title(),
                        {key: value for key, value in artifact.items() if key not in {"content_hash", "created_at"}},
                    )
        revision = _doc(
            "project_revision",
            target_id,
            {
                "project_revision_id": target_id,
                "project_id": proposal["project_id"],
                "parent_project_revision_id": base_id,
                "package_ref": copy.deepcopy(proposal.get("base_package_ref")),
                "artifacts": [
                    _artifact_ref(kind, artifact, f"revisions/{target_id}/{kind}.json")
                    for kind, artifact in artifacts.items()
                ],
                "pending_decision_ids": [
                    str(item)
                    for item in _read_json(staging / "decisions.json").get("items", [])
                    if isinstance(item, Mapping) and item.get("status") in {"pending", "proposed"}
                ]
                if (staging / "decisions.json").is_file()
                else [],
                "change_id": proposal["change_id"],
                "status": "private_draft",
            },
            now=now,
        )
        _write_doc(staging / "revision.json", revision)
        _write_projection(
            staging / "README.md",
            "Project revision",
            {"project_revision_id": target_id, "parent": base_id, "change_id": proposal["change_id"]},
        )
        os.replace(staging, target_dir)
        return target_id, target_dir, revision
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def prepare_project_change(
    project_root: Path | str,
    change_id: str,
    *,
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Compile a change into a new immutable revision without changing pointers."""

    root = _root(project_root)
    request_hash = _request_hash(
        "project.change.prepare", {"change_id": change_id, "expected_revision": expected_revision}
    )
    try:
        with _project_lock(root):
            project = _load_project(root)
            replay = _idempotency_replay(root, idempotency_key, request_hash)
            if replay is not None:
                return replay
            proposal, impact, receipts = _load_change(root, change_id)
            if proposal.get("project_id") != project.get("project_id"):
                raise MasterProjectError("INVALID_INPUT", "change belongs to another project")
            if expected_revision is not None and project.get("write_revision") != expected_revision:
                raise MasterProjectError(
                    "STALE_REVISION", "project write revision does not match", field="expected_revision"
                )
            current_base = project.get("working_project_revision_id") or project.get("active_project_revision_id")
            if current_base != proposal.get("base_project_revision_id"):
                raise MasterProjectError(
                    "STALE_REVISION", "change base revision is no longer current", field="base_project_revision_id"
                )
            for operation in proposal.get("operations", []):
                expected_hash = operation.get("expected_hash") if isinstance(operation, Mapping) else None
                if expected_hash is not None:
                    observed_hash = _entity_hash_in_revision(root, str(current_base), str(operation.get("target_id")))
                    if observed_hash != expected_hash:
                        raise MasterProjectError(
                            "STALE_REVISION", "change target hash no longer matches its base", field="expected_hash"
                        )
            prepared = next((item for item in receipts.get("receipts", []) if item.get("phase") == "prepared"), None)
            if (
                prepared
                and isinstance(prepared.get("project_revision_id"), str)
                and (root / "revisions" / prepared["project_revision_id"]).is_dir()
            ):
                response = _envelope(
                    ok=True,
                    outcome="unchanged",
                    project_id=str(project["project_id"]),
                    data={"change": proposal, "impact": impact, "receipt": prepared},
                    next_actions=["project change activate"],
                )
                _idempotency_store(root, idempotency_key, request_hash, response)
                return response
            if impact.get("unknown_dependencies") and not proposal.get("dependency_review_ack"):
                # Preparation is safe, but records the broad-review blocker for activation.
                pass
            current = _iso(now)
            revision_id, revision_dir, revision = _clone_revision_for_change(root, proposal, now=current)
            receipt = {
                "phase": "prepared",
                "change_id": change_id,
                "project_revision_id": revision_id,
                "base_project_revision_id": proposal["base_project_revision_id"],
                "base_package_ref": copy.deepcopy(proposal.get("base_package_ref")),
                "revision_hash": revision["content_hash"],
                "impact_hash": content_hash(impact),
                "recorded_at": current,
            }
            receipts.setdefault("receipts", []).append(receipt)
            write_json_atomic(_change_paths(root, change_id)[3], receipts)
            proposal = dict(proposal)
            proposal["status"] = "prepared"
            proposal.pop("content_hash", None)
            proposal["content_hash"] = content_hash(proposal)
            _write_doc(_change_paths(root, change_id)[1], proposal)
            _advance_project_revision(root, project)
            response = _envelope(
                ok=True,
                outcome="applied",
                project_id=str(project["project_id"]),
                data={"change": proposal, "impact": impact, "receipt": receipt, "revision": revision},
                next_actions=["project change activate"],
            )
            _idempotency_store(root, idempotency_key, request_hash, response)
            return response
    except MasterProjectError as exc:
        return _failure(exc)
    except (OSError, TypeError, UnicodeError, ValueError) as exc:
        return _failure(MasterProjectError("INVALID_INPUT", str(exc)))


def _activation_journal_path(root: Path) -> Path:
    return _meta(root) / "activation-journal.json"


def _write_activation_journal(root: Path, payload: Mapping[str, Any]) -> None:
    write_json_atomic(_activation_journal_path(root), dict(payload))


def _recover_activation_locked(root: Path) -> dict[str, Any]:
    journal = _read_json(_activation_journal_path(root))
    if not isinstance(journal, Mapping) or journal.get("status") not in {"intent", "pointer_written"}:
        return {"status": "clean"}
    project = _load_project(root)
    target = journal.get("target_project_revision_id")
    target_dir = root / "revisions" / str(target)
    target_revision = (
        _read_json(target_dir / "revision.json") if isinstance(target, str) and target_dir.is_dir() else None
    )
    exact = isinstance(target_revision, Mapping) and target_revision.get("content_hash") == journal.get(
        "target_revision_hash"
    )
    pointers_target = (
        project.get("active_project_revision_id") == target and project.get("working_project_revision_id") == target
    )
    if exact and pointers_target:
        if isinstance(journal.get("change_id"), str):
            _directory, _proposal_path, _impact_path, receipts_path = _change_paths(root, str(journal["change_id"]))
            proposal = _read_json(_proposal_path)
            if isinstance(proposal, Mapping) and proposal.get("status") != "activated":
                updated_proposal = dict(proposal)
                updated_proposal["status"] = "activated"
                updated_proposal.pop("content_hash", None)
                updated_proposal["content_hash"] = content_hash(updated_proposal)
                _write_doc(_proposal_path, updated_proposal)
            receipts = _read_json(receipts_path)
            if isinstance(receipts, Mapping):
                values = [dict(item) for item in receipts.get("receipts", []) if isinstance(item, Mapping)]
                if not any(item.get("phase") == "activated" for item in values):
                    values.append(
                        {
                            "phase": "activated",
                            "change_id": journal["change_id"],
                            "project_revision_id": target,
                            "revision_hash": journal.get("target_revision_hash"),
                            "package_ref": journal.get("target_package_ref"),
                            "recovered": True,
                            "recorded_at": _iso(),
                        }
                    )
                    write_json_atomic(receipts_path, {**dict(receipts), "receipts": values})
        committed = {**dict(journal), "status": "committed", "recovered_at": _iso()}
        _write_activation_journal(root, committed)
        return {"status": "recovered", "action": "completed", "target_project_revision_id": target}
    if project.get("active_project_revision_id") == target and not exact:
        restored = dict(project)
        restored["active_project_revision_id"] = journal.get("base_active_project_revision_id")
        restored["working_project_revision_id"] = journal.get("base_working_project_revision_id")
        restored["write_revision"] = int(project.get("write_revision", 0)) + 1
        restored.pop("content_hash", None)
        restored["content_hash"] = content_hash(restored)
        _write_doc(_project_file(root), restored)
        _write_activation_journal(root, {**dict(journal), "status": "rolled_back", "recovered_at": _iso()})
        return {"status": "recovered", "action": "restored_base", "target_project_revision_id": target}
    pointers_base = project.get("active_project_revision_id") == journal.get(
        "base_active_project_revision_id"
    ) and project.get("working_project_revision_id") == journal.get("base_working_project_revision_id")
    if pointers_base:
        _write_activation_journal(
            root, {**dict(journal), "status": "rolled_back", "recovered_at": _iso(), "reason": "promotion_not_observed"}
        )
        return {"status": "recovered", "action": "preserved_base", "target_project_revision_id": target}
    return {"status": "required", "reason": "activation journal does not prove an exact composition"}


def inspect_project_recovery(project_root: Path | str) -> dict[str, Any]:
    """Inspect a project/pointer activation journal without claiming success."""

    root = _root(project_root)
    try:
        with _project_lock(root):
            journal = _read_json(_activation_journal_path(root))
            if not isinstance(journal, Mapping) or journal.get("status") in {None, "clean", "committed", "rolled_back"}:
                return {"status": "clean"}
            project = _load_project(root)
            target = journal.get("target_project_revision_id")
            exact = False
            if isinstance(target, str):
                revision = _read_json(root / "revisions" / target / "revision.json")
                exact = isinstance(revision, Mapping) and revision.get("content_hash") == journal.get(
                    "target_revision_hash"
                )
            return {
                "status": "pending",
                "exact_target_available": exact,
                "active_pointer": project.get("active_project_revision_id"),
                "target": target,
                "action": "recover before another mutation",
            }
    except MasterProjectError as exc:
        return {"status": "required", "code": exc.code, "reason": str(exc)}


def recover_project_activation(
    project_root: Path | str,
    *,
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Complete an exact interrupted activation or restore the prior pointer."""

    root = _root(project_root)
    request_hash = _request_hash("project.recovery.run", {"expected_revision": expected_revision})
    try:
        with _project_lock(root):
            project = _load_project(root)
            replay = _idempotency_replay(root, idempotency_key, request_hash)
            if replay is not None:
                return replay
            _check_expected_project_revision(project, expected_revision)
            result = _recover_activation_locked(root)
            response = _envelope(
                ok=result.get("status") != "required",
                outcome="applied" if result.get("status") != "required" else "blocked",
                project_id=str(project["project_id"]),
                data={"recovery": result},
                next_actions=[],
            )
            _idempotency_store(root, idempotency_key, request_hash, response)
            return response
    except MasterProjectError as exc:
        return _failure(exc)


def _change_receipt(receipts: Mapping[str, Any], phase: str) -> dict[str, Any] | None:
    values = receipts.get("receipts", [])
    if not isinstance(values, list):
        return None
    return next(
        (dict(item) for item in reversed(values) if isinstance(item, Mapping) and item.get("phase") == phase), None
    )


def _target_revision_from_change(
    root: Path, proposal: Mapping[str, Any], receipts: Mapping[str, Any]
) -> tuple[str, dict[str, Any]]:
    prepared = _change_receipt(receipts, "prepared")
    if prepared is None:
        raise MasterProjectError("DECISION_REQUIRED", "change must be prepared before activation", field="change_id")
    target = str(prepared.get("project_revision_id") or "")
    revision = _read_json(root / "revisions" / target / "revision.json")
    if not isinstance(revision, Mapping) or revision.get("content_hash") != prepared.get("revision_hash"):
        raise MasterProjectError("RECOVERY_REQUIRED", "prepared revision hash cannot be verified")
    return target, dict(revision)


def _change_requires_authorization(proposal: Mapping[str, Any]) -> bool:
    return any(
        item.get("type")
        in {"source_add", "source_update", "source_withdraw", "source_revoke", "decision_correct", "conflict_record"}
        for item in proposal.get("operations", [])
        if isinstance(item, Mapping)
    )


def activate_project_change(
    project_root: Path | str,
    change_id: str,
    *,
    expected_revision: int | None = None,
    authorization_id: str | None = None,
    manual_reviewed: bool = False,
    lifecycle_receipt: Mapping[str, Any] | None = None,
    idempotency_key: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Atomically activate one prepared project composition after all gates."""

    root = _root(project_root)
    request_hash = _request_hash(
        "project.change.activate",
        {
            "change_id": change_id,
            "expected_revision": expected_revision,
            "authorization_id": authorization_id,
            "manual_reviewed": manual_reviewed,
            "lifecycle_receipt": lifecycle_receipt,
        },
    )
    try:
        with _project_lock(root):
            recovery = inspect_project_recovery(root)
            if recovery.get("status") == "pending":
                recovered = _recover_activation_locked(root)
                if recovered.get("status") == "required":
                    raise MasterProjectError("RECOVERY_REQUIRED", "an earlier activation is not proven complete")
            project = _load_project(root)
            replay = _idempotency_replay(root, idempotency_key, request_hash)
            if replay is not None:
                return replay
            if expected_revision is not None and project.get("write_revision") != expected_revision:
                raise MasterProjectError(
                    "STALE_REVISION", "project write revision does not match", field="expected_revision"
                )
            proposal, impact, receipts = _load_change(root, change_id)
            target, target_revision = _target_revision_from_change(root, proposal, receipts)
            if (
                project.get("working_project_revision_id") or project.get("active_project_revision_id")
            ) != proposal.get("base_project_revision_id"):
                raise MasterProjectError("STALE_REVISION", "change base revision is no longer current")
            if proposal.get("policy_revision") != _project_policy_revision(root):
                raise MasterProjectError("STALE_REVISION", "change policy revision is no longer current")
            if impact.get("unknown_dependencies") and not proposal.get("dependency_review_ack"):
                raise MasterProjectError(
                    "DEPENDENCY_UNKNOWN", "activation requires acknowledged broad dependency review"
                )
            if _change_requires_authorization(proposal):
                if authorization_id:
                    auth = authorize_factual_change(root, change_id, authorization_id, now=now)
                    if not auth.get("ok"):
                        raise MasterProjectError("RIGHTS_BLOCKED", "delegated authorization did not allow this change")
                elif not manual_reviewed and proposal.get("manual_reviewed") is not True:
                    # Explicit manual activation is allowed only when the caller records that review happened.
                    raise MasterProjectError(
                        "DECISION_REQUIRED", "factual change requires manual_reviewed=true or a scoped authorization"
                    )
            for operation in proposal.get("operations", []):
                if operation.get("type") == "source_revoke":
                    # Revocation is applied before pointer activation and can never be undone by rollback.
                    revoke_project_source(root, str(operation.get("target_id")), reason="change activation", now=now)
            current = _iso(now)
            journal = {
                "schema_version": SCHEMA_VERSION,
                "status": "intent",
                "change_id": change_id,
                "base_active_project_revision_id": project.get("active_project_revision_id"),
                "base_working_project_revision_id": project.get("working_project_revision_id"),
                "target_project_revision_id": target,
                "target_revision_hash": target_revision["content_hash"],
                "base_package_ref": proposal.get("base_package_ref"),
                "target_package_ref": target_revision.get("package_ref"),
                "idempotency_key": idempotency_key,
                "created_at": current,
            }
            _write_activation_journal(root, journal)
            updated = dict(project)
            updated["active_project_revision_id"] = target
            updated["working_project_revision_id"] = target
            updated["write_revision"] = int(project["write_revision"]) + 1
            updated.pop("content_hash", None)
            updated["content_hash"] = content_hash(updated)
            _write_doc(_project_file(root), updated)
            _write_activation_journal(root, {**journal, "status": "pointer_written", "pointer_written_at": current})
            if os.environ.get("DOCOPS_TEST_PROJECT_CRASH_AFTER_POINTER") == "1":
                raise RuntimeError("synthetic project crash after pointer write")
            receipt = {
                "phase": "activated",
                "change_id": change_id,
                "project_revision_id": target,
                "revision_hash": target_revision["content_hash"],
                "package_ref": target_revision.get("package_ref"),
                "lifecycle_receipt": copy.deepcopy(lifecycle_receipt),
                "recorded_at": current,
            }
            receipts.setdefault("receipts", []).append(receipt)
            write_json_atomic(_change_paths(root, change_id)[3], receipts)
            proposal = dict(proposal)
            proposal["status"] = "activated"
            proposal.pop("content_hash", None)
            proposal["content_hash"] = content_hash(proposal)
            _write_doc(_change_paths(root, change_id)[1], proposal)
            _write_activation_journal(root, {**journal, "status": "committed", "committed_at": current})
            response = _envelope(
                ok=True,
                outcome="applied",
                project_id=str(project["project_id"]),
                data={
                    "change_id": change_id,
                    "project_revision_id": target,
                    "project": _project_projection(updated),
                    "receipt": receipt,
                },
                next_actions=["project health"],
            )
            _idempotency_store(root, idempotency_key, request_hash, response)
            return response
    except MasterProjectError as exc:
        return _failure(exc)
    except RuntimeError:
        raise
    except (OSError, TypeError, UnicodeError, ValueError) as exc:
        return _failure(MasterProjectError("INVALID_INPUT", str(exc)))


def rollback_project(
    project_root: Path | str,
    target_revision_id: str,
    *,
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Move the project pointer to a validated historical revision."""

    root = _root(project_root)
    request_hash = _request_hash(
        "project.rollback", {"target_revision_id": target_revision_id, "expected_revision": expected_revision}
    )
    try:
        with _project_lock(root):
            project = _load_project(root)
            replay = _idempotency_replay(root, idempotency_key, request_hash)
            if replay is not None:
                return replay
            _check_expected_project_revision(project, expected_revision)
            target_dir = root / "revisions" / target_revision_id
            target = _verify_doc(
                _read_json(target_dir / "revision.json", required=True), expected_kind="project_revision"
            )
            if target.get("project_id") != project.get("project_id"):
                raise MasterProjectError("INVALID_INPUT", "rollback target is not a project revision")
            expected_prefix = f"revisions/{target_revision_id}/"
            for reference in target.get("artifacts", []):
                if not isinstance(reference, Mapping):
                    raise MasterProjectError("INVALID_INPUT", "rollback artifact reference is invalid")
                relative = _relative_project_path(str(reference.get("path") or ""))
                if not relative.startswith(expected_prefix):
                    raise MasterProjectError("INVALID_INPUT", "rollback artifact escapes its revision")
                artifact = _verify_doc(
                    _read_json(root / relative, required=True), expected_kind=str(reference.get("kind"))
                )
                if artifact.get("id") != reference.get("artifact_id") or artifact.get("content_hash") != reference.get(
                    "hash"
                ):
                    raise MasterProjectError("INVALID_INPUT", "rollback artifact hash does not match its revision")
            governance = _read_json(target_dir / "source-governance.json")
            revocation_payload = _read_json(_revocations_path(_governance_root(root)))
            revoked_ids = (
                {
                    item.get("source_id")
                    for item in (revocation_payload or {}).get("sources", [])
                    if isinstance(item, Mapping)
                }
                if isinstance(revocation_payload, Mapping)
                else set()
            )
            if revoked_ids:
                if not isinstance(governance, Mapping):
                    raise MasterProjectError(
                        "SOURCE_REVOKED", "rollback cannot prove that historical revision excludes revoked sources"
                    )
                if any(
                    item.get("source_id") in revoked_ids or item.get("lifecycle") == "revoked"
                    for item in governance.get("sources", [])
                    if isinstance(item, Mapping)
                ):
                    raise MasterProjectError("SOURCE_REVOKED", "rollback would reintroduce a revoked source")
            if project.get("active_project_revision_id") == target_revision_id:
                response = _envelope(
                    ok=True,
                    outcome="unchanged",
                    project_id=str(project["project_id"]),
                    data={"project_revision_id": target_revision_id},
                )
                _idempotency_store(root, idempotency_key, request_hash, response)
                return response
            updated = dict(project)
            updated["active_project_revision_id"] = target_revision_id
            updated["working_project_revision_id"] = target_revision_id
            updated["write_revision"] = int(project["write_revision"]) + 1
            updated.pop("content_hash", None)
            updated["content_hash"] = content_hash(updated)
            _write_doc(_project_file(root), updated)
            response = _envelope(
                ok=True,
                outcome="applied",
                project_id=str(project["project_id"]),
                data={
                    "project_revision_id": target_revision_id,
                    "project": _project_projection(updated),
                    "historical": True,
                },
                next_actions=[],
            )
            _idempotency_store(root, idempotency_key, request_hash, response)
            return response
    except MasterProjectError as exc:
        return _failure(exc)
    except (OSError, TypeError, UnicodeError, ValueError) as exc:
        return _failure(MasterProjectError("INVALID_INPUT", str(exc)))


def _supervisor_path(root: Path) -> Path:
    return _meta(root) / "supervisor.json"


def _supervisor_state(root: Path) -> dict[str, Any]:
    value = _read_json(_supervisor_path(root))
    if value is None:
        return _doc(
            "supervisor_status",
            "supervisor-status",
            {
                "status": "stopped",
                "tick": 0,
                "last_source_hash": None,
                "pending_events": [],
                "last_error": None,
                "missed_cycles": 0,
                "max_missed_cycles": 2,
                "queue_path": None,
            },
        )
    if not isinstance(value, Mapping) or value.get("schema_version") != SCHEMA_VERSION:
        raise MasterProjectError("INVALID_INPUT", "supervisor state is invalid")
    if value.get("kind") == "supervisor_status":
        state = _verify_doc(dict(value), expected_kind="supervisor_status")
        state.setdefault("missed_cycles", 0)
        state.setdefault("max_missed_cycles", 2)
        state.setdefault("queue_path", None)
        return state
    # Read old pre-contract state once and upgrade it without losing polling data.
    payload = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key not in {"schema_version", "kind", "id", "created_at", "content_hash"}
    }
    payload.setdefault("status", "stopped")
    payload.setdefault("tick", 0)
    payload.setdefault("last_source_hash", None)
    payload.setdefault("pending_events", [])
    payload.setdefault("last_error", None)
    payload.setdefault("missed_cycles", 0)
    payload.setdefault("max_missed_cycles", 2)
    payload.setdefault("queue_path", None)
    return _doc("supervisor_status", "supervisor-status", payload, now=value.get("created_at"))


def _save_supervisor_state(
    root: Path, state: Mapping[str, Any], *, now: datetime | date | str | None = None
) -> dict[str, Any]:
    payload = {
        key: copy.deepcopy(item)
        for key, item in state.items()
        if key not in {"schema_version", "kind", "id", "created_at", "content_hash"}
    }
    payload.setdefault("status", "stopped")
    payload.setdefault("tick", 0)
    payload.setdefault("last_source_hash", None)
    payload.setdefault("pending_events", [])
    payload.setdefault("last_error", None)
    payload.setdefault("missed_cycles", 0)
    payload.setdefault("max_missed_cycles", 2)
    payload.setdefault("queue_path", None)
    value = _doc(
        "supervisor_status",
        str(state.get("id") or "supervisor-status"),
        payload,
        now=state.get("created_at") or _iso(now),
    )
    _write_doc(_supervisor_path(root), value)
    return value


def stop_project_supervisor(
    project_root: Path | str,
    *,
    reason: str = "operator",
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Persist an explicit stop; no scheduler is installed by this operation."""

    root = _root(project_root)
    request_hash = _request_hash("project.supervisor.stop", {"reason": reason, "expected_revision": expected_revision})
    try:
        with _project_lock(root):
            project = _load_project(root)
            replay = _idempotency_replay(root, idempotency_key, request_hash)
            if replay is not None:
                return replay
            _check_expected_project_revision(project, expected_revision)
            state = _supervisor_state(root)
            state.update(
                {
                    "status": "stopped",
                    "stop_reason": str(reason),
                    "stopped_at": _iso(now),
                    "schema_version": SCHEMA_VERSION,
                }
            )
            state = _save_supervisor_state(root, state, now=now)
            project = _advance_project_revision(root, project)
            response = _envelope(
                ok=True,
                outcome="applied",
                project_id=str(project["project_id"]),
                data={"supervisor": state, "project": _project_projection(project)},
                next_actions=["supervisor run"],
            )
            _idempotency_store(root, idempotency_key, request_hash, response)
            return response
    except MasterProjectError as exc:
        return _failure(exc)


def resume_project_supervisor(
    project_root: Path | str,
    *,
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Resume persisted polling after an explicit stop."""

    root = _root(project_root)
    request_hash = _request_hash("project.supervisor.resume", {"expected_revision": expected_revision})
    try:
        with _project_lock(root):
            project = _load_project(root)
            replay = _idempotency_replay(root, idempotency_key, request_hash)
            if replay is not None:
                return replay
            _check_expected_project_revision(project, expected_revision)
            state = _supervisor_state(root)
            state.update({"status": "running", "resumed_at": _iso(now), "last_error": None})
            state = _save_supervisor_state(root, state, now=now)
            project = _advance_project_revision(root, project)
            response = _envelope(
                ok=True,
                outcome="applied",
                project_id=str(project["project_id"]),
                data={"supervisor": state, "project": _project_projection(project)},
                next_actions=["supervisor run"],
            )
            _idempotency_store(root, idempotency_key, request_hash, response)
            return response
    except MasterProjectError as exc:
        return _failure(exc)


def _redact_supervisor_payload(value: Any) -> Any:
    """Keep supervisor events actionable without persisting user content or secrets."""

    forbidden = {
        "token",
        "secret",
        "password",
        "credential",
        "query",
        "content",
        "text",
        "prompt",
        "command",
        "script",
        "shell",
    }
    if isinstance(value, Mapping):
        return {
            str(key): _redact_supervisor_payload(child)
            for key, child in value.items()
            if str(key).casefold() not in forbidden
        }
    if isinstance(value, list):
        return [_redact_supervisor_payload(item) for item in value]
    return copy.deepcopy(value)


def run_project_supervisor_once(
    project_root: Path | str,
    *,
    source_path: Path | str | None = None,
    source_id: str = "source-fixture",
    queue_path: Path | str | None = None,
    work: Mapping[str, Any] | None = None,
    max_missed_cycles: int | None = None,
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Poll once and enqueue at most one coalesced worker event."""

    root = _root(project_root)
    request_hash = _request_hash(
        "project.supervisor.run",
        {
            "source_path": str(source_path) if source_path is not None else None,
            "source_id": source_id,
            "queue_path": str(queue_path) if queue_path is not None else None,
            "work": dict(work or {}),
            "max_missed_cycles": max_missed_cycles,
            "expected_revision": expected_revision,
        },
    )
    try:
        with _project_lock(root):
            project = _load_project(root)
            replay = _idempotency_replay(root, idempotency_key, request_hash)
            if replay is not None:
                return replay
            _check_expected_project_revision(project, expected_revision)
            state = _supervisor_state(root)
            if state.get("status") != "running":
                return _envelope(
                    ok=False,
                    outcome="blocked",
                    project_id=str(project["project_id"]),
                    data={"supervisor": state},
                    errors=[_error(MasterProjectError("LEASE_BUSY", "supervisor is stopped"))],
                    next_actions=["supervisor resume"],
                )
            threshold = max_missed_cycles if max_missed_cycles is not None else state.get("max_missed_cycles", 2)
            if isinstance(threshold, bool) or not isinstance(threshold, int) or threshold < 1:
                raise MasterProjectError(
                    "INVALID_INPUT", "max_missed_cycles must be a positive integer", field="max_missed_cycles"
                )
            state["max_missed_cycles"] = threshold
            if queue_path is not None:
                state["queue_path"] = str(Path(queue_path).expanduser().resolve())
            if source_path is not None:
                source_candidate = Path(source_path).expanduser()
                if source_candidate.is_symlink() or not source_candidate.exists():
                    current = _iso(now)
                    state["tick"] = int(state.get("tick", 0)) + 1
                    state["missed_cycles"] = int(state.get("missed_cycles", 0)) + 1
                    state["last_error"] = "source_unavailable"
                    state["last_polled_at"] = current
                    state = _save_supervisor_state(root, state, now=now)
                    project = _advance_project_revision(root, project)
                    response = _envelope(
                        ok=False,
                        outcome="blocked",
                        project_id=str(project["project_id"]),
                        data={
                            "supervisor": state,
                            "project": _project_projection(project),
                            "changed": False,
                            "source_unavailable": True,
                            "threshold_reached": state["missed_cycles"] >= threshold,
                        },
                        errors=[
                            _error(
                                MasterProjectError("SOURCE_UNAVAILABLE", "polled source is unavailable", retryable=True)
                            )
                        ],
                        next_actions=["retry supervisor poll"],
                    )
                    _idempotency_store(root, idempotency_key, request_hash, response)
                    return response
            if source_path is None:
                source_hash = "no-source"
            else:
                source_hash = tree_hash(source_path)
            current = _iso(now)
            state["tick"] = int(state.get("tick", 0)) + 1
            state["missed_cycles"] = 0
            state["last_success_at"] = current
            state["last_error"] = None
            changed = source_hash != state.get("last_source_hash")
            event_result: dict[str, Any] | None = None
            if changed:
                project = _read_json(_project_file(root))
                project_id = str(project.get("project_id")) if isinstance(project, Mapping) else "project-fixture"
                job_work = _redact_supervisor_payload(dict(work or {}))
                if source_path is not None:
                    job_work.setdefault("source", str(Path(source_path).resolve()))
                job_work.setdefault("output_dir", str((_package_root(root)).resolve()))
                job_work.setdefault("publication_policy", "candidate")
                event_hash = content_hash(
                    {
                        "project_id": project_id,
                        "source_id": source_id,
                        "observed_revision": source_hash,
                        "policy_revision": _project_policy_revision(root),
                    }
                )
                event = {
                    "schema_version": SCHEMA_VERSION,
                    "event_id": f"supervisor-event-{event_hash[:32]}",
                    "type": "source_changed",
                    "package_id": project_id,
                    "source_id": source_id,
                    "observed_revision": source_hash,
                    "occurred_at": current,
                    "origin": "project-supervisor",
                    "payload": {"policy_revision": _project_policy_revision(root), "work": job_work},
                }
                event_path = _meta(root) / "supervisor-event.json"
                prior_event = _read_json(event_path)
                if not isinstance(prior_event, Mapping) or prior_event.get("event_id") != event["event_id"]:
                    write_json_atomic(event_path, event)
                else:
                    event = dict(prior_event)
                if queue_path is not None:
                    from .coordination import submit_event

                    event_result = submit_event(queue_path, event_path, now=current)
                else:
                    event_result = {"code": "event_pending", "event_id": event["event_id"]}
                state["last_source_hash"] = source_hash
                if event["event_id"] not in state.setdefault("pending_events", []):
                    state["pending_events"].append(event["event_id"])
            state["last_polled_at"] = current
            state = _save_supervisor_state(root, state, now=current)
            project = _advance_project_revision(root, project)
            response = _envelope(
                ok=True,
                outcome="applied" if changed else "unchanged",
                project_id=str(project["project_id"]),
                data={
                    "supervisor": state,
                    "project": _project_projection(project),
                    "changed": changed,
                    "event": event_result,
                },
                next_actions=["work --once"] if changed and queue_path is not None else [],
            )
            _idempotency_store(root, idempotency_key, request_hash, response)
            return response
    except MasterProjectError as exc:
        return _failure(exc)
    except (OSError, TypeError, UnicodeError, ValueError) as exc:
        return _failure(MasterProjectError("INVALID_INPUT", str(exc)))


def inspect_project_health(
    project_root: Path | str,
    *,
    queue_path: Path | str | None = None,
    max_missed_cycles: int | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Return redacted actionable health signals for project and optional queue."""

    root = _root(project_root)
    try:
        project = _load_project(root)
        recovery = inspect_project_recovery(root)
        supervisor = _supervisor_state(root)
        threshold = max_missed_cycles if max_missed_cycles is not None else supervisor.get("max_missed_cycles", 2)
        if isinstance(threshold, bool) or not isinstance(threshold, int) or threshold < 1:
            raise MasterProjectError(
                "INVALID_INPUT", "max_missed_cycles must be a positive integer", field="max_missed_cycles"
            )
        resolved_queue = queue_path or supervisor.get("queue_path")
        checks = {
            "project_state": "ok",
            "recovery": recovery.get("status", "clean"),
            "supervisor": supervisor.get("status", "stopped"),
            "package": "ok" if _package_ref(root) else "not_configured",
            "governance": "ok" if _governance_path(_governance_root(root)).is_file() else "unknown",
            "supervisor_missed_cycles": int(supervisor.get("missed_cycles", 0)),
            "supervisor_missed_cycle_threshold": threshold,
        }
        incidents: list[dict[str, Any]] = []
        if recovery.get("status") in {"pending", "required"}:
            incidents.append(
                {
                    "code": "RECOVERY_REQUIRED",
                    "severity": "high",
                    "message": "activation recovery is pending",
                    "fingerprint": content_hash({"code": "RECOVERY_REQUIRED", "project": project["project_id"]}),
                }
            )
        if supervisor.get("status") != "running":
            incidents.append(
                {
                    "code": "SUPERVISOR_STOPPED",
                    "severity": "info",
                    "message": "supervisor is stopped; no polling is active",
                    "fingerprint": content_hash({"code": "SUPERVISOR_STOPPED", "project": project["project_id"]}),
                }
            )
        if int(supervisor.get("missed_cycles", 0)) >= threshold:
            incidents.append(
                {
                    "code": "SUPERVISOR_MISSED_CYCLES",
                    "severity": "high",
                    "message": "supervisor has exceeded its missed polling threshold",
                    "fingerprint": content_hash(
                        {"code": "SUPERVISOR_MISSED_CYCLES", "project": project["project_id"], "threshold": threshold}
                    ),
                }
            )
        if resolved_queue:
            try:
                from .coordination import list_jobs

                queue = list_jobs(resolved_queue, now=now)
                checks["queue"] = {
                    "state": "ok",
                    "ready_count": int(queue.get("ready_count", 0)),
                    "job_count": len(queue.get("jobs", [])) if isinstance(queue.get("jobs"), list) else 0,
                }
            except Exception:
                checks["queue"] = {"state": "unavailable"}
                incidents.append(
                    {
                        "code": "QUEUE_UNAVAILABLE",
                        "severity": "high",
                        "message": "supervisor queue health cannot be read",
                        "fingerprint": content_hash({"code": "QUEUE_UNAVAILABLE", "project": project["project_id"]}),
                    }
                )
        incident_path = _meta(root) / "incidents.json"
        existing = _read_json(incident_path)
        persisted = (
            [dict(item) for item in existing.get("incidents", []) if isinstance(item, Mapping)]
            if isinstance(existing, Mapping)
            else []
        )
        fingerprints = {item.get("fingerprint") for item in persisted}
        for incident in incidents:
            if incident["fingerprint"] not in fingerprints:
                persisted.append({**incident, "status": "open", "first_seen_at": _iso(now), "last_seen_at": _iso(now)})
            else:
                for item in persisted:
                    if item.get("fingerprint") == incident["fingerprint"]:
                        item.update({**incident, "status": "open", "last_seen_at": _iso(now)})
                        item.pop("resolved_at", None)
        active_fingerprints = {item["fingerprint"] for item in incidents}
        for item in persisted:
            if item.get("fingerprint") not in active_fingerprints and item.get("status") == "open":
                item["status"] = "closed"
                item["resolved_at"] = _iso(now)
        write_json_atomic(incident_path, {"schema_version": SCHEMA_VERSION, "incidents": persisted})
        health = (
            "blocked"
            if recovery.get("status") in {"pending", "required"}
            else "degraded"
            if checks.get("governance") == "unknown"
            or supervisor.get("status") != "running"
            or int(supervisor.get("missed_cycles", 0)) >= threshold
            or any(item.get("severity") == "high" for item in incidents)
            else "ok"
        )
        return _envelope(
            ok=True,
            outcome="unchanged",
            project_id=str(project["project_id"]),
            data={"checks": checks, "incidents": incidents, "incident_history": persisted, "health": health},
            next_actions=["recover"] if recovery.get("status") in {"pending", "required"} else [],
        )
    except MasterProjectError as exc:
        return _failure(exc)


def _backup_copy_names(root: Path) -> list[str]:
    names = ["project.json", "init", "revisions", "changes", "package", ".docops-project", ".docops"]
    return [name for name in names if (root / name).exists() and not (root / name).is_symlink()]


def _manifest_files(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        if relative == "manifest.json":
            continue
        if any(part.casefold() in {"models_cache", "secrets", "__pycache__"} for part in path.relative_to(root).parts):
            continue
        if path.name.casefold() in {".env", ".env.local"} or path.suffix.casefold() in {".key", ".pem", ".p12"}:
            continue
        records.append({"path": relative, "sha256": file_hash(path), "size": path.stat().st_size})
    return records


def _queue_snapshot(root: Path, staging: Path) -> dict[str, Any] | None:
    """Snapshot the supervisor queue into the backup without exposing its locator."""

    state = _supervisor_state(root)
    raw_locator = state.get("queue_path")
    if raw_locator is None:
        return None
    if not isinstance(raw_locator, str) or not raw_locator.strip():
        raise MasterProjectError("QUEUE_UNAVAILABLE", "supervisor queue locator is invalid", retryable=True)
    source = Path(raw_locator).expanduser()
    if not source.is_absolute():
        source = root / source
    if source.is_symlink() or not source.is_file():
        raise MasterProjectError("QUEUE_UNAVAILABLE", "supervisor queue is unavailable", retryable=True)
    source = source.resolve()
    relative = Path(".docops-project") / "queue.sqlite3"
    destination = staging / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        if destination.is_dir():
            raise MasterProjectError("QUEUE_BACKUP_FAILED", "queue snapshot destination is not a file")
        destination.unlink()
    source_connection: sqlite3.Connection | None = None
    destination_connection: sqlite3.Connection | None = None
    try:
        source_connection = sqlite3.connect(str(source), timeout=30)
        destination_connection = sqlite3.connect(str(destination), timeout=30)
        source_connection.backup(destination_connection)
        destination_connection.commit()
    except sqlite3.Error as exc:
        raise MasterProjectError("QUEUE_BACKUP_FAILED", "supervisor queue snapshot failed", retryable=True) from exc
    finally:
        if source_connection is not None:
            source_connection.close()
        if destination_connection is not None:
            destination_connection.close()
    if not destination.is_file():
        raise MasterProjectError("QUEUE_BACKUP_FAILED", "supervisor queue snapshot is missing")
    return {
        "included": True,
        "path": relative.as_posix(),
        "snapshot_sha256": file_hash(destination),
        "snapshot_method": "sqlite_backup",
    }


def _relocate_restored_queue(staging: Path, target: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Point a restored supervisor at its isolated queue and refresh manifest hashes."""

    extensions = manifest.get("extensions") if isinstance(manifest.get("extensions"), Mapping) else {}
    queue = extensions.get("queue") if isinstance(extensions.get("queue"), Mapping) else None
    if not isinstance(queue, Mapping) or queue.get("included") is not True:
        return dict(manifest)
    relative = _relative_project_path(str(queue.get("path") or ""))
    queue_path = staging / relative
    if not queue_path.is_file() or queue_path.is_symlink():
        raise MasterProjectError("BACKUP_CHECKSUM_INVALID", "restored supervisor queue snapshot is missing")
    supervisor_path = staging / ".docops-project" / "supervisor.json"
    supervisor = _read_json(supervisor_path)
    if isinstance(supervisor, Mapping):
        updated = dict(supervisor)
        updated["queue_path"] = str(target / relative)
        updated.pop("content_hash", None)
        updated["content_hash"] = content_hash(updated)
        _write_doc(supervisor_path, updated)
    updated_manifest = dict(manifest)
    records = [dict(item) for item in manifest.get("files", []) if isinstance(item, Mapping)]
    for record in records:
        if record.get("path") == ".docops-project/supervisor.json":
            record["sha256"] = file_hash(supervisor_path)
            record["size"] = supervisor_path.stat().st_size
    updated_manifest["files"] = records
    updated_manifest.pop("content_hash", None)
    updated_manifest["content_hash"] = content_hash(updated_manifest)
    _write_doc(staging / "manifest.json", updated_manifest)
    return updated_manifest


def verify_project_backup(backup_root: Path | str, *, allow_tombstone_overrides: bool = False) -> dict[str, Any]:
    """Verify a folder backup manifest before any restore writes."""

    root = Path(os.path.abspath(os.fspath(Path(backup_root).expanduser())))
    try:
        manifest = _read_json(root / "manifest.json", required=True)
        if (
            not isinstance(manifest, Mapping)
            or manifest.get("schema_version") != SCHEMA_VERSION
            or manifest.get("kind") != "backup_manifest"
        ):
            raise MasterProjectError("INVALID_INPUT", "backup manifest is invalid")
        _verify_doc(dict(manifest), expected_kind="backup_manifest")
        errors: list[dict[str, Any]] = []
        listed: set[str] = set()
        for item in manifest.get("files", []):
            if not isinstance(item, Mapping) or not isinstance(item.get("path"), str):
                errors.append({"code": "INVALID_INPUT", "message": "backup file record is invalid"})
                continue
            relative = _relative_project_path(item["path"])
            listed.add(relative)
            path = root / relative
            if not path.is_file() or path.is_symlink():
                errors.append({"code": "BACKUP_CHECKSUM_INVALID", "message": f"backup file is missing: {relative}"})
            elif file_hash(path) != item.get("sha256") and not (
                allow_tombstone_overrides and relative.endswith("/tombstones.json")
            ):
                errors.append({"code": "BACKUP_CHECKSUM_INVALID", "message": f"backup checksum mismatch: {relative}"})
        for path in root.rglob("*"):
            if not path.is_file() or path.is_symlink() or path.name == "manifest.json":
                continue
            relative = path.relative_to(root).as_posix()
            sensitive = (
                any(
                    part.casefold() in {"models_cache", "secrets", "__pycache__"}
                    for part in path.relative_to(root).parts
                )
                or path.name.casefold() in {".env", ".env.local"}
                or path.suffix.casefold() in {".key", ".pem", ".p12"}
            )
            if sensitive:
                errors.append(
                    {
                        "code": "BACKUP_SECRET_EXCLUDED",
                        "message": f"backup contains an excluded sensitive file: {relative}",
                    }
                )
            elif relative not in listed and not relative.endswith("/tombstones.json"):
                errors.append(
                    {
                        "code": "BACKUP_UNMANIFESTED_FILE",
                        "message": f"backup file is not listed in the manifest: {relative}",
                    }
                )
        return {
            "schema_version": SCHEMA_VERSION,
            "ok": not errors,
            "backup_id": manifest.get("backup_id"),
            "files": len(manifest.get("files", [])),
            "errors": errors,
        }
    except MasterProjectError as exc:
        return {"schema_version": SCHEMA_VERSION, "ok": False, "errors": [_error(exc)]}
    except (OSError, TypeError, UnicodeError, ValueError) as exc:
        return {
            "schema_version": SCHEMA_VERSION,
            "ok": False,
            "errors": [_error(MasterProjectError("INVALID_INPUT", str(exc)))],
        }


def backup_project(
    project_root: Path | str,
    destination: Path | str,
    *,
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Create a consistent folder backup of project state, package and receipts."""

    root = _root(project_root)
    target = Path(os.path.abspath(os.fspath(Path(destination).expanduser())))
    request_hash = _request_hash(
        "project.backup",
        {"destination": str(target), "expected_revision": expected_revision},
    )
    try:
        with _project_lock(root):
            project = _load_project(root)
            replay = _idempotency_replay(root, idempotency_key, request_hash)
            if replay is not None:
                return replay
            _check_expected_project_revision(project, expected_revision)
            if target.exists():
                raise MasterProjectError("INVALID_INPUT", "backup destination already exists")
            if target == root or root in target.parents:
                raise MasterProjectError("INVALID_INPUT", "backup destination must be outside project")
            target.parent.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix=".project-backup-", dir=str(target.parent)))
            try:
                for name in _backup_copy_names(root):
                    source = root / name
                    if source.is_dir():
                        _copy_tree_checked(source, staging / name, exclude_sensitive=True)
                    elif source.is_file():
                        (staging / name).parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source, staging / name)
                queue_info = _queue_snapshot(root, staging)
                files = _manifest_files(staging)
                backup_id = f"backup-{uuid.uuid4().hex}"
                manifest = _doc(
                    "backup_manifest",
                    backup_id,
                    {
                        "backup_id": backup_id,
                        "project_id": project.get("project_id"),
                        "created_at_source": _iso(now),
                        "root_locator": "folder",
                        "files": files,
                        "excluded": ["secrets", "models_cache", ".env", "private credentials"],
                        "rpo_observed_at": _iso(now),
                        "extensions": {"queue": queue_info} if queue_info is not None else {},
                    },
                    now=_iso(now),
                )
                _write_doc(staging / "manifest.json", manifest)
                os.replace(staging, target)
            except Exception:
                shutil.rmtree(staging, ignore_errors=True)
                raise
        verification = verify_project_backup(target)
        if not verification["ok"]:
            raise MasterProjectError("BACKUP_CHECKSUM_INVALID", "new backup failed self-verification")
        response = _envelope(
            ok=True,
            outcome="applied",
            project_id=str(project["project_id"]),
            data={"backup_root": str(target), "manifest": manifest, "verification": verification},
            next_actions=["verify backup", "restore project in isolated directory"],
        )
        with _project_lock(root):
            _idempotency_store(root, idempotency_key, request_hash, response)
        return response
    except MasterProjectError as exc:
        return _failure(exc)
    except (OSError, TypeError, UnicodeError, ValueError) as exc:
        return _failure(MasterProjectError("INVALID_INPUT", str(exc)))


def restore_project(
    backup_root: Path | str,
    target_root: Path | str,
    *,
    current_root: Path | str | None = None,
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Restore a verified backup into an isolated new project directory."""

    backup = Path(os.path.abspath(os.fspath(Path(backup_root).expanduser())))
    target = Path(os.path.abspath(os.fspath(Path(target_root).expanduser())))
    request_hash = _request_hash(
        "project.restore",
        {
            "backup_root": str(backup),
            "target_root": str(target),
            "current_root": str(current_root) if current_root is not None else None,
            "expected_revision": expected_revision,
        },
    )
    try:
        ledger_root: Path | None = None
        current: Path | None = None
        project: dict[str, Any] | None = None
        if current_root is not None:
            current = _root(current_root)
            project = _load_project(current)
            ledger_root = current
            replay = _idempotency_replay(ledger_root, idempotency_key, request_hash)
            if replay is not None:
                return replay
            _check_expected_project_revision(project, expected_revision)
        elif expected_revision is not None:
            raise MasterProjectError(
                "INVALID_INPUT", "expected_revision requires current_root", field="expected_revision"
            )
        verification = verify_project_backup(backup)
        if not verification.get("ok"):
            raise MasterProjectError("BACKUP_CHECKSUM_INVALID", "backup checksum verification failed")
        manifest = _read_json(backup / "manifest.json", required=True)
        if target.exists():
            raise MasterProjectError("INVALID_INPUT", "restore target must not already exist")
        if target == backup or backup in target.parents or (current is not None and target == current):
            raise MasterProjectError("INVALID_INPUT", "restore target must be isolated from the backup")
        if current is not None and current in target.parents:
            raise MasterProjectError("INVALID_INPUT", "restore target must be outside the current project")
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".project-restore-", dir=str(target.parent)))
        try:
            shutil.copy2(backup / "manifest.json", staging / "manifest.json")
            for name in _backup_copy_names(backup):
                source = backup / name
                if source.is_dir():
                    _copy_tree_checked(source, staging / name)
                elif source.is_file():
                    (staging / name).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, staging / name)
            if current_root is not None:
                current = Path(os.path.abspath(os.fspath(Path(current_root).expanduser())))
                for relative in (
                    Path(".docops-project") / "tombstones.json",
                    Path(".docops") / "tombstones.json",
                    Path("package") / ".docops" / "tombstones.json",
                ):
                    current_tombstones = _read_json(current / relative)
                    if isinstance(current_tombstones, Mapping):
                        write_json_atomic(staging / relative, current_tombstones)
            restored_manifest = _relocate_restored_queue(staging, target, manifest)
            os.replace(staging, target)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        restored = verify_project_backup(target, allow_tombstone_overrides=True)
        # The original manifest is not copied as a project state artifact; verify the
        # copied files directly against the source manifest as well.
        if not restored["ok"]:
            raise MasterProjectError("BACKUP_CHECKSUM_INVALID", "restored project failed verification")
        project = _read_json(target / "project.json")
        response = _envelope(
            ok=True,
            outcome="applied",
            project_id=str(project.get("project_id")) if isinstance(project, Mapping) else None,
            data={
                "target_root": str(target),
                "backup_id": verification.get("backup_id"),
                "verification": restored,
                "receipts_preserved": (target / ".docops-project").is_dir(),
                "queue_restored": bool(
                    isinstance(restored_manifest.get("extensions"), Mapping)
                    and isinstance(restored_manifest["extensions"].get("queue"), Mapping)
                    and restored_manifest["extensions"]["queue"].get("included") is True
                ),
            },
            next_actions=["inspect project", "query project evidence"],
        )
        if ledger_root is not None:
            with _project_lock(ledger_root):
                _idempotency_store(ledger_root, idempotency_key, request_hash, response)
        return response
    except MasterProjectError as exc:
        return _failure(exc)
    except (OSError, TypeError, UnicodeError, ValueError) as exc:
        return _failure(MasterProjectError("INVALID_INPUT", str(exc)))


def validate_dependency_mitigation(
    raw_audit: Path | str | Mapping[str, Any],
    mitigation: Path | str | Mapping[str, Any],
    *,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Check that a tolerated dependency finding has current, scoped evidence."""

    try:
        if isinstance(raw_audit, Mapping):
            raw = dict(raw_audit)
        else:
            raw = _read_json(Path(raw_audit), required=True)
        if isinstance(mitigation, Mapping):
            decision = dict(mitigation)
        else:
            decision = _read_json(Path(mitigation), required=True)
        if not isinstance(raw, Mapping) or not isinstance(decision, Mapping):
            raise MasterProjectError("INVALID_INPUT", "dependency audit and mitigation must be JSON objects")
        current = _datetime(now)
        nested_audit = raw.get("raw_audit") if isinstance(raw.get("raw_audit"), Mapping) else {}
        findings = raw.get("findings") or raw.get("unresolved") or nested_audit.get("findings", [])
        if not isinstance(findings, list):
            findings = []
        finding_ids = {str(item.get("id")) for item in findings if isinstance(item, Mapping) and item.get("id")}
        decision_ids = (
            {str(item) for item in decision.get("finding_ids", [])}
            if isinstance(decision.get("finding_ids"), list)
            else set()
        )
        errors: list[dict[str, Any]] = []
        owner = decision.get("owner") or decision.get("responsible")
        evidence_ref = decision.get("evidence_ref") or decision.get("evidence")
        if (
            not decision.get("artifact")
            or not decision.get("lockfile_hash")
            or not decision.get("threat_model")
            or not owner
            or not evidence_ref
        ):
            errors.append(
                {
                    "code": "MITIGATION_EVIDENCE_INCOMPLETE",
                    "message": "artifact, lockfile_hash, threat_model, owner and evidence_ref are required",
                }
            )
        if not isinstance(decision.get("lockfile_hash"), str) or not _HEX64.fullmatch(
            str(decision.get("lockfile_hash"))
        ):
            errors.append({"code": "MITIGATION_LOCK_INVALID", "message": "mitigation lockfile_hash must be SHA-256"})
        if decision.get("decision") not in {"supported", "tolerated", "upgrade", "remove"}:
            errors.append({"code": "MITIGATION_DECISION_INVALID", "message": "mitigation decision is not supported"})
        if not decision_ids or decision_ids != finding_ids:
            errors.append(
                {
                    "code": "MITIGATION_SCOPE_INVALID",
                    "message": "mitigation must cover exactly the findings present in the raw audit",
                }
            )
        expires = decision.get("expires_at")
        if not isinstance(expires, str):
            errors.append({"code": "MITIGATION_EXPIRY_MISSING", "message": "mitigation expiry is required"})
        else:
            try:
                if current >= _datetime(expires):
                    errors.append({"code": "MITIGATION_EXPIRED", "message": "mitigation has expired"})
            except MasterProjectError:
                errors.append({"code": "MITIGATION_EXPIRY_INVALID", "message": "mitigation expiry is invalid"})
        raw_locks = raw.get("locks") if isinstance(raw.get("locks"), Mapping) else {}
        raw_digest = (
            raw.get("lockfile_hash") or raw_locks.get("requirements_sha256") or nested_audit.get("lockfile_hash")
        )
        if raw_digest and decision.get("lockfile_hash") != raw_digest:
            errors.append(
                {"code": "MITIGATION_LOCK_MISMATCH", "message": "mitigation lockfile hash differs from raw audit"}
            )
        raw_artifact_hash = raw.get("artifact_hash") or nested_audit.get("artifact_hash")
        if raw_artifact_hash and decision.get("artifact_hash") != raw_artifact_hash:
            errors.append(
                {"code": "MITIGATION_ARTIFACT_MISMATCH", "message": "mitigation artifact hash differs from raw audit"}
            )
        raw_threat_model = raw.get("threat_model") or nested_audit.get("threat_model")
        if raw_threat_model and decision.get("threat_model") != raw_threat_model:
            errors.append(
                {
                    "code": "MITIGATION_THREAT_MODEL_MISMATCH",
                    "message": "mitigation threat model differs from raw audit",
                }
            )
        raw_versions = {
            (str(item.get("name")), str(item.get("version")))
            for item in (raw.get("dependencies") if isinstance(raw.get("dependencies"), list) else [])
            if isinstance(item, Mapping) and item.get("name") and item.get("version")
        }
        selected_version = (
            (str(decision.get("dependency")), str(decision.get("version")))
            if decision.get("dependency") and decision.get("version")
            else None
        )
        if raw_versions and selected_version is not None and selected_version not in raw_versions:
            errors.append(
                {
                    "code": "MITIGATION_VERSION_MISMATCH",
                    "message": "mitigation dependency version is absent from raw audit",
                }
            )
        return {
            "schema_version": SCHEMA_VERSION,
            "ok": not errors,
            "status": "supported" if not errors else "blocked",
            "raw_audit_separate": True,
            "finding_ids": sorted(finding_ids),
            "errors": errors,
        }
    except MasterProjectError as exc:
        return {"schema_version": SCHEMA_VERSION, "ok": False, "status": "blocked", "errors": [_error(exc)]}
    except (OSError, TypeError, UnicodeError, ValueError) as exc:
        return {
            "schema_version": SCHEMA_VERSION,
            "ok": False,
            "status": "blocked",
            "errors": [_error(MasterProjectError("INVALID_INPUT", str(exc)))],
        }


def _load_declarative_preset(canonical_id: str, *, theme: str | None = None) -> dict[str, Any]:
    path = Path(__file__).with_name("presets") / f"{canonical_id}.json"
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MasterProjectError("FEATURE_NOT_ENABLED", f"preset data is unavailable: {canonical_id}") from exc
    if (
        not isinstance(result, Mapping)
        or result.get("id") != canonical_id
        or not isinstance(result.get("themes"), list)
    ):
        raise MasterProjectError("INVALID_INPUT", f"preset data is invalid: {canonical_id}")
    result = copy.deepcopy(dict(result))
    for item in result["themes"]:
        if isinstance(item, Mapping) and not isinstance(item.get("queries"), list):
            title = str(item.get("title") or item.get("id"))
            region = f" {result['region']}" if result.get("region") else ""
            item["queries"] = [
                f"{title} fonte oficial{region}",
                f"{title} experiência prática",
                f"{title} limitações evidência",
            ]
    if theme is not None and not any(
        isinstance(item, Mapping) and item.get("id") == theme for item in result["themes"]
    ):
        raise MasterProjectError("INVALID_INPUT", f"unknown preset theme: {theme}", field="theme")
    return result


def load_project_preset(preset_id: str, *, theme: str | None = None) -> dict[str, Any]:
    """Load a declarative preset without embedding domain rules in the core."""

    identifier = str(preset_id).strip().casefold()
    aliases = {
        "neutral": "neutral",
        "generic": "neutral",
        "neutro": "neutral",
    }
    canonical_id = aliases.get(identifier)
    if canonical_id is None:
        raise MasterProjectError("INVALID_INPUT", f"unknown preset: {preset_id}", field="preset_id")
    return _load_declarative_preset(canonical_id, theme=theme)


def apply_project_preset(
    project_root: Path | str,
    preset_id: str,
    *,
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Attach a preset suggestion to init state; it never confirms product decisions."""

    root = _root(project_root)
    request_hash = _request_hash(
        "project.preset.apply", {"preset_id": preset_id, "expected_revision": expected_revision}
    )
    try:
        preset = load_project_preset(preset_id)
        project = _read_json(_project_file(root))
        if project is None:
            started = start_project_init(
                root,
                {"language": preset.get("language"), "region": preset.get("region")},
                preset={"id": preset["id"], "version": preset["version"]},
                expected_revision=expected_revision,
                idempotency_key=None,
                now=now,
            )
            if started.get("ok"):
                _idempotency_store(root, idempotency_key, request_hash, started)
            return started
        project = _verify_doc(project, expected_kind="project")
        replay = _idempotency_replay(root, idempotency_key, request_hash)
        if replay is not None:
            return replay
        _check_expected_project_revision(project, expected_revision)
        session = _load_session(root)
        if session["status"] in {"finalized", "cancelled"}:
            raise MasterProjectError("INVALID_INPUT", "terminal session cannot change preset")
        updated = dict(session)
        updated["preset"] = {
            "id": preset["id"],
            "version": preset["version"],
            "themes": [item["id"] for item in preset["themes"]],
        }
        updated["preset_suggestions"] = preset["themes"]
        updated["session_revision"] = int(session.get("session_revision", 0)) + 1
        updated["content_hash"] = content_hash({key: value for key, value in updated.items() if key != "content_hash"})
        _write_doc(_session_file(root), updated)
        project = _advance_project_revision(root, project)
        response = _envelope(
            ok=True,
            outcome="applied",
            project_id=str(project["project_id"]),
            session_revision=int(updated["session_revision"]),
            data={"preset": preset, "session": _session_projection(updated)},
            next_actions=["init answer"],
        )
        _idempotency_store(root, idempotency_key, request_hash, response)
        return response
    except MasterProjectError as exc:
        return _failure(exc)


def project_preset_golden_candidates(preset_id: str, *, theme: str | None = None) -> list[dict[str, Any]]:
    """Create unreviewed, synthetic Golden candidates from a preset taxonomy."""

    preset = load_project_preset(preset_id, theme=theme)
    themes = [item for item in preset["themes"] if theme is None or item["id"] == theme]
    return [
        {
            "query": query,
            "theme": item["id"],
            "expected_filepath": None,
            "reviewed": False,
            "review_note": "candidate; review required",
        }
        for item in themes
        for query in item["queries"]
    ]


def _enrichment_path(root: Path, request_id: str) -> Path:
    return _meta(root) / "enrichment" / f"{request_id}.json"


def _reject_unsafe_external_payload(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            lowered = str(key).casefold()
            if lowered in {"token", "secret", "password", "credential", "command", "script", "shell", "executable"}:
                raise MasterProjectError("INVALID_INPUT", f"external enrichment field is not allowed: {key}")
            _reject_unsafe_external_payload(child)
    elif isinstance(value, list):
        for item in value:
            _reject_unsafe_external_payload(item)


def dispatch_project_enrichment(
    project_root: Path | str,
    request: Mapping[str, Any],
    *,
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Create a durable provider-neutral enrichment request."""

    root = _root(project_root)
    body = dict(request)
    request_hash = _request_hash("enrichment.dispatch", {"request": body, "expected_revision": expected_revision})
    try:
        with _project_lock(root):
            project = _load_project(root)
            replay = _idempotency_replay(root, idempotency_key, request_hash)
            if replay is not None:
                return replay
            current_revision = project.get("working_project_revision_id") or project.get("active_project_revision_id")
            base = body.get("base_project_revision_id") or current_revision
            if base != current_revision:
                raise MasterProjectError(
                    "STALE_REVISION", "enrichment base revision is stale", field="base_project_revision_id"
                )
            if expected_revision is not None and project.get("write_revision") != expected_revision:
                raise MasterProjectError(
                    "STALE_REVISION", "project write revision does not match", field="expected_revision"
                )
            _reject_unsafe_external_payload(body)
            allowed_artifacts = body.get("allowed_artifacts") or ["skill", "router"]
            if (
                not isinstance(allowed_artifacts, list)
                or not allowed_artifacts
                or not all(isinstance(item, str) and item for item in allowed_artifacts)
            ):
                raise MasterProjectError("INVALID_INPUT", "allowed_artifacts must be a non-empty list")
            allowed_artifacts = [_relative_project_path(item) for item in allowed_artifacts]
            if any(not item for item in allowed_artifacts):
                raise MasterProjectError("INVALID_INPUT", "allowed_artifacts must contain relative paths")
            request_id = str(body.get("request_id") or f"enrichment-{uuid.uuid4().hex}")
            if not _ID.fullmatch(request_id):
                raise MasterProjectError("INVALID_INPUT", "request_id is invalid", field="request_id")
            deadline = body.get("deadline_at")
            deadline = (
                _normalise_time_field(deadline, "deadline_at")
                if deadline
                else _iso(_datetime(now) + timedelta(hours=24))
            )
            budget = (
                body.get("budget")
                if isinstance(body.get("budget"), Mapping)
                else {"max_files": 4, "max_bytes": 2_000_000}
            )
            max_files = budget.get("max_files", 4)
            max_bytes = budget.get("max_bytes", 2_000_000)
            if (
                isinstance(max_files, bool)
                or not isinstance(max_files, int)
                or max_files < 1
                or isinstance(max_bytes, bool)
                or not isinstance(max_bytes, int)
                or max_bytes < 1
            ):
                raise MasterProjectError("INVALID_INPUT", "enrichment budget is invalid", field="budget")
            attempt = body.get("attempt", 1)
            if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
                raise MasterProjectError(
                    "INVALID_INPUT", "enrichment attempt must be a positive integer", field="attempt"
                )
            value = _doc(
                "enrichment_request",
                request_id,
                {
                    "request_id": request_id,
                    "project_id": project["project_id"],
                    "base_project_revision_id": base,
                    "policy_revision": _project_policy_revision(root),
                    "allowed_artifacts": list(allowed_artifacts),
                    "budget": {**dict(budget), "max_files": max_files, "max_bytes": max_bytes},
                    "state": "dispatched",
                    "attempt": attempt,
                    "deadline_at": deadline,
                    "harness": body.get("harness") if isinstance(body.get("harness"), Mapping) else None,
                    "created_at_external": _iso(now),
                },
                now=_iso(now),
            )
            path = _enrichment_path(root, request_id)
            if path.exists():
                prior = _read_json(path)
                if isinstance(prior, Mapping) and prior.get("content_hash") == value.get("content_hash"):
                    response = _envelope(
                        ok=True,
                        outcome="unchanged",
                        project_id=str(project["project_id"]),
                        data={"request": prior},
                        next_actions=["submit enrichment receipt"],
                    )
                    _idempotency_store(root, idempotency_key, request_hash, response)
                    return response
                raise MasterProjectError("IDEMPOTENCY_CONFLICT", "enrichment request ID already exists")
            path.parent.mkdir(parents=True, exist_ok=True)
            _write_doc(path, value)
            _advance_project_revision(root, project)
            response = _envelope(
                ok=True,
                outcome="applied",
                project_id=str(project["project_id"]),
                data={"request": value, "harness_available": bool(value.get("harness"))},
                next_actions=["submit enrichment receipt"],
            )
            _idempotency_store(root, idempotency_key, request_hash, response)
            return response
    except MasterProjectError as exc:
        return _failure(exc)
    except (OSError, TypeError, UnicodeError, ValueError) as exc:
        return _failure(MasterProjectError("INVALID_INPUT", str(exc)))


def inspect_project_enrichment(project_root: Path | str, request_id: str) -> dict[str, Any]:
    root = _root(project_root)
    try:
        project = _load_project(root)
        value = _verify_doc(
            _read_json(_enrichment_path(root, request_id), required=True), expected_kind="enrichment_request"
        )
        return _envelope(
            ok=True,
            outcome="unchanged",
            project_id=str(project["project_id"]),
            data={"request": value},
            next_actions=["submit enrichment receipt"] if value.get("state") == "dispatched" else [],
        )
    except MasterProjectError as exc:
        return _failure(exc)


def submit_project_enrichment(
    project_root: Path | str,
    request_id: str,
    receipt: Mapping[str, Any],
    *,
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Acknowledge an external receipt without applying it to the active project."""

    root = _root(project_root)
    request_hash = _request_hash(
        "enrichment.submit",
        {"request_id": request_id, "receipt": dict(receipt), "expected_revision": expected_revision},
    )
    try:
        with _project_lock(root):
            project = _load_project(root)
            replay = _idempotency_replay(root, idempotency_key, request_hash)
            if replay is not None:
                return replay
            _check_expected_project_revision(project, expected_revision)
            request = _verify_doc(
                _read_json(_enrichment_path(root, request_id), required=True), expected_kind="enrichment_request"
            )
            if not isinstance(receipt, Mapping):
                raise MasterProjectError("INVALID_INPUT", "enrichment receipt must be an object")
            _reject_unsafe_external_payload(receipt)
            if receipt.get("request_id") != request_id:
                raise MasterProjectError("INVALID_INPUT", "enrichment receipt request_id does not match")
            if receipt.get("policy_revision") is not None and receipt.get("policy_revision") != request.get(
                "policy_revision"
            ):
                raise MasterProjectError("STALE_REVISION", "enrichment receipt policy revision is stale")
            receipt_contract = validate_artifact("enrichment-receipt", dict(receipt))
            if not receipt_contract.ok:
                raise MasterProjectError(
                    "INVALID_INPUT",
                    "enrichment receipt violates its contract",
                    details={"errors": receipt_contract.errors},
                )
            if request.get("state") == "acknowledged":
                response = _envelope(
                    ok=True, outcome="unchanged", project_id=str(project["project_id"]), data={"request": request}
                )
                _idempotency_store(root, idempotency_key, request_hash, response)
                return response
            if request.get("state") in {"timed_out", "cancelled"}:
                raise MasterProjectError("INVALID_INPUT", "enrichment request is terminal")
            if receipt.get("base_project_revision_id") != request.get("base_project_revision_id"):
                raise MasterProjectError("STALE_REVISION", "enrichment receipt base revision is stale")
            outputs = receipt.get("outputs") or []
            if not isinstance(outputs, list):
                raise MasterProjectError("INVALID_INPUT", "enrichment receipt outputs must be a list")
            budget = request.get("budget") if isinstance(request.get("budget"), Mapping) else {}
            max_files = budget.get("max_files", 4)
            max_bytes = budget.get("max_bytes", 2_000_000)
            if (
                isinstance(max_files, bool)
                or not isinstance(max_files, int)
                or max_files < 1
                or isinstance(max_bytes, bool)
                or not isinstance(max_bytes, int)
                or max_bytes < 1
            ):
                raise MasterProjectError("INVALID_INPUT", "enrichment budget is invalid", field="budget")
            if len(outputs) > max_files:
                raise MasterProjectError("INVALID_INPUT", "enrichment output exceeds file budget")
            total_bytes = 0
            for output in outputs:
                if not isinstance(output, Mapping) or not isinstance(output.get("path"), str):
                    raise MasterProjectError("INVALID_INPUT", "enrichment output reference is invalid")
                path = _relative_project_path(output["path"])
                allowed_roots = [_relative_project_path(str(item)) for item in request.get("allowed_artifacts", [])]
                allowed = any(path == item or path.startswith(f"{item}/") for item in allowed_roots)
                if not allowed:
                    raise MasterProjectError("INVALID_INPUT", "enrichment output is outside allowed artifacts")
                if not isinstance(output.get("sha256"), str) or not _HEX64.fullmatch(output["sha256"]):
                    raise MasterProjectError("INVALID_INPUT", "enrichment output hash is invalid")
                size = output.get("size", 0)
                if isinstance(size, bool) or not isinstance(size, int) or size < 0:
                    raise MasterProjectError("INVALID_INPUT", "enrichment output size is invalid")
                total_bytes += size
            if total_bytes > max_bytes:
                raise MasterProjectError("INVALID_INPUT", "enrichment output exceeds byte budget")
            updated = dict(request)
            updated["state"] = "acknowledged"
            updated["receipt"] = copy.deepcopy(dict(receipt))
            updated["acknowledged_at"] = _iso(now)
            updated.pop("content_hash", None)
            updated["content_hash"] = content_hash(updated)
            _write_doc(_enrichment_path(root, request_id), updated)
            project = _advance_project_revision(root, project)
            response = _envelope(
                ok=True,
                outcome="applied",
                project_id=str(project["project_id"]),
                data={"request": updated, "active_changed": False},
                next_actions=["project change propose"],
            )
            _idempotency_store(root, idempotency_key, request_hash, response)
            return response
    except MasterProjectError as exc:
        return _failure(exc)


def timeout_project_enrichment(
    project_root: Path | str,
    request_id: str,
    *,
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    root = _root(project_root)
    request_hash = _request_hash(
        "enrichment.timeout", {"request_id": request_id, "expected_revision": expected_revision}
    )
    try:
        with _project_lock(root):
            project = _load_project(root)
            replay = _idempotency_replay(root, idempotency_key, request_hash)
            if replay is not None:
                return replay
            _check_expected_project_revision(project, expected_revision)
            request = _verify_doc(
                _read_json(_enrichment_path(root, request_id), required=True), expected_kind="enrichment_request"
            )
            if request.get("project_id") != project.get("project_id"):
                raise MasterProjectError("INVALID_INPUT", "enrichment request belongs to another project")
            current = _datetime(now)
            if request.get("state") == "dispatched" and current >= _datetime(request["deadline_at"]):
                updated = dict(request)
                updated["state"] = "timed_out"
                updated["timed_out_at"] = _iso(now)
                updated.pop("content_hash", None)
                updated["content_hash"] = content_hash(updated)
                _write_doc(_enrichment_path(root, request_id), updated)
                project = _advance_project_revision(root, project)
                response = _envelope(
                    ok=True,
                    outcome="applied",
                    project_id=str(project["project_id"]),
                    data={"request": updated},
                    next_actions=["retry enrichment"],
                )
                _idempotency_store(root, idempotency_key, request_hash, response)
                return response
            response = _envelope(
                ok=True,
                outcome="unchanged",
                project_id=str(request["project_id"]),
                data={"request": request},
                next_actions=[],
            )
            _idempotency_store(root, idempotency_key, request_hash, response)
            return response
    except MasterProjectError as exc:
        return _failure(exc)


def retry_project_enrichment(
    project_root: Path | str,
    request_id: str,
    *,
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    root = _root(project_root)
    request_hash = _request_hash("enrichment.retry", {"request_id": request_id, "expected_revision": expected_revision})
    try:
        with _project_lock(root):
            project = _load_project(root)
            replay = _idempotency_replay(root, idempotency_key, request_hash)
            if replay is not None:
                return replay
            _check_expected_project_revision(project, expected_revision)
            request = _verify_doc(
                _read_json(_enrichment_path(root, request_id), required=True), expected_kind="enrichment_request"
            )
            if request.get("project_id") != project.get("project_id"):
                raise MasterProjectError("INVALID_INPUT", "enrichment request belongs to another project")
            if request.get("state") not in {"timed_out", "failed"}:
                response = _envelope(
                    ok=True,
                    outcome="unchanged",
                    project_id=str(request["project_id"]),
                    data={"request": request},
                    next_actions=[],
                )
                _idempotency_store(root, idempotency_key, request_hash, response)
                return response
            updated = dict(request)
            updated["state"] = "dispatched"
            updated["attempt"] = int(request.get("attempt", 1)) + 1
            updated["retried_at"] = _iso(now)
            updated["deadline_at"] = _iso(_datetime(now) + timedelta(hours=24))
            updated.pop("content_hash", None)
            updated["content_hash"] = content_hash(updated)
            _write_doc(_enrichment_path(root, request_id), updated)
            project = _advance_project_revision(root, project)
            response = _envelope(
                ok=True,
                outcome="applied",
                project_id=str(project["project_id"]),
                data={"request": updated, "same_request_id": True},
                next_actions=["submit enrichment receipt"],
            )
            _idempotency_store(root, idempotency_key, request_hash, response)
            return response
    except MasterProjectError as exc:
        return _failure(exc)


def _authorizations_path(root: Path) -> Path:
    return _meta(root) / "authorizations.json"


def _authorizations(root: Path) -> list[dict[str, Any]]:
    value = _read_json(_authorizations_path(root))
    if value is None:
        return []
    if not isinstance(value, Mapping) or not isinstance(value.get("authorizations"), list):
        raise MasterProjectError("INVALID_INPUT", "delegated authorization store is invalid")
    records: list[dict[str, Any]] = []
    for item in value["authorizations"]:
        if not isinstance(item, Mapping):
            continue
        record = dict(item)
        if record.get("kind") == "delegated_authorization":
            record = _verify_doc(record, expected_kind="delegated_authorization")
        records.append(record)
    return records


def create_delegated_authorization(
    project_root: Path | str,
    authorization: Mapping[str, Any],
    *,
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Persist a narrow, authenticated factual delegation; never generic publish authority."""

    root = _root(project_root)
    body = dict(authorization)
    request_hash = _request_hash("delegation.create", {"authorization": body, "expected_revision": expected_revision})
    try:
        project = _load_project(root)
        replay = _idempotency_replay(root, idempotency_key, request_hash)
        if replay is not None:
            return replay
        _check_expected_project_revision(project, expected_revision)
        value = body
        _reject_unsafe_external_payload({key: child for key, child in value.items() if key not in {"budget"}})
        auth_id = str(value.get("authorization_id") or f"authorization-{uuid.uuid4().hex}")
        owner = value.get("owner")
        actions = [str(item) for item in value.get("actions", [])] if isinstance(value.get("actions"), list) else []
        forbidden = {
            "publish",
            "approve",
            "activate",
            "public_distribution",
            "change_price",
            "change_guarantee",
            "change_cta",
            "generic_autopublish",
        }
        allowed_actions = {"factual_update", "source_update", "source_revoke", "indexing", "retrieval"}
        if not _is_text(owner) or not actions or not set(actions) <= allowed_actions or set(actions) & forbidden:
            raise MasterProjectError("INVALID_INPUT", "delegated authorization scope is invalid")
        authority_ref = value.get("authority_ref") or value.get("authenticated_ref")
        if not _is_text(authority_ref):
            raise MasterProjectError("DECISION_REQUIRED", "authenticated authority reference is required")
        expires = _normalise_time_field(value.get("expires_at"), "expires_at")
        if expires is None or _datetime(expires) <= _datetime(now):
            raise MasterProjectError("INVALID_INPUT", "authorization must expire in the future")
        budget = (
            value.get("budget")
            if isinstance(value.get("budget"), Mapping)
            else {"max_operations": 1, "used_operations": 0}
        )
        max_operations = budget.get("max_operations", 1)
        used_operations = budget.get("used_operations", 0)
        if (
            isinstance(max_operations, bool)
            or not isinstance(max_operations, int)
            or max_operations < 1
            or isinstance(used_operations, bool)
            or not isinstance(used_operations, int)
            or used_operations < 0
            or used_operations > max_operations
        ):
            raise MasterProjectError("INVALID_INPUT", "authorization budget is invalid", field="budget")
        source_ids = (
            [str(item) for item in value.get("source_ids", [])] if isinstance(value.get("source_ids"), list) else []
        )
        if (
            any(action in {"source_update", "source_revoke", "indexing", "retrieval"} for action in actions)
            and not source_ids
        ):
            raise MasterProjectError(
                "INVALID_INPUT", "source-scoped delegation requires source_ids", field="source_ids"
            )
        if any(not _ID.fullmatch(source_id) for source_id in source_ids):
            raise MasterProjectError("INVALID_INPUT", "source_ids must contain stable identifiers", field="source_ids")
        record = _doc(
            "delegated_authorization",
            auth_id,
            {
                "authorization_id": auth_id,
                "project_id": project["project_id"],
                "owner": str(owner),
                "actions": actions,
                "source_ids": source_ids,
                "expires_at": expires,
                "budget": {**dict(budget), "max_operations": max_operations, "used_operations": used_operations},
                "authority_ref": str(authority_ref),
                "policy_revision": _effective_policy_revision(root),
                "kill_switch": bool(value.get("kill_switch", False)),
                "status": "active",
            },
            now=_iso(now),
        )
        records = [item for item in _authorizations(root) if item.get("authorization_id") != auth_id]
        records.append(record)
        write_json_atomic(_authorizations_path(root), {"schema_version": SCHEMA_VERSION, "authorizations": records})
        project = _advance_project_revision(root, project)
        response = _envelope(
            ok=True,
            outcome="applied",
            project_id=str(project["project_id"]),
            data={"authorization": record},
            next_actions=["authorize factual change"],
        )
        _idempotency_store(root, idempotency_key, request_hash, response)
        return response
    except MasterProjectError as exc:
        return _failure(exc)


def revoke_delegated_authorization(
    project_root: Path | str,
    authorization_id: str,
    *,
    reason: str = "operator",
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    root = _root(project_root)
    request_hash = _request_hash(
        "delegation.revoke",
        {"authorization_id": authorization_id, "reason": reason, "expected_revision": expected_revision},
    )
    try:
        project = _load_project(root)
        replay = _idempotency_replay(root, idempotency_key, request_hash)
        if replay is not None:
            return replay
        _check_expected_project_revision(project, expected_revision)
        records = _authorizations(root)
        found = False
        for item in records:
            if item.get("authorization_id") == authorization_id:
                item["status"] = "revoked"
                item["revoked_at"] = _iso(now)
                item["reason"] = str(reason)
                item.pop("content_hash", None)
                item["content_hash"] = content_hash(item)
                found = True
        if not found:
            raise MasterProjectError("INVALID_INPUT", "authorization does not exist")
        write_json_atomic(_authorizations_path(root), {"schema_version": SCHEMA_VERSION, "authorizations": records})
        project = _advance_project_revision(root, project)
        response = _envelope(
            ok=True,
            outcome="applied",
            project_id=str(project["project_id"]),
            data={"authorization_id": authorization_id, "status": "revoked"},
            next_actions=[],
        )
        _idempotency_store(root, idempotency_key, request_hash, response)
        return response
    except MasterProjectError as exc:
        return _failure(exc)


def authorize_factual_change(
    project_root: Path | str,
    change_id: str,
    authorization_id: str,
    *,
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
    now: datetime | date | str | None = None,
) -> dict[str, Any]:
    """Check a delegation against one factual proposal and persist its receipt."""

    root = _root(project_root)
    request_hash = _request_hash(
        "delegation.authorize",
        {"change_id": change_id, "authorization_id": authorization_id, "expected_revision": expected_revision},
    )
    try:
        project = _load_project(root)
        replay = _idempotency_replay(root, idempotency_key, request_hash)
        if replay is not None:
            return replay
        _check_expected_project_revision(project, expected_revision)
        proposal, _impact, receipts = _load_change(root, change_id)
        auth = next((item for item in _authorizations(root) if item.get("authorization_id") == authorization_id), None)
        if not isinstance(auth, Mapping) or auth.get("status") not in {"active", "exhausted"}:
            raise MasterProjectError("RIGHTS_BLOCKED", "delegated authorization is missing or revoked")
        if _datetime(now) >= _datetime(auth["expires_at"]) or auth.get("kill_switch") is True:
            raise MasterProjectError("RIGHTS_BLOCKED", "delegated authorization is expired or killed")
        policy_revision = _effective_policy_revision(root)
        if auth.get("policy_revision") != policy_revision:
            raise MasterProjectError("RIGHTS_BLOCKED", "delegated authorization is bound to a stale policy revision")
        proposal_hash = str(proposal.get("change_hash") or _change_identity_hash(proposal))
        if not _HEX64.fullmatch(proposal_hash):
            raise MasterProjectError("INVALID_INPUT", "change proposal hash is invalid")
        prior_receipts = receipts.get("receipts", [])
        if not isinstance(prior_receipts, list):
            raise MasterProjectError("INVALID_INPUT", "change receipts are invalid")
        prior_authorization = next(
            (
                item
                for item in reversed(prior_receipts)
                if isinstance(item, Mapping)
                and item.get("phase") == "authorization"
                and item.get("authorization_id") == authorization_id
            ),
            None,
        )
        if prior_authorization is not None:
            same_change = (
                prior_authorization.get("proposal_hash") == proposal_hash
                and prior_authorization.get("base_project_revision_id") == proposal.get("base_project_revision_id")
                and prior_authorization.get("policy_revision") == policy_revision
            )
            if not same_change:
                raise MasterProjectError(
                    "RIGHTS_BLOCKED", "authorization receipt does not match the exact change proposal"
                )
            response = _envelope(
                ok=True,
                outcome="unchanged",
                project_id=str(project["project_id"]),
                data={"receipt": dict(prior_authorization), "idempotent": True},
                next_actions=["project change activate"],
            )
            _idempotency_store(root, idempotency_key, request_hash, response)
            return response
        operations = [item for item in proposal.get("operations", []) if isinstance(item, Mapping)]
        if any(
            item.get("type")
            not in {"source_add", "source_update", "source_withdraw", "source_revoke", "decision_correct"}
            for item in operations
        ):
            raise MasterProjectError("RIGHTS_BLOCKED", "delegation cannot authorize editorial or commercial changes")
        required_action = (
            "source_revoke"
            if any(item.get("type") == "source_revoke" for item in operations)
            else "source_update"
            if any(str(item.get("type", "")).startswith("source_") for item in operations)
            else "factual_update"
        )
        if required_action not in auth.get("actions", []):
            raise MasterProjectError("RIGHTS_BLOCKED", "delegation does not include the required action")
        allowed_sources = set(auth.get("source_ids", []))
        if allowed_sources and any(
            str(item.get("target_id")) not in allowed_sources
            for item in operations
            if str(item.get("type", "")).startswith("source_")
        ):
            raise MasterProjectError("RIGHTS_BLOCKED", "delegation is outside its source scope")
        for item in operations:
            if item.get("type") not in {"source_add", "source_update"}:
                continue
            payload = item.get("payload") if isinstance(item.get("payload"), Mapping) else {}
            if "use_policy" in payload:
                use_policy = payload.get("use_policy")
                grants = use_policy.get("grants") if isinstance(use_policy, Mapping) else None
                grant_map = (
                    {str(grant.get("purpose")): grant for grant in grants if isinstance(grant, Mapping)}
                    if isinstance(grants, list)
                    else {}
                )
                if any(
                    not isinstance(grant_map.get(purpose), Mapping) or grant_map[purpose].get("decision") != "allowed"
                    for purpose in ("acquisition", "storage")
                ):
                    raise MasterProjectError(
                        "RIGHTS_BLOCKED",
                        "delegation cannot approve a source with uncertain acquisition or storage rights",
                    )
        budget = dict(auth.get("budget") or {})
        used = int(budget.get("used_operations", 0))
        maximum = int(budget.get("max_operations", 1))
        if used >= maximum:
            raise MasterProjectError("RIGHTS_BLOCKED", "delegated operation budget is exhausted")
        budget["used_operations"] = used + 1
        if budget["used_operations"] >= maximum:
            next_status = "exhausted"
        else:
            next_status = "active"
        auth_records = _authorizations(root)
        for item in auth_records:
            if item.get("authorization_id") == authorization_id:
                item["budget"] = budget
                item["status"] = next_status
                item.pop("content_hash", None)
                item["content_hash"] = content_hash(item)
        write_json_atomic(
            _authorizations_path(root), {"schema_version": SCHEMA_VERSION, "authorizations": auth_records}
        )
        receipt = {
            "phase": "authorization",
            "change_id": change_id,
            "authorization_id": authorization_id,
            "proposal_hash": proposal_hash,
            "base_project_revision_id": proposal.get("base_project_revision_id"),
            "policy_revision": policy_revision,
            "authority_ref": auth.get("authority_ref"),
            "recorded_at": _iso(now),
        }
        receipts.setdefault("receipts", []).append(receipt)
        write_json_atomic(_change_paths(root, change_id)[3], receipts)
        project = _advance_project_revision(root, project)
        response = _envelope(
            ok=True,
            outcome="applied",
            project_id=str(project["project_id"]),
            data={"receipt": receipt},
            next_actions=["project change activate"],
        )
        _idempotency_store(root, idempotency_key, request_hash, response)
        return response
    except MasterProjectError as exc:
        return _failure(exc)
