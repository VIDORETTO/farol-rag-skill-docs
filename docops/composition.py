"""Atomic Farol 2.0 composition candidates, promotion and recovery."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .revisions import content_hash
from .storage import write_json_atomic


class CompositionError(RuntimeError):
    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(message)


@dataclass(frozen=True)
class CompositionCandidate:
    composition_id: str
    components: dict[str, Any]
    impact: str
    status: str = "preparing"
    evaluation: dict[str, Any] = field(default_factory=dict)
    previous_composition_id: str | None = None
    invalidates: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "kind": "composition",
            "composition_id": self.composition_id,
            "components": self.components,
            "impact": self.impact,
            "status": self.status,
            "evaluation": self.evaluation,
            "previous_composition_id": self.previous_composition_id,
            "invalidates": self.invalidates,
        }


@dataclass(frozen=True)
class CompositionReceipt:
    status: str
    operation: str
    composition_id: str | None = None
    previous_composition_id: str | None = None
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "kind": "composition_receipt",
            "status": self.status,
            "operation": self.operation,
            "composition_id": self.composition_id,
            "previous_composition_id": self.previous_composition_id,
            "message": self.message,
        }


class CompositionManager:
    REQUIRED_COMPONENTS = (
        "project_revision",
        "ir_revision",
        "taxonomy_revision",
        "skill_revisions",
        "router_revision",
        "index_revision",
    )

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root is not None else None
        self._candidates: dict[str, CompositionCandidate] = {}
        self._active: CompositionCandidate | None = None
        self._previous: CompositionCandidate | None = None

    @property
    def active_revision(self) -> str | None:
        return self._active.composition_id if self._active else None

    def prepare(
        self,
        components: Mapping[str, Any],
        *,
        impact: str = "factual",
        invalidates: list[str] | None = None,
    ) -> CompositionCandidate:
        missing = [key for key in self.REQUIRED_COMPONENTS if key not in components]
        if missing:
            raise CompositionError(
                "incomplete_component", "composition is missing required components", details={"missing": missing}
            )
        if impact not in {"factual", "conceptual", "rights", "conflict", "revocation"}:
            raise CompositionError("impact_invalid", "unsupported composition impact")
        normalized = {str(key): value for key, value in components.items()}
        if not normalized.get("skill_revisions") or not isinstance(normalized["skill_revisions"], list):
            raise CompositionError("incomplete_component", "skill_revisions must be a non-empty list")
        identity = content_hash({"components": normalized, "impact": impact, "invalidates": invalidates or []})
        composition_id = f"composition-{identity[:24]}"
        existing = self._candidates.get(composition_id)
        if existing is not None:
            return existing
        candidate = CompositionCandidate(
            composition_id=composition_id,
            components=normalized,
            impact=impact,
            previous_composition_id=self.active_revision,
            invalidates=list(invalidates or []),
        )
        self._candidates[composition_id] = candidate
        self._write(candidate, "candidate")
        return candidate

    def evaluate(self, candidate: CompositionCandidate, *, gates: Mapping[str, Any]) -> CompositionCandidate:
        owned = self._owned(candidate)
        if not gates or any(value is not True for value in gates.values()):
            updated = CompositionCandidate(**{**owned.__dict__, "status": "blocked", "evaluation": dict(gates)})
            self._candidates[owned.composition_id] = updated
            self._write(updated, "candidate")
            raise CompositionError("gate_failed", "composition gates did not pass", details=dict(gates))
        updated = CompositionCandidate(**{**owned.__dict__, "status": "evaluated", "evaluation": dict(gates)})
        self._candidates[owned.composition_id] = updated
        self._write(updated, "candidate")
        return updated

    def promote(
        self,
        candidate: CompositionCandidate,
        *,
        approval: Mapping[str, Any] | None = None,
        expected_active: str | None = None,
        fail_after_journal: bool = False,
    ) -> CompositionReceipt:
        owned = self._owned(candidate)
        if owned.status != "evaluated":
            raise CompositionError("candidate_not_evaluated", "composition must pass evaluation before promotion")
        if expected_active is not None and expected_active != self.active_revision:
            raise CompositionError(
                "stale_revision",
                "active composition changed",
                details={"expected": expected_active, "actual": self.active_revision},
            )
        if owned.impact != "factual" and not (approval and approval.get("approved") is True):
            raise CompositionError("approval_required", "non-factual composition changes require approval")
        journal = {
            "schema_version": 2,
            "kind": "composition_journal",
            "phase": "prepared",
            "candidate": owned.to_dict(),
            "previous": self._active.to_dict() if self._active else None,
        }
        self._write_payload("composition-journal.json", journal)
        if fail_after_journal:
            raise CompositionError("promotion_interrupted", "promotion interrupted after journal write")
        self._previous = self._active
        active = CompositionCandidate(**{**owned.__dict__, "status": "active"})
        self._active = active
        self._candidates[active.composition_id] = active
        self._write_payload("active-composition.json", active.to_dict())
        self._write_payload("composition-journal.json", {**journal, "phase": "committed"})
        return CompositionReceipt("active", "promote", active.composition_id, active.previous_composition_id)

    def rollback(self, target: CompositionCandidate | None = None) -> CompositionReceipt:
        previous = target or self._previous
        if previous is None:
            self._active = None
            self._write_payload(
                "active-composition.json", {"schema_version": 2, "kind": "composition_pointer", "composition_id": None}
            )
            return CompositionReceipt("rolled_back", "rollback")
        self._active = previous
        self._write_payload("active-composition.json", previous.to_dict())
        return CompositionReceipt("rolled_back", "rollback", previous.composition_id)

    def recover(self) -> CompositionReceipt:
        journal = self._read_payload("composition-journal.json")
        if not journal or journal.get("phase") == "committed":
            return CompositionReceipt("noop", "recover", self.active_revision, message="no interrupted promotion")
        previous = journal.get("previous")
        if isinstance(previous, Mapping):
            self._active = _candidate_from_dict(previous)
        else:
            self._active = None
        self._write_payload(
            "active-composition.json",
            self._active.to_dict()
            if self._active
            else {"schema_version": 2, "kind": "composition_pointer", "composition_id": None},
        )
        self._write_payload("composition-journal.json", {**journal, "phase": "recovered"})
        return CompositionReceipt("recovered", "recover", self.active_revision)

    def _owned(self, candidate: CompositionCandidate) -> CompositionCandidate:
        owned = self._candidates.get(candidate.composition_id)
        if owned is None:
            raise CompositionError("candidate_unknown", "composition candidate is not owned")
        return owned

    def _write(self, candidate: CompositionCandidate, name: str) -> None:
        self._write_payload(f"{name}-{candidate.composition_id}.json", candidate.to_dict())

    def _write_payload(self, name: str, payload: Mapping[str, Any]) -> None:
        if self.root is not None:
            write_json_atomic(self.root / ".docops" / name, dict(payload))

    def _read_payload(self, name: str) -> dict[str, Any]:
        if self.root is None:
            return {}
        path = self.root / ".docops" / name
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {}
        return dict(value) if isinstance(value, Mapping) else {}


def _candidate_from_dict(value: Mapping[str, Any]) -> CompositionCandidate:
    return CompositionCandidate(
        composition_id=str(value.get("composition_id") or ""),
        components=dict(value.get("components") or {}),
        impact=str(value.get("impact") or "factual"),
        status=str(value.get("status") or "active"),
        evaluation=dict(value.get("evaluation") or {}),
        previous_composition_id=value.get("previous_composition_id")
        if isinstance(value.get("previous_composition_id"), str)
        else None,
        invalidates=[str(item) for item in value.get("invalidates", []) if isinstance(item, str)],
    )
