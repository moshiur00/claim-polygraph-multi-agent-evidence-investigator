"""Validated registry and legacy-report adapter for authoritative operations."""

from datetime import UTC, datetime
from uuid import UUID

from claim_polygraph_ng.domain.investigation import ArtifactType, InvestigationReport
from claim_polygraph_ng.domain.operations import (
    OPERATION_INPUT_MODELS,
    OPERATION_RESULT_MODELS,
    ApplyJudgmentPolicyResult,
    ArtifactReference,
    AuthoritativeOperation,
    AuthoritativeOperationContract,
    CancellationBoundary,
    FinalizeReportResult,
    OperationFailureSemantics,
    OperationRetryClass,
)

_TELEMETRY = (
    "investigation_id",
    "operation_id",
    "operation",
    "operation_version",
    "attempt_number",
    "idempotency_key",
)


def _contract(
    operation: AuthoritativeOperation,
    responsibility: str,
    *,
    inputs: tuple[ArtifactType, ...] = (),
    outputs: tuple[ArtifactType, ...] = (),
    writes: tuple[str, ...] = ("artifacts", "trace_events"),
    cancellation: CancellationBoundary = CancellationBoundary.AFTER_DURABLE_WRITE,
    retry: OperationRetryClass = OperationRetryClass.DETERMINISTIC,
    failure: OperationFailureSemantics = OperationFailureSemantics.FAIL_INVESTIGATION,
    paid: bool = False,
) -> AuthoritativeOperationContract:
    return AuthoritativeOperationContract(
        operation=operation,
        current_responsibility=responsibility,
        input_model=OPERATION_INPUT_MODELS[operation].__name__,
        result_model=OPERATION_RESULT_MODELS[operation].__name__,
        required_input_artifact_types=inputs,
        output_artifact_types=outputs,
        database_writes=writes,
        idempotency_scope="investigation_id + operation + version + canonical input hash",
        cancellation_boundary=cancellation,
        retry_class=retry,
        failure_semantics=failure,
        telemetry_attributes=_TELEMETRY,
        may_invoke_paid_provider=paid,
    )


AUTHORITATIVE_OPERATION_CONTRACTS = (
    _contract(
        AuthoritativeOperation.CREATE_INVESTIGATION,
        "create_investigation",
        writes=("investigations", "trace_events"),
    ),
    _contract(
        AuthoritativeOperation.NORMALIZE_CLAIM,
        "normalize_claim",
        outputs=(ArtifactType.CLAIM,),
        retry=OperationRetryClass.RECEIPT_GUARDED,
        paid=True,
    ),
    _contract(
        AuthoritativeOperation.PLAN_INVESTIGATION,
        "plan_investigation",
        inputs=(ArtifactType.CLAIM,),
        outputs=(ArtifactType.PLAN,),
        retry=OperationRetryClass.RECEIPT_GUARDED,
        paid=True,
    ),
    _contract(
        AuthoritativeOperation.PREPARE_RESEARCH_REQUIREMENTS,
        "execute_research",
        inputs=(ArtifactType.CLAIM, ArtifactType.PLAN),
    ),
    _contract(
        AuthoritativeOperation.EXECUTE_RESEARCH,
        "execute_research",
        inputs=(ArtifactType.CLAIM,),
        outputs=(ArtifactType.SOURCE, ArtifactType.CHUNK, ArtifactType.EVIDENCE),
        cancellation=CancellationBoundary.BETWEEN_PROVIDER_CALLS,
        retry=OperationRetryClass.RECEIPT_GUARDED,
        failure=OperationFailureSemantics.RETAIN_PARTIAL_AND_ROUTE_REVIEW,
        paid=True,
    ),
    _contract(
        AuthoritativeOperation.CONSOLIDATE_EVIDENCE,
        "execute_research",
        outputs=(ArtifactType.EVIDENCE, ArtifactType.INDEPENDENCE),
    ),
    _contract(
        AuthoritativeOperation.ANALYZE_PROVENANCE,
        "analyze_provenance",
        inputs=(ArtifactType.PLAN, ArtifactType.EVIDENCE),
        outputs=(ArtifactType.PROVENANCE,),
    ),
    _contract(
        AuthoritativeOperation.VERIFY_CONTEXT,
        "verify_context",
        inputs=(ArtifactType.CLAIM, ArtifactType.PLAN, ArtifactType.EVIDENCE),
        outputs=(ArtifactType.CONTEXT_VERIFICATION, ArtifactType.VERIFICATION_PACKET),
    ),
    _contract(
        AuthoritativeOperation.BUILD_ARGUMENT_LEDGER,
        "build_argument_ledger",
        inputs=(
            ArtifactType.CLAIM,
            ArtifactType.EVIDENCE,
            ArtifactType.VERIFICATION_PACKET,
            ArtifactType.PROVENANCE,
        ),
        outputs=(ArtifactType.ARGUMENT_LEDGER,),
    ),
    _contract(
        AuthoritativeOperation.CONSTRUCT_DEFENDER_ARGUMENT,
        "build_argument_ledger",
        inputs=(ArtifactType.ARGUMENT_LEDGER, ArtifactType.EVIDENCE),
    ),
    _contract(
        AuthoritativeOperation.CONSTRUCT_CHALLENGER_ARGUMENT,
        "build_argument_ledger",
        inputs=(ArtifactType.ARGUMENT_LEDGER, ArtifactType.EVIDENCE),
    ),
    _contract(
        AuthoritativeOperation.RECONCILE_ARGUMENTS,
        "build_argument_ledger",
        outputs=(ArtifactType.ARGUMENT_LEDGER,),
    ),
    _contract(
        AuthoritativeOperation.DRAFT_VERDICT,
        "draft_and_constrain_verdict",
        inputs=(ArtifactType.ARGUMENT_LEDGER,),
        outputs=(ArtifactType.PROPOSED_VERDICT,),
        retry=OperationRetryClass.RECEIPT_GUARDED,
        paid=True,
    ),
    _contract(
        AuthoritativeOperation.APPLY_JUDGMENT_POLICY,
        "draft_and_constrain_verdict",
        inputs=(ArtifactType.PROPOSED_VERDICT, ArtifactType.ARGUMENT_LEDGER),
        outputs=(ArtifactType.ENFORCED_VERDICT, ArtifactType.JUDGMENT_POLICY),
    ),
    _contract(
        AuthoritativeOperation.AUDIT_CITATIONS,
        "audit_citations",
        inputs=(ArtifactType.ENFORCED_VERDICT, ArtifactType.EVIDENCE),
        outputs=(
            ArtifactType.VERDICT,
            ArtifactType.AUDIT,
            ArtifactType.FULL_REPORT_ASSURANCE,
        ),
        retry=OperationRetryClass.RECEIPT_GUARDED,
        failure=OperationFailureSemantics.BLOCK_PUBLICATION,
        paid=True,
    ),
    _contract(
        AuthoritativeOperation.ASSESS_READINESS,
        "assess_readiness",
        inputs=(
            ArtifactType.ARGUMENT_LEDGER,
            ArtifactType.VERIFICATION_PACKET,
            ArtifactType.PROVENANCE,
            ArtifactType.FULL_REPORT_ASSURANCE,
        ),
        outputs=(ArtifactType.READINESS,),
    ),
    _contract(
        AuthoritativeOperation.ROUTE_REVIEW,
        "finalize_or_fail",
        inputs=(
            ArtifactType.READINESS,
            ArtifactType.VERDICT,
            ArtifactType.FULL_REPORT_ASSURANCE,
        ),
        writes=("review_ledger", "trace_events"),
        outputs=(ArtifactType.PUBLICATION_DECISION,),
        failure=OperationFailureSemantics.INTERRUPT_FOR_REVIEW,
    ),
    _contract(
        AuthoritativeOperation.FINALIZE_REPORT,
        "finalize_or_fail",
        inputs=(
            ArtifactType.VERDICT,
            ArtifactType.FULL_REPORT_ASSURANCE,
            ArtifactType.READINESS,
        ),
        writes=("investigations", "artifacts", "trace_events"),
        cancellation=CancellationBoundary.NOT_CANCELLABLE,
        failure=OperationFailureSemantics.BLOCK_PUBLICATION,
    ),
)


def validate_operation_contract_registry() -> None:
    operations = tuple(item.operation for item in AUTHORITATIVE_OPERATION_CONTRACTS)
    expected = set(AuthoritativeOperation)
    if len(operations) != len(set(operations)) or set(operations) != expected:
        raise ValueError("every authoritative operation requires exactly one contract")
    if set(OPERATION_INPUT_MODELS) != expected or set(OPERATION_RESULT_MODELS) != expected:
        raise ValueError("every operation requires exactly one input and result model")
    for contract in AUTHORITATIVE_OPERATION_CONTRACTS:
        if contract.input_model != OPERATION_INPUT_MODELS[contract.operation].__name__:
            raise ValueError(f"{contract.operation}: input model mismatch")
        if contract.result_model != OPERATION_RESULT_MODELS[contract.operation].__name__:
            raise ValueError(f"{contract.operation}: result model mismatch")
        if contract.may_invoke_paid_provider and (
            contract.retry_class is not OperationRetryClass.RECEIPT_GUARDED
        ):
            raise ValueError(f"{contract.operation}: paid operations must be receipt guarded")


def legacy_report_artifact_references(
    report: InvestigationReport,
) -> dict[ArtifactType, tuple[ArtifactReference, ...]]:
    """Expose an existing report through the new reference contract."""
    investigation_id = report.investigation.investigation_id

    def ref(artifact_type: ArtifactType, artifact_id: UUID) -> ArtifactReference:
        return ArtifactReference(
            investigation_id=investigation_id,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
        )

    references: dict[ArtifactType, tuple[ArtifactReference, ...]] = {
        ArtifactType.CLAIM: (ref(ArtifactType.CLAIM, report.claim.claim_id),),
        ArtifactType.PLAN: (ref(ArtifactType.PLAN, report.claim.claim_id),),
        ArtifactType.SOURCE: tuple(
            ref(ArtifactType.SOURCE, item.source_id) for item in report.sources
        ),
        ArtifactType.EVIDENCE: tuple(
            ref(ArtifactType.EVIDENCE, item.evidence_id) for item in report.evidence
        ),
        ArtifactType.VERDICT: (ref(ArtifactType.VERDICT, report.verdict.verdict_id),),
        ArtifactType.AUDIT: tuple(
            ref(ArtifactType.AUDIT, item.sentence_id) for item in report.audits
        ),
    }
    optional = (
        (ArtifactType.INDEPENDENCE, report.independence_analysis, report.claim.claim_id),
        (ArtifactType.PROVENANCE, report.provenance, report.claim.claim_id),
        (ArtifactType.VERIFICATION_PACKET, report.verification_packet, report.claim.claim_id),
        (ArtifactType.ARGUMENT_LEDGER, report.argument_ledger, report.claim.claim_id),
        (ArtifactType.JUDGMENT_POLICY, report.judgment_policy, report.verdict.verdict_id),
        (ArtifactType.READINESS, report.readiness, report.claim.claim_id),
        (
            ArtifactType.CONTEXT_VERIFICATION,
            report.context_verification,
            report.claim.claim_id,
        ),
        (
            ArtifactType.FULL_REPORT_ASSURANCE,
            report.full_report_assurance,
            report.claim.claim_id,
        ),
        (
            ArtifactType.PUBLICATION_DECISION,
            report.publication_decision,
            (
                report.publication_decision.decision_id
                if report.publication_decision is not None
                else report.claim.claim_id
            ),
        ),
        (
            ArtifactType.SOCIAL_EVIDENCE_POLICY,
            report.social_evidence_policy,
            report.claim.claim_id,
        ),
    )
    references.update(
        {
            artifact_type: (ref(artifact_type, artifact_id),)
            for artifact_type, value, artifact_id in optional
            if value is not None
        }
    )
    return references


def legacy_report_final_results(
    *,
    report: InvestigationReport,
    apply_policy_operation_id: UUID,
    finalize_operation_id: UUID,
    completed_at: datetime | None = None,
) -> tuple[ApplyJudgmentPolicyResult, FinalizeReportResult]:
    """Adapt the current monolithic result without executing any operation."""
    references = legacy_report_artifact_references(report)
    timestamp = completed_at or datetime.now(UTC)
    verdict_ref = references[ArtifactType.VERDICT][0]
    policy_ref = references[ArtifactType.JUDGMENT_POLICY][0]
    assurance_ref = references[ArtifactType.FULL_REPORT_ASSURANCE][0]
    readiness_ref = references[ArtifactType.READINESS][0]
    report_ref = ArtifactReference(
        investigation_id=report.investigation.investigation_id,
        artifact_type=ArtifactType.CHECKPOINT,
        artifact_id=report.investigation.investigation_id,
    )
    return (
        ApplyJudgmentPolicyResult(
            operation_id=apply_policy_operation_id,
            investigation_id=report.investigation.investigation_id,
            enforced_verdict_ref=verdict_ref,
            judgment_policy_ref=policy_ref,
            label_changed=bool(report.judgment_policy and report.judgment_policy.changed),
            output_artifacts=(verdict_ref, policy_ref),
            completed_at=timestamp,
        ),
        FinalizeReportResult(
            operation_id=finalize_operation_id,
            investigation_id=report.investigation.investigation_id,
            report_ref=report_ref,
            publication_blocked=bool(
                report.full_report_assurance
                and report.full_report_assurance.publication_status.value == "blocked"
            ),
            output_artifacts=(report_ref, assurance_ref, readiness_ref),
            completed_at=timestamp,
        ),
    )


validate_operation_contract_registry()
