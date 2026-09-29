# seam-scope: implementation-infrastructure (feedback governance fixtures)
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import docops
from docops.feedback import FeedbackError, submit_feedback


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "docops", *args, "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _package(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\nStable fixture facts.\n", encoding="utf-8")
    output = tmp_path / "package"
    result = docops.apply(
        docops.plan(
            docops.OperationRequest(
                source,
                docops.OperationOptions(
                    output_dir=output,
                    source_root=source.parent,
                    slug="feedback-guide",
                    license="MIT",
                    mode="run",
                    layers=("conceptual", "factual"),
                    publication_policy="direct",
                    index_rag=False,
                ),
            )
        )
    )
    assert result.ok, result.errors
    return output


def _feedback(
    *,
    feedback_id: str,
    session_id: str,
    occurred_at: str,
    question: str = "Private customer question with a secret@example.test address",
    dataset_id: str = "golden-a",
) -> dict[str, object]:
    return {
        "feedback_id": feedback_id,
        "event_id": f"event-{feedback_id}",
        "package_id": "package-fixture",
        "generation": {
            "release_id": "release-1",
            "composition_hash": "a" * 64,
            "corpus_revision": "corpus-1",
            "index_revision": "index-1",
            "golden_revision": "golden-1",
            "harness_revision": "harness-1",
            "configuration_hash": "config-1",
        },
        "kind": "wrong_answer",
        "question": question,
        "reporter_id": f"reporter-{session_id}",
        "session_id": session_id,
        "authentication": {
            "authenticated": True,
            "source": "fixture-feedback-idp",
            "subject": f"reporter-{session_id}",
            "proof": f"signed-feedback-{feedback_id}",
        },
        "occurred_at": occurred_at,
        "usage": {"latency_ms": 120, "cost_units": 0.02, "denominator": 1},
        "comparison": {
            "metric": "recall_at_5",
            "baseline": {
                "value": 0.95,
                "denominator": 100,
                "dataset_id": dataset_id,
                "corpus_revision": "corpus-1",
                "index_revision": "index-1",
                "golden_revision": "golden-1",
                "harness_revision": "harness-1",
                "configuration_hash": "config-1",
            },
            "current": {
                "value": 0.80,
                "denominator": 100,
                "dataset_id": "golden-b",
                "corpus_revision": "corpus-2",
                "index_revision": "index-2",
                "golden_revision": "golden-2",
                "harness_revision": "harness-2",
                "configuration_hash": "config-2",
            },
        },
    }


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(
        path for path in root.rglob("*") if path.is_file() and not path.is_symlink() and ".docops" not in path.parts
    ):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def test_feedback_requires_an_authenticated_origin(tmp_path: Path) -> None:
    package = _package(tmp_path)
    path = tmp_path / "unauthenticated-feedback.json"
    feedback = _feedback(
        feedback_id="unauthenticated-feedback",
        session_id="session-unauthenticated",
        occurred_at="2026-09-05T00:00:00Z",
    )
    feedback.pop("authentication")
    _write_json(path, feedback)

    submitted = _run_cli("feedback-submit", "--package", str(package), "--feedback", str(path))

    assert submitted.returncode == 1
    assert json.loads(submitted.stdout)["errors"][0]["code"] == "feedback_authentication_required"


def test_feedback_event_id_is_single_use_even_when_feedback_id_changes(tmp_path: Path) -> None:
    package = _package(tmp_path)
    first_path = tmp_path / "first-feedback.json"
    second_path = tmp_path / "replayed-feedback.json"
    first = _feedback(
        feedback_id="first-feedback",
        session_id="session-replay",
        occurred_at="2026-09-05T00:00:00Z",
    )
    second = _feedback(
        feedback_id="second-feedback",
        session_id="session-replay",
        occurred_at="2026-09-05T00:00:01Z",
    )
    second["event_id"] = first["event_id"]
    _write_json(first_path, first)
    _write_json(second_path, second)

    accepted = _run_cli("feedback-submit", "--package", str(package), "--feedback", str(first_path))
    replayed = _run_cli("feedback-submit", "--package", str(package), "--feedback", str(second_path))

    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert replayed.returncode == 1
    assert json.loads(replayed.stdout)["errors"][0]["code"] == "feedback_replay"
    stored = json.loads(next((package / ".docops" / "feedback" / "submissions").glob("*.json")).read_text())
    assert stored["authentication"]["authenticated"] is True
    assert "subject" not in stored["authentication"]
    assert "proof" not in stored["authentication"]


def test_feedback_rate_limit_is_scoped_to_authenticated_origin(tmp_path: Path) -> None:
    package = _package(tmp_path)
    for index in range(20):
        submit_feedback(
            package,
            _feedback(
                feedback_id=f"rate-{index}",
                session_id="rate-limited-session",
                occurred_at="2026-09-05T00:00:00Z",
            ),
        )

    try:
        submit_feedback(
            package,
            _feedback(
                feedback_id="rate-20",
                session_id="rate-limited-session",
                occurred_at="2026-09-05T00:00:30Z",
            ),
        )
    except FeedbackError as exc:
        assert exc.code == "feedback_rate_limited"
    else:
        raise AssertionError("the authenticated origin should be rate limited")


def test_three_independent_failures_open_unreviewed_investigation_without_mutation(tmp_path: Path) -> None:
    package = _package(tmp_path)
    golden = package / "golden.json"
    _write_json(golden, {"schema_version": 1, "reviewed": True, "cases": [{"query": "stable"}]})
    before_active = _tree_hash(package)

    paths: list[Path] = []
    for index in range(3):
        path = tmp_path / f"feedback-{index}.json"
        _write_json(
            path,
            _feedback(
                feedback_id=f"feedback-{index}",
                session_id=f"session-{index}",
                occurred_at=f"2026-09-05T00:0{index}:00Z",
            ),
        )
        paths.append(path)
        submitted = _run_cli("feedback-submit", "--package", str(package), "--feedback", str(path))
        assert submitted.returncode == 0, submitted.stdout + submitted.stderr

    report = _run_cli(
        "feedback-report",
        "--package",
        str(package),
        "--now",
        "2026-09-05T00:07:00Z",
        "--window-days",
        "7",
    )
    assert report.returncode == 0, report.stdout + report.stderr
    payload = json.loads(report.stdout)
    assert payload["investigations"][0]["status"] == "candidate_requested"
    assert payload["investigations"][0]["golden_candidate"]["reviewed"] is False
    assert payload["publication_allowed"] is False
    assert payload["golden_changed"] is False
    assert payload["expected_response_changed"] is False
    assert payload["occurrences"][0]["question"] == "<redacted-query>"
    assert "secret@example.test" not in report.stdout
    assert _tree_hash(package) == before_active


def test_repeated_signal_is_deduplicated_and_noncomparable_metrics_are_not_regressions(tmp_path: Path) -> None:
    package = _package(tmp_path)
    for index, session_id in enumerate(("session-0", "session-1", "session-2", "session-0")):
        path = tmp_path / f"duplicate-feedback-{index}.json"
        _write_json(
            path,
            _feedback(
                feedback_id=f"duplicate-feedback-{index}",
                session_id=session_id,
                occurred_at=f"2026-09-05T00:0{index}:00Z",
            ),
        )
        submitted = _run_cli("feedback-submit", "--package", str(package), "--feedback", str(path))
        assert submitted.returncode == 0, submitted.stdout + submitted.stderr

    report = _run_cli(
        "feedback-report",
        "--package",
        str(package),
        "--now",
        "2026-09-05T00:07:00Z",
    )
    assert report.returncode == 0, report.stdout + report.stderr
    payload = json.loads(report.stdout)
    assert payload["counts"] == {
        "submissions": 4,
        "unique_occurrences": 3,
        "duplicate_submissions": 1,
        "investigations": 1,
    }
    assert payload["comparison"]["status"] == "not_comparable"
    assert payload["comparison"]["controlled_regression"] is False
    assert payload["usage"]["denominators"]["submissions"] == 4
    assert payload["usage"]["denominators"]["unique_occurrences"] == 3
    assert "secret@example.test" not in report.stdout


def test_feedback_queue_worker_reports_without_publishing(tmp_path: Path) -> None:
    package = _package(tmp_path)
    golden = package / "golden.json"
    golden.write_text(
        json.dumps({"schema_version": 1, "reviewed": True, "cases": [{"query": "stable"}]}),
        encoding="utf-8",
    )
    golden_before = golden.read_bytes()
    queue = tmp_path / "queue.sqlite"

    for index in range(3):
        path = tmp_path / f"queued-feedback-{index}.json"
        _write_json(
            path,
            _feedback(
                feedback_id=f"queued-feedback-{index}",
                session_id=f"queued-session-{index}",
                occurred_at=f"2026-09-05T00:0{index}:00Z",
            ),
        )
        submitted = _run_cli(
            "feedback-submit",
            "--package",
            str(package),
            "--feedback",
            str(path),
            "--queue",
            str(queue),
            "--now",
            "2026-09-05T00:00:00Z",
        )
        assert submitted.returncode == 0, submitted.stdout + submitted.stderr

    worked = _run_cli(
        "work",
        "--once",
        "--queue",
        str(queue),
        "--now",
        "2026-09-05T00:10:00Z",
        "--worker-id",
        "feedback-worker-fixture",
    )
    assert worked.returncode == 0, worked.stdout + worked.stderr
    worker_payload = json.loads(worked.stdout)
    assert worker_payload["code"] == "feedback_reported"
    assert worker_payload["job"]["state"] == "succeeded"
    assert worker_payload["job"]["result_ref"].startswith("feedback-report-")
    assert golden.read_bytes() == golden_before

    reports = list((package / ".docops" / "feedback" / "reports").glob("*.json"))
    candidates = list((package / ".docops" / "feedback" / "golden-candidates").glob("*.json"))
    assert len(reports) == 1
    assert len(candidates) == 1
    report_payload = json.loads(reports[0].read_text(encoding="utf-8"))
    candidate_payload = json.loads(candidates[0].read_text(encoding="utf-8"))
    assert report_payload["publication_allowed"] is False
    assert report_payload["golden_changed"] is False
    assert candidate_payload["reviewed"] is False
