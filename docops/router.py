"""Global conceptual/factual/hybrid routing and canonical evidence filtering."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping
from urllib.parse import quote

from .backends import EvidenceResult, QueryRequest
from .ir import IRBlock


class RouterError(ValueError):
    """A query cannot be routed under the pinned reader contract."""


@dataclass(frozen=True)
class RoutePlan:
    route: str
    query_request: QueryRequest
    skill_ids: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    outcome: str = "ready"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "kind": "route_plan",
            "route": self.route,
            "query_request": self.query_request.to_dict(),
            "skill_ids": self.skill_ids,
            "reasons": self.reasons,
            "outcome": self.outcome,
        }


def route_query_v2(query: str, *, high_risk: bool = False, current: bool = False) -> str:
    value = query.strip()
    if not value:
        raise RouterError("query_required")
    if re.search(r"\b(safe|security|risk|production|deploy now|agora)\b", value, re.I):
        high_risk = True
    literal = re.compile(
        r"\b(default|defaults|signature|endpoint|version|changelog|exact|literal|parameter|config|configuration|valor|padrão|assinatura|endpoint|versão|exato)\b",
        re.I,
    )
    conceptual = re.compile(
        r"\b(how|why|pattern|concept|conceptual|guide|best practice|trade-?off|design|como|por que|padrão|melhor prática|projeto|desenhar)\b",
        re.I,
    )
    if high_risk or current:
        return "hybrid"
    has_literal = bool(literal.search(value))
    has_conceptual = bool(conceptual.search(value))
    if has_literal and has_conceptual:
        return "hybrid"
    if has_literal:
        return "factual"
    return "conceptual"


class GlobalRouter:
    def __init__(self, taxonomy_nodes: Iterable[Mapping[str, Any]] | Any) -> None:
        raw = taxonomy_nodes.nodes if hasattr(taxonomy_nodes, "nodes") else taxonomy_nodes
        self.nodes = [dict(node.to_dict() if hasattr(node, "to_dict") else node) for node in raw]

    def route(
        self,
        query: str,
        *,
        project_revision: str,
        top_k: int = 5,
        filters: Mapping[str, Any] | None = None,
        as_of: str | None = None,
        region: str | None = None,
        high_risk: bool = False,
        current: bool = False,
    ) -> RoutePlan:
        route = route_query_v2(query, high_risk=high_risk, current=current)
        skill_ids = self._select_skills(query) if route in {"conceptual", "hybrid"} else []
        query_filters = dict(filters or {})
        if skill_ids:
            query_filters["skill_ids"] = skill_ids
        reasons = [route]
        if high_risk:
            reasons.append("high_risk")
        if current:
            reasons.append("current")
        return RoutePlan(
            route=route,
            skill_ids=skill_ids,
            reasons=reasons,
            query_request=QueryRequest(
                query=query,
                top_k=top_k,
                project_revision=project_revision,
                filters=query_filters,
                as_of=as_of,
                region=region,
            ),
        )

    def _select_skills(self, query: str) -> list[str]:
        tokens = set(re.findall(r"[\w-]+", query.casefold()))
        scored: list[tuple[int, str]] = []
        for node in self.nodes:
            labels = [str(node.get("node_id") or ""), str(node.get("slug") or ""), str(node.get("title") or "")]
            labels.extend(str(item) for item in node.get("aliases", []) if isinstance(item, str))
            label_tokens = set(re.findall(r"[\w-]+", " ".join(labels).casefold()))
            score = len(tokens & label_tokens)
            if score:
                scored.append((score, str(node.get("node_id") or node.get("slug"))))
        scored.sort(key=lambda value: (-value[0], value[1]))
        return [node_id for _score, node_id in scored]

    @staticmethod
    def filter_evidence(
        query: QueryRequest,
        hits: Iterable[Mapping[str, Any]],
        blocks: Iterable[IRBlock | Mapping[str, Any]],
    ) -> EvidenceResult:
        raw_hits = [dict(hit) for hit in hits]
        block_map: dict[str, dict[str, Any]] = {}
        for block in blocks:
            payload = block.to_dict() if isinstance(block, IRBlock) else dict(block)
            if payload.get("block_id"):
                block_map[str(payload["block_id"])] = payload
        eligible: list[dict[str, Any]] = []
        for raw in raw_hits:
            hit = dict(raw)
            block_id = str(hit.get("block_id") or "")
            block = block_map.get(block_id)
            if block is None or hit.get("revoked") is True:
                continue
            locators = hit.get("locators") if isinstance(hit.get("locators"), list) else block.get("locators")
            if not isinstance(locators, list) or not locators:
                continue
            if hit.get("eligible") is False:
                continue
            canonical = dict(hit)
            canonical["locators"] = [dict(locator) for locator in locators if isinstance(locator, Mapping)]
            if not canonical["locators"]:
                continue
            canonical.setdefault("text", block.get("text"))
            canonical.setdefault("source_id", hit.get("source_id") or block.get("source_id") or "unknown")
            canonical.setdefault(
                "source_revision_id", hit.get("source_revision_id") or block.get("source_revision_id") or "unknown"
            )
            canonical["citations"] = _citations(canonical)
            eligible.append(canonical)
        eligible.sort(key=lambda item: (-float(item.get("score", 0.0)), str(item.get("block_id"))))
        selected = eligible[: query.top_k]
        outcome = "ok" if selected else "insufficient_evidence"
        if _has_conflict(selected):
            outcome = "conflict"
        return EvidenceResult(
            index_revision=str(query.filters.get("index_revision") or "unbound"),
            query=query,
            hits=selected,
            outcome=outcome,
            metadata={"eligible_before_top_k": len(eligible), "filtered": len(raw_hits) - len(eligible)},
        )


def _citations(hit: Mapping[str, Any]) -> list[str]:
    source = str(hit.get("source_id") or "unknown")
    revision = str(hit.get("source_revision_id") or "unknown")
    result: list[str] = []
    for locator in hit.get("locators", []):
        if not isinstance(locator, Mapping):
            continue
        kind = str(locator.get("kind") or "")
        label = str(locator.get("label") or "")
        if kind and label:
            result.append(f"source/{source}@{revision}#{kind}={quote(label, safe='._~-')}")
    return list(dict.fromkeys(result))


def _has_conflict(hits: list[Mapping[str, Any]]) -> bool:
    groups: dict[str, set[str]] = {}
    for hit in hits:
        group = hit.get("conflict_group")
        text = hit.get("text")
        if group and text:
            groups.setdefault(str(group), set()).add(str(text))
    return any(len(values) > 1 for values in groups.values())
