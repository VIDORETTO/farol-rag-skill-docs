# seam-scope: implementation-infrastructure (validator fixtures; public package contract)
from __future__ import annotations

import json
from pathlib import Path

import pytest

from docops.package_validator import validate_package
from docops.pipeline import PipelineOptions, run_pipeline


def test_validator_rejects_a_package_missing_one_product(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "run-1",
                "source": {"input": "fixture", "canonical": "file:///fixture", "version": "local"},
                "provenance": {"license": "MIT", "redistribution": "allowed"},
                "artifacts": {"skill": "skill", "router": "router", "rag": "rag"},
            }
        ),
        encoding="utf-8",
    )

    result = validate_package(tmp_path)

    assert not result.ok
    assert "missing_skill" in {error["code"] for error in result.errors}


def test_validator_accepts_the_complete_fixture_package(tmp_path: Path) -> None:
    skill = tmp_path / "skill"
    router = tmp_path / "router"
    rag = tmp_path / "rag"
    (skill / "chapters").mkdir(parents=True)
    router.mkdir()
    (rag / "documents").mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: fixture-skill\ndescription: Fixture knowledge skill.\n---\n# Fixture\n\n- Version: "
        + chr(96)
        + "local"
        + chr(96)
        + "\n",
        encoding="utf-8",
    )
    (router / "SKILL.md").write_text(
        "---\nname: fixture-router\ndescription: Routes fixture questions.\n---\n"
        "Use fixture-skill for concepts and search_knowledge for facts. Cite source.\n",
        encoding="utf-8",
    )
    (rag / "documents" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (rag / "index.json").write_text(json.dumps({"status": "ready", "documents": 1, "chunks": 1}), encoding="utf-8")
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "run-1",
                "source": {"input": "fixture", "canonical": "file:///fixture", "version": "local"},
                "provenance": {"license": "MIT", "redistribution": "allowed"},
                "artifacts": {"skill": "skill", "router": "router", "rag": "rag"},
            }
        ),
        encoding="utf-8",
    )

    result = validate_package(tmp_path)

    assert result.ok, result.errors


def test_validator_rejects_an_unavailable_harness_config(tmp_path: Path) -> None:
    skill = tmp_path / "skill"
    router = tmp_path / "router"
    rag = tmp_path / "rag"
    skill.mkdir()
    router.mkdir()
    (rag / "documents").mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: fixture\ndescription: Fixture.\n---\n", encoding="utf-8")
    (router / "SKILL.md").write_text(
        "---\nname: fixture-router\ndescription: Router.\n---\nfixture search_knowledge citation", encoding="utf-8"
    )
    (rag / "documents" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (rag / "index.json").write_text(json.dumps({"status": "ready", "documents": 1, "chunks": 1}), encoding="utf-8")
    (tmp_path / "harness.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "package_root": ".",
                "skills": ["skill", "router"],
                "backend": {
                    "name": "ragflow",
                    "version": "0.27.2",
                    "adapter": "docops.backends.ragflow.RagFlowAdapter",
                    "transport": "https-or-loopback-development",
                    "cwd": ".",
                    "config": "config.yaml",
                    "capabilities": ["probe", "query"],
                    "external": True,
                },
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "run-1",
                "source": {"input": "fixture", "canonical": "file:///fixture", "version": "local"},
                "provenance": {"license": "MIT", "redistribution": "private-only"},
                "artifacts": {
                    "skill": "skill",
                    "router": "router",
                    "rag": "rag",
                    "harness": "harness.json",
                    "config": "config.yaml",
                },
            }
        ),
        encoding="utf-8",
    )

    result = validate_package(tmp_path)

    assert not result.ok
    assert "missing_config" in {error["code"] for error in result.errors}


def test_validator_audits_the_config_used_by_the_harness(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\n", encoding="utf-8")
    package = tmp_path / "package"
    assert run_pipeline(source, options=PipelineOptions(output_dir=package, slug="guide", license="MIT")).ok

    (package / "unsafe.yaml").write_text("server:\n  transport: sse\n", encoding="utf-8")
    harness_path = package / "harness.json"
    harness = json.loads(harness_path.read_text(encoding="utf-8"))
    harness["backend"]["config"] = "unsafe.yaml"
    harness_path.write_text(json.dumps(harness), encoding="utf-8")

    result = validate_package(package)

    assert not result.ok
    assert "network_auth_required" in {error["code"] for error in result.errors}


def test_validator_does_not_claim_success_when_skill_version_diverges(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\n", encoding="utf-8")
    package = tmp_path / "package"
    assert run_pipeline(
        source, options=PipelineOptions(output_dir=package, slug="guide", version="v1", license="MIT")
    ).ok

    skill = package / "skill" / "SKILL.md"
    marker_v1 = "Version: " + chr(96) + "v1" + chr(96)
    marker_v2 = "Version: " + chr(96) + "v2" + chr(96)
    skill.write_text(skill.read_text(encoding="utf-8").replace(marker_v1, marker_v2), encoding="utf-8")

    result = validate_package(package)

    assert not result.ok
    assert "skill_rag_divergence" in {error["code"] for error in result.errors}


def test_validator_rejects_nested_symlink_artifacts(tmp_path: Path) -> None:
    package = tmp_path / "package"
    skill = package / "skill"
    router = package / "router"
    rag = package / "rag"
    (skill / "chapters").mkdir(parents=True)
    router.mkdir(parents=True)
    (rag / "documents").mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: fixture\ndescription: Fixture.\n---\n", encoding="utf-8")
    (router / "SKILL.md").write_text(
        "---\nname: fixture-router\ndescription: Router.\n---\nfixture search_knowledge citation",
        encoding="utf-8",
    )
    (rag / "index.json").write_text(json.dumps({"status": "ready", "documents": 1, "chunks": 1}), encoding="utf-8")
    external = tmp_path / "outside.md"
    external.write_text("# outside\n", encoding="utf-8")
    try:
        (rag / "documents" / "outside.md").symlink_to(external)
    except OSError:
        pytest.skip("symlink creation is unavailable on this host")
    (package / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "run-1",
                "source": {"input": "fixture", "canonical": "file:///fixture", "version": "local"},
                "provenance": {"license": "MIT", "redistribution": "private-only"},
                "artifacts": {"skill": "skill", "router": "router", "rag": "rag"},
            }
        ),
        encoding="utf-8",
    )

    result = validate_package(package)

    assert not result.ok
    assert "symlink_artifact" in {error["code"] for error in result.errors}
