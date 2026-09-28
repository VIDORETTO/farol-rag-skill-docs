# seam-scope: implementation-infrastructure (Farol 3 public module seam: content safety classification used by extraction, index, MCP and synthesis)
from __future__ import annotations

import json
from pathlib import Path

import pytest

from docops.safety import classify

CASES = json.loads((Path(__file__).parent / "fixtures" / "adversarial" / "cases.json").read_text(encoding="utf-8"))[
    "cases"
]


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_hand_labelled_adversarial_corpus(case: dict) -> None:
    verdict = classify(case["text"])

    assert verdict.risk == case["risk"], verdict.reasons
    assert bool(verdict.reasons) is (case["risk"] != "none")
