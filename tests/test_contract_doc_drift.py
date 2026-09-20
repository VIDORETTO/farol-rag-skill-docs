# seam-scope: implementation-infrastructure (contract/documentation gates)
from __future__ import annotations

import json
from pathlib import Path

from scripts.check_documentation import check_documentation
from scripts.sync_schemas import check_schema_distribution


def test_schema_distribution_detects_bundled_content_drift(tmp_path: Path) -> None:
    canonical = tmp_path / "schemas"
    bundled = tmp_path / "docops" / "schemas"
    canonical.mkdir(parents=True)
    bundled.mkdir(parents=True)
    schema = {"$schema": "fixture", "required": ["schema_version"], "properties": {"schema_version": {"const": 1}}}
    (canonical / "fixture.schema.json").write_text(json.dumps(schema), encoding="utf-8")
    (bundled / "fixture.schema.json").write_text(json.dumps({**schema, "title": "drift"}), encoding="utf-8")

    result = check_schema_distribution(canonical, bundled)

    assert result["ok"] is False
    assert any(finding["code"] == "schema_content_drift" for finding in result["findings"])


def test_documentation_checker_rejects_unknown_docops_command(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("`python -m docops definitely-not-a-command --json`\n", encoding="utf-8")

    result = check_documentation(tmp_path)

    assert result["ok"] is False
    assert any(finding["code"] == "documented_command_unknown" for finding in result["findings"])


def test_documentation_checker_accepts_farol_launcher(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("```text\nfarol doctor --json\n```\n", encoding="utf-8")

    result = check_documentation(tmp_path)

    assert result["ok"] is True, result["findings"]


def test_documentation_checker_reads_tilde_fenced_commands(tmp_path: Path) -> None:
    # The repository README fences command blocks with tildes; a backtick-only
    # scanner silently skips them and lets real CLI drift through.
    (tmp_path / "README.md").write_text("~~~text\ndocops definitely-not-a-command --json\n~~~\n", encoding="utf-8")

    result = check_documentation(tmp_path)

    assert result["ok"] is False
    assert any(finding["code"] == "documented_command_unknown" for finding in result["findings"])


def test_documentation_checker_expands_documented_command_groups(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "~~~text\ndocops v2 {inspect,apply}\ndocops v2 {not-a-verb}\n~~~\n",
        encoding="utf-8",
    )

    result = check_documentation(tmp_path)

    findings = [finding for finding in result["findings"] if finding["code"] == "documented_command_unknown"]
    assert any("not-a-verb" in finding["message"] for finding in findings)
    assert not any("inspect" in finding["message"] or "apply" in finding["message"] for finding in findings)


def test_documentation_checker_covers_the_normative_specs_tree(tmp_path: Path) -> None:
    # The Farol 2.0 spec/tickets/evidence live under specs/; a broken citation
    # link there must fail the gate just like one under docs/.
    spec = tmp_path / "specs" / "farol-2"
    spec.mkdir(parents=True)
    (spec / "spec.md").write_text("See [ticket](tickets/TK-999.md).\n", encoding="utf-8")

    result = check_documentation(tmp_path)

    assert result["ok"] is False
    assert any(
        finding["code"] == "broken_local_link" and "specs/farol-2/spec.md" in finding["path"]
        for finding in result["findings"]
    )


def test_documentation_checker_requires_evidence_for_done_tickets(tmp_path: Path) -> None:
    ticket_root = tmp_path / "docs" / "main-consolidation" / "tickets"
    ticket_root.mkdir(parents=True)
    (ticket_root / "01-fixture.md").write_text(
        "---\nstatus: done\n---\n# T01\n\n## Acceptance criteria\n\n- [x] complete\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "main-consolidation" / "IMPLEMENTATION-STATUS.md").write_text(
        "| T01 | concluído | — | evidence |\n",
        encoding="utf-8",
    )

    result = check_documentation(tmp_path)

    assert result["ok"] is False
    assert any(finding["code"] == "implemented_claim_without_evidence" for finding in result["findings"])


def test_repository_documentation_passes_its_quality_gate() -> None:
    result = check_documentation(Path(__file__).parents[1])

    assert result["ok"] is True, result["findings"]
