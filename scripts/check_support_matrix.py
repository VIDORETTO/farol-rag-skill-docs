"""Validate that published support and workflow gates agree."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "docs" / "SUPPORT-MATRIX.json"
_ACTION = re.compile(r"^\s*-?\s*uses:\s+[^\s]+@([^\s#]+)", re.MULTILINE)


def _load_matrix(path: Path = MATRIX_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("support matrix must be an object")
    return value


def _workflow_text(workflows_dir: Path = ROOT / ".github" / "workflows") -> str:
    paths = sorted([*workflows_dir.glob("*.yml"), *workflows_dir.glob("*.yaml")])
    return "\n".join(path.read_text(encoding="utf-8") for path in paths)


def _workflow_jobs(workflows: str) -> set[str]:
    return set(re.findall(r"^  ([A-Za-z0-9_-]+):\s*$", workflows, re.MULTILINE))


def _workflow_job_blocks(workflows: str) -> dict[str, str]:
    """Return the text owned by each job for claim-to-gate verification."""

    blocks: dict[str, list[str]] = {}
    current: str | None = None
    in_jobs = False
    for line in workflows.splitlines():
        if line == "jobs:":
            in_jobs = True
            current = None
            continue
        if in_jobs and line and not line[0].isspace():
            in_jobs = False
            current = None
            continue
        if not in_jobs:
            continue
        match = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if match:
            current = match.group(1)
            blocks[current] = [line]
        elif current is not None:
            blocks[current].append(line)
    return {name: "\n".join(lines) for name, lines in blocks.items()}


def _executable_job_text(block: str) -> str:
    """Exclude comments and steps statically disabled with ``if: false``."""

    lines = block.splitlines()
    kept: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        step = re.match(r"^(\s{6})-\s+", line)
        if not step:
            if not line.lstrip().startswith("#"):
                kept.append(line)
            index += 1
            continue
        indent = len(step.group(1))
        end = index + 1
        while end < len(lines) and not re.match(rf"^\s{{{indent}}}-\s+", lines[end]):
            end += 1
        chunk = [value for value in lines[index:end] if not value.lstrip().startswith("#")]
        disabled = any(
            re.match(r"^\s+if:\s*(?:false|\$\{\{\s*false\s*\}\})\s*(?:#.*)?$", value, re.IGNORECASE) for value in chunk
        )
        if not disabled:
            kept.extend(chunk)
        index = end
    return "\n".join(kept)


def _artifact_paths(block: str) -> list[str]:
    """Extract inline and block-scalar upload paths from a job."""

    lines = block.splitlines()
    paths: list[str] = []
    index = 0
    while index < len(lines):
        match = re.match(r"^(\s*)path:\s*(.*?)\s*$", lines[index])
        if not match:
            index += 1
            continue
        indent = len(match.group(1))
        value = match.group(2).split(" #", 1)[0].strip().strip("'\"")
        if value not in {"", "|", ">", "|-", ">-"}:
            paths.append(value)
            index += 1
            continue
        index += 1
        while index < len(lines):
            child = lines[index]
            if child.strip() and len(child) - len(child.lstrip()) <= indent:
                break
            candidate = child.strip().split(" #", 1)[0].strip().strip("'\"")
            if candidate and not candidate.startswith("#"):
                paths.append(candidate)
            index += 1
    return paths


def audit(*, matrix_path: Path = MATRIX_PATH, workflows_dir: Path = ROOT / ".github" / "workflows") -> dict[str, Any]:
    matrix = _load_matrix(matrix_path)
    findings: list[dict[str, str]] = []
    python = matrix.get("python") if isinstance(matrix.get("python"), dict) else {}
    supported = python.get("supported") if isinstance(python.get("supported"), list) else []
    tolerated = python.get("tolerated") if isinstance(python.get("tolerated"), list) else []
    runner_values = matrix.get("runners") if isinstance(matrix.get("runners"), list) else []
    if not supported or python.get("minimum") != supported[0]:
        findings.append(
            {"code": "invalid_python_matrix", "message": "minimum Python must be the first supported version"}
        )
    overlap = sorted(set(supported) & set(tolerated))
    if overlap:
        findings.append(
            {
                "code": "supported_tolerated_overlap",
                "message": f"Python versions cannot be both supported and tolerated: {', '.join(overlap)}",
            }
        )
    try:
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    except OSError as exc:
        findings.append({"code": "pyproject_unreadable", "message": str(exc)})
        pyproject = ""
    minimum = str(python.get("minimum", ""))
    if f'requires-python = ">={minimum}"' not in pyproject:
        findings.append({"code": "python_floor_drift", "message": "pyproject minimum differs from support matrix"})
    workflows = _workflow_text(workflows_dir)
    for version in supported:
        if f'"{version}"' not in workflows:
            findings.append(
                {"code": "python_version_missing", "message": f"supported Python {version} is absent from CI"}
            )
    for version in tolerated:
        if f'"{version}"' in workflows:
            findings.append(
                {
                    "code": "tolerated_version_in_matrix",
                    "message": f"tolerated Python {version} must not be advertised as supported CI",
                }
            )
    job_blocks = _workflow_job_blocks(workflows)
    executable_blocks = {name: _executable_job_text(block) for name, block in job_blocks.items()}
    executable_workflows = "\n".join(executable_blocks.values())
    for action_revision in _ACTION.findall(executable_workflows):
        if not re.fullmatch(r"[0-9a-f]{40}", action_revision):
            findings.append(
                {"code": "mutable_action", "message": "workflow actions must use full immutable commit SHAs"}
            )
    expected_commands = {
        "pytest": "python -m pytest",
        "ruff": "python -m ruff check",
        "format": "python -m ruff format --check",
        "doctor": "python -m docops doctor",
        "dependency-audit": "scripts/audit_dependencies.py",
        "pip-check": "python -m pip check",
        "workflow-yaml": "scripts/validate_workflows.py",
        "release-audit": "scripts/audit_release.py",
        "clean-clone": "scripts/verify_clean_clone.py",
        "contract-conformance": "scripts/check_contracts.py",
        "ragflow-profile": "scripts/run_release_gates.py --profile ragflow",
        "ragflow": "scripts/run_release_gates.py --profile ragflow",
        "wheel-create-validate-evaluate": "scripts/verify_wheel.py",
        "supply-chain": "scripts/generate_supply_chain.py",
        "supply-chain-verify": "scripts/verify_supply_chain.py",
        "candidate-audit": "scripts/audit_release.py --candidate",
        "candidate-bundle": "scripts/prepare_candidate.py",
        "candidate-verify": "scripts/verify_candidate.py",
        "public-seams": "scripts/check_public_seams.py",
    }
    for gate, marker in expected_commands.items():
        if marker not in executable_workflows:
            findings.append({"code": "gate_missing", "message": f"workflow does not execute {gate}: {marker}"})
    if "scripts/check_support_matrix.py" not in executable_workflows:
        findings.append({"code": "matrix_gate_missing", "message": "CI must validate the normative support matrix"})
    try:
        release_doc = (ROOT / "docs" / "RELEASE.md").read_text(encoding="utf-8")
    except OSError as exc:
        findings.append({"code": "release_runbook_unreadable", "message": str(exc)})
        release_doc = ""
    profiles = matrix.get("profiles") if isinstance(matrix.get("profiles"), dict) else {}
    gate_names = matrix.get("gates") if isinstance(matrix.get("gates"), dict) else {}
    for profile_name, profile in profiles.items():
        if not isinstance(profile, dict):
            findings.append({"code": "invalid_profile", "message": f"profile must be an object: {profile_name}"})
            continue
        profile_gates = profile.get("gates") if isinstance(profile.get("gates"), list) else []
        for gate in profile_gates:
            if gate not in gate_names:
                findings.append(
                    {
                        "code": "profile_gate_missing",
                        "message": f"profile {profile_name} references unknown gate: {gate}",
                    }
                )
    wrappers = matrix.get("wrappers") if isinstance(matrix.get("wrappers"), dict) else {}
    for wrapper_group, paths in wrappers.items():
        if not isinstance(paths, list):
            findings.append(
                {"code": "invalid_wrapper_group", "message": f"wrapper group must be a list: {wrapper_group}"}
            )
            continue
        for relative in paths:
            if not isinstance(relative, str) or not (ROOT / relative).is_file():
                findings.append({"code": "wrapper_missing", "message": f"declared wrapper is missing: {relative}"})
            elif relative not in executable_workflows:
                findings.append(
                    {
                        "code": "wrapper_unexercised",
                        "message": f"workflow does not exercise declared wrapper: {relative}",
                    }
                )
    skips = matrix.get("skips") if isinstance(matrix.get("skips"), list) else []
    for skip in skips:
        if (
            not isinstance(skip, dict)
            or not isinstance(skip.get("condition"), str)
            or not isinstance(skip.get("observable"), str)
        ):
            findings.append(
                {"code": "invalid_skip_policy", "message": "each skip policy needs condition and observable"}
            )
    jobs = _workflow_jobs(workflows)
    artifact_requirements = {
        "package": {
            "code": "candidate_artifact_missing",
            "markers": (
                "actions/upload-artifact@",
                "name: candidate-2.0.0rc1-${{ github.sha }}",
                "path: artifacts/candidate-2.0.0rc1",
                "if-no-files-found: error",
            ),
        },
        "ragflow": {
            "code": "integration_artifact_missing",
            "markers": (
                "actions/upload-artifact@",
                "name: integration-evidence-${{ github.sha }}",
                "artifacts/ragflow-release-gates.json",
                "if-no-files-found: error",
            ),
        },
    }
    for job, requirement in artifact_requirements.items():
        block = executable_blocks.get(job, "")
        safe_rag_artifacts = {
            "artifacts/ragflow-release-gates.json",
        }
        if job == "ragflow" and any(path not in safe_rag_artifacts for path in _artifact_paths(block)):
            findings.append(
                {
                    "code": "integration_artifact_unsafe",
                    "message": "workflow job ragflow must retain an explicit safe file list, not the full RAG directory",
                }
            )
        missing = [marker for marker in requirement["markers"] if marker not in block]
        if missing:
            findings.append(
                {
                    "code": requirement["code"],
                    "message": f"workflow job {job} must retain its audited evidence; missing {', '.join(missing)}",
                }
            )
    claims = matrix.get("claims") if isinstance(matrix.get("claims"), list) else []
    for claim in claims:
        if not isinstance(claim, dict):
            findings.append({"code": "invalid_claim", "message": "support claims must be objects"})
            continue
        profile = claim.get("profile")
        job = claim.get("job")
        if not isinstance(profile, str) or profile not in profiles:
            findings.append(
                {"code": "unknown_profile", "message": f"support claim references unknown profile: {profile}"}
            )
        elif isinstance(profiles.get(profile), dict):
            for gate_name in profiles[profile].get("gates", []):
                for requirement in gate_names.get(gate_name, []) if isinstance(gate_names.get(gate_name), list) else []:
                    marker = expected_commands.get(requirement)
                    if marker and marker not in executable_workflows:
                        findings.append(
                            {
                                "code": "profile_gate_unexecuted",
                                "message": f"profile {profile} requires {requirement}: {marker}",
                            }
                        )
        if not isinstance(job, str) or job not in jobs:
            findings.append({"code": "claim_job_missing", "message": f"support claim has no workflow job: {job}"})
        else:
            job_text = executable_blocks.get(job, "")
            profile_value = profiles.get(profile) if isinstance(profile, str) else None
            profile_gate_names = profile_value.get("gates", []) if isinstance(profile_value, dict) else []
            for gate_name in profile_gate_names if isinstance(profile_gate_names, list) else []:
                requirements = gate_names.get(gate_name) if isinstance(gate_names.get(gate_name), list) else []
                direct_marker = expected_commands.get(gate_name) or expected_commands.get(
                    str(gate_name).replace("_", "-")
                )
                markers = [direct_marker] if direct_marker else [expected_commands.get(item) for item in requirements]
                missing = [marker for marker in markers if marker and marker not in job_text]
                if missing:
                    findings.append(
                        {
                            "code": "claim_gate_unexecuted_by_job",
                            "message": f"claim {claim.get('id', '<unknown>')} job {job} does not execute profile gate {gate_name}",
                        }
                    )
            claim_versions = claim.get("python_versions", claim.get("python"))
            if isinstance(claim_versions, str):
                claim_versions = [claim_versions]
            if claim_versions is not None:
                if isinstance(claim_versions, list):
                    for version in claim_versions:
                        if version in tolerated:
                            findings.append(
                                {
                                    "code": "claim_tolerated_python",
                                    "message": f"claim {claim.get('id', '<unknown>')} advertises tolerated Python {version} as supported",
                                }
                            )
                        elif version not in supported:
                            findings.append(
                                {
                                    "code": "claim_unknown_python",
                                    "message": f"claim {claim.get('id', '<unknown>')} references unknown Python {version}",
                                }
                            )
                if not isinstance(claim_versions, list) or any(
                    not isinstance(version, str) or f'"{version}"' not in job_text for version in claim_versions
                ):
                    findings.append(
                        {
                            "code": "claim_python_missing",
                            "message": f"claim {claim.get('id', '<unknown>')} Python versions are absent from job {job}",
                        }
                    )
        platforms = claim.get("platforms", claim.get("platform"))
        if isinstance(platforms, str):
            platforms = [platforms]
        if not isinstance(platforms, list) or not platforms:
            findings.append(
                {"code": "invalid_claim_platform", "message": "support claim must name at least one platform"}
            )
        else:
            for platform in platforms:
                if not isinstance(platform, str) or platform not in runner_values:
                    findings.append(
                        {
                            "code": "claim_platform_unknown",
                            "message": f"support claim platform is absent from the declared runners: {platform}",
                        }
                    )
                elif platform not in executable_workflows:
                    findings.append(
                        {
                            "code": "claim_platform_missing",
                            "message": f"support claim platform is absent from workflows: {platform}",
                        }
                    )
                elif isinstance(job, str) and job in jobs and platform not in executable_blocks.get(job, ""):
                    findings.append(
                        {
                            "code": "claim_platform_unexecuted_by_job",
                            "message": f"claim {claim.get('id', '<unknown>')} platform is absent from job {job}",
                        }
                    )
    order = matrix.get("order")
    if isinstance(order, list):
        if len(order) != len(set(order)):
            findings.append({"code": "duplicate_gate_order", "message": "support order must not repeat a stage"})
        known_stages = {
            "bootstrap",
            "doctor",
            "dependencies",
            "support-matrix",
            "contracts",
            "pytest",
            "ruff",
            "clean-clone",
            "wheel",
            "supply-chain",
            "supply-chain-verify",
            "rag",
            "ragflow",
            "candidate-audit",
            "candidate-bundle",
            "candidate-verify",
            "public-seams",
            "dependency-audit",
            "pip-check",
            "workflow-yaml",
        }
        for stage in order:
            if stage not in known_stages:
                findings.append(
                    {"code": "unknown_gate_order", "message": f"support order contains an unknown stage: {stage}"}
                )
            marker = expected_commands.get(stage) if isinstance(stage, str) else None
            if marker and marker not in release_doc:
                findings.append(
                    {"code": "runbook_gate_missing", "message": f"release runbook does not execute {stage}: {marker}"}
                )
    return {"schema_version": 1, "ok": not findings, "matrix": matrix, "findings": findings}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=MATRIX_PATH)
    parser.add_argument("--workflows", type=Path, default=ROOT / ".github" / "workflows")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = audit(matrix_path=args.matrix.expanduser().resolve(), workflows_dir=args.workflows.expanduser().resolve())
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
