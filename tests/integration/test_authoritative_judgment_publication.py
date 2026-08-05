"""Stage 9.8 authoritative judgment and publication integration."""

import asyncio

import pytest

from claim_polygraph_ng.analysis import assure_full_report
from claim_polygraph_ng.application import InvestigationService
from claim_polygraph_ng.application.langgraph_authoritative import (
    AuthoritativeFixtureLangGraphWorkflow,
)
from claim_polygraph_ng.domain import (
    AuthoritativePublicationDecision,
    PublicationGateStatus,
    ReviewDecisionKind,
    Verdict,
    VerdictLabel,
)
from claim_polygraph_ng.domain.investigation import ArtifactType
from claim_polygraph_ng.persistence import SQLiteInvestigationRepository
from claim_polygraph_ng.providers import (
    DeterministicModelProvider,
    DeterministicSearchProvider,
)
from claim_polygraph_ng.reporting import (
    PublicationBlockedError,
    load_report,
    render_publishable_markdown,
)


def test_authoritative_graph_persists_auditable_judgment_publication_chain(
    tmp_path,
) -> None:
    repository = SQLiteInvestigationRepository(tmp_path / "investigations.db")
    with AuthoritativeFixtureLangGraphWorkflow(
        service=InvestigationService(
            repository=repository,
            model_provider=DeterministicModelProvider(),
            search_provider=DeterministicSearchProvider(),
        ),
        investigations=repository,
        langgraph_checkpoint_path=tmp_path / "langgraph.db",
        state_checkpoint_path=tmp_path / "state.db",
    ) as workflow:
        result = asyncio.run(workflow.start("The fixture programme reduced waste."))

    state = result.state
    assert state.proposed_verdict_ref is not None
    assert state.proposed_verdict_ref.artifact_type is ArtifactType.PROPOSED_VERDICT
    assert state.enforced_verdict_ref is not None
    assert state.enforced_verdict_ref.artifact_type is ArtifactType.VERDICT
    assert state.citation_assurance_ref is not None
    assert state.readiness_ref is not None
    assert state.publication_decision_ref is not None
    assert (
        state.publication_decision_ref.artifact_type
        is ArtifactType.PUBLICATION_DECISION
    )
    decision = _one(
        repository,
        state.investigation_id,
        ArtifactType.PUBLICATION_DECISION,
        AuthoritativePublicationDecision,
    )
    assert result.report.publication_decision == decision
    assert decision.citation_revision_count <= 2 * len(
        result.report.full_report_assurance.original_assertions
    )
    assert decision.publication_allowed
    assert not state.publication_blocked
    assert render_publishable_markdown(result.report, ())


def test_unsupported_critical_assertion_blocks_graph_publication(tmp_path) -> None:
    class BlockedCitationService(InvestigationService):
        async def audit_citations(self, investigation, claim, verdict, evidence):
            investigation, _verdict, audit, _assurance = await super().audit_citations(
                investigation, claim, verdict, evidence
            )
            blocked_verdict = Verdict(
                claim_id=claim.claim_id,
                label=VerdictLabel.UNVERIFIABLE,
                concise_explanation=(
                    "The available material cannot verify the submitted claim."
                ),
                detailed_reasoning=(
                    "No approved evidence establishes the material assertion."
                ),
                human_review_required=True,
                review_reason="Unsupported critical assertions require review.",
            )
            assurance = assure_full_report(
                claim_id=claim.claim_id,
                verdict=blocked_verdict,
                evidence=evidence,
                approved_evidence_ids=tuple(item.evidence_id for item in evidence),
            )
            self._save_artifact(
                investigation,
                ArtifactType.VERDICT,
                blocked_verdict.verdict_id,
                blocked_verdict,
            )
            self._save_artifact(
                investigation,
                ArtifactType.FULL_REPORT_ASSURANCE,
                claim.claim_id,
                assurance,
            )
            return investigation, blocked_verdict, audit, assurance

    repository = SQLiteInvestigationRepository(tmp_path / "blocked.db")
    with AuthoritativeFixtureLangGraphWorkflow(
        service=BlockedCitationService(
            repository=repository,
            model_provider=DeterministicModelProvider(),
            search_provider=DeterministicSearchProvider(),
        ),
        investigations=repository,
        langgraph_checkpoint_path=tmp_path / "blocked-langgraph.db",
        state_checkpoint_path=tmp_path / "blocked-state.db",
    ) as workflow:
        result = asyncio.run(workflow.start("The fixture programme reduced waste."))

    report = load_report(
        repository,
        result.state.investigation_id,
        require_completed=False,
    )
    decision = report.publication_decision
    assert decision is not None
    assert not decision.publication_allowed
    assert decision.unsupported_critical_assertion_count > 0
    assert report.full_report_assurance.publication_status is (
        PublicationGateStatus.BLOCKED
    )
    assert result.interrupt is not None
    assert ReviewDecisionKind.APPROVE not in result.interrupt.allowed_decisions
    assert result.interrupt.allowed_decisions[0] is ReviewDecisionKind.REQUEST_EVIDENCE
    assert result.state.publication_blocked
    assert result.state.publication_blocking_reasons
    with pytest.raises(PublicationBlockedError):
        render_publishable_markdown(report, ())


def test_direct_rollback_also_emits_and_enforces_publication_decision(
    tmp_path,
) -> None:
    repository = SQLiteInvestigationRepository(tmp_path / "direct.db")
    report = asyncio.run(
        InvestigationService(
            repository=repository,
            model_provider=DeterministicModelProvider(),
            search_provider=DeterministicSearchProvider(),
        ).investigate("The fixture programme reduced waste.")
    )
    assert report.publication_decision is not None
    stored = _one(
        repository,
        report.investigation.investigation_id,
        ArtifactType.PUBLICATION_DECISION,
        AuthoritativePublicationDecision,
    )
    assert report.publication_decision == stored
    assert report.publication_decision.publication_allowed


def _one(repository, investigation_id, artifact_type, model):
    values = repository.list_artifacts(
        investigation_id, artifact_type, model
    )
    assert len(values) == 1
    return values[0]
