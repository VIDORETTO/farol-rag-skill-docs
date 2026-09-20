# seam-scope: implementation-infrastructure (release contraction boundary fixtures)
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from docops.release_v2 import audit_release_surface, require_cutover_approved


def test_surface_auditor_reports_forbidden_terms_without_content_leak(tmp_path) -> None:
    source = tmp_path / "docops" / "example.py"
    source.parent.mkdir()
    source.write_text("course page knowledge-rag\n", encoding="utf-8")

    report = audit_release_surface(tmp_path, surface="all")

    assert report.ok is False
    assert report.findings[0]["path"] == "docops/example.py"
    assert "course page knowledge-rag" not in str(report.to_dict())


def test_surface_auditor_allows_explicit_migration_surface(tmp_path) -> None:
    source = tmp_path / "docops" / "migration.py"
    source.parent.mkdir()
    source.write_text("course is excluded\n", encoding="utf-8")

    assert audit_release_surface(tmp_path, surface="editorial").ok


def test_legacy_contraction_requires_an_approved_decision() -> None:
    with pytest.raises(RuntimeError):
        require_cutover_approved({"status": "not_run", "ok": False})

    with pytest.raises(RuntimeError):
        require_cutover_approved({"status": "cutover_approved", "ok": True})


def test_repository_checkout_has_no_editorial_surface_residual() -> None:
    # AC-028's oracle must run against the real checkout, not only a tmp fixture:
    # the gate must fail if Mercado Livre / course / page / offer resurfaces in a
    # tracked normative file.
    root = Path(__file__).resolve().parents[1]

    report = audit_release_surface(root, surface="editorial")

    assert report.ok is True, report.findings[:10]


def _wheel(path: Path, members: dict[str, str]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, text in members.items():
            archive.writestr(name, text)
    return path


def test_wheel_audit_flags_a_removed_editorial_contract(tmp_path: Path) -> None:
    # AC-028 names the wheel auditor; the distribution must not carry the removed
    # editorial surface even though the checkout is clean.
    wheel = _wheel(
        tmp_path / "dist.whl",
        {
            "docops/__init__.py": "VERSION = '1.0'\n",
            "docops/presets/course.json": '{"kind": "course_id"}',
        },
    )

    report = audit_release_surface(tmp_path, surface="editorial", wheel=wheel)

    assert report.ok is False
    assert {finding["path"] for finding in report.findings} == {"docops/presets/course.json"}
    # The auditor reports the matched term, never the surrounding source line.
    assert '{"kind": "course_id"}' not in str(report.to_dict())


def test_wheel_audit_accepts_a_clean_distribution(tmp_path: Path) -> None:
    wheel = _wheel(
        tmp_path / "dist.whl",
        {"docops/__init__.py": "VERSION = '1.0'\n", "docops/assets/readme.txt": "clean\n"},
    )

    report = audit_release_surface(tmp_path, surface="editorial", wheel=wheel)

    assert report.ok is True, report.findings
