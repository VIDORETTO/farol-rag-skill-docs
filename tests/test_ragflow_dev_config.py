from __future__ import annotations

from pathlib import Path

import pytest

from scripts import prepare_ragflow_dev
from scripts.prepare_ragflow_dev import RagFlowDevError, apply_plan, build_plan


def test_ragflow_dev_plan_is_pinned_loopback_only_and_does_not_apply(tmp_path: Path) -> None:
    digest = "infiniflow/ragflow@sha256:" + "a" * 64

    plan = build_plan(tmp_path / "ragflow", digest)

    assert plan["ok"] is True
    assert plan["source"] == {
        "repository": "https://github.com/infiniflow/ragflow.git",
        "tag": "v0.27.2",
        "commit": "a024bea0cd93f39e6652a42bf84dd20c55bc560b",
    }
    assert plan["runtime"]["sdk_version"] == "0.27.2"
    assert plan["runtime"]["network_exposure"] == "loopback-only"
    assert plan["runtime"]["profiles"] == ["cpu", "elasticsearch", "metadata-mysql", "tei-cpu"]
    assert plan["runtime"]["services"] == ["es01", "mysql", "minio", "redis", "tei-cpu", "ragflow-cpu"]
    assert plan["runtime"]["embedding_model"] == "BAAI/bge-small-en-v1.5"
    assert plan["runtime"]["tei_image_digest"].endswith(
        "@sha256:ad4a00f5af757f7f323bdeb9e873313ed71225cf57d94658cbc9c6c17dc67d85"
    )
    assert plan["commands"]["compose"].count("--profile") == 4
    assert plan["commands"]["compose"][-6:] == ["es01", "mysql", "minio", "redis", "tei-cpu", "ragflow-cpu"]
    assert not (tmp_path / "ragflow").exists()


def test_ragflow_dev_plan_fails_closed_without_a_repository_digest(tmp_path: Path) -> None:
    plan = build_plan(tmp_path / "ragflow", "infiniflow/ragflow:v0.27.2")

    assert plan["ok"] is False
    assert plan["status"] == "blocked"
    assert plan["blockers"] == ["DOCOPS_RAGFLOW_IMAGE_DIGEST"]


def test_ragflow_compose_override_publishes_only_loopback_ports() -> None:
    override = Path("config/ragflow/compose.dev.override.yaml").read_text(encoding="utf-8")

    assert "DOCOPS_RAGFLOW_IMAGE_DIGEST" in override
    assert "DOCOPS_RAGFLOW_TEI_IMAGE_DIGEST" in override
    assert "BAAI/bge-small-en-v1.5" in override
    assert '"127.0.0.1:${DOCOPS_RAGFLOW_WEB_PORT:-8080}:80"' in override
    assert '"127.0.0.1:${DOCOPS_RAGFLOW_API_PORT:-9380}:9380"' in override
    assert '"127.0.0.1:${TEI_PORT:-6380}:80"' in override
    assert "9381:9381" not in override
    assert "9382:9382" not in override
    published_ports = [line.strip() for line in override.splitlines() if line.lstrip().startswith('- "')]
    assert published_ports
    assert all(line.startswith('- "127.0.0.1:') for line in published_ports)


def test_ragflow_dev_apply_refuses_to_reuse_a_different_git_checkout(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "existing"
    (workspace / ".git").mkdir(parents=True)
    digest = "infiniflow/ragflow@sha256:" + "a" * 64
    plan = build_plan(workspace, digest)

    monkeypatch.setattr(
        prepare_ragflow_dev.subprocess,
        "run",
        lambda *args, **kwargs: prepare_ragflow_dev.subprocess.CompletedProcess(
            args[0], 0, stdout="https://github.com/example/other.git\n", stderr=""
        ),
    )

    with pytest.raises(RagFlowDevError) as caught:
        apply_plan(plan, digest)

    assert caught.value.code == "workspace_source_mismatch"
