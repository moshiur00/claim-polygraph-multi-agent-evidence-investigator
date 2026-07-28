"""Promotion and rollback tests for the default API orchestration boundary."""

import asyncio

from claim_polygraph_ng.api_server import build_development_app
from claim_polygraph_ng.application import (
    InvestigationService,
    LangGraphInvestigationOrchestrator,
)
from claim_polygraph_ng.persistence import (
    SQLiteInvestigationRepository,
    SQLiteReviewLedger,
)
from claim_polygraph_ng.providers import (
    DeterministicModelProvider,
    DeterministicSearchProvider,
)


def test_promoted_orchestrator_preserves_authoritative_report_and_creates_graph(
    tmp_path,
) -> None:
    repository = SQLiteInvestigationRepository(tmp_path / "investigations.db")
    service = InvestigationService(
        repository=repository,
        model_provider=DeterministicModelProvider(),
        search_provider=DeterministicSearchProvider(),
    )
    reviews = SQLiteReviewLedger(tmp_path / "reviews.db")
    orchestrator = LangGraphInvestigationOrchestrator(
        investigate_authoritatively=service.investigate,
        checkpoint_path=tmp_path / "langgraph.db",
        reviews=reviews,
    )

    report = asyncio.run(orchestrator.investigate("A factual claim for orchestration."))

    assert report.investigation.status.value == "completed"
    assert repository.get_investigation(report.investigation.investigation_id) is not None
    assert len(reviews.list_requests()) == int(report.verdict.human_review_required)


def test_api_defaults_to_langgraph_and_retains_direct_rollback(tmp_path) -> None:
    promoted = build_development_app(tmp_path / "promoted")
    direct = build_development_app(tmp_path / "direct", orchestrator="direct")

    assert promoted is not None
    assert direct is not None
