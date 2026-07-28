"""Runnable zero-cost development API for the Phase 7 dashboard."""

import os
from pathlib import Path

import uvicorn

from claim_polygraph_ng.api import ApiDependencies, create_app
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


def build_development_app(
    data_directory: str | Path = "data",
    *,
    orchestrator: str | None = None,
):
    """Wire the API to deterministic providers and local SQLite databases."""
    root = Path(data_directory)
    root.mkdir(parents=True, exist_ok=True)
    repository = SQLiteInvestigationRepository(root / "investigations.db")
    service = InvestigationService(
        repository=repository,
        model_provider=DeterministicModelProvider(),
        search_provider=DeterministicSearchProvider(),
    )
    reviews = SQLiteReviewLedger(root / "reviews.db")
    checkpoint_path = root / "langgraph-checkpoints.db"
    selected = (
        orchestrator or os.getenv("CLAIM_POLYGRAPH_ORCHESTRATOR", "langgraph")
    ).strip().casefold()
    if selected == "langgraph":
        investigate = LangGraphInvestigationOrchestrator(
            investigate_authoritatively=service.investigate,
            checkpoint_path=checkpoint_path,
            reviews=reviews,
        ).investigate
    elif selected == "direct":
        investigate = service.investigate
    else:
        raise ValueError("CLAIM_POLYGRAPH_ORCHESTRATOR must be 'langgraph' or 'direct'")
    return create_app(
        ApiDependencies(
            investigations=repository,
            reviews=reviews,
            graph_checkpoint_path=checkpoint_path,
            investigate=investigate,
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
