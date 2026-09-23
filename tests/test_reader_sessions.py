from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import docops

ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "docops", *args, "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def _package_fixture(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\nPinned reader facts.\n", encoding="utf-8")
    output = tmp_path / "package"
    request = docops.OperationRequest(
        source,
        docops.OperationOptions(
            output_dir=output,
            source_root=source.parent,
            slug="reader-guide",
            license="MIT",
            mode="run",
        ),
    )
    result = docops.apply(docops.plan(request))
    assert result.ok, result.errors
    return source, output


def test_reader_session_pins_generation_and_refuses_writer_tools(tmp_path: Path) -> None:
    _source, package = _package_fixture(tmp_path)

    created = _run_cli(
        "reader-session",
        "--package",
        str(package),
        "--adapter",
        "memory",
        "--now",
        "2026-09-05T13:00:00Z",
    )
    assert created.returncode == 0, created.stdout + created.stderr
    session = json.loads(created.stdout)
    assert session["ok"] is True
    assert session["permissions"]["read_only"] is True
    assert session["generation"]["release_id"].startswith("release-")

    queried = _run_cli(
        "reader-query",
        "--package",
        str(package),
        "--session",
        session["session_id"],
        "--tool",
        "search_knowledge",
        "--query",
        "Pinned reader facts",
        "--adapter",
        "memory",
        "--now",
        "2026-09-05T13:01:00Z",
    )
    assert queried.returncode == 0, queried.stdout + queried.stderr
    result = json.loads(queried.stdout)
    assert result["generation"] == session["generation"]
    assert result["results"]

    denied = _run_cli(
        "reader-query",
        "--package",
        str(package),
        "--session",
        session["session_id"],
        "--tool",
        "add_document",
        "--query",
        "should be refused",
        "--adapter",
        "memory",
        "--now",
        "2026-09-05T13:01:00Z",
    )
    assert denied.returncode == 1
    assert json.loads(denied.stdout)["errors"][0]["code"] == "reader_tool_denied"


def test_reader_session_pins_an_explicit_rag_snapshot(tmp_path: Path) -> None:
    _source, package = _package_fixture(tmp_path)
    snapshot_path = tmp_path / "reader-snapshot.json"
    snapshot_result = _run_cli(
        "rag-snapshot",
        "--package",
        str(package),
        "--backend",
        "memory",
        "--snapshot-out",
        str(snapshot_path),
    )
    assert snapshot_result.returncode == 0, snapshot_result.stdout + snapshot_result.stderr
    snapshot = json.loads(snapshot_result.stdout)["snapshot"]

    created = _run_cli(
        "reader-session",
        "--package",
        str(package),
        "--adapter",
        "memory",
        "--snapshot",
        str(snapshot_path),
        "--now",
        "2026-09-05T13:00:00Z",
    )

    assert created.returncode == 0, created.stdout + created.stderr
    session = json.loads(created.stdout)
    assert session["snapshot"]["snapshot_id"] == snapshot["snapshot_id"]
    assert session["snapshot"]["corpus_hash"] == snapshot["corpus_hash"]

    queried = _run_cli(
        "reader-query",
        "--package",
        str(package),
        "--session",
        session["session_id"],
        "--tool",
        "search_knowledge",
        "--query",
        "Pinned reader facts",
        "--adapter",
        "memory",
        "--now",
        "2026-09-05T13:01:00Z",
    )
    assert queried.returncode == 0, queried.stdout + queried.stderr
    assert json.loads(queried.stdout)["snapshot"]["snapshot_id"] == snapshot["snapshot_id"]


def test_new_reader_session_gets_new_generation_and_old_session_does_not_follow_it(tmp_path: Path) -> None:
    source, package = _package_fixture(tmp_path)
    first = json.loads(
        _run_cli(
            "reader-session",
            "--package",
            str(package),
            "--adapter",
            "memory",
            "--now",
            "2026-09-05T13:00:00Z",
        ).stdout
    )

    source.joinpath("guide.md").write_text("# Guide\nA newer generation.\n", encoding="utf-8")
    updated = docops.apply(
        docops.plan(
            docops.OperationRequest(
                source,
                docops.OperationOptions(
                    output_dir=package,
                    source_root=source.parent,
                    slug="reader-guide",
                    license="MIT",
                    mode="update",
                ),
            )
        )
    )
    assert updated.ok, updated.errors

    second_result = _run_cli(
        "reader-session",
        "--package",
        str(package),
        "--adapter",
        "memory",
        "--now",
        "2026-09-05T13:01:00Z",
    )
    assert second_result.returncode == 0, second_result.stdout + second_result.stderr
    second = json.loads(second_result.stdout)
    assert second["generation"]["release_id"] != first["generation"]["release_id"]

    old_query = _run_cli(
        "reader-query",
        "--package",
        str(package),
        "--session",
        first["session_id"],
        "--tool",
        "search_knowledge",
        "--query",
        "Pinned reader facts",
        "--adapter",
        "memory",
        "--now",
        "2026-09-05T13:01:00Z",
    )
    assert old_query.returncode == 1
    assert json.loads(old_query.stdout)["errors"][0]["code"] == "reader_generation_unavailable"


def test_reader_cache_is_generation_bound_and_revocation_wins(tmp_path: Path) -> None:
    _source, package = _package_fixture(tmp_path)
    created = json.loads(
        _run_cli(
            "reader-session",
            "--package",
            str(package),
            "--adapter",
            "memory",
            "--now",
            "2026-09-05T13:00:00Z",
        ).stdout
    )
    first = _run_cli(
        "reader-query",
        "--package",
        str(package),
        "--session",
        created["session_id"],
        "--tool",
        "search_knowledge",
        "--query",
        "Pinned reader facts",
        "--adapter",
        "memory",
        "--now",
        "2026-09-05T13:01:00Z",
    )
    assert first.returncode == 0
    assert json.loads(first.stdout)["cache_hit"] is False

    cached = _run_cli(
        "reader-query",
        "--package",
        str(package),
        "--session",
        created["session_id"],
        "--tool",
        "search_knowledge",
        "--query",
        "Pinned reader facts",
        "--adapter",
        "memory",
        "--now",
        "2026-09-05T13:01:00Z",
    )
    assert cached.returncode == 0
    assert json.loads(cached.stdout)["cache_hit"] is True

    revoked = _run_cli(
        "reader-session-revoke",
        "--package",
        str(package),
        "--session",
        created["session_id"],
        "--now",
        "2026-09-05T13:02:00Z",
    )
    assert revoked.returncode == 0

    after_revoke = _run_cli(
        "reader-query",
        "--package",
        str(package),
        "--session",
        created["session_id"],
        "--tool",
        "search_knowledge",
        "--query",
        "Pinned reader facts",
        "--adapter",
        "memory",
        "--now",
        "2026-09-05T13:03:00Z",
    )
    assert after_revoke.returncode == 1
    assert json.loads(after_revoke.stdout)["errors"][0]["code"] == "reader_session_revoked"


def test_non_memory_reader_is_rejected_after_legacy_contraction(tmp_path: Path) -> None:
    _source, package = _package_fixture(tmp_path)
    harness_path = package / "harness.json"
    harness = json.loads(harness_path.read_text(encoding="utf-8"))
    harness["backend"]["name"] = "other-backend"
    harness["backend"]["capabilities"] = ["query", "discard"]
    harness_path.write_text(json.dumps(harness), encoding="utf-8")

    result = _run_cli(
        "reader-session",
        "--package",
        str(package),
        "--adapter",
        "mcp",
        "--now",
        "2026-09-05T13:00:00Z",
    )
    assert result.returncode == 2
    assert "invalid choice" in result.stderr


def test_reader_refuses_a_package_with_a_revoked_rag_source(tmp_path: Path) -> None:
    _source, package = _package_fixture(tmp_path)
    sources_path = package / "rag" / "sources.json"
    sources = json.loads(sources_path.read_text(encoding="utf-8"))
    sources["sources"][0]["revoked"] = True
    sources_path.write_text(json.dumps(sources), encoding="utf-8")

    result = _run_cli(
        "reader-session",
        "--package",
        str(package),
        "--adapter",
        "memory",
        "--now",
        "2026-09-05T13:00:00Z",
    )

    assert result.returncode == 1
    assert json.loads(result.stdout)["errors"][0]["code"] == "reader_snapshot_revoked"


def test_reader_snapshot_rejects_a_revoked_learning_derivative(tmp_path: Path) -> None:
    _source, package = _package_fixture(tmp_path)
    derived = package / "rag" / "documents" / "learning" / "revoked-fact.md"
    derived.parent.mkdir(parents=True, exist_ok=True)
    derived.write_text("derived claim\n", encoding="utf-8")

    created = _run_cli(
        "reader-session",
        "--package",
        str(package),
        "--adapter",
        "memory",
        "--now",
        "2026-09-05T13:00:00Z",
    )
    assert created.returncode == 0, created.stdout + created.stderr
    session = json.loads(created.stdout)

    tombstones = package / ".docops" / "learning" / "tombstones.json"
    tombstones.parent.mkdir(parents=True, exist_ok=True)
    tombstones.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "tombstones": [
                    {
                        "schema_version": 1,
                        "proposal_id": "revoked-fact",
                        "path": "rag/documents/learning/revoked-fact.md",
                        "revoked_at": "2026-09-05T13:01:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    queried = _run_cli(
        "reader-query",
        "--package",
        str(package),
        "--session",
        session["session_id"],
        "--tool",
        "search_knowledge",
        "--query",
        "derived claim",
        "--adapter",
        "memory",
        "--now",
        "2026-09-05T13:02:00Z",
    )

    assert queried.returncode == 1
    assert json.loads(queried.stdout)["errors"][0]["code"] == "reader_snapshot_revoked"
