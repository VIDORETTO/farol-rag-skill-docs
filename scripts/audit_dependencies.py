"""Run a fail-closed dependency audit for the Farol 2.0 lock."""

from __future__ import annotations

import argparse
import hashlib
import json
import site
import subprocess
import sys
from pathlib import Path
from typing import Any


def _command(*, requirements: Path | None = None, local: bool = False) -> list[str]:
    command = [sys.executable, "-m", "pip_audit", "--format", "json", "--progress-spinner", "off"]
    if requirements is not None:
        command.extend(["--requirement", str(requirements), "--strict"])
    if local:
        command.append("--skip-editable")
        for path in site.getsitepackages():
            command.extend(["--path", path])
    return command


def _run(*, requirements: Path | None = None, local: bool = False) -> dict[str, Any]:
    completed = subprocess.run(
        _command(requirements=requirements, local=local), check=False, capture_output=True, text=True
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"pip-audit did not return JSON: {completed.stderr[-2000:]}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("dependencies"), list):
        raise RuntimeError("pip-audit returned an unexpected JSON shape")
    return {
        "source": "local" if local else "requirements",
        "exit_code": completed.returncode,
        **payload,
        "stderr": completed.stderr,
    }


def _raw_findings(audits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for audit in audits:
        for dependency in audit.get("dependencies", []):
            for vulnerability in dependency.get("vulns", []):
                if isinstance(vulnerability, dict):
                    findings.append(
                        {
                            "source": audit.get("source"),
                            "package": dependency.get("name"),
                            "version": dependency.get("version"),
                            "id": vulnerability.get("id"),
                            "aliases": vulnerability.get("aliases", []),
                            "fix_versions": vulnerability.get("fix_versions", []),
                        }
                    )
    return findings


def _write_evidence(directory: Path, audits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    directory.mkdir(parents=True, exist_ok=True)
    summaries = []
    for audit in audits:
        source = str(audit["source"])
        stdout = json.dumps({key: value for key, value in audit.items() if key not in {"stderr"}}, sort_keys=True)
        stderr = str(audit.get("stderr", ""))
        (directory / f"{source}.stdout.json").write_text(stdout + "\n", encoding="utf-8")
        (directory / f"{source}.stderr.log").write_text(stderr, encoding="utf-8")
        (directory / f"{source}.exit-code").write_text(f"{audit['exit_code']}\n", encoding="ascii")
        summaries.append({"source": source, "exit_code": audit["exit_code"]})
    return summaries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requirements", type=Path, required=True)
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--evidence-dir", type=Path)
    args = parser.parse_args(argv)
    requirements = args.requirements.expanduser().resolve()
    if not requirements.is_file():
        print(json.dumps({"ok": False, "status": "blocked", "error": "requirements file missing"}))
        return 2
    audits = [_run(requirements=requirements)]
    if args.local:
        audits.append(_run(local=True))
    findings = _raw_findings(audits)
    collection_failed = any(item["exit_code"] not in {0, 1} for item in audits)
    evidence = (
        _write_evidence(args.evidence_dir.resolve(), audits)
        if args.evidence_dir
        else [{"source": item["source"], "exit_code": item["exit_code"]} for item in audits]
    )
    result = {
        "schema_version": 1,
        "ok": not collection_failed and not findings,
        "audits": evidence,
        "raw_audit": {
            "status": "clean" if not findings and not collection_failed else "findings",
            "ok": not findings and not collection_failed,
            "findings": findings,
        },
        "policy_evaluation": {
            "status": "pass" if not findings and not collection_failed else "fail",
            "ok": not findings and not collection_failed,
        },
        "policy": {
            "backend": "ragflow",
            "legacy_dependencies": "removed",
            "lock_sha256": hashlib.sha256(requirements.read_bytes()).hexdigest(),
        },
    }
    if args.evidence_dir:
        (args.evidence_dir.resolve() / "summary.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 2 if collection_failed else (0 if result["ok"] else 1)


if __name__ == "__main__":
    raise SystemExit(main())
