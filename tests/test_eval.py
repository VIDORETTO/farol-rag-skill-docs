# seam-scope: implementation-infrastructure (Farol 3.1 TK-215: S1 `farol eval` and the `questions` task)
"""TK-215: any package measures its own retrieval from its skill lineage."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from fixtures_31 import distilled_package

ROOT = Path(__file__).resolve().parents[1]


def _cli(*args: str) -> tuple[int, dict]:
    completed = subprocess.run(
        [sys.executable, "-m", "docops", *args, "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT), "FAROL_SEMANTIC": "0"},
        timeout=120,
    )
    return completed.returncode, json.loads(completed.stdout)


def test_eval_measures_recall_from_lineage_and_labels_it_self_assessment(tmp_path: Path) -> None:
    package = distilled_package(tmp_path)

    code, report = _cli("eval", "--package", str(package))

    lineage = report["lineage"]
    assert code == 0 and report["status"] == "measured"
    assert lineage["method"] == "lineage-self-assessment"
    # Hand-checked against the fixture: of 5 statements only two share a content
    # word with their blocks ("idempotent", "seconds"; "only" is a stopword).
    assert lineage["cases"] == 5
    assert lineage["recall_at_5"] == 0.4 and lineage["mrr_at_5"] == 0.4
    assert "optimistic" in report["note"]
    assert lineage["chapters"][0]["recall_at_5"] == 0.4


def test_eval_uses_agent_written_questions_when_present(tmp_path: Path) -> None:
    from docops.agent_tasks import next_task, submit_task

    package = distilled_package(tmp_path)
    code, _plan = _cli("task", "plan", "--questions", "2", "--package", str(package))
    assert code == 0
    task = next_task(package)
    assert task["kind"] == "questions" and "[b" in task["instructions"]
    refs = sorted({ref for chapter in task["inputs"]["chapters"] for ref in chapter["refs"]})
    folder = tmp_path / "questions"
    folder.mkdir()
    (folder / "questions.json").write_text(
        json.dumps(
            {
                "questions": [
                    {"question": "How many times does the client retry?", "refs": [refs[0]]},
                    {"question": "Who keeps the lighthouse lamp lit?", "refs": [refs[-1]]},
                ]
            }
        ),
        encoding="utf-8",
    )
    assert submit_task(package, "questions", folder)["status"] == "accepted"

    _code, report = _cli("eval", "--package", str(package))

    questions = report["questions"]
    assert questions["method"] == "agent-questions" and questions["cases"] == 2
    assert questions["recall_at_5"] == 0.5


def test_eval_without_a_distilled_skill_is_not_run(tmp_path: Path) -> None:
    package = distilled_package(tmp_path, install=False)

    code, report = _cli("eval", "--package", str(package))

    assert code == 1
    assert report["status"] == "not_run" and report["code"] == "skill_not_distilled"
