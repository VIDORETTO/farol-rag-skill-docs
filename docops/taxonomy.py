"""Deterministic taxonomy proposals with explicit approval and CAS semantics."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from .ir import IRBlock, IRDocument
from .revisions import content_hash
from .storage import write_json_atomic


class TaxonomyError(ValueError):
    """A taxonomy candidate cannot be safely accepted."""

    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(message)


@dataclass(frozen=True)
class TaxonomyNode:
    node_id: str
    concept_id: str
    title: str
    slug: str
    owner: str
    parent_id: str | None = None
    aliases: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    coverage: list[str] = field(default_factory=list)
    cross_references: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "concept_id": self.concept_id,
            "title": self.title,
            "slug": self.slug,
            "owner": self.owner,
            "parent_id": self.parent_id,
            "aliases": list(self.aliases),
            "dependencies": list(self.dependencies),
            "coverage": list(self.coverage),
            "cross_references": list(self.cross_references),
        }


@dataclass(frozen=True)
class TaxonomyProposal:
    project_revision: str
    ir_revision: str
    goal: str
    nodes: list[TaxonomyNode]
    coverage: dict[str, Any]
    overlaps: list[dict[str, Any]]
    orphans: list[str]
    proposal_hash: str
    request_id: str | None = None
    requires_approval: bool = True
    status: str = "proposed"

    @property
    def metrics(self) -> dict[str, Any]:
        """Backward-compatible name for the coverage summary."""

        return self.coverage

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "kind": "taxonomy_proposal",
            "project_revision": self.project_revision,
            "ir_revision": self.ir_revision,
            "goal": self.goal,
            "nodes": [node.to_dict() for node in self.nodes],
            "coverage": self.coverage,
            "overlaps": self.overlaps,
            "orphans": self.orphans,
            "proposal_hash": self.proposal_hash,
            "request_id": self.request_id,
            "requires_approval": self.requires_approval,
            "status": self.status,
        }


@dataclass(frozen=True)
class TaxonomyRevision:
    revision_id: str
    project_revision: str
    ir_revision: str
    nodes: list[TaxonomyNode]
    coverage: dict[str, Any]
    overlaps: list[dict[str, Any]]
    orphans: list[str]
    approval: dict[str, Any]
    status: str = "active"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "kind": "taxonomy",
            "revision_id": self.revision_id,
            "project_revision": self.project_revision,
            "ir_revision": self.ir_revision,
            "nodes": [node.to_dict() for node in self.nodes],
            "coverage": self.coverage,
            "overlaps": self.overlaps,
            "orphans": self.orphans,
            "approval": self.approval,
            "status": self.status,
        }


class TaxonomyEngine:
    """Own the proposal/approval seam without choosing a model or provider."""

    def __init__(self) -> None:
        self.active_revision: str | None = None
        self._requests: dict[str, str] = {}
        self._proposals: dict[str, TaxonomyProposal] = {}
        self._revisions: dict[str, TaxonomyRevision] = {}

    def propose(
        self,
        blocks: Iterable[IRBlock | IRDocument | Mapping[str, Any]],
        *,
        goal: str,
        proposal: Mapping[str, Any] | None = None,
        project_revision: str = "project-revision-unknown",
        ir_revision: str = "ir-revision-unknown",
        request_id: str | None = None,
    ) -> TaxonomyProposal:
        known = _block_index(blocks)
        if not goal.strip():
            raise TaxonomyError("goal_required", "taxonomy goal is required")
        if request_id and request_id in self._requests:
            previous = self._proposals[self._requests[request_id]]
            candidate_payload = _proposal_input(proposal) if proposal is not None else None
            if candidate_payload is None or content_hash(candidate_payload) == previous.proposal_hash:
                return previous
            raise TaxonomyError("idempotency_conflict", "request_id was reused with a different taxonomy input")
        nodes = _nodes_from_input(proposal, known) if proposal is not None else _suggest_nodes(known)
        _validate_nodes(nodes, set(known))
        coverage = _coverage(nodes, set(known))
        overlaps = _overlaps(nodes)
        orphans = sorted(set(known) - set(coverage["covered_refs"]))
        payload = {
            "project_revision": project_revision,
            "ir_revision": ir_revision,
            "goal": goal,
            "nodes": [node.to_dict() for node in nodes],
            "coverage": coverage,
            "overlaps": overlaps,
            "orphans": orphans,
        }
        result = TaxonomyProposal(
            project_revision=project_revision,
            ir_revision=ir_revision,
            goal=goal,
            nodes=nodes,
            coverage=coverage,
            overlaps=overlaps,
            orphans=orphans,
            proposal_hash=content_hash(payload),
            request_id=request_id,
        )
        self._proposals[result.proposal_hash] = result
        if request_id:
            self._requests[request_id] = result.proposal_hash
        return result

    def approve(
        self,
        proposal: TaxonomyProposal,
        approval: Mapping[str, Any] | bool,
        *,
        expected_revision: str | None = None,
    ) -> TaxonomyRevision:
        if expected_revision != self.active_revision:
            raise TaxonomyError(
                "stale_revision",
                "taxonomy compare-and-swap revision does not match the active revision",
                details={"expected": expected_revision, "actual": self.active_revision},
            )
        approved = approval is True or (isinstance(approval, Mapping) and approval.get("approved") is True)
        if not approved:
            raise TaxonomyError("approval_required", "taxonomy activation requires explicit approval")
        approval_payload = dict(approval) if isinstance(approval, Mapping) else {"approved": True}
        revision_fingerprint = content_hash({"proposal": proposal.proposal_hash, "approval": approval_payload})
        revision_id = f"taxonomy-{revision_fingerprint[:24]}"
        existing = self._revisions.get(revision_id)
        if existing is not None:
            self.active_revision = existing.revision_id
            return existing
        revision = TaxonomyRevision(
            revision_id=revision_id,
            project_revision=proposal.project_revision,
            ir_revision=proposal.ir_revision,
            nodes=proposal.nodes,
            coverage=proposal.coverage,
            overlaps=proposal.overlaps,
            orphans=proposal.orphans,
            approval=approval_payload,
        )
        self._revisions[revision_id] = revision
        self.active_revision = revision_id
        return revision

    @staticmethod
    def diff(left: TaxonomyRevision | None, right: TaxonomyProposal | TaxonomyRevision) -> dict[str, Any]:
        left_nodes = {node.node_id: node.to_dict() for node in left.nodes} if left else {}
        right_nodes = {node.node_id: node.to_dict() for node in right.nodes}
        added = sorted(set(right_nodes) - set(left_nodes))
        removed = sorted(set(left_nodes) - set(right_nodes))
        changed = sorted(
            node_id for node_id in set(left_nodes) & set(right_nodes) if left_nodes[node_id] != right_nodes[node_id]
        )
        return {
            "added": added,
            "removed": removed,
            "changed": changed,
            "requires_candidate": bool(added or removed or changed),
        }


class TaxonomyStore:
    """Persist proposals/revisions as private JSON with atomic replacement."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def write(self, value: TaxonomyProposal | TaxonomyRevision) -> Path:
        payload = value.to_dict()
        identity = value.proposal_hash if isinstance(value, TaxonomyProposal) else value.revision_id
        destination = self.root / identity / f"{payload['kind']}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(destination, payload)
        return destination


def _block_index(values: Iterable[IRBlock | IRDocument | Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for value in values:
        if isinstance(value, IRDocument):
            for block in value.blocks:
                result[block.block_id] = block.to_dict()
        elif isinstance(value, IRBlock):
            result[value.block_id] = value.to_dict()
        elif isinstance(value, Mapping):
            if value.get("kind") == "ir_document":
                for block in value.get("blocks", []):
                    if isinstance(block, Mapping) and block.get("block_id"):
                        result[str(block["block_id"])] = dict(block)
            elif value.get("block_id"):
                result[str(value["block_id"])] = dict(value)
    return result


def _proposal_input(proposal: Mapping[str, Any] | None) -> dict[str, Any] | None:
    return {str(key): value for key, value in proposal.items()} if proposal is not None else None


def _nodes_from_input(proposal: Mapping[str, Any], known: Mapping[str, Mapping[str, Any]]) -> list[TaxonomyNode]:
    raw_nodes = proposal.get("nodes")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise TaxonomyError("nodes_required", "taxonomy proposal must contain non-empty nodes")
    nodes: list[TaxonomyNode] = []
    for index, raw in enumerate(raw_nodes):
        if not isinstance(raw, Mapping):
            raise TaxonomyError("node_invalid", f"taxonomy node {index} is not an object")
        title = str(raw.get("title") or raw.get("slug") or raw.get("concept_id") or "").strip()
        slug = _slug(str(raw.get("slug") or raw.get("node_id") or title))
        node_id = str(raw.get("node_id") or slug or f"topic-{index + 1}")
        concept_id = str(raw.get("concept_id") or node_id)
        owner = str(raw.get("owner") or concept_id)
        nodes.append(
            TaxonomyNode(
                node_id=node_id,
                concept_id=concept_id,
                title=title or node_id,
                slug=slug or node_id,
                owner=owner,
                parent_id=str(raw["parent_id"]) if raw.get("parent_id") else None,
                aliases=[str(item) for item in raw.get("aliases", []) if isinstance(item, str)],
                dependencies=[str(item) for item in raw.get("dependencies", []) if isinstance(item, str)],
                coverage=[str(item) for item in raw.get("coverage", []) if isinstance(item, str)],
                cross_references=[str(item) for item in raw.get("cross_references", []) if isinstance(item, str)],
            )
        )
    return nodes


def _suggest_nodes(known: Mapping[str, Mapping[str, Any]]) -> list[TaxonomyNode]:
    groups: dict[str, list[str]] = {}
    labels: dict[str, str] = {}
    for block_id, block in known.items():
        heading_path = block.get("heading_path") if isinstance(block.get("heading_path"), list) else []
        title = str(heading_path[0] if heading_path else block.get("text") or "General").strip()
        label = title.split(".", 1)[0].strip()[:80] or "General"
        slug = _slug(label)
        groups.setdefault(slug, []).append(block_id)
        labels.setdefault(slug, label)
    return [
        TaxonomyNode(node_id=slug, concept_id=slug, title=labels[slug], slug=slug, owner=slug, coverage=refs)
        for slug, refs in sorted(groups.items())
    ]


def _validate_nodes(nodes: list[TaxonomyNode], known: set[str]) -> None:
    ids = [node.node_id for node in nodes]
    concepts = [node.concept_id for node in nodes]
    owners = [node.owner for node in nodes]
    slugs = [node.slug for node in nodes]
    if len(ids) != len(set(ids)) or len(concepts) != len(set(concepts)) or len(owners) != len(set(owners)):
        raise TaxonomyError("duplicate_owner", "node_id, concept_id and owner must be unique")
    if len(slugs) != len(set(slugs)):
        raise TaxonomyError("duplicate_slug", "taxonomy skill slugs must be unique")
    node_ids = set(ids)
    for node in nodes:
        if not node.owner:
            raise TaxonomyError("owner_required", f"node {node.node_id} has no owner")
        if node.parent_id and node.parent_id not in node_ids:
            raise TaxonomyError("dangling_parent", f"node {node.node_id} has an unknown parent")
        if any(ref not in known for ref in node.coverage):
            raise TaxonomyError("dangling_evidence", f"node {node.node_id} covers an unknown IR block")
        if any(ref not in node_ids for ref in node.dependencies):
            raise TaxonomyError("dangling_dependency", f"node {node.node_id} has an unknown dependency")
    _assert_acyclic(nodes)


def _assert_acyclic(nodes: list[TaxonomyNode]) -> None:
    edges = {node.node_id: [item for item in (node.parent_id, *node.dependencies) if item] for node in nodes}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise TaxonomyError("cycle", "taxonomy graph must be acyclic")
        if node_id in visited:
            return
        visiting.add(node_id)
        for child in edges[node_id]:
            visit(child)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in edges:
        visit(node_id)


def _coverage(nodes: list[TaxonomyNode], known: set[str]) -> dict[str, Any]:
    covered = sorted({ref for node in nodes for ref in node.coverage})
    return {
        "total_blocks": len(known),
        "covered_blocks": len(covered),
        "covered_refs": covered,
        "coverage_ratio": round(len(covered) / len(known), 6) if known else 0.0,
    }


def _overlaps(nodes: list[TaxonomyNode]) -> list[dict[str, Any]]:
    refs: dict[str, list[str]] = {}
    for node in nodes:
        for ref in node.coverage:
            refs.setdefault(ref, []).append(node.node_id)
    return [{"block_id": ref, "nodes": owners} for ref, owners in sorted(refs.items()) if len(owners) > 1]


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "topic"
