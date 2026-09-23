# seam-scope: implementation-infrastructure (public extractor registry fixtures)
from __future__ import annotations

from pathlib import Path

import pytest

from docops.extractors import (
    ExtractorError,
    ExtractorPolicy,
    ExtractorRegistry,
    LegacyTextExtractor,
    default_registry,
)


def test_registry_selects_local_extractor_by_signature_and_declares_fallback(tmp_path: Path) -> None:
    source = tmp_path / "guide.md"
    source.write_text("# Guide\n\nUse a token.\n", encoding="utf-8")
    registry = ExtractorRegistry([LegacyTextExtractor()])

    result = registry.extract(
        source,
        policy=ExtractorPolicy(rights_ref="rights-fixture", source_id="source-fixture", source_revision_id="rev-1"),
    )

    assert result.document is not None
    assert result.receipt.fidelity == "text-fallback"
    assert result.document.blocks[0].locators[0]["kind"] == "section"
    assert result.receipt.extractor["execution"] == "local"


def test_remote_plugin_is_blocked_before_receiving_bytes(tmp_path: Path) -> None:
    source = tmp_path / "guide.md"
    source.write_text("secret source bytes", encoding="utf-8")

    class RemotePlugin(LegacyTextExtractor):
        def __init__(self) -> None:
            super().__init__(name="remote-fixture", execution="remote")
            self.called = False

        def extract(self, artifact, policy, budget):  # type: ignore[no-untyped-def]
            self.called = True
            raise AssertionError("remote extractor received bytes before opt-in")

    plugin = RemotePlugin()
    registry = ExtractorRegistry([plugin])

    with pytest.raises(ExtractorError) as caught:
        registry.extract(source, policy=ExtractorPolicy(rights_ref="rights-fixture"))

    assert caught.value.code == "permission_required"
    assert plugin.called is False


def test_registry_fails_closed_for_missing_rights_and_budget(tmp_path: Path) -> None:
    source = tmp_path / "guide.md"
    source.write_text("# Guide\n", encoding="utf-8")
    registry = ExtractorRegistry([LegacyTextExtractor()])

    with pytest.raises(ExtractorError) as rights:
        registry.extract(source, policy=ExtractorPolicy())
    assert rights.value.code == "rights_required"

    with pytest.raises(ExtractorError) as budget:
        registry.extract(
            source,
            policy=ExtractorPolicy(rights_ref="rights-fixture", max_bytes=1),
        )
    assert budget.value.code == "budget_exceeded"


def test_default_registry_selects_repository_for_directory(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    selected = default_registry().choose(
        tmp_path,
        policy=ExtractorPolicy(rights_ref="rights", required_fidelity="structured-native"),
    )

    assert selected.describe().name == "repository"
