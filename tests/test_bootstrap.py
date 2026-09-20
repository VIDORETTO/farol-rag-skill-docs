from __future__ import annotations

import sys
from pathlib import Path

import pytest

from scripts.bootstrap import install_command, main, pip_upgrade_command


def test_bootstrap_rejects_the_removed_legacy_profile(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="legacy RAG profile was removed"):
        install_command(Path("python"), tmp_path, rag=True, formats=True, dev=True)


def test_bootstrap_installs_the_project_and_optional_formats_profile(tmp_path: Path) -> None:
    command = install_command(Path("python"), tmp_path, formats=True, dev=True)

    assert command[:5] == ["python", "-m", "pip", "install", "--editable"]
    assert str(tmp_path) in command
    assert "--requirement" not in command
    assert "pytest==9.1.1" in command
    assert "pip-audit==2.10.1" in command
    assert "setuptools==84.0.0" in command
    assert "PyYAML==6.0.3" in command
    assert "pypdf==6.16.2" in command


def test_bootstrap_pins_a_known_safe_pip_before_installing_packages() -> None:
    command = pip_upgrade_command(Path("python"))

    assert command[-2:] == ["pip==26.2.1", "setuptools==84.0.0"]


def test_bootstrap_cli_isolates_a_foreign_platform_venv(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='fixture'\n", encoding="utf-8")
    foreign_home = "/usr/bin" if sys.platform == "win32" else r"C:\Python314"
    primary = tmp_path / ".venv"
    primary.mkdir()
    config = primary / "pyvenv.cfg"
    config.write_text(f"home = {foreign_home}\n", encoding="utf-8")

    assert main(["--root", str(tmp_path), "--no-install"]) == 0

    platform_name = ".venv-windows" if sys.platform == "win32" else ".venv-posix"
    relative = Path("Scripts/python.exe") if sys.platform == "win32" else Path("bin/python")
    assert (tmp_path / platform_name / relative).is_file()
    assert config.read_text(encoding="utf-8") == f"home = {foreign_home}\n"
