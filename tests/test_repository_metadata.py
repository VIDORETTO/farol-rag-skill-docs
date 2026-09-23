from __future__ import annotations

import json
import tomllib
from pathlib import Path

import docops


def test_repository_metadata_is_consistent_and_utf8_clean() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
    metadata = json.loads(Path("docs/REPOSITORY-METADATA.json").read_text(encoding="utf-8"))
    readme = Path("README.md").read_text(encoding="utf-8")
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")

    assert metadata["name"] == pyproject["name"]
    assert metadata["description"] == pyproject["description"]
    assert metadata["version"] == pyproject["version"] == docops.__version__
    assert pyproject["scripts"]["farol"] == pyproject["scripts"]["docops"] == "docops.__main__:main"
    assert f"**Versão do pacote:** [v{docops.__version__}]" in readme
    assert f"## {docops.__version__} —" in changelog
    assert "Ã" not in readme
