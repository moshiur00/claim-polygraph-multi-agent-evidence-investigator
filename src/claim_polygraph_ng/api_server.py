"""Runnable local API with explicit deterministic or live retrieval."""

import os
from pathlib import Path

import uvicorn

from claim_polygraph_ng.api import ApiDependencies, create_app
from claim_polygraph_ng.application import (
    AuthoritativeMultiAgentResearchAdapter,
    AuthoritativeVerificationFanOutWorkflow,
    ClaimExtractionService,
    DeterministicResearchWorker,
    DirectInvestigationOrchestrator,
    ExperimentalMultiAgentInvestigationOrchestrator,
    InvestigationService,
    LangGraphAdversarialArgumentWorkflow,
    LangGraphInvestigationOrchestrator,
    LangGraphResearchFanOutWorkflow,
    MultiAgentInvestigationService,
    SharedResearchOperations,
    parse_orchestrator_mode,
)
from claim_polygraph_ng.application.langgraph_authoritative import (
    AuthoritativeFixtureLangGraphWorkflow,
)
from claim_polygraph_ng.domain.jobs import JobAdmissionPolicy
from claim_polygraph_ng.domain.telemetry import MetricName
from claim_polygraph_ng.persistence import (
    SQLiteInvestigationRepository,
    SQLiteResearchRepository,
    SQLiteReviewLedger,
)
from claim_polygraph_ng.persistence.jobs import SQLiteJobQueue
from claim_polygraph_ng.persistence.paid_operations import SQLitePaidOperationLedger
from claim_polygraph_ng.providers import (
    DeterministicModelProvider,
    DeterministicSearchProvider,
    OpenAIStructuredModelProvider,
    SearXNGSearchProvider,
    SerpAPISearchProvider,
)
from claim_polygraph_ng.retrieval import FetchedDocument, SafeHttpFetcher, UrlSafetyPolicy
from claim_polygraph_ng.telemetry import TelemetryCollector


class _InlineOnlyFetcher:
    """Fail closed if a deterministic development search result lacks inline text."""

    provider_id = "inline-only"

    async def fetch(self, url: str) -> FetchedDocument:
        raise RuntimeError(f"deterministic development result requires inline content: {url}")


def _configured_search():
    """Select retrieval explicitly; never silently fall back from a live mode."""
    mode = os.getenv("CLAIM_POLYGRAPH_SEARCH_PROVIDER", "deterministic").strip().casefold()
    if mode == "deterministic":
        return DeterministicSearchProvider(), _InlineOnlyFetcher(), False
    if mode == "searxng":
        base_url = os.getenv("SEARXNG_BASE_URL", "http://searxng:8080")
        engines = tuple(
            value.strip()
            for value in os.getenv("SEARXNG_ENGINES", "").split(",")
            if value.strip()
        )
        return (
            SearXNGSearchProvider(base_url, engines=engines),
            SafeHttpFetcher(policy=UrlSafetyPolicy()),
            True,
        )
    if mode == "serpapi":
        api_key = os.getenv("SERPAPI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "CLAIM_POLYGRAPH_SEARCH_PROVIDER=serpapi requires SERPAPI_API_KEY"
            )
        return (
            SerpAPISearchProvider(
                api_key=api_key,
                engine=os.getenv("SERPAPI_ENGINE", "google"),
                language=os.getenv("SERPAPI_LANGUAGE", "en"),
                country=os.getenv("SERPAPI_COUNTRY", "us"),
                timeout_seconds=float(os.getenv("SERPAPI_TIMEOUT_SECONDS", "15")),
            ),
            SafeHttpFetcher(policy=UrlSafetyPolicy()),
            True,
        )
    raise RuntimeError(
        "CLAIM_POLYGRAPH_SEARCH_PROVIDER must be deterministic, searxng, or serpapi"
    )


def _configured_model():
    mode = os.getenv("CLAIM_POLYGRAPH_MODEL_PROVIDER", "deterministic").strip().casefold()
    if mode == "deterministic":
        return DeterministicModelProvider()
    if mode == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "CLAIM_POLYGRAPH_MODEL_PROVIDER=openai requires OPENAI_API_KEY"
            )
        return OpenAIStructuredModelProvider(
            api_key=api_key,
            model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
            fast_model=os.getenv("OPENAI_FAST_MODEL", "gpt-4o-mini"),
            timeout_seconds=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "60")),
        )
    raise RuntimeError("CLAIM_POLYGRAPH_MODEL_PROVIDER must be deterministic or openai")


def build_development_app(
    data_directory: str | Path = "data",
    *,
    orchestrator: str | None = None,
):
    """Wire the API to deterministic providers and local SQLite databases."""
    root = Path(data_directory)
    root.mkdir(parents=True, exist_ok=True)
    search_provider, content_fetcher, live_research = _configured_search()
    model_provider = _configured_model()
    telemetry = TelemetryCollector(root / "telemetry.db")
    repository = SQLiteInvestigationRepository(root / "investigations.db")
    service = InvestigationService(
        repository=repository,
        model_provider=model_provider,
        search_provider=search_provider,
        content_fetcher=content_fetcher if live_research else None,
    )
    reviews = SQLiteReviewLedger(root / "reviews.db")
    checkpoint_path = root / "langgraph-checkpoints.db"
    job_queue = SQLiteJobQueue(
        root / "jobs.db",
        JobAdmissionPolicy(
            maximum_queue_depth=50,
            maximum_active_jobs=1,
            default_provider_limit=1,
        ),
    )
    research_repository = SQLiteResearchRepository(root / "research.db")
    shared_research = SharedResearchOperations(
        repository=research_repository,
        search_provider=search_provider,
        fetcher=content_fetcher,
        telemetry=telemetry,
    )
    authoritative_workflow = AuthoritativeFixtureLangGraphWorkflow(
        service=service,
        investigations=repository,
        langgraph_checkpoint_path=root / "authoritative-langgraph.db",
        state_checkpoint_path=root / "authoritative-state.db",
        research_adapter=AuthoritativeMultiAgentResearchAdapter(
            workflow=LangGraphResearchFanOutWorkflow(
                repository=research_repository,
                operations=shared_research,
                worker=DeterministicResearchWorker(research_repository),
                telemetry=telemetry,
            ),
            paid_capable=live_research,
            paid_operation_ledger=SQLitePaidOperationLedger(root / "paid-operations.db"),
        ),
        verification_workflow=AuthoritativeVerificationFanOutWorkflow(),
        argument_workflow=LangGraphAdversarialArgumentWorkflow(
            repository=research_repository
        ),
        review_ledger=reviews,
    )

    async def investigate_authoritatively(claim: str):
        try:
            return await service.investigate(claim)
        finally:
            for usage in service.model_usage:
                telemetry.metric(
                    MetricName.MODEL_TOKENS,
                    usage.input_tokens + usage.output_tokens,
                    "tokens",
                    attributes={"provider.id": model_provider.provider_id, "model": usage.model},
                )
                if usage.estimated_cost_usd is not None:
                    telemetry.metric(
                        MetricName.MODEL_COST_USD,
                        usage.estimated_cost_usd,
                        "usd",
                        attributes={
                            "provider.id": model_provider.provider_id,
                            "model": usage.model,
                        },
                    )
    selected = parse_orchestrator_mode(
        orchestrator or os.getenv("CLAIM_POLYGRAPH_ORCHESTRATOR", "langgraph")
    )
    if selected.value == "langgraph":
        selected_orchestrator = LangGraphInvestigationOrchestrator(
            investigate_authoritatively=investigate_authoritatively,
            checkpoint_path=checkpoint_path,
            reviews=reviews,
            argument_workflow=LangGraphAdversarialArgumentWorkflow(
                repository=research_repository,
            ),
            research_fan_out=LangGraphResearchFanOutWorkflow(
                repository=research_repository,
                operations=shared_research,
                worker=DeterministicResearchWorker(research_repository),
                telemetry=telemetry,
            ),
            telemetry=telemetry,
        )
    elif selected.value == "direct":
        selected_orchestrator = DirectInvestigationOrchestrator(investigate_authoritatively)
    else:
        durable_authoritative = LangGraphInvestigationOrchestrator(
            investigate_authoritatively=investigate_authoritatively,
            checkpoint_path=checkpoint_path,
            reviews=reviews,
            telemetry=telemetry,
        )
        selected_orchestrator = ExperimentalMultiAgentInvestigationOrchestrator(
            investigate_authoritatively=durable_authoritative.investigate,
            multi_agent_service=MultiAgentInvestigationService(
                repository=research_repository,
                operations=shared_research,
            ),
        )
    return create_app(
        ApiDependencies(
            investigations=repository,
            reviews=reviews,
            graph_checkpoint_path=checkpoint_path,
            investigate=selected_orchestrator.investigate,
            orchestrator_mode=selected_orchestrator.mode,
            extract_claims=ClaimExtractionService(
                SafeHttpFetcher(policy=UrlSafetyPolicy()).fetch
            ).extract,
            telemetry=telemetry,
            retrieval_provider=search_provider.provider_id,
            live_research=live_research,
            model_provider=model_provider.provider_id,
            job_queue=job_queue,
            authoritative_workflow=authoritative_workflow,
        )
    )


def create_development_app():
    """ASGI factory used by Uvicorn without import-time filesystem writes."""
    return build_development_app(os.getenv("CLAIM_POLYGRAPH_DATA_DIR", "data"))


def main() -> None:
    """Run the local development API; production deployment supplies its own ASGI wiring."""
    uvicorn.run(
        "claim_polygraph_ng.api_server:create_development_app",
        host=os.getenv("CLAIM_POLYGRAPH_API_HOST", "127.0.0.1"),
        port=int(os.getenv("CLAIM_POLYGRAPH_API_PORT", "8000")),
        factory=True,
        reload=False,
    )
