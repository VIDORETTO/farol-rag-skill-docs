# seam-scope: implementation-infrastructure (public format extractor fixtures)
from __future__ import annotations

import subprocess
from pathlib import Path

from docops.extractors import ExtractorPolicy
from docops.extractors.repository import RepositoryExtractor
from docops.ir import validate_ir_document


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "fixture-repo"
    (root / "docs").mkdir(parents=True)
    (root / "schemas").mkdir()
    (root / "src").mkdir()
    (root / "docs" / "guide.md").write_text("# Guide\n\nUse a token.\n", encoding="utf-8")
    (root / "schemas" / "openapi.yaml").write_text("openapi: 3.1.0\ninfo:\n  title: Fixture\n", encoding="utf-8")
    (root / "src" / "service.py").write_text(
        "class Service:\n    pass\n\ndef run():\n    return True\n", encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "fixture@example.test"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Fixture"], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
    return root


def _policy() -> ExtractorPolicy:
    return ExtractorPolicy(
        rights_ref="rights-repository",
        source_id="source-repository",
        source_revision_id="revision-repository",
        required_fidelity="structured-native",
    )


def test_repository_defaults_to_docs_contracts_and_schemas(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    result = RepositoryExtractor().extract(root, _policy(), {})

    assert result.document is not None
    assert "docs/guide.md" in result.receipt.metadata["selected"]
    assert "schemas/openapi.yaml" in result.receipt.metadata["selected"]
    assert "src/service.py" in result.receipt.metadata["ignored"]
    assert result.receipt.metadata["commit"]
    assert validate_ir_document(result.document).ok


def test_repository_code_requires_explicit_scope_and_preserves_symbols(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    result = RepositoryExtractor().extract(
        {"path": str(root), "code_include": ["src/**/*.py"]},
        _policy(),
        {},
    )

    assert result.document is not None
    code = [block for block in result.document.blocks if block.symbol]
    assert {block.symbol for block in code} >= {"Service", "run"}
    assert any(locator.get("path") == "src/service.py" for block in code for locator in block.locators)
    assert any(locator.get("line") == 4 for block in code for locator in block.locators)


def test_repository_budget_failure_does_not_promote_partial_ir(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    result = RepositoryExtractor().extract(root, _policy(), {"max_files": 1})

    assert result.document is None
    assert result.receipt.status == "failed"
    assert result.receipt.errors[0]["code"] == "budget_exceeded"
