"""Promoted orchestration boundary around the authoritative investigation service."""

from collections.abc import Awaitable, Callable
from pathlib import Path
from uuid import UUID

from claim_polygraph_ng.application.langgraph_durable import (
    DurableFixtureLangGraphWorkflow,
    ExistingGraphThreadError,
)
from claim_polygraph_ng.domain.graph import FixtureGraphRequest
from claim_polygraph_ng.domain.investigation import InvestigationReport
from claim_polygraph_ng.domain.review import ReviewRequest
from claim_polygraph_ng.persistence.review import SQLiteReviewLedger


class LangGraphInvestigationOrchestrator:
    """Run authoritative investigation work, then durably orchestrate its disposition."""

    def __init__(
        self,
        *,
        investigate_authoritatively: Callable[[str], Awaitable[InvestigationReport]],
        checkpoint_path: str | Path,
        reviews: SQLiteReviewLedger,
        review_created_by: str = "langgraph-review-router",
    ) -> None:
        self._investigate_authoritatively = investigate_authoritatively
        self._checkpoint_path = Path(checkpoint_path)
        self._reviews = reviews
        self._review_created_by = review_created_by
        self._reviews.initialize()

    async def investigate(self, claim: str) -> InvestigationReport:
        """Preserve the authoritative report while making LangGraph the default journey."""
        report = await self._investigate_authoritatively(claim)
        investigation_id = report.investigation.investigation_id
        request = FixtureGraphRequest(
            graph_run_id=investigation_id,
            claim_text=report.claim.text,
            approved_evidence_ids=tuple(item.evidence_id for item in report.evidence),
            authoritative_verdict=report.verdict.label,
            review_required=report.verdict.human_review_required,
            review_reason=report.verdict.review_reason,
        )
        with DurableFixtureLangGraphWorkflow(self._checkpoint_path, enabled=True) as workflow:
            try:
                snapshot = workflow.start(request)
            except ExistingGraphThreadError:
                snapshot = workflow.snapshot(str(investigation_id))
        if snapshot.interrupt is not None and not self._review_exists(investigation_id):
            self._reviews.create_request(
                ReviewRequest(
                    investigation_id=investigation_id,
                    graph_thread_id=str(investigation_id),
                    claim_id=report.claim.claim_id,
                    reason=snapshot.interrupt.route_reason,
                    created_by=self._review_created_by,
                )
            )
        return report

    def _review_exists(self, investigation_id: UUID) -> bool:
        return any(
            item.investigation_id == investigation_id
            for item in self._reviews.list_requests()
        )
