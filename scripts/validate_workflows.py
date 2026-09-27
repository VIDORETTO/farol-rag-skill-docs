"""Validate GitHub Actions YAML and require executable job steps."""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from pathlib import Path
from typing import Any

import yaml

_EXTRA_GROUP = re.compile(r"\.\[([A-Za-z0-9_.-]+(?:,[A-Za-z0-9_.-]+)*)\]")


def validate_workflows(workflows_dir: Path, *, project_file: Path | None = None) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    paths = sorted([*workflows_dir.glob("*.yml"), *workflows_dir.glob("*.yaml")])
    if project_file is None:
        inferred_project = workflows_dir.parent.parent / "pyproject.toml"
        project_file = inferred_project if inferred_project.is_file() else None
    declared_extras: set[str] | None = None
    if project_file is not None:
        try:
            with project_file.open("rb") as handle:
                project_metadata = tomllib.load(handle)
            optional_dependencies = project_metadata.get("project", {}).get("optional-dependencies", {})
            if isinstance(optional_dependencies, dict):
                declared_extras = set(optional_dependencies)
        except (OSError, tomllib.TOMLDecodeError):
            findings.append(
                {
                    "code": "project_metadata_invalid",
                    "file": project_file.name,
                    "message": "project optional-dependency groups could not be read",
                }
            )
    for path in paths:
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError):
            findings.append(
                {
                    "code": "workflow_yaml_invalid",
                    "file": path.name,
                    "message": "workflow is not valid UTF-8 YAML",
                }
            )
            continue
        if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), dict):
            findings.append(
                {"code": "workflow_jobs_missing", "file": path.name, "message": "workflow jobs must be a mapping"}
            )
            continue
        for name, job in payload["jobs"].items():
            if not isinstance(job, dict) or not isinstance(job.get("steps"), list) or not job["steps"]:
                findings.append(
                    {
                        "code": "job_steps_missing",
                        "file": path.name,
                        "message": f"workflow job has no executable steps: {name}",
                    }
                )
                continue
            if declared_extras is None:
                continue
            for step in job["steps"]:
                run = step.get("run") if isinstance(step, dict) else None
                if not isinstance(run, str):
                    continue
                for group in _EXTRA_GROUP.findall(run):
                    for extra in group.split(","):
                        if extra not in declared_extras:
                            findings.append(
                                {
                                    "code": "workflow_extra_undeclared",
                                    "file": path.name,
                                    "message": f"workflow installs an undeclared project extra: {extra}",
                                }
                            )
    return {
        "schema_version": 1,
        "ok": not findings and bool(paths),
        "workflow_count": len(paths),
        "findings": findings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflows", type=Path, default=Path(__file__).resolve().parents[1] / ".github/workflows")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = validate_workflows(args.workflows.expanduser().resolve())
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
