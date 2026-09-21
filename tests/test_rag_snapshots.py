# seam-scope: implementation-infrastructure (RAG snapshot public seams)
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from docops.rag_snapshots import package_rag_config_text


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "docops", *args, "--json"],
        capture_output=True,
        text=True,
        check=False,
    )


def _package_fixture(tmp_path: Path, *, count: int = 100) -> Path:
    package = tmp_path / "package"
    documents = package / "rag" / "documents"
    documents.mkdir(parents=True)
    (package / "config.yaml").write_text(package_rag_config_text(), encoding="utf-8")
    (package / "manifest.json").write_text(
        json.dumps({"package_id": "snapshot-fixture"}, ensure_ascii=False),
        encoding="utf-8",
    )
    for index in range(count):
        (documents / f"doc-{index:03d}.md").write_text(
            f"doc-{index:03d}-aaaaaaaa\n",
            encoding="utf-8",
        )
    return package


def test_snapshot_reuses_unchanged_documents_and_detects_same_stat_change(tmp_path: Path) -> None:
    package = _package_fixture(tmp_path)
    previous = tmp_path / "previous-snapshot.json"

    first = _run_cli(
        "rag-snapshot",
        "--package",
        str(package),
        "--backend",
        "memory",
        "--supports-incremental",
        "--snapshot-out",
        str(previous),
    )
    assert first.returncode == 0, first.stdout + first.stderr
    before = (package / "rag" / "documents" / "doc-042.md").stat()
    (package / "rag" / "documents" / "doc-042.md").write_text(
        "doc-042-bbbbbbbb\n",
        encoding="utf-8",
    )
    os.utime(package / "rag" / "documents" / "doc-042.md", ns=(before.st_atime_ns, before.st_mtime_ns))

    second = _run_cli(
        "rag-snapshot",
        "--package",
        str(package),
        "--previous",
        str(previous),
        "--backend",
        "memory",
        "--supports-incremental",
    )

    assert second.returncode == 0, second.stdout + second.stderr
    report = json.loads(second.stdout)
    assert report["plan"]["mode"] == "incremental"
    assert report["plan"]["reused_count"] == 99
    assert report["plan"]["changed_count"] == 1
    assert report["plan"]["changed_paths"] == ["doc-042.md"]
    assert report["plan"]["logical_stats"]["current_documents"] == 100


def test_embedding_change_forces_full_rebuild(tmp_path: Path) -> None:
    package = _package_fixture(tmp_path, count=2)
    previous = tmp_path / "previous-snapshot.json"

    first = _run_cli(
        "rag-snapshot",
        "--package",
        str(package),
        "--backend",
        "memory",
        "--supports-incremental",
        "--snapshot-out",
        str(previous),
    )
    assert first.returncode == 0, first.stdout + first.stderr
    config = package / "config.yaml"
    config.write_text(
        config.read_text(encoding="utf-8").replace("profile: compact", "profile: multilingual"), encoding="utf-8"
    )

    second = _run_cli(
        "rag-snapshot",
        "--package",
        str(package),
        "--previous",
        str(previous),
        "--backend",
        "memory",
        "--supports-incremental",
    )

    assert second.returncode == 0, second.stdout + second.stderr
    report = json.loads(second.stdout)
    assert report["plan"]["mode"] == "full_rebuild"
    assert report["plan"]["reason"] == "embedding_changed"
    assert report["plan"]["reused_count"] == 0


def test_backend_without_incremental_capability_declares_rebuild(tmp_path: Path) -> None:
    package = _package_fixture(tmp_path, count=3)
    previous = tmp_path / "previous-snapshot.json"

    first = _run_cli(
        "rag-snapshot",
        "--package",
        str(package),
        "--backend",
        "legacy",
        "--supports-incremental",
        "--snapshot-out",
        str(previous),
    )
    assert first.returncode == 0, first.stdout + first.stderr

    second = _run_cli(
        "rag-snapshot",
        "--package",
        str(package),
        "--previous",
        str(previous),
        "--backend",
        "legacy",
    )

    assert second.returncode == 0, second.stdout + second.stderr
    report = json.loads(second.stdout)
    assert report["plan"]["mode"] == "full_rebuild"
    assert report["plan"]["reason"] == "backend_incremental_unsupported"
    assert report["plan"]["reused_count"] == 0


def test_invalid_snapshot_fails_closed_and_preserves_active_package(tmp_path: Path) -> None:
    package = _package_fixture(tmp_path, count=1)
    active_document = package / "rag" / "documents" / "doc-000.md"
    before = active_document.read_bytes()
    previous = tmp_path / "broken-snapshot.json"
    previous.write_text("{not-json", encoding="utf-8")

    result = _run_cli(
        "rag-snapshot",
        "--package",
        str(package),
        "--previous",
        str(previous),
        "--backend",
        "memory",
        "--supports-incremental",
    )

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["ok"] is False
    assert report["active_preserved"] is True
    assert report["error"]["code"] == "rag_snapshot_invalid"
    assert active_document.read_bytes() == before


def test_snapshot_report_can_verify_search_on_the_current_package(tmp_path: Path) -> None:
    package = _package_fixture(tmp_path, count=2)

    result = _run_cli(
        "rag-snapshot",
        "--package",
        str(package),
        "--backend",
        "memory",
        "--supports-incremental",
        "--verify-query",
        "doc-001",
        "--verify-adapter",
        "memory",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["verification"]["ok"] is True
    assert report["verification"]["result_count"] >= 1
    assert "doc-001.md" in report["verification"]["top_sources"]


def test_snapshot_records_full_compatibility_identity_and_rejects_artifact_reuse(tmp_path: Path) -> None:
    package = _package_fixture(tmp_path, count=2)
    data_dir = package / "rag" / "data"
    data_dir.mkdir()
    (data_dir / "backend.bin").write_bytes(b"first-index")
    previous = tmp_path / "previous-snapshot.json"

    first = _run_cli(
        "rag-snapshot",
        "--package",
        str(package),
        "--backend",
        "memory",
        "--supports-incremental",
        "--snapshot-out",
        str(previous),
    )
    assert first.returncode == 0, first.stdout + first.stderr
    snapshot = json.loads(first.stdout)["snapshot"]
    assert snapshot["release"]["release_id"]
    assert snapshot["corpus_hash"]
    assert snapshot["embedding"]["profile"] == "compact"
    assert "model" in snapshot and "configuration" in snapshot and "artifacts" in snapshot
    assert snapshot["configuration"]["redacted"] is True
    assert "rag/data/backend.bin" in snapshot["artifacts"]["files"]

    (data_dir / "backend.bin").write_bytes(b"second-index")
    second = _run_cli(
        "rag-snapshot",
        "--package",
        str(package),
        "--previous",
        str(previous),
        "--backend",
        "memory",
        "--supports-incremental",
    )

    assert second.returncode == 0, second.stdout + second.stderr
    report = json.loads(second.stdout)
    assert report["plan"]["mode"] == "full_rebuild"
    assert report["plan"]["reason"] == "artifacts_changed"
    assert report["plan"]["reused_count"] == 0
