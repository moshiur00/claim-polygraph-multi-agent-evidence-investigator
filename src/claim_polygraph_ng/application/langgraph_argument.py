"""Independent defender/challenger LangGraph fan-out with deterministic reconciliation."""

import operator
from typing import Annotated, Any, Protocol, TypedDict
from uuid import NAMESPACE_URL, UUID, uuid5

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from claim_polygraph_ng.analysis import build_argument_ledger
from claim_polygraph_ng.domain import (
    ARGUMENT_PERMISSIONS,
    AdversarialArgumentCheckpoint,
    AdversarialArgumentReport,
    ArgumentAssignment,
    ArgumentLedger,
    ArgumentRole,
    ArgumentRoleResult,
    ArgumentWorkflowStage,
    AtomicClaim,
    Evidence,
    EvidenceStance,
    InvestigationProvenance,
    MaterialProposition,
    PropositionArgument,
    PropositionResolution,
    VerificationPacketV2,
)
from claim_polygraph_ng.persistence import SQLiteResearchRepository


class ArgumentWorker(Protocol):
    async def run(
        self,
        assignment: ArgumentAssignment,
        checkpoint: AdversarialArgumentCheckpoint,
    ) -> ArgumentRoleResult: ...


class DeterministicArgumentWorker:
    """Build one position from approved records without tools or new facts."""

    async def run(
        self,
        assignment: ArgumentAssignment,
        checkpoint: AdversarialArgumentCheckpoint,
    ) -> ArgumentRoleResult:
        evidence = tuple(
            item
            for item in checkpoint.approved_evidence
            if item.evidence_id in assignment.approved_evidence_ids and item.relevance_score >= 0.5
        )
        by_stance = {
            stance: tuple(item.evidence_id for item in evidence if item.stance is stance)
            for stance in EvidenceStance
        }
        if assignment.role is ArgumentRole.DEFENDER:
            arguments = tuple(
                PropositionArgument(
                    proposition_id=item.proposition_id,
                    resolution=(
                        PropositionResolution.SUPPORTED
                        if by_stance[EvidenceStance.SUPPORTS]
                        else PropositionResolution.UNRESOLVED
                    ),
                    supporting_evidence_ids=by_stance[EvidenceStance.SUPPORTS],
                    contextual_evidence_ids=by_stance[EvidenceStance.CONTEXT],
                    unresolved_reasons=(
                        ()
                        if by_stance[EvidenceStance.SUPPORTS]
                        else ("No approved supporting evidence was available.",)
                    ),
                )
                for item in checkpoint.propositions
            )
            findings = ()
        else:
            arguments = tuple(
                PropositionArgument(
                    proposition_id=item.proposition_id,
                    resolution=_challenger_resolution(by_stance),
                    contradictory_evidence_ids=by_stance[EvidenceStance.CONTRADICTS],
                    qualifying_evidence_ids=by_stance[EvidenceStance.QUALIFIES],
                    unresolved_reasons=(
                        ()
                        if (
                            by_stance[EvidenceStance.CONTRADICTS]
                            or by_stance[EvidenceStance.QUALIFIES]
                        )
                        else ("No approved counterevidence was available.",)
                    ),
                )
                for item in checkpoint.propositions
            )
            findings = build_argument_ledger(
                claim=checkpoint.claim,
                evidence=checkpoint.approved_evidence,
                verification=checkpoint.verification,
                provenance=checkpoint.provenance,
                propositions=checkpoint.propositions,
            ).challenge_findings
        consumed = _referenced_evidence(arguments, findings)
        return ArgumentRoleResult(
            assignment_id=assignment.assignment_id,
            claim_id=assignment.claim_id,
            role=assignment.role,
            arguments=arguments,
            challenge_findings=findings,
            consumed_evidence_ids=consumed,
        )


class _ArgumentState(TypedDict, total=False):
    assignments: list[dict[str, Any]]
    results: Annotated[list[dict[str, Any]], operator.add]


class LangGraphAdversarialArgumentWorkflow:
    """Run isolated positions concurrently, persist them, then reconcile."""

    def __init__(
        self,
        *,
        repository: SQLiteResearchRepository,
        worker: ArgumentWorker | None = None,
    ) -> None:
        self._repository = repository
        self._worker = worker or DeterministicArgumentWorker()
        self._repository.initialize()

    async def start_or_resume(
        self,
        *,
        investigation_id: UUID,
        claim: AtomicClaim,
        approved_evidence: tuple[Evidence, ...],
        authoritative_ledger: ArgumentLedger | None,
        verification: VerificationPacketV2 | None = None,
        provenance: InvestigationProvenance | None = None,
    ) -> AdversarialArgumentReport:
        checkpoint = self._repository.get_argument_workflow(investigation_id)
        if checkpoint is None:
            checkpoint = _new_checkpoint(
                investigation_id=investigation_id,
                claim=claim,
                approved_evidence=approved_evidence,
                authoritative_ledger=authoritative_ledger,
                verification=verification,
                provenance=provenance,
            )
            self._repository.save_argument_workflow(checkpoint)
        elif checkpoint.claim.claim_id != claim.claim_id:
            raise ValueError("argument checkpoint claim does not match investigation")

        if checkpoint.stage is ArgumentWorkflowStage.PLANNED:
            output = await _build_graph(self._execute_one, checkpoint).ainvoke(
                {
                    "assignments": [
                        item.model_dump(mode="json") for item in checkpoint.assignments
                    ],
                    "results": [],
                }
            )
            by_assignment = {
                item.assignment_id: item
                for item in (
                    ArgumentRoleResult.model_validate(raw) for raw in output.get("results", [])
                )
            }
            checkpoint = checkpoint.model_copy(
                update={
                    "stage": ArgumentWorkflowStage.ARGUED,
                    "results": tuple(
                        by_assignment[item.assignment_id] for item in checkpoint.assignments
                    ),
                }
            )
            self._repository.save_argument_workflow(checkpoint)

        if checkpoint.stage is ArgumentWorkflowStage.ARGUED:
            ledger = build_argument_ledger(
                claim=checkpoint.claim,
                evidence=checkpoint.approved_evidence,
                verification=checkpoint.verification,
                provenance=checkpoint.provenance,
                propositions=checkpoint.propositions,
            )
            checkpoint = checkpoint.model_copy(
                update={
                    "stage": ArgumentWorkflowStage.RECONCILED,
                    "reconciled_ledger": ledger,
                }
            )
            self._repository.save_argument_workflow(checkpoint)
        return _report(checkpoint)

    async def _execute_one(
        self,
        assignment: ArgumentAssignment,
        checkpoint: AdversarialArgumentCheckpoint,
    ) -> ArgumentRoleResult:
        stored = self._repository.get_argument_result(assignment.assignment_id)
        if stored is not None:
            return stored
        try:
            result = await self._worker.run(assignment, checkpoint)
            if (
                result.assignment_id != assignment.assignment_id
                or result.claim_id != assignment.claim_id
                or result.role is not assignment.role
            ):
                raise ValueError("argument result does not match assignment identity")
            if not set(result.consumed_evidence_ids) <= set(assignment.approved_evidence_ids):
                raise ValueError("argument role consumed out-of-packet evidence")
        except Exception as exc:
            result = ArgumentRoleResult(
                assignment_id=assignment.assignment_id,
                claim_id=assignment.claim_id,
                role=assignment.role,
                arguments=tuple(
                    PropositionArgument(
                        proposition_id=item,
                        resolution=PropositionResolution.UNRESOLVED,
                        unresolved_reasons=("Argument role failed before completion.",),
                    )
                    for item in assignment.proposition_ids
                ),
                failure_reason=f"{type(exc).__name__}: {exc}",
            )
        self._repository.save_argument_result(result)
        return result


def _build_graph(execute_one, checkpoint):
    builder = StateGraph(_ArgumentState)

    async def build_position(state: _ArgumentState) -> dict[str, list[dict[str, Any]]]:
        assignment = ArgumentAssignment.model_validate(state["assignments"][0])
        result = await execute_one(assignment, checkpoint)
        return {"results": [result.model_dump(mode="json")]}

    builder.add_node("dispatch_arguments", lambda _state: {})
    builder.add_node("build_position", build_position)
    builder.add_node("join_arguments", lambda _state: {})
    builder.add_edge(START, "dispatch_arguments")
    builder.add_conditional_edges(
        "dispatch_arguments",
        lambda state: [
            Send("build_position", {"assignments": [item], "results": []})
            for item in state["assignments"]
        ],
    )
    builder.add_edge("build_position", "join_arguments")
    builder.add_edge("join_arguments", END)
    return builder.compile()


def _new_checkpoint(
    *,
    investigation_id,
    claim,
    approved_evidence,
    authoritative_ledger,
    verification,
    provenance,
):
    if not approved_evidence:
        raise ValueError("argument workflow requires approved evidence")
    if any(item.claim_id != claim.claim_id for item in approved_evidence):
        raise ValueError("approved evidence must reference the argument claim")
    propositions = (
        authoritative_ledger.propositions
        if authoritative_ledger is not None
        else (
            MaterialProposition(
                proposition_id=uuid5(NAMESPACE_URL, f"{claim.claim_id}/{claim.text}"),
                claim_id=claim.claim_id,
                text=claim.text,
            ),
        )
    )
    approved_ids = tuple(item.evidence_id for item in approved_evidence)
    assignments = tuple(
        ArgumentAssignment(
            investigation_id=investigation_id,
            claim_id=claim.claim_id,
            role=role,
            proposition_ids=tuple(item.proposition_id for item in propositions),
            approved_evidence_ids=approved_ids,
            permissions=ARGUMENT_PERMISSIONS,
        )
        for role in (ArgumentRole.DEFENDER, ArgumentRole.CHALLENGER)
    )
    return AdversarialArgumentCheckpoint(
        investigation_id=investigation_id,
        claim=claim,
        approved_evidence=approved_evidence,
        propositions=propositions,
        assignments=assignments,
        stage=ArgumentWorkflowStage.PLANNED,
        authoritative_ledger=authoritative_ledger,
        verification=verification,
        provenance=provenance,
    )


def _report(checkpoint):
    if checkpoint.reconciled_ledger is None:
        raise ValueError("argument workflow did not reach reconciliation")
    complete = (
        len(checkpoint.results) == 2
        and {item.role for item in checkpoint.results}
        == {ArgumentRole.DEFENDER, ArgumentRole.CHALLENGER}
        and all(item.failure_reason is None for item in checkpoint.results)
    )
    equivalent = (
        checkpoint.authoritative_ledger is not None
        and checkpoint.reconciled_ledger == checkpoint.authoritative_ledger
    )
    reason = None
    if not complete:
        reason = "A defender or challenger position failed; human review is required."
    elif not equivalent:
        reason = (
            "Deterministic adversarial reconciliation differs from the "
            "authoritative argument ledger."
        )
    return AdversarialArgumentReport(
        investigation_id=checkpoint.investigation_id,
        assignments=checkpoint.assignments,
        results=checkpoint.results,
        reconciled_ledger=checkpoint.reconciled_ledger,
        authoritative_ledger_equivalent=equivalent,
        complete_role_coverage=complete,
        human_review_required=reason is not None,
        human_review_reason=reason,
    )


def _challenger_resolution(by_stance):
    if by_stance[EvidenceStance.CONTRADICTS]:
        return PropositionResolution.CONTRADICTED
    if by_stance[EvidenceStance.QUALIFIES]:
        return PropositionResolution.QUALIFIED
    return PropositionResolution.UNRESOLVED


def _referenced_evidence(arguments, findings):
    return tuple(
        dict.fromkeys(
            evidence_id
            for argument in arguments
            for evidence_id in (
                *argument.supporting_evidence_ids,
                *argument.contradictory_evidence_ids,
                *argument.qualifying_evidence_ids,
                *argument.contextual_evidence_ids,
            )
        )
        | dict.fromkeys(evidence_id for finding in findings for evidence_id in finding.evidence_ids)
    )
