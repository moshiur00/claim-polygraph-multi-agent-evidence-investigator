"""Initial authoritative LangGraph skeleton over extracted service operations."""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar
from itertools import pairwise
from pathlib import Path
from typing import Any, TypedDict
from uuid import NAMESPACE_URL, uuid5

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from claim_polygraph_ng.analysis import assure_full_report, route_human_review
from claim_polygraph_ng.application.authoritative_research import (
    AuthoritativeMultiAgentResearchAdapter,
    evidence_family_id,
)
from claim_polygraph_ng.application.investigation_service import InvestigationService
from claim_polygraph_ng.application.langgraph_argument import (
    LangGraphAdversarialArgumentWorkflow,
)
from claim_polygraph_ng.application.langgraph_durable import (
    DuplicateReviewDecisionError,
    GraphResumeError,
)
from claim_polygraph_ng.application.langgraph_verification import (
    AuthoritativeVerificationFanOutWorkflow,
)
from claim_polygraph_ng.domain import (
    AdversarialArgumentReport,
    ArgumentLedger,
    AtomicClaim,
    ContextVerification,
    Evidence,
    FullReportCitationAssurance,
    IndependenceAnalysis,
    Investigation,
    InvestigationPlan,
    InvestigationProvenance,
    InvestigationReport,
    JudgmentPolicyTrace,
    JudgmentReadiness,
    ReviewDecision,
    ReviewDecisionKind,
    ReviewInterruptPayload,
    ReviewRiskLevel,
    ReviewRoutingContext,
    SentenceAudit,
    SocialEvidencePolicyResult,
    Source,
    Verdict,
    VerificationPacketV2,
)
from claim_polygraph_ng.domain.authoritative_graph import (
    AuthoritativeGraphPhase,
    AuthoritativeInvestigationGraphState,
    PaidOperationReceiptReference,
    PaidOperationReceiptStatus,
)
from claim_polygraph_ng.domain.graph import (
    DurableAssignmentReference,
    DurableComponentReference,
    DurableEvidenceFamilyReference,
    DurableRequirementReference,
    DurableResultReference,
    DurableUnresolvedQuestion,
)
from claim_polygraph_ng.domain.investigation import ArtifactType
from claim_polygraph_ng.domain.operations import ArtifactReference, AuthoritativeOperation
from claim_polygraph_ng.domain.publication import (
    AuthoritativePublicationDecision,
    AuthoritativePublicationStatus,
)
from claim_polygraph_ng.domain.research import ResearchRequirementKind
from claim_polygraph_ng.domain.review import (
    ApprovalDecision,
    ApprovalRecord,
    AuthoritativeChangeKind,
    ReviewerDecisionRecord,
    ReviewRequest,
    VerdictRevision,
)
from claim_polygraph_ng.persistence.authoritative_graph import (
    SQLiteAuthoritativeGraphCheckpointRepository,
)
from claim_polygraph_ng.persistence.base import InvestigationRepository
from claim_polygraph_ng.persistence.review import SQLiteReviewLedger


class _GraphState(TypedDict, total=False):
    thread_id: str
    claim_text: str
    authoritative_state: dict[str, Any]
    provisional_verdict: dict[str, Any]
    adversarial_report: dict[str, Any]
    review_required: bool
    decision_kind: str


class AuthoritativeGraphRunResult:
    def __init__(
        self,
        state: AuthoritativeInvestigationGraphState,
        report=None,
        interrupt: ReviewInterruptPayload | None = None,
    ) -> None:
        self.state = state
        self.report = report
        self.interrupt = interrupt


class AuthoritativeFixtureLangGraphWorkflow:
    """Checkpoint every extracted operation while preserving service authority."""

    def __init__(
        self,
        *,
        service: InvestigationService,
        investigations: InvestigationRepository,
        langgraph_checkpoint_path: str | Path,
        state_checkpoint_path: str | Path,
        research_adapter: AuthoritativeMultiAgentResearchAdapter | None = None,
        research_budget=None,
        verification_workflow: AuthoritativeVerificationFanOutWorkflow | None = None,
        argument_workflow: LangGraphAdversarialArgumentWorkflow | None = None,
        review_ledger: SQLiteReviewLedger | None = None,
        require_human_review: bool = False,
    ) -> None:
        self._service = service
        self._investigations = investigations
        self._state_repository = SQLiteAuthoritativeGraphCheckpointRepository(state_checkpoint_path)
        self._langgraph_checkpoint_path = str(langgraph_checkpoint_path)
        self._research_adapter = research_adapter
        self._research_budget = research_budget
        self._verification_workflow = verification_workflow
        self._argument_workflow = argument_workflow
        self._review_ledger = review_ledger or SQLiteReviewLedger(
            Path(state_checkpoint_path).with_suffix(".reviews.db")
        )
        self._review_ledger.initialize()
        self._require_human_review = require_human_review
        self._safe_boundary: ContextVar[Callable[[], None] | None] = ContextVar(
            "authoritative_safe_boundary", default=None
        )

    async def run_to_completion(self, claim_text: str) -> AuthoritativeGraphRunResult:
        """Compatibility helper that auto-approves fixture review interruptions."""
        result = await self.start(claim_text)
        if result.interrupt is None:
            return result
        return await self.resume(
            result.state.thread_id,
            ReviewDecision(
                kind=ReviewDecisionKind.APPROVE,
                reviewer_identity="stage9-fixture-reviewer",
                rationale="Fixture compatibility approval.",
            ),
            approver_identity="stage9-fixture-approver",
        )

    async def start(
        self,
        claim_text: str,
        *,
        thread_id: str | None = None,
        safe_boundary: Callable[[], None] | None = None,
    ) -> AuthoritativeGraphRunResult:
        """Start once or reconstruct the current state of the same graph thread."""
        thread_id = thread_id or str(uuid5(NAMESPACE_URL, f"phase9-fixture:{claim_text}"))
        config = {"configurable": {"thread_id": thread_id}}
        boundary_token = self._safe_boundary.set(safe_boundary)
        try:
            async with AsyncSqliteSaver.from_conn_string(self._langgraph_checkpoint_path) as saver:
                saver.serde = JsonPlusSerializer(pickle_fallback=False)
                graph = _build_graph(self, saver)
                before = await graph.aget_state(config)
                if before.values:
                    if before.next and not before.interrupts:
                        # A worker may have died after LangGraph durably selected the
                        # next node. Continue from that checkpoint; completed nodes
                        # and paid-operation receipts remain authoritative.
                        values = await graph.ainvoke(None, config=config)
                        snapshot = await graph.aget_state(config)
                    else:
                        snapshot = before
                        values = before.values
                else:
                    values = await graph.ainvoke(
                        {"thread_id": thread_id, "claim_text": claim_text},
                        config=config,
                    )
                    snapshot = await graph.aget_state(config)
        finally:
            self._safe_boundary.reset(boundary_token)
        return self._result(values, snapshot)

    def latest_state(self, thread_id: str) -> AuthoritativeInvestigationGraphState | None:
        """Return the latest compact durable state without executing the graph."""
        return self._state_repository.latest(thread_id)

    def state_history(self, thread_id: str) -> tuple[AuthoritativeInvestigationGraphState, ...]:
        """Return append-only checkpoints for SSE and audit reconstruction."""
        return self._state_repository.history(thread_id)

    def review_trail(self, thread_id: str):
        """Return the authoritative review trail associated with a thread."""
        return self._review_ledger.find_by_thread(thread_id)

    async def resume(
        self,
        thread_id: str,
        decision: ReviewDecision,
        *,
        approver_identity: str | None = None,
    ) -> AuthoritativeGraphRunResult:
        """Persist a typed decision and resume exactly the interrupted thread."""
        config = {"configurable": {"thread_id": thread_id}}
        async with AsyncSqliteSaver.from_conn_string(self._langgraph_checkpoint_path) as saver:
            saver.serde = JsonPlusSerializer(pickle_fallback=False)
            graph = _build_graph(self, saver)
            before = await graph.aget_state(config)
            if not before.values:
                raise GraphResumeError(f"unknown graph thread: {thread_id}")
            if not before.interrupts:
                trail = (
                    self._review_ledger.find_by_thread(thread_id)
                    if self._review_ledger is not None
                    else None
                )
                if trail and trail.decisions:
                    if any(item.decision_id == decision.decision_id for item in trail.decisions):
                        return self._result(before.values, before)
                    raise DuplicateReviewDecisionError(
                        "the graph thread already has a different accepted decision"
                    )
                raise GraphResumeError("graph thread has no pending human interruption")
            if self._review_ledger is None:
                raise GraphResumeError("authoritative review requires a durable review ledger")
            existing = self._review_ledger.find_by_thread(thread_id)
            if existing and existing.decisions:
                if existing.decisions[0].decision_id == decision.decision_id:
                    return self._result(before.values, before)
                raise DuplicateReviewDecisionError(
                    "the graph thread already has a different accepted decision"
                )
            values = await graph.ainvoke(
                Command(
                    resume={
                        "decision": decision.model_dump(mode="json"),
                        "approver_identity": approver_identity,
                    }
                ),
                config=config,
            )
            snapshot = await graph.aget_state(config)
        return self._result(values, snapshot)

    def _result(self, values, snapshot) -> AuthoritativeGraphRunResult:
        state = AuthoritativeInvestigationGraphState.model_validate(values["authoritative_state"])
        reports = self._investigations.list_artifacts(
            state.investigation_id,
            ArtifactType.REPORT,
            InvestigationReport,
        )
        interrupt_value = None
        if snapshot.interrupts:
            interrupt_value = ReviewInterruptPayload.model_validate(snapshot.interrupts[0].value)
        return AuthoritativeGraphRunResult(
            state,
            reports[-1] if reports else None,
            interrupt_value,
        )

    def close(self) -> None:
        """The async checkpointer is scoped to each execution."""

    def __enter__(self) -> AuthoritativeFixtureLangGraphWorkflow:
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    def checkpoint(
        self,
        graph: _GraphState,
        *,
        phase: AuthoritativeGraphPhase,
        operation: AuthoritativeOperation,
        **updates: Any,
    ) -> dict[str, Any]:
        prior = AuthoritativeInvestigationGraphState.model_validate(graph["authoritative_state"])
        state = prior.model_copy(
            update={
                "checkpoint_sequence": prior.checkpoint_sequence + 1,
                "phase": phase,
                "completed_operations": (*prior.completed_operations, operation),
                "operation_versions": {**prior.operation_versions, operation: 1},
                **updates,
            }
        )
        state = AuthoritativeInvestigationGraphState.model_validate(state.model_dump())
        self._state_repository.append(state)
        boundary = self._safe_boundary.get()
        if boundary is not None:
            boundary()
        return {"authoritative_state": state.model_dump(mode="json")}

    def checkpoint_progress(
        self,
        graph: _GraphState,
        *,
        phase: AuthoritativeGraphPhase,
        **updates: Any,
    ) -> dict[str, Any]:
        """Append routing/review progress without repeating an operation."""
        prior = AuthoritativeInvestigationGraphState.model_validate(graph["authoritative_state"])
        state = prior.model_copy(
            update={
                "checkpoint_sequence": prior.checkpoint_sequence + 1,
                "phase": phase,
                **updates,
            }
        )
        state = AuthoritativeInvestigationGraphState.model_validate(state.model_dump())
        self._state_repository.append(state)
        boundary = self._safe_boundary.get()
        if boundary is not None:
            boundary()
        return {"authoritative_state": state.model_dump(mode="json")}


def _build_graph(workflow: AuthoritativeFixtureLangGraphWorkflow, checkpointer):
    builder = StateGraph(_GraphState)

    async def create(graph: _GraphState):
        investigation = workflow._service.create_investigation(graph["claim_text"])
        state = AuthoritativeInvestigationGraphState(
            thread_id=graph["thread_id"],
            investigation_id=investigation.investigation_id,
            phase=AuthoritativeGraphPhase.CREATED,
            completed_operations=(AuthoritativeOperation.CREATE_INVESTIGATION,),
            operation_versions={AuthoritativeOperation.CREATE_INVESTIGATION: 1},
        )
        workflow._state_repository.append(state)
        return {"authoritative_state": state.model_dump(mode="json")}

    async def normalize(graph: _GraphState):
        state = _state(graph)
        investigation = _investigation(workflow, state)
        claim = await workflow._service.normalize_claim(investigation, graph["claim_text"])
        reference = _ref(state, ArtifactType.CLAIM, claim.claim_id)
        return workflow.checkpoint(
            graph,
            phase=AuthoritativeGraphPhase.CLAIM_ANALYSIS,
            operation=AuthoritativeOperation.NORMALIZE_CLAIM,
            parent_claim_id=claim.claim_id,
            components=(
                DurableComponentReference(
                    component_id=claim.claim_id,
                    parent_claim_id=claim.claim_id,
                    claim_summary=claim.text[:500],
                ),
            ),
            artifacts=(*state.artifacts, reference),
        )

    async def plan(graph: _GraphState):
        state = _state(graph)
        investigation, plan_value = await workflow._service.plan_investigation(
            _investigation(workflow, state),
            _one(workflow._investigations, state.investigation_id, ArtifactType.CLAIM, AtomicClaim),
        )
        del investigation
        return workflow.checkpoint(
            graph,
            phase=AuthoritativeGraphPhase.PLANNING,
            operation=AuthoritativeOperation.PLAN_INVESTIGATION,
            artifacts=(*state.artifacts, _ref(state, ArtifactType.PLAN, plan_value.claim_id)),
        )

    async def prepare(graph: _GraphState):
        state = _state(graph)
        claim = _one(
            workflow._investigations,
            state.investigation_id,
            ArtifactType.CLAIM,
            AtomicClaim,
        )
        plan_value = _one(
            workflow._investigations, state.investigation_id, ArtifactType.PLAN, InvestigationPlan
        )
        paths = workflow._service.prepare_research_requirements(claim, plan_value)
        requirements = tuple(
            DurableRequirementReference(
                requirement_id=uuid5(
                    NAMESPACE_URL,
                    f"{state.investigation_id}:requirement:{path.value}",
                ),
                component_id=claim.claim_id,
                kind=_requirement_kind(path.value),
                rationale_summary=f"Authoritative plan requires {path.value} research.",
            )
            for path in paths
        )
        return workflow.checkpoint(
            graph,
            phase=AuthoritativeGraphPhase.PLANNING,
            operation=AuthoritativeOperation.PREPARE_RESEARCH_REQUIREMENTS,
            requirements=requirements,
        )

    async def research(graph: _GraphState):
        state = _state(graph)
        investigation = _investigation(workflow, state)
        claim = _one(
            workflow._investigations,
            state.investigation_id,
            ArtifactType.CLAIM,
            AtomicClaim,
        )
        if workflow._research_adapter is None:
            plan_value = _one(
                workflow._investigations,
                state.investigation_id,
                ArtifactType.PLAN,
                InvestigationPlan,
            )
            _updated, packet = await workflow._service.execute_research(
                investigation, claim, plan_value, plan_value.required_research_paths
            )
            sources, evidence, _independence = packet
            graph_updates = {}
        else:
            budget = workflow._research_budget or state.budget
            report = await workflow._research_adapter.execute(
                investigation_id=state.investigation_id,
                claim=claim,
                requirements=state.requirements,
                budget=budget,
            )
            packet = (
                report.consolidation.sources,
                report.consolidation.evidence,
                report.consolidation.independence,
            )
            workflow._service.accept_research_packet(
                investigation,
                claim,
                packet,
            )
            sources, evidence, _independence = packet
            receipt_ledger = workflow._research_adapter.paid_operation_ledger
            receipts = (
                _receipt_references(receipt_ledger.list_receipts(state.investigation_id))
                if receipt_ledger is not None
                else ()
            )
            graph_updates = {
                "budget": budget,
                "assignments": tuple(
                    DurableAssignmentReference(
                        assignment_id=item.assignment_id,
                        component_id=item.component_id,
                        role=item.role,
                        round_number=item.round_number,
                        requirement_ids=item.requirement_ids,
                    )
                    for item in report.assignments
                ),
                "research_results": tuple(
                    DurableResultReference(
                        result_id=item.result_id,
                        assignment_id=item.assignment_id,
                        component_id=item.component_id,
                        source_ids=item.source_ids,
                        evidence_ids=item.evidence_ids,
                        unresolved_requirement_ids=item.unresolved_requirement_ids,
                        failure_summary=item.failure_reason,
                    )
                    for item in report.results
                ),
                "evidence_families": tuple(
                    DurableEvidenceFamilyReference(
                        family_id=evidence_family_id(item.source_ids),
                        source_ids=item.source_ids,
                        evidence_ids=item.evidence_ids,
                        grouping_summary=(
                            "Consolidated evidence family: "
                            + ", ".join(item.hostnames or ("unknown host",))
                        )[:500],
                    )
                    for item in report.consolidation.independence.families
                    if item.source_ids and item.evidence_ids
                ),
                "consumption": report.consumption,
                "paid_receipts": receipts,
                "unresolved_questions": tuple(
                    DurableUnresolvedQuestion(
                        component_id=claim.claim_id,
                        requirement_ids=(requirement_id,),
                        question_summary=(
                            "Research stopped before satisfying requirement "
                            f"{requirement_id}: {report.final_assessment.decision.value}."
                        ),
                    )
                    for requirement_id in report.unresolved_requirement_ids
                ),
            }
        references = [
            *(_ref(state, ArtifactType.SOURCE, item.source_id) for item in sources),
            *(_ref(state, ArtifactType.EVIDENCE, item.evidence_id) for item in evidence),
            _ref(state, ArtifactType.INDEPENDENCE, claim.claim_id),
        ]
        if workflow._research_adapter is None:
            references.extend(
                _ref(state, ArtifactType.CHUNK, item.chunk_id)
                for item in evidence
                if item.chunk_id is not None
            )
        checkpoint_update = workflow.checkpoint(
            graph,
            phase=AuthoritativeGraphPhase.RESEARCH,
            operation=AuthoritativeOperation.EXECUTE_RESEARCH,
            artifacts=_merge_refs(state.artifacts, tuple(references)),
            **graph_updates,
        )
        if workflow._research_adapter is not None:
            checkpoint_update["review_required"] = report.human_review_required
        return checkpoint_update

    async def consolidate(graph: _GraphState):
        state = _state(graph)
        sources = _many(workflow, state, ArtifactType.SOURCE, Source)
        evidence = _many(workflow, state, ArtifactType.EVIDENCE, Evidence)
        independence = _one(
            workflow._investigations,
            state.investigation_id,
            ArtifactType.INDEPENDENCE,
            IndependenceAnalysis,
        )
        workflow._service.consolidate_evidence((sources, evidence, independence))
        return workflow.checkpoint(
            graph,
            phase=AuthoritativeGraphPhase.RESEARCH,
            operation=AuthoritativeOperation.CONSOLIDATE_EVIDENCE,
            approved_evidence_ids=tuple(item.evidence_id for item in evidence),
        )

    async def provenance(graph: _GraphState):
        state = _state(graph)
        claim = _claim(workflow, state)
        if workflow._verification_workflow is None:
            workflow._service.analyze_provenance(
                _investigation(workflow, state),
                claim,
                _plan(workflow, state),
                _many(workflow, state, ArtifactType.SOURCE, Source),
                _many(workflow, state, ArtifactType.EVIDENCE, Evidence),
            )
            references = (_ref(state, ArtifactType.PROVENANCE, claim.claim_id),)
        else:
            evidence = _approved_evidence(workflow, state)
            report = await workflow._verification_workflow.execute(
                investigation_id=state.investigation_id,
                claim=claim,
                plan=_plan(workflow, state),
                sources=_many(workflow, state, ArtifactType.SOURCE, Source),
                evidence=evidence,
                approved_evidence_ids=state.approved_evidence_ids,
            )
            workflow._service.accept_verification_report(_investigation(workflow, state), report)
            references = (
                _ref(state, ArtifactType.PROVENANCE, claim.claim_id),
                _ref(state, ArtifactType.CONTEXT_VERIFICATION, claim.claim_id),
                _ref(state, ArtifactType.VERIFICATION_PACKET, claim.claim_id),
                _ref(state, ArtifactType.COVERAGE, claim.claim_id),
            )
        return workflow.checkpoint(
            graph,
            phase=AuthoritativeGraphPhase.VERIFICATION,
            operation=AuthoritativeOperation.ANALYZE_PROVENANCE,
            artifacts=_merge_refs(state.artifacts, references),
        )

    async def verify(graph: _GraphState):
        state = _state(graph)
        claim = _claim(workflow, state)
        if workflow._verification_workflow is None:
            workflow._service.verify_context(
                _investigation(workflow, state),
                claim,
                _plan(workflow, state),
                _many(workflow, state, ArtifactType.SOURCE, Source),
                _many(workflow, state, ArtifactType.EVIDENCE, Evidence),
            )
        refs = (
            _ref(state, ArtifactType.CONTEXT_VERIFICATION, claim.claim_id),
            _ref(state, ArtifactType.VERIFICATION_PACKET, claim.claim_id),
        )
        verification_packet = _one(
            workflow._investigations,
            state.investigation_id,
            ArtifactType.VERIFICATION_PACKET,
            VerificationPacketV2,
        )
        return workflow.checkpoint(
            graph,
            phase=AuthoritativeGraphPhase.VERIFICATION,
            operation=AuthoritativeOperation.VERIFY_CONTEXT,
            artifacts=_merge_refs(state.artifacts, refs),
            verification_construction_ids=tuple(
                item.construction_id
                for item in (
                    *verification_packet.comparative_constructions,
                    *verification_packet.temporal_constructions,
                )
            ),
            verification_construction_states={
                item.construction_id: item.state
                for item in (
                    *verification_packet.comparative_constructions,
                    *verification_packet.temporal_constructions,
                )
            },
        )

    async def ledger(graph: _GraphState):
        state = _state(graph)
        claim = _claim(workflow, state)
        workflow._service.build_argument_ledger(
            _investigation(workflow, state),
            claim,
            _many(workflow, state, ArtifactType.EVIDENCE, Evidence),
            _one(
                workflow._investigations,
                state.investigation_id,
                ArtifactType.VERIFICATION_PACKET,
                VerificationPacketV2,
            ),
            _one(
                workflow._investigations,
                state.investigation_id,
                ArtifactType.PROVENANCE,
                InvestigationProvenance,
            ),
        )
        reference = _ref(state, ArtifactType.ARGUMENT_LEDGER, claim.claim_id)
        return workflow.checkpoint(
            graph,
            phase=AuthoritativeGraphPhase.ARGUMENTS,
            operation=AuthoritativeOperation.BUILD_ARGUMENT_LEDGER,
            artifacts=(*state.artifacts, reference),
            reconciled_ledger_ref=reference,
        )

    async def defender(graph: _GraphState):
        state = _state(graph)
        approved_evidence = _approved_evidence(workflow, state)
        if workflow._argument_workflow is None or not approved_evidence:
            workflow._service.construct_defender_argument(_ledger(workflow, state))
            return {
                **workflow.checkpoint(
                    graph,
                    phase=AuthoritativeGraphPhase.ARGUMENTS,
                    operation=AuthoritativeOperation.CONSTRUCT_DEFENDER_ARGUMENT,
                    defender_result_id=uuid5(NAMESPACE_URL, f"{state.investigation_id}:defender"),
                ),
                "review_required": (bool(graph.get("review_required")) or not approved_evidence),
            }
        report = await workflow._argument_workflow.start_or_resume(
            investigation_id=state.investigation_id,
            claim=_claim(workflow, state),
            approved_evidence=approved_evidence,
            authoritative_ledger=_ledger(workflow, state),
            verification=_one(
                workflow._investigations,
                state.investigation_id,
                ArtifactType.VERIFICATION_PACKET,
                VerificationPacketV2,
            ),
            provenance=_one(
                workflow._investigations,
                state.investigation_id,
                ArtifactType.PROVENANCE,
                InvestigationProvenance,
            ),
        )
        defender_result = next(item for item in report.results if item.role.value == "defender")
        return {
            **workflow.checkpoint(
                graph,
                phase=AuthoritativeGraphPhase.ARGUMENTS,
                operation=AuthoritativeOperation.CONSTRUCT_DEFENDER_ARGUMENT,
                defender_result_id=defender_result.result_id,
            ),
            "adversarial_report": report.model_dump(mode="json"),
            "review_required": (bool(graph.get("review_required")) or report.human_review_required),
        }

    async def challenger(graph: _GraphState):
        state = _state(graph)
        if workflow._argument_workflow is None or not graph.get("adversarial_report"):
            workflow._service.construct_challenger_argument(_ledger(workflow, state))
            result_id = uuid5(NAMESPACE_URL, f"{state.investigation_id}:challenger")
        else:
            report = AdversarialArgumentReport.model_validate(graph["adversarial_report"])
            result_id = next(
                item.result_id for item in report.results if item.role.value == "challenger"
            )
        return workflow.checkpoint(
            graph,
            phase=AuthoritativeGraphPhase.ARGUMENTS,
            operation=AuthoritativeOperation.CONSTRUCT_CHALLENGER_ARGUMENT,
            challenger_result_id=result_id,
        )

    async def reconcile(graph: _GraphState):
        state = _state(graph)
        value = _ledger(workflow, state)
        if workflow._argument_workflow is None or not graph.get("adversarial_report"):
            workflow._service.reconcile_arguments(value, value)
        else:
            workflow._service.reconcile_adversarial_report(
                value,
                AdversarialArgumentReport.model_validate(graph["adversarial_report"]),
            )
        workflow._service.evaluate_social_evidence_policy(
            _investigation(workflow, state),
            value,
            _many(workflow, state, ArtifactType.SOURCE, Source),
            _many(workflow, state, ArtifactType.EVIDENCE, Evidence),
            _one(
                workflow._investigations,
                state.investigation_id,
                ArtifactType.PROVENANCE,
                InvestigationProvenance,
            ),
        )
        reference = _ref(state, ArtifactType.SOCIAL_EVIDENCE_POLICY, state.parent_claim_id)
        return workflow.checkpoint(
            graph,
            phase=AuthoritativeGraphPhase.ARGUMENTS,
            operation=AuthoritativeOperation.RECONCILE_ARGUMENTS,
            artifacts=(*state.artifacts, reference),
        )

    async def draft(graph: _GraphState):
        state = _state(graph)
        investigation, verdict = await workflow._service.draft_verdict(
            _investigation(workflow, state),
            _claim(workflow, state),
            _many(workflow, state, ArtifactType.SOURCE, Source),
            _many(workflow, state, ArtifactType.EVIDENCE, Evidence),
            _one(
                workflow._investigations,
                state.investigation_id,
                ArtifactType.INDEPENDENCE,
                IndependenceAnalysis,
            ),
            _one(
                workflow._investigations,
                state.investigation_id,
                ArtifactType.CONTEXT_VERIFICATION,
                ContextVerification,
            ),
            _one(
                workflow._investigations,
                state.investigation_id,
                ArtifactType.VERIFICATION_PACKET,
                VerificationPacketV2,
            ),
            _ledger(workflow, state),
        )
        del investigation
        return {
            **workflow.checkpoint(
                graph,
                phase=AuthoritativeGraphPhase.JUDGMENT,
                operation=AuthoritativeOperation.DRAFT_VERDICT,
            ),
            "provisional_verdict": verdict.model_dump(mode="json"),
        }

    async def policy(graph: _GraphState):
        state = _state(graph)
        verdict, _policy = workflow._service.apply_judgment_policy(
            _investigation(workflow, state),
            Verdict.model_validate(graph["provisional_verdict"]),
            _many(workflow, state, ArtifactType.EVIDENCE, Evidence),
            _one(
                workflow._investigations,
                state.investigation_id,
                ArtifactType.INDEPENDENCE,
                IndependenceAnalysis,
            ),
            _one(
                workflow._investigations,
                state.investigation_id,
                ArtifactType.CONTEXT_VERIFICATION,
                ContextVerification,
            ),
            _ledger(workflow, state),
            _one(
                workflow._investigations,
                state.investigation_id,
                ArtifactType.SOCIAL_EVIDENCE_POLICY,
                SocialEvidencePolicyResult,
            ),
        )
        reference = _ref(state, ArtifactType.JUDGMENT_POLICY, verdict.verdict_id)
        proposed_ref = _ref(state, ArtifactType.PROPOSED_VERDICT, verdict.verdict_id)
        enforced_ref = _ref(state, ArtifactType.ENFORCED_VERDICT, verdict.verdict_id)
        return {
            **workflow.checkpoint(
                graph,
                phase=AuthoritativeGraphPhase.JUDGMENT,
                operation=AuthoritativeOperation.APPLY_JUDGMENT_POLICY,
                artifacts=_merge_refs(state.artifacts, (reference, proposed_ref, enforced_ref)),
                proposed_verdict_ref=proposed_ref,
                enforced_verdict_ref=enforced_ref,
            ),
            "provisional_verdict": verdict.model_dump(mode="json"),
        }

    async def audit(graph: _GraphState):
        state = _state(graph)
        _investigation_value, verdict, _audit, _assurance = await workflow._service.audit_citations(
            _investigation(workflow, state),
            _claim(workflow, state),
            Verdict.model_validate(graph["provisional_verdict"]),
            _many(workflow, state, ArtifactType.EVIDENCE, Evidence),
        )
        verdict_ref = _ref(state, ArtifactType.VERDICT, verdict.verdict_id)
        assurance_ref = _ref(state, ArtifactType.FULL_REPORT_ASSURANCE, state.parent_claim_id)
        audit_value = _many(workflow, state, ArtifactType.AUDIT, SentenceAudit)[-1]
        refs = (
            verdict_ref,
            _ref(state, ArtifactType.AUDIT, audit_value.sentence_id),
            assurance_ref,
        )
        return {
            **workflow.checkpoint(
                graph,
                phase=AuthoritativeGraphPhase.CITATION_ASSURANCE,
                operation=AuthoritativeOperation.AUDIT_CITATIONS,
                artifacts=(*state.artifacts, *refs),
                enforced_verdict_ref=verdict_ref,
                citation_assurance_ref=assurance_ref,
            ),
            "provisional_verdict": verdict.model_dump(mode="json"),
        }

    async def readiness(graph: _GraphState):
        state = _state(graph)
        claim = _claim(workflow, state)
        workflow._service.assess_readiness(
            _investigation(workflow, state),
            claim,
            _ledger(workflow, state),
            _one(
                workflow._investigations,
                state.investigation_id,
                ArtifactType.VERIFICATION_PACKET,
                VerificationPacketV2,
            ),
            _one(
                workflow._investigations,
                state.investigation_id,
                ArtifactType.PROVENANCE,
                InvestigationProvenance,
            ),
            _many(workflow, state, ArtifactType.AUDIT, SentenceAudit)[-1],
            Verdict.model_validate(graph["provisional_verdict"]),
            _one(
                workflow._investigations,
                state.investigation_id,
                ArtifactType.SOCIAL_EVIDENCE_POLICY,
                SocialEvidencePolicyResult,
            ),
        )
        reference = _ref(state, ArtifactType.READINESS, claim.claim_id)
        return workflow.checkpoint(
            graph,
            phase=AuthoritativeGraphPhase.READINESS,
            operation=AuthoritativeOperation.ASSESS_READINESS,
            artifacts=(*state.artifacts, reference),
            readiness_ref=reference,
        )

    async def route(graph: _GraphState):
        state = _state(graph)
        enforced_verdict = Verdict.model_validate(graph["provisional_verdict"])
        readiness = _one(
            workflow._investigations,
            state.investigation_id,
            ArtifactType.READINESS,
            JudgmentReadiness,
        )
        assurance = _one(
            workflow._investigations,
            state.investigation_id,
            ArtifactType.FULL_REPORT_ASSURANCE,
            FullReportCitationAssurance,
        )
        proposed_verdict = _one(
            workflow._investigations,
            state.investigation_id,
            ArtifactType.PROPOSED_VERDICT,
            Verdict,
        )
        policy = _one(
            workflow._investigations,
            state.investigation_id,
            ArtifactType.JUDGMENT_POLICY,
            JudgmentPolicyTrace,
        )
        provenance = _one(
            workflow._investigations,
            state.investigation_id,
            ArtifactType.PROVENANCE,
            InvestigationProvenance,
        )
        policy_review = workflow._service.route_review(
            enforced_verdict,
            readiness,
            assurance,
        )
        decision = workflow._service.assess_publication(
            _investigation(workflow, state),
            proposed_verdict,
            enforced_verdict,
            policy,
            assurance,
            readiness,
            _one(
                workflow._investigations,
                state.investigation_id,
                ArtifactType.SOCIAL_EVIDENCE_POLICY,
                SocialEvidencePolicyResult,
            ),
        )
        routing = route_human_review(
            ReviewRoutingContext(
                claim_id=state.parent_claim_id,
                risk_level=ReviewRiskLevel.MEDIUM,
                citation_assurance=assurance.final_audit,
                readiness_state=readiness.state,
                provenance_state=provenance.requirement_state,
                critical_verification_unresolved=(
                    readiness.verification_assertion_count > 0
                    and readiness.verification_completeness < 1
                ),
                policy_disagreement=(
                    proposed_verdict.label is not enforced_verdict.label
                    or policy.human_review_required
                ),
                blocking_challenge_count=readiness.blocking_challenge_count,
                verdict_requested_review=workflow._require_human_review,
            )
        )
        routing_id = uuid5(NAMESPACE_URL, f"{state.thread_id}:review-routing")
        workflow._service.record_review_routing(
            _investigation(workflow, state),
            routing_id,
            routing,
        )
        review = (
            bool(graph.get("review_required"))
            or policy_review
            or decision.human_review_required
            or routing.review_required
        )
        decision_ref = _ref(state, ArtifactType.PUBLICATION_DECISION, decision.decision_id)
        routing_ref = _ref(state, ArtifactType.REVIEW_ROUTING, routing_id)
        review_request_ids = state.review_request_ids
        if review:
            request = workflow._review_ledger.find_by_thread(state.thread_id)
            if request is None:
                created = workflow._review_ledger.create_request(
                    ReviewRequest(
                        request_id=uuid5(NAMESPACE_URL, f"{state.thread_id}:review-request"),
                        investigation_id=state.investigation_id,
                        graph_thread_id=state.thread_id,
                        claim_id=state.parent_claim_id,
                        reason=" ".join((*decision.blocking_reasons, routing.reason)),
                        created_by="authoritative-langgraph",
                    )
                )
                review_request_ids = (*review_request_ids, created.request_id)
            else:
                review_request_ids = (*review_request_ids, request.request.request_id)
        return {
            **workflow.checkpoint(
                graph,
                phase=(
                    AuthoritativeGraphPhase.REVIEW
                    if review
                    else AuthoritativeGraphPhase.FINALIZATION
                ),
                operation=AuthoritativeOperation.ROUTE_REVIEW,
                artifacts=(*state.artifacts, decision_ref, routing_ref),
                publication_decision_ref=decision_ref,
                publication_blocked=not decision.publication_allowed,
                publication_blocking_reasons=(
                    decision.blocking_reasons if not decision.publication_allowed else ()
                ),
                review_request_ids=tuple(dict.fromkeys(review_request_ids)),
            ),
            "review_required": review,
        }

    async def review(graph: _GraphState):
        state = _state(graph)
        allowed_decisions = (
            (
                ReviewDecisionKind.REQUEST_EVIDENCE,
                ReviewDecisionKind.REJECT,
            )
            if not state.approved_evidence_ids
            else (
                ReviewDecisionKind.APPROVE,
                ReviewDecisionKind.REVISE,
                ReviewDecisionKind.REQUEST_EVIDENCE,
                ReviewDecisionKind.REJECT,
            )
        )
        payload = ReviewInterruptPayload(
            thread_id=state.thread_id,
            question="Approve, revise, request more evidence, or reject this investigation.",
            claim_text=_claim(workflow, state).text,
            provisional_verdict=Verdict.model_validate(graph["provisional_verdict"]).label,
            approved_evidence_ids=state.approved_evidence_ids,
            route_reason=(
                " ".join(state.publication_blocking_reasons)
                or "Authoritative human review is required."
            ),
            allowed_decisions=allowed_decisions,
        )
        raw = interrupt(payload.model_dump(mode="json"))
        envelope = dict(raw)
        decision = ReviewDecision.model_validate(envelope["decision"])
        if (
            decision.verification_construction_id is not None
            and decision.verification_construction_id
            not in state.verification_construction_ids
        ):
            raise ValueError(
                "review decision references an unknown verification construction"
            )
        if not set(decision.corrected_evidence_ids).issubset(
            state.approved_evidence_ids
        ):
            raise ValueError(
                "verification corrections may reference only approved evidence"
            )
        approver_identity = envelope.get("approver_identity")
        trail = workflow._review_ledger.find_by_thread(state.thread_id)
        if trail is None:
            raise ValueError("review interruption has no durable review request")
        request = trail.request
        record = workflow._review_ledger.record_decision(
            ReviewerDecisionRecord(
                decision_id=decision.decision_id,
                request_id=request.request_id,
                kind=decision.kind,
                reviewer_identity=decision.reviewer_identity,
                rationale=decision.rationale,
                proposed_verdict=decision.revised_verdict,
                verification_construction_id=decision.verification_construction_id,
                verification_disposition=decision.verification_disposition,
                corrected_left_subject=decision.corrected_left_subject,
                corrected_right_subject=decision.corrected_right_subject,
                corrected_comparator=decision.corrected_comparator,
                corrected_claim_text_span=decision.corrected_claim_text_span,
                corrected_value=decision.corrected_value,
                corrected_unit=decision.corrected_unit,
                corrected_evidence_ids=decision.corrected_evidence_ids,
            ),
            expected_sequence=len(trail.events),
        )
        if decision.kind in {ReviewDecisionKind.APPROVE, ReviewDecisionKind.REVISE}:
            if not approver_identity:
                raise ValueError("approval and revision require a distinct approver")
            approval = workflow._review_ledger.record_approval(
                ApprovalRecord(
                    approval_id=uuid5(NAMESPACE_URL, f"{decision.decision_id}:approval"),
                    request_id=request.request_id,
                    decision_record_id=record.record_id,
                    approver_identity=approver_identity,
                    decision=ApprovalDecision.APPROVE,
                    rationale=f"Approved review decision {decision.decision_id}.",
                ),
                expected_sequence=len(workflow._review_ledger.load(request.request_id).events),
            )
        else:
            approval = None
        provisional = Verdict.model_validate(graph["provisional_verdict"])
        if decision.kind is ReviewDecisionKind.REVISE:
            revised = Verdict.model_validate(
                {
                    **provisional.model_dump(),
                    "verdict_id": str(uuid5(NAMESPACE_URL, f"{decision.decision_id}:verdict")),
                    "version": provisional.version + 1,
                    "label": decision.revised_verdict,
                    "human_review_required": False,
                    "review_reason": None,
                }
            )
            workflow._service._save_artifact(
                _investigation(workflow, state),
                ArtifactType.VERDICT,
                revised.verdict_id,
                revised,
            )
            revised_assurance = assure_full_report(
                claim_id=revised.claim_id,
                verdict=revised,
                evidence=_approved_evidence(workflow, state),
                approved_evidence_ids=state.approved_evidence_ids,
            )
            workflow._service._save_artifact(
                _investigation(workflow, state),
                ArtifactType.FULL_REPORT_ASSURANCE,
                revised.claim_id,
                revised_assurance,
            )
            workflow._review_ledger.record_revision(
                VerdictRevision(
                    revision_id=uuid5(NAMESPACE_URL, f"{decision.decision_id}:revision"),
                    request_id=request.request_id,
                    decision_record_id=record.record_id,
                    approval_id=approval.approval_id,
                    original_verdict_id=provisional.verdict_id,
                    original_verdict=provisional.label,
                    revised_verdict=revised.label,
                    change_kind=AuthoritativeChangeKind.INVESTIGATION_VERDICT,
                    rationale=decision.rationale,
                ),
                expected_sequence=len(workflow._review_ledger.load(request.request_id).events),
            )
            provisional = revised
        return {
            **workflow.checkpoint_progress(
                graph,
                phase=AuthoritativeGraphPhase.REVIEW,
                review_decision_ids=(
                    *state.review_decision_ids,
                    decision.decision_id,
                ),
                enforced_verdict_ref=(
                    _ref(state, ArtifactType.VERDICT, provisional.verdict_id)
                    if decision.kind is ReviewDecisionKind.REVISE
                    else state.enforced_verdict_ref
                ),
                artifacts=(
                    _merge_refs(
                        state.artifacts,
                        (
                            _ref(
                                state,
                                ArtifactType.VERDICT,
                                provisional.verdict_id,
                            ),
                        ),
                    )
                    if decision.kind is ReviewDecisionKind.REVISE
                    else state.artifacts
                ),
            ),
            "provisional_verdict": provisional.model_dump(mode="json"),
            "decision_kind": decision.kind.value,
        }

    async def approve_or_revise(graph: _GraphState):
        state = _state(graph)
        decision = _one(
            workflow._investigations,
            state.investigation_id,
            ArtifactType.PUBLICATION_DECISION,
            AuthoritativePublicationDecision,
        )
        if (
            decision.status is AuthoritativePublicationStatus.REVIEW_REQUIRED
            or graph["decision_kind"] == ReviewDecisionKind.REVISE.value
        ):
            assurance = _one(
                workflow._investigations,
                state.investigation_id,
                ArtifactType.FULL_REPORT_ASSURANCE,
                FullReportCitationAssurance,
            )
            citation_blocked = assurance.publication_status.value == "blocked"
            social_policy = _one(
                workflow._investigations,
                state.investigation_id,
                ArtifactType.SOCIAL_EVIDENCE_POLICY,
                SocialEvidencePolicyResult,
            )
            publication_blocked = citation_blocked or social_policy.publication_blocked
            blocking_reasons = (
                *assurance.blocking_reasons,
                *social_policy.blocking_reasons,
            )
            updated = decision.model_copy(
                update={
                    "decision_id": uuid5(
                        NAMESPACE_URL,
                        f"{state.thread_id}:{state.review_decision_ids[-1]}:publication",
                    ),
                    "enforced_label": Verdict.model_validate(graph["provisional_verdict"]).label,
                    "citation_revision_count": len(assurance.revisions),
                    "citation_support_rate": assurance.final_audit.full_support_rate,
                    "unsupported_critical_assertion_count": (assurance.critical_failure_count),
                    "status": (
                        AuthoritativePublicationStatus.BLOCKED
                        if publication_blocked
                        else AuthoritativePublicationStatus.READY
                    ),
                    "publication_allowed": not publication_blocked,
                    "human_review_required": publication_blocked,
                    "reason_codes": (
                        (
                            (
                                "social_evidence_policy_blocked"
                                if social_policy.publication_blocked
                                else "citation_assurance_blocked"
                            ),
                        )
                        if publication_blocked
                        else ("human_review_approved",)
                    ),
                    "blocking_reasons": (blocking_reasons if publication_blocked else ()),
                }
            )
            workflow._service._save_artifact(
                _investigation(workflow, state),
                ArtifactType.PUBLICATION_DECISION,
                updated.decision_id,
                updated,
            )
            decision = updated
        reference = _ref(state, ArtifactType.PUBLICATION_DECISION, decision.decision_id)
        return workflow.checkpoint_progress(
            graph,
            phase=AuthoritativeGraphPhase.FINALIZATION,
            artifacts=_merge_refs(state.artifacts, (reference,)),
            publication_decision_ref=reference,
            publication_blocked=not decision.publication_allowed,
            publication_blocking_reasons=(
                decision.blocking_reasons if not decision.publication_allowed else ()
            ),
        )

    async def more_evidence(graph: _GraphState):
        return workflow.checkpoint_progress(
            graph,
            phase=AuthoritativeGraphPhase.REVIEW,
        )

    async def reject(graph: _GraphState):
        return workflow.checkpoint_progress(
            graph,
            phase=AuthoritativeGraphPhase.CANCELLED,
        )

    async def finalize(graph: _GraphState):
        state = _state(graph)
        report = workflow._service.finalize_report(
            investigation=_investigation(workflow, state),
            claim=_claim(workflow, state),
            plan=_plan(workflow, state),
            sources=_many(workflow, state, ArtifactType.SOURCE, Source),
            evidence_items=_many(workflow, state, ArtifactType.EVIDENCE, Evidence),
            independence=_one(
                workflow._investigations,
                state.investigation_id,
                ArtifactType.INDEPENDENCE,
                IndependenceAnalysis,
            ),
            provenance=_one(
                workflow._investigations,
                state.investigation_id,
                ArtifactType.PROVENANCE,
                InvestigationProvenance,
            ),
            verification_packet=_one(
                workflow._investigations,
                state.investigation_id,
                ArtifactType.VERIFICATION_PACKET,
                VerificationPacketV2,
            ),
            argument_ledger=_ledger(workflow, state),
            judgment_policy=_one(
                workflow._investigations,
                state.investigation_id,
                ArtifactType.JUDGMENT_POLICY,
                JudgmentPolicyTrace,
            ),
            readiness=_one(
                workflow._investigations,
                state.investigation_id,
                ArtifactType.READINESS,
                JudgmentReadiness,
            ),
            context_verification=_one(
                workflow._investigations,
                state.investigation_id,
                ArtifactType.CONTEXT_VERIFICATION,
                ContextVerification,
            ),
            verdict=Verdict.model_validate(graph["provisional_verdict"]),
            audit=_many(workflow, state, ArtifactType.AUDIT, SentenceAudit)[-1],
            full_report_assurance=_one(
                workflow._investigations,
                state.investigation_id,
                ArtifactType.FULL_REPORT_ASSURANCE,
                FullReportCitationAssurance,
            ),
            publication_decision=_many(
                workflow,
                state,
                ArtifactType.PUBLICATION_DECISION,
                AuthoritativePublicationDecision,
            )[-1],
            social_evidence_policy=_one(
                workflow._investigations,
                state.investigation_id,
                ArtifactType.SOCIAL_EVIDENCE_POLICY,
                SocialEvidencePolicyResult,
            ),
        )
        workflow._service.persist_final_report(report)
        report_ref = _ref(state, ArtifactType.REPORT, state.investigation_id)
        return workflow.checkpoint(
            graph,
            phase=AuthoritativeGraphPhase.COMPLETE,
            operation=AuthoritativeOperation.FINALIZE_REPORT,
            artifacts=(*state.artifacts, report_ref),
            final_report_ref=report_ref,
        )

    nodes = {
        "create": create,
        "normalize": normalize,
        "plan": plan,
        "prepare": prepare,
        "research": research,
        "consolidate": consolidate,
        "provenance": provenance,
        "verify": verify,
        "ledger": ledger,
        "defender": defender,
        "challenger": challenger,
        "reconcile": reconcile,
        "draft": draft,
        "policy": policy,
        "audit": audit,
        "readiness": readiness,
        "route": route,
        "review": review,
        "approve_or_revise": approve_or_revise,
        "more_evidence": more_evidence,
        "reject": reject,
        "finalize": finalize,
    }
    for name, node in nodes.items():
        builder.add_node(name, node)
    sequence = tuple(nodes)[:17]
    builder.add_edge(START, sequence[0])
    for prior, following in pairwise(sequence):
        builder.add_edge(prior, following)
    builder.add_conditional_edges(
        "route",
        lambda state: "review" if state.get("review_required") else "finalize",
        {"review": "review", "finalize": "finalize"},
    )
    builder.add_conditional_edges(
        "review",
        lambda state: (
            "more_evidence"
            if state.get("decision_kind") == ReviewDecisionKind.REQUEST_EVIDENCE.value
            else (
                "reject"
                if state.get("decision_kind") == ReviewDecisionKind.REJECT.value
                else "approve_or_revise"
            )
        ),
        {
            "approve_or_revise": "approve_or_revise",
            "more_evidence": "more_evidence",
            "reject": "reject",
        },
    )
    builder.add_edge("approve_or_revise", "finalize")
    builder.add_edge("more_evidence", END)
    builder.add_edge("reject", END)
    builder.add_edge("finalize", END)
    return builder.compile(checkpointer=checkpointer)


def _state(graph: _GraphState) -> AuthoritativeInvestigationGraphState:
    return AuthoritativeInvestigationGraphState.model_validate(graph["authoritative_state"])


def _investigation(
    workflow: AuthoritativeFixtureLangGraphWorkflow,
    state: AuthoritativeInvestigationGraphState,
) -> Investigation:
    value = workflow._investigations.get_investigation(state.investigation_id)
    if value is None:
        raise ValueError("authoritative investigation is missing")
    return value


def _one(repository, investigation_id, artifact_type, model):
    values = repository.list_artifacts(investigation_id, artifact_type, model)
    if len(values) != 1:
        raise ValueError(f"expected one {artifact_type.value} artifact")
    return values[0]


def _many(workflow, state, artifact_type, model):
    return workflow._investigations.list_artifacts(state.investigation_id, artifact_type, model)


def _claim(workflow, state):
    return _one(workflow._investigations, state.investigation_id, ArtifactType.CLAIM, AtomicClaim)


def _plan(workflow, state):
    return _one(
        workflow._investigations,
        state.investigation_id,
        ArtifactType.PLAN,
        InvestigationPlan,
    )


def _ledger(workflow, state):
    return _one(
        workflow._investigations,
        state.investigation_id,
        ArtifactType.ARGUMENT_LEDGER,
        ArgumentLedger,
    )


def _approved_evidence(workflow, state):
    by_id = {
        item.evidence_id: item for item in _many(workflow, state, ArtifactType.EVIDENCE, Evidence)
    }
    if not set(state.approved_evidence_ids) <= set(by_id):
        raise ValueError("approved graph evidence is missing from persistence")
    return tuple(by_id[item] for item in state.approved_evidence_ids)


def _ref(state, artifact_type, artifact_id):
    return ArtifactReference(
        investigation_id=state.investigation_id,
        artifact_type=artifact_type,
        artifact_id=artifact_id,
    )


def _merge_refs(existing, added):
    seen = {(item.artifact_type, item.artifact_id) for item in existing}
    return (
        *existing,
        *(item for item in added if (item.artifact_type, item.artifact_id) not in seen),
    )


def _requirement_kind(path: str) -> ResearchRequirementKind:
    return {
        "primary": ResearchRequirementKind.PRIMARY_SOURCE,
        "academic": ResearchRequirementKind.ACADEMIC_EVIDENCE,
        "fact_check": ResearchRequirementKind.PRIOR_FACT_CHECK,
        "contradiction": ResearchRequirementKind.CONTRADICTION_OR_QUALIFICATION,
        "general": ResearchRequirementKind.COMPONENT_COVERAGE,
    }[path]


def _receipt_references(receipts):
    return tuple(
        PaidOperationReceiptReference(
            receipt_id=item.receipt_id,
            operation=AuthoritativeOperation.EXECUTE_RESEARCH,
            provider=item.spec.provider,
            canonical_input_sha256=item.spec.canonical_input_sha256,
            status=PaidOperationReceiptStatus(item.status.value),
        )
        for item in receipts
    )
