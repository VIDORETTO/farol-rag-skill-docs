import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def test_support_checker_rejects_a_platform_claim_without_a_matching_workflow_job(tmp_path: Path) -> None:
    matrix = json.loads(Path("docs/SUPPORT-MATRIX.json").read_text(encoding="utf-8"))
    matrix["claims"] = [
        {"id": "uncovered-profile", "platform": "windows", "profile": "bootstrap", "job": "missing-profile-job"}
    ]
    matrix_path = tmp_path / "SUPPORT-MATRIX.json"
    matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    for path in Path(".github/workflows").glob("*.yml"):
        shutil.copy2(path, workflows / path.name)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/check_support_matrix.py",
            "--matrix",
            str(matrix_path),
            "--workflows",
            str(workflows),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    report = json.loads(completed.stdout)
    assert any(finding["code"] == "claim_job_missing" for finding in report["findings"])


def test_support_checker_rejects_a_claim_when_its_job_does_not_execute_the_profile_gate(
    tmp_path: Path,
) -> None:
    matrix = json.loads(Path("docs/SUPPORT-MATRIX.json").read_text(encoding="utf-8"))
    matrix["profiles"]["core"]["gates"] = ["clean_clone"]
    matrix_path = tmp_path / "SUPPORT-MATRIX.json"
    matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    for path in Path(".github/workflows").glob("*.yml"):
        shutil.copy2(path, workflows / path.name)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/check_support_matrix.py",
            "--matrix",
            str(matrix_path),
            "--workflows",
            str(workflows),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    report = json.loads(completed.stdout)
    assert any(finding["code"] == "claim_gate_unexecuted_by_job" for finding in report["findings"])


def test_package_workflow_retains_candidate_evidence() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "actions/upload-artifact@" in workflow
    assert "path: artifacts/candidate-1.1.0" in workflow
    assert "candidate-1.1.0-${{ github.sha }}" in workflow


def test_release_identity_gate_is_an_explicit_manual_workflow_input() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "release_verification:" in workflow
    assert "type: boolean" in workflow
    assert "github.event_name == 'workflow_dispatch' && inputs.release_verification == true" in workflow
    assert "github.event_name == 'push' && github.ref == 'refs/heads/main'" not in workflow


def test_quick_workflow_retains_raw_dependency_audit_evidence_and_checks_installation() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "python -m pip check" in workflow
    assert "--evidence-dir artifacts/dependency-audit" in workflow
    assert "name: dependency-audit-${{ runner.os }}-py${{ matrix.python-version }}-${{ github.sha }}" in workflow
    assert "path: artifacts/dependency-audit" in workflow
    assert "if-no-files-found: error" in workflow


def test_integration_workflow_retains_redacted_rag_evidence() -> None:
    workflow = Path(".github/workflows/integration.yml").read_text(encoding="utf-8")

    assert "actions/upload-artifact@" in workflow
    assert "integration-evidence-${{ github.sha }}" in workflow
    assert "artifacts/ragflow-release-gates.json" in workflow


def test_support_checker_rejects_package_without_candidate_artifact(tmp_path: Path) -> None:
    matrix_path = tmp_path / "SUPPORT-MATRIX.json"
    matrix_path.write_text(Path("docs/SUPPORT-MATRIX.json").read_text(encoding="utf-8"), encoding="utf-8")
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    for path in Path(".github/workflows").glob("*.yml"):
        content = path.read_text(encoding="utf-8")
        if path.name == "ci.yml":
            content = content.replace(
                "      - name: Retain candidate bundle and identity evidence\n"
                "        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4.6.2\n",
                "      - name: Candidate artifact deliberately omitted\n        run: true\n",
                1,
            )
        (workflows / path.name).write_text(content, encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/check_support_matrix.py",
            "--matrix",
            str(matrix_path),
            "--workflows",
            str(workflows),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    report = json.loads(completed.stdout)
    assert any(finding["code"] == "candidate_artifact_missing" for finding in report["findings"])


def test_support_checker_rejects_broad_rag_artifact(tmp_path: Path) -> None:
    matrix_path = tmp_path / "SUPPORT-MATRIX.json"
    matrix_path.write_text(Path("docs/SUPPORT-MATRIX.json").read_text(encoding="utf-8"), encoding="utf-8")
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    for path in Path(".github/workflows").glob("*.yml"):
        content = path.read_text(encoding="utf-8")
        if path.name == "integration.yml":
            content += """
      - name: Unsafe broad artifact
        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4.6.2
        with:
          name: unsafe
          path: artifacts/ragflow
"""
        (workflows / path.name).write_text(content, encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/check_support_matrix.py",
            "--matrix",
            str(matrix_path),
            "--workflows",
            str(workflows),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    report = json.loads(completed.stdout)
    assert any(finding["code"] == "integration_artifact_unsafe" for finding in report["findings"])


@pytest.mark.parametrize("unsafe_path", ["artifacts/ragflow/rag", "artifacts", "artifacts/ragflow/**"])
def test_support_checker_rejects_every_broad_integration_artifact_path(
    tmp_path: Path,
    unsafe_path: str,
) -> None:
    matrix_path = tmp_path / "SUPPORT-MATRIX.json"
    matrix_path.write_text(Path("docs/SUPPORT-MATRIX.json").read_text(encoding="utf-8"), encoding="utf-8")
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    for path in Path(".github/workflows").glob("*.yml"):
        content = path.read_text(encoding="utf-8")
        if path.name == "integration.yml":
            content += f"""
      - name: Unsafe broad artifact
        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02
        with:
          name: unsafe
          path: {unsafe_path}
"""
        (workflows / path.name).write_text(content, encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/check_support_matrix.py",
            "--matrix",
            str(matrix_path),
            "--workflows",
            str(workflows),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    report = json.loads(completed.stdout)
    assert any(finding["code"] == "integration_artifact_unsafe" for finding in report["findings"])


def test_support_checker_rejects_a_gate_marker_that_is_only_a_comment(tmp_path: Path) -> None:
    matrix = json.loads(Path("docs/SUPPORT-MATRIX.json").read_text(encoding="utf-8"))
    matrix["profiles"]["bootstrap"]["gates"] = ["clean_clone"]
    matrix_path = tmp_path / "SUPPORT-MATRIX.json"
    matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    for path in Path(".github/workflows").glob("*.yml"):
        content = path.read_text(encoding="utf-8")
        if path.name == "ci.yml":
            content = content.replace(
                "        run: python scripts/verify_clean_clone.py",
                "        # python scripts/verify_clean_clone.py\n        run: python -c \"print('gate omitted')\"",
            )
        (workflows / path.name).write_text(content, encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/check_support_matrix.py",
            "--matrix",
            str(matrix_path),
            "--workflows",
            str(workflows),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    report = json.loads(completed.stdout)
    assert any(finding["code"] == "claim_gate_unexecuted_by_job" for finding in report["findings"])


def test_support_checker_rejects_quick_job_without_pip_check(tmp_path: Path) -> None:
    matrix_path = tmp_path / "SUPPORT-MATRIX.json"
    matrix_path.write_text(Path("docs/SUPPORT-MATRIX.json").read_text(encoding="utf-8"), encoding="utf-8")
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    for path in Path(".github/workflows").glob("*.yml"):
        content = path.read_text(encoding="utf-8")
        if path.name == "ci.yml":
            content = content.replace("        run: python -m pip check", "        run: python -c \"print('omitted')\"")
        (workflows / path.name).write_text(content, encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/check_support_matrix.py",
            "--matrix",
            str(matrix_path),
            "--workflows",
            str(workflows),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    report = json.loads(completed.stdout)
    assert any(finding["code"] in {"gate_missing", "claim_gate_unexecuted_by_job"} for finding in report["findings"])


def test_support_checker_rejects_tolerated_python_as_supported(tmp_path: Path) -> None:
    matrix = json.loads(Path("docs/SUPPORT-MATRIX.json").read_text(encoding="utf-8"))
    matrix["python"]["supported"].append("3.14")
    matrix_path = tmp_path / "SUPPORT-MATRIX.json"
    matrix_path.write_text(json.dumps(matrix), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, "scripts/check_support_matrix.py", "--matrix", str(matrix_path), "--json"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    report = json.loads(completed.stdout)
    assert any(finding["code"] == "supported_tolerated_overlap" for finding in report["findings"])
