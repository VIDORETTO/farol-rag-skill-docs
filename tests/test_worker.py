from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "docops", *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        env=env,
    )


def test_work_once_prepares_a_candidate_without_activating_it(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\nWorker facts.\n", encoding="utf-8")
    output = tmp_path / "package"
    queue = tmp_path / "queue.sqlite"
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "event_id": "worker-event-1",
                "type": "source_changed",
                "package_id": "package-fixture",
                "source_id": "source-fixture",
                "observed_revision": "revision-1",
                "occurred_at": "2026-09-05T12:00:00Z",
                "origin": "synthetic-fixture",
                "payload": {
                    "policy_revision": "policy-1",
                    "work": {
                        "source": str(source),
                        "output_dir": str(output),
                        "source_root": str(tmp_path),
                        "slug": "worker-fixture",
                        "license": "MIT",
                        "mode": "run",
                        "layers": ["conceptual", "factual"],
                        "publication_policy": "candidate",
                        "index_rag": False,
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    submitted = _run_cli(
        "event-submit",
        "--queue",
        str(queue),
        "--event",
        str(event),
        "--now",
        "2026-09-05T12:00:00Z",
        "--json",
    )
    worked = _run_cli(
        "work",
        "--once",
        "--queue",
        str(queue),
        "--now",
        "2026-09-05T12:02:00Z",
        "--json",
    )

    assert submitted.returncode == 0, submitted.stderr
    assert worked.returncode == 0, worked.stderr
    report = json.loads(worked.stdout)
    assert report["code"] == "candidate_prepared"
    assert report["job"]["state"] == "succeeded"
    assert not (output / "manifest.json").exists()
    assert report["candidate_id"]


def test_work_once_blocks_rag_indexing_without_persisted_authorization(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\nWorker facts.\n", encoding="utf-8")
    output = tmp_path / "package"
    queue = tmp_path / "queue.sqlite"
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "event_id": "worker-event-rag-without-auth",
                "type": "source_changed",
                "package_id": "package-fixture",
                "source_id": "source-fixture",
                "observed_revision": "revision-1",
                "occurred_at": "2026-09-05T12:00:00Z",
                "origin": "synthetic-fixture",
                "payload": {
                    "policy_revision": "policy-1",
                    "work": {
                        "source": str(source),
                        "output_dir": str(output),
                        "source_root": str(tmp_path),
                        "slug": "worker-fixture",
                        "license": "MIT",
                        "mode": "run",
                        "layers": ["conceptual", "factual"],
                        "publication_policy": "candidate",
                        "index_rag": True,
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    submitted = _run_cli(
        "event-submit",
        "--queue",
        str(queue),
        "--event",
        str(event),
        "--now",
        "2026-09-05T12:00:00Z",
        "--json",
    )
    worked = _run_cli(
        "work",
        "--once",
        "--queue",
        str(queue),
        "--now",
        "2026-09-05T12:02:00Z",
        "--json",
    )

    assert submitted.returncode == 0, submitted.stderr
    assert worked.returncode == 2, worked.stderr
    report = json.loads(worked.stdout)
    assert report["code"] == "job_blocked"
    assert report["job"]["state"] == "blocked"
    assert report["job"]["error_code"] == "rag_authorization_required"
    assert not (output / "manifest.json").exists()
    assert not (output / "rag" / "index.json").exists()


def test_work_once_blocks_direct_publication_policy(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\nWorker facts.\n", encoding="utf-8")
    output = tmp_path / "package"
    queue = tmp_path / "queue.sqlite"
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "event_id": "worker-event-direct-publication",
                "type": "source_changed",
                "package_id": "package-fixture",
                "source_id": "source-fixture",
                "observed_revision": "revision-1",
                "occurred_at": "2026-09-05T12:00:00Z",
                "origin": "synthetic-fixture",
                "payload": {
                    "policy_revision": "policy-1",
                    "work": {
                        "source": str(source),
                        "output_dir": str(output),
                        "source_root": str(tmp_path),
                        "slug": "worker-fixture",
                        "license": "MIT",
                        "mode": "run",
                        "layers": ["conceptual", "factual"],
                        "publication_policy": "direct",
                        "index_rag": False,
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    submitted = _run_cli(
        "event-submit",
        "--queue",
        str(queue),
        "--event",
        str(event),
        "--now",
        "2026-09-05T12:00:00Z",
        "--json",
    )
    worked = _run_cli(
        "work",
        "--once",
        "--queue",
        str(queue),
        "--now",
        "2026-09-05T12:02:00Z",
        "--json",
    )

    assert submitted.returncode == 0, submitted.stderr
    assert worked.returncode == 2, worked.stderr
    report = json.loads(worked.stdout)
    assert report["code"] == "job_blocked"
    assert report["job"]["state"] == "blocked"
    assert report["job"]["error_code"] == "auto_publication_disabled"
    assert not (output / "manifest.json").exists()


def test_work_once_reconciles_effect_after_worker_crash(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\nWorker facts.\n", encoding="utf-8")
    output = tmp_path / "package"
    queue = tmp_path / "queue.sqlite"
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "event_id": "worker-event-crash-window",
                "type": "source_changed",
                "package_id": "package-fixture",
                "source_id": "source-fixture",
                "observed_revision": "revision-1",
                "occurred_at": "2026-09-05T12:00:00Z",
                "origin": "synthetic-fixture",
                "payload": {
                    "policy_revision": "policy-1",
                    "work": {
                        "source": str(source),
                        "output_dir": str(output),
                        "source_root": str(tmp_path),
                        "slug": "worker-fixture",
                        "license": "MIT",
                        "mode": "run",
                        "layers": ["conceptual", "factual"],
                        "publication_policy": "candidate",
                        "index_rag": False,
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    submitted = _run_cli(
        "event-submit",
        "--queue",
        str(queue),
        "--event",
        str(event),
        "--now",
        "2026-09-05T12:00:00Z",
        "--json",
    )
    crashing_env = os.environ.copy()
    crashing_env["DOCOPS_TEST_WORKER_CRASH_AFTER_EFFECT"] = "1"
    crashed = _run_cli(
        "work",
        "--once",
        "--queue",
        str(queue),
        "--now",
        "2026-09-05T12:02:00Z",
        "--json",
        env=crashing_env,
    )
    candidate_root = output.parent / ".package.candidates"
    candidates_after_crash = sorted(path for path in candidate_root.iterdir() if path.is_dir())
    receipt_root = output / ".docops" / "job-receipts"
    receipts_after_crash = sorted(receipt_root.glob("*.json"))

    resumed = _run_cli(
        "work",
        "--once",
        "--queue",
        str(queue),
        "--now",
        "2026-09-05T12:05:00Z",
        "--json",
    )

    assert submitted.returncode == 0, submitted.stderr
    assert crashed.returncode != 0
    assert len(candidates_after_crash) == 1
    assert len(receipts_after_crash) == 1
    assert resumed.returncode == 0, resumed.stderr
    report = json.loads(resumed.stdout)
    assert report["code"] == "effect_reconciled"
    assert report["job"]["state"] == "succeeded"
    assert report["result_ref"]
    assert len([path for path in candidate_root.iterdir() if path.is_dir()]) == 1


def test_event_during_running_job_is_queued_for_a_later_batch(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\nWorker facts.\n", encoding="utf-8")
    output = tmp_path / "package"
    queue = tmp_path / "queue.sqlite"
    event_one = tmp_path / "event-one.json"
    event_two = tmp_path / "event-two.json"

    payload = {
        "policy_revision": "policy-1",
        "work": {
            "source": str(source),
            "output_dir": str(output),
            "source_root": str(tmp_path),
            "slug": "worker-fixture",
            "license": "MIT",
            "mode": "run",
            "layers": ["conceptual", "factual"],
            "publication_policy": "candidate",
            "index_rag": False,
        },
    }
    event_one.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "event_id": "worker-event-running-one",
                "type": "source_changed",
                "package_id": "package-fixture",
                "source_id": "source-fixture",
                "observed_revision": "revision-1",
                "occurred_at": "2026-09-05T12:00:00Z",
                "origin": "synthetic-fixture",
                "payload": payload,
            }
        ),
        encoding="utf-8",
    )
    event_two.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "event_id": "worker-event-running-two",
                "type": "source_changed",
                "package_id": "package-fixture",
                "source_id": "source-fixture",
                "observed_revision": "revision-1",
                "occurred_at": "2026-09-05T12:03:00Z",
                "origin": "synthetic-fixture",
                "payload": payload,
            }
        ),
        encoding="utf-8",
    )

    submitted_one = _run_cli(
        "event-submit",
        "--queue",
        str(queue),
        "--event",
        str(event_one),
        "--now",
        "2026-09-05T12:00:00Z",
        "--json",
    )
    crashing_env = os.environ.copy()
    crashing_env["DOCOPS_TEST_WORKER_CRASH_AFTER_EFFECT"] = "1"
    crashed = _run_cli(
        "work",
        "--once",
        "--queue",
        str(queue),
        "--now",
        "2026-09-05T12:02:00Z",
        "--json",
        env=crashing_env,
    )
    submitted_two = _run_cli(
        "event-submit",
        "--queue",
        str(queue),
        "--event",
        str(event_two),
        "--now",
        "2026-09-05T12:03:00Z",
        "--json",
    )
    listed = _run_cli(
        "jobs",
        "--queue",
        str(queue),
        "--now",
        "2026-09-05T12:03:00Z",
        "--json",
    )

    assert submitted_one.returncode == 0, submitted_one.stderr
    assert crashed.returncode != 0
    assert submitted_two.returncode == 0, submitted_two.stderr
    assert listed.returncode == 0, listed.stderr
    jobs = json.loads(listed.stdout)["jobs"]
    assert len(jobs) == 2
    assert {job["state"] for job in jobs} == {"running", "pending"}
    assert len({job["job_key"] for job in jobs}) == 2


def test_transient_writer_busy_retries_then_blocks_at_the_attempt_limit(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\nWorker facts.\n", encoding="utf-8")
    output = tmp_path / "package"
    queue = tmp_path / "queue.sqlite"
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "event_id": "worker-event-retry-limit",
                "type": "source_changed",
                "package_id": "package-fixture",
                "source_id": "source-fixture",
                "observed_revision": "revision-1",
                "occurred_at": "2026-09-05T12:00:00Z",
                "origin": "synthetic-fixture",
                "payload": {
                    "policy_revision": "policy-1",
                    "work": {
                        "source": str(source),
                        "output_dir": str(output),
                        "source_root": str(tmp_path),
                        "slug": "worker-fixture",
                        "license": "MIT",
                        "mode": "run",
                        "layers": ["conceptual", "factual"],
                        "publication_policy": "candidate",
                        "index_rag": False,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    submitted = _run_cli(
        "event-submit",
        "--queue",
        str(queue),
        "--event",
        str(event),
        "--now",
        "2026-09-05T12:00:00Z",
        "--json",
    )
    holder_code = (
        "import sys\n"
        "from pathlib import Path\n"
        "from docops.lease import PackageLease\n"
        "lease = PackageLease(Path(sys.argv[1]), policy='fail')\n"
        "lease.acquire()\n"
        "print('ready', flush=True)\n"
        "sys.stdin.readline()\n"
        "lease.release()\n"
    )
    holder = subprocess.Popen(
        [sys.executable, "-c", holder_code, str(output)],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "ready"
        retry_times = (
            "2026-09-05T12:02:00Z",
            "2026-09-05T12:03:00Z",
            "2026-09-05T12:08:00Z",
            "2026-09-05T12:23:00Z",
        )
        reports = []
        for retry_time in retry_times:
            worked = _run_cli(
                "work",
                "--once",
                "--queue",
                str(queue),
                "--now",
                retry_time,
                "--json",
            )
            assert worked.returncode == 2, worked.stderr
            reports.append(json.loads(worked.stdout))
        blocked = _run_cli(
            "work",
            "--once",
            "--queue",
            str(queue),
            "--now",
            "2026-09-05T13:23:00Z",
            "--json",
        )
    finally:
        if holder.stdin is not None:
            holder.stdin.write("\n")
            holder.stdin.flush()
        holder.wait(timeout=5)

    assert submitted.returncode == 0, submitted.stderr
    assert [report["code"] for report in reports] == ["retry_scheduled"] * 4
    assert all(report["job"]["state"] == "pending" for report in reports)
    assert all(report["job"]["error_code"] == "writer_busy" for report in reports)
    assert blocked.returncode == 2, blocked.stderr
    blocked_report = json.loads(blocked.stdout)
    assert blocked_report["code"] == "job_blocked"
    assert blocked_report["job"]["state"] == "blocked"
    assert blocked_report["job"]["attempt"] == 5
    assert blocked_report["job"]["error_code"] == "writer_busy"
