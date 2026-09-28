# seam-scope: implementation-infrastructure (Farol 3 public module seam: S9: scripts/benchmark_value.py with a fake harness)
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.benchmark_value import grade_answer  # noqa: E402


def test_grading_uses_answer_keys_and_verifiable_citations() -> None:
    case = {"answer_keys": [["5", "five"], ["second"]], "expected_text": "retries 5 times"}
    blocks = {"rag/documents/guide.md:7": "The client retries 5 times with backoff."}

    right = grade_answer("It retries five times, each after a few seconds [rag/documents/guide.md:7].", case, blocks)
    wrong = grade_answer("It retries 3 times.", case, blocks)
    fake_citation = grade_answer("Five seconds (rag/documents/other.md:1).", case, blocks)

    assert right == {"correct": True, "citations": 1, "verified_citations": 1}
    assert wrong["correct"] is False
    assert fake_citation["citations"] == 1 and fake_citation["verified_citations"] == 0


def test_runner_compares_three_arms_with_a_fake_harness(tmp_path: Path) -> None:
    source = tmp_path / "docs"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\n\n## Retries\n\nThe client retries 5 times.\n", encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    for args in (("add", str(source), "--license", "MIT"), ("build",)):
        subprocess.run([sys.executable, "-m", "docops", *args], cwd=project, env=env, check=True, capture_output=True)
    harness = tmp_path / "fake_agent.py"
    harness.write_text(
        "import json, sys\n"
        "prompt = sys.stdin.read()\n"
        "if 'retries 5 times' in prompt or 'farol' in prompt:\n"
        "    answer = 'It retries five times [rag/documents/guide.md:5].'\n"
        "else:\n"
        "    answer = 'I do not know.'\n"
        "print(json.dumps({'result': answer, 'usage': {'input_tokens': len(prompt) // 4, 'output_tokens': 9}}))\n",
        encoding="utf-8",
    )
    cases = tmp_path / "cases.json"
    cases.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "retries",
                        "source": "docs",
                        "question": "How many retries?",
                        "expected_text": "retries 5 times",
                        "answer_keys": [["5", "five"]],
                    }
                ]
            }
        )
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/benchmark_value.py",
            "--project",
            str(project),
            "--cases",
            str(cases),
            "--harness",
            f"{sys.executable} {harness}",
            "--json",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env=env,
        timeout=120,
    )

    report = json.loads(completed.stdout)
    assert completed.returncode == 0, completed.stderr
    arms = report["arms"]
    assert set(arms) == {"no_context", "raw_corpus", "farol"}
    assert arms["no_context"]["accuracy"] == 0.0
    assert arms["farol"]["accuracy"] == 1.0 and arms["farol"]["verified_citation_rate"] == 1.0
    assert arms["raw_corpus"]["input_tokens"] > 0
    assert report["method"]["harness"].endswith("fake_agent.py")
