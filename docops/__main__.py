"""Command line entry point for the portable documentation operator."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .agent_skill import install_agents_bootstrap, skill_metadata
from .candidates import submit_enrichment
from .config_audit import audit_config_file
from .contracts import validate_artifact
from .coordination import list_jobs, submit_event, work_once
from .doctor import run_doctor
from .evaluator import evaluate_package, generate_golden_candidates
from .feedback import build_feedback_report, submit_feedback
from .harness import export_enrichment_request
from .learning import review_learning_proposal, submit_learning_proposal
from .lifecycle import LifecycleFacade
from .manifest import redact_metadata
from .master import (
    activate_project_change,
    adopt_project_package,
    answer_project_init,
    apply_project_preset,
    authorize_factual_change,
    backup_project,
    create_delegated_authorization,
    dispatch_project_enrichment,
    evaluate_project_candidate,
    finalize_project_init,
    ingest_external_transcription,
    inspect_project,
    inspect_project_change,
    inspect_project_enrichment,
    inspect_project_health,
    inspect_project_init,
    inspect_project_recovery,
    load_project_preset,
    prepare_project_change,
    prepare_project_rag_candidate,
    project_preset_golden_candidates,
    propose_project_change,
    query_project_evidence,
    record_project_claim,
    record_project_conflict,
    recover_project_activation,
    register_source_governance,
    restore_project,
    resume_project_supervisor,
    retry_project_enrichment,
    revoke_delegated_authorization,
    revoke_project_source,
    rollback_project,
    run_project_supervisor_once,
    source_use_decision,
    start_project_init,
    stop_project_supervisor,
    submit_project_enrichment,
    timeout_project_enrichment,
    validate_dependency_mitigation,
    verify_project_backup,
)
from .observability import redact_report, redact_text
from .operations import (
    CandidatePublicationError,
    OperationOptions,
    approve_candidate,
    preview,
    publish_candidate,
    rollback_candidate,
)
from .operations import apply as apply_operation
from .operations import cleanup as cleanup_residue
from .operations import plan as build_plan
from .package_validator import validate_package
from .project import ProjectError, ProjectService
from .rag_snapshots import RagSnapshotError, compare_embedding_profiles, snapshot_rag_package
from .reader_sessions import create_reader_session, query_reader_session, revoke_reader_session
from .source_policy import reconcile_source, register_source
from .source_resolver import SourceResolver
from .triggers import assess_conceptual_impact

# The flat commands remain the compatibility surface during expand-contract.
# Keep this mapping explicit so each legacy entry point has one documented
# canonical spelling and can be removed by policy instead of by accident.
CLI_COMPATIBILITY_MAP = {
    "doctor": "doctor",
    "skill": "skill",
    "agents-bootstrap": "agents-bootstrap",
    "resolve": "source resolve",
    "plan": "package plan",
    "run": "package run",
    "validate": "package validate",
    "cleanup": "package cleanup",
    "evaluate": "quality evaluate",
    "golden-candidates": "quality golden-candidates",
    "candidate-request": "lifecycle candidate enrichment-request",
    "candidate-submit": "lifecycle candidate enrich",
    "candidate-approve": "lifecycle candidate approve",
    "candidate-publish": "lifecycle candidate publish",
    "candidate-rollback": "lifecycle candidate rollback",
    "source-register": "lifecycle source register",
    "source-reconcile": "lifecycle source reconcile",
    "event-submit": "lifecycle event submit",
    "jobs": "lifecycle worker list",
    "jobs-list": "lifecycle worker list",
    "work": "lifecycle worker run",
    "impact-assess": "lifecycle impact assess",
    "reader-session": "lifecycle reader session",
    "reader-query": "lifecycle reader query",
    "reader-session-revoke": "lifecycle reader revoke",
    "rag-snapshot": "lifecycle rag snapshot",
    "rag-profile-compare": "lifecycle rag profile-compare",
    "learning-submit": "lifecycle learning submit",
    "learning_submit": "lifecycle learning submit",
    "learning-review": "lifecycle learning review",
    "learning_review": "lifecycle learning review",
    "feedback-submit": "lifecycle feedback submit",
    "feedback_submit": "lifecycle feedback submit",
    "feedback-report": "lifecycle feedback report",
    "feedback_report": "lifecycle feedback report",
    "config-audit": "security config-audit",
    "lifecycle-status": "lifecycle status",
    "init-start": "init start",
    "init-status": "init status",
    "init-answer": "init answer",
    "init-finalize": "init finalize",
    "project-inspect": "project inspect",
    "project-adopt": "project adopt",
    "project-source-govern": "project source govern",
    "project-source-ingest": "project source ingest",
    "project-source-revoke": "project source revoke",
    "project-source-use": "project source use",
    "project-evidence-query": "project evidence query",
    "project-rag-prepare": "project rag prepare",
    "project-candidate-evaluate": "project candidate evaluate",
    "project-dependency-mitigation": "project dependency mitigation",
    "project-delegate-authorize": "project delegate authorize",
    "project-claim-record": "project evidence claim",
    "project-conflict-record": "project evidence conflict",
    "project-change-propose": "project change propose",
    "project-change-inspect": "project change inspect",
    "project-change-prepare": "project change prepare",
    "project-change-activate": "project change activate",
    "project-rollback": "project rollback",
    "project-enrichment-dispatch": "project enrichment dispatch",
    "project-enrichment-inspect": "project enrichment inspect",
    "project-enrichment-submit": "project enrichment submit",
    "project-enrichment-timeout": "project enrichment timeout",
    "project-enrichment-retry": "project enrichment retry",
    "project-delegate": "project delegate create",
    "project-delegate-revoke": "project delegate revoke",
    "project-health": "project health",
    "project-recovery": "project recovery inspect",
    "project-recovery-run": "project recovery run",
    "project-backup": "project backup",
    "project-backup-verify": "project backup verify",
    "project-restore": "project restore",
    "project-preset": "project preset",
    "project-preset-candidates": "project preset candidates",
    "project-v2-start": "v2 start",
    "project-v2-inspect": "v2 inspect",
    "project-v2-apply": "v2 apply",
    "supervisor-run": "supervisor run",
    "supervisor-stop": "supervisor stop",
    "supervisor-resume": "supervisor resume",
}

_CANONICAL_TO_FLAT = {
    tuple(canonical.split()): legacy
    for legacy, canonical in CLI_COMPATIBILITY_MAP.items()
    if canonical != legacy and legacy not in {"jobs-list", "learning_submit", "learning_review", "feedback_submit"}
}
_CANONICAL_HELP = """Canonical domain commands:

  lifecycle status
  lifecycle source {register,reconcile}
  lifecycle event submit
  lifecycle worker {list,run}
  lifecycle candidate {enrichment-request,enrich,approve,publish,rollback}
  lifecycle reader {session,query,revoke}
  lifecycle rag {snapshot,profile-compare}
  lifecycle learning {submit,review}
  lifecycle feedback {submit,report}
  init {start,status,answer,finalize}
  project {inspect,adopt,source,evidence,change,rollback,health,backup,restore,preset}
  v2 {start,inspect,apply}
  supervisor {run,stop,resume}

Flat commands are temporary compatibility aliases. They emit the same JSON
contract and exit code as their canonical spelling; deprecation metadata is
kept out of structured output. Remove an alias only after all callers have
migrated and the alias-usage gate is zero for one complete release window.
"""

_CANONICAL_GROUP_HELP = {
    "lifecycle": "lifecycle status source event worker candidate reader rag learning feedback",
    "init": "init start status answer finalize",
    "project": "project inspect adopt source evidence change rollback health backup restore preset",
    "v2": "v2 start inspect apply",
    "supervisor": "supervisor run stop resume",
}


def _expand_canonical_argv(argv: list[str]) -> list[str]:
    """Translate one canonical hierarchy prefix to its legacy parser seam."""

    for prefix in sorted(_CANONICAL_TO_FLAT, key=len, reverse=True):
        if tuple(argv[: len(prefix)]) == prefix:
            return [_CANONICAL_TO_FLAT[prefix], *argv[len(prefix) :]]
    return list(argv)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="docops",
        description="Portable documentation lifecycle operator",
        epilog=_CANONICAL_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="command", required=True)
    skill = commands.add_parser("skill", help="inspect the first-party DOCOPS agent skill")
    skill_commands = skill.add_subparsers(dest="skill_command", required=True)
    skill_path = skill_commands.add_parser("path", help="show the bundled docops-agent skill path")
    skill_path.add_argument("--skill-root", type=Path)
    skill_path.add_argument("--json", action="store_true")
    agents_bootstrap = commands.add_parser("agents-bootstrap", help="install the DOCOPS rule in AGENTS.md")
    agents_bootstrap.add_argument("--root", type=Path, default=Path.cwd())
    agents_bootstrap.add_argument("--check", action="store_true", help="do not write; fail if the rule is absent")
    agents_bootstrap.add_argument("--json", action="store_true")
    doctor = commands.add_parser("doctor", help="diagnose a clean clone")
    doctor.add_argument("--root", type=Path, default=Path.cwd())
    doctor.add_argument("--json", action="store_true", help="emit JSON")
    resolve = commands.add_parser("resolve", help="resolve a documentation source")
    resolve.add_argument("source")
    resolve.add_argument("--root", type=Path, default=Path.cwd())
    resolve.add_argument("--catalog", type=Path)
    resolve.add_argument("--version")
    resolve.add_argument("--scope")
    resolve.add_argument("--language")
    resolve.add_argument("--json", action="store_true")
    plan = commands.add_parser("plan", help="plan a package operation without writing artifacts")
    plan.add_argument("source")
    plan.add_argument("--output", type=Path, required=True)
    plan.add_argument("--catalog", type=Path)
    plan.add_argument("--slug")
    plan.add_argument("--version")
    plan.add_argument("--scope")
    plan.add_argument("--language")
    plan.add_argument("--mode", choices=("create", "update", "run", "dry-run"), default="run")
    plan.add_argument("--layer", dest="layer_values", action="append", choices=("conceptual", "factual"))
    plan.add_argument("--layers", dest="layers_csv")
    plan.add_argument("--publication-policy", choices=("direct", "candidate"), default="direct")
    plan.add_argument("--license", default=None)
    plan.add_argument("--redistribution", default="private-only")
    plan.add_argument("--index-rag", action="store_true")
    plan.add_argument("--allow-private-network", action="store_true")
    plan.add_argument("--max-pages", type=int, default=50)
    plan.add_argument("--max-depth", type=int, default=2)
    plan.add_argument("--include", dest="include_patterns", action="append", default=[])
    plan.add_argument("--exclude", dest="exclude_patterns", action="append", default=[])
    plan.add_argument("--runtime-root", type=Path)
    plan.add_argument("--source-root", type=Path)
    plan.add_argument("--lease-policy", choices=("fail", "wait"), default="fail")
    plan.add_argument("--lease-timeout-seconds", type=float, default=0.0)
    plan.add_argument("--stale-lease-seconds", type=float, default=300.0)
    plan.add_argument("--json", action="store_true")
    run = commands.add_parser("run", help="produce a knowledge package")
    run.add_argument("source")
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--catalog", type=Path)
    run.add_argument("--slug")
    run.add_argument("--version")
    run.add_argument("--scope")
    run.add_argument("--language")
    run.add_argument("--mode", choices=("create", "update", "run", "dry-run"), default="run")
    run.add_argument("--layer", dest="layer_values", action="append", choices=("conceptual", "factual"))
    run.add_argument("--layers", dest="layers_csv")
    run.add_argument("--publication-policy", choices=("direct", "candidate"), default="direct")
    run.add_argument("--license", default=None)
    run.add_argument("--redistribution", default="private-only")
    run.add_argument("--index-rag", action="store_true")
    run.add_argument("--allow-private-network", action="store_true")
    run.add_argument("--max-pages", type=int, default=50)
    run.add_argument("--max-depth", type=int, default=2)
    run.add_argument("--include", dest="include_patterns", action="append", default=[])
    run.add_argument("--exclude", dest="exclude_patterns", action="append", default=[])
    run.add_argument("--runtime-root", type=Path)
    run.add_argument("--source-root", type=Path)
    run.add_argument("--lease-policy", choices=("fail", "wait"), default="fail")
    run.add_argument("--lease-timeout-seconds", type=float, default=0.0)
    run.add_argument("--stale-lease-seconds", type=float, default=300.0)
    run.add_argument("--json", action="store_true")
    validate = commands.add_parser("validate", help="validate a produced knowledge package")
    validate.add_argument("package", type=Path)
    validate.add_argument("--json", action="store_true")
    cleanup = commands.add_parser("cleanup", help="remove expired operation residue safely")
    cleanup.add_argument("package", type=Path)
    cleanup.add_argument("--retention-seconds", type=float, default=7 * 24 * 60 * 60)
    cleanup.add_argument("--keep-attempts", type=int, default=20)
    cleanup.add_argument("--json", action="store_true")
    evaluate = commands.add_parser("evaluate", help="evaluate reviewed golden cases")
    evaluate.add_argument("--package", type=Path, required=True)
    evaluate.add_argument("--cases", type=Path, required=True)
    evaluate.add_argument("--recall-threshold", type=float, default=0.85)
    evaluate.add_argument("--mrr-threshold", type=float, default=0.7)
    evaluate.add_argument("--top-k", type=int, default=5)
    evaluate.add_argument("--adapter", choices=("lexical", "memory", "mcp"), default="lexical")
    evaluate.add_argument("--runtime-root", type=Path)
    evaluate.add_argument("--response-receipt", type=Path)
    evaluate.add_argument("--response-fidelity-threshold", type=float, default=0.98)
    evaluate.add_argument("--citation-coverage-threshold", type=float, default=0.98)
    evaluate.add_argument("--json", action="store_true")
    candidates = commands.add_parser("golden-candidates", help="generate unreviewed golden candidates")
    candidates.add_argument("package", type=Path)
    candidates.add_argument("--limit", type=int, default=20)
    candidates.add_argument("--json", action="store_true")
    candidate_request = commands.add_parser(
        "candidate-request", help="export an external enrichment task for a candidate"
    )
    candidate_request.add_argument("--package", type=Path, required=True)
    candidate_request.add_argument("--candidate-id", required=True)
    candidate_request.add_argument("--language")
    candidate_request.add_argument("--json", action="store_true")
    candidate_submit = commands.add_parser("candidate-submit", help="receive an external enrichment result")
    candidate_submit.add_argument("--package", type=Path, required=True)
    candidate_submit.add_argument("--candidate-id", required=True)
    candidate_submit.add_argument("--source-dir", type=Path, required=True)
    candidate_submit.add_argument("--receipt", type=Path, required=True)
    candidate_submit.add_argument("--json", action="store_true")
    candidate_approve = commands.add_parser(
        "candidate-approve",
        help="record explicit authority for a reviewable candidate",
    )
    candidate_approve.add_argument("--package", type=Path, required=True)
    candidate_approve.add_argument("--candidate-id", required=True)
    candidate_approve.add_argument("--actor", required=True)
    candidate_approve.add_argument(
        "--role",
        choices=("human_approver", "delegated_policy"),
        required=True,
    )
    candidate_approve.add_argument(
        "--authority-json",
        help="authenticated external authority attestation; proof is hashed before storage",
    )
    candidate_approve.add_argument("--json", action="store_true")
    candidate_publish = commands.add_parser(
        "candidate-publish",
        help="publish an approved candidate after exact evidence revalidation",
    )
    candidate_publish.add_argument("--package", type=Path, required=True)
    candidate_publish.add_argument("--candidate-id", required=True)
    candidate_publish.add_argument("--json", action="store_true")
    candidate_rollback = commands.add_parser(
        "candidate-rollback",
        help="restore a retained editorial generation after validation",
    )
    candidate_rollback.add_argument("--package", type=Path, required=True)
    candidate_rollback.add_argument("--release-id", required=True)
    candidate_rollback.add_argument("--json", action="store_true")
    source_register = commands.add_parser("source-register", help="register one documentation source")
    source_register.add_argument("--package", type=Path, required=True)
    source_register.add_argument("--source-id", required=True)
    source_register.add_argument("--canonical", required=True)
    source_register.add_argument("--kind", choices=("local", "repository", "web"), default="web")
    source_register.add_argument("--scope", default="/**")
    source_register.add_argument("--version-policy", choices=("latest", "pinned"), default="latest")
    source_register.add_argument("--version")
    source_register.add_argument("--language")
    source_register.add_argument("--rights", default="unknown")
    source_register.add_argument("--privacy", default="unknown")
    source_register.add_argument("--authority", default="operator")
    source_register.add_argument("--owner", default="local")
    source_register.add_argument(
        "--readmit",
        action="store_true",
        help="explicitly reauthorize a previously withdrawn source",
    )
    source_register.add_argument("--json", action="store_true")
    source_reconcile = commands.add_parser("source-reconcile", help="reconcile one acquisition snapshot")
    source_reconcile.add_argument("--package", type=Path, required=True)
    source_reconcile.add_argument("--snapshot", type=Path, required=True)
    source_reconcile.add_argument("--source-id")
    source_reconcile.add_argument("--withdraw", action="store_true")
    source_reconcile.add_argument("--json", action="store_true")
    event_submit = commands.add_parser("event-submit", help="persist one coordination event")
    event_submit.add_argument("--queue", type=Path, required=True)
    event_submit.add_argument("--event", type=Path, required=True)
    event_submit.add_argument("--now")
    event_submit.add_argument("--json", action="store_true")
    jobs = commands.add_parser("jobs", aliases=("jobs-list",), help="list durable coordination jobs")
    jobs.add_argument("--queue", type=Path, required=True)
    jobs.add_argument("--now")
    jobs.add_argument("--json", action="store_true")
    work = commands.add_parser("work", help="execute at most one durable coordination job")
    work.add_argument("--once", action="store_true", required=True)
    work.add_argument("--queue", type=Path, required=True)
    work.add_argument("--now")
    work.add_argument("--worker-id")
    work.add_argument("--lease-seconds", type=int, default=120)
    work.add_argument("--json", action="store_true")
    impact = commands.add_parser("impact-assess", help="assess conceptual impact from source events")
    impact.add_argument("--package", type=Path, required=True)
    impact.add_argument("--events", type=Path, required=True)
    impact.add_argument("--threshold", type=int, default=10)
    impact.add_argument("--budget", type=int, default=4)
    impact.add_argument("--corpus-documents", type=int, default=100)
    impact.add_argument("--now")
    impact.add_argument("--causation-id")
    impact.add_argument("--json", action="store_true")
    reader_session = commands.add_parser("reader-session", help="create a pinned read-only reader session")
    reader_session.add_argument("--package", type=Path, required=True)
    reader_session.add_argument("--adapter", choices=("memory",), default="memory")
    reader_session.add_argument("--session-id")
    reader_session.add_argument("--snapshot", type=Path, help="explicit relocatable RAG snapshot to pin")
    reader_session.add_argument("--now")
    reader_session.add_argument("--expires-at")
    reader_session.add_argument("--json", action="store_true")
    reader_query = commands.add_parser("reader-query", help="query through a pinned reader session")
    reader_query.add_argument("--package", type=Path, required=True)
    reader_query.add_argument("--session", required=True)
    reader_query.add_argument("--tool", required=True)
    reader_query.add_argument("--query", required=True)
    reader_query.add_argument("--adapter", choices=("memory",))
    reader_query.add_argument("--max-results", type=int, default=5)
    reader_query.add_argument("--now")
    reader_query.add_argument("--runtime-root", type=Path)
    reader_query.add_argument("--json", action="store_true")
    reader_revoke = commands.add_parser("reader-session-revoke", help="revoke a pinned reader session")
    reader_revoke.add_argument("--package", type=Path, required=True)
    reader_revoke.add_argument("--session", required=True)
    reader_revoke.add_argument("--now")
    reader_revoke.add_argument("--reason")
    reader_revoke.add_argument("--json", action="store_true")
    rag_snapshot = commands.add_parser("rag-snapshot", help="plan safe RAG snapshot reuse without promotion")
    rag_snapshot.add_argument("--package", type=Path, required=True)
    rag_snapshot.add_argument("--previous", type=Path)
    rag_snapshot.add_argument("--snapshot-out", type=Path)
    rag_snapshot.add_argument("--backend", default="ragflow")
    rag_snapshot.add_argument("--supports-incremental", action="store_true")
    rag_snapshot.add_argument("--server-version")
    rag_snapshot.add_argument("--verify-query")
    rag_snapshot.add_argument("--verify-adapter", choices=("memory", "mcp"), default="memory")
    rag_snapshot.add_argument("--runtime-root", type=Path)
    rag_snapshot.add_argument("--json", action="store_true")
    rag_profile_compare = commands.add_parser(
        "rag-profile-compare",
        help="compare embedding profiles without changing the active index",
    )
    rag_profile_compare.add_argument("--package", type=Path, required=True)
    rag_profile_compare.add_argument("--profiles", default="compact,multilingual")
    rag_profile_compare.add_argument("--language")
    rag_profile_compare.add_argument("--select-profile")
    rag_profile_compare.add_argument("--json", action="store_true")
    learning_submit = commands.add_parser(
        "learning-submit",
        aliases=("learning_submit",),
        help="capture a minimized learning proposal in quarantine",
    )
    learning_submit.add_argument("--package", type=Path, required=True)
    learning_submit.add_argument("--proposal", type=Path, required=True)
    learning_submit.add_argument("--capture-opt-in", action="store_true")
    learning_submit.add_argument("--now")
    learning_submit.add_argument("--json", action="store_true")
    learning_review = commands.add_parser(
        "learning-review",
        aliases=("learning_review",),
        help="review, admit, reject or revoke a learning proposal",
    )
    learning_review.add_argument("--package", type=Path, required=True)
    learning_review.add_argument("--proposal-id", required=True)
    learning_review.add_argument("--decision", choices=("admit", "reject", "revoke"), required=True)
    learning_review.add_argument("--actor", required=True)
    learning_review.add_argument("--role", default="human_approver", choices=("human_approver",))
    learning_review.add_argument("--evidence", type=Path)
    learning_review.add_argument("--now")
    learning_review.add_argument("--reason")
    learning_review.add_argument("--json", action="store_true")
    feedback_submit = commands.add_parser(
        "feedback-submit",
        aliases=("feedback_submit",),
        help="capture one redacted usage signal and optionally queue its report",
    )
    feedback_submit.add_argument("--package", type=Path, required=True)
    feedback_submit.add_argument("--feedback", type=Path, required=True)
    feedback_submit.add_argument("--queue", type=Path)
    feedback_submit.add_argument("--now")
    feedback_submit.add_argument("--json", action="store_true")
    feedback_report = commands.add_parser(
        "feedback-report",
        aliases=("feedback_report",),
        help="aggregate usage feedback into review-only investigations",
    )
    feedback_report.add_argument("--package", type=Path, required=True)
    feedback_report.add_argument("--window-days", type=int, default=7)
    feedback_report.add_argument("--now")
    feedback_report.add_argument("--json", action="store_true")
    init_start = commands.add_parser("init-start", help="start a private structured project initialization")
    init_start.add_argument("--project", type=Path, required=True)
    init_start.add_argument("--input", type=Path)
    init_start.add_argument("--preset")
    init_start.add_argument("--idempotency-key")
    init_start.add_argument("--expected-revision", type=int)
    init_start.add_argument("--now")
    init_start.add_argument("--json", action="store_true")
    init_status = commands.add_parser("init-status", help="inspect a project initialization session")
    init_status.add_argument("--project", type=Path, required=True)
    init_status.add_argument("--session-id")
    init_status.add_argument("--json", action="store_true")
    init_answer = commands.add_parser("init-answer", help="answer a project initialization question")
    init_answer.add_argument("--project", type=Path, required=True)
    init_answer.add_argument("--input", type=Path, required=True)
    init_answer.add_argument("--idempotency-key")
    init_answer.add_argument("--expected-revision", type=int)
    init_answer.add_argument("--now")
    init_answer.add_argument("--json", action="store_true")
    init_finalize = commands.add_parser("init-finalize", help="finalize a private project revision")
    init_finalize.add_argument("--project", type=Path, required=True)
    init_finalize.add_argument("--input", type=Path)
    init_finalize.add_argument("--idempotency-key")
    init_finalize.add_argument("--expected-revision", type=int)
    init_finalize.add_argument("--now")
    init_finalize.add_argument("--json", action="store_true")
    project_inspect = commands.add_parser("project-inspect", help="inspect project state")
    project_inspect.add_argument("--project", type=Path, required=True)
    project_inspect.add_argument("--json", action="store_true")
    project_adopt = commands.add_parser("project-adopt", help="adopt a verified legacy package")
    project_adopt.add_argument("--project", type=Path, required=True)
    project_adopt.add_argument("--package", type=Path, required=True)
    project_adopt.add_argument("--dry-run", action="store_true")
    project_adopt.add_argument("--no-backup", action="store_true")
    project_adopt.add_argument("--idempotency-key")
    project_adopt.add_argument("--expected-revision", type=int)
    project_adopt.add_argument("--now")
    project_adopt.add_argument("--json", action="store_true")
    project_govern = commands.add_parser("project-source-govern", help="register source governance")
    project_govern.add_argument("--project", type=Path, required=True)
    project_govern.add_argument("--input", type=Path, required=True)
    project_govern.add_argument("--readmit", action="store_true")
    project_govern.add_argument("--idempotency-key")
    project_govern.add_argument("--expected-revision", type=int)
    project_govern.add_argument("--now")
    project_govern.add_argument("--json", action="store_true")
    project_ingest = commands.add_parser("project-source-ingest", help="ingest timestamped external transcription")
    project_ingest.add_argument("--project", type=Path, required=True)
    project_ingest.add_argument("--source-id", required=True)
    project_ingest.add_argument("--input", type=Path, required=True)
    project_ingest.add_argument("--video-url")
    project_ingest.add_argument("--provider")
    project_ingest.add_argument("--permission-ref")
    project_ingest.add_argument("--idempotency-key")
    project_ingest.add_argument("--expected-revision", type=int)
    project_ingest.add_argument("--now")
    project_ingest.add_argument("--json", action="store_true")
    project_revoke = commands.add_parser("project-source-revoke", help="revoke source-derived evidence")
    project_revoke.add_argument("--project", type=Path, required=True)
    project_revoke.add_argument("--source-id", required=True)
    project_revoke.add_argument("--reason", default="operator")
    project_revoke.add_argument("--idempotency-key")
    project_revoke.add_argument("--expected-revision", type=int)
    project_revoke.add_argument("--now")
    project_revoke.add_argument("--json", action="store_true")
    project_source_use = commands.add_parser("project-source-use", help="evaluate one source use authorization")
    project_source_use.add_argument("--project", type=Path, required=True)
    project_source_use.add_argument("--source-id", required=True)
    project_source_use.add_argument("--purpose", required=True)
    project_source_use.add_argument("--region")
    project_source_use.add_argument("--now")
    project_source_use.add_argument("--json", action="store_true")
    project_query = commands.add_parser("project-evidence-query", help="query eligible project evidence")
    project_query.add_argument("--project", type=Path, required=True)
    project_query.add_argument("--query", required=True)
    project_query.add_argument("--filters", type=Path)
    project_query.add_argument("--session-id")
    project_query.add_argument("--max-results", type=int, default=5)
    project_query.add_argument("--now")
    project_query.add_argument("--json", action="store_true")
    project_claim = commands.add_parser("project-claim-record", help="record a classified claim")
    project_claim.add_argument("--project", type=Path, required=True)
    project_claim.add_argument("--input", type=Path, required=True)
    project_claim.add_argument("--idempotency-key")
    project_claim.add_argument("--expected-revision", type=int)
    project_claim.add_argument("--now")
    project_claim.add_argument("--json", action="store_true")
    project_conflict = commands.add_parser("project-conflict-record", help="record an evidence conflict")
    project_conflict.add_argument("--project", type=Path, required=True)
    project_conflict.add_argument("--input", type=Path, required=True)
    project_conflict.add_argument("--idempotency-key")
    project_conflict.add_argument("--expected-revision", type=int)
    project_conflict.add_argument("--now")
    project_conflict.add_argument("--json", action="store_true")
    project_change_propose = commands.add_parser("project-change-propose", help="propose a project change")
    project_change_propose.add_argument("--project", type=Path, required=True)
    project_change_propose.add_argument("--input", type=Path, required=True)
    project_change_propose.add_argument("--idempotency-key")
    project_change_propose.add_argument("--expected-revision", type=int)
    project_change_propose.add_argument("--now")
    project_change_propose.add_argument("--json", action="store_true")
    project_change_inspect = commands.add_parser("project-change-inspect", help="inspect a project change")
    project_change_inspect.add_argument("--project", type=Path, required=True)
    project_change_inspect.add_argument("--change-id", required=True)
    project_change_inspect.add_argument("--json", action="store_true")
    project_change_prepare = commands.add_parser("project-change-prepare", help="prepare a project change")
    project_change_prepare.add_argument("--project", type=Path, required=True)
    project_change_prepare.add_argument("--change-id", required=True)
    project_change_prepare.add_argument("--idempotency-key")
    project_change_prepare.add_argument("--expected-revision", type=int)
    project_change_prepare.add_argument("--now")
    project_change_prepare.add_argument("--json", action="store_true")
    project_change_activate = commands.add_parser("project-change-activate", help="activate a prepared project change")
    project_change_activate.add_argument("--project", type=Path, required=True)
    project_change_activate.add_argument("--change-id", required=True)
    project_change_activate.add_argument("--authorization-id")
    project_change_activate.add_argument("--manual-reviewed", action="store_true")
    project_change_activate.add_argument("--idempotency-key")
    project_change_activate.add_argument("--expected-revision", type=int)
    project_change_activate.add_argument("--now")
    project_change_activate.add_argument("--json", action="store_true")
    project_rollback = commands.add_parser("project-rollback", help="rollback to a project revision")
    project_rollback.add_argument("--project", type=Path, required=True)
    project_rollback.add_argument("--revision-id", required=True)
    project_rollback.add_argument("--idempotency-key")
    project_rollback.add_argument("--expected-revision", type=int)
    project_rollback.add_argument("--now")
    project_rollback.add_argument("--json", action="store_true")
    project_rag_prepare = commands.add_parser("project-rag-prepare", help="prepare an isolated RAG candidate")
    project_rag_prepare.add_argument("--project", type=Path, required=True)
    project_rag_prepare.add_argument("--candidate", type=Path)
    project_rag_prepare.add_argument("--profiles", nargs="+", default=["compact", "multilingual"])
    project_rag_prepare.add_argument("--selected-profile")
    project_rag_prepare.add_argument("--language", default="pt-BR")
    project_rag_prepare.add_argument("--previous-snapshot", type=Path)
    project_rag_prepare.add_argument("--verify-query")
    project_rag_prepare.add_argument("--verify-adapter", default="memory")
    project_rag_prepare.add_argument("--runtime-root", type=Path)
    project_rag_prepare.add_argument("--idempotency-key")
    project_rag_prepare.add_argument("--expected-revision", type=int)
    project_rag_prepare.add_argument("--now")
    project_rag_prepare.add_argument("--json", action="store_true")
    project_candidate_evaluate = commands.add_parser("project-candidate-evaluate", help="evaluate a project candidate")
    project_candidate_evaluate.add_argument("--project", type=Path, required=True)
    project_candidate_evaluate.add_argument("--candidate", type=Path, required=True)
    project_candidate_evaluate.add_argument("--golden", type=Path, required=True)
    project_candidate_evaluate.add_argument("--candidate-id")
    project_candidate_evaluate.add_argument("--snapshot", type=Path)
    project_candidate_evaluate.add_argument("--thresholds", type=Path)
    project_candidate_evaluate.add_argument("--top-k", type=int, default=5)
    project_candidate_evaluate.add_argument("--adapter", default=None)
    project_candidate_evaluate.add_argument("--runtime-root", type=Path)
    project_candidate_evaluate.add_argument("--response-receipt", type=Path)
    project_candidate_evaluate.add_argument("--idempotency-key")
    project_candidate_evaluate.add_argument("--expected-revision", type=int)
    project_candidate_evaluate.add_argument("--now")
    project_candidate_evaluate.add_argument("--json", action="store_true")
    project_dependency = commands.add_parser(
        "project-dependency-mitigation", help="validate dependency mitigation evidence"
    )
    project_dependency.add_argument("--raw-audit", type=Path, required=True)
    project_dependency.add_argument("--mitigation", type=Path, required=True)
    project_dependency.add_argument("--now")
    project_dependency.add_argument("--json", action="store_true")
    project_enrich_dispatch = commands.add_parser("project-enrichment-dispatch", help="dispatch external enrichment")
    project_enrich_dispatch.add_argument("--project", type=Path, required=True)
    project_enrich_dispatch.add_argument("--input", type=Path, required=True)
    project_enrich_dispatch.add_argument("--idempotency-key")
    project_enrich_dispatch.add_argument("--expected-revision", type=int)
    project_enrich_dispatch.add_argument("--now")
    project_enrich_dispatch.add_argument("--json", action="store_true")
    project_enrich_inspect = commands.add_parser("project-enrichment-inspect", help="inspect external enrichment")
    project_enrich_inspect.add_argument("--project", type=Path, required=True)
    project_enrich_inspect.add_argument("--request-id", required=True)
    project_enrich_inspect.add_argument("--json", action="store_true")
    project_enrich_submit = commands.add_parser("project-enrichment-submit", help="submit external enrichment receipt")
    project_enrich_submit.add_argument("--project", type=Path, required=True)
    project_enrich_submit.add_argument("--request-id", required=True)
    project_enrich_submit.add_argument("--input", type=Path, required=True)
    project_enrich_submit.add_argument("--idempotency-key")
    project_enrich_submit.add_argument("--expected-revision", type=int)
    project_enrich_submit.add_argument("--now")
    project_enrich_submit.add_argument("--json", action="store_true")
    project_enrich_timeout = commands.add_parser("project-enrichment-timeout", help="timeout external enrichment")
    project_enrich_timeout.add_argument("--project", type=Path, required=True)
    project_enrich_timeout.add_argument("--request-id", required=True)
    project_enrich_timeout.add_argument("--idempotency-key")
    project_enrich_timeout.add_argument("--expected-revision", type=int)
    project_enrich_timeout.add_argument("--now")
    project_enrich_timeout.add_argument("--json", action="store_true")
    project_enrich_retry = commands.add_parser("project-enrichment-retry", help="retry external enrichment")
    project_enrich_retry.add_argument("--project", type=Path, required=True)
    project_enrich_retry.add_argument("--request-id", required=True)
    project_enrich_retry.add_argument("--idempotency-key")
    project_enrich_retry.add_argument("--expected-revision", type=int)
    project_enrich_retry.add_argument("--now")
    project_enrich_retry.add_argument("--json", action="store_true")
    project_delegate = commands.add_parser("project-delegate", help="create scoped factual delegation")
    project_delegate.add_argument("--project", type=Path, required=True)
    project_delegate.add_argument("--input", type=Path, required=True)
    project_delegate.add_argument("--idempotency-key")
    project_delegate.add_argument("--expected-revision", type=int)
    project_delegate.add_argument("--now")
    project_delegate.add_argument("--json", action="store_true")
    project_delegate_revoke = commands.add_parser("project-delegate-revoke", help="revoke factual delegation")
    project_delegate_revoke.add_argument("--project", type=Path, required=True)
    project_delegate_revoke.add_argument("--authorization-id", required=True)
    project_delegate_revoke.add_argument("--reason", default="operator")
    project_delegate_revoke.add_argument("--idempotency-key")
    project_delegate_revoke.add_argument("--expected-revision", type=int)
    project_delegate_revoke.add_argument("--now")
    project_delegate_revoke.add_argument("--json", action="store_true")
    project_delegate_authorize = commands.add_parser("project-delegate-authorize", help="authorize one factual change")
    project_delegate_authorize.add_argument("--project", type=Path, required=True)
    project_delegate_authorize.add_argument("--change-id", required=True)
    project_delegate_authorize.add_argument("--authorization-id", required=True)
    project_delegate_authorize.add_argument("--idempotency-key")
    project_delegate_authorize.add_argument("--expected-revision", type=int)
    project_delegate_authorize.add_argument("--now")
    project_delegate_authorize.add_argument("--json", action="store_true")
    project_health = commands.add_parser("project-health", help="inspect project health")
    project_health.add_argument("--project", type=Path, required=True)
    project_health.add_argument("--queue", type=Path)
    project_health.add_argument("--max-missed-cycles", type=int, default=None)
    project_health.add_argument("--now")
    project_health.add_argument("--json", action="store_true")
    project_recovery = commands.add_parser("project-recovery", help="inspect project recovery")
    project_recovery.add_argument("--project", type=Path, required=True)
    project_recovery.add_argument("--json", action="store_true")
    project_recovery_run = commands.add_parser("project-recovery-run", help="recover an interrupted project activation")
    project_recovery_run.add_argument("--project", type=Path, required=True)
    project_recovery_run.add_argument("--idempotency-key")
    project_recovery_run.add_argument("--expected-revision", type=int)
    project_recovery_run.add_argument("--json", action="store_true")
    project_backup = commands.add_parser("project-backup", help="create a project backup")
    project_backup.add_argument("--project", type=Path, required=True)
    project_backup.add_argument("--destination", type=Path, required=True)
    project_backup.add_argument("--idempotency-key")
    project_backup.add_argument("--expected-revision", type=int)
    project_backup.add_argument("--now")
    project_backup.add_argument("--json", action="store_true")
    project_backup_verify = commands.add_parser("project-backup-verify", help="verify a project backup")
    project_backup_verify.add_argument("--backup", type=Path, required=True)
    project_backup_verify.add_argument("--json", action="store_true")
    project_restore = commands.add_parser("project-restore", help="restore a project backup in isolation")
    project_restore.add_argument("--backup", type=Path, required=True)
    project_restore.add_argument("--target", type=Path, required=True)
    project_restore.add_argument("--current", type=Path)
    project_restore.add_argument("--idempotency-key")
    project_restore.add_argument("--expected-revision", type=int)
    project_restore.add_argument("--now")
    project_restore.add_argument("--json", action="store_true")
    project_preset = commands.add_parser("project-preset", help="load or attach a project preset")
    project_preset.add_argument("--project", type=Path)
    project_preset.add_argument("--preset", required=True)
    project_preset.add_argument("--idempotency-key")
    project_preset.add_argument("--expected-revision", type=int)
    project_preset.add_argument("--now")
    project_preset.add_argument("--json", action="store_true")
    project_preset_candidates = commands.add_parser(
        "project-preset-candidates", help="generate preset golden candidates"
    )
    project_preset_candidates.add_argument("--preset", required=True)
    project_preset_candidates.add_argument("--theme")
    project_preset_candidates.add_argument("--json", action="store_true")
    project_v2_start = commands.add_parser("project-v2-start", help="start a resumable Farol 2.0 project")
    project_v2_start.add_argument("--project", type=Path, required=True)
    project_v2_start.add_argument("--name", required=True)
    project_v2_start.add_argument("--objective", required=True)
    project_v2_start.add_argument("--sources", type=Path, required=True, help="JSON object or array of sources")
    project_v2_start.add_argument("--idempotency-key", required=True)
    project_v2_start.add_argument("--session-id")
    project_v2_start.add_argument("--json", action="store_true")
    project_v2_inspect = commands.add_parser("project-v2-inspect", help="inspect a Farol 2.0 project")
    project_v2_inspect.add_argument("--project", type=Path, required=True)
    project_v2_inspect.add_argument("--json", action="store_true")
    project_v2_apply = commands.add_parser("project-v2-apply", help="apply a resumable Farol 2.0 operation")
    project_v2_apply.add_argument("--project", type=Path, required=True)
    project_v2_apply.add_argument(
        "--operation", choices=("plan", "apply", "resume", "inspect", "migrate"), required=True
    )
    project_v2_apply.add_argument("--inputs", type=Path, help="JSON object with operation inputs")
    project_v2_apply.add_argument("--expected-revision", type=int, required=True)
    project_v2_apply.add_argument("--idempotency-key", required=True)
    project_v2_apply.add_argument("--json", action="store_true")
    supervisor_run = commands.add_parser("supervisor-run", help="poll a project supervisor once")
    supervisor_run.add_argument("--project", type=Path, required=True)
    supervisor_run.add_argument("--source", type=Path)
    supervisor_run.add_argument("--source-id", default="source-fixture")
    supervisor_run.add_argument("--queue", type=Path)
    supervisor_run.add_argument("--input", type=Path)
    supervisor_run.add_argument("--max-missed-cycles", type=int, default=None)
    supervisor_run.add_argument("--idempotency-key")
    supervisor_run.add_argument("--expected-revision", type=int)
    supervisor_run.add_argument("--now")
    supervisor_run.add_argument("--json", action="store_true")
    supervisor_stop = commands.add_parser("supervisor-stop", help="stop project supervisor")
    supervisor_stop.add_argument("--project", type=Path, required=True)
    supervisor_stop.add_argument("--reason", default="operator")
    supervisor_stop.add_argument("--idempotency-key")
    supervisor_stop.add_argument("--expected-revision", type=int)
    supervisor_stop.add_argument("--now")
    supervisor_stop.add_argument("--json", action="store_true")
    supervisor_resume = commands.add_parser("supervisor-resume", help="resume project supervisor")
    supervisor_resume.add_argument("--project", type=Path, required=True)
    supervisor_resume.add_argument("--idempotency-key")
    supervisor_resume.add_argument("--expected-revision", type=int)
    supervisor_resume.add_argument("--now")
    supervisor_resume.add_argument("--json", action="store_true")
    lifecycle_status = commands.add_parser("lifecycle-status", help="show the versioned lifecycle status")
    lifecycle_status.add_argument("--package", type=Path, required=True)
    lifecycle_status.add_argument("--runtime-root", type=Path)
    lifecycle_status.add_argument("--json", action="store_true")
    lifecycle = commands.add_parser(
        "lifecycle",
        help="canonical hierarchy for reviewed lifecycle operations",
        description="Canonical lifecycle command hierarchy",
        epilog=_CANONICAL_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    lifecycle.set_defaults(_canonical_namespace=True)
    config_audit = commands.add_parser("config-audit", help="audit package transport security")
    config_audit.add_argument("config", type=Path)
    config_audit.add_argument("--json", action="store_true")
    return parser


def _layers_from_args(args: argparse.Namespace) -> tuple[str, ...]:
    values = list(args.layer_values or [])
    if args.layers_csv:
        values.extend(part.strip() for part in args.layers_csv.split(","))
    return tuple(values) if values else ("conceptual", "factual")


def _read_input_file(path: Path | None) -> dict[str, object]:
    if path is None:
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("--input must contain a JSON object")
    return value


def _read_sources_file(path: Path) -> list[dict[str, object]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, dict):
        value = value.get("sources")
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError("--sources must contain a JSON array or an object with a sources array")
    return [dict(item) for item in value]


def _new_result_exit(result: dict[str, object]) -> int:
    outcome = result.get("outcome")
    if outcome == "needs_input":
        return 2
    if outcome == "blocked":
        return 3
    return 0 if result.get("ok") else 1


def _print_new_result(result: dict[str, object]) -> int:
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return _new_result_exit(result)


def _recovery_result(project: Path, *, run: bool) -> dict[str, object]:
    return recover_project_activation(project) if run else inspect_project_recovery(project)


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "skill":
        if args.skill_command != "path":
            return 2
        result = {"ok": True, **skill_metadata(args.skill_root)}
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) if args.json else result["path"])
        return 0
    if args.command == "agents-bootstrap":
        result = install_agents_bootstrap(args.root, check=args.check)
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) if args.json else result["status"])
        return 0 if result["ok"] else 2
    if args.command == "lifecycle-status":
        result = LifecycleFacade(args.package, runtime_root=args.runtime_root).status()
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) if args.json else result)
        return 0 if result.get("ok") else 1
    if args.command == "init-start":
        preset = load_project_preset(args.preset) if args.preset else None
        result = start_project_init(
            args.project,
            _read_input_file(args.input),
            preset={"id": preset["id"], "version": preset["version"]} if preset else None,
            expected_revision=args.expected_revision,
            idempotency_key=args.idempotency_key,
            now=args.now,
        )
        return _print_new_result(result)
    if args.command == "init-status":
        return _print_new_result(inspect_project_init(args.project, session_id=args.session_id))
    if args.command == "init-answer":
        body = _read_input_file(args.input)
        result = answer_project_init(
            args.project,
            body,
            expected_revision=args.expected_revision,
            idempotency_key=args.idempotency_key,
            now=args.now,
        )
        return _print_new_result(result)
    if args.command == "init-finalize":
        result = finalize_project_init(
            args.project,
            _read_input_file(args.input),
            expected_revision=args.expected_revision,
            idempotency_key=args.idempotency_key,
            now=args.now,
        )
        return _print_new_result(result)
    if args.command == "project-inspect":
        return _print_new_result(inspect_project(args.project))
    if args.command == "project-v2-start":
        result = ProjectService(args.project).start(
            args.name,
            args.objective,
            _read_sources_file(args.sources),
            idempotency_key=args.idempotency_key,
            session_id=args.session_id,
        )
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False, sort_keys=True))
        return 0 if result.status == "succeeded" else 2 if result.status == "needs_input" else 1
    if args.command == "project-v2-inspect":
        project = ProjectService(args.project).inspect()
        print(json.dumps(project.to_dict(), indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "project-v2-apply":
        result = ProjectService(args.project).apply(
            args.operation,
            _read_input_file(args.inputs),
            expected_revision=args.expected_revision,
            idempotency_key=args.idempotency_key,
        )
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False, sort_keys=True))
        return 0 if result.status in {"succeeded", "resumed"} else 2 if result.status == "needs_input" else 1
    if args.command == "project-adopt":
        return _print_new_result(
            adopt_project_package(
                args.project,
                args.package,
                dry_run=args.dry_run,
                backup=not args.no_backup,
                expected_revision=args.expected_revision,
                idempotency_key=args.idempotency_key,
                now=args.now,
            )
        )
    if args.command == "project-source-govern":
        return _print_new_result(
            register_source_governance(
                args.project,
                _read_input_file(args.input),
                readmit=args.readmit,
                expected_revision=args.expected_revision,
                idempotency_key=args.idempotency_key,
                now=args.now,
            )
        )
    if args.command == "project-source-ingest":
        return _print_new_result(
            ingest_external_transcription(
                args.project,
                args.source_id,
                args.input,
                video_url=args.video_url,
                provider=args.provider,
                permission_ref=args.permission_ref,
                expected_revision=args.expected_revision,
                idempotency_key=args.idempotency_key,
                now=args.now,
            )
        )
    if args.command == "project-source-revoke":
        return _print_new_result(
            revoke_project_source(
                args.project,
                args.source_id,
                reason=args.reason,
                expected_revision=args.expected_revision,
                idempotency_key=args.idempotency_key,
                now=args.now,
            )
        )
    if args.command == "project-source-use":
        return _print_new_result(
            source_use_decision(args.project, args.source_id, args.purpose, region=args.region, now=args.now)
        )
    if args.command == "project-evidence-query":
        filters = _read_input_file(args.filters) if args.filters else None
        return _print_new_result(
            query_project_evidence(
                args.project,
                args.query,
                filters=filters,
                session_id=args.session_id,
                max_results=args.max_results,
                now=args.now,
            )
        )
    if args.command == "project-claim-record":
        return _print_new_result(
            record_project_claim(
                args.project,
                _read_input_file(args.input),
                expected_revision=args.expected_revision,
                idempotency_key=args.idempotency_key,
                now=args.now,
            )
        )
    if args.command == "project-conflict-record":
        return _print_new_result(
            record_project_conflict(
                args.project,
                _read_input_file(args.input),
                expected_revision=args.expected_revision,
                idempotency_key=args.idempotency_key,
                now=args.now,
            )
        )
    if args.command == "project-change-propose":
        return _print_new_result(
            propose_project_change(
                args.project,
                _read_input_file(args.input),
                expected_revision=args.expected_revision,
                idempotency_key=args.idempotency_key,
                now=args.now,
            )
        )
    if args.command == "project-change-inspect":
        return _print_new_result(inspect_project_change(args.project, args.change_id))
    if args.command == "project-change-prepare":
        return _print_new_result(
            prepare_project_change(
                args.project,
                args.change_id,
                expected_revision=args.expected_revision,
                idempotency_key=args.idempotency_key,
                now=args.now,
            )
        )
    if args.command == "project-change-activate":
        result = activate_project_change(
            args.project,
            args.change_id,
            expected_revision=args.expected_revision,
            authorization_id=args.authorization_id,
            manual_reviewed=args.manual_reviewed,
            idempotency_key=args.idempotency_key,
            now=args.now,
        )
        return _print_new_result(result)
    if args.command == "project-rollback":
        return _print_new_result(
            rollback_project(
                args.project,
                args.revision_id,
                expected_revision=args.expected_revision,
                idempotency_key=args.idempotency_key,
                now=args.now,
            )
        )
    if args.command == "project-rag-prepare":
        return _print_new_result(
            prepare_project_rag_candidate(
                args.project,
                args.candidate,
                profiles=tuple(args.profiles),
                selected_profile=args.selected_profile,
                language=args.language,
                previous_snapshot=args.previous_snapshot,
                verify_query=args.verify_query,
                verify_adapter=args.verify_adapter,
                runtime_root=args.runtime_root,
                expected_revision=args.expected_revision,
                idempotency_key=args.idempotency_key,
                now=args.now,
            )
        )
    if args.command == "project-candidate-evaluate":
        thresholds = _read_input_file(args.thresholds) if args.thresholds else None
        return _print_new_result(
            evaluate_project_candidate(
                args.project,
                args.candidate,
                args.golden,
                candidate_id=args.candidate_id,
                snapshot=args.snapshot,
                thresholds=thresholds,
                top_k=args.top_k,
                adapter=args.adapter,
                runtime_root=args.runtime_root,
                response_receipt=args.response_receipt,
                expected_revision=args.expected_revision,
                idempotency_key=args.idempotency_key,
                now=args.now,
            )
        )
    if args.command == "project-dependency-mitigation":
        return _print_new_result(validate_dependency_mitigation(args.raw_audit, args.mitigation, now=args.now))
    if args.command == "project-enrichment-dispatch":
        return _print_new_result(
            dispatch_project_enrichment(
                args.project,
                _read_input_file(args.input),
                expected_revision=args.expected_revision,
                idempotency_key=args.idempotency_key,
                now=args.now,
            )
        )
    if args.command == "project-enrichment-inspect":
        return _print_new_result(inspect_project_enrichment(args.project, args.request_id))
    if args.command == "project-enrichment-submit":
        return _print_new_result(
            submit_project_enrichment(
                args.project,
                args.request_id,
                _read_input_file(args.input),
                expected_revision=args.expected_revision,
                idempotency_key=args.idempotency_key,
                now=args.now,
            )
        )
    if args.command == "project-enrichment-timeout":
        return _print_new_result(
            timeout_project_enrichment(
                args.project,
                args.request_id,
                expected_revision=args.expected_revision,
                idempotency_key=args.idempotency_key,
                now=args.now,
            )
        )
    if args.command == "project-enrichment-retry":
        return _print_new_result(
            retry_project_enrichment(
                args.project,
                args.request_id,
                expected_revision=args.expected_revision,
                idempotency_key=args.idempotency_key,
                now=args.now,
            )
        )
    if args.command == "project-delegate":
        return _print_new_result(
            create_delegated_authorization(
                args.project,
                _read_input_file(args.input),
                expected_revision=args.expected_revision,
                idempotency_key=args.idempotency_key,
                now=args.now,
            )
        )
    if args.command == "project-delegate-revoke":
        return _print_new_result(
            revoke_delegated_authorization(
                args.project,
                args.authorization_id,
                reason=args.reason,
                expected_revision=args.expected_revision,
                idempotency_key=args.idempotency_key,
                now=args.now,
            )
        )
    if args.command == "project-delegate-authorize":
        return _print_new_result(
            authorize_factual_change(
                args.project,
                args.change_id,
                args.authorization_id,
                expected_revision=args.expected_revision,
                idempotency_key=args.idempotency_key,
                now=args.now,
            )
        )
    if args.command == "project-health":
        return _print_new_result(
            inspect_project_health(
                args.project, queue_path=args.queue, max_missed_cycles=args.max_missed_cycles, now=args.now
            )
        )
    if args.command == "project-recovery":
        return _print_new_result(_recovery_result(args.project, run=False))
    if args.command == "project-recovery-run":
        return _print_new_result(
            recover_project_activation(
                args.project,
                expected_revision=args.expected_revision,
                idempotency_key=args.idempotency_key,
            )
        )
    if args.command == "project-backup":
        return _print_new_result(
            backup_project(
                args.project,
                args.destination,
                expected_revision=args.expected_revision,
                idempotency_key=args.idempotency_key,
                now=args.now,
            )
        )
    if args.command == "project-backup-verify":
        return _print_new_result(verify_project_backup(args.backup))
    if args.command == "project-restore":
        return _print_new_result(
            restore_project(
                args.backup,
                args.target,
                current_root=args.current,
                expected_revision=args.expected_revision,
                idempotency_key=args.idempotency_key,
                now=args.now,
            )
        )
    if args.command == "project-preset":
        if args.project:
            return _print_new_result(
                apply_project_preset(
                    args.project,
                    args.preset,
                    expected_revision=args.expected_revision,
                    idempotency_key=args.idempotency_key,
                    now=args.now,
                )
            )
        return _print_new_result(
            {
                "schema_version": 1,
                "ok": True,
                "outcome": "unchanged",
                "data": {"preset": load_project_preset(args.preset)},
                "errors": [],
                "next_actions": [],
            }
        )
    if args.command == "project-preset-candidates":
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "ok": True,
                    "preset": args.preset,
                    "reviewed": False,
                    "cases": project_preset_golden_candidates(args.preset, theme=args.theme),
                },
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "supervisor-run":
        return _print_new_result(
            run_project_supervisor_once(
                args.project,
                source_path=args.source,
                source_id=args.source_id,
                queue_path=args.queue,
                work=_read_input_file(args.input),
                max_missed_cycles=args.max_missed_cycles,
                expected_revision=args.expected_revision,
                idempotency_key=args.idempotency_key,
                now=args.now,
            )
        )
    if args.command == "supervisor-stop":
        return _print_new_result(
            stop_project_supervisor(
                args.project,
                reason=args.reason,
                expected_revision=args.expected_revision,
                idempotency_key=args.idempotency_key,
                now=args.now,
            )
        )
    if args.command == "supervisor-resume":
        return _print_new_result(
            resume_project_supervisor(
                args.project,
                expected_revision=args.expected_revision,
                idempotency_key=args.idempotency_key,
                now=args.now,
            )
        )
    if args.command == "doctor":
        report = run_doctor(args.root)
        if args.json:
            print(report.to_json())
        else:
            print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        return 0 if report.ok else 1
    if args.command == "resolve":
        resolver = (
            SourceResolver.from_catalog_file(args.catalog, root=args.root)
            if args.catalog
            else SourceResolver(root=args.root)
        )
        resolution = resolver.resolve(args.source, version=args.version, scope=args.scope, language=args.language)
        print(
            json.dumps(
                redact_report(redact_metadata(resolution.to_dict())), indent=2, ensure_ascii=False, sort_keys=True
            )
        )
        return 0 if resolution.selected is not None and not resolution.requires_decision else 2
    if args.command == "plan":
        operation = build_plan(
            args.source,
            options=OperationOptions(
                output_dir=args.output,
                catalog=args.catalog,
                slug=args.slug,
                version=args.version,
                scope=args.scope,
                language=args.language,
                mode=args.mode,
                layers=_layers_from_args(args),
                publication_policy=args.publication_policy,
                license=args.license,
                redistribution=args.redistribution,
                index_rag=args.index_rag,
                allow_private_network=args.allow_private_network,
                max_pages=args.max_pages,
                max_depth=args.max_depth,
                include_patterns=tuple(args.include_patterns),
                exclude_patterns=tuple(args.exclude_patterns),
                runtime_root=args.runtime_root,
                source_root=args.source_root,
                lease_policy=args.lease_policy,
                lease_timeout_seconds=args.lease_timeout_seconds,
                stale_lease_seconds=args.stale_lease_seconds,
            ),
        )
        print(operation.json())
        return 0 if operation.ok else 2
    if args.command == "run":
        operation = build_plan(
            args.source,
            options=OperationOptions(
                output_dir=args.output,
                catalog=args.catalog,
                slug=args.slug,
                version=args.version,
                scope=args.scope,
                language=args.language,
                mode=args.mode,
                layers=_layers_from_args(args),
                publication_policy=args.publication_policy,
                license=args.license,
                redistribution=args.redistribution,
                index_rag=args.index_rag,
                allow_private_network=args.allow_private_network,
                max_pages=args.max_pages,
                max_depth=args.max_depth,
                include_patterns=tuple(args.include_patterns),
                exclude_patterns=tuple(args.exclude_patterns),
                runtime_root=args.runtime_root,
                source_root=args.source_root,
                lease_policy=args.lease_policy,
                lease_timeout_seconds=args.lease_timeout_seconds,
                stale_lease_seconds=args.stale_lease_seconds,
            ),
        )
        result = preview(operation) if args.mode == "dry-run" else apply_operation(operation)
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False, sort_keys=True))
        return result.exit_code if not result.ok else 0
    if args.command == "validate":
        result = validate_package(args.package)
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False, sort_keys=True))
        return 0 if result.ok else 1
    if args.command == "cleanup":
        result = cleanup_residue(
            args.package,
            retention_seconds=args.retention_seconds,
            keep_attempts=args.keep_attempts,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return 0 if result.get("ok") else 3 if result.get("code") == "writer_busy" else 1
    if args.command == "evaluate":
        metric_top_k = args.top_k if 1 <= args.top_k <= 100 else 5
        result = evaluate_package(
            args.package,
            args.cases,
            thresholds={
                f"recall_at_{metric_top_k}": args.recall_threshold,
                f"mrr_at_{metric_top_k}": args.mrr_threshold,
                "response_fidelity": args.response_fidelity_threshold,
                "citation_coverage": args.citation_coverage_threshold,
            },
            top_k=args.top_k,
            adapter=args.adapter,
            runtime_root=args.runtime_root,
            response_receipt=args.response_receipt,
        )
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False, sort_keys=True))
        return 0 if result.ok else 1
    if args.command == "golden-candidates":
        payload = {
            "schema_version": 1,
            "reviewed": False,
            "cases": generate_golden_candidates(args.package, limit=args.limit),
        }
        contract = validate_artifact("golden-candidates", payload)
        if not contract.ok:
            raise ValueError("generated golden candidates violate their contract")
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "candidate-request":
        payload = export_enrichment_request(args.package, args.candidate_id, language=args.language)
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "candidate-submit":
        payload = submit_enrichment(args.package, args.candidate_id, args.source_dir, args.receipt)
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "candidate-approve":
        authority = None
        if args.authority_json is not None:
            try:
                authority = json.loads(args.authority_json)
            except json.JSONDecodeError as exc:
                raise CandidatePublicationError(
                    "approval_authority_invalid",
                    "--authority-json must contain valid JSON",
                ) from exc
        payload = approve_candidate(
            args.package,
            args.candidate_id,
            actor=args.actor,
            role=args.role,
            authority=authority,
        )
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "candidate-publish":
        payload = publish_candidate(args.package, args.candidate_id)
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "candidate-rollback":
        payload = rollback_candidate(args.package, args.release_id)
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "source-register":
        payload = register_source(
            args.package,
            source_id=args.source_id,
            canonical=args.canonical,
            kind=args.kind,
            scope=args.scope,
            version_policy=args.version_policy,
            version=args.version,
            language=args.language,
            rights=args.rights,
            privacy=args.privacy,
            authority=args.authority,
            owner=args.owner,
            readmit=args.readmit,
        )
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "source-reconcile":
        payload = reconcile_source(
            args.package,
            args.snapshot,
            source_id=args.source_id,
            withdraw=args.withdraw,
        )
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 0 if payload.get("ok") else 2
    if args.command == "event-submit":
        payload = submit_event(args.queue, args.event, now=args.now)
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command in {"jobs", "jobs-list"}:
        payload = list_jobs(args.queue, now=args.now)
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "work":
        payload = work_once(
            args.queue,
            now=args.now,
            worker_id=args.worker_id,
            lease_seconds=args.lease_seconds,
        )
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 0 if payload.get("ok") else 2
    if args.command == "impact-assess":
        payload = assess_conceptual_impact(
            args.package,
            args.events,
            now=args.now,
            threshold=args.threshold,
            budget=args.budget,
            corpus_documents=args.corpus_documents,
            causation_id=args.causation_id,
        )
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "reader-session":
        payload = create_reader_session(
            args.package,
            adapter=args.adapter,
            session_id=args.session_id,
            snapshot=args.snapshot,
            now=args.now,
            expires_at=args.expires_at,
        )
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "reader-query":
        payload = query_reader_session(
            args.package,
            args.session,
            tool=args.tool,
            query=args.query,
            adapter=args.adapter,
            max_results=args.max_results,
            now=args.now,
            runtime_root=args.runtime_root,
        )
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "reader-session-revoke":
        payload = revoke_reader_session(
            args.package,
            args.session,
            now=args.now,
            reason=args.reason,
        )
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "rag-snapshot":
        try:
            payload = snapshot_rag_package(
                args.package,
                previous=args.previous,
                snapshot_out=args.snapshot_out,
                backend=args.backend,
                supports_incremental=args.supports_incremental,
                server_version=args.server_version,
                verify_query=args.verify_query,
                verify_adapter=args.verify_adapter,
                runtime_root=args.runtime_root,
            )
        except RagSnapshotError as exc:
            print(
                json.dumps(
                    {
                        "schema_version": 1,
                        "ok": False,
                        "active_preserved": True,
                        "error": {"code": exc.code, "message": redact_text(exc)},
                    },
                    indent=2,
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 1
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "rag-profile-compare":
        try:
            profiles = tuple(part.strip() for part in args.profiles.split(","))
            payload = compare_embedding_profiles(
                args.package,
                profiles=profiles,
                language=args.language,
                selected_profile=args.select_profile,
            )
        except RagSnapshotError as exc:
            print(
                json.dumps(
                    {
                        "schema_version": 1,
                        "ok": False,
                        "publication_allowed": False,
                        "error": {"code": exc.code, "message": redact_text(exc)},
                    },
                    indent=2,
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 1
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command in {"learning-submit", "learning_submit"}:
        payload = submit_learning_proposal(
            args.package,
            args.proposal,
            capture_opt_in=args.capture_opt_in,
            now=args.now,
        )
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command in {"learning-review", "learning_review"}:
        evidence = None
        if args.evidence:
            evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
        payload = review_learning_proposal(
            args.package,
            args.proposal_id,
            decision=args.decision,
            actor=args.actor,
            role=args.role,
            evidence=evidence,
            now=args.now,
            reason=args.reason,
        )
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command in {"feedback-submit", "feedback_submit"}:
        payload = submit_feedback(
            args.package,
            args.feedback,
            now=args.now,
            queue_path=args.queue,
        )
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command in {"feedback-report", "feedback_report"}:
        payload = build_feedback_report(
            args.package,
            now=args.now,
            window_days=args.window_days,
        )
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "config-audit":
        try:
            result = audit_config_file(args.config)
        except (OSError, ValueError) as exc:
            print(
                json.dumps(
                    {"schema_version": 1, "ok": False, "errors": [{"code": "config_unreadable", "message": str(exc)}]},
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 1
        print(result.to_json())
        return 0 if result.ok else 1
    return 2


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if len(raw_argv) == 2 and raw_argv[0] in _CANONICAL_GROUP_HELP and raw_argv[1] in {"-h", "--help"}:
        print(f"usage: docops {_CANONICAL_GROUP_HELP[raw_argv[0]]}")
        print("Use a concrete subcommand followed by --help for its options.")
        return 0
    args = build_parser().parse_args(_expand_canonical_argv(raw_argv))
    try:
        return _dispatch(args)
    except (OSError, TypeError, UnicodeError, ValueError, ProjectError) as exc:
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "ok": False,
                    "errors": [
                        {
                            "code": str(getattr(exc, "code", "invalid_request")),
                            "message": redact_text(exc),
                        }
                    ],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
