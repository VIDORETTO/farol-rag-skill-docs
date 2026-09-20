"""Run the opt-in RAGFlow contract gate with fail-closed external checks."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from typing import Any

EXPECTED_SDK_VERSION = "0.27.2"
IMAGE_DIGEST_PATTERN = re.compile(r".+@sha256:[0-9a-f]{64}")
PYTEST_COUNT_PATTERN = re.compile(
    r"(?P<count>\d+)\s+(?P<label>passed|failed|skipped|xfailed|xpassed|error|errors)\b",
    re.IGNORECASE,
)
PYTEST_DURATION_PATTERN = re.compile(r"\bin\s+[0-9]+(?:\.[0-9]+)?s\b", re.IGNORECASE)
NO_TESTS_PATTERN = re.compile(r"\bno tests ran\b", re.IGNORECASE)
BLOCKED_PATTERN = re.compile(
    r"^\s*(?:status=)?blocked\b|^\s*blocked:",
    re.IGNORECASE | re.MULTILINE,
)
NOT_RUN_PATTERN = re.compile(
    r"^\s*(?:status=)?not[-_]run\b|SKIPPED.*\bnot[-_]run:",
    re.IGNORECASE | re.MULTILINE,
)
REQUIRED_ENVIRONMENT = (
    "DOCOPS_RAGFLOW_ENDPOINT",
    "DOCOPS_RAGFLOW_TOKEN",
    "DOCOPS_RAGFLOW_IMAGE_DIGEST",
    "DOCOPS_RAGFLOW_SDK_VERSION",
)
DEFAULT_TIMEOUT_SECONDS = 900.0


def _redact(value: str, secrets: tuple[str, ...]) -> str:
    redacted = value
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "<redacted>")
    return redacted[-4000:]


def _report(payload: dict[str, Any], *, exit_code: int) -> int:
    # Keep the report shape stable for both preflight and subprocess outcomes.
    # Empty tails mean that no subprocess was started; executed subprocesses
    # replace them with redacted output below.
    payload.setdefault("stdout_tail", "")
    payload.setdefault("stderr_tail", "")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return exit_code


def _pytest_counts(output: str) -> dict[str, int]:
    """Extract the final pytest result counts without trusting its exit code."""

    counts = {
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "xfailed": 0,
        "xpassed": 0,
        "error": 0,
    }
    lines = [line for line in output.splitlines() if PYTEST_COUNT_PATTERN.search(line)]
    if not lines:
        return counts

    # Pytest normally emits one terminal summary line with a duration.  Prefer
    # it so counts printed by a test itself cannot be mistaken for test results.
    summary = next(
        (line for line in reversed(lines) if PYTEST_DURATION_PATTERN.search(line)),
        lines[-1],
    )
    for match in PYTEST_COUNT_PATTERN.finditer(summary):
        label = match.group("label").casefold()
        if label == "errors":
            label = "error"
        counts[label] += int(match.group("count"))
    return counts


def _classify_integration_result(
    *,
    returncode: int,
    stdout: str,
    stderr: str,
) -> tuple[str, str | None, dict[str, int | bool | str]]:
    """Classify the integration result independently from pytest's exit code."""

    output = f"{stdout}\n{stderr}"
    counts = _pytest_counts(output)
    has_blocked = bool(BLOCKED_PATTERN.search(output))
    has_not_run = bool(NOT_RUN_PATTERN.search(output))
    no_tests = bool(NO_TESTS_PATTERN.search(output)) or (returncode == 5 and not any(counts.values()))
    failed = counts["failed"] + counts["error"] + counts["xfailed"]
    passed = counts["passed"] + counts["xpassed"]
    executed = passed + failed

    integration = {
        "filter": "integration",
        "executed": executed,
        "passed": passed,
        "failed": failed,
        "skipped": counts["skipped"],
        "xfailed": counts["xfailed"],
        "xpassed": counts["xpassed"],
        "error": counts["error"],
        "blocked": has_blocked,
        "not_run": has_not_run or no_tests or counts["skipped"] > 0,
    }

    # A real failure wins over a diagnostic word such as "blocked" in the
    # traceback.  Otherwise preserve explicit blocked/not-run semantics before
    # considering the subprocess exit code.
    if failed:
        return "failed", "contract_test_failed", integration
    if has_blocked:
        return "blocked", "integration_blocked", integration
    if has_not_run or no_tests or counts["skipped"] > 0:
        return "not_run", "integration_not_run", integration
    if returncode != 0:
        return "failed", "contract_test_failed", integration
    if passed > 0:
        return "passed", None, integration
    return "not_run", "integration_not_run", integration


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", default="tests/spikes/test_ragflow_contract.py")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--json", action="store_true", help="emit one machine-readable report line")
    args = parser.parse_args(argv)
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        return _report(
            {
                "schema_version": 1,
                "ok": False,
                "status": "blocked",
                "reason": "timeout_invalid",
                "timeout_seconds": args.timeout,
            },
            exit_code=2,
        )

    values = {name: os.environ.get(name, "").strip() for name in REQUIRED_ENVIRONMENT}
    missing = [name for name, value in values.items() if not value]
    if missing:
        return _report(
            {
                "schema_version": 1,
                "ok": False,
                "status": "blocked",
                "reason": "missing_external_inputs",
                "missing": missing,
                "sdk_version": EXPECTED_SDK_VERSION,
            },
            exit_code=1,
        )
    if values["DOCOPS_RAGFLOW_SDK_VERSION"] != EXPECTED_SDK_VERSION:
        return _report(
            {
                "schema_version": 1,
                "ok": False,
                "status": "blocked",
                "reason": "sdk_version_mismatch",
                "expected_sdk_version": EXPECTED_SDK_VERSION,
            },
            exit_code=1,
        )
    if not IMAGE_DIGEST_PATTERN.fullmatch(values["DOCOPS_RAGFLOW_IMAGE_DIGEST"]):
        return _report(
            {
                "schema_version": 1,
                "ok": False,
                "status": "blocked",
                "reason": "image_digest_unpinned",
                "expected": "repository@sha256:<64 hex>",
            },
            exit_code=1,
        )
    try:
        import ragflow_sdk  # type: ignore[import-not-found]
    except ImportError:
        return _report(
            {
                "schema_version": 1,
                "ok": False,
                "status": "blocked",
                "reason": "sdk_missing",
                "expected_sdk_version": EXPECTED_SDK_VERSION,
            },
            exit_code=1,
        )
    observed_version = str(getattr(ragflow_sdk, "__version__", ""))
    if observed_version != EXPECTED_SDK_VERSION:
        return _report(
            {
                "schema_version": 1,
                "ok": False,
                "status": "blocked",
                "reason": "installed_sdk_version_mismatch",
                "expected_sdk_version": EXPECTED_SDK_VERSION,
                "observed_sdk_version": observed_version or None,
            },
            exit_code=1,
        )

    environment = dict(os.environ)
    environment["DOCOPS_RAGFLOW_INTEGRATION"] = "1"
    secrets = tuple(values[name] for name in REQUIRED_ENVIRONMENT)
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
        stdout = _redact(str(exc.output or ""), secrets)
        stderr = _redact(str(exc.stderr or ""), secrets)
        return _report(
            {
                "schema_version": 1,
                "ok": False,
                "status": "failed",
                "reason": "integration_timeout",
                "sdk_version": observed_version,
                "timeout_seconds": float(args.timeout),
                "stdout_tail": stdout,
                "stderr_tail": stderr,
            },
            exit_code=124,
        )
    stdout = _redact(str(completed.stdout or ""), secrets)
    stderr = _redact(str(completed.stderr or ""), secrets)
    status, reason, integration = _classify_integration_result(
        returncode=completed.returncode,
        stdout=stdout,
        stderr=stderr,
    )
    payload = {
        "schema_version": 1,
        "ok": status == "passed",
        "status": status,
        "reason": reason,
        "sdk_version": observed_version,
        "integration": integration,
        "timeout_seconds": float(args.timeout),
        "stdout_tail": stdout,
        "stderr_tail": stderr,
    }
    exit_code = 0 if status == "passed" else completed.returncode or 1
    return _report(payload, exit_code=exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
