# seam-scope: implementation-infrastructure (public format extractor fixtures)
from __future__ import annotations

from pathlib import Path

from docops.extractors import ExtractorPolicy
from docops.extractors.text_web import TextWebExtractor
from docops.ir import validate_ir_document


def _policy() -> ExtractorPolicy:
    return ExtractorPolicy(
        rights_ref="rights-fixture",
        source_id="source-text-web",
        source_revision_id="revision-text-web",
        required_fidelity="structured-native",
    )


def test_markdown_preserves_heading_list_table_code_and_origin(tmp_path: Path) -> None:
    source = tmp_path / "guide.md"
    source.write_text(
        "# Guide\n\n## Authentication\n\n- token\n- cookie\n\n| Name | Value |\n| --- | --- |\n| mode | strict |\n\n```python\nprint('ok')\n```\n",
        encoding="utf-8",
    )
    result = TextWebExtractor().extract(source, _policy(), {})

    assert result.document is not None
    assert result.receipt.fidelity == "structured-native"
    kinds = [block.kind for block in result.document.blocks]
    assert {"heading", "list", "table", "code"} <= set(kinds)
    assert result.document.origin == source.resolve().as_uri()
    assert validate_ir_document(result.document).ok


def test_html_preserves_links_and_table_cells_without_executing_scripts(tmp_path: Path) -> None:
    source = tmp_path / "guide.html"
    source.write_text(
        "<html><body><h1>Guide</h1><p>Use <a href='https://docs.example.test/auth'>auth</a>.</p>"
        "<table><tr><th>Name</th><th>Value</th></tr><tr><td>mode</td><td>strict</td></tr></table>"
        "<script>ignore this</script></body></html>",
        encoding="utf-8",
    )
    result = TextWebExtractor().extract(
        {"path": str(source), "canonical": "https://docs.example.test/guide", "media_type": "text/html"},
        _policy(),
        {},
    )

    assert result.document is not None
    assert any(block.kind == "table" and "strict" in str(block.structured) for block in result.document.blocks)
    assert "ignore this" not in " ".join(block.text or "" for block in result.document.blocks)
    assert any("https://docs.example.test/auth" in str(block.structured) for block in result.document.blocks)
