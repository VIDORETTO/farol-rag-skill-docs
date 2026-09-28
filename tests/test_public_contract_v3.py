# seam-scope: implementation-infrastructure (Farol 3 public module seam: Farol 3 public surface: CLI, MCP tools, package layout, upgrades)
from __future__ import annotations

import json
from pathlib import Path

import docops
from docops.contract_surface import current_surface

ROOT = Path(__file__).resolve().parents[1]
BASELINE = json.loads((ROOT / "docs" / "PUBLIC-SURFACE-3.json").read_text(encoding="utf-8"))


def test_nothing_public_disappears_without_a_deprecation_entry() -> None:
    surface = current_surface()
    deprecated = {(item["kind"], item["name"]) for item in BASELINE.get("deprecations", [])}

    missing = [
        (kind, name)
        for kind, names in BASELINE["surface"].items()
        for name in names
        if name not in surface.get(kind, []) and (kind, name) not in deprecated
    ]

    assert missing == []


def test_new_public_items_must_be_recorded_in_the_baseline() -> None:
    surface = current_surface()

    unrecorded = [
        (kind, name)
        for kind, names in surface.items()
        for name in names
        if name not in BASELINE["surface"].get(kind, [])
    ]

    assert unrecorded == []


def test_a_package_generated_by_the_2_0_pipeline_upgrades_in_place(tmp_path: Path) -> None:
    from docops.agent_tasks import next_task, plan_synthesis
    from docops.backends import QueryRequest
    from docops.mcp_server import KnowledgeServer
    from docops.package_index import build_package_index

    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\n\n## Retries\n\nThe client retries 5 times.\n", encoding="utf-8")
    package = tmp_path / "package"
    result = docops.apply(
        docops.plan(
            docops.OperationRequest(
                source,
                docops.OperationOptions(output_dir=package, source_root=source.parent, slug="guide", license="MIT"),
            )
        )
    )
    assert result.ok
    assert not (package / "rag" / "local-index").exists()  # what a 2.0 package looks like

    build_package_index(package, embedder=None)
    hits = KnowledgeServer(package).search_knowledge("retries")["hits"]
    plan_synthesis(package, language="en")

    from docops.contract_surface import SEARCH_HIT_FIELDS

    assert "5 times" in hits[0]["text"]
    assert set(hits[0]) == set(SEARCH_HIT_FIELDS)
    assert next_task(package)["kind"] == "chapter"
    del QueryRequest


def test_a_project_file_from_a_newer_farol_is_rejected_clearly(tmp_path: Path) -> None:
    import pytest

    from docops.journey import JourneyError, status

    (tmp_path / "farol.json").write_text('{"schema_version": 99, "name": "x", "sources": []}', encoding="utf-8")

    with pytest.raises(JourneyError) as error:
        status(tmp_path)

    assert error.value.code == "project_version_unsupported"
