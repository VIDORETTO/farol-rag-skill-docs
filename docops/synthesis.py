"""Provider-neutral conceptual synthesis and verifiable skill lineage."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol

from .ir import IRBlock
from .revisions import content_hash
from .taxonomy import TaxonomyRevision


class SynthesisError(ValueError):
    """A synthesis request or result cannot be accepted as a candidate."""

    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(message)


@dataclass(frozen=True)
class SynthesisRequest:
    request_id: str
    project_revision: str
    ir_revision: str
    taxonomy_revision: str
    adapter: str
    language: str
    budget: dict[str, Any]
    topics: list[dict[str, Any]]
    request_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "kind": "synthesis_request",
            "request_id": self.request_id,
            "project_revision": self.project_revision,
            "ir_revision": self.ir_revision,
            "taxonomy_revision": self.taxonomy_revision,
            "adapter": self.adapter,
            "language": self.language,
            "budget": self.budget,
            "topics": self.topics,
            "request_hash": self.request_hash,
        }


@dataclass(frozen=True)
class ClaimLineage:
    claim_id: str
    text: str
    topic_id: str
    block_refs: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "topic_id": self.topic_id,
            "block_refs": self.block_refs,
        }


@dataclass(frozen=True)
class SkillArtifact:
    topic_id: str
    slug: str
    language: str
    markdown: str
    chapters: dict[str, str]
    lineage: list[ClaimLineage]
    token_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic_id": self.topic_id,
            "slug": self.slug,
            "language": self.language,
            "markdown": self.markdown,
            "chapters": self.chapters,
            "lineage": [item.to_dict() for item in self.lineage],
            "token_count": self.token_count,
        }


@dataclass(frozen=True)
class SynthesisReceipt:
    request_id: str
    request_hash: str
    adapter: dict[str, Any]
    status: str
    input_hash: str
    output_hash: str | None
    skills: list[str]
    rejected_claims: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "kind": "synthesis_receipt",
            "request_id": self.request_id,
            "request_hash": self.request_hash,
            "adapter": self.adapter,
            "status": self.status,
            "input_hash": self.input_hash,
            "output_hash": self.output_hash,
            "skills": self.skills,
            "rejected_claims": self.rejected_claims,
            "warnings": self.warnings,
        }


@dataclass(frozen=True)
class SynthesisCandidate:
    request: SynthesisRequest
    skills: list[SkillArtifact]
    receipt: SynthesisReceipt
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.request.to_dict(),
            "skills": [skill.to_dict() for skill in self.skills],
            "receipt": self.receipt.to_dict(),
            "status": self.status,
        }


class SynthesisAdapter(Protocol):
    name: str
    version: str
    execution: str

    def synthesize(self, request: SynthesisRequest, projections: Mapping[str, list[IRBlock]]) -> Mapping[str, Any]: ...


class BookToSkillAdapter:
    """Contract adapter used by fixtures; a harness may replace its renderer."""

    name = "book-to-skill"
    version = "contract-2.0"
    execution = "contract-fixture"

    def synthesize(self, request: SynthesisRequest, projections: Mapping[str, list[IRBlock]]) -> Mapping[str, Any]:
        skills: list[dict[str, Any]] = []
        for topic in request.topics:
            topic_id = str(topic["topic_id"])
            title = str(topic["title"])
            blocks = projections.get(topic_id, [])
            lines = [f"# {title}", "", f"Use this skill in {request.language} for conceptual guidance.", ""]
            claims: list[dict[str, Any]] = []
            for block in blocks:
                if not block.text:
                    continue
                claim_id = f"claim-{hashlib.sha256(f'{topic_id}:{block.block_id}'.encode()).hexdigest()[:16]}"
                lines.extend([f"## {block.text[:80]}", "", f"- {block.text}", ""])
                claims.append(
                    {
                        "claim_id": claim_id,
                        "text": block.text,
                        "lineage": [{"block_id": block.block_id}],
                    }
                )
            skills.append(
                {
                    "topic_id": topic_id,
                    "slug": str(topic["slug"]),
                    "markdown": "\n".join(lines),
                    "claims": claims,
                }
            )
        return {"skills": skills}


class SynthesisEngine:
    def __init__(self, adapter: SynthesisAdapter | None = None) -> None:
        self.adapter = adapter or BookToSkillAdapter()
        self._requests: dict[str, SynthesisCandidate] = {}
        self._prepared_blocks: dict[str, dict[str, IRBlock]] = {}

    def prepare(
        self,
        taxonomy: TaxonomyRevision,
        blocks: Iterable[IRBlock],
        *,
        language: str = "en",
        budget: Mapping[str, Any] | None = None,
        request_id: str | None = None,
    ) -> SynthesisRequest:
        block_map = {block.block_id: block for block in blocks}
        topics = []
        for node in taxonomy.nodes:
            refs = [ref for ref in node.coverage if ref in block_map]
            topics.append({"topic_id": node.node_id, "slug": node.slug, "title": node.title, "block_ids": refs})
        normalized_budget = {"max_tokens": int((budget or {}).get("max_tokens", 4000)), **dict(budget or {})}
        if normalized_budget["max_tokens"] < 1:
            raise SynthesisError("budget_invalid", "max_tokens must be positive")
        identity_payload = {"taxonomy": taxonomy.revision_id, "language": language, "topics": topics}
        identity = request_id or f"synthesis-{content_hash(identity_payload)[:16]}"
        payload = {
            "request_id": identity,
            "project_revision": taxonomy.project_revision,
            "ir_revision": taxonomy.ir_revision,
            "taxonomy_revision": taxonomy.revision_id,
            "adapter": f"{self.adapter.name}@{self.adapter.version}",
            "language": language,
            "budget": normalized_budget,
            "topics": topics,
        }
        request = SynthesisRequest(**payload, request_hash=content_hash(payload))
        self._prepared_blocks[request.request_hash] = block_map
        return request

    def submit(
        self,
        request: SynthesisRequest,
        *,
        output: Mapping[str, Any] | None = None,
        blocks: Iterable[IRBlock] | None = None,
    ) -> SynthesisCandidate:
        previous = self._requests.get(request.request_id)
        if previous is not None:
            if previous.request.request_hash != request.request_hash:
                raise SynthesisError("idempotency_conflict", "synthesis request was reused with different inputs")
            return previous
        block_map = (
            {block.block_id: block for block in blocks}
            if blocks is not None
            else self._prepared_blocks.get(request.request_hash, {})
        )
        if output is None:
            projections = {
                str(topic["topic_id"]): [block_map[ref] for ref in topic.get("block_ids", []) if ref in block_map]
                for topic in request.topics
            }
            if not block_map:
                raise SynthesisError("projection_required", "blocks are required when the adapter is invoked")
            output = self.adapter.synthesize(request, projections)
        skills = _validate_output(request, output, block_map)
        output_hash = content_hash({"skills": [skill.to_dict() for skill in skills]})
        receipt = SynthesisReceipt(
            request_id=request.request_id,
            request_hash=request.request_hash,
            adapter={
                "name": self.adapter.name,
                "version": self.adapter.version,
                "execution": getattr(self.adapter, "execution", "external"),
            },
            status="ready",
            input_hash=content_hash(request.to_dict()),
            output_hash=output_hash,
            skills=[skill.slug for skill in skills],
        )
        candidate = SynthesisCandidate(request, skills, receipt, "ready")
        self._requests[request.request_id] = candidate
        return candidate

    def generate(
        self,
        taxonomy: TaxonomyRevision,
        blocks: Iterable[IRBlock],
        *,
        language: str = "en",
        budget: Mapping[str, Any] | None = None,
        request_id: str | None = None,
    ) -> SynthesisCandidate:
        block_list = list(blocks)
        request = self.prepare(taxonomy, block_list, language=language, budget=budget, request_id=request_id)
        return self.submit(request, blocks=block_list)

    @staticmethod
    def write(candidate: SynthesisCandidate, root: Path | str) -> list[Path]:
        destination = Path(root)
        written: list[Path] = []
        for skill in candidate.skills:
            skill_dir = destination / "skills" / skill.slug
            chapters = skill_dir / "chapters"
            chapters.mkdir(parents=True, exist_ok=True)
            main = skill_dir / "SKILL.md"
            main.write_text(skill.markdown, encoding="utf-8")
            written.append(main)
            for name, content in skill.chapters.items():
                path = chapters / name
                path.write_text(content, encoding="utf-8")
                written.append(path)
            lineage = skill_dir / "lineage.json"
            lineage.write_text(
                json.dumps([item.to_dict() for item in skill.lineage], ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            written.append(lineage)
        return written


def _validate_output(
    request: SynthesisRequest, output: Mapping[str, Any], blocks: Mapping[str, IRBlock]
) -> list[SkillArtifact]:
    raw_skills = output.get("skills") if isinstance(output, Mapping) else None
    if not isinstance(raw_skills, list):
        raise SynthesisError("output_invalid", "synthesizer output must contain skills")
    expected = {str(topic["topic_id"]): topic for topic in request.topics}
    seen: set[str] = set()
    result: list[SkillArtifact] = []
    for raw in raw_skills:
        if not isinstance(raw, Mapping):
            raise SynthesisError("output_invalid", "skill output must be an object")
        topic_id = str(raw.get("topic_id") or "")
        if topic_id not in expected or topic_id in seen:
            raise SynthesisError("owner_conflict", "each taxonomy concept must have one skill owner")
        seen.add(topic_id)
        allowed_block_ids = {str(block_id) for block_id in expected[topic_id].get("block_ids", [])}
        expected_slug = str(expected[topic_id]["slug"])
        slug = str(raw.get("slug") or expected_slug)
        if slug != expected_slug or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) is None:
            raise SynthesisError("output_invalid", f"skill {topic_id} must preserve its approved taxonomy slug")
        markdown = str(raw.get("markdown") or "")
        if not markdown.strip():
            raise SynthesisError("output_invalid", f"skill {topic_id} is empty")
        token_count = _tokens(markdown)
        if token_count > int(request.budget.get("max_tokens", 4000)):
            raise SynthesisError("budget_exceeded", f"skill {topic_id} exceeds the configured token budget")
        raw_chapters = raw.get("chapters") or {}
        if not isinstance(raw_chapters, Mapping):
            raise SynthesisError("output_invalid", f"skill {topic_id} chapters must be an object")
        chapters: dict[str, str] = {}
        for raw_name, raw_content in raw_chapters.items():
            name = str(raw_name)
            if re.fullmatch(r"[a-z0-9][a-z0-9._-]*\.md", name) is None:
                raise SynthesisError("output_invalid", f"skill {topic_id} contains an unsafe chapter path")
            chapters[name] = str(raw_content)
        lineages: list[ClaimLineage] = []
        claims = raw.get("claims", [])
        if not isinstance(claims, list):
            raise SynthesisError("output_invalid", "claims must be a list")
        for claim in claims:
            if not isinstance(claim, Mapping):
                raise SynthesisError("output_invalid", "claim must be an object")
            refs = claim.get("lineage")
            if not isinstance(refs, list) or not refs:
                raise SynthesisError("lineage_required", f"claim {claim.get('claim_id')} has no lineage")
            canonical_refs: list[dict[str, Any]] = []
            for ref in refs:
                if isinstance(ref, str):
                    ref = {"block_id": ref}
                if not isinstance(ref, Mapping) or str(ref.get("block_id") or "") not in blocks:
                    raise SynthesisError(
                        "lineage_invalid", f"claim {claim.get('claim_id')} references an unknown block"
                    )
                block_id = str(ref["block_id"])
                if block_id not in allowed_block_ids:
                    raise SynthesisError(
                        "lineage_invalid",
                        f"claim {claim.get('claim_id')} references a block outside the topic projection",
                    )
                block = blocks[block_id]
                canonical_refs.append(
                    {
                        "block_id": block.block_id,
                        "source_fragment_hash": block.source_fragment_hash,
                        "locators": [dict(locator) for locator in block.locators],
                    }
                )
            lineages.append(
                ClaimLineage(
                    claim_id=str(claim.get("claim_id") or content_hash(dict(claim))[:16]),
                    text=str(claim.get("text") or ""),
                    topic_id=topic_id,
                    block_refs=canonical_refs,
                )
            )
        result.append(
            SkillArtifact(
                topic_id=topic_id,
                slug=slug,
                language=request.language,
                markdown=markdown,
                chapters=chapters,
                lineage=lineages,
                token_count=token_count,
            )
        )
    missing = sorted(set(expected) - seen)
    if missing:
        raise SynthesisError("owner_missing", "taxonomy concepts are missing skills", details={"topics": missing})
    return result


def _tokens(value: str) -> int:
    return len(re.findall(r"\S+", value))
