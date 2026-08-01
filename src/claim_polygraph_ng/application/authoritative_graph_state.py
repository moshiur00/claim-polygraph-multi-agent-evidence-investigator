"""Migration, monotonic transition and reconstruction policy for graph state."""

from collections.abc import Callable, Mapping
from typing import Any

from claim_polygraph_ng.domain.authoritative_graph import (
    AuthoritativeGraphPhase,
    AuthoritativeInvestigationGraphState,
)
from claim_polygraph_ng.domain.graph import DurableMultiAgentGraphState
from claim_polygraph_ng.domain.investigation import ArtifactType
from claim_polygraph_ng.domain.operations import ArtifactReference, AuthoritativeOperation

ArtifactExists = Callable[[ArtifactReference], bool]

_TERMINAL = {
    AuthoritativeGraphPhase.COMPLETE,
    AuthoritativeGraphPhase.FAILED,
    AuthoritativeGraphPhase.CANCELLED,
}
_ALLOWED_PHASE_TRANSITIONS = {
    AuthoritativeGraphPhase.CREATED: {AuthoritativeGraphPhase.CLAIM_ANALYSIS},
    AuthoritativeGraphPhase.CLAIM_ANALYSIS: {AuthoritativeGraphPhase.PLANNING},
    AuthoritativeGraphPhase.PLANNING: {AuthoritativeGraphPhase.RESEARCH},
    AuthoritativeGraphPhase.RESEARCH: {AuthoritativeGraphPhase.VERIFICATION},
    AuthoritativeGraphPhase.VERIFICATION: {AuthoritativeGraphPhase.ARGUMENTS},
    AuthoritativeGraphPhase.ARGUMENTS: {AuthoritativeGraphPhase.JUDGMENT},
    AuthoritativeGraphPhase.JUDGMENT: {AuthoritativeGraphPhase.CITATION_ASSURANCE},
    AuthoritativeGraphPhase.CITATION_ASSURANCE: {AuthoritativeGraphPhase.READINESS},
    AuthoritativeGraphPhase.READINESS: {
        AuthoritativeGraphPhase.REVIEW,
        AuthoritativeGraphPhase.FINALIZATION,
    },
    AuthoritativeGraphPhase.REVIEW: {
        AuthoritativeGraphPhase.RESEARCH,
        AuthoritativeGraphPhase.FINALIZATION,
        AuthoritativeGraphPhase.CANCELLED,
    },
    AuthoritativeGraphPhase.FINALIZATION: {AuthoritativeGraphPhase.COMPLETE},
}


def validate_monotonic_graph_transition(
    previous: AuthoritativeInvestigationGraphState,
    current: AuthoritativeInvestigationGraphState,
) -> None:
    """Reject checkpoint updates that erase durable progress or consumption."""
    if (
        previous.thread_id != current.thread_id
        or previous.investigation_id != current.investigation_id
        or previous.graph_version != current.graph_version
    ):
        raise ValueError("graph identity and version are immutable")
    if (
        previous.parent_claim_id is not None
        and previous.parent_claim_id != current.parent_claim_id
    ):
        raise ValueError("parent claim identity is immutable once assigned")
    if current.checkpoint_sequence != previous.checkpoint_sequence + 1:
        raise ValueError("checkpoint sequence must increase by exactly one")
    if previous.phase in _TERMINAL:
        raise ValueError("terminal graph state cannot transition")
    allowed = _ALLOWED_PHASE_TRANSITIONS.get(previous.phase, set())
    if current.phase != previous.phase and current.phase not in allowed:
        raise ValueError(f"invalid graph phase transition: {previous.phase} -> {current.phase}")
    _require_subset(
        previous.completed_operations,
        current.completed_operations,
        "completed operations",
    )
    if any(
        current.operation_versions.get(operation) != version
        for operation, version in previous.operation_versions.items()
    ):
        raise ValueError("completed operation versions are immutable")
    _require_subset(_artifact_keys(previous), _artifact_keys(current), "artifact references")
    _require_subset(
        previous.approved_evidence_ids,
        current.approved_evidence_ids,
        "approved evidence",
    )
    _require_subset(
        previous.verification_construction_ids,
        current.verification_construction_ids,
        "verification constructions",
    )
    if any(
        current.verification_construction_states.get(construction_id) is not state
        for construction_id, state in previous.verification_construction_states.items()
    ):
        raise ValueError("verification construction states are immutable")
    _require_subset(
        previous.review_request_ids,
        current.review_request_ids,
        "review requests",
    )
    _require_subset(
        previous.review_decision_ids,
        current.review_decision_ids,
        "review decisions",
    )
    _require_subset(
        tuple(item.receipt_id for item in previous.paid_receipts),
        tuple(item.receipt_id for item in current.paid_receipts),
        "paid receipts",
    )
    _require_subset(
        tuple(item.failure_id for item in previous.failures),
        tuple(item.failure_id for item in current.failures),
        "failure records",
    )
    for field in (
        "completed_rounds",
        "role_activations",
        "search_calls",
        "fetched_pages",
        "model_calls",
        "total_tokens",
        "duration_seconds",
        "estimated_cost_usd",
    ):
        if getattr(current.consumption, field) < getattr(previous.consumption, field):
            raise ValueError(f"consumption cannot decrease: {field}")
    if previous.final_report_ref is not None and (
        current.final_report_ref != previous.final_report_ref
    ):
        raise ValueError("final report reference is immutable once assigned")


def migrate_authoritative_graph_state(
    payload: Mapping[str, Any],
) -> AuthoritativeInvestigationGraphState:
    """Load v1 or migrate the former durable multi-agent research state."""
    version = int(payload.get("schema_version", 0))
    if version == 1 and "graph_version" in payload:
        return AuthoritativeInvestigationGraphState.model_validate(payload)
    if version not in {0, 1}:
        raise ValueError(f"unsupported authoritative graph state version: {version}")
    legacy = DurableMultiAgentGraphState.model_validate(payload)
    artifacts = tuple(
        ArtifactReference(
            investigation_id=legacy.investigation_id,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
        )
        for artifact_type, values in (
            (ArtifactType.SOURCE, legacy.stored_source_ids),
            (ArtifactType.EVIDENCE, legacy.stored_evidence_ids),
        )
        for artifact_id in values
    )
    completed = (
        (AuthoritativeOperation.EXECUTE_RESEARCH,)
        if legacy.results
        else ()
    )
    if legacy.approved_evidence_ids:
        completed += (AuthoritativeOperation.CONSOLIDATE_EVIDENCE,)
    return AuthoritativeInvestigationGraphState(
        thread_id=str(legacy.investigation_id),
        investigation_id=legacy.investigation_id,
        parent_claim_id=legacy.parent_claim_id,
        phase=AuthoritativeGraphPhase.RESEARCH,
        completed_operations=completed,
        operation_versions={operation: 1 for operation in completed},
        artifacts=artifacts,
        components=legacy.components,
        requirements=legacy.requirements,
        assignments=legacy.assignments,
        research_results=legacy.results,
        evidence_families=legacy.evidence_families,
        approved_evidence_ids=legacy.approved_evidence_ids,
        defender_result_id=(
            legacy.argument_role_result_ids[0]
            if len(legacy.argument_role_result_ids) == 2
            else None
        ),
        challenger_result_id=(
            legacy.argument_role_result_ids[1]
            if len(legacy.argument_role_result_ids) == 2
            else None
        ),
        budget=legacy.budget,
        consumption=legacy.consumption,
        unresolved_questions=legacy.unresolved_questions,
    )


def reconstruct_authoritative_graph_state(
    payload: Mapping[str, Any],
    *,
    artifact_exists: ArtifactExists,
) -> AuthoritativeInvestigationGraphState:
    """Migrate, validate and prove that every artifact reference is durable."""
    state = migrate_authoritative_graph_state(payload)
    missing = tuple(item for item in state.artifacts if not artifact_exists(item))
    if missing:
        labels = ", ".join(
            f"{item.artifact_type.value}:{item.artifact_id}" for item in missing
        )
        raise ValueError(f"checkpoint references missing authoritative artifacts: {labels}")
    return state


def _artifact_keys(
    state: AuthoritativeInvestigationGraphState,
) -> tuple[tuple[ArtifactType, object], ...]:
    return tuple((item.artifact_type, item.artifact_id) for item in state.artifacts)


def _require_subset(previous: tuple, current: tuple, label: str) -> None:
    if not set(previous) <= set(current):
        raise ValueError(f"{label} cannot disappear from a later checkpoint")
