"""Small resumable project/operation service for the Farol 2.0 public seam."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Mapping

from .api_types import KnowledgeProjectV2, OperationResultV2
from .revisions import content_hash
from .storage import write_json_atomic


class ProjectError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class ProjectService:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).expanduser().resolve()
        self.state_path = self.root / ".docops" / "knowledge-project.json"
        self.operations_path = self.root / ".docops" / "operations-v2.json"

    def start(
        self,
        name: str,
        objective: str,
        sources: list[Mapping[str, Any]],
        *,
        idempotency_key: str,
        session_id: str | None = None,
    ) -> OperationResultV2:
        if not idempotency_key:
            raise ProjectError("idempotency_required", "idempotency_key is required")
        payload = {"name": name, "objective": objective, "sources": [dict(source) for source in sources]}
        previous = self._read_operation(idempotency_key)
        if previous is not None:
            if previous.get("request_hash") != content_hash(payload):
                raise ProjectError("idempotency_conflict", "idempotency key was reused with a different payload")
            return _operation_result(previous["result"])
        if not name.strip() or not objective.strip():
            raise ProjectError("input_required", "name and objective are required")
        normalized_sources = [_normalize_source(source) for source in sources]
        project_id = f"project-{content_hash(payload)[:24]}"
        project = KnowledgeProjectV2(
            project_id=project_id,
            session_id=session_id or f"session-{uuid.uuid4().hex[:24]}",
            revision=1,
            name=name.strip(),
            objective=objective.strip(),
            sources=normalized_sources,
            status="proposed",
        )
        self._write_project(project)
        operation_identity = content_hash({"key": idempotency_key, "project": project_id})
        result = OperationResultV2(
            operation_id=f"operation-{operation_identity[:24]}",
            project_id=project.project_id,
            idempotency_key=idempotency_key,
            status="needs_input",
            revision=project.revision,
            pending=[
                {"kind": "rights", "source_ids": [source["source_id"] for source in normalized_sources]},
                {"kind": "taxonomy_approval", "reason": "initial taxonomy activation requires approval"},
            ],
            next_action="authorize sources and approve the initial taxonomy",
            blockers=[],
            result=project.to_dict(),
        )
        self._write_operation(idempotency_key, payload, result)
        return result

    def inspect(self) -> KnowledgeProjectV2:
        payload = self._read_json(self.state_path)
        if not payload:
            raise ProjectError("project_missing", "Farol 2.0 project has not been started")
        return KnowledgeProjectV2(
            project_id=str(payload["project_id"]),
            session_id=str(payload["session_id"]),
            revision=int(payload["revision"]),
            name=str(payload["name"]),
            objective=str(payload["objective"]),
            sources=[dict(value) for value in payload.get("sources", [])],
            taxonomy_revision=payload.get("taxonomy_revision")
            if isinstance(payload.get("taxonomy_revision"), str)
            else None,
            active_composition_id=payload.get("active_composition_id")
            if isinstance(payload.get("active_composition_id"), str)
            else None,
            status=str(payload.get("status") or "proposed"),
            created_at=str(payload.get("created_at") or "1970-01-01T00:00:00Z"),
            extensions=dict(payload.get("extensions") or {}),
        )

    def apply(
        self,
        operation: str,
        inputs: Mapping[str, Any],
        *,
        expected_revision: int,
        idempotency_key: str,
    ) -> OperationResultV2:
        if not idempotency_key:
            raise ProjectError("idempotency_required", "idempotency_key is required")
        project = self.inspect()
        if expected_revision != project.revision:
            raise ProjectError("revision_conflict", "project revision does not match expected_revision")
        if operation not in {"plan", "apply", "resume", "inspect", "migrate"}:
            raise ProjectError("operation_invalid", "unsupported v2 operation")
        payload = {"operation": operation, "inputs": dict(inputs), "expected_revision": expected_revision}
        previous = self._read_operation(idempotency_key)
        if previous is not None:
            if previous.get("request_hash") != content_hash(payload):
                raise ProjectError("idempotency_conflict", "idempotency key was reused with a different payload")
            return _operation_result(previous["result"])
        operation_identity = content_hash({"key": idempotency_key, "project": project.project_id})
        result = OperationResultV2(
            operation_id=f"operation-{operation_identity[:24]}",
            project_id=project.project_id,
            idempotency_key=idempotency_key,
            status="succeeded" if operation in {"plan", "inspect"} else "needs_input",
            revision=project.revision,
            pending=[] if operation in {"plan", "inspect"} else [{"kind": "external_gate", "operation": operation}],
            next_action="inspect project state" if operation in {"plan", "inspect"} else "complete the pending gate",
            blockers=[],
            result={"operation": operation, "inputs": dict(inputs), "project": project.to_dict()},
        )
        self._write_operation(idempotency_key, payload, result)
        return result

    def _write_project(self, project: KnowledgeProjectV2) -> None:
        write_json_atomic(self.state_path, project.to_dict())

    def _write_operation(self, key: str, payload: Mapping[str, Any], result: OperationResultV2) -> None:
        operations = self._read_json(self.operations_path)
        operations[key] = {"request_hash": content_hash(payload), "result": result.to_dict()}
        write_json_atomic(self.operations_path, operations)

    def _read_operation(self, key: str) -> dict[str, Any] | None:
        value = self._read_json(self.operations_path).get(key)
        return dict(value) if isinstance(value, Mapping) else None

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {}
        return dict(value) if isinstance(value, Mapping) else {}


def _normalize_source(source: Mapping[str, Any]) -> dict[str, Any]:
    source_id = str(source.get("source_id") or "")
    canonical = str(source.get("canonical") or "")
    if not source_id or not canonical:
        raise ProjectError("source_invalid", "source_id and canonical are required")
    return {
        "source_id": source_id,
        "canonical": canonical,
        "source_revision": str(source.get("source_revision") or "proposed"),
        "status": str(source.get("status") or "proposed"),
        "rights": str(source.get("rights") or "unknown"),
        "privacy": str(source.get("privacy") or "unknown"),
        "language": str(source.get("language") or "und"),
        "purpose": str(source.get("purpose") or "knowledge"),
        "version": source.get("version") if isinstance(source.get("version"), str) else None,
        "region": source.get("region") if isinstance(source.get("region"), str) else None,
    }


def _operation_result(value: Mapping[str, Any]) -> OperationResultV2:
    return OperationResultV2(
        operation_id=str(value.get("operation_id") or ""),
        project_id=str(value.get("project_id") or ""),
        idempotency_key=str(value.get("idempotency_key") or ""),
        status=str(value.get("status") or "failed"),
        revision=int(value.get("revision") or 0),
        pending=[dict(item) for item in value.get("pending", []) if isinstance(item, Mapping)],
        next_action=str(value.get("next_action") or "inspect project state"),
        blockers=[dict(item) for item in value.get("blockers", []) if isinstance(item, Mapping)],
        result=dict(value.get("result") or {}),
        extensions=dict(value.get("extensions") or {}),
    )
