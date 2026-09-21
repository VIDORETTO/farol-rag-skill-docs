from __future__ import annotations

import json
import subprocess

from scripts import run_ocr_profile


def _versions(monkeypatch) -> None:
    monkeypatch.setattr(
        run_ocr_profile.importlib.metadata,
        "version",
        lambda package: run_ocr_profile.EXPECTED_VERSIONS[package],
    )


def test_ocr_profile_fails_closed_when_dependencies_are_missing(monkeypatch, capsys) -> None:
    def missing(_package: str) -> str:
        raise run_ocr_profile.importlib.metadata.PackageNotFoundError

    monkeypatch.setattr(run_ocr_profile.importlib.metadata, "version", missing)

    assert run_ocr_profile.main(["--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "blocked"
    assert payload["reason"] == "dependencies_missing"


def test_ocr_profile_passes_only_an_executed_integration(monkeypatch, capsys) -> None:
    _versions(monkeypatch)
    monkeypatch.setattr(
        run_ocr_profile.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, stdout="1 passed in 1.0s\n", stderr=""),
    )

    assert run_ocr_profile.main(["--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "passed"
    assert payload["integration"]["passed"] == 1


def test_ocr_profile_does_not_promote_a_skipped_contract(monkeypatch, capsys) -> None:
    _versions(monkeypatch)
    monkeypatch.setattr(
        run_ocr_profile.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, stdout="1 skipped in 0.1s\n", stderr=""),
    )

    assert run_ocr_profile.main(["--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "not_run"
