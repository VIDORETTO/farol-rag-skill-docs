from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_doctor_command_emits_machine_readable_report(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='fixture'\n", encoding="utf-8")
    (tmp_path / "requirements.lock").write_text("# fixture\n", encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, "-m", "docops", "doctor", "--root", str(tmp_path), "--json"],
        check=False,
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "DOCOPS_SKIP_RAG": "1"},
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["ok"] is True
    assert report["capabilities"]["harness"] == "external Agent Skills + RAGFlow"
    assert str(tmp_path.resolve()) not in completed.stdout
    assert report["project_root"] == "."
    assert report["checks"]["project_metadata"]["path"] == "pyproject.toml"
    assert report["checks"]["dependency_lock"]["path"] == "requirements.lock"


def test_project_init_resumes_across_cli_processes_without_repeating_answers(tmp_path: Path) -> None:
    project = tmp_path / "project"
    start_input = tmp_path / "start.json"
    start_input.write_text(
        json.dumps({"name": "CLI fixture", "deliverables": ["knowledge"]}),
        encoding="utf-8",
    )

    started = subprocess.run(
        [
            sys.executable,
            "-m",
            "docops",
            "init-start",
            "--project",
            str(project),
            "--input",
            str(start_input),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert started.returncode == 2, started.stderr
    started_payload = json.loads(started.stdout)
    session = started_payload["data"]["session"]

    answer_input = tmp_path / "answer.json"
    answer_input.write_text(
        json.dumps({"session_id": session["session_id"], "objective": "Retomar uma fixture"}),
        encoding="utf-8",
    )
    answered = subprocess.run(
        [
            sys.executable,
            "-m",
            "docops",
            "init-answer",
            "--project",
            str(project),
            "--input",
            str(answer_input),
            "--expected-revision",
            str(session["session_revision"]),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert answered.returncode == 0, answered.stderr

    inspected = subprocess.run(
        [
            sys.executable,
            "-m",
            "docops",
            "init-status",
            "--project",
            str(project),
            "--session-id",
            session["session_id"],
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert inspected.returncode == 0, inspected.stderr
    inspected_payload = json.loads(inspected.stdout)
    assert inspected_payload["data"]["session"]["status"] == "draft_ready"
    assert (
        next(
            answer["value"]
            for answer in inspected_payload["data"]["session"]["answers"]
            if answer["question_key"] == "objective"
        )
        == "Retomar uma fixture"
    )


def test_evaluate_command_never_emits_the_golden_query(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Confidential roadmap\nMerger milestones.\n", encoding="utf-8")
    output = tmp_path / "package"
    created = subprocess.run(
        [
            sys.executable,
            "-m",
            "docops",
            "run",
            str(source),
            "--output",
            str(output),
            "--slug",
            "privacy",
            "--license",
            "MIT",
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert created.returncode == 0, created.stdout + created.stderr
    query = "customer-merger-confidential-roadmap"
    cases = tmp_path / "cases.json"
    cases.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "reviewed": True,
                "cases": [
                    {
                        "query": query,
                        "expected_filepath": "guide.md",
                        "kind": "factual",
                        "reviewed": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    evaluated = subprocess.run(
        [
            sys.executable,
            "-m",
            "docops",
            "evaluate",
            "--package",
            str(output),
            "--cases",
            str(cases),
            "--adapter",
            "lexical",
            "--recall-threshold",
            "0",
            "--mrr-threshold",
            "0",
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert evaluated.returncode == 0, evaluated.stdout + evaluated.stderr
    assert query not in evaluated.stdout
    assert json.loads(evaluated.stdout)["cases"][0]["query"] == "<redacted-query>"


def test_resolve_and_run_commands_are_consumable_by_a_harness(tmp_path: Path) -> None:
    source = tmp_path / "docs"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\nUse the guide.", encoding="utf-8")
    output = tmp_path / "package"

    resolved = subprocess.run(
        [sys.executable, "-m", "docops", "resolve", str(source), "--json"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert resolved.returncode == 0, resolved.stderr
    assert json.loads(resolved.stdout)["selected"]["kind"] == "local"

    executed = subprocess.run(
        [
            sys.executable,
            "-m",
            "docops",
            "run",
            str(source),
            "--output",
            str(output),
            "--slug",
            "fixture",
            "--license",
            "MIT",
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert executed.returncode == 0, executed.stderr
    assert json.loads(executed.stdout)["ok"] is True


def test_plan_command_emits_a_reviewable_no_effects_plan(tmp_path: Path) -> None:
    source = tmp_path / "docs"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\n", encoding="utf-8")
    output = tmp_path / "package"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "docops",
            "plan",
            str(source),
            "--output",
            str(output),
            "--slug",
            "guide",
            "--license",
            "MIT",
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["plan_version"] == 1
    assert payload["actions"][0]["kind"] == "add"
    assert not output.exists()


def test_config_audit_command_rejects_an_unauthenticated_http_profile(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("server:\n  transport: sse\n", encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, "-m", "docops", "config-audit", str(config), "--json"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert "network_auth_required" in completed.stdout


def test_resolve_command_does_not_echo_url_credentials(tmp_path: Path) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "docops", "resolve", "https://docs.example.test/guide?api_key=super-secret-value"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "super-secret-value" not in completed.stdout
    assert "REDACTED" in completed.stdout


def test_cli_returns_structured_json_for_invalid_pipeline_options(tmp_path: Path) -> None:
    source = tmp_path / "docs"
    source.mkdir()
    (source / "guide.md").write_text("# Guide\n", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "docops",
            "run",
            str(source),
            "--output",
            str(tmp_path / "package"),
            "--slug",
            "Not A Slug",
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert "Traceback" not in completed.stdout
    assert "Traceback" not in completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "invalid_request"
