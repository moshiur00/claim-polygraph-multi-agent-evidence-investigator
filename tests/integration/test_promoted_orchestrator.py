"""Promotion and rollback tests for the default API orchestration boundary."""

import asyncio

import httpx

from claim_polygraph_ng.api_server import build_development_app
from claim_polygraph_ng.application import (
    DirectInvestigationOrchestrator,
    ExperimentalMultiAgentInvestigationOrchestrator,
    InvestigationOrchestrator,
    InvestigationService,
    LangGraphInvestigationOrchestrator,
    OrchestratorMode,
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


async def _request(app, method: str, url: str, **kwargs):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        return await client.request(method, url, **kwargs)


def test_api_modes_are_declared_and_graph_modes_checkpoint_automatically(tmp_path) -> None:
    for mode in (
        OrchestratorMode.LANGGRAPH,
        OrchestratorMode.DIRECT,
        OrchestratorMode.MULTI_AGENT_EXPERIMENTAL,
    ):
        app = build_development_app(tmp_path / mode.value, orchestrator=mode.value)
        health = asyncio.run(_request(app, "GET", "/health"))
        created = asyncio.run(
            _request(
                app,
                "POST",
                "/api/investigations",
                json={"claim": f"A factual claim for {mode.value}."},
            )
        )

        assert health.json()["orchestrator"] == mode.value
        assert created.status_code == 201
        assert created.headers["x-claim-polygraph-orchestrator"] == mode.value
        investigation_id = created.json()["investigation"]["investigation_id"]
        graph = asyncio.run(_request(app, "GET", f"/api/graph-runs/{investigation_id}"))
        assert graph.status_code == (404 if mode is OrchestratorMode.DIRECT else 200)
        if mode is not OrchestratorMode.DIRECT:
            research_state = graph.json()["research_state"]
            assert research_state["investigation_id"] == investigation_id
            assert research_state["components"]
            assert research_state["requirements"]
            assert research_state["consumption"]["model_calls"] == 0
            if mode is OrchestratorMode.LANGGRAPH:
                assert len(research_state["assignments"]) == 3
                assert len(research_state["results"]) == 3
                assert research_state["consumption"]["role_activations"] == 3
                approved = set(research_state["approved_evidence_ids"])
                authoritative = {
                    item["evidence_id"] for item in created.json()["evidence"]
                }
                assert approved == authoritative
                assert approved < set(research_state["stored_evidence_ids"])


def test_langgraph_replay_does_not_duplicate_review_or_graph_work(tmp_path) -> None:
    repository = SQLiteInvestigationRepository(tmp_path / "idempotent-authority.db")
    service = InvestigationService(
        repository=repository,
        model_provider=DeterministicModelProvider(),
        search_provider=DeterministicSearchProvider(),
    )
    authoritative = asyncio.run(service.investigate("A stable authoritative claim."))

    async def fixed_report(_claim: str):
        return authoritative

    reviews = SQLiteReviewLedger(tmp_path / "idempotent-reviews.db")
    orchestrator = LangGraphInvestigationOrchestrator(
        investigate_authoritatively=fixed_report,
        checkpoint_path=tmp_path / "idempotent-graph.db",
        reviews=reviews,
    )
    first = asyncio.run(orchestrator.investigate(authoritative.claim.text))
    second = asyncio.run(orchestrator.investigate(authoritative.claim.text))

    assert first == second == authoritative
    assert len(reviews.list_requests()) == int(authoritative.verdict.human_review_required)


def test_all_modes_satisfy_one_contract_and_preserve_authority(tmp_path) -> None:
    repository = SQLiteInvestigationRepository(tmp_path / "authority.db")
    service = InvestigationService(
        repository=repository,
        model_provider=DeterministicModelProvider(),
        search_provider=DeterministicSearchProvider(),
    )
    direct = DirectInvestigationOrchestrator(service.investigate)
    langgraph = LangGraphInvestigationOrchestrator(
        investigate_authoritatively=service.investigate,
        checkpoint_path=tmp_path / "contract-graph.db",
        reviews=SQLiteReviewLedger(tmp_path / "contract-reviews.db"),
    )

    class ExperimentalService:
        def __init__(self) -> None:
            self.called = False

        async def investigate(self, claim, requirements, *, budget):
            self.called = True
            return {"claim_id": claim.claim_id, "requirements": requirements, "budget": budget}

    experimental_service = ExperimentalService()
    recorded = []
    experimental = ExperimentalMultiAgentInvestigationOrchestrator(
        investigate_authoritatively=service.investigate,
        multi_agent_service=experimental_service,  # type: ignore[arg-type]
        record_result=lambda report, result: recorded.append((report, result)),
    )

    assert isinstance(direct, InvestigationOrchestrator)
    assert isinstance(langgraph, InvestigationOrchestrator)
    assert isinstance(experimental, InvestigationOrchestrator)
    assert direct.mode is OrchestratorMode.DIRECT
    assert langgraph.mode is OrchestratorMode.LANGGRAPH
    assert experimental.mode is OrchestratorMode.MULTI_AGENT_EXPERIMENTAL

    direct_report = asyncio.run(direct.investigate("A direct factual claim."))
    graph_report = asyncio.run(langgraph.investigate("A graph factual claim."))
    experimental_report = asyncio.run(
        experimental.investigate("An experimental factual claim.")
    )

    assert direct_report.verdict.label == graph_report.verdict.label
    assert graph_report.verdict.label == experimental_report.verdict.label
    assert experimental_service.called
    assert recorded[0][0] is experimental_report
