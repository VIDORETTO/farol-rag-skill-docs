from __future__ import annotations

from pathlib import Path

from scripts.validate_workflows import validate_workflows


def test_repository_workflows_are_valid_yaml_with_executable_jobs() -> None:
    report = validate_workflows(Path(".github/workflows"))

    assert report["ok"] is True
    assert report["workflow_count"] >= 2


def test_workflow_validator_rejects_invalid_yaml_and_missing_steps(tmp_path: Path) -> None:
    (tmp_path / "invalid.yml").write_text("jobs: [\n", encoding="utf-8")
    (tmp_path / "empty.yml").write_text("name: Empty\njobs:\n  noop:\n    runs-on: ubuntu-latest\n", encoding="utf-8")

    report = validate_workflows(tmp_path)

    assert report["ok"] is False
    assert {finding["code"] for finding in report["findings"]} == {"workflow_yaml_invalid", "job_steps_missing"}


def test_workflow_validator_rejects_undeclared_project_extras(tmp_path: Path) -> None:
    project_file = tmp_path / "pyproject.toml"
    project_file.write_text(
        '[project.optional-dependencies]\ndev = ["pytest"]\nformats = ["PyYAML"]\n',
        encoding="utf-8",
    )
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text(
        "name: CI\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n"
        '      - run: python -m pip install -e ".[dev,missing]"\n',
        encoding="utf-8",
    )

    report = validate_workflows(workflows, project_file=project_file)

    assert report["ok"] is False
    assert [finding["code"] for finding in report["findings"]] == ["workflow_extra_undeclared"]
