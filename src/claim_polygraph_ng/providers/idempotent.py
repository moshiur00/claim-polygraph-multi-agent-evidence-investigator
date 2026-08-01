"""Receipt-guarded decorators for metered model and search providers."""

import hashlib
import json
from collections.abc import Callable, Mapping
from time import perf_counter
from typing import TypeVar
from uuid import UUID

from pydantic import JsonValue

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.investigation import (
    ModelCallUsage,
    ModelTask,
    SearchRequest,
    SearchResult,
)
from claim_polygraph_ng.domain.paid_operations import (
    PaidOperationKind,
    PaidOperationSpec,
    PaidReceiptDecision,
)
from claim_polygraph_ng.persistence.paid_operations import (
    PaidOperationActiveError,
    PaidOperationAmbiguousError,
    PaidOperationTerminalError,
    SQLitePaidOperationLedger,
)
from claim_polygraph_ng.providers.base import SearchProvider, StructuredModelProvider
from claim_polygraph_ng.providers.ollama import ModelUnavailableError

StructuredResult = TypeVar("StructuredResult", bound=DomainModel)


def canonical_paid_operation_spec(
    *,
    investigation_id: UUID,
    node_id: str,
    kind: PaidOperationKind,
    provider: str,
    task: str,
    payload: object,
    model_or_engine: str | None = None,
) -> PaidOperationSpec:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    input_hash = hashlib.sha256(canonical.encode()).hexdigest()
    key_material = json.dumps(
        {
            "investigation_id": str(investigation_id),
            "node_id": node_id,
            "kind": kind.value,
            "provider": provider,
            "model_or_engine": model_or_engine,
            "task": task,
            "canonical_input_sha256": input_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return PaidOperationSpec(
        operation_key=f"paid:{hashlib.sha256(key_material.encode()).hexdigest()}",
        investigation_id=investigation_id,
        node_id=node_id,
        kind=kind,
        provider=provider,
        model_or_engine=model_or_engine,
        task=task,
        canonical_input_sha256=input_hash,
    )


class IdempotentStructuredModelProvider:
    """Return stored structured output instead of repeating a completed model call."""

    def __init__(
        self,
        *,
        provider: StructuredModelProvider,
        ledger: SQLitePaidOperationLedger,
        investigation_id: UUID,
        node_id: str,
        worker_id: str,
        lease_seconds: int = 120,
        before_provider_start: Callable[[], None] | None = None,
        after_provider_success: Callable[[], None] | None = None,
        unknown_cost_upper_bound_usd: float = 0.05,
    ) -> None:
        self._provider = provider
        self._ledger = ledger
        self._investigation_id = investigation_id
        self._node_id = node_id
        self._worker_id = worker_id
        self._lease_seconds = lease_seconds
        self._before_provider_start = before_provider_start
        self._after_provider_success = after_provider_success
        if unknown_cost_upper_bound_usd < 0:
            raise ValueError("unknown cost upper bound cannot be negative")
        self._unknown_cost_upper_bound_usd = unknown_cost_upper_bound_usd
        self._last_usage: ModelCallUsage | None = None
        self.provider_id = f"idempotent:{provider.provider_id}"

    async def generate(
        self,
        *,
        task: ModelTask,
        response_model: type[StructuredResult],
        inputs: Mapping[str, JsonValue],
    ) -> StructuredResult:
        spec = self.operation_spec(
            task=task,
            response_model=response_model,
            inputs=inputs,
        )
        model = spec.model_or_engine
        claim = self._ledger.reserve(
            spec,
            worker_id=self._worker_id,
            lease_seconds=self._lease_seconds,
        )
        if claim.decision is PaidReceiptDecision.RETURN_CACHED:
            self._last_usage = ModelCallUsage(
                provider_id=f"receipt-cache:{self._provider.provider_id}",
                model=model or "unknown",
                task=task,
                duration_seconds=0,
                input_tokens=0,
                cached_input_tokens=0,
                output_tokens=0,
                estimated_cost_usd=0,
                pricing_version="durable-receipt-cache-v1",
                output_valid=True,
            )
            return response_model.model_validate_json(
                self._ledger.load_result(claim.receipt)
            )
        _raise_non_executable(claim.decision, spec.operation_key)
        if self._before_provider_start is not None:
            self._before_provider_start()
        self._ledger.mark_provider_started(
            spec.operation_key,
            worker_id=self._worker_id,
        )
        started = perf_counter()
        try:
            result = await self._provider.generate(
                task=task,
                response_model=response_model,
                inputs=inputs,
            )
        except Exception as error:
            usage = _take_usage(self._provider)
            self._last_usage = usage
            self._ledger.fail(
                spec.operation_key,
                worker_id=self._worker_id,
                retryable=isinstance(error, ModelUnavailableError),
                error=error,
                usage=usage,
                unknown_cost_upper_bound_usd=self._unknown_cost_upper_bound_usd,
                duration_seconds=perf_counter() - started,
            )
            raise
        usage = _take_usage(self._provider)
        self._last_usage = usage
        if self._after_provider_success is not None:
            self._after_provider_success()
        self._ledger.complete(
            spec.operation_key,
            worker_id=self._worker_id,
            result_payload=result.model_dump_json(),
            usage=usage,
            unknown_cost_upper_bound_usd=self._unknown_cost_upper_bound_usd,
            duration_seconds=perf_counter() - started,
        )
        return result

    def operation_spec(
        self,
        *,
        task: ModelTask,
        response_model: type[StructuredResult],
        inputs: Mapping[str, JsonValue],
    ) -> PaidOperationSpec:
        """Expose the exact canonical receipt key for pre-call budget checks."""
        model_for_task = getattr(self._provider, "model_for_task", None)
        model = model_for_task(task) if callable(model_for_task) else getattr(
            self._provider, "model", None
        )
        payload: dict[str, object] = {
            "response_model": response_model.__name__,
            "inputs": inputs,
        }
        if task is ModelTask.ASSIST_VERIFICATION_CONSTRUCTION:
            payload["provider_prompt_version"] = getattr(
                self._provider, "prompt_version", "unspecified"
            )
        return canonical_paid_operation_spec(
            investigation_id=self._investigation_id,
            node_id=self._node_id,
            kind=PaidOperationKind.MODEL,
            provider=self._provider.provider_id,
            model_or_engine=model,
            task=task.value,
            payload=payload,
        )

    def take_last_usage(self) -> ModelCallUsage | None:
        usage = self._last_usage
        self._last_usage = None
        return usage


class IdempotentSearchProvider:
    """Return a stored result page instead of repeating a completed metered search."""

    def __init__(
        self,
        *,
        provider: SearchProvider,
        ledger: SQLitePaidOperationLedger,
        investigation_id: UUID,
        node_id: str,
        worker_id: str,
        engine: str | None = None,
        lease_seconds: int = 120,
        before_provider_start: Callable[[], None] | None = None,
        after_provider_success: Callable[[], None] | None = None,
    ) -> None:
        self._provider = provider
        self._ledger = ledger
        self._investigation_id = investigation_id
        self._node_id = node_id
        self._worker_id = worker_id
        self._engine = engine
        self._lease_seconds = lease_seconds
        self._before_provider_start = before_provider_start
        self._after_provider_success = after_provider_success
        self.provider_id = f"idempotent:{provider.provider_id}"

    async def search(self, request: SearchRequest) -> tuple[SearchResult, ...]:
        spec = canonical_paid_operation_spec(
            investigation_id=self._investigation_id,
            node_id=self._node_id,
            kind=PaidOperationKind.SEARCH,
            provider=self._provider.provider_id,
            model_or_engine=self._engine,
            task=f"search:{request.research_path.value}",
            payload=request.model_dump(mode="json"),
        )
        claim = self._ledger.reserve(
            spec,
            worker_id=self._worker_id,
            lease_seconds=self._lease_seconds,
        )
        if claim.decision is PaidReceiptDecision.RETURN_CACHED:
            payload = json.loads(self._ledger.load_result(claim.receipt))
            return tuple(SearchResult.model_validate(item) for item in payload)
        _raise_non_executable(claim.decision, spec.operation_key)
        if self._before_provider_start is not None:
            self._before_provider_start()
        self._ledger.mark_provider_started(
            spec.operation_key,
            worker_id=self._worker_id,
        )
        started = perf_counter()
        try:
            results = await self._provider.search(request)
        except Exception as error:
            self._ledger.fail(
                spec.operation_key,
                worker_id=self._worker_id,
                retryable=True,
                error=error,
            )
            raise
        if self._after_provider_success is not None:
            self._after_provider_success()
        self._ledger.complete(
            spec.operation_key,
            worker_id=self._worker_id,
            result_payload=json.dumps(
                [item.model_dump(mode="json") for item in results],
                sort_keys=True,
                separators=(",", ":"),
            ),
            duration_seconds=perf_counter() - started,
        )
        return results


def _raise_non_executable(
    decision: PaidReceiptDecision,
    operation_key: str,
) -> None:
    if decision is PaidReceiptDecision.EXECUTE:
        return
    if decision is PaidReceiptDecision.ACTIVE:
        raise PaidOperationActiveError(f"paid operation is active: {operation_key}")
    if decision is PaidReceiptDecision.AMBIGUOUS:
        raise PaidOperationAmbiguousError(
            f"paid operation completion is ambiguous: {operation_key}"
        )
    raise PaidOperationTerminalError(f"paid operation cannot execute: {operation_key}")


def _take_usage(provider: StructuredModelProvider) -> ModelCallUsage | None:
    take = getattr(provider, "take_last_usage", None)
    if not callable(take):
        return None
    usage = take()
    return usage if isinstance(usage, ModelCallUsage) else None
