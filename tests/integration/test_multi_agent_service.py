import asyncio
from uuid import uuid4

import pytest

from claim_polygraph_ng.application import (
    MultiAgentInvestigationService,
    SharedResearchOperations,
)
from claim_polygraph_ng.domain import (
    AtomicClaim,
    ClaimType,
    ResearchRequirement,
    ResearchRequirementKind,
    ResearchRole,
    SufficiencyDecision,
    SupportLevel,
    VerdictLabel,
)
from claim_polygraph_ng.persistence import SQLiteResearchRepository
from claim_polygraph_ng.providers import DeterministicSearchProvider
from claim_polygraph_ng.reporting import render_multi_agent_markdown


class UnusedFetcher:
    provider_id = "unused-fetcher"

    def __init__(self) -> None:
        self.calls = 0

    async def fetch(self, url):
        self.calls += 1
        raise AssertionError("deterministic inline results must not be fetched")


class CountingSearchProvider(DeterministicSearchProvider):
    def __init__(self) -> None:
        self.calls = 0

    async def search(self, request):
        self.calls += 1
        return await super().search(request)


class EmptySearchProvider:
    provider_id = "empty-search"

    async def search(self, request):
        return ()


def test_minimum_multi_agent_workflow_is_grounded_and_sufficient(tmp_path) -> None:
    repository, service, search, fetcher = _service(tmp_path)
    claim = _claim()

    report = asyncio.run(service.investigate(claim, _requirements(claim.claim_id)))

    assert tuple(item.role for item in report.assignments) == (
        ResearchRole.PRIMARY_SOURCE,
        ResearchRole.GENERAL_EVIDENCE,
        ResearchRole.CHALLENGER,
    )
    assert report.assessment.decision is SufficiencyDecision.SUFFICIENT
    assert report.verdict.label is VerdictLabel.MIXED
    assert report.audit.support_level is SupportLevel.FULL
    stored_ids = {item.evidence_id for item in report.consolidation.evidence}
    assert set(report.verdict.decisive_evidence_ids) <= stored_ids
    assert set(report.audit.cited_evidence_ids) <= stored_ids
    assert search.calls == 3
    assert fetcher.calls == 0
    assert repository.get_workflow(report.investigation_id) is not None
    rendered = render_multi_agent_markdown(report)
    assert "Roles activated" in rendered
    assert "Stopping decision:** sufficient" in rendered
    assert "Citation support:** full" in rendered


def test_completed_multi_agent_workflow_resumes_without_provider_calls(tmp_path) -> None:
    _, service, search, _ = _service(tmp_path)
    claim = _claim()
    first = asyncio.run(service.investigate(claim, _requirements(claim.claim_id)))
    calls_before = search.calls

    resumed = asyncio.run(service.resume(first.investigation_id))

    assert resumed == first
    assert search.calls == calls_before


def test_empty_research_packet_fails_closed_with_visible_audit(tmp_path) -> None:
    repository = SQLiteResearchRepository(tmp_path / "empty.sqlite3")
    operations = SharedResearchOperations(
        repository=repository,
        search_provider=EmptySearchProvider(),
        fetcher=UnusedFetcher(),
    )
    service = MultiAgentInvestigationService(repository=repository, operations=operations)
    claim = _claim()

    report = asyncio.run(service.investigate(claim, _requirements(claim.claim_id)))

    assert report.assessment.decision is SufficiencyDecision.STOP_DIMINISHING_RETURN
    assert report.verdict.label is VerdictLabel.UNVERIFIABLE
    assert report.verdict.human_review_required
    assert report.audit.support_level is SupportLevel.NONE
    assert report.audit.cited_evidence_ids == ()


def test_unknown_workflow_cannot_be_resumed(tmp_path) -> None:
    _, service, _, _ = _service(tmp_path)

    with pytest.raises(ValueError, match="not found"):
        asyncio.run(service.resume(uuid4()))


def _service(tmp_path):
    repository = SQLiteResearchRepository(tmp_path / "multi.sqlite3")
    search = CountingSearchProvider()
    fetcher = UnusedFetcher()
    operations = SharedResearchOperations(
        repository=repository,
        search_provider=search,
        fetcher=fetcher,
    )
    service = MultiAgentInvestigationService(repository=repository, operations=operations)
    return repository, service, search, fetcher


def _claim() -> AtomicClaim:
    return AtomicClaim(
        text="The programme improved outcomes for every participant.",
        claim_type=ClaimType.FACTUAL,
        retained_context=("The universal wording is material.",),
        checkworthiness=0.9,
    )


def _requirements(component_id):
    return (
        ResearchRequirement(
            component_id=component_id,
            kind=ResearchRequirementKind.COMPONENT_COVERAGE,
            rationale="The material component requires relevant evidence.",
        ),
        ResearchRequirement(
            component_id=component_id,
            kind=ResearchRequirementKind.PRIMARY_SOURCE,
            rationale="The material component requires a suitable primary source.",
        ),
        ResearchRequirement(
            component_id=component_id,
            kind=ResearchRequirementKind.INDEPENDENT_CORROBORATION,
            minimum_independent_families=2,
            rationale="The material component requires independent corroboration.",
        ),
        ResearchRequirement(
            component_id=component_id,
            kind=ResearchRequirementKind.CONTRADICTION_OR_QUALIFICATION,
            rationale="The universal wording requires a challenger evidence path.",
        ),
    )
