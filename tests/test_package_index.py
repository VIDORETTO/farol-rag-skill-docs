# seam-scope: implementation-infrastructure (Farol 3 public module seam: package local index built from a generated package)
from __future__ import annotations

import json
from pathlib import Path

import docops
from docops.backends import QueryRequest
from docops.package_index import build_package_index, open_package_index


def _package(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text(
        "# Acme Guide\n\nIntro.\n\n## Retries\n\nThe client retries 5 times with exponential backoff.\n",
        encoding="utf-8",
    )
    output = tmp_path / "package"
    docops.apply(
        docops.plan(
            docops.OperationRequest(
                source,
                docops.OperationOptions(output_dir=output, source_root=source.parent, slug="acme", license="MIT"),
            )
        )
    )
    return output


def test_generated_package_becomes_queryable_with_relative_citations(tmp_path: Path) -> None:
    package = _package(tmp_path)

    report = build_package_index(package)
    backend, index = open_package_index(package)
    result = backend.query(index, QueryRequest(query="how many retries", top_k=1))

    assert report["status"] == "queryable"
    assert report["blocks"] >= 2
    hit = result.hits[0]
    assert "5 times" in hit["text"]
    assert hit["path"] == "rag/documents/guide.md"
    assert hit["heading_path"] == ["Acme Guide", "Retries"]
    assert any(locator["kind"] == "line" for locator in hit["locators"])
    serialized = json.dumps(result.to_dict())
    assert str(tmp_path) not in serialized
    assert "file://" not in serialized


def test_rebuilding_the_package_index_is_deterministic(tmp_path: Path) -> None:
    package = _package(tmp_path)
    first = build_package_index(package)
    for path in (package / "rag" / "local-index").iterdir():
        path.unlink()

    second = build_package_index(package)
    backend, index = open_package_index(package)

    assert second["index_revision"] == first["index_revision"]
    assert backend.query(index, QueryRequest(query="exponential backoff", top_k=1)).hits[0]["path"] == (
        "rag/documents/guide.md"
    )
