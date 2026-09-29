from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "docops", *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
    )


def _event(
    event_id: str,
    *,
    document_id: str,
    revision: str,
    base_revision: str = "base",
    impact: str = "conceptual",
    source_id: str = "source-fixture",
    occurred_at: str = "2026-09-05T12:00:00Z",
    revoked: bool = False,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "event_id": event_id,
        "type": "source_changed",
        "package_id": "package-fixture",
        "source_id": source_id,
        "observed_revision": revision,
        "occurred_at": occurred_at,
        "origin": "synthetic-fixture",
        "causation_id": None,
        "payload": {
            "document_id": document_id,
            "document_revision": revision,
            "base_revision": base_revision,
            "impact": impact,
            "revoked": revoked,
        },
    }


def test_conceptual_trigger_counts_net_impact_and_keeps_factual_updates_out(tmp_path: Path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    events = tmp_path / "events.json"
    events.write_text(
        json.dumps(
            [
                _event(
                    f"event-{index}",
                    document_id=f"doc-{index}",
                    revision=f"revision-{index}",
                )
                for index in range(10)
            ]
            + [
                _event(
                    "event-factual",
                    document_id="doc-factual",
                    revision="revision-factual",
                    impact="factual",
                ),
                _event(
                    "event-reverted",
                    document_id="doc-0",
                    revision="base",
                    base_revision="base",
                ),
            ]
        ),
        encoding="utf-8",
    )

    result = _run_cli(
        "impact-assess",
        "--package",
        str(package),
        "--events",
        str(events),
        "--now",
        "2026-09-05T12:05:00Z",
        "--threshold",
        "10",
        "--budget",
        "1",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["relevant_count"] == 9
    assert report["batch"]["status"] == "none"
    assert report["reverted_documents"] == ["doc-0"]
    assert report["factual_documents"] == ["doc-factual"]


def test_conceptual_trigger_uncertain_impact_requires_review(tmp_path: Path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    events = tmp_path / "events.json"
    events.write_text(
        json.dumps(
            [
                _event(
                    "event-uncertain",
                    document_id="doc-uncertain",
                    revision="revision-uncertain",
                    impact="uncertain",
                )
            ]
        ),
        encoding="utf-8",
    )

    result = _run_cli(
        "impact-assess",
        "--package",
        str(package),
        "--events",
        str(events),
        "--threshold",
        "1",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["batch"]["status"] == "review_required"
    assert report["batch"]["publication_allowed"] is False


def test_conceptual_trigger_exposes_budget_backlog_and_revocation_without_budget(tmp_path: Path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    first_events = tmp_path / "first.json"
    first_events.write_text(
        json.dumps(
            [
                _event(
                    "event-first",
                    document_id="doc-first",
                    revision="revision-first",
                )
            ]
        ),
        encoding="utf-8",
    )
    first = _run_cli(
        "impact-assess",
        "--package",
        str(package),
        "--events",
        str(first_events),
        "--threshold",
        "1",
        "--budget",
        "1",
        "--json",
    )
    assert first.returncode == 0, first.stderr
    assert json.loads(first.stdout)["batch"]["status"] == "candidate_requested"

    second_events = tmp_path / "second.json"
    second_events.write_text(
        json.dumps(
            [
                _event(
                    "event-second",
                    document_id="doc-second",
                    revision="revision-second",
                    occurred_at="2026-09-05T12:01:00Z",
                ),
                _event(
                    "event-revoke",
                    document_id="doc-first",
                    revision="revision-first",
                    occurred_at="2026-09-05T12:02:00Z",
                    revoked=True,
                ),
            ]
        ),
        encoding="utf-8",
    )
    second = _run_cli(
        "impact-assess",
        "--package",
        str(package),
        "--events",
        str(second_events),
        "--threshold",
        "1",
        "--budget",
        "1",
        "--now",
        "2026-09-05T12:03:00Z",
        "--json",
    )

    assert second.returncode == 0, second.stderr
    report = json.loads(second.stdout)
    assert report["batch"]["status"] == "backlog"
    assert report["backlog_count"] == 1
    assert report["revocations"][0]["document_id"] == "doc-first"
    assert report["revocations"][0]["support_valid"] is False
