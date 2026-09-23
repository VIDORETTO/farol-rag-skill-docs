# seam-scope: compatibility-infrastructure (provider-free release fixture)
from __future__ import annotations

import json
from pathlib import Path

from scripts.run_farol_v2_fixture import run_fixture


def test_provider_free_farol_v2_fixture_is_complete_and_redacted(tmp_path: Path) -> None:
    report = run_fixture(tmp_path / "fixture")

    assert report["status"] == "passed"
    assert report["external"]["ragflow"]["status"] == "not_run"
    assert report["journey"]["composition_rollback"] is True
    serialized = json.dumps(report, ensure_ascii=False)
    assert "Use a token" not in serialized
