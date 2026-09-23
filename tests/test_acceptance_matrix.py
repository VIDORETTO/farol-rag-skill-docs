# seam-scope: compatibility-infrastructure (release acceptance-matrix fixture)
from __future__ import annotations

from scripts.check_acceptance_matrix import (
    UMBRELLA_TICKET,
    backlog_traceability_findings,
    build_matrix,
    render_markdown,
)


def test_acceptance_matrix_covers_every_criterion_without_the_umbrella() -> None:
    matrix = build_matrix()

    assert [row["ac"] for row in matrix["rows"]] == [f"AC-{i:03d}" for i in range(1, 34)]
    umbrella_only = []
    for row in matrix["rows"]:
        # Every AC must point at a covering ticket (the umbrella is allowed).
        assert row["tickets"], row["ac"]
        # The umbrella alone cannot make an AC verified; such a row would be
        # blocked so missing dedicated coverage stays visible.
        if row["tickets"] == [UMBRELLA_TICKET]:
            umbrella_only.append(row["ac"])
            assert row["status"] == "blocked", row["ac"]
    assert umbrella_only == []
    ac031 = next(row for row in matrix["rows"] if row["ac"] == "AC-031")
    assert ac031["dedicated_tickets"] == ["TK-021"]
    assert ac031["status"] == "verified"


def test_acceptance_matrix_status_is_derived_not_asserted() -> None:
    matrix = build_matrix()
    summary = matrix["summary"]

    assert sum(summary.values()) == len(matrix["rows"]) == 33
    # TK-017 verified the editorial contraction, so AC-028 is verified.
    ac028 = next(row for row in matrix["rows"] if row["ac"] == "AC-028")
    assert ac028["status"] == "verified"
    # AC-029 is verified after the approved cutover and bounded contraction.
    ac029 = next(row for row in matrix["rows"] if row["ac"] == "AC-029")
    assert ac029["status"] == "verified"


def test_acceptance_matrix_artifact_matches_the_derivation() -> None:
    matrix = build_matrix()
    observed = (
        __import__("pathlib")
        .Path(__file__)
        .resolve()
        .parents[1]
        .joinpath("specs", "farol-2", "acceptance-matrix.md")
        .read_text(encoding="utf-8")
    )

    assert observed == render_markdown(matrix)


def test_backlog_traceability_matches_dedicated_coverage() -> None:
    matrix = build_matrix()

    findings = backlog_traceability_findings(matrix)

    # Every AC attributed by the backlog to a dedicated ticket is referenced by
    # that ticket; AC-031 is now covered by TK-021.
    assert findings == [], findings
    assert matrix["unattributed"] == []


def test_backlog_drift_check_detects_a_false_dedicated_claim() -> None:
    matrix = build_matrix()
    drifted = {
        **matrix,
        "rows": [
            {**row, "dedicated_tickets": [] if row["ac"] == "AC-005" else row["dedicated_tickets"]}
            for row in matrix["rows"]
        ],
    }

    findings = backlog_traceability_findings(drifted)

    assert any(
        finding["code"] == "backlog_unattributed_claim" and "AC-005" in finding["message"] for finding in findings
    )
