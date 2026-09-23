"""Portable, deterministic orchestration helpers for the documentation pipeline."""

__all__ = [
    "__version__",
    "OperationOptions",
    "OperationPlan",
    "OperationRequest",
    "OperationResult",
    "PipelineOptions",
    "approve_candidate",
    "apply",
    "cleanup",
    "inspect",
    "plan",
    "publish_candidate",
    "preview",
    "rollback_candidate",
    "reconcile_source",
    "register_source",
    "list_jobs",
    "submit_event",
    "work_once",
    "renew_job_lease",
    "assess_conceptual_impact",
    "create_reader_session",
    "query_reader_session",
    "revoke_reader_session",
    "build_rag_snapshot",
    "read_rag_snapshot",
    "rag_snapshot_identity",
    "validate_rag_snapshot",
    "compare_embedding_profiles",
    "plan_rag_reuse",
    "snapshot_rag_package",
    "submit_learning_proposal",
    "review_learning_proposal",
    "read_learning_proposal",
    "submit_feedback",
    "build_feedback_report",
    "report_feedback",
    "CanonicalLifecycle",
    "Lifecycle",
    "LifecycleError",
    "LifecycleFacade",
    "LifecycleStateMachine",
    "RuntimeState",
    "lifecycle_status",
    "start_project_init",
    "inspect_project_init",
    "answer_project_init",
    "finalize_project_init",
    "adopt_project_package",
    "rollback_project_adoption",
    "inspect_project",
    "register_source_governance",
    "source_use_decision",
    "ingest_external_transcription",
    "record_project_claim",
    "record_project_conflict",
    "revoke_project_source",
    "query_project_evidence",
    "prepare_project_rag_candidate",
    "evaluate_project_candidate",
    "propose_project_change",
    "inspect_project_change",
    "prepare_project_change",
    "activate_project_change",
    "rollback_project",
    "dispatch_project_enrichment",
    "inspect_project_enrichment",
    "submit_project_enrichment",
    "timeout_project_enrichment",
    "retry_project_enrichment",
    "create_delegated_authorization",
    "revoke_delegated_authorization",
    "authorize_factual_change",
    "load_project_preset",
    "apply_project_preset",
    "project_preset_golden_candidates",
    "run_project_supervisor_once",
    "stop_project_supervisor",
    "resume_project_supervisor",
    "inspect_project_health",
    "inspect_project_recovery",
    "recover_project_activation",
    "backup_project",
    "verify_project_backup",
    "restore_project",
    "validate_dependency_mitigation",
    "KnowledgeProjectV2",
    "OperationRequestV2",
    "OperationResultV2",
    "CapabilityV2",
    "MigrationPlanV2",
    "KnowledgeBackend",
    "QueryRequest",
    "RagFlowAdapter",
    "TaxonomyEngine",
    "TaxonomyError",
    "TaxonomyNode",
    "TaxonomyProposal",
    "TaxonomyRevision",
    "BookToSkillAdapter",
    "ClaimLineage",
    "SkillArtifact",
    "SynthesisCandidate",
    "SynthesisEngine",
    "SynthesisError",
    "SynthesisReceipt",
    "SynthesisRequest",
    "GlobalRouter",
    "RoutePlan",
    "RouterError",
    "route_query_v2",
    "CompositionCandidate",
    "CompositionError",
    "CompositionManager",
    "CompositionReceipt",
    "LegacyInspection",
    "MigrationError",
    "MigrationReceipt",
    "apply_migration",
    "inspect_legacy_package",
    "plan_migration",
    "rollback_migration",
    "ProjectError",
    "ProjectService",
    "CutoverDecision",
    "evaluate_cutover",
    "build_cutover_receipt",
    "cutover_metrics_from_arms",
    "SurfaceAudit",
    "audit_release_surface",
    "require_cutover_approved",
]
__version__ = "2.0.0rc1"

from .api_types import CapabilityV2, KnowledgeProjectV2, MigrationPlanV2, OperationRequestV2, OperationResultV2
from .backends import KnowledgeBackend, QueryRequest, RagFlowAdapter
from .composition import CompositionCandidate, CompositionError, CompositionManager, CompositionReceipt
from .migration import (
    LegacyInspection,
    MigrationError,
    MigrationReceipt,
    apply_migration,
    inspect_legacy_package,
    plan_migration,
    rollback_migration,
)
from .project import ProjectError, ProjectService
from .release_v2 import (
    CutoverDecision,
    SurfaceAudit,
    audit_release_surface,
    build_cutover_receipt,
    cutover_metrics_from_arms,
    evaluate_cutover,
    require_cutover_approved,
)
from .router import GlobalRouter, RoutePlan, RouterError, route_query_v2
from .synthesis import (
    BookToSkillAdapter,
    ClaimLineage,
    SkillArtifact,
    SynthesisCandidate,
    SynthesisEngine,
    SynthesisError,
    SynthesisReceipt,
    SynthesisRequest,
)
from .taxonomy import TaxonomyEngine, TaxonomyError, TaxonomyNode, TaxonomyProposal, TaxonomyRevision


def plan(*args, **kwargs):
    """Build a side-effect-free operation plan."""

    from .operations import plan as build_plan

    return build_plan(*args, **kwargs)


def apply(*args, **kwargs):
    """Apply a previously created operation plan."""

    from .operations import apply as apply_plan

    return apply_plan(*args, **kwargs)


def cleanup(*args, **kwargs):
    """Remove expired, non-resumable operation residue safely."""

    from .operations import cleanup as cleanup_residue

    return cleanup_residue(*args, **kwargs)


def inspect(*args, **kwargs):
    """Inspect the active package and recoverable operation residue."""

    from .operations import inspect as inspect_package

    return inspect_package(*args, **kwargs)


def preview(*args, **kwargs):
    """Turn a plan into a terminal no-effects result."""

    from .operations import preview as preview_plan

    return preview_plan(*args, **kwargs)


def approve_candidate(*args, **kwargs):
    """Record explicit authority for a reviewable candidate."""

    from .operations import approve_candidate as approve

    return approve(*args, **kwargs)


def publish_candidate(*args, **kwargs):
    """Promote an approved candidate after exact evidence revalidation."""

    from .operations import publish_candidate as publish

    return publish(*args, **kwargs)


def rollback_candidate(*args, **kwargs):
    """Restore one retained editorial generation after exact validation."""

    from .operations import rollback_candidate as rollback

    return rollback(*args, **kwargs)


def register_source(*args, **kwargs):
    """Register one source without replacing other source registrations."""

    from .source_policy import register_source as register

    return register(*args, **kwargs)


def reconcile_source(*args, **kwargs):
    """Reconcile one acquisition snapshot without implicit withdrawal."""

    from .source_policy import reconcile_source as reconcile

    return reconcile(*args, **kwargs)


def submit_event(*args, **kwargs):
    """Persist a coordination event and coalesce its durable job."""

    from .coordination import submit_event as submit

    return submit(*args, **kwargs)


def list_jobs(*args, **kwargs):
    """List the public durable-job projection."""

    from .coordination import list_jobs as list_queue_jobs

    return list_queue_jobs(*args, **kwargs)


def work_once(*args, **kwargs):
    """Claim and execute at most one durable job with resumable effects."""

    from .coordination import work_once as execute_work_once

    return execute_work_once(*args, **kwargs)


def renew_job_lease(*args, **kwargs):
    """Renew a worker lease using the current fencing token."""

    from .coordination import renew_job_lease as renew

    return renew(*args, **kwargs)


def assess_conceptual_impact(*args, **kwargs):
    """Assess conceptual impact without publishing or mutating active knowledge."""

    from .triggers import assess_conceptual_impact as assess

    return assess(*args, **kwargs)


def create_reader_session(*args, **kwargs):
    """Pin a read-only session to one package generation."""

    from .reader_sessions import create_reader_session as create

    return create(*args, **kwargs)


def query_reader_session(*args, **kwargs):
    """Query only read tools through a pinned reader session."""

    from .reader_sessions import query_reader_session as query

    return query(*args, **kwargs)


def revoke_reader_session(*args, **kwargs):
    """Revoke a reader session without changing package content."""

    from .reader_sessions import revoke_reader_session as revoke

    return revoke(*args, **kwargs)


def build_rag_snapshot(*args, **kwargs):
    """Build a relocatable content snapshot without mutating the package."""

    from .rag_snapshots import build_rag_snapshot as build

    return build(*args, **kwargs)


def read_rag_snapshot(*args, **kwargs):
    """Read and verify a relocatable RAG snapshot."""

    from .rag_snapshots import read_rag_snapshot as read

    return read(*args, **kwargs)


def rag_snapshot_identity(*args, **kwargs):
    """Return the compact identity used to pin a reader to a snapshot."""

    from .rag_snapshots import rag_snapshot_identity as identity

    return identity(*args, **kwargs)


def validate_rag_snapshot(*args, **kwargs):
    """Validate a snapshot against a package generation and revocations."""

    from .rag_snapshots import validate_rag_snapshot as validate

    return validate(*args, **kwargs)


def compare_embedding_profiles(*args, **kwargs):
    """Compare embedding profiles without changing the active package."""

    from .rag_snapshots import compare_embedding_profiles as compare

    return compare(*args, **kwargs)


def plan_rag_reuse(*args, **kwargs):
    """Plan incremental reuse or a declared full rebuild."""

    from .rag_snapshots import plan_rag_reuse as plan

    return plan(*args, **kwargs)


def snapshot_rag_package(*args, **kwargs):
    """Build and optionally persist a snapshot plus its non-mutating reuse plan."""

    from .rag_snapshots import snapshot_rag_package as snapshot

    return snapshot(*args, **kwargs)


def submit_learning_proposal(*args, **kwargs):
    """Capture one minimized conversation-derived proposal in quarantine."""

    from .learning import submit_learning_proposal as submit

    return submit(*args, **kwargs)


def review_learning_proposal(*args, **kwargs):
    """Review one quarantined proposal with explicit human authority."""

    from .learning import review_learning_proposal as review

    return review(*args, **kwargs)


def read_learning_proposal(*args, **kwargs):
    """Read one learning proposal through its validation boundary."""

    from .learning import read_learning_proposal as read

    return read(*args, **kwargs)


def submit_feedback(*args, **kwargs):
    """Persist a redacted usage signal without changing active knowledge."""

    from .feedback import submit_feedback as submit

    return submit(*args, **kwargs)


def build_feedback_report(*args, **kwargs):
    """Aggregate usage signals into review-only investigations."""

    from .feedback import build_feedback_report as build

    return build(*args, **kwargs)


def report_feedback(*args, **kwargs):
    """Compatibility alias for the public feedback report operation."""

    from .feedback import report_feedback as report

    return report(*args, **kwargs)


def lifecycle_status(*args, **kwargs):
    """Return the versioned status projection of the canonical lifecycle."""

    from .lifecycle import lifecycle_status as status

    return status(*args, **kwargs)


def start_project_init(*args, **kwargs):
    """Start or resume a private structured project initialization session."""

    from .master import start_project_init as start

    return start(*args, **kwargs)


def inspect_project_init(*args, **kwargs):
    """Read a project initialization session without changing it."""

    from .master import inspect_project_init as inspect_session

    return inspect_session(*args, **kwargs)


def answer_project_init(*args, **kwargs):
    """Apply structured answers using session compare-and-swap."""

    from .master import answer_project_init as answer

    return answer(*args, **kwargs)


def finalize_project_init(*args, **kwargs):
    """Finalize one private immutable project revision."""

    from .master import finalize_project_init as finalize

    return finalize(*args, **kwargs)


def adopt_project_package(*args, **kwargs):
    """Adopt a verified legacy package without rebuilding its RAG index."""

    from .master import adopt_project_package as adopt

    return adopt(*args, **kwargs)


def rollback_project_adoption(*args, **kwargs):
    """Restore a retained package-adoption backup."""

    from .master import rollback_project_adoption as rollback

    return rollback(*args, **kwargs)


def inspect_project(*args, **kwargs):
    """Inspect project identity, revision and package state."""

    from .master import inspect_project as inspect_state

    return inspect_state(*args, **kwargs)


def register_source_governance(*args, **kwargs):
    """Register per-purpose, fail-closed governance for one source."""

    from .master import register_source_governance as register

    return register(*args, **kwargs)


def source_use_decision(*args, **kwargs):
    """Evaluate the effective authorization for one source use."""

    from .master import source_use_decision as decide

    return decide(*args, **kwargs)


def ingest_external_transcription(*args, **kwargs):
    """Persist timestamped external transcription with provenance."""

    from .master import ingest_external_transcription as ingest

    return ingest(*args, **kwargs)


def record_project_claim(*args, **kwargs):
    """Record a classified evidence claim in review-only storage."""

    from .master import record_project_claim as record

    return record(*args, **kwargs)


def record_project_conflict(*args, **kwargs):
    """Record an explicit open or reviewed conflict relation."""

    from .master import record_project_conflict as record

    return record(*args, **kwargs)


def revoke_project_source(*args, **kwargs):
    """Revoke source-derived evidence and write durable tombstones."""

    from .master import revoke_project_source as revoke

    return revoke(*args, **kwargs)


def query_project_evidence(*args, **kwargs):
    """Query project evidence with typed filters and explicit evidence outcome."""

    from .master import query_project_evidence as query

    return query(*args, **kwargs)


def prepare_project_rag_candidate(*args, **kwargs):
    """Prepare an isolated, profile-pinned project RAG candidate."""

    from .master import prepare_project_rag_candidate as prepare

    return prepare(*args, **kwargs)


def evaluate_project_candidate(*args, **kwargs):
    """Evaluate a project candidate against a pinned snapshot and Golden set."""

    from .master import evaluate_project_candidate as evaluate

    return evaluate(*args, **kwargs)


def propose_project_change(*args, **kwargs):
    from .master import propose_project_change as propose

    return propose(*args, **kwargs)


def inspect_project_change(*args, **kwargs):
    from .master import inspect_project_change as inspect_change

    return inspect_change(*args, **kwargs)


def prepare_project_change(*args, **kwargs):
    from .master import prepare_project_change as prepare

    return prepare(*args, **kwargs)


def activate_project_change(*args, **kwargs):
    from .master import activate_project_change as activate

    return activate(*args, **kwargs)


def rollback_project(*args, **kwargs):
    from .master import rollback_project as rollback

    return rollback(*args, **kwargs)


def dispatch_project_enrichment(*args, **kwargs):
    from .master import dispatch_project_enrichment as dispatch

    return dispatch(*args, **kwargs)


def inspect_project_enrichment(*args, **kwargs):
    from .master import inspect_project_enrichment as inspect_request

    return inspect_request(*args, **kwargs)


def submit_project_enrichment(*args, **kwargs):
    from .master import submit_project_enrichment as submit

    return submit(*args, **kwargs)


def timeout_project_enrichment(*args, **kwargs):
    from .master import timeout_project_enrichment as timeout

    return timeout(*args, **kwargs)


def retry_project_enrichment(*args, **kwargs):
    from .master import retry_project_enrichment as retry

    return retry(*args, **kwargs)


def create_delegated_authorization(*args, **kwargs):
    from .master import create_delegated_authorization as create

    return create(*args, **kwargs)


def revoke_delegated_authorization(*args, **kwargs):
    from .master import revoke_delegated_authorization as revoke

    return revoke(*args, **kwargs)


def authorize_factual_change(*args, **kwargs):
    from .master import authorize_factual_change as authorize

    return authorize(*args, **kwargs)


def load_project_preset(*args, **kwargs):
    from .master import load_project_preset as load

    return load(*args, **kwargs)


def apply_project_preset(*args, **kwargs):
    from .master import apply_project_preset as apply_preset

    return apply_preset(*args, **kwargs)


def project_preset_golden_candidates(*args, **kwargs):
    from .master import project_preset_golden_candidates as candidates

    return candidates(*args, **kwargs)


def run_project_supervisor_once(*args, **kwargs):
    from .master import run_project_supervisor_once as run_once

    return run_once(*args, **kwargs)


def stop_project_supervisor(*args, **kwargs):
    from .master import stop_project_supervisor as stop

    return stop(*args, **kwargs)


def resume_project_supervisor(*args, **kwargs):
    from .master import resume_project_supervisor as resume

    return resume(*args, **kwargs)


def inspect_project_health(*args, **kwargs):
    from .master import inspect_project_health as health

    return health(*args, **kwargs)


def inspect_project_recovery(*args, **kwargs):
    from .master import inspect_project_recovery as inspect_recovery

    return inspect_recovery(*args, **kwargs)


def recover_project_activation(*args, **kwargs):
    from .master import recover_project_activation as recover

    return recover(*args, **kwargs)


def backup_project(*args, **kwargs):
    from .master import backup_project as backup

    return backup(*args, **kwargs)


def verify_project_backup(*args, **kwargs):
    from .master import verify_project_backup as verify

    return verify(*args, **kwargs)


def restore_project(*args, **kwargs):
    from .master import restore_project as restore

    return restore(*args, **kwargs)


def validate_dependency_mitigation(*args, **kwargs):
    from .master import validate_dependency_mitigation as validate

    return validate(*args, **kwargs)


def __getattr__(name):
    if name in {"OperationOptions", "OperationPlan", "OperationRequest"}:
        from .operations import OperationOptions, OperationPlan, OperationRequest

        return {
            "OperationOptions": OperationOptions,
            "OperationPlan": OperationPlan,
            "OperationRequest": OperationRequest,
        }[name]
    if name == "OperationResult":
        from .api_types import PipelineResult

        return PipelineResult
    if name == "PipelineOptions":
        from .api_types import PipelineOptions

        return PipelineOptions
    if name in {
        "CanonicalLifecycle",
        "Lifecycle",
        "LifecycleError",
        "LifecycleFacade",
        "LifecycleStateMachine",
        "RuntimeState",
    }:
        from .lifecycle import (
            CanonicalLifecycle,
            Lifecycle,
            LifecycleError,
            LifecycleFacade,
            LifecycleStateMachine,
            RuntimeState,
        )

        return {
            "CanonicalLifecycle": CanonicalLifecycle,
            "Lifecycle": Lifecycle,
            "LifecycleError": LifecycleError,
            "LifecycleFacade": LifecycleFacade,
            "LifecycleStateMachine": LifecycleStateMachine,
            "RuntimeState": RuntimeState,
        }[name]
    raise AttributeError(name)
