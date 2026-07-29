"""Authority bridge for the genuine multi-agent research subgraph."""

from __future__ import annotations

from uuid import NAMESPACE_URL, UUID, uuid5

from claim_polygraph_ng.application.langgraph_research import (
    LangGraphResearchFanOutWorkflow,
)
from claim_polygraph_ng.domain import (
    AtomicClaim,
    MultiAgentFanOutReport,
    ResearchBudget,
    ResearchRequirement,
)
from claim_polygraph_ng.domain.graph import DurableRequirementReference
from claim_polygraph_ng.persistence.paid_operations import SQLitePaidOperationLedger


class UnguardedPaidResearchError(RuntimeError):
    """Raised before paid-capable research can run without durable receipts."""


class AuthoritativeMultiAgentResearchAdapter:
    """Run the proven map/reduce workflow under the authoritative graph boundary."""

    def __init__(
        self,
        *,
        workflow: LangGraphResearchFanOutWorkflow,
        paid_capable: bool = False,
        paid_operation_ledger: SQLitePaidOperationLedger | None = None,
    ) -> None:
        if paid_capable and paid_operation_ledger is None:
            raise UnguardedPaidResearchError(
                "paid-capable authoritative research requires a paid-operation ledger"
            )
        self._workflow = workflow
        self._paid_capable = paid_capable
        self._paid_operation_ledger = paid_operation_ledger

    @property
    def paid_operation_ledger(self) -> SQLitePaidOperationLedger | None:
        return self._paid_operation_ledger

    async def execute(
        self,
        *,
        investigation_id: UUID,
        claim: AtomicClaim,
        requirements: tuple[DurableRequirementReference, ...],
        budget: ResearchBudget,
    ) -> MultiAgentFanOutReport:
        if not requirements:
            raise ValueError("authoritative multi-agent research requires typed requirements")
        typed = tuple(
            ResearchRequirement(
                requirement_id=item.requirement_id,
                component_id=item.component_id,
                kind=item.kind,
                rationale=item.rationale_summary,
            )
            for item in requirements
        )
        report = await self._workflow.start_or_resume(
            investigation_id=investigation_id,
            claim=claim,
            requirements=typed,
            budget=budget,
        )
        if report.investigation_id != investigation_id:
            raise ValueError("research report belongs to a different investigation")
        if report.component_id != claim.claim_id:
            raise ValueError("research report belongs to a different claim component")
        return report


def evidence_family_id(source_ids: tuple[UUID, ...]) -> UUID:
    """Return a stable graph identity for one consolidated evidence family."""
    return uuid5(
        NAMESPACE_URL,
        "authoritative-evidence-family:" + "|".join(sorted(map(str, source_ids))),
    )
