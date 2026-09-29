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


def test_repeated_event_across_processes_creates_one_durable_job(tmp_path: Path) -> None:
    queue = tmp_path / "queue.sqlite"
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "event_id": "event-1",
                "type": "source_changed",
                "package_id": "package-fixture",
                "source_id": "source-fixture",
                "observed_revision": "revision-1",
                "occurred_at": "2026-09-05T12:00:00Z",
                "origin": "fixture",
                "causation_id": None,
                "payload": {"policy_revision": "policy-1"},
            }
        ),
        encoding="utf-8",
    )

    first = _run_cli(
        "event-submit",
        "--queue",
        str(queue),
        "--event",
        str(event),
        "--now",
        "2026-09-05T12:00:00Z",
        "--json",
    )
    second = _run_cli(
        "event-submit",
        "--queue",
        str(queue),
        "--event",
        str(event),
        "--now",
        "2026-09-05T12:00:30Z",
        "--json",
    )
    listed = _run_cli(
        "jobs",
        "--queue",
        str(queue),
        "--now",
        "2026-09-05T12:01:00Z",
        "--json",
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert listed.returncode == 0, listed.stderr
    payload = json.loads(listed.stdout)
    assert payload["ok"] is True
    assert len(payload["jobs"]) == 1
    assert payload["jobs"][0]["target_revision"] == "revision-1"


def test_reusing_event_id_with_different_payload_is_rejected(tmp_path: Path) -> None:
    queue = tmp_path / "queue.sqlite"
    event = {
        "schema_version": 1,
        "event_id": "event-conflict",
        "type": "source_changed",
        "package_id": "package-fixture",
        "source_id": "source-fixture",
        "observed_revision": "revision-1",
        "occurred_at": "2026-09-05T12:00:00Z",
        "origin": "fixture",
        "causation_id": None,
        "payload": {"policy_revision": "policy-1", "changed": "a"},
    }
    (tmp_path / "first.json").write_text(json.dumps(event), encoding="utf-8")
    first = _run_cli(
        "event-submit",
        "--queue",
        str(queue),
        "--event",
        str(tmp_path / "first.json"),
        "--now",
        "2026-09-05T12:00:00Z",
        "--json",
    )
    event["payload"]["changed"] = "b"
    (tmp_path / "second.json").write_text(json.dumps(event), encoding="utf-8")
    second = _run_cli(
        "event-submit",
        "--queue",
        str(queue),
        "--event",
        str(tmp_path / "second.json"),
        "--now",
        "2026-09-05T12:00:30Z",
        "--json",
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 1
    assert json.loads(second.stdout)["errors"][0]["code"] == "event_id_conflict"


def test_debounce_uses_short_window_without_exceeding_maximum(tmp_path: Path) -> None:
    queue = tmp_path / "queue.sqlite"
    for index, occurred_at in enumerate(
        ("2026-09-05T12:00:00Z", "2026-09-05T12:00:30Z", "2026-09-05T12:04:30Z"),
        start=1,
    ):
        event = {
            "schema_version": 1,
            "event_id": f"event-{index}",
            "type": "source_changed",
            "package_id": "package-fixture",
            "source_id": "source-fixture",
            "observed_revision": "revision-1",
            "occurred_at": occurred_at,
            "origin": "fixture",
            "causation_id": None,
            "payload": {"policy_revision": "policy-1"},
        }
        path = tmp_path / f"event-{index}.json"
        path.write_text(json.dumps(event), encoding="utf-8")
        completed = _run_cli(
            "event-submit",
            "--queue",
            str(queue),
            "--event",
            str(path),
            "--now",
            occurred_at,
            "--json",
        )
        assert completed.returncode == 0, completed.stderr

    listed = _run_cli("jobs", "--queue", str(queue), "--now", "2026-09-05T12:04:30Z", "--json")
    assert listed.returncode == 0, listed.stderr
    job = json.loads(listed.stdout)["jobs"][0]
    assert job["event_count"] == 3
    assert job["due_at"] == "2026-09-05T12:05:00Z"


def test_unstable_file_does_not_block_completed_file(tmp_path: Path) -> None:
    queue = tmp_path / "queue.sqlite"
    event = {
        "schema_version": 1,
        "event_id": "event-files",
        "type": "source_changed",
        "package_id": "package-fixture",
        "source_id": "source-fixture",
        "observed_revision": "revision-1",
        "occurred_at": "2026-09-05T12:00:00Z",
        "origin": "fixture",
        "causation_id": None,
        "payload": {
            "policy_revision": "policy-1",
            "files": [
                {"path": "done.md", "status": "completed"},
                {"path": "draft.md", "status": "unstable"},
            ],
        },
    }
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event), encoding="utf-8")

    submitted = _run_cli(
        "event-submit",
        "--queue",
        str(queue),
        "--event",
        str(event_path),
        "--now",
        "2026-09-05T12:00:00Z",
        "--json",
    )
    listed = _run_cli(
        "jobs",
        "--queue",
        str(queue),
        "--now",
        "2026-09-05T12:01:00Z",
        "--json",
    )

    assert submitted.returncode == 0, submitted.stderr
    assert listed.returncode == 0, listed.stderr
    job = json.loads(listed.stdout)["jobs"][0]
    assert job["completed_files"] == ["done.md"]
    assert job["deferred_files"] == ["draft.md"]
    assert job["ready"] is True


def test_coordination_state_is_excluded_from_source_acquisition(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\n", encoding="utf-8")
    runtime_state = source / ".docops" / "queue.sqlite"
    runtime_state.parent.mkdir()
    runtime_state.write_bytes(b"runtime queue")
    output = tmp_path / "package"

    request = docops.OperationRequest(
        source,
        docops.OperationOptions(
            output_dir=output,
            source_root=source.parent,
            slug="coordination-fixture",
            license="MIT",
            mode="run",
        ),
    )
    result = docops.apply(docops.plan(request))

    assert result.ok, result.errors
    assert (output / "rag" / "documents" / "guide.md").is_file()
    assert not list((output / "rag" / "documents").rglob("*.sqlite*"))
