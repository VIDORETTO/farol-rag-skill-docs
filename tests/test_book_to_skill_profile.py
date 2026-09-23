from __future__ import annotations

from pathlib import Path

from scripts.run_book_to_skill_profile import (
    _external_skill_output,
    _extract_ir,
    run_profile,
)


def test_book_to_skill_profile_fails_closed_when_harness_is_missing(tmp_path: Path) -> None:
    report = run_profile(
        source_dir=Path("documents/fixtures/acme-docs"),
        harness_root=tmp_path / "missing-harness",
        output_root=None,
    )

    assert report["status"] == "blocked"
    assert report["reason"] == "harness_unavailable"


def test_external_book_to_skill_projection_has_two_owned_skills_and_lineage() -> None:
    _, blocks = _extract_ir(Path("documents/fixtures/acme-docs"))
    output = _external_skill_output(blocks, "pt-BR")

    assert [skill["slug"] for skill in output["skills"]] == [
        "acme-api-reliability",
        "acme-api-release",
    ]
    assert all(skill["claims"] for skill in output["skills"])
    assert all(claim["lineage"] for skill in output["skills"] for claim in skill["claims"])
    assert all(skill["markdown"].startswith("---\n") for skill in output["skills"])
