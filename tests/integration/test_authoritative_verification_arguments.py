"""Stage 9.7 authoritative verification and argument integration."""

import asyncio

import pytest

from claim_polygraph_ng.analysis import (
    bridge_legacy_verification,
    build_argument_ledger,
    verify_claim_context,
)
from claim_polygraph_ng.analysis.investigation_provenance import (
    build_investigation_provenance,
)
from claim_polygraph_ng.application import InvestigationService
from claim_polygraph_ng.application.langgraph_argument import (
    LangGraphAdversarialArgumentWorkflow,
)
from claim_polygraph_ng.application.langgraph_authoritative import (
    AuthoritativeFixtureLangGraphWorkflow,
)
from claim_polygraph_ng.application.langgraph_verification import (
    AuthoritativeVerificationFanOutWorkflow,
)
from claim_polygraph_ng.domain import (
    ArgumentLedger,
    AtomicClaim,
    ContextVerification,
    Evidence,
    InvestigationPlan,
    InvestigationProvenance,
    ReviewDecisionKind,
    Source,
    VerificationPacketV2,
)
from claim_polygraph_ng.domain.authoritative_analysis import EvidenceCoverageCheck
from claim_polygraph_ng.domain.investigation import ArtifactType
from claim_polygraph_ng.persistence import (
    SQLiteInvestigationRepository,
    SQLiteResearchRepository,
)
from claim_polygraph_ng.providers import (
    DeterministicModelProvider,
    DeterministicSearchProvider,
)


class _EmptySearchProvider(DeterministicSearchProvider):
    async def search(self, request):
        del request
        return ()


def test_verification_and_arguments_fan_out_inside_authoritative_graph(
    tmp_path,
) -> None:
    investigations = SQLiteInvestigationRepository(tmp_path / "investigations.db")
    argument_repository = SQLiteResearchRepository(tmp_path / "arguments.db")
    verification_workflow = AuthoritativeVerificationFanOutWorkflow()
    argument_workflow = LangGraphAdversarialArgumentWorkflow(
        repository=argument_repository
    )
    service = InvestigationService(
        repository=investigations,
        model_provider=DeterministicModelProvider(),
        search_provider=DeterministicSearchProvider(),
    )
    with AuthoritativeFixtureLangGraphWorkflow(
        service=service,
        investigations=investigations,
        langgraph_checkpoint_path=tmp_path / "langgraph.db",
        state_checkpoint_path=tmp_path / "state.db",
        verification_workflow=verification_workflow,
        argument_workflow=argument_workflow,
    ) as workflow:
        result = asyncio.run(
            workflow.run_to_completion(
                "The fixture programme reduced waste for every participant."
            )
        )

    investigation_id = result.state.investigation_id
    claim = _one(investigations, investigation_id, ArtifactType.CLAIM, AtomicClaim)
    plan = _one(investigations, investigation_id, ArtifactType.PLAN, InvestigationPlan)
    sources = _many(investigations, investigation_id, ArtifactType.SOURCE, Source)
    evidence = _many(investigations, investigation_id, ArtifactType.EVIDENCE, Evidence)
    context = _one(
        investigations,
        investigation_id,
        ArtifactType.CONTEXT_VERIFICATION,
        ContextVerification,
    )
    verification = _one(
        investigations,
        investigation_id,
        ArtifactType.VERIFICATION_PACKET,
        VerificationPacketV2,
    )
    provenance = _one(
        investigations,
        investigation_id,
        ArtifactType.PROVENANCE,
        InvestigationProvenance,
    )
    coverage = _one(
        investigations,
        investigation_id,
        ArtifactType.COVERAGE,
        EvidenceCoverageCheck,
    )
    ledger = _one(
        investigations,
        investigation_id,
        ArtifactType.ARGUMENT_LEDGER,
        ArgumentLedger,
    )

    legacy_context = verify_claim_context(
        claim=claim, plan=plan, sources=sources, evidence=evidence
    )
    legacy_verification = bridge_legacy_verification(
        claim=claim,
        legacy=legacy_context,
        sources=sources,
        evidence=evidence,
    )
    legacy_provenance = build_investigation_provenance(
        plan=plan, sources=sources, evidence=evidence
    )
    legacy_ledger = build_argument_ledger(
        claim=claim,
        evidence=evidence,
        verification=legacy_verification,
        provenance=legacy_provenance,
    )

    assert verification_workflow.maximum_active_branches == 4
    assert context == legacy_context
    assert verification == legacy_verification
    assert provenance == legacy_provenance
    assert ledger == legacy_ledger
    assert coverage.approved_evidence_ids == result.state.approved_evidence_ids
    assert set(verification.approved_evidence_ids) == set(
        result.state.approved_evidence_ids
    )
    checkpoint = argument_repository.get_argument_workflow(investigation_id)
    assert checkpoint is not None
    assert len(checkpoint.assignments) == len(checkpoint.results) == 2
    assert {item.role.value for item in checkpoint.results} == {
        "defender",
        "challenger",
    }
    assert all(
        item.search_calls == item.fetch_calls == item.model_calls == 0
        for item in checkpoint.results
    )
    assert all(
        set(item.consumed_evidence_ids) <= set(result.state.approved_evidence_ids)
        for item in checkpoint.results
    )
    assert {result.state.defender_result_id, result.state.challenger_result_id} == {
        item.result_id for item in checkpoint.results
    }
    assert result.report.argument_ledger == legacy_ledger
    resumed = asyncio.run(
        argument_workflow.start_or_resume(
            investigation_id=investigation_id,
            claim=claim,
            approved_evidence=evidence,
            authoritative_ledger=ledger,
            verification=verification,
            provenance=provenance,
        )
    )
    assert resumed.results == checkpoint.results
    assert resumed.reconciled_ledger == ledger
    with pytest.raises(ValueError, match="approved evidence packet"):
        asyncio.run(
            AuthoritativeVerificationFanOutWorkflow().execute(
                investigation_id=investigation_id,
                claim=claim,
                plan=plan,
                sources=sources,
                evidence=evidence,
                approved_evidence_ids=tuple(
                    reversed(result.state.approved_evidence_ids)
                ),
            )
        )


def test_empty_approved_packet_routes_review_without_adversarial_failure(
    tmp_path,
) -> None:
    investigations = SQLiteInvestigationRepository(tmp_path / "empty-investigations.db")
    service = InvestigationService(
        repository=investigations,
        model_provider=DeterministicModelProvider(),
        search_provider=_EmptySearchProvider(),
    )
    with AuthoritativeFixtureLangGraphWorkflow(
        service=service,
        investigations=investigations,
        langgraph_checkpoint_path=tmp_path / "empty-langgraph.db",
        state_checkpoint_path=tmp_path / "empty-state.db",
        argument_workflow=LangGraphAdversarialArgumentWorkflow(
            repository=SQLiteResearchRepository(tmp_path / "empty-arguments.db")
        ),
    ) as workflow:
        pending = asyncio.run(
            workflow.start("A claim whose candidate pages could not be fetched.")
        )

    assert pending.interrupt is not None
    assert pending.state.approved_evidence_ids == ()
    assert pending.state.defender_result_id is not None
    assert pending.state.challenger_result_id is not None
    assert pending.interrupt.allowed_decisions == (
        ReviewDecisionKind.REQUEST_EVIDENCE,
        ReviewDecisionKind.REJECT,
    )


def _one(repository, investigation_id, artifact_type, model):
    values = repository.list_artifacts(investigation_id, artifact_type, model)
    assert len(values) == 1
    return values[0]


def _many(repository, investigation_id, artifact_type, model):
    return repository.list_artifacts(investigation_id, artifact_type, model)
