# seam-scope: implementation-infrastructure (adapter/evaluator unit tests)
from __future__ import annotations

from pathlib import Path

from docops.evaluator import evaluate_package, generate_golden_candidates
from docops.pipeline import PipelineOptions, run_pipeline
from docops.retrieval import InMemoryRetrievalAdapter


def _package(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text("# Authentication\nToken validation and errors.", encoding="utf-8")
    output = tmp_path / "package"
    result = run_pipeline(str(source), options=PipelineOptions(output_dir=output, slug="fixture", license="MIT"))
    assert result.ok
    return output


def test_evaluator_requires_reviewed_cases_and_reports_recall_and_mrr(tmp_path: Path) -> None:
    package = _package(tmp_path)
    cases = {
        "schema_version": 1,
        "reviewed": True,
        "cases": [
            {
                "query": "Authentication token validation",
                "expected_filepath": "guide.md",
                "kind": "factual",
                "reviewed": True,
            }
        ],
    }

    result = evaluate_package(package, cases)

    assert result.ok
    assert result.metrics["recall_at_5"] == 1.0
    assert result.metrics["mrr_at_5"] == 1.0
    assert result.cases[0]["expected_found"] is True
    assert result.thresholds == {"recall_at_5": 0.85, "mrr_at_5": 0.7}


def test_memory_adapter_reports_a_real_adapter_contract(tmp_path: Path) -> None:
    package = _package(tmp_path)
    adapter = InMemoryRetrievalAdapter({"guide.md": "Authentication token validation and errors."})
    cases = {
        "schema_version": 1,
        "reviewed": True,
        "cases": [{"query": "Authentication", "expected_filepath": "guide.md", "reviewed": True}],
    }

    result = evaluate_package(package, cases, adapter=adapter)

    assert result.ok, result.errors
    assert result.metadata["backend"] == "memory"
    assert result.metadata["mode"] == "gate"
    assert result.metadata["top_k"] == 5


def test_router_cases_measure_the_real_routing_decision(tmp_path: Path) -> None:
    package = _package(tmp_path)
    cases = {
        "schema_version": 1,
        "reviewed": True,
        "cases": [
            {"query": "What is the exact default version?", "kind": "router", "expected_route": "rag", "reviewed": True}
        ],
    }

    result = evaluate_package(package, cases, adapter=InMemoryRetrievalAdapter({}))

    assert result.ok, result.errors
    assert result.metrics["route_accuracy"] == 1.0
    assert result.cases[0]["route"] == "rag"


def test_evaluator_metric_names_follow_the_requested_top_k(tmp_path: Path) -> None:
    package = _package(tmp_path)
    cases = {
        "schema_version": 1,
        "reviewed": True,
        "cases": [{"query": "Authentication", "expected_filepath": "guide.md", "reviewed": True}],
    }

    result = evaluate_package(
        package,
        cases,
        top_k=1,
        thresholds={"recall_at_1": 1.0, "mrr_at_1": 1.0},
    )

    assert result.ok, result.errors
    assert result.metrics == {"recall_at_1": 1.0, "mrr_at_1": 1.0}
    assert result.thresholds == {"recall_at_1": 1.0, "mrr_at_1": 1.0}


def test_unreviewed_golden_candidates_cannot_be_used_as_a_quality_gate(tmp_path: Path) -> None:
    package = _package(tmp_path)
    candidates = generate_golden_candidates(package)
    result = evaluate_package(package, {"schema_version": 1, "cases": candidates})

    assert not result.ok
    assert any(error["code"] == "golden_not_reviewed" for error in result.errors)


def test_each_golden_case_must_be_reviewed_even_when_the_envelope_is_reviewed(tmp_path: Path) -> None:
    package = _package(tmp_path)
    result = evaluate_package(
        package,
        {
            "schema_version": 1,
            "reviewed": True,
            "cases": [{"query": "Authentication", "expected_filepath": "guide.md", "reviewed": False}],
        },
    )

    assert not result.ok
    assert any(error["code"] == "golden_not_reviewed" for error in result.errors)


def test_evaluator_includes_normalized_code_documents(tmp_path: Path) -> None:
    from docops.pipeline import PipelineOptions

    source = tmp_path / "source"
    source.mkdir()
    (source / "client.py").write_text("# Client\nBearer token validation.", encoding="utf-8")
    package = tmp_path / "package"
    assert run_pipeline(source, options=PipelineOptions(output_dir=package, slug="code", license="MIT")).ok

    result = evaluate_package(
        package,
        {
            "schema_version": 1,
            "reviewed": True,
            "cases": [{"query": "Bearer token validation", "expected_filepath": "client.py", "reviewed": True}],
        },
    )

    assert result.ok, result.errors


def test_evaluator_rejects_invalid_quality_gate_parameters(tmp_path: Path) -> None:
    package = _package(tmp_path)
    cases = {
        "schema_version": 1,
        "reviewed": True,
        "cases": [
            {
                "query": "guide",
                "expected_filepath": "guide.md",
                "kind": "factual",
                "reviewed": True,
            }
        ],
    }

    result = evaluate_package(
        package,
        cases,
        thresholds={"recall_at_5": 1.1, "mrr_at_5": float("nan")},
        top_k=0,
    )

    assert not result.ok
    codes = {error["code"] for error in result.errors}
    assert {"top_k_out_of_range", "threshold_out_of_range"} <= codes


def test_evaluator_rejects_windows_absolute_golden_paths(tmp_path: Path) -> None:
    package = _package(tmp_path)
    result = evaluate_package(
        package,
        {
            "schema_version": 1,
            "reviewed": True,
            "cases": [
                {
                    "query": "Authentication",
                    "expected_filepath": "C:\\outside\\guide.md",
                    "reviewed": True,
                }
            ],
        },
    )

    assert not result.ok
    assert any(error["code"] == "golden_case_path" for error in result.errors)
