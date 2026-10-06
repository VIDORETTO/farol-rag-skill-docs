# seam-scope: implementation-infrastructure (Farol 3.1 TK-210: S1 `farol add --as course` and S11 playlist client)
"""TK-210: a course (folder of lessons or YouTube playlist) is one source and one skill."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fixtures_31 import course_folder

from docops import journey, transcripts

VTT = "WEBVTT\n\n00:00:01.000 --> 00:00:05.000\n{text}\n"


def _course(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    journey.add_source(project, str(course_folder(tmp_path)), license="CC-BY-4.0", as_kind="course")
    assert journey.build(project)["ok"]
    return project


def test_course_folder_becomes_one_package_with_modules_in_natural_order(tmp_path: Path) -> None:
    from docops.package_index import package_documents

    project = _course(tmp_path)

    packages = journey.project_packages(project)
    documents, _skipped = package_documents(packages["curso-python"])

    assert list(packages) == ["curso-python"]
    assert [document["blocks"][0]["heading_path"][0] for document in documents] == [
        "Aula 1 - Introdução",
        "Aula 2 - Variáveis",
        "Aula 10 - Projeto final",
        "material",
    ]
    assert documents[-1]["blocks"][0]["heading_path"][:2] == ["material", "Slides"]


def test_course_citations_name_the_lesson_and_timestamp(tmp_path: Path) -> None:
    from docops.mcp_server import KnowledgeServer

    project = _course(tmp_path)

    server = KnowledgeServer(packages=journey.project_packages(project))
    top = server.search_knowledge("projeto final testes automatizados", top_k=1)["hits"][0]

    assert "Aula 10 - Projeto final" in top["citation"] and "(at 00:02:30)" in top["citation"]


def test_course_requires_a_declared_license_for_local_folders(tmp_path: Path) -> None:
    with pytest.raises(journey.JourneyError) as error:
        journey.add_source(tmp_path / "project", str(course_folder(tmp_path)), as_kind="course")

    assert error.value.code == "license_required"


def _fake_playlist(monkeypatch, licenses: list[str]) -> list[str]:
    ids = [f"vid{index:08d}" for index in range(1, len(licenses) + 1)]

    def fake_playlist(url: str, *, max_items: int) -> list[dict[str, Any]]:
        assert "list=" in url
        return [
            {"id": video, "title": f"Lesson {position}: part {position}", "playlist_index": position}
            for position, video in enumerate(ids, 1)
        ][:max_items]

    def fake_fetch(url: str, *, languages: list[str]) -> dict[str, Any]:
        video = url.rsplit("=", 1)[1]
        position = ids.index(video) + 1
        return {
            "id": video,
            "title": f"Lesson {position}: part {position}",
            "channel": "Teacher",
            "license": licenses[position - 1],
            "duration": 60,
            "chapters": [],
            "captions": {
                "kind": "manual",
                "language": "en",
                "vtt": VTT.format(text=f"Lesson {position} covers loops."),
            },
        }

    monkeypatch.setattr(transcripts, "fetch_playlist", fake_playlist)
    monkeypatch.setattr(transcripts, "fetch_youtube", fake_fetch)
    return ids


def test_playlist_course_keeps_playlist_order_and_per_video_licenses(tmp_path: Path, monkeypatch) -> None:
    from docops.package_index import package_documents

    cc = "Creative Commons Attribution license (reuse allowed)"
    _fake_playlist(monkeypatch, [cc, cc, cc])
    project = tmp_path / "project"
    url = "https://www.youtube.com/playlist?list=PL123"

    added = journey.add_source(project, url, as_kind="course")
    assert journey.build(project)["ok"]

    source = json.loads((project / "farol.json").read_text(encoding="utf-8"))["sources"][0]
    assert added["source"]["kind"] == "course" and source["license"] == "CC-BY-3.0"
    assert [member["order"] for member in source["members"]] == [1, 2, 3]
    assert {member["license"] for member in source["members"]} == {"CC-BY-3.0"}
    documents, _ = package_documents(journey.project_packages(project)[source["id"]])
    assert [document["blocks"][0]["heading_path"][0] for document in documents] == [
        "Lesson 1: part 1",
        "Lesson 2: part 2",
        "Lesson 3: part 3",
    ]


def test_non_redistributable_member_blocks_course_redistribution(tmp_path: Path, monkeypatch) -> None:
    cc = "Creative Commons Attribution license (reuse allowed)"
    _fake_playlist(monkeypatch, [cc, "Standard YouTube License", cc])
    project = tmp_path / "project"

    journey.add_source(project, "https://www.youtube.com/playlist?list=PL9", as_kind="course", redistribution="public")
    assert journey.build(project)["ok"]

    source = json.loads((project / "farol.json").read_text(encoding="utf-8"))["sources"][0]
    assert source["redistribution"] == "private-only"
    assert source["license"] is None or source["license"] == "mixed"


def test_course_outline_task_lists_modules_in_order(tmp_path: Path) -> None:
    from docops.agent_tasks import next_task, plan_synthesis

    project = _course(tmp_path)
    package = journey.project_packages(project)["curso-python"]

    plan_synthesis(package, language="pt", outline="agent")
    native = [item["title"] for item in next_task(package)["inputs"]["native_chapters"]]

    assert native == ["Aula 1 - Introdução", "Aula 2 - Variáveis", "Aula 10 - Projeto final", "material"]


def test_a_windows_drive_path_is_never_mistaken_for_a_playlist(monkeypatch) -> None:
    called: list[str] = []
    monkeypatch.setattr(journey, "_acquire_playlist", lambda project, source: called.append("playlist") or "")
    source = {"id": "curso", "kind": "course", "input": r"C:\Users\aluno\curso", "license": "MIT"}

    class Project:
        root = Path("unused")

        def package(self, _id: str) -> Path:
            return Path("unused")

    with pytest.raises(Exception):
        journey._build_one(Project(), source)  # the folder does not exist here; only routing matters
    assert called == []
