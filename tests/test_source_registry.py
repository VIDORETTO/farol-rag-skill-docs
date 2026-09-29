from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import docops

ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "docops", *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
    )


def _registry(package: Path) -> dict[str, object]:
    return json.loads((package / ".docops" / "source-registry.json").read_text(encoding="utf-8"))


def _register(package: Path, source_id: str, canonical: str, *, version_policy: str = "latest") -> None:
    completed = _run_cli(
        "source-register",
        "--package",
        str(package),
        "--source-id",
        source_id,
        "--canonical",
        canonical,
        "--kind",
        "web",
        "--scope",
        "docs/**",
        "--version-policy",
        version_policy,
        *(() if version_policy == "latest" else ("--version", "1.0")),
        "--rights",
        "MIT",
        "--privacy",
        "public",
        "--authority",
        "official",
        "--owner",
        "fixture",
        "--json",
    )
    assert completed.returncode == 0, completed.stderr


def test_registering_a_second_source_preserves_the_first(tmp_path: Path) -> None:
    package = tmp_path / "package"
    first = _run_cli(
        "source-register",
        "--package",
        str(package),
        "--source-id",
        "fastapi-docs",
        "--canonical",
        "https://docs.example.test/fastapi",
        "--kind",
        "web",
        "--scope",
        "docs/**",
        "--version-policy",
        "pinned",
        "--version",
        "1.0",
        "--rights",
        "MIT",
        "--privacy",
        "public",
        "--authority",
        "official",
        "--owner",
        "fixture",
        "--json",
    )
    assert first.returncode == 0, first.stderr

    second = _run_cli(
        "source-register",
        "--package",
        str(package),
        "--source-id",
        "pydantic-docs",
        "--canonical",
        "https://docs.example.test/pydantic",
        "--kind",
        "web",
        "--scope",
        "docs/**",
        "--version-policy",
        "latest",
        "--rights",
        "MIT",
        "--privacy",
        "public",
        "--authority",
        "official",
        "--owner",
        "fixture",
        "--json",
    )
    assert second.returncode == 0, second.stderr

    payload = _registry(package)
    registrations = payload["registrations"]
    assert isinstance(registrations, list)
    assert {item["source_id"] for item in registrations} == {"fastapi-docs", "pydantic-docs"}


def test_partial_reconcile_preserves_all_active_sources(tmp_path: Path) -> None:
    package = tmp_path / "package"
    _register(package, "fastapi-docs", "https://docs.example.test/fastapi")
    _register(package, "pydantic-docs", "https://docs.example.test/pydantic")
    snapshot = tmp_path / "partial.json"
    snapshot.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_id": "fastapi-docs",
                "revision": "crawl-2",
                "version": None,
                "entries": [{"canonical": "https://docs.example.test/fastapi/intro"}],
                "scope": "docs/**",
                "completeness": "partial",
                "observation_time": "2026-09-05T12:00:00Z",
                "errors": [{"code": "max_pages", "message": "synthetic limit reached"}],
            }
        ),
        encoding="utf-8",
    )

    reconciled = _run_cli(
        "source-reconcile",
        "--package",
        str(package),
        "--snapshot",
        str(snapshot),
        "--json",
    )

    assert reconciled.returncode == 2
    payload = json.loads(reconciled.stdout)
    assert payload["code"] == "acquisition_incomplete"
    registry = _registry(package)
    assert {item["source_id"] for item in registry["registrations"] if item["status"] == "active"} == {
        "fastapi-docs",
        "pydantic-docs",
    }
    assert registry["withdrawals"] == []
    assert registry["snapshots"][-1]["decision"] == "preserved_incomplete"


def test_physical_duplicate_keeps_distinct_provenance_and_rights(tmp_path: Path) -> None:
    package = tmp_path / "package"
    canonical = "https://docs.example.test/shared"
    for source_id, rights, owner in (
        ("mirror-a", "MIT", "team-a"),
        ("mirror-b", "CC-BY-4.0", "team-b"),
    ):
        completed = _run_cli(
            "source-register",
            "--package",
            str(package),
            "--source-id",
            source_id,
            "--canonical",
            canonical,
            "--kind",
            "web",
            "--scope",
            "docs/**",
            "--version-policy",
            "latest",
            "--rights",
            rights,
            "--privacy",
            "public",
            "--authority",
            "operator",
            "--owner",
            owner,
            "--json",
        )
        assert completed.returncode == 0, completed.stderr

    registrations = _registry(package)["registrations"]
    assert len(registrations) == 2
    assert {item["source_id"] for item in registrations} == {"mirror-a", "mirror-b"}
    assert {item["rights"] for item in registrations} == {"MIT", "CC-BY-4.0"}
    assert {item["owner"] for item in registrations} == {"team-a", "team-b"}


def test_pinned_version_does_not_advance_from_snapshot(tmp_path: Path) -> None:
    package = tmp_path / "package"
    _register(package, "fastapi-docs", "https://docs.example.test/fastapi", version_policy="pinned")
    snapshot = tmp_path / "new-version.json"
    snapshot.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_id": "fastapi-docs",
                "revision": "commit-2",
                "version": "2.0",
                "entries": [{"canonical": "https://docs.example.test/fastapi/intro"}],
                "scope": "docs/**",
                "completeness": "complete",
                "observation_time": "2026-09-05T12:00:00Z",
                "errors": [],
            }
        ),
        encoding="utf-8",
    )

    reconciled = _run_cli(
        "source-reconcile",
        "--package",
        str(package),
        "--snapshot",
        str(snapshot),
        "--json",
    )

    assert reconciled.returncode == 2
    assert json.loads(reconciled.stdout)["code"] == "version_pinned"
    registration = _registry(package)["registrations"][0]
    assert registration["version"] == "1.0"
    assert _registry(package)["snapshots"][-1]["decision"] == "preserved_pinned"


def test_empty_complete_snapshot_requires_explicit_withdrawal(tmp_path: Path) -> None:
    package = tmp_path / "package"
    _register(package, "fastapi-docs", "https://docs.example.test/fastapi")
    snapshot = tmp_path / "empty.json"
    snapshot.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_id": "fastapi-docs",
                "revision": "crawl-empty",
                "version": None,
                "entries": [],
                "scope": "docs/**",
                "completeness": "complete",
                "observation_time": "2026-09-05T12:00:00Z",
                "errors": [],
            }
        ),
        encoding="utf-8",
    )

    preserved = _run_cli(
        "source-reconcile",
        "--package",
        str(package),
        "--snapshot",
        str(snapshot),
        "--json",
    )
    assert preserved.returncode == 2
    assert json.loads(preserved.stdout)["code"] == "withdrawal_confirmation_required"
    assert _registry(package)["registrations"][0]["status"] == "active"

    withdrawn = _run_cli(
        "source-reconcile",
        "--package",
        str(package),
        "--snapshot",
        str(snapshot),
        "--withdraw",
        "--json",
    )
    assert withdrawn.returncode == 0
    payload = json.loads(withdrawn.stdout)
    assert payload["code"] == "source_withdrawn"
    registry = _registry(package)
    assert registry["registrations"][0]["status"] == "withdrawn"
    assert registry["withdrawals"][-1]["source_id"] == "fastapi-docs"


def test_reconciliation_requires_explicit_rights_privacy_and_authority(tmp_path: Path) -> None:
    package = tmp_path / "package"
    unadmitted = _run_cli(
        "source-register",
        "--package",
        str(package),
        "--source-id",
        "unadmitted",
        "--canonical",
        "https://docs.example.test/unadmitted",
        "--kind",
        "web",
        "--scope",
        "docs/**",
        "--rights",
        "unknown",
        "--privacy",
        "unknown",
        "--authority",
        "unknown",
        "--owner",
        "fixture",
        "--json",
    )
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_id": "unadmitted",
                "revision": "revision-1",
                "version": None,
                "entries": [{"canonical": "https://docs.example.test/unadmitted/guide"}],
                "scope": "docs/**",
                "completeness": "complete",
                "observation_time": "2026-09-05T12:00:00Z",
                "errors": [],
            }
        ),
        encoding="utf-8",
    )

    reconciled = _run_cli(
        "source-reconcile",
        "--package",
        str(package),
        "--snapshot",
        str(snapshot),
        "--json",
    )

    assert unadmitted.returncode == 0, unadmitted.stderr
    assert reconciled.returncode == 2
    assert json.loads(reconciled.stdout)["code"] == "source_not_admitted"
    assert _registry(package)["registrations"][0]["status"] == "active"


def test_withdrawn_source_requires_explicit_readmission(tmp_path: Path) -> None:
    package = tmp_path / "package"
    _register(package, "withdrawn", "https://docs.example.test/withdrawn")
    snapshot = tmp_path / "empty.json"
    snapshot.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_id": "withdrawn",
                "revision": "revision-withdrawn",
                "version": None,
                "entries": [],
                "scope": "docs/**",
                "completeness": "complete",
                "observation_time": "2026-09-05T12:00:00Z",
                "errors": [],
            }
        ),
        encoding="utf-8",
    )
    withdrawn = _run_cli(
        "source-reconcile",
        "--package",
        str(package),
        "--snapshot",
        str(snapshot),
        "--withdraw",
        "--json",
    )
    ordinary_register = _run_cli(
        "source-register",
        "--package",
        str(package),
        "--source-id",
        "withdrawn",
        "--canonical",
        "https://docs.example.test/withdrawn",
        "--kind",
        "web",
        "--scope",
        "docs/**",
        "--rights",
        "MIT",
        "--privacy",
        "public",
        "--authority",
        "official",
        "--owner",
        "fixture",
        "--json",
    )
    still_withdrawn = _registry(package)["registrations"][0]["status"]
    assert withdrawn.returncode == 0, withdrawn.stderr
    assert ordinary_register.returncode == 1
    assert json.loads(ordinary_register.stdout)["errors"][0]["code"] == "source_readmission_required"
    assert still_withdrawn == "withdrawn"

    readmitted = _run_cli(
        "source-register",
        "--package",
        str(package),
        "--source-id",
        "withdrawn",
        "--canonical",
        "https://docs.example.test/withdrawn",
        "--kind",
        "web",
        "--scope",
        "docs/**",
        "--rights",
        "MIT",
        "--privacy",
        "public",
        "--authority",
        "official",
        "--owner",
        "fixture",
        "--readmit",
        "--json",
    )
    assert readmitted.returncode == 0, readmitted.stdout + readmitted.stderr
    assert _registry(package)["registrations"][0]["status"] == "active"


def test_plan_does_not_advertise_removal_after_empty_acquisition(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    document = source / "guide.md"
    document.write_text("# Guide\nStable facts.\n", encoding="utf-8")
    package = tmp_path / "package"
    request = docops.OperationRequest(
        source,
        docops.OperationOptions(
            output_dir=package,
            source_root=source.parent,
            slug="guide",
            license="MIT",
            mode="run",
        ),
    )
    assert docops.apply(docops.plan(request)).ok
    document.unlink()

    blocked = docops.plan(
        docops.OperationRequest(
            source,
            docops.OperationOptions(
                output_dir=package,
                source_root=source.parent,
                slug="guide",
                license="MIT",
                mode="update",
            ),
        )
    )

    assert any(item["code"] == "no_accepted_documents" for item in blocked.blockers)
    assert blocked.state_diff["removed"] == 0
    assert (package / "rag" / "documents" / "guide.md").read_text(encoding="utf-8") == "# Guide\nStable facts.\n"
