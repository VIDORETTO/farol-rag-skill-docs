"""Run the real, pinned local Docling OCR integration contract fail-closed."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import os
import re
import subprocess
import sys
from typing import Any

EXPECTED_VERSIONS = {"docling": "2.129.0", "onnxruntime": "1.30.0"}
DEFAULT_TIMEOUT_SECONDS = 900.0
SUMMARY = re.compile(r"(?P<passed>\d+) passed|(?P<failed>\d+) failed|(?P<skipped>\d+) skipped")


def _report(payload: dict[str, Any], exit_code: int) -> int:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return exit_code


def _counts(output: str) -> dict[str, int]:
    result = {"passed": 0, "failed": 0, "skipped": 0}
    for match in SUMMARY.finditer(output):
        for key in result:
            if match.group(key) is not None:
                result[key] = max(result[key], int(match.group(key)))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", default="tests/spikes/test_docling_ocr_contract.py")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        return _report(
            {"schema_version": 1, "ok": False, "status": "blocked", "reason": "timeout_invalid"},
            2,
        )
    observed: dict[str, str] = {}
    missing: list[str] = []
    mismatched: list[str] = []
    for package, expected in EXPECTED_VERSIONS.items():
        try:
            observed[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            missing.append(package)
            continue
        if observed[package] != expected:
            mismatched.append(package)
    if missing:
        return _report(
            {
                "schema_version": 1,
                "ok": False,
                "status": "blocked",
                "reason": "dependencies_missing",
                "missing": missing,
                "expected_versions": EXPECTED_VERSIONS,
            },
            1,
        )
    if mismatched:
        return _report(
            {
                "schema_version": 1,
                "ok": False,
                "status": "blocked",
                "reason": "dependency_version_mismatch",
                "mismatched": mismatched,
                "expected_versions": EXPECTED_VERSIONS,
                "observed_versions": observed,
            },
            1,
        )
    environment = dict(os.environ)
    environment["DOCOPS_OCR_INTEGRATION"] = "1"
    command = [sys.executable, "-m", "pytest", "-q", "-ra", "-m", "integration", args.test]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env=environment,
            timeout=float(args.timeout),
        )
    except subprocess.TimeoutExpired as exc:
        return _report(
            {
                "schema_version": 1,
                "ok": False,
                "status": "failed",
                "reason": "integration_timeout",
                "timeout_seconds": float(args.timeout),
                "stdout_tail": str(exc.output or "")[-4000:],
                "stderr_tail": str(exc.stderr or "")[-4000:],
            },
            124,
        )
    stdout = str(completed.stdout or "")[-4000:]
    stderr = str(completed.stderr or "")[-4000:]
    counts = _counts(stdout + "\n" + stderr)
    if completed.returncode == 0 and counts["passed"] > 0 and counts["skipped"] == 0:
        status, reason, code = "passed", None, 0
    elif completed.returncode == 0 and counts["skipped"] > 0:
        status, reason, code = "not_run", "integration_not_run", 1
    else:
        status, reason, code = "failed", "contract_test_failed", completed.returncode or 1
    return _report(
        {
            "schema_version": 1,
            "ok": status == "passed",
            "status": status,
            "reason": reason,
            "versions": observed,
            "integration": counts,
            "timeout_seconds": float(args.timeout),
            "stdout_tail": stdout,
            "stderr_tail": stderr,
        },
        code,
    )


if __name__ == "__main__":
    raise SystemExit(main())
