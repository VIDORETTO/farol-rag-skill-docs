"""Derive the Farol 2.0 acceptance matrix from the canonical tickets.

TK-020's release readiness requires every acceptance criterion (AC-001..AC-033)
to have either executed evidence or an explicit blocker. This module derives,
never invents: each AC's status and evidence pointer come from the covering
tickets' ``acceptance_refs`` / ``status`` / ``verification_status`` fields and
their evidence files. TK-020 itself is excluded from the status roll-up because
it is the umbrella delivery ticket; the matrix exists so that umbrella gate can
be evaluated.

``--check`` compares the checked-in artifact against a fresh derivation so the
matrix cannot drift from the tickets.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC_ROOT = PROJECT_ROOT / "specs" / "farol-2"
UMBRELLA_TICKET = "TK-020"
AC_COUNT = 33

_FIELD = re.compile(r"^(?P<key>[a-z_]+):\s*(?P<value>.+)$")


def _parse_ticket(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if line.startswith("---"):
            if fields:
                break
            continue
        match = _FIELD.match(line)
        if match:
            fields[match.group("key")] = match.group("value").strip()
    refs = fields.get("acceptance_refs", "[]").strip()
    if refs.startswith("[") and refs.endswith("]"):
        refs = refs[1:-1]
    return {
        "id": fields.get("id") or path.stem,
        "status": fields.get("status", "unknown"),
        "verification_status": fields.get("verification_status", "unknown"),
        "acceptance_refs": [item.strip() for item in refs.split(",") if item.strip()],
    }


def _tickets() -> dict[str, dict[str, Any]]:
    return {path.stem: _parse_ticket(path) for path in sorted((SPEC_ROOT / "tickets").glob("TK-*.md"))}


def _evidence_file(ticket_id: str) -> str | None:
    path = SPEC_ROOT / "evidence" / f"{ticket_id}.md"
    return f"specs/farol-2/evidence/{ticket_id}.md" if path.is_file() else None


def _derive_status(covering: list[dict[str, Any]]) -> str:
    relevant = [ticket for ticket in covering if ticket["id"] != UMBRELLA_TICKET]
    if not relevant:
        return "blocked"
    if all(ticket["status"] == "verified" for ticket in relevant):
        return "verified"
    if any(ticket["status"] == "in_progress" for ticket in relevant):
        return "in_progress"
    return "blocked"


def build_matrix() -> dict[str, Any]:
    tickets = _tickets()
    rows: list[dict[str, Any]] = []
    for index in range(1, AC_COUNT + 1):
        ac = f"AC-{index:03d}"
        covering = [ticket for ticket in tickets.values() if ac in ticket["acceptance_refs"]]
        covering_ids = sorted(ticket["id"] for ticket in covering)
        evidence = sorted({path for ticket in covering if (path := _evidence_file(ticket["id"])) is not None})
        dedicated = [ticket_id for ticket_id in covering_ids if ticket_id != UMBRELLA_TICKET]
        rows.append(
            {
                "ac": ac,
                "tickets": covering_ids,
                "dedicated_tickets": dedicated,
                "status": _derive_status(covering),
                "evidence": evidence,
            }
        )
    summary: dict[str, int] = {}
    for row in rows:
        summary[row["status"]] = summary.get(row["status"], 0) + 1
    return {
        "schema_version": 1,
        "kind": "farol_v2_acceptance_matrix",
        "umbrella_ticket": UMBRELLA_TICKET,
        "summary": summary,
        "unattributed": [row["ac"] for row in rows if not row["dedicated_tickets"]],
        "rows": rows,
    }


def backlog_traceability_findings(matrix: dict[str, Any]) -> list[dict[str, str]]:
    """Report where the backlog's AC->ticket claims disagree with the tickets."""

    backlog = SPEC_ROOT / "backlog.md"
    try:
        text = backlog.read_text(encoding="utf-8")
    except OSError as exc:
        return [{"code": "backlog_unreadable", "artifact": "specs/farol-2/backlog.md", "message": str(exc)}]
    # Backlog shorthand abbreviates ranges, e.g. ``AC-001–003`` (second number
    # drops the prefix) and ``TK-016–019``, and may list several ACs on one line.
    claims: dict[str, set[str]] = {}
    for line in text.splitlines():
        if not line.startswith("- AC-"):
            continue
        ac_field, _, ticket_field = line[len("- ") :].partition(":")
        ac_field = ac_field.strip()
        claimed: set[str] = set()
        for part in ticket_field.rstrip(". ").split("/"):
            part = part.strip()
            expand = re.fullmatch(r"TK-(\d{3})[–-](\d{3})", part)
            if expand:
                claimed.update(f"TK-{n:03d}" for n in range(int(expand.group(1)), int(expand.group(2)) + 1))
            elif re.fullmatch(r"TK-\d{3}", part):
                claimed.add(part)
        for piece in re.finditer(r"AC-(\d{3})[–-](\d{3})", ac_field):
            for index in range(int(piece.group(1)), int(piece.group(2)) + 1):
                claims[f"AC-{index:03d}"] = claimed
        for piece in re.finditer(r"(?<![\d–-])AC-(\d{3})", ac_field):
            index = int(piece.group(1))
            claims.setdefault(f"AC-{index:03d}", claimed)
    findings: list[dict[str, str]] = []
    for row in matrix["rows"]:
        claimed = claims.get(row["ac"])
        if claimed is None:
            findings.append(
                {
                    "code": "backlog_missing_ac",
                    "artifact": "specs/farol-2/backlog.md",
                    "message": f"{row['ac']} is not covered by the backlog traceability map",
                }
            )
            continue
        # The backlog groups AC ranges against ticket ranges, so it is
        # intentionally coarse. The one claim that is always checkable is
        # whether an AC the backlog says has a dedicated ticket actually has
        # one: if the tickets never reference it, the traceability is wrong.
        if not row["dedicated_tickets"]:
            claimed_dedicated = sorted(ticket for ticket in claimed if ticket != UMBRELLA_TICKET)
            if claimed_dedicated:
                findings.append(
                    {
                        "code": "backlog_unattributed_claim",
                        "artifact": "specs/farol-2/backlog.md",
                        "message": (
                            f"{row['ac']} is claimed under {claimed_dedicated} but no ticket "
                            "references it in acceptance_refs"
                        ),
                    }
                )
    return findings


def render_markdown(matrix: dict[str, Any]) -> str:
    lines = [
        "# Matriz de aceite Farol 2.0",
        "",
        "Gerado por `scripts/check_acceptance_matrix.py`. Cada AC deriva seu estado",
        "dos tickets cobertos por `acceptance_refs` (excluindo o guarda-chuva",
        f"`{matrix['umbrella_ticket']}`). `verified` exige que todo ticket cobertor",
        "esteja `verified`; qualquer cobertura `in_progress` mantém o AC em",
        "`in_progress`, com o blocker registrado no ticket/evidência.",
        "",
        f"Resumo: {json.dumps(matrix['summary'], ensure_ascii=False, sort_keys=True)}",
        "",
        ("Sem ticket dedicado (só o guarda-chuva): " + (", ".join(matrix["unattributed"]) or "nenhum")),
        "",
        "| AC | Tickets cobertores | Estado | Evidência |",
        "| --- | --- | --- | --- |",
    ]
    for row in matrix["rows"]:
        tickets = ", ".join(row["tickets"]) or "—"
        evidence = ", ".join(row["evidence"]) or "—"
        lines.append(f"| {row['ac']} | {tickets} | {row['status']} | {evidence} |")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the artifact drifts from the tickets")
    parser.add_argument("--write", action="store_true", help="regenerate the artifact")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    matrix = build_matrix()
    artifact = SPEC_ROOT / "acceptance-matrix.md"
    if args.write:
        artifact.write_text(render_markdown(matrix), encoding="utf-8")
    if args.json:
        report = {
            **matrix,
            "backlog_findings": backlog_traceability_findings(matrix),
        }
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.check:
        expected = render_markdown(matrix)
        observed = artifact.read_text(encoding="utf-8") if artifact.is_file() else ""
        backlog_findings = backlog_traceability_findings(matrix)
        if observed != expected:
            print(
                json.dumps(
                    {
                        "schema_version": 1,
                        "ok": False,
                        "code": "acceptance_matrix_drift",
                        "message": "specs/farol-2/acceptance-matrix.md is stale; run with --write",
                    },
                    ensure_ascii=False,
                )
            )
            return 1
        report = {
            "schema_version": 1,
            "ok": not backlog_findings,
            "summary": matrix["summary"],
            "unattributed": matrix["unattributed"],
            "backlog_findings": backlog_findings,
        }
        print(json.dumps(report, ensure_ascii=False))
        return 0 if report["ok"] else 1
    print(render_markdown(matrix))
    return 0


if __name__ == "__main__":
    sys.exit(main())
