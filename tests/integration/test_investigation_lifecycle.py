"""End-to-end tests for the first executable investigation lifecycle."""

import asyncio

import pytest

from claim_polygraph_ng.application import BudgetExceededError, InvestigationService
from claim_polygraph_ng.config import ExecutionBudget, RuntimePolicy
from claim_polygraph_ng.domain import (
    ArtifactType,
    AtomicClaim,
    Evidence,
    InvestigationPlan,
    InvestigationStage,
    InvestigationStatus,
    SentenceAudit,
    Source,
    TraceEventType,
    Verdict,
    VerdictLabel,
)
from claim_polygraph_ng.persistence import SQLiteInvestigationRepository
from claim_polygraph_ng.providers import (
    DeterministicModelProvider,
    DeterministicSearchProvider,
)
from claim_polygraph_ng.retrieval import DocumentChunk


def test_complete_investigation_is_persisted_and_reloadable(tmp_path) -> None:
    repository = SQLiteInvestigationRepository(tmp_path / "investigations.sqlite3")
    service = InvestigationService(
        repository=repository,
        model_provider=DeterministicModelProvider(),
        search_provider=DeterministicSearchProvider(),
    )

    report = asyncio.run(
        service.investigate("The example policy reduced emissions by ten percent.")
    )
    investigation_id = report.investigation.investigation_id

    stored_investigation = repository.get_investigation(investigation_id)
    assert stored_investigation is not None
    assert stored_investigation.status is InvestigationStatus.COMPLETED
    assert stored_investigation.stage is InvestigationStage.COMPLETE

    assert repository.list_artifacts(investigation_id, ArtifactType.CLAIM, AtomicClaim) == (
        report.claim,
    )
    assert repository.list_artifacts(investigation_id, ArtifactType.PLAN, InvestigationPlan) == (
        report.plan,
    )
    assert (
        repository.list_artifacts(investigation_id, ArtifactType.SOURCE, Source) == report.sources
    )
    chunks = repository.list_artifacts(
        investigation_id,
        ArtifactType.CHUNK,
        DocumentChunk,
    )
    assert len(chunks) == 3
    assert (
        repository.list_artifacts(investigation_id, ArtifactType.EVIDENCE, Evidence)
        == report.evidence
    )
    assert repository.list_artifacts(investigation_id, ArtifactType.VERDICT, Verdict) == (
        report.verdict,
    )
    assert (
        repository.list_artifacts(investigation_id, ArtifactType.AUDIT, SentenceAudit)
        == report.audits
    )

    assert len(report.sources) == 3
    assert len(report.evidence) == 3
    assert all(item.chunk_id is not None for item in report.evidence)
    assert report.verdict.label is VerdictLabel.MIXED
    assert report.audits[0].cited_evidence_ids

    events = repository.list_events(investigation_id)
    assert events[0].event_type is TraceEventType.INVESTIGATION_CREATED
    assert events[-1].event_type is TraceEventType.INVESTIGATION_COMPLETED
    assert any(event.event_type is TraceEventType.PROVIDER_CALLED for event in events)


def test_budget_failure_is_persisted_and_traced(tmp_path) -> None:
    repository = SQLiteInvestigationRepository(tmp_path / "budget-failure.sqlite3")
    service = InvestigationService(
        repository=repository,
        model_provider=DeterministicModelProvider(),
        search_provider=DeterministicSearchProvider(),
        runtime_policy=RuntimePolicy(
            budget=ExecutionBudget(maximum_llm_calls=1),
        ),
    )

    with pytest.raises(BudgetExceededError, match="maximum LLM calls"):
        asyncio.run(service.investigate("A claim that exceeds its model-call budget."))

    investigations = repository.list_investigations()
    assert len(investigations) == 1
    stored = investigations[0]
    assert stored.status is InvestigationStatus.FAILED
    assert stored.stage is InvestigationStage.FAILED
    assert "maximum LLM calls exceeded" in stored.failure_reason

    events = repository.list_events(stored.investigation_id)
    assert events[-1].event_type is TraceEventType.INVESTIGATION_FAILED
