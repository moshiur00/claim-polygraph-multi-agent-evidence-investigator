"""V4.1 failed-operation cost and usage observability contracts."""

import asyncio
import json
from uuid import uuid4

import httpx
import pytest

from claim_polygraph_ng.domain import AtomicClaim, ClaimType, ModelCallUsage, ModelTask
from claim_polygraph_ng.domain.paid_operations import (
    PaidOperationReceipt,
    PaidReceiptStatus,
    PaidUsageDisposition,
)
from claim_polygraph_ng.persistence.paid_operations import SQLitePaidOperationLedger
from claim_polygraph_ng.providers.idempotent import IdempotentStructuredModelProvider
from claim_polygraph_ng.providers.ollama import ModelOutputError, ModelUnavailableError
from claim_polygraph_ng.providers.openai import OpenAIStructuredModelProvider


class MeasuredMalformedProvider:
    provider_id = "measured-malformed"
    model = "fixture-model"

    def __init__(self) -> None:
        self._usage = None

    async def generate(self, *, task, response_model, inputs):
        del response_model, inputs
        self._usage = ModelCallUsage(
            provider_id=self.provider_id,
            model=self.model,
            task=task,
            duration_seconds=0.25,
            input_tokens=120,
            cached_input_tokens=20,
            output_tokens=30,
            estimated_cost_usd=0.004,
            pricing_version="fixture-v1",
            output_valid=False,
        )
        raise ModelOutputError("fixture schema rejection")

    def take_last_usage(self):
        usage = self._usage
        self._usage = None
        return usage


class UnmeasuredFailureProvider:
    provider_id = "unmeasured-failure"
    model = "fixture-model"

    async def generate(self, *, task, response_model, inputs):
        del task, response_model, inputs
        raise ModelUnavailableError("fixture transport failure")


class SuccessfulUnpricedProvider:
    provider_id = "successful-unpriced"
    model = "fixture-model"

    async def generate(self, *, task, response_model, inputs):
        del task
        return response_model(
            text=str(inputs["claim_text"]),
            claim_type=ClaimType.FACTUAL,
            checkworthiness=0.8,
        )


class UnknownThenMeasuredProvider:
    provider_id = "unknown-then-measured"
    model = "fixture-model"

    def __init__(self) -> None:
        self.calls = 0
        self._usage = None

    async def generate(self, *, task, response_model, inputs):
        self.calls += 1
        if self.calls == 1:
            raise ModelUnavailableError("first attempt has unknown usage")
        self._usage = ModelCallUsage(
            provider_id=self.provider_id,
            model=self.model,
            task=task,
            duration_seconds=0.2,
            input_tokens=80,
            cached_input_tokens=0,
            output_tokens=20,
            estimated_cost_usd=0.002,
            pricing_version="fixture-v1",
            output_valid=True,
        )
        return response_model(
            text=str(inputs["claim_text"]),
            claim_type=ClaimType.FACTUAL,
            checkworthiness=0.8,
        )

    def take_last_usage(self):
        usage = self._usage
        self._usage = None
        return usage


def _wrapper(tmp_path, provider, *, upper_bound=0.05):
    investigation_id = uuid4()
    safe_provider_id = "".join(
        character if character.isalnum() else "-"
        for character in provider.provider_id
    )
    ledger = SQLitePaidOperationLedger(tmp_path / f"{safe_provider_id}.db")
    wrapper = IdempotentStructuredModelProvider(
        provider=provider,
        ledger=ledger,
        investigation_id=investigation_id,
        node_id="v4-cost-observability",
        worker_id="v4-test-worker",
        unknown_cost_upper_bound_usd=upper_bound,
    )
    return investigation_id, ledger, wrapper


def _invoke(wrapper):
    return asyncio.run(
        wrapper.generate(
            task=ModelTask.NORMALIZE_CLAIM,
            response_model=AtomicClaim,
            inputs={"claim_text": "A bounded fixture claim."},
        )
    )


def test_malformed_response_retains_measured_usage_and_cost(tmp_path) -> None:
    investigation_id, ledger, wrapper = _wrapper(
        tmp_path, MeasuredMalformedProvider()
    )

    with pytest.raises(ModelOutputError):
        _invoke(wrapper)

    receipt = ledger.list_receipts(investigation_id)[0]
    costs = ledger.cost_ledger(investigation_id)
    assert receipt.status is PaidReceiptStatus.FAILED_PERMANENT
    assert receipt.usage_disposition is PaidUsageDisposition.MEASURED
    assert receipt.input_tokens == 120
    assert receipt.cached_input_tokens == 20
    assert receipt.output_tokens == 30
    assert receipt.estimated_cost_usd == 0.004
    assert receipt.estimated_cost_upper_bound_usd is None
    assert costs.attempted_operation_count == 1
    assert costs.failed_operation_count == 1
    assert costs.estimated_cost_usd == 0.004
    assert costs.estimated_cost_upper_bound_usd == 0.004
    assert not costs.cost_is_lower_bound


def test_unmeasured_failure_is_explicit_with_conservative_upper_bound(tmp_path) -> None:
    investigation_id, ledger, wrapper = _wrapper(
        tmp_path, UnmeasuredFailureProvider(), upper_bound=0.05
    )

    with pytest.raises(ModelUnavailableError):
        _invoke(wrapper)

    receipt = ledger.list_receipts(investigation_id)[0]
    costs = ledger.cost_ledger(investigation_id)
    assert receipt.status is PaidReceiptStatus.FAILED_RETRYABLE
    assert (
        receipt.usage_disposition
        is PaidUsageDisposition.UNKNOWN_WITH_UPPER_BOUND
    )
    assert receipt.estimated_cost_usd == 0
    assert receipt.estimated_cost_upper_bound_usd == 0.05
    assert receipt.usage_note
    assert costs.estimated_cost_usd == 0
    assert costs.estimated_cost_upper_bound_usd == 0.05
    assert costs.unpriced_operation_count == 1
    assert costs.cost_is_lower_bound


def test_success_without_usage_is_not_silently_treated_as_free(tmp_path) -> None:
    investigation_id, ledger, wrapper = _wrapper(
        tmp_path, SuccessfulUnpricedProvider(), upper_bound=0.03
    )

    result = _invoke(wrapper)

    assert result.text == "A bounded fixture claim."
    receipt = ledger.list_receipts(investigation_id)[0]
    assert (
        receipt.usage_disposition
        is PaidUsageDisposition.UNKNOWN_WITH_UPPER_BOUND
    )
    assert receipt.estimated_cost_upper_bound_usd == 0.03
    assert ledger.cost_ledger(investigation_id).cost_is_lower_bound


def test_legacy_receipt_remains_readable_but_explicitly_unclassified() -> None:
    receipt = PaidOperationReceipt.model_validate(
        {
            "spec": {
                "operation_key": "paid:" + "a" * 64,
                "investigation_id": str(uuid4()),
                "node_id": "legacy-node",
                "kind": "model",
                "provider": "legacy-provider",
                "model_or_engine": "legacy-model",
                "task": "legacy-task",
                "canonical_input_sha256": "b" * 64,
            },
            "lease_owner": "legacy-worker",
            "lease_expires_at": "2030-01-01T00:00:00Z",
        }
    )

    assert receipt.usage_disposition is PaidUsageDisposition.LEGACY_UNCLASSIFIED


def test_retry_accumulates_prior_unknown_bound_and_later_measured_cost(
    tmp_path,
) -> None:
    provider = UnknownThenMeasuredProvider()
    investigation_id, ledger, wrapper = _wrapper(
        tmp_path, provider, upper_bound=0.05
    )
    with pytest.raises(ModelUnavailableError):
        _invoke(wrapper)

    result = _invoke(wrapper)

    assert result.text == "A bounded fixture claim."
    receipt = ledger.list_receipts(investigation_id)[0]
    costs = ledger.cost_ledger(investigation_id)
    assert receipt.attempt_number == 2
    assert (
        receipt.usage_disposition
        is PaidUsageDisposition.UNKNOWN_WITH_UPPER_BOUND
    )
    assert receipt.estimated_cost_usd == 0.002
    assert receipt.estimated_cost_upper_bound_usd == 0.05
    assert costs.estimated_cost_usd == 0.002
    assert costs.estimated_cost_upper_bound_usd == pytest.approx(0.052)
    assert costs.cost_is_lower_bound
    assert costs.attempted_operation_count == 2
    assert costs.failed_operation_count == 1


def test_openai_schema_failure_usage_survives_receipt_boundary(tmp_path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "usage": {
                    "input_tokens": 100,
                    "input_tokens_details": {"cached_tokens": 10},
                    "output_tokens": 25,
                },
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps({"invalid": "schema"}),
                            }
                        ],
                    }
                ],
            },
        )

    provider = OpenAIStructuredModelProvider(
        api_key="test-secret",
        model="gpt-5.4-mini",
        fast_model="gpt-4o-mini",
        transport=httpx.MockTransport(handler),
    )
    investigation_id, ledger, wrapper = _wrapper(tmp_path, provider)

    with pytest.raises(ModelOutputError):
        _invoke(wrapper)

    receipt = ledger.list_receipts(investigation_id)[0]
    assert receipt.status is PaidReceiptStatus.FAILED_PERMANENT
    assert receipt.usage_disposition is PaidUsageDisposition.MEASURED
    assert receipt.input_tokens == 100
    assert receipt.cached_input_tokens == 10
    assert receipt.output_tokens == 25
    assert receipt.estimated_cost_usd > 0
