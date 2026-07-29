"""Stage 9.5 duplicate-charge and crash-boundary tests."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from claim_polygraph_ng.domain import (
    AtomicClaim,
    ClaimType,
    ModelCallUsage,
    ModelTask,
    ResearchPath,
    SearchRequest,
)
from claim_polygraph_ng.domain.paid_operations import (
    PaidOperationKind,
    PaidReceiptDecision,
    PaidReceiptStatus,
)
from claim_polygraph_ng.persistence.paid_operations import (
    PaidOperationAmbiguousError,
    SQLitePaidOperationLedger,
)
from claim_polygraph_ng.providers.idempotent import (
    IdempotentSearchProvider,
    IdempotentStructuredModelProvider,
    canonical_paid_operation_spec,
)
from claim_polygraph_ng.providers.mock import DeterministicSearchProvider
from claim_polygraph_ng.providers.ollama import ModelUnavailableError


class SimulatedProcessCrash(BaseException):
    pass


class CountingModelProvider:
    provider_id = "counted-model"
    model = "fixture-model"

    def __init__(self, *, fail_once: bool = False, crash_during: bool = False) -> None:
        self.calls = 0
        self.fail_once = fail_once
        self.crash_during = crash_during
        self._usage = None

    async def generate(self, *, task, response_model, inputs):
        self.calls += 1
        if self.crash_during:
            raise SimulatedProcessCrash()
        if self.fail_once:
            self.fail_once = False
            raise ModelUnavailableError("temporary provider failure")
        result = AtomicClaim(
            text=str(inputs["claim_text"]),
            claim_type=ClaimType.FACTUAL,
            checkworthiness=0.8,
        )
        self._usage = ModelCallUsage(
            provider_id=self.provider_id,
            model=self.model,
            task=task,
            duration_seconds=0.5,
            input_tokens=100,
            cached_input_tokens=10,
            output_tokens=20,
            estimated_cost_usd=0.002,
            pricing_version="fixture-v1",
            output_valid=True,
        )
        return response_model.model_validate(result.model_dump())

    def take_last_usage(self):
        usage = self._usage
        self._usage = None
        return usage


class CountingSearchProvider(DeterministicSearchProvider):
    def __init__(self) -> None:
        self.calls = 0

    async def search(self, request):
        self.calls += 1
        return await super().search(request)


def _model_wrapper(tmp_path, provider, *, after_success=None, before_start=None):
    investigation_id = uuid4()
    ledger = SQLitePaidOperationLedger(tmp_path / "paid.db")
    wrapper = IdempotentStructuredModelProvider(
        provider=provider,
        ledger=ledger,
        investigation_id=investigation_id,
        node_id="normalize",
        worker_id="worker-one",
        lease_seconds=1,
        before_provider_start=before_start,
        after_provider_success=after_success,
    )
    return investigation_id, ledger, wrapper


def test_completed_model_call_replays_result_without_duplicate_cost(tmp_path) -> None:
    provider = CountingModelProvider()
    investigation_id, ledger, wrapper = _model_wrapper(tmp_path, provider)
    inputs = {"claim_text": "A receipt-grounded factual claim."}

    first = asyncio.run(
        wrapper.generate(
            task=ModelTask.NORMALIZE_CLAIM,
            response_model=AtomicClaim,
            inputs=inputs,
        )
    )
    first_usage = wrapper.take_last_usage()
    second = asyncio.run(
        wrapper.generate(
            task=ModelTask.NORMALIZE_CLAIM,
            response_model=AtomicClaim,
            inputs=inputs,
        )
    )
    cached_usage = wrapper.take_last_usage()
    costs = ledger.cost_ledger(investigation_id)

    assert first == second
    assert provider.calls == 1
    assert first_usage.estimated_cost_usd == 0.002
    assert cached_usage.estimated_cost_usd == 0
    assert costs.completed_operation_count == 1
    assert costs.estimated_cost_usd == 0.002
    assert costs.input_tokens == 100


def test_active_reservation_blocks_concurrent_worker_and_stale_pre_call_is_safe(
    tmp_path,
) -> None:
    ledger = SQLitePaidOperationLedger(tmp_path / "reservation.db")
    instant = datetime.now(UTC)
    spec = canonical_paid_operation_spec(
        investigation_id=uuid4(),
        node_id="research",
        kind=PaidOperationKind.SEARCH,
        provider="metered-search",
        task="search:primary",
        payload={"query": "claim"},
    )
    first = ledger.reserve(spec, worker_id="worker-one", lease_seconds=10, now=instant)
    active = ledger.reserve(spec, worker_id="worker-two", lease_seconds=10, now=instant)
    reclaimed = ledger.reserve(
        spec,
        worker_id="worker-two",
        lease_seconds=10,
        now=instant + timedelta(seconds=11),
    )

    assert first.decision is PaidReceiptDecision.EXECUTE
    assert active.decision is PaidReceiptDecision.ACTIVE
    assert reclaimed.decision is PaidReceiptDecision.EXECUTE
    assert reclaimed.receipt.lease_owner == "worker-two"
    assert reclaimed.receipt.attempt_number == 0


def test_crash_during_provider_becomes_ambiguous_and_never_auto_retries(tmp_path) -> None:
    provider = CountingModelProvider(crash_during=True)
    investigation_id, ledger, wrapper = _model_wrapper(tmp_path, provider)
    inputs = {"claim_text": "A provider crash claim."}
    spec = canonical_paid_operation_spec(
        investigation_id=investigation_id,
        node_id="normalize",
        kind=PaidOperationKind.MODEL,
        provider=provider.provider_id,
        model_or_engine=provider.model,
        task=ModelTask.NORMALIZE_CLAIM.value,
        payload={"response_model": "AtomicClaim", "inputs": inputs},
    )

    with pytest.raises(SimulatedProcessCrash):
        asyncio.run(
            wrapper.generate(
                task=ModelTask.NORMALIZE_CLAIM,
                response_model=AtomicClaim,
                inputs=inputs,
            )
        )
    in_progress = ledger.get(spec.operation_key)
    claim = ledger.reserve(
        spec,
        worker_id="worker-two",
        now=in_progress.lease_expires_at + timedelta(seconds=1),
    )

    assert provider.calls == 1
    assert claim.decision is PaidReceiptDecision.AMBIGUOUS
    assert claim.receipt.status is PaidReceiptStatus.AMBIGUOUS
    with pytest.raises(PaidOperationAmbiguousError):
        asyncio.run(
            IdempotentStructuredModelProvider(
                provider=provider,
                ledger=ledger,
                investigation_id=investigation_id,
                node_id="normalize",
                worker_id="worker-two",
            ).generate(
                task=ModelTask.NORMALIZE_CLAIM,
                response_model=AtomicClaim,
                inputs=inputs,
            )
        )
    assert provider.calls == 1
    ledger.authorize_ambiguous_retry(spec.operation_key, actor="recovery-operator")
    provider.crash_during = False
    recovered = asyncio.run(
        IdempotentStructuredModelProvider(
            provider=provider,
            ledger=ledger,
            investigation_id=investigation_id,
            node_id="normalize",
            worker_id="worker-two",
        ).generate(
            task=ModelTask.NORMALIZE_CLAIM,
            response_model=AtomicClaim,
            inputs=inputs,
        )
    )
    assert recovered.text == inputs["claim_text"]
    assert provider.calls == 2


def test_crash_after_provider_success_does_not_repeat_ambiguous_charge(tmp_path) -> None:
    provider = CountingModelProvider()

    def crash_after_success():
        raise SimulatedProcessCrash()

    investigation_id, ledger, wrapper = _model_wrapper(
        tmp_path,
        provider,
        after_success=crash_after_success,
    )
    inputs = {"claim_text": "A post-success crash claim."}
    with pytest.raises(SimulatedProcessCrash):
        asyncio.run(
            wrapper.generate(
                task=ModelTask.NORMALIZE_CLAIM,
                response_model=AtomicClaim,
                inputs=inputs,
            )
        )
    receipt = next(
        item
        for item in (
            ledger.get(
                canonical_paid_operation_spec(
                    investigation_id=investigation_id,
                    node_id="normalize",
                    kind=PaidOperationKind.MODEL,
                    provider=provider.provider_id,
                    model_or_engine=provider.model,
                    task=ModelTask.NORMALIZE_CLAIM.value,
                    payload={"response_model": "AtomicClaim", "inputs": inputs},
                ).operation_key
            ),
        )
        if item is not None
    )
    assert receipt.status is PaidReceiptStatus.IN_PROGRESS
    assert provider.calls == 1


def test_retryable_failure_may_retry_and_completed_search_is_cached(tmp_path) -> None:
    provider = CountingModelProvider(fail_once=True)
    investigation_id, ledger, wrapper = _model_wrapper(tmp_path, provider)
    inputs = {"claim_text": "A retryable model claim."}
    with pytest.raises(ModelUnavailableError):
        asyncio.run(
            wrapper.generate(
                task=ModelTask.NORMALIZE_CLAIM,
                response_model=AtomicClaim,
                inputs=inputs,
            )
        )
    result = asyncio.run(
        wrapper.generate(
            task=ModelTask.NORMALIZE_CLAIM,
            response_model=AtomicClaim,
            inputs=inputs,
        )
    )
    assert result.text == inputs["claim_text"]
    assert provider.calls == 2
    assert ledger.cost_ledger(investigation_id).completed_operation_count == 1

    search = CountingSearchProvider()
    search_wrapper = IdempotentSearchProvider(
        provider=search,
        ledger=ledger,
        investigation_id=investigation_id,
        node_id="primary-search",
        worker_id="worker-one",
        engine="fixture",
    )
    request = SearchRequest(
        claim_id=uuid4(),
        query="official primary source: a factual claim",
        research_path=ResearchPath.PRIMARY,
    )
    first = asyncio.run(search_wrapper.search(request))
    second = asyncio.run(search_wrapper.search(request))
    assert first == second
    assert search.calls == 1
    assert ledger.cost_ledger(investigation_id).search_operation_count == 1


def test_stage9_5_offline_gate_and_release_manifest_verify(tmp_path) -> None:
    from pathlib import Path

    from claim_polygraph_ng.evaluation.phase9_paid_operations import (
        build_phase9_paid_operation_release_manifest,
        evaluate_phase9_paid_operation_gate,
        verify_phase9_paid_operation_release_manifest,
    )

    root = Path(__file__).parents[2]
    gate = evaluate_phase9_paid_operation_gate(tmp_path / "gate.db")
    gate_path = root / "artifacts/evaluations/phase9-stage9.5-paid-operation-safety-v1.json"
    gate_path.write_text(gate.model_dump_json(indent=2) + "\n", encoding="utf-8")
    manifest = build_phase9_paid_operation_release_manifest(root)
    verification = verify_phase9_paid_operation_release_manifest(manifest, root)

    assert gate.completed_replay_without_execution
    assert gate.active_concurrency_blocked
    assert gate.stale_pre_call_reclaimable
    assert gate.stale_in_flight_ambiguous
    assert gate.unique_cost_entry_count == 1
    assert verification.valid
