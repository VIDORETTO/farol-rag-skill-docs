# seam-scope: implementation-infrastructure (runtime selection unit tests)
from __future__ import annotations

import sys
from pathlib import Path

from docops.runtime import discover_rag_python, runtime_contract, runtime_environment, venv_config_matches_host


def test_ragflow_python_discovery_accepts_explicit_override(tmp_path: Path) -> None:
    executable = tmp_path / "custom-python"
    executable.touch()

    result = discover_rag_python(tmp_path, environ={"DOCOPS_RAG_PYTHON": str(executable)})

    assert result.path == executable
    assert result.source == "environment"


def test_runtime_environment_is_minimal_and_does_not_embed_author_paths(tmp_path: Path) -> None:
    environment = runtime_environment(tmp_path, environ={"PATH": "fixture"})

    assert environment["PYTHONUNBUFFERED"] == "1"
    assert "KNOWLEDGE_RAG_DIR" not in environment
    assert "Documents\\Sistemas\\consulta-documentacao" not in str(environment)


def test_runtime_contract_reports_the_external_ragflow_profile(tmp_path: Path) -> None:
    contract = runtime_contract(tmp_path, python=sys.executable, expected_version="0.27.2")

    assert contract["backend"] == "ragflow"
    assert contract["expected_version"] == "0.27.2"
    assert contract["python_source"] == "explicit"


def test_venv_config_accepts_native_host_home(tmp_path: Path) -> None:
    directory = tmp_path / ".venv"
    directory.mkdir()
    (directory / "pyvenv.cfg").write_text("home = C:\\Python314\n", encoding="utf-8")
    assert venv_config_matches_host(directory)
