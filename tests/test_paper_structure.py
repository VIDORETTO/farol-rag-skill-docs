# seam-scope: implementation-infrastructure (Farol 3 public module seam: PDF books/papers → package index, citations and synthesis sections)
from __future__ import annotations

import io
from pathlib import Path

from pypdf import PdfReader, PdfWriter

import docops
from docops.agent_tasks import next_task, plan_synthesis
from docops.backends import QueryRequest
from docops.mcp_server import citation
from docops.package_index import build_package_index, open_package_index

PAGES = [
    "arXiv:2404.16130v2 A Graph Approach. Introduction. Retrieval helps global questions.",
    "Methods. We partition the graph with community detection.",
    "Results. The graph had 8564 nodes and 20691 edges.",
    "References. Traag et al. 2019.",
]


def _pdf(texts: list[str]) -> bytes:
    count = len(texts)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Count {count} /Kids [{' '.join(f'{3 + i} 0 R' for i in range(count))}] >>".encode(),
    ]
    for index in range(count):
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 200] /Resources << /Font << /F1 {3 + count * 2} 0 R"
            f" >> >> /Contents {3 + count + index} 0 R >>".encode()
        )
    for text in texts:
        stream = b"BT /F1 10 Tf 10 100 Td (" + text.encode() + b") Tj ET"
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    output = bytearray(b"%PDF-1.4\n")
    offsets = []
    for object_id, body in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{object_id} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(bytes(output))))
    for page, title in enumerate(("Introduction", "Methods", "Results", "References")):
        writer.add_outline_item(title, page)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _package(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    (source / "paper.pdf").write_bytes(_pdf(PAGES))
    output = tmp_path / "package"
    result = docops.apply(
        docops.plan(
            docops.OperationRequest(
                source,
                docops.OperationOptions(
                    output_dir=output, source_root=source.parent, slug="paper", license="CC-BY-4.0"
                ),
            )
        )
    )
    assert result.ok, result.errors
    build_package_index(output)
    return output


def test_pdf_outline_gives_sections_and_every_hit_cites_its_page(tmp_path: Path) -> None:
    package = _package(tmp_path)
    backend, index = open_package_index(package)

    hit = backend.query(index, QueryRequest(query="how many nodes did the graph have", top_k=1)).hits[0]

    assert "8564 nodes" in hit["text"]
    assert "Results" in hit["heading_path"]
    assert {"kind": "page", "page": 3} in [
        {k: v for k, v in item.items() if k in {"kind", "page"}} for item in hit["locators"]
    ]
    assert citation(hit).endswith("(page 3)")


def test_paper_metadata_is_extracted_into_the_document(tmp_path: Path) -> None:
    package = _package(tmp_path)

    document = (package / "rag" / "documents" / "paper.md").read_text(encoding="utf-8")

    assert "- arXiv: 2404.16130v2" in document
    assert "- Pages: 4" in document


def test_synthesis_sections_follow_the_pdf_outline_not_pages(tmp_path: Path) -> None:
    package = _package(tmp_path)
    plan_synthesis(package, language="en", outline="agent")

    titles = [section["title"] for section in next_task(package)["inputs"]["sections"]]

    assert any(title.endswith("Methods") for title in titles)
    assert not any("Page" in title for title in titles)


def test_arxiv_sources_are_downloaded_with_their_declared_license(tmp_path: Path, monkeypatch) -> None:
    from docops.journey import add_source, build, status

    mirror = tmp_path / "mirror"
    (mirror / "pdf").mkdir(parents=True)
    (mirror / "abs").mkdir()
    (mirror / "pdf" / "2404.16130v2").write_bytes(_pdf(PAGES))
    (mirror / "abs" / "2404.16130v2").write_text(
        '<a href="http://creativecommons.org/licenses/by/4.0/" rel="license">CC BY 4.0</a>'
        '<h1 class="title mathjax">Title:From Local to Global</h1>',
        encoding="utf-8",
    )
    monkeypatch.setenv("FAROL_ARXIV_MIRROR", mirror.as_uri())
    project = tmp_path / "project"

    added = add_source(project, "arXiv:2404.16130v2")
    built = build(project)
    report = status(project)

    assert added["source"]["id"] == "arxiv-2404-16130v2" and added["source"]["kind"] == "arxiv"
    assert built["ok"], built
    source = report["sources"][0]
    assert source["state"] == "awaiting_agent" and not source["warnings"]
    import json

    config = json.loads((project / "farol.json").read_text(encoding="utf-8"))
    assert config["sources"][0]["license"] == "CC-BY-4.0"
    assert config["sources"][0]["title"] == "From Local to Global"


def test_outline_sections_are_not_nested_under_metadata(tmp_path: Path) -> None:
    package = _package(tmp_path)
    plan_synthesis(package, language="en", outline="agent")

    titles = [section["title"] for section in next_task(package)["inputs"]["sections"]]

    assert titles[:3] == ["Introduction", "Methods", "Results"]


def test_pdf_text_is_not_parsed_as_markdown() -> None:
    from docops.normalizer import _pdf_page_markdown, markdown_headings

    text = (
        "Git keeps a local database of every change in the project so\n"
        "history is read from disk.\n"
        "# On branch master\n"
        "```not a fence\n"
        "Git has three main states that your files can reside in, modified,\n"
        "staged, and committed.\n"
    )

    rendered = _pdf_page_markdown(text)

    assert markdown_headings(rendered) == []
    assert "\\# On branch master" in rendered and "\\```not a fence" in rendered
    assert "Git has three main states that your files can reside in" in rendered
