"""Authoritative, orchestration-neutral investigation operation contracts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import Field, JsonValue, model_validator

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.investigation import ArtifactType, InvestigationStatus


class AuthoritativeOperation(StrEnum):
    CREATE_INVESTIGATION = "create_investigation"
    NORMALIZE_CLAIM = "normalize_claim"
    PLAN_INVESTIGATION = "plan_investigation"
    PREPARE_RESEARCH_REQUIREMENTS = "prepare_research_requirements"
    EXECUTE_RESEARCH = "execute_research"
    CONSOLIDATE_EVIDENCE = "consolidate_evidence"
    ANALYZE_PROVENANCE = "analyze_provenance"
    VERIFY_CONTEXT = "verify_context"
    BUILD_ARGUMENT_LEDGER = "build_argument_ledger"
    CONSTRUCT_DEFENDER_ARGUMENT = "construct_defender_argument"
    CONSTRUCT_CHALLENGER_ARGUMENT = "construct_challenger_argument"
    RECONCILE_ARGUMENTS = "reconcile_arguments"
    DRAFT_VERDICT = "draft_verdict"
    APPLY_JUDGMENT_POLICY = "apply_judgment_policy"
    AUDIT_CITATIONS = "audit_citations"
    ASSESS_READINESS = "assess_readiness"
    ROUTE_REVIEW = "route_review"
    FINALIZE_REPORT = "finalize_report"


class OperationRetryClass(StrEnum):
    NEVER = "never"
    DETERMINISTIC = "deterministic"
    PROVIDER_TRANSIENT_ONCE = "provider_transient_once"
    RECEIPT_GUARDED = "receipt_guarded"


class OperationFailureSemantics(StrEnum):
    FAIL_INVESTIGATION = "fail_investigation"
    RETAIN_PARTIAL_AND_ROUTE_REVIEW = "retain_partial_and_route_review"
    BLOCK_PUBLICATION = "block_publication"
    INTERRUPT_FOR_REVIEW = "interrupt_for_review"


class CancellationBoundary(StrEnum):
    BEFORE_OPERATION = "before_operation"
    BETWEEN_PROVIDER_CALLS = "between_provider_calls"
    AFTER_DURABLE_WRITE = "after_durable_write"
    NOT_CANCELLABLE = "not_cancellable"


class OperationExecutionStatus(StrEnum):
    COMPLETED = "completed"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_PERMANENT = "failed_permanent"
    CANCELLED = "cancelled"


class OperationBudget(DomainModel):
    maximum_search_calls: int = Field(default=0, ge=0)
    maximum_page_fetches: int = Field(default=0, ge=0)
    maximum_model_calls: int = Field(default=0, ge=0)
    maximum_tokens: int = Field(default=0, ge=0)
    maximum_cost_usd: float = Field(default=0, ge=0)
    deadline: datetime | None = None


class ArtifactReference(DomainModel):
    investigation_id: UUID
    artifact_type: ArtifactType
    artifact_id: UUID
    schema_version: int = Field(default=1, ge=1)
    content_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class OperationRequest(DomainModel):
    operation_id: UUID
    investigation_id: UUID
    operation: AuthoritativeOperation
    operation_version: int = Field(default=1, ge=1)
    attempt_number: int = Field(default=1, ge=1)
    budget: OperationBudget = OperationBudget()
    input_artifacts: tuple[ArtifactReference, ...] = ()
    idempotency_key: str = Field(min_length=16, max_length=200)

    @model_validator(mode="after")
    def validate_artifact_scope(self) -> OperationRequest:
        if any(
            artifact.investigation_id != self.investigation_id
            for artifact in self.input_artifacts
        ):
            raise ValueError("input artifacts must belong to the operation investigation")
        if len(self.input_artifacts) != len(
            {(item.artifact_type, item.artifact_id) for item in self.input_artifacts}
        ):
            raise ValueError("input artifact references must be unique")
        return self


class CreateInvestigationInput(OperationRequest):
    operation: AuthoritativeOperation = AuthoritativeOperation.CREATE_INVESTIGATION
    original_claim: str = Field(min_length=3, max_length=10_000)
    parent_investigation_id: UUID | None = None
    component_claim_id: UUID | None = None


class NormalizeClaimInput(OperationRequest):
    operation: AuthoritativeOperation = AuthoritativeOperation.NORMALIZE_CLAIM
    original_claim: str = Field(min_length=3, max_length=10_000)


class PlanInvestigationInput(OperationRequest):
    operation: AuthoritativeOperation = AuthoritativeOperation.PLAN_INVESTIGATION
    claim_ref: ArtifactReference


class PrepareResearchRequirementsInput(OperationRequest):
    operation: AuthoritativeOperation = AuthoritativeOperation.PREPARE_RESEARCH_REQUIREMENTS
    claim_ref: ArtifactReference
    plan_ref: ArtifactReference


class ExecuteResearchInput(OperationRequest):
    operation: AuthoritativeOperation = AuthoritativeOperation.EXECUTE_RESEARCH
    claim_ref: ArtifactReference
    requirement_refs: tuple[ArtifactReference, ...] = Field(min_length=1)


class ConsolidateEvidenceInput(OperationRequest):
    operation: AuthoritativeOperation = AuthoritativeOperation.CONSOLIDATE_EVIDENCE
    research_result_refs: tuple[ArtifactReference, ...] = Field(min_length=1)


class AnalyzeProvenanceInput(OperationRequest):
    operation: AuthoritativeOperation = AuthoritativeOperation.ANALYZE_PROVENANCE
    plan_ref: ArtifactReference
    approved_evidence_refs: tuple[ArtifactReference, ...] = Field(min_length=1)


class VerifyContextInput(OperationRequest):
    operation: AuthoritativeOperation = AuthoritativeOperation.VERIFY_CONTEXT
    claim_ref: ArtifactReference
    plan_ref: ArtifactReference
    approved_evidence_refs: tuple[ArtifactReference, ...] = Field(min_length=1)


class BuildArgumentLedgerInput(OperationRequest):
    operation: AuthoritativeOperation = AuthoritativeOperation.BUILD_ARGUMENT_LEDGER
    claim_ref: ArtifactReference
    approved_evidence_refs: tuple[ArtifactReference, ...] = Field(min_length=1)
    verification_ref: ArtifactReference
    provenance_ref: ArtifactReference


class ConstructDefenderArgumentInput(OperationRequest):
    operation: AuthoritativeOperation = AuthoritativeOperation.CONSTRUCT_DEFENDER_ARGUMENT
    argument_ledger_ref: ArtifactReference
    approved_evidence_refs: tuple[ArtifactReference, ...] = Field(min_length=1)


class ConstructChallengerArgumentInput(OperationRequest):
    operation: AuthoritativeOperation = AuthoritativeOperation.CONSTRUCT_CHALLENGER_ARGUMENT
    argument_ledger_ref: ArtifactReference
    approved_evidence_refs: tuple[ArtifactReference, ...] = Field(min_length=1)


class ReconcileArgumentsInput(OperationRequest):
    operation: AuthoritativeOperation = AuthoritativeOperation.RECONCILE_ARGUMENTS
    defender_ref: ArtifactReference
    challenger_ref: ArtifactReference


class DraftVerdictInput(OperationRequest):
    operation: AuthoritativeOperation = AuthoritativeOperation.DRAFT_VERDICT
    reconciled_ledger_ref: ArtifactReference


class ApplyJudgmentPolicyInput(OperationRequest):
    operation: AuthoritativeOperation = AuthoritativeOperation.APPLY_JUDGMENT_POLICY
    proposed_verdict_ref: ArtifactReference
    reconciled_ledger_ref: ArtifactReference


class AuditCitationsInput(OperationRequest):
    operation: AuthoritativeOperation = AuthoritativeOperation.AUDIT_CITATIONS
    enforced_verdict_ref: ArtifactReference
    approved_evidence_refs: tuple[ArtifactReference, ...] = Field(min_length=1)
    maximum_revision_attempts: int = Field(default=2, ge=0, le=2)


class AssessReadinessInput(OperationRequest):
    operation: AuthoritativeOperation = AuthoritativeOperation.ASSESS_READINESS
    ledger_ref: ArtifactReference
    verification_ref: ArtifactReference
    provenance_ref: ArtifactReference
    citation_assurance_ref: ArtifactReference
    unresolved_question_count: int = Field(default=0, ge=0)


class RouteReviewInput(OperationRequest):
    operation: AuthoritativeOperation = AuthoritativeOperation.ROUTE_REVIEW
    readiness_ref: ArtifactReference
    verdict_ref: ArtifactReference
    citation_assurance_ref: ArtifactReference


class FinalizeReportInput(OperationRequest):
    operation: AuthoritativeOperation = AuthoritativeOperation.FINALIZE_REPORT
    verdict_ref: ArtifactReference
    citation_assurance_ref: ArtifactReference
    readiness_ref: ArtifactReference
    review_decision_ref: ArtifactReference | None = None


class OperationResult(DomainModel):
    operation_id: UUID
    investigation_id: UUID
    operation: AuthoritativeOperation
    operation_version: int = Field(default=1, ge=1)
    status: OperationExecutionStatus = OperationExecutionStatus.COMPLETED
    output_artifacts: tuple[ArtifactReference, ...] = ()
    emitted_event_ids: tuple[UUID, ...] = ()
    provider_receipt_ids: tuple[UUID, ...] = ()
    completed_at: datetime


class CreateInvestigationResult(OperationResult):
    operation: AuthoritativeOperation = AuthoritativeOperation.CREATE_INVESTIGATION
    investigation_status: InvestigationStatus


class NormalizeClaimResult(OperationResult):
    operation: AuthoritativeOperation = AuthoritativeOperation.NORMALIZE_CLAIM
    claim_ref: ArtifactReference
    ambiguity_count: int = Field(default=0, ge=0)


class PlanInvestigationResult(OperationResult):
    operation: AuthoritativeOperation = AuthoritativeOperation.PLAN_INVESTIGATION
    plan_ref: ArtifactReference


class PrepareResearchRequirementsResult(OperationResult):
    operation: AuthoritativeOperation = AuthoritativeOperation.PREPARE_RESEARCH_REQUIREMENTS
    requirement_refs: tuple[ArtifactReference, ...] = Field(min_length=1)


class ExecuteResearchResult(OperationResult):
    operation: AuthoritativeOperation = AuthoritativeOperation.EXECUTE_RESEARCH
    assignment_refs: tuple[ArtifactReference, ...] = ()
    result_refs: tuple[ArtifactReference, ...] = Field(min_length=1)


class ConsolidateEvidenceResult(OperationResult):
    operation: AuthoritativeOperation = AuthoritativeOperation.CONSOLIDATE_EVIDENCE
    source_refs: tuple[ArtifactReference, ...] = ()
    approved_evidence_refs: tuple[ArtifactReference, ...] = Field(min_length=1)
    independence_ref: ArtifactReference


class AnalyzeProvenanceResult(OperationResult):
    operation: AuthoritativeOperation = AuthoritativeOperation.ANALYZE_PROVENANCE
    provenance_ref: ArtifactReference


class VerifyContextResult(OperationResult):
    operation: AuthoritativeOperation = AuthoritativeOperation.VERIFY_CONTEXT
    context_verification_ref: ArtifactReference
    verification_packet_ref: ArtifactReference


class BuildArgumentLedgerResult(OperationResult):
    operation: AuthoritativeOperation = AuthoritativeOperation.BUILD_ARGUMENT_LEDGER
    argument_ledger_ref: ArtifactReference


class ConstructDefenderArgumentResult(OperationResult):
    operation: AuthoritativeOperation = AuthoritativeOperation.CONSTRUCT_DEFENDER_ARGUMENT
    defender_ref: ArtifactReference


class ConstructChallengerArgumentResult(OperationResult):
    operation: AuthoritativeOperation = AuthoritativeOperation.CONSTRUCT_CHALLENGER_ARGUMENT
    challenger_ref: ArtifactReference


class ReconcileArgumentsResult(OperationResult):
    operation: AuthoritativeOperation = AuthoritativeOperation.RECONCILE_ARGUMENTS
    reconciled_ledger_ref: ArtifactReference


class DraftVerdictResult(OperationResult):
    operation: AuthoritativeOperation = AuthoritativeOperation.DRAFT_VERDICT
    proposed_verdict_ref: ArtifactReference


class ApplyJudgmentPolicyResult(OperationResult):
    operation: AuthoritativeOperation = AuthoritativeOperation.APPLY_JUDGMENT_POLICY
    enforced_verdict_ref: ArtifactReference
    judgment_policy_ref: ArtifactReference
    label_changed: bool


class AuditCitationsResult(OperationResult):
    operation: AuthoritativeOperation = AuthoritativeOperation.AUDIT_CITATIONS
    citation_assurance_ref: ArtifactReference
    publication_blocked: bool


class AssessReadinessResult(OperationResult):
    operation: AuthoritativeOperation = AuthoritativeOperation.ASSESS_READINESS
    readiness_ref: ArtifactReference


class RouteReviewResult(OperationResult):
    operation: AuthoritativeOperation = AuthoritativeOperation.ROUTE_REVIEW
    review_required: bool
    route_reason_codes: tuple[str, ...] = ()
    review_request_ref: ArtifactReference | None = None


class FinalizeReportResult(OperationResult):
    operation: AuthoritativeOperation = AuthoritativeOperation.FINALIZE_REPORT
    report_ref: ArtifactReference
    publication_blocked: bool


class AuthoritativeOperationContract(DomainModel):
    operation: AuthoritativeOperation
    current_responsibility: str
    input_model: str
    result_model: str
    required_input_artifact_types: tuple[ArtifactType, ...] = ()
    output_artifact_types: tuple[ArtifactType, ...] = ()
    database_writes: tuple[str, ...]
    idempotency_scope: str
    cancellation_boundary: CancellationBoundary
    retry_class: OperationRetryClass
    failure_semantics: OperationFailureSemantics
    telemetry_attributes: tuple[str, ...] = Field(min_length=1)
    may_invoke_paid_provider: bool = False


OPERATION_INPUT_MODELS: dict[AuthoritativeOperation, type[OperationRequest]] = {
    item.model_fields["operation"].default: item
    for item in (
        CreateInvestigationInput,
        NormalizeClaimInput,
        PlanInvestigationInput,
        PrepareResearchRequirementsInput,
        ExecuteResearchInput,
        ConsolidateEvidenceInput,
        AnalyzeProvenanceInput,
        VerifyContextInput,
        BuildArgumentLedgerInput,
        ConstructDefenderArgumentInput,
        ConstructChallengerArgumentInput,
        ReconcileArgumentsInput,
        DraftVerdictInput,
        ApplyJudgmentPolicyInput,
        AuditCitationsInput,
        AssessReadinessInput,
        RouteReviewInput,
        FinalizeReportInput,
    )
}

OPERATION_RESULT_MODELS: dict[AuthoritativeOperation, type[OperationResult]] = {
    item.model_fields["operation"].default: item
    for item in (
        CreateInvestigationResult,
        NormalizeClaimResult,
        PlanInvestigationResult,
        PrepareResearchRequirementsResult,
        ExecuteResearchResult,
        ConsolidateEvidenceResult,
        AnalyzeProvenanceResult,
        VerifyContextResult,
        BuildArgumentLedgerResult,
        ConstructDefenderArgumentResult,
        ConstructChallengerArgumentResult,
        ReconcileArgumentsResult,
        DraftVerdictResult,
        ApplyJudgmentPolicyResult,
        AuditCitationsResult,
        AssessReadinessResult,
        RouteReviewResult,
        FinalizeReportResult,
    )
}


def canonical_operation_idempotency_key(
    *,
    operation: AuthoritativeOperation,
    investigation_id: UUID,
    operation_version: int,
    payload: dict[str, JsonValue],
) -> str:
    """Return the stable key shared by direct and LangGraph compositions."""
    canonical = json.dumps(
        {
            "operation": operation.value,
            "investigation_id": str(investigation_id),
            "operation_version": operation_version,
            "payload": payload,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"op:{operation.value}:{hashlib.sha256(canonical.encode()).hexdigest()}"


def validate_operation_pair(
    request: OperationRequest,
    result: OperationResult,
) -> None:
    if request.operation != result.operation:
        raise ValueError("operation request/result types do not match")
    if request.operation_id != result.operation_id:
        raise ValueError("operation request/result IDs do not match")
    if request.investigation_id != result.investigation_id:
        raise ValueError("operation request/result investigation IDs do not match")
    if request.operation_version != result.operation_version:
        raise ValueError("operation request/result versions do not match")


def schema_fingerprint(model: type[DomainModel]) -> str:
    schema: dict[str, Any] = model.model_json_schema()
    payload = json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()
