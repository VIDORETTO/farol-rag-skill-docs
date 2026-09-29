from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import docops


def _request(
    source: Path,
    output: Path,
    *,
    mode: str = "run",
    policy: str = "direct",
) -> docops.OperationRequest:
    return docops.OperationRequest(
        source,
        docops.OperationOptions(
            output_dir=output,
            source_root=source.parent,
            slug="history-guide",
            license="MIT",
            mode=mode,
            publication_policy=policy,
        ),
    )


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "docops", *args, "--json"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _candidate_dir(output: Path, candidate_id: str) -> Path:
    return output.parent / f".{output.name}.candidates" / candidate_id


def _evaluate_candidate(output: Path, candidate_id: str, tmp_path: Path, expected: str) -> None:
    golden = tmp_path / f"golden-{candidate_id}.json"
    golden.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "reviewed": True,
                "cases": [
                    {
                        "id": f"case-{candidate_id}",
                        "query": expected,
                        "expected_filepath": "guide.md",
                        "kind": "factual",
                        "reviewed": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    completed = _run_cli(
        "evaluate",
        "--package",
        str(_candidate_dir(output, candidate_id)),
        "--cases",
        str(golden),
        "--adapter",
        "memory",
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(completed.stdout)["ok"] is True


def _publish_generation(source: Path, output: Path, tmp_path: Path, text: str) -> str:
    source.joinpath("guide.md").write_text(f"# Guide\n{text}\n", encoding="utf-8")
    prepared = docops.apply(docops.plan(_request(source, output, mode="update", policy="candidate")))
    assert prepared.ok, prepared.errors
    candidate_id = str(prepared.outcome["candidate_id"])
    _evaluate_candidate(output, candidate_id, tmp_path, text)

    approved = _run_cli(
        "candidate-approve",
        "--package",
        str(output),
        "--candidate-id",
        candidate_id,
        "--actor",
        "editor@example.test",
        "--role",
        "human_approver",
    )
    assert approved.returncode == 0, approved.stdout + approved.stderr
    published = _run_cli(
        "candidate-publish",
        "--package",
        str(output),
        "--candidate-id",
        candidate_id,
    )
    assert published.returncode == 0, published.stdout + published.stderr
    return str(json.loads(published.stdout)["release_id"])


def _two_published_generations(tmp_path: Path) -> tuple[Path, Path, str, str]:
    source = tmp_path / "source"
    source.mkdir()
    source.joinpath("guide.md").write_text("# Guide\nInitial facts.\n", encoding="utf-8")
    output = tmp_path / "package"
    initial = docops.apply(docops.plan(_request(source, output)))
    assert initial.ok, initial.errors
    first_release = _publish_generation(source, output, tmp_path, "First published facts.")
    second_release = _publish_generation(source, output, tmp_path, "Second published facts.")
    return source, output, first_release, second_release


def test_two_published_generations_can_return_to_the_first(tmp_path: Path) -> None:
    _source, output, first_release, second_release = _two_published_generations(tmp_path)
    assert first_release != second_release

    rollback = _run_cli(
        "candidate-rollback",
        "--package",
        str(output),
        "--release-id",
        first_release,
    )

    assert rollback.returncode == 0, rollback.stdout + rollback.stderr
    payload = json.loads(rollback.stdout)
    assert payload["status"] == "rolled_back"
    assert payload["release_id"] == first_release
    active = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert active["revisions"]["release_id"] == first_release
    assert active["revisions"]["release_id"] != second_release


def test_revoked_history_cannot_be_restored(tmp_path: Path) -> None:
    _source, output, first_release, _second_release = _two_published_generations(tmp_path)
    history_receipt_path = output.parent / f".{output.name}.history" / first_release / ".docops" / "history.json"
    receipt = json.loads(history_receipt_path.read_text(encoding="utf-8"))
    receipt["revoked"] = True
    history_receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    active_before = (output / "manifest.json").read_bytes()

    rollback = _run_cli(
        "candidate-rollback",
        "--package",
        str(output),
        "--release-id",
        first_release,
    )

    assert rollback.returncode == 1
    assert json.loads(rollback.stdout)["errors"][0]["code"] == "source_revoked"
    assert (output / "manifest.json").read_bytes() == active_before


@pytest.mark.parametrize("failpoint", ("after-active-to-backup", "after-stage-to-active"))
def test_rollback_recovers_after_promotion_crash_before_retry(tmp_path: Path, failpoint: str) -> None:
    _source, output, first_release, _second_release = _two_published_generations(tmp_path)
    crashed = subprocess.run(
        [
            sys.executable,
            "-m",
            "docops",
            "candidate-rollback",
            "--package",
            str(output),
            "--release-id",
            first_release,
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "DOCOPS_TEST_PROMOTION_FAILPOINT": failpoint},
    )
    assert crashed.returncode == 86, crashed.stdout + crashed.stderr

    retried = _run_cli(
        "candidate-rollback",
        "--package",
        str(output),
        "--release-id",
        first_release,
    )
    assert retried.returncode == 0, retried.stdout + retried.stderr
    assert json.loads(retried.stdout)["status"] in {"rolled_back", "already_active"}
    active = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert active["revisions"]["release_id"] == first_release


def test_incompatible_history_requires_rebuild_before_restore(tmp_path: Path) -> None:
    _source, output, first_release, _second_release = _two_published_generations(tmp_path)
    history_receipt_path = output.parent / f".{output.name}.history" / first_release / ".docops" / "history.json"
    receipt = json.loads(history_receipt_path.read_text(encoding="utf-8"))
    receipt["index_compatible"] = False
    history_receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    active_before = (output / "manifest.json").read_bytes()

    rollback = _run_cli(
        "candidate-rollback",
        "--package",
        str(output),
        "--release-id",
        first_release,
    )

    assert rollback.returncode == 1
    assert json.loads(rollback.stdout)["errors"][0]["code"] == "index_incompatible"
    assert (output / "manifest.json").read_bytes() == active_before


def test_history_quota_blocks_publication_before_active_is_lost(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    source.joinpath("guide.md").write_text("# Guide\nInitial facts.\n", encoding="utf-8")
    output = tmp_path / "package"
    initial = docops.apply(docops.plan(_request(source, output)))
    assert initial.ok, initial.errors
    first_release = _publish_generation(source, output, tmp_path, "First published facts.")
    active_before = (output / "manifest.json").read_bytes()

    source.joinpath("guide.md").write_text("# Guide\nSecond published facts.\n", encoding="utf-8")
    prepared = docops.apply(docops.plan(_request(source, output, mode="update", policy="candidate")))
    assert prepared.ok, prepared.errors
    candidate_id = str(prepared.outcome["candidate_id"])
    _evaluate_candidate(output, candidate_id, tmp_path, "Second published facts.")
    approved = _run_cli(
        "candidate-approve",
        "--package",
        str(output),
        "--candidate-id",
        candidate_id,
        "--actor",
        "editor@example.test",
        "--role",
        "human_approver",
    )
    assert approved.returncode == 0, approved.stdout + approved.stderr

    monkeypatch.setenv("DOCOPS_TEST_HISTORY_QUOTA_BYTES", "1")
    published = _run_cli(
        "candidate-publish",
        "--package",
        str(output),
        "--candidate-id",
        candidate_id,
    )

    assert published.returncode == 1
    assert json.loads(published.stdout)["errors"][0]["code"] == "history_quota_exceeded"
    assert (output / "manifest.json").read_bytes() == active_before
    assert (
        json.loads((output / "manifest.json").read_text(encoding="utf-8"))["revisions"]["release_id"] == first_release
    )


def test_editorial_history_is_not_cleanup_residue(tmp_path: Path) -> None:
    _source, output, first_release, _second_release = _two_published_generations(tmp_path)

    inspected = docops.inspect(output)
    history = inspected["history"]
    assert first_release in {entry["release_id"] for entry in history}
    assert all(entry["status"] == "retained" for entry in history)

    cleaned = docops.cleanup(output, retention_seconds=0, keep_attempts=0)
    assert cleaned["ok"] is True
    assert first_release in {entry["release_id"] for entry in docops.inspect(output)["history"]}
