"""Stage 8.7 independent argument fan-out and reconciliation tests."""

import asyncio
from uuid import uuid4

import pytest
from pydantic import ValidationError

from claim_polygraph_ng.analysis import build_argument_ledger
from claim_polygraph_ng.application import (
    DeterministicArgumentWorker,
    LangGraphAdversarialArgumentWorkflow,
)
from claim_polygraph_ng.domain import (
    ARGUMENT_PERMISSIONS,
    AdversarialArgumentCheckpoint,
    ArgumentAssignment,
    ArgumentRole,
    ArgumentRoleResult,
    ArgumentWorkflowStage,
    AtomicClaim,
    Evidence,
    EvidenceStance,
    PropositionArgument,
    PropositionResolution,
)
from claim_polygraph_ng.persistence import SQLiteResearchRepository


class ConcurrentArgumentWorker:
    def __init__(self) -> None:
        self.delegate = DeterministicArgumentWorker()
        self.active = 0
        self.maximum_active = 0
        self.calls = []

    async def run(self, assignment, checkpoint):
        self.calls.append(assignment.role)
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        try:
            await asyncio.sleep(0.03)
            return await self.delegate.run(assignment, checkpoint)
        finally:
            self.active -= 1


class OutOfPacketWorker:
    async def run(self, assignment, _checkpoint):
        invented = uuid4()
        return ArgumentRoleResult(
            assignment_id=assignment.assignment_id,
            claim_id=assignment.claim_id,
            role=assignment.role,
            arguments=tuple(
                PropositionArgument(
                    proposition_id=proposition_id,
                    resolution=PropositionResolution.SUPPORTED,
                    supporting_evidence_ids=(invented,),
                )
                for proposition_id in assignment.proposition_ids
            ),
            consumed_evidence_ids=(invented,),
        )


def test_defender_and_challenger_run_concurrently_and_reconcile_exactly(
    tmp_path,
) -> None:
    repository = SQLiteResearchRepository(tmp_path / "arguments.db")
    worker = ConcurrentArgumentWorker()
    claim, evidence = _packet()
    authoritative = build_argument_ledger(claim=claim, evidence=evidence)
    workflow = LangGraphAdversarialArgumentWorkflow(
        repository=repository,
        worker=worker,
    )
    investigation_id = uuid4()

    first = asyncio.run(
        workflow.start_or_resume(
            investigation_id=investigation_id,
            claim=claim,
            approved_evidence=evidence,
            authoritative_ledger=authoritative,
        )
    )
    calls_after_first = len(worker.calls)
    resumed = asyncio.run(
        workflow.start_or_resume(
            investigation_id=investigation_id,
            claim=claim,
            approved_evidence=evidence,
            authoritative_ledger=authoritative,
        )
    )

    assert worker.maximum_active == 2
    assert {item.role for item in first.results} == {
        ArgumentRole.DEFENDER,
        ArgumentRole.CHALLENGER,
    }
    assert all(item.permissions == ARGUMENT_PERMISSIONS for item in first.assignments)
    assert all(item.search_calls == item.fetch_calls == 0 for item in first.results)
    assert first.reconciled_ledger == authoritative
    assert first.authoritative_ledger_equivalent
    assert first.complete_role_coverage
    assert not first.human_review_required
    assert not first.authoritative_output_applied
    assert resumed == first
    assert len(worker.calls) == calls_after_first
    checkpoint = repository.get_argument_workflow(investigation_id)
    assert checkpoint is not None
    assert checkpoint.stage is ArgumentWorkflowStage.RECONCILED


def test_out_of_packet_role_output_fails_closed_and_escalates_review(
    tmp_path,
) -> None:
    repository = SQLiteResearchRepository(tmp_path / "out-of-packet.db")
    claim, evidence = _packet()
    report = asyncio.run(
        LangGraphAdversarialArgumentWorkflow(
            repository=repository,
            worker=OutOfPacketWorker(),
        ).start_or_resume(
            investigation_id=uuid4(),
            claim=claim,
            approved_evidence=evidence,
            authoritative_ledger=build_argument_ledger(
                claim=claim,
                evidence=evidence,
            ),
        )
    )

    assert all(item.failure_reason for item in report.results)
    assert report.human_review_required
    assert not report.complete_role_coverage
    assert report.reconciled_ledger.approved_evidence_ids == tuple(
        item.evidence_id for item in evidence
    )


def test_completed_role_is_reused_after_mid_fanout_restart(tmp_path) -> None:
    repository = SQLiteResearchRepository(tmp_path / "mid-restart.db")
    repository.initialize()
    claim, evidence = _packet()
    authoritative = build_argument_ledger(claim=claim, evidence=evidence)
    assignments = tuple(
        ArgumentAssignment(
            investigation_id=uuid4(),
            claim_id=claim.claim_id,
            role=role,
            proposition_ids=tuple(item.proposition_id for item in authoritative.propositions),
            approved_evidence_ids=tuple(item.evidence_id for item in evidence),
        )
        for role in (ArgumentRole.DEFENDER, ArgumentRole.CHALLENGER)
    )
    investigation_id = assignments[0].investigation_id
    assignments = (
        assignments[0],
        assignments[1].model_copy(update={"investigation_id": investigation_id}),
    )
    checkpoint = AdversarialArgumentCheckpoint(
        investigation_id=investigation_id,
        claim=claim,
        approved_evidence=evidence,
        propositions=authoritative.propositions,
        assignments=assignments,
        stage=ArgumentWorkflowStage.PLANNED,
        authoritative_ledger=authoritative,
    )
    repository.save_argument_workflow(checkpoint)
    completed = asyncio.run(DeterministicArgumentWorker().run(assignments[0], checkpoint))
    repository.save_argument_result(completed)
    worker = ConcurrentArgumentWorker()

    report = asyncio.run(
        LangGraphAdversarialArgumentWorkflow(
            repository=repository,
            worker=worker,
        ).start_or_resume(
            investigation_id=investigation_id,
            claim=claim,
            approved_evidence=evidence,
            authoritative_ledger=authoritative,
        )
    )

    assert worker.calls == [ArgumentRole.CHALLENGER]
    assert report.results[0] == completed
    assert report.reconciled_ledger == authoritative


def test_argument_contracts_forbid_retrieval_usage() -> None:
    claim, evidence = _packet()
    assignment = ArgumentAssignment(
        investigation_id=uuid4(),
        claim_id=claim.claim_id,
        role=ArgumentRole.DEFENDER,
        proposition_ids=(uuid4(),),
        approved_evidence_ids=tuple(item.evidence_id for item in evidence),
    )
    with pytest.raises(ValidationError):
        ArgumentRoleResult(
            assignment_id=assignment.assignment_id,
            claim_id=claim.claim_id,
            role=assignment.role,
            arguments=(
                PropositionArgument(
                    proposition_id=assignment.proposition_ids[0],
                    resolution=PropositionResolution.UNRESOLVED,
                ),
            ),
            search_calls=1,
        )


def _packet():
    claim = AtomicClaim(
        text="Every participant benefited from the programme.",
        checkworthiness=0.9,
    )
    return claim, (
        Evidence(
            claim_id=claim.claim_id,
            source_id=uuid4(),
            passage="The programme improved the average measured outcome.",
            stance=EvidenceStance.SUPPORTS,
            relevance_score=0.9,
        ),
        Evidence(
            claim_id=claim.claim_id,
            source_id=uuid4(),
            passage="Some participant subgroups showed no measurable benefit.",
            stance=EvidenceStance.QUALIFIES,
            relevance_score=0.9,
        ),
    )
