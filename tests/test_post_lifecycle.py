# seam-scope: compatibility-infrastructure (public lifecycle coverage lives in test_public_seams.py)
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import threading
from dataclasses import FrozenInstanceError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

import docops
import docops.storage as storage
from docops.lease import PackageLease
from docops.package_validator import validate_package
from docops.pipeline import PipelineOptions, apply, plan, run_pipeline


def test_plan_reports_new_documents_without_touching_the_destination(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\nPlan me.\n", encoding="utf-8")
    output = tmp_path / "package"

    operation = plan(
        source,
        options=PipelineOptions(output_dir=output, slug="guide", license="MIT", mode="dry-run"),
    )

    assert operation.blockers == ()
    assert [action.kind for action in operation.actions] == ["add"]
    assert operation.actions[0].destination == "guide.md"
    assert operation.expected_readiness["rag"] == "corpus-ready"
    assert not output.exists()


def test_run_dry_run_is_the_public_plan_alias_and_preserves_the_full_diff(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\nPlan alias.\n", encoding="utf-8")
    output = tmp_path / "package"

    result = run_pipeline(
        source,
        options=PipelineOptions(output_dir=output, slug="guide", license="MIT", mode="dry-run"),
    )

    assert result.ok, result.errors
    assert result.outcome["code"] == "planned"
    assert result.state_diff == {"added": 1, "updated": 0, "removed": 0}
    assert result.manifest["metrics"]["plan"]["actions"][0]["kind"] == "add"
    assert not output.exists()


def test_apply_materializes_exactly_the_plan_actions(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\nApply me.\n", encoding="utf-8")
    output = tmp_path / "package"
    operation = plan(source, options=PipelineOptions(output_dir=output, slug="guide", license="MIT"))

    result = apply(operation)

    assert result.ok, result.errors
    assert result.state_diff == {"added": 1, "updated": 0, "removed": 0}
    assert (output / "rag" / "documents" / "guide.md").read_text(encoding="utf-8") == "# Guide\nApply me.\n"
    assert result.manifest["outcome"]["status"] == "succeeded"


def test_apply_does_not_reacquire_a_remote_corpus_while_holding_the_writer_lease(tmp_path: Path) -> None:
    requests = {"count": 0}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib callback name
            requests["count"] += 1
            if self.path in {"/robots.txt", "/sitemap.xml"}:
                self.send_response(404)
                self.end_headers()
                return
            body = (
                b"<html><body><h1>Guide</h1>"
                b"<p>This page contains enough stable documentation text for the bounded crawler.</p>"
                b"</body></html>"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        source = f"http://127.0.0.1:{server.server_port}/guide"
        output = tmp_path / "package"
        operation = plan(
            source,
            options=PipelineOptions(
                output_dir=output,
                slug="guide",
                license="MIT",
                allow_private_network=True,
                max_pages=1,
                max_depth=0,
            ),
        )
        planned_requests = requests["count"]

        result = apply(operation)

        assert result.ok, result.errors
        assert planned_requests > 0
        assert requests["count"] <= planned_requests * 2
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_validation_receipt_keeps_the_measured_phase_duration(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\n", encoding="utf-8")
    output = tmp_path / "package"

    result = run_pipeline(source, options=PipelineOptions(output_dir=output, slug="guide", license="MIT"))

    assert result.ok, result.errors
    checkpoints = json.loads((output / ".docops" / "checkpoints.json").read_text(encoding="utf-8"))
    assert checkpoints["phases"]["validate"]["duration_ms"] > 0


def test_plan_is_byte_for_byte_read_only_against_an_existing_package(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\nStable.\n", encoding="utf-8")
    output = tmp_path / "package"
    assert run_pipeline(source, options=PipelineOptions(output_dir=output, slug="guide", license="MIT")).ok
    before = {path.relative_to(output).as_posix(): path.read_bytes() for path in output.rglob("*") if path.is_file()}

    operation = plan(source, options=PipelineOptions(output_dir=output, slug="guide", license="MIT", mode="update"))

    after = {path.relative_to(output).as_posix(): path.read_bytes() for path in output.rglob("*") if path.is_file()}
    assert operation.state_diff == {"added": 0, "updated": 0, "removed": 0}
    assert before == after


def test_apply_rejects_a_plan_when_the_source_changes_after_planning(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    guide = source / "guide.md"
    guide.write_text("# Guide\nBefore.\n", encoding="utf-8")
    output = tmp_path / "package"
    assert run_pipeline(source, options=PipelineOptions(output_dir=output, slug="guide", license="MIT")).ok
    operation = plan(source, options=PipelineOptions(output_dir=output, slug="guide", license="MIT", mode="update"))
    guide.write_text("# Guide\nAfter.\n", encoding="utf-8")

    result = apply(operation)

    assert not result.ok
    assert result.outcome["code"] == "stale_plan"
    assert (output / "rag" / "documents" / "guide.md").read_text(encoding="utf-8") == "# Guide\nBefore.\n"


def test_explicit_create_refuses_to_replace_a_managed_package(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\nOriginal.\n", encoding="utf-8")
    output = tmp_path / "package"
    assert run_pipeline(
        source, options=PipelineOptions(output_dir=output, slug="guide", license="MIT", mode="create")
    ).ok
    before = (output / "rag" / "documents" / "guide.md").read_bytes()

    result = run_pipeline(
        source, options=PipelineOptions(output_dir=output, slug="guide", license="MIT", mode="create")
    )

    assert not result.ok
    assert result.outcome["code"] == "destination_exists"
    assert (output / "rag" / "documents" / "guide.md").read_bytes() == before


def test_update_accepts_a_legacy_manifest_without_contract_version(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    guide = source / "guide.md"
    guide.write_text("# Guide\nOriginal.\n", encoding="utf-8")
    output = tmp_path / "package"
    assert run_pipeline(source, options=PipelineOptions(output_dir=output, slug="guide", license="MIT")).ok

    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("contract_version")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert validate_package(output).ok
    guide.write_text("# Guide\nUpdated.\n", encoding="utf-8")

    operation = plan(source, options=PipelineOptions(output_dir=output, slug="guide", license="MIT", mode="update"))

    assert operation.blockers == ()
    result = apply(operation)
    assert result.ok, result.errors


def test_update_rejects_an_unmanaged_destination(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\n", encoding="utf-8")
    output = tmp_path / "unmanaged"
    output.mkdir()
    (output / "user-data.txt").write_text("keep", encoding="utf-8")

    result = run_pipeline(
        source, options=PipelineOptions(output_dir=output, slug="guide", license="MIT", mode="update")
    )

    assert not result.ok
    assert result.outcome["code"] == "destination_not_managed"
    assert (output / "user-data.txt").read_text(encoding="utf-8") == "keep"


def test_dry_run_reports_the_same_unmanaged_destination_blocker_as_run(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\n", encoding="utf-8")
    output = tmp_path / "unmanaged"
    output.mkdir()
    (output / "user-data.txt").write_text("keep", encoding="utf-8")

    operation = plan(source, options=PipelineOptions(output_dir=output, slug="guide", license="MIT", mode="dry-run"))

    assert any(blocker["code"] == "destination_not_managed" for blocker in operation.blockers)


def test_repeating_plan_is_deterministic_for_the_same_state(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\nStable.\n", encoding="utf-8")
    output = tmp_path / "package"
    options = PipelineOptions(output_dir=output, slug="guide", license="MIT")

    first = plan(source, options=options)
    second = plan(source, options=options)

    assert first.plan_hash == second.plan_hash
    assert first.to_dict() == second.to_dict()


def test_operation_plan_captures_an_immutable_request_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\n", encoding="utf-8")
    output = tmp_path / "package"
    options = PipelineOptions(output_dir=output, slug="guide", license="MIT")

    operation = plan(source, options=options)
    options.slug = "changed-after-plan"
    options.output_dir = tmp_path / "other-package"

    assert operation.request.options.slug == "guide"
    assert operation.request.options.output_dir == output.resolve()
    with pytest.raises(FrozenInstanceError):
        operation.request.options.slug = "mutated-plan"


def test_failed_post_promotion_validation_restores_the_previous_generation(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    guide = source / "guide.md"
    guide.write_text("# Guide\nBefore.\n", encoding="utf-8")
    output = tmp_path / "package"
    assert run_pipeline(source, options=PipelineOptions(output_dir=output, slug="guide", license="MIT")).ok
    active_before = {
        path.relative_to(output).as_posix(): path.read_bytes() for path in output.rglob("*") if path.is_file()
    }
    guide.write_text("# Guide\nAfter.\n", encoding="utf-8")
    operation = plan(source, options=PipelineOptions(output_dir=output, slug="guide", license="MIT", mode="update"))

    real_replace = storage.os.replace

    def fail_active_manifest(source_path, destination_path):
        if Path(destination_path).name == "manifest.json" and Path(destination_path).parent == output:
            raise OSError("fixture post-promotion filesystem failure")
        return real_replace(source_path, destination_path)

    monkeypatch.setattr(storage.os, "replace", fail_active_manifest)
    result = apply(operation)

    assert not result.ok
    assert result.outcome["phase"] == "promote"
    active_after = {
        path.relative_to(output).as_posix(): path.read_bytes() for path in output.rglob("*") if path.is_file()
    }
    assert active_after == active_before
    monkeypatch.undo()
    assert validate_package(output).ok


def test_separate_reader_never_observes_an_invalid_generation_during_update(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    guide = source / "guide.md"
    guide.write_text("# Guide\nBefore.\n", encoding="utf-8")
    output = tmp_path / "package"
    options = PipelineOptions(output_dir=output, slug="guide", license="MIT")
    assert run_pipeline(source, options=options).ok

    guide.write_text("# Guide\nAfter.\n", encoding="utf-8")
    operation = plan(source, options=PipelineOptions(output_dir=output, slug="guide", license="MIT", mode="update"))
    stop = tmp_path / "reader-stop"
    failure = tmp_path / "reader-failure.json"
    reader_code = textwrap.dedent(
        """
        import json
        import sys
        import time
        from pathlib import Path

        import docops

        root = Path(sys.argv[1])
        stop = Path(sys.argv[2])
        failure = Path(sys.argv[3])
        while not stop.exists():
            report = docops.inspect(root)
            active = report.get("active", {})
            validation = active.get("validation")
            if not report.get("managed") or not isinstance(validation, dict) or validation.get("ok") is not True:
                failure.write_text(json.dumps(report), encoding="utf-8")
                break
            time.sleep(0.001)
        """,
    )
    reader = subprocess.Popen(
        [sys.executable, "-c", reader_code, str(output), str(stop), str(failure)],
        cwd=str(Path.cwd()),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        result = apply(operation)
    finally:
        stop.write_text("stop", encoding="utf-8")
    stdout, stderr = reader.communicate(timeout=10)

    assert result.ok, result.errors
    assert reader.returncode == 0, stderr or stdout
    assert not failure.exists(), failure.read_text(encoding="utf-8") if failure.exists() else ""


def test_cleanup_preserves_active_and_resumable_residue_but_removes_expired_items(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\n", encoding="utf-8")
    output = tmp_path / "package"
    assert run_pipeline(source, options=PipelineOptions(output_dir=output, slug="guide", license="MIT")).ok
    operation = plan(source, options=PipelineOptions(output_dir=output, slug="guide", license="MIT", mode="update"))

    resumable = output.parent / f".{output.name}.staging-resumable"
    (resumable / ".docops").mkdir(parents=True)
    (resumable / ".docops" / "plan.json").write_text(json.dumps(operation.to_dict()), encoding="utf-8")
    orphan = output.parent / f".{output.name}.staging-orphan"
    orphan.mkdir()
    backup = output.parent / f".{output.name}.backup-old"
    backup.mkdir()
    (backup / "old.txt").write_text("old", encoding="utf-8")
    attempts = output.parent / f".{output.name}.docops-attempts"
    attempts.mkdir(exist_ok=True)
    attempt = attempts / "attempt-old.json"
    attempt.write_text(json.dumps({"schema_version": 1, "attempt_id": "attempt-old"}), encoding="utf-8")
    old_time = 1.0
    os.utime(backup, (old_time, old_time))
    os.utime(attempt, (old_time, old_time))

    lease = PackageLease(output)
    lease.acquire()
    try:
        busy = docops.cleanup(output)
        assert not busy["ok"]
        assert busy["code"] == "writer_busy"
        assert resumable.is_dir()
    finally:
        lease.release()

    result = docops.cleanup(output, retention_seconds=1, keep_attempts=0)

    assert result["ok"], result
    assert resumable.is_dir()
    assert not orphan.exists()
    assert not backup.exists()
    assert not attempt.exists()
    assert docops.inspect(output)["active"]["validation"]["ok"] is True


def test_resume_ignores_staging_generation_with_symbolic_links(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    guide = source / "guide.md"
    guide.write_text("# Guide\nBefore.\n", encoding="utf-8")
    output = tmp_path / "package"
    assert run_pipeline(source, options=PipelineOptions(output_dir=output, slug="guide", license="MIT")).ok
    active_before = (output / "rag" / "documents" / "guide.md").read_bytes()
    guide.write_text("# Guide\nAfter.\n", encoding="utf-8")
    operation = plan(source, options=PipelineOptions(output_dir=output, slug="guide", license="MIT", mode="update"))

    outside = tmp_path / "outside"
    (outside / "documents").mkdir(parents=True)
    sentinel = outside / "documents" / "sentinel.txt"
    sentinel.write_text("must remain outside the package", encoding="utf-8")
    staging = output.parent / f".{output.name}.staging-malicious"
    (staging / ".docops").mkdir(parents=True)
    (staging / ".docops" / "plan.json").write_text(json.dumps(operation.to_dict()), encoding="utf-8")
    try:
        (staging / "rag").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        (staging / "rag").write_text("malformed staging path", encoding="utf-8")

    result = apply(operation)

    if (staging / "rag").is_symlink():
        assert result.ok, result.errors
    else:
        assert not result.ok
        assert (output / "rag" / "documents" / "guide.md").read_bytes() == active_before
    assert sentinel.read_text(encoding="utf-8") == "must remain outside the package"


def test_apply_returns_a_terminal_result_when_output_parent_is_not_a_directory(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\n", encoding="utf-8")
    parent = tmp_path / "parent-file"
    parent.write_text("not a directory", encoding="utf-8")
    output = parent / "package"

    operation = plan(source, options=PipelineOptions(output_dir=output, slug="guide", license="MIT"))

    result = apply(operation)

    assert not result.ok
    assert result.outcome["status"] == "failed"
    assert result.outcome["phase"] == "prepare"
