# seam-scope: implementation-infrastructure (doctor unit tests)
from __future__ import annotations

from pathlib import Path

import pytest

from docops.doctor import discover_python, run_doctor


def test_discover_python_prefers_project_virtualenv_without_platform_assumptions(
    tmp_path: Path,
) -> None:
    executable = tmp_path / ".venv" / "bin" / "python"
    executable.parent.mkdir(parents=True)
    executable.touch()

    result = discover_python(tmp_path, environ={})

    assert result.path == executable
    assert result.source == "project-venv"


def test_doctor_reports_portable_capabilities_as_json_ready_data(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='consulta-documentacao'\n", encoding="utf-8")
    (tmp_path / "requirements.lock").write_text("# fixture\n", encoding="utf-8")

    report = run_doctor(tmp_path, environ={"DOCOPS_SKIP_RAG": "1"})

    assert report.ok
    payload = report.to_dict()
    assert payload["schema_version"] == 1
    assert payload["project_root"] == "."
    assert payload["checks"]["project_metadata"]["path"] == "pyproject.toml"
    assert payload["capabilities"]["rag"] == "skipped"
    assert payload["checks"]["extractors"]["status"] == "available"
    assert "legacy-text" in payload["capabilities"]["extractors"]
    assert payload["checks"]["python"]["ok"] is True


def test_doctor_includes_the_transport_security_audit(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='consulta-documentacao'\n", encoding="utf-8")
    (tmp_path / "requirements.lock").write_text("# fixture\n", encoding="utf-8")
    (tmp_path / "config.yaml").write_text("server:\n  transport: stdio\n", encoding="utf-8")

    report = run_doctor(tmp_path, environ={"DOCOPS_SKIP_RAG": "1"})

    assert report.checks["config"]["ok"] is True
    assert report.checks["config"]["transport"] == "stdio"


def test_doctor_fails_when_the_present_config_is_not_safe(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='consulta-documentacao'\n", encoding="utf-8")
    (tmp_path / "requirements.lock").write_text("# fixture\n", encoding="utf-8")
    (tmp_path / "config.yaml").write_text("server:\n  transport: streamable-http\n", encoding="utf-8")

    report = run_doctor(tmp_path, environ={"DOCOPS_SKIP_RAG": "1"})

    assert not report.ok
    assert report.checks["config"]["ok"] is False


def test_doctor_reports_redacted_ragflow_configuration_without_probing_by_default(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='consulta-documentacao'\n", encoding="utf-8")
    (tmp_path / "requirements.lock").write_text("# fixture\n", encoding="utf-8")
    token = "abc123xyz456"
    digest = "ragflow@sha256:" + "a" * 64

    report = run_doctor(
        tmp_path,
        environ={
            "DOCOPS_SKIP_RAG": "1",
            "DOCOPS_RAGFLOW_ENDPOINT": "https://ragflow.example.test/api",
            "DOCOPS_RAGFLOW_TOKEN": token,
            "DOCOPS_RAGFLOW_IMAGE_DIGEST": digest,
            "DOCOPS_RAGFLOW_SDK_VERSION": "0.27.2",
        },
    )

    payload = report.to_dict()
    ragflow = payload["checks"]["ragflow"]
    assert ragflow["endpoint"] == "https://ragflow.example.test:443"
    assert ragflow["authentication"] == "configured"
    assert ragflow["health"] == "not_probed"
    assert ragflow["image_digest_pinned"] is True
    assert token not in str(payload)


def test_doctor_works_outside_checkout_for_an_installed_distribution(tmp_path: Path) -> None:
    report = run_doctor(tmp_path, environ={})
    assert report.ok
    assert report.checks["installation"]["mode"] == "installed"
    assert report.checks["operator_skill"]["ok"] is True


def test_installed_doctor_does_not_require_farol_lock_in_an_unrelated_python_project(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='my-application'\n", encoding="utf-8")
    report = run_doctor(tmp_path, environ={})
    assert report.ok
    assert report.checks["installation"]["mode"] == "installed"


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://[broken",
        "https://host:bad",
        "http://remote.test",
        "https://user:secret@host",
        "https://host?token=secret",
    ],
)
def test_doctor_rejects_unsafe_endpoints_without_crashing(tmp_path: Path, endpoint: str) -> None:
    report = run_doctor(tmp_path, environ={"DOCOPS_RAGFLOW_ENDPOINT": endpoint})
    assert report.checks["ragflow"]["status"] == "unavailable"
    assert "secret" not in report.to_json()


def test_doctor_probes_once_and_accepts_a_healthy_required_service(tmp_path: Path, monkeypatch) -> None:
    from docops.backends.base import ProbeResult
    from docops.backends.ragflow import RagFlowAdapter

    calls = []

    def probe(self):
        calls.append(1)
        return ProbeResult("ragflow", "healthy", version="0.27.2")

    monkeypatch.setattr(RagFlowAdapter, "probe", probe)
    report = run_doctor(
        tmp_path,
        environ={
            "DOCOPS_RAGFLOW_ENDPOINT": "https://ragflow.example.test",
            "DOCOPS_RAGFLOW_TOKEN": "private-test-token",
            "DOCOPS_RAGFLOW_IMAGE_DIGEST": "ragflow@sha256:" + "a" * 64,
            "DOCOPS_RAGFLOW_SDK_VERSION": "0.27.2",
            "DOCOPS_REQUIRE_RAGFLOW": "1",
            "DOCOPS_RAGFLOW_PROBE": "1",
        },
    )
    assert report.ok
    assert report.capabilities["rag"] == "available"
    assert len(calls) == 1


def test_doctor_never_probes_without_a_pinned_image(tmp_path: Path, monkeypatch) -> None:
    from docops.backends.ragflow import RagFlowAdapter

    def probe(self):
        pytest.fail("incomplete configuration must not make a network request")

    monkeypatch.setattr(RagFlowAdapter, "probe", probe)
    report = run_doctor(
        tmp_path,
        environ={
            "DOCOPS_RAGFLOW_ENDPOINT": "https://ragflow.example.test",
            "DOCOPS_RAGFLOW_TOKEN": "private-test-token",
            "DOCOPS_RAGFLOW_SDK_VERSION": "0.27.2",
            "DOCOPS_RAGFLOW_PROBE": "1",
        },
    )
    assert report.checks["ragflow"]["status"] == "not_ready"
