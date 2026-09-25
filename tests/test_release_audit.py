# seam-scope: implementation-infrastructure (release policy unit tests)
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from docops.release_audit import audit_release


def test_release_audit_rejects_prohibited_runtime_artifacts_and_secrets(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("safe", encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "index.bin").write_bytes(b"runtime")
    secret = "sk-" + "1234567890abcdef1234567890"
    (tmp_path / "config.yaml").write_text(f"api_key: {secret}\n", encoding="utf-8")

    result = audit_release(tmp_path)

    assert not result.ok
    codes = {finding["code"] for finding in result.findings}
    assert "prohibited_artifact" in codes
    assert "secret_like_value" in codes


def test_release_audit_accepts_synthetic_fixture_and_token_placeholder(tmp_path: Path) -> None:
    (tmp_path / "documents" / "fixtures").mkdir(parents=True)
    (tmp_path / "documents" / "fixtures" / "guide.md").write_text(
        "# Fixture\nUse a placeholder such as REPLACE_WITH_A_TOKEN.", encoding="utf-8"
    )
    (tmp_path / "config.example.yaml").write_text(
        'bearer_token: "REPLACE_WITH_A_RANDOM_TOKEN_OF_AT_LEAST_16_CHARACTERS"\n', encoding="utf-8"
    )

    result = audit_release(tmp_path)

    assert result.ok, result.findings


def test_release_audit_rejects_json_escaped_windows_author_paths(tmp_path: Path) -> None:
    escaped_path = "C:" + "\\\\" + "Users" + "\\\\" + "Author" + "\\\\" + "Documents" + "\\\\" + "docs"
    (tmp_path / "manifest.json").write_text(
        '{"source": "' + escaped_path + '"}',
        encoding="utf-8",
    )

    result = audit_release(tmp_path)

    assert not result.ok
    assert any(finding["code"] == "author_path" for finding in result.findings)


def test_tracked_only_audit_fails_without_a_git_index(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("safe", encoding="utf-8")

    result = audit_release(tmp_path, tracked_only=True)

    assert not result.ok
    assert any(finding["code"] == "git_index_unavailable" for finding in result.findings)


def test_candidate_audit_ignores_deleted_tracked_files_and_rejects_an_empty_tree(tmp_path: Path) -> None:
    source = tmp_path / "README.md"
    source.write_text("candidate source\n", encoding="utf-8")
    subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True)
    source.unlink()

    result = audit_release(tmp_path, candidate=True)

    assert result.scanned_files == 0
    assert any(finding["code"] == "candidate_empty" for finding in result.findings)
    assert not any(finding["code"] == "candidate_file_missing" for finding in result.findings)


def test_tracked_candidate_audit_rejects_forced_added_nested_binary_before_decoding(tmp_path: Path) -> None:
    (tmp_path / "nested" / "data").mkdir(parents=True)
    prohibited = tmp_path / "nested" / "data" / "index.bin"
    prohibited.write_bytes(b"\\x00\\xffprivate-index")
    subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-f", "nested/data/index.bin"], cwd=tmp_path, check=True)

    result = audit_release(tmp_path, tracked_only=True)

    assert not result.ok
    assert any(
        finding["code"] == "prohibited_artifact" and finding["path"] == "nested/data/index.bin"
        for finding in result.findings
    )


def test_tracked_candidate_audit_rejects_nested_private_paths_and_structured_bearer_canary(tmp_path: Path) -> None:
    canary = "canary-" + "bearer-token-value-1234567890"
    files = {
        "vendor/data/index.bin": b"private index",
        "vendor/models_cache/model.bin": b"private model",
        "vendor/.docops/receipt.json": b"private receipt",
        "vendor/documents/acquired.md": b"acquired corpus",
        "vendor/config/network.yaml": b"transport: http\n",
        "vendor/settings.json": ('{"bearer_token": "' + canary + '"}').encode(),
    }
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-f", *files], cwd=tmp_path, check=True)

    result = audit_release(tmp_path, tracked_only=True)
    report = result.to_json()

    assert not result.ok
    assert sum(finding["code"] == "prohibited_artifact" for finding in result.findings) >= 5
    assert any(finding["code"] == "secret_like_value" for finding in result.findings)
    assert canary not in report


def test_candidate_cli_audits_tracked_and_new_public_files(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("safe", encoding="utf-8")
    (tmp_path / "new-module.py").write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True)

    completed = subprocess.run(
        [sys.executable, "scripts/audit_release.py", "--root", str(tmp_path), "--candidate", "--json"],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["candidate"] is True
    assert payload["scanned_files"] == 2
