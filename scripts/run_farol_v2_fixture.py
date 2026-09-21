"""Run the licensed/provider-free Farol 2.0 journey fixture."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from docops.composition import CompositionManager  # noqa: E402
from docops.extractors.base import ExtractorPolicy  # noqa: E402
from docops.extractors.text_web import TextWebExtractor  # noqa: E402
from docops.project import ProjectService  # noqa: E402
from docops.router import GlobalRouter  # noqa: E402
from docops.synthesis import SynthesisEngine  # noqa: E402
from docops.taxonomy import TaxonomyEngine  # noqa: E402


def run_fixture(root: Path | str) -> dict[str, Any]:
    workspace = Path(root).expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    source = workspace / "guide.md"
    source.write_text(
        "# Authentication\n\nUse a token for requests.\n\n# Deployment\n\nDeploy after validation.\n",
        encoding="utf-8",
    )
    project = ProjectService(workspace).start(
        "Fixture knowledge",
        "Operate the service safely",
        [
            {
                "source_id": "source-fixture",
                "canonical": source.resolve().as_uri(),
                "source_revision": "source-rev-1",
                "rights": "MIT",
                "privacy": "private",
                "language": "en",
                "purpose": "knowledge",
            }
        ],
        idempotency_key="fixture-start",
    )
    extraction = TextWebExtractor().extract(
        source,
        ExtractorPolicy(
            rights_ref="rights-fixture",
            source_id="source-fixture",
            source_revision_id="source-rev-1",
            required_fidelity="structured-native",
        ),
        {},
    )
    if extraction.document is None:
        return {"status": "failed", "error": "fixture extraction failed"}
    blocks = extraction.document.blocks
    taxonomy_engine = TaxonomyEngine()
    proposal = taxonomy_engine.propose(
        blocks,
        goal="Operate the service safely",
        project_revision=project.project_id,
        ir_revision=extraction.document.revision_hash(),
    )
    taxonomy = taxonomy_engine.approve(proposal, {"approved": True, "actor": "fixture-reviewer"})
    skills = SynthesisEngine().generate(taxonomy, blocks, language="en", budget={"max_tokens": 4000})
    router = GlobalRouter(taxonomy)
    route = router.route("What is the exact token behavior?", project_revision=project.project_id)
    evidence = router.filter_evidence(
        route.query_request,
        [
            {
                "block_id": block.block_id,
                "score": float(len(block.text or "")),
                "source_id": extraction.document.source_id,
                "source_revision_id": extraction.document.source_revision_id,
            }
            for block in blocks
        ],
        blocks,
    )
    composition = CompositionManager(workspace)
    candidate = composition.prepare(
        {
            "project_revision": project.project_id,
            "ir_revision": extraction.document.revision_hash(),
            "taxonomy_revision": taxonomy.revision_id,
            "skill_revisions": [skills.receipt.output_hash or "skill-fixture"],
            "router_revision": "router-fixture-1",
            "index_revision": "index-fixture-1",
        },
        impact="factual",
    )
    composition.evaluate(candidate, gates={"lineage": True, "citations": evidence.outcome == "ok"})
    promoted = composition.promote(candidate)
    rolled_back = composition.rollback()
    return {
        "schema_version": 2,
        "status": "passed" if promoted.status == "active" and rolled_back.status == "rolled_back" else "failed",
        "project": {"project_id": project.project_id, "revision": project.revision},
        "journey": {
            "extraction": extraction.receipt.fidelity,
            "taxonomy": taxonomy.revision_id,
            "skills": [skill.slug for skill in skills.skills],
            "route": route.route,
            "evidence": evidence.outcome,
            "composition_rollback": rolled_back.status == "rolled_back" and composition.active_revision is None,
        },
        "external": {
            "ragflow": {
                "status": "not_run",
                "reason": "operator-provisioned endpoint, token, SDK and image digest are absent",
            },
            "book_to_skill": {"status": "contract_fixture", "adapter": skills.receipt.adapter},
        },
        "security": {"raw_content_emitted": False, "secrets_emitted": False},
        "legacy_adapter": {"status": "not_selected", "reason": "provider-free v2 fixture"},
        "evidence": {"project_start": project.status, "receipt_hash": skills.receipt.output_hash},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    temporary: tempfile.TemporaryDirectory[str] | None = None
    if args.output is None:
        temporary = tempfile.TemporaryDirectory(prefix="farol-v2-fixture-")
        root = Path(temporary.name)
    else:
        root = args.output
    try:
        print(json.dumps(run_fixture(root), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    finally:
        if temporary is not None:
            temporary.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
