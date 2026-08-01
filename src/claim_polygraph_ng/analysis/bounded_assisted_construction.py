"""Budgeted, receipt-guarded boundary for V3 assisted construction."""

from __future__ import annotations

import json
from collections.abc import Callable
from math import ceil
from uuid import UUID

from pydantic import Field, JsonValue

from claim_polygraph_ng.analysis.assisted_verification_construction import (
    AssistedConstructionKind,
    AssistedConstructionProposal,
    AssistedConstructionRequest,
    AssistedNumericalProviderProposal,
    AssistedScalarProviderProposal,
    AssistedTemporalFactProviderProposal,
    AssistedTemporalProviderProposal,
    canonicalize_assisted_proposal,
    validate_assisted_proposal,
)
from claim_polygraph_ng.domain import Evidence, ModelCallUsage, ModelTask
from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.paid_operations import PaidReceiptStatus
from claim_polygraph_ng.domain.telemetry import MetricName, SpanKind
from claim_polygraph_ng.persistence.paid_operations import SQLitePaidOperationLedger
from claim_polygraph_ng.providers.idempotent import IdempotentStructuredModelProvider
from claim_polygraph_ng.telemetry import TelemetryCollector


class AssistedConstructionBudget(DomainModel):
    maximum_calls_per_case: int = Field(default=1, ge=1, le=1)
    maximum_total_calls: int = Field(default=25, ge=1, le=25)
    maximum_input_tokens: int = Field(default=6_000, ge=1, le=6_000)
    maximum_output_tokens: int = Field(default=1_200, ge=1, le=1_200)
    maximum_total_cost_usd: float = Field(default=0.75, gt=0, le=0.75)


class AssistedConstructionBudgetExceeded(RuntimeError):
    """The frozen V3 experiment budget cannot authorize another call."""


class AssistedConstructionCancelled(RuntimeError):
    """Cancellation was observed at a safe provider boundary."""


class BoundedAssistedConstructionService:
    """Execute at most one validated proposal through a durable paid receipt."""

    def __init__(
        self,
        *,
        provider: IdempotentStructuredModelProvider,
        ledger: SQLitePaidOperationLedger,
        investigation_id: UUID,
        budget: AssistedConstructionBudget | None = None,
        telemetry: TelemetryCollector | None = None,
        cancellation_requested: Callable[[], bool] | None = None,
    ) -> None:
        self._provider = provider
        self._ledger = ledger
        self._investigation_id = investigation_id
        self._budget = budget or AssistedConstructionBudget()
        self._telemetry = telemetry
        self._cancellation_requested = cancellation_requested or (lambda: False)

    async def propose(
        self,
        *,
        request: AssistedConstructionRequest,
        evidence: tuple[Evidence, ...],
    ) -> AssistedConstructionProposal:
        inputs = _provider_inputs(request, evidence)
        response_model = _response_model(request.construction_kind)
        spec = self._provider.operation_spec(
            task=ModelTask.ASSIST_VERIFICATION_CONSTRUCTION,
            response_model=response_model,
            inputs=inputs,
        )
        self._check_cancellation()
        self._check_budget(spec.operation_key, spec.node_id, inputs)

        if self._telemetry is None:
            proposal = await self._generate(inputs, request.construction_kind)
        else:
            with self._telemetry.span(
                "provider.assisted_verification_construction",
                SpanKind.PROVIDER,
                attributes={
                    "provider.task": ModelTask.ASSIST_VERIFICATION_CONSTRUCTION.value,
                    "provider.model": spec.model_or_engine or "unknown",
                    "provider.cached": self._ledger.get(spec.operation_key) is not None,
                },
            ):
                proposal = await self._generate(inputs, request.construction_kind)
        usage = self._provider.take_last_usage()
        self._record_usage_metrics(usage)

        normalized = canonicalize_assisted_proposal(
            proposal=proposal,
            evidence=evidence,
        )
        validated = validate_assisted_proposal(
            request=request,
            proposal=normalized,
            evidence=evidence,
        )
        if (
            usage
            and usage.output_tokens
            and usage.output_tokens > self._budget.maximum_output_tokens
        ):
            raise AssistedConstructionBudgetExceeded(
                "provider output exceeded the frozen 1,200-token budget"
            )
        if usage and usage.input_tokens and usage.input_tokens > self._budget.maximum_input_tokens:
            raise AssistedConstructionBudgetExceeded(
                "provider input exceeded the frozen 6,000-token budget"
            )
        self._check_cancellation()
        return validated

    async def _generate(
        self,
        inputs: dict[str, JsonValue],
        kind: AssistedConstructionKind,
    ) -> AssistedConstructionProposal:
        response_model = _response_model(kind)
        result = await self._provider.generate(
            task=ModelTask.ASSIST_VERIFICATION_CONSTRUCTION,
            response_model=response_model,
            inputs=inputs,
        )
        if isinstance(result, AssistedNumericalProviderProposal):
            return result.to_proposal()
        if isinstance(result, AssistedScalarProviderProposal):
            return result.to_proposal()
        if isinstance(result, AssistedTemporalProviderProposal):
            return result.to_proposal()
        if isinstance(result, AssistedTemporalFactProviderProposal):
            return result.to_proposal()
        raise TypeError("assisted provider returned the wrong typed branch")

    def _check_budget(
        self,
        operation_key: str,
        node_id: str,
        inputs: dict[str, JsonValue],
    ) -> None:
        encoded = json.dumps(inputs, ensure_ascii=False, sort_keys=True).encode("utf-8")
        estimated_input_tokens = ceil(len(encoded) / 3)
        if estimated_input_tokens > self._budget.maximum_input_tokens:
            raise AssistedConstructionBudgetExceeded(
                "input exceeds the frozen 6,000-token pre-call estimate"
            )
        receipts = self._ledger.list_receipts(self._investigation_id)
        assisted = [
            item
            for item in receipts
            if item.spec.task == ModelTask.ASSIST_VERIFICATION_CONSTRUCTION.value
        ]
        same_node = [item for item in assisted if item.spec.node_id == node_id]
        if same_node and all(item.spec.operation_key != operation_key for item in same_node):
            raise AssistedConstructionBudgetExceeded(
                "a different assisted operation already exists for this case"
            )
        matching = [item for item in same_node if item.spec.operation_key == operation_key]
        if matching and any(
            item.status is not PaidReceiptStatus.COMPLETED and item.attempt_number >= 1
            for item in matching
        ):
            raise AssistedConstructionBudgetExceeded(
                "automatic retry is disabled after an assisted provider attempt"
            )
        completed = [item for item in assisted if item.status is PaidReceiptStatus.COMPLETED]
        attempts = sum(item.attempt_number for item in assisted)
        if attempts >= self._budget.maximum_total_calls and not any(
            item.spec.operation_key == operation_key for item in completed
        ):
            raise AssistedConstructionBudgetExceeded("total assisted-call budget exhausted")
        cost = sum(item.estimated_cost_usd for item in completed)
        if cost >= self._budget.maximum_total_cost_usd and not any(
            item.spec.operation_key == operation_key for item in completed
        ):
            raise AssistedConstructionBudgetExceeded("assisted-construction cost exhausted")

    def _check_cancellation(self) -> None:
        if self._cancellation_requested():
            raise AssistedConstructionCancelled(
                "assisted construction cancelled at a safe provider boundary"
            )

    def _record_usage_metrics(self, usage: ModelCallUsage | None) -> None:
        if usage is None or self._telemetry is None:
            return
        if usage.input_tokens is not None:
            self._telemetry.metric(
                MetricName.MODEL_TOKENS,
                usage.input_tokens,
                "tokens",
                attributes={"token.kind": "input", "model": usage.model},
            )
        if usage.output_tokens is not None:
            self._telemetry.metric(
                MetricName.MODEL_TOKENS,
                usage.output_tokens,
                "tokens",
                attributes={"token.kind": "output", "model": usage.model},
            )
        if usage.estimated_cost_usd is not None:
            self._telemetry.metric(
                MetricName.MODEL_COST_USD,
                usage.estimated_cost_usd,
                "usd",
                attributes={"model": usage.model},
            )


def _provider_inputs(
    request: AssistedConstructionRequest,
    evidence: tuple[Evidence, ...],
) -> dict[str, JsonValue]:
    approved = set(request.approved_evidence_ids)
    available = {item.evidence_id for item in evidence}
    missing = approved.difference(available)
    if missing:
        raise ValueError("approved evidence packet is incomplete")
    return {
        "claim_id": str(request.claim_id),
        "claim_text": request.claim_text,
        "failed_construction_id": str(request.failed_construction_id),
        "construction_kind": request.construction_kind.value,
        "approved_evidence": [
            {
                "evidence_id": str(item.evidence_id),
                "passage": item.passage,
            }
            for item in evidence
            if item.evidence_id in approved
        ],
    }


def _response_model(kind: AssistedConstructionKind):
    if kind is AssistedConstructionKind.NUMERICAL:
        return AssistedNumericalProviderProposal
    if kind is AssistedConstructionKind.NUMERICAL_SCALAR:
        return AssistedScalarProviderProposal
    return AssistedTemporalFactProviderProposal
