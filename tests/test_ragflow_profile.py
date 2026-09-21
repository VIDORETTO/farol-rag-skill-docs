from __future__ import annotations

import json
import subprocess
import sys
from types import SimpleNamespace

from scripts import run_ragflow_profile


def test_ragflow_profile_fails_closed_when_external_inputs_are_missing(monkeypatch, capsys) -> None:
    for name in (
        "DOCOPS_RAGFLOW_ENDPOINT",
        "DOCOPS_RAGFLOW_TOKEN",
        "DOCOPS_RAGFLOW_IMAGE_DIGEST",
        "DOCOPS_RAGFLOW_SDK_VERSION",
    ):
        monkeypatch.delenv(name, raising=False)

    assert run_ragflow_profile.main(["--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["status"] == "blocked"
    assert payload["reason"] == "missing_external_inputs"
    assert "DOCOPS_RAGFLOW_TOKEN" in payload["missing"]
    assert payload["stdout_tail"] == ""
    assert payload["stderr_tail"] == ""


def test_ragflow_profile_rejects_an_unpinned_image_before_importing_sdk(monkeypatch, capsys) -> None:
    monkeypatch.setenv("DOCOPS_RAGFLOW_ENDPOINT", "https://ragflow.example.test")
    monkeypatch.setenv("DOCOPS_RAGFLOW_TOKEN", "configured")
    monkeypatch.setenv("DOCOPS_RAGFLOW_IMAGE_DIGEST", "ragflow:0.27.2")
    monkeypatch.setenv("DOCOPS_RAGFLOW_SDK_VERSION", "0.27.2")

    assert run_ragflow_profile.main(["--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["reason"] == "image_digest_unpinned"


def _configure_valid_environment(monkeypatch) -> dict[str, str]:
    values = {
        "DOCOPS_RAGFLOW_ENDPOINT": "https://ragflow.example.test/api",
        "DOCOPS_RAGFLOW_TOKEN": "token-for-test-only",
        "DOCOPS_RAGFLOW_IMAGE_DIGEST": "registry.example/ragflow@sha256:" + "a" * 64,
        "DOCOPS_RAGFLOW_SDK_VERSION": "0.27.2",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setitem(sys.modules, "ragflow_sdk", SimpleNamespace(__version__="0.27.2"))
    return values


def _mock_pytest(
    monkeypatch,
    *,
    returncode: int,
    stdout: str,
    stderr: str = "",
) -> list[tuple[list[str], dict[str, object]]]:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(command, **kwargs):
        calls.append((list(command), kwargs))
        return subprocess.CompletedProcess(command, returncode, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(run_ragflow_profile.subprocess, "run", fake_run)
    return calls


def test_ragflow_profile_does_not_turn_only_skipped_integration_into_passed(monkeypatch, capsys) -> None:
    _configure_valid_environment(monkeypatch)
    calls = _mock_pytest(
        monkeypatch,
        returncode=0,
        stdout=(
            "s                                                                        [100%]\n"
            "SKIPPED [1] tests/spikes/test_ragflow_contract.py:23: "
            "not_run: RAGFlow integration is opt-in\n"
            "1 skipped in 0.10s\n"
        ),
        stderr="integration subprocess completed without executing a test\n",
    )

    assert run_ragflow_profile.main(["--json"]) == 1
    payload = json.loads(capsys.readouterr().out)

    assert payload["ok"] is False
    assert payload["status"] == "not_run"
    assert payload["reason"] == "integration_not_run"
    assert "not_run" in payload["stdout_tail"]
    assert "without executing" in payload["stderr_tail"]
    command, kwargs = calls[0]
    marker_index = command.index("-m", command.index("-m") + 1)
    assert command[marker_index : marker_index + 2] == ["-m", "integration"]
    assert kwargs["env"]["DOCOPS_RAGFLOW_INTEGRATION"] == "1"


def test_ragflow_profile_does_not_turn_mixed_pass_and_skip_into_passed(monkeypatch, capsys) -> None:
    _configure_valid_environment(monkeypatch)
    _mock_pytest(monkeypatch, returncode=0, stdout="1 passed, 1 skipped in 0.10s\n")

    assert run_ragflow_profile.main(["--json"]) == 1
    payload = json.loads(capsys.readouterr().out)

    assert payload["ok"] is False
    assert payload["status"] == "not_run"
    assert payload["reason"] == "integration_not_run"


def test_ragflow_profile_preserves_blocked_subprocess_result_and_evidence(monkeypatch, capsys) -> None:
    _configure_valid_environment(monkeypatch)
    _mock_pytest(
        monkeypatch,
        returncode=0,
        stdout="status=blocked: remote RAGFlow is unavailable\n",
        stderr="blocked: integration prerequisites are not ready\n",
    )

    assert run_ragflow_profile.main(["--json"]) == 1
    payload = json.loads(capsys.readouterr().out)

    assert payload["ok"] is False
    assert payload["status"] == "blocked"
    assert payload["reason"] == "integration_blocked"
    assert "status=blocked" in payload["stdout_tail"]
    assert "blocked:" in payload["stderr_tail"]


def test_ragflow_profile_passes_only_when_an_integration_test_passes(monkeypatch, capsys) -> None:
    _configure_valid_environment(monkeypatch)
    _mock_pytest(monkeypatch, returncode=0, stdout="1 passed in 0.10s\n")

    assert run_ragflow_profile.main(["--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["ok"] is True
    assert payload["status"] == "passed"
    assert payload["reason"] is None
    assert payload["integration"]["passed"] == 1
    assert payload["integration"]["executed"] == 1


def test_ragflow_profile_keeps_real_subprocess_failure_failed(monkeypatch, capsys) -> None:
    _configure_valid_environment(monkeypatch)
    _mock_pytest(
        monkeypatch,
        returncode=1,
        stdout="F                                                                        [100%]\n1 failed in 0.10s\n",
        stderr="AssertionError: RAGFlow contract mismatch\n",
    )

    assert run_ragflow_profile.main(["--json"]) == 1
    payload = json.loads(capsys.readouterr().out)

    assert payload["ok"] is False
    assert payload["status"] == "failed"
    assert payload["reason"] == "contract_test_failed"
    assert "1 failed" in payload["stdout_tail"]
    assert "contract mismatch" in payload["stderr_tail"]


def test_ragflow_profile_redacts_all_external_values_in_subprocess_evidence(monkeypatch, capsys) -> None:
    values = _configure_valid_environment(monkeypatch)
    _mock_pytest(
        monkeypatch,
        returncode=0,
        stdout=(
            f"status=blocked endpoint={values['DOCOPS_RAGFLOW_ENDPOINT']} "
            f"digest={values['DOCOPS_RAGFLOW_IMAGE_DIGEST']}\n"
        ),
        stderr=(f"token={values['DOCOPS_RAGFLOW_TOKEN']} endpoint={values['DOCOPS_RAGFLOW_ENDPOINT']}\n"),
    )

    assert run_ragflow_profile.main(["--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    serialized = json.dumps(payload, ensure_ascii=False)

    for value in (
        values["DOCOPS_RAGFLOW_ENDPOINT"],
        values["DOCOPS_RAGFLOW_TOKEN"],
        values["DOCOPS_RAGFLOW_IMAGE_DIGEST"],
    ):
        assert value not in serialized
    assert "<redacted>" in payload["stdout_tail"]
    assert "<redacted>" in payload["stderr_tail"]


def test_ragflow_profile_reports_a_bounded_subprocess_timeout(monkeypatch, capsys) -> None:
    _configure_valid_environment(monkeypatch)
    calls: list[dict[str, object]] = []

    def fake_run(command, **kwargs):
        calls.append(kwargs)
        raise subprocess.TimeoutExpired(
            command,
            timeout=7,
            output="partial integration output",
            stderr="partial integration error",
        )

    monkeypatch.setattr(run_ragflow_profile.subprocess, "run", fake_run)

    assert run_ragflow_profile.main(["--json", "--timeout", "7"]) == 124
    payload = json.loads(capsys.readouterr().out)

    assert payload["ok"] is False
    assert payload["status"] == "failed"
    assert payload["reason"] == "integration_timeout"
    assert payload["timeout_seconds"] == 7.0
    assert "partial integration output" in payload["stdout_tail"]
    assert "partial integration error" in payload["stderr_tail"]
    assert calls[0]["timeout"] == 7.0


def test_ragflow_profile_rejects_non_finite_timeout(monkeypatch, capsys) -> None:
    _configure_valid_environment(monkeypatch)

    assert run_ragflow_profile.main(["--json", "--timeout", "nan"]) == 2
    payload = json.loads(capsys.readouterr().out)

    assert payload["ok"] is False
    assert payload["status"] == "blocked"
    assert payload["reason"] == "timeout_invalid"


def test_ragflow_profile_ignores_unstructured_blocked_word(monkeypatch, capsys) -> None:
    _configure_valid_environment(monkeypatch)
    _mock_pytest(
        monkeypatch,
        returncode=0,
        stdout="1 passed in 0.10s\n",
        stderr="test name contains the word blocked but completed normally\n",
    )

    assert run_ragflow_profile.main(["--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "passed"
