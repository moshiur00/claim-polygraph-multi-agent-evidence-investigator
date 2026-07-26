"""Tests for the hosted OpenAI structured-model adapter."""

import asyncio
import json
from uuid import uuid4

import httpx
import pytest

from claim_polygraph_ng.domain import AtomicClaim, ClaimType, InvestigationPlan, ModelTask
from claim_polygraph_ng.evaluation import SemanticPassageJudgment
from claim_polygraph_ng.providers import (
    ModelOutputError,
    ModelUnavailableError,
    OpenAIStructuredModelProvider,
)


def test_openai_sends_strict_responses_request_and_validates_output() -> None:
    captured: dict[str, object] = {}
    artifact = AtomicClaim(
        text="Earth takes about one year to orbit the Sun.",
        claim_type=ClaimType.SCIENTIFIC,
        checkworthiness=0.8,
    )
    semantics = artifact.model_dump(exclude={"claim_id", "parent_claim_id"}, mode="json")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.openai.com/v1/responses"
        assert request.headers["authorization"] == "Bearer test-secret"
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "resp_test",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(semantics),
                            }
                        ],
                    }
                ],
            },
        )

    provider = OpenAIStructuredModelProvider(
        api_key="test-secret",
        model="gpt-test",
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(
        provider.generate(
            task=ModelTask.NORMALIZE_CLAIM,
            response_model=AtomicClaim,
            inputs={"claim_text": "Earth takes about one year to orbit the Sun."},
        )
    )

    assert result.model_dump(exclude={"claim_id"}) == artifact.model_dump(exclude={"claim_id"})
    assert captured["model"] == "gpt-test"
    assert captured["store"] is False
    assert captured["reasoning"] == {"effort": "low"}
    assert captured["max_output_tokens"] == 2_048
    text_format = captured["text"]["format"]
    assert text_format["type"] == "json_schema"
    assert text_format["strict"] is True
    schema = text_format["schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert "claim_id" not in schema["properties"]


def test_openai_normalizes_auth_error_without_exposing_key() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            401,
            json={"error": {"message": "Incorrect API key", "type": "invalid_request_error"}},
        )

    provider = OpenAIStructuredModelProvider(
        api_key="do-not-leak-this-key",
        model="gpt-test",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ModelUnavailableError) as captured:
        asyncio.run(
            provider.generate(
                task=ModelTask.NORMALIZE_CLAIM,
                response_model=AtomicClaim,
                inputs={"claim_text": "A factual claim."},
            )
        )

    assert "HTTP 401" in str(captured.value)
    assert "do-not-leak-this-key" not in str(captured.value)


def test_openai_routes_focused_and_reasoning_tasks_with_compatible_parameters() -> None:
    claim_id = uuid4()
    requests: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        if payload["model"] == "gpt-4o-mini":
            content = {
                "text": "A normalized factual claim.",
                "claim_type": "factual",
                "entities": [],
                "quantities": [],
                "reference_date": None,
                "geography": None,
                "ambiguities": [],
                "checkworthiness": 0.8,
            }
        else:
            content = {
                "required_research_paths": ["general", "contradiction"],
                "required_source_types": [],
                "minimum_independent_families": 2,
                "requires_numerical_check": False,
                "requires_temporal_check": False,
                "maximum_research_rounds": 2,
                "maximum_search_calls": 6,
                "maximum_pages_fetched": 10,
            }
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": json.dumps(content)}],
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
    asyncio.run(
        provider.generate(
            task=ModelTask.NORMALIZE_CLAIM,
            response_model=AtomicClaim,
            inputs={"claim_text": "A factual claim."},
        )
    )
    asyncio.run(
        provider.generate(
            task=ModelTask.PLAN_INVESTIGATION,
            response_model=InvestigationPlan,
            inputs={"claim_id": str(claim_id), "claim_text": "A factual claim."},
        )
    )

    assert provider.provider_id == "openai:routed:gpt-4o-mini->gpt-5.4-mini"
    assert requests[0]["model"] == "gpt-4o-mini"
    assert "reasoning" not in requests[0]
    assert requests[1]["model"] == "gpt-5.4-mini"
    assert requests[1]["reasoning"] == {"effort": "low"}


def test_openai_routes_semantic_passage_evaluation_to_reasoning_model() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        content = SemanticPassageJudgment(
            relationship="equivalent",
            rationale=(
                "The passage establishes the same material evidentiary point as the reviewed "
                "target."
            ),
            matched_points=("Both establish the relevant qualification.",),
            missing_or_conflicting_points=(),
        )
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": content.model_dump_json(),
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
    result = asyncio.run(
        provider.generate(
            task=ModelTask.EVALUATE_PASSAGE,
            response_model=SemanticPassageJudgment,
            inputs={
                "claim": "A claim.",
                "reviewed_evidence": {"summary": "A reviewed point."},
                "retrieved_passage": "A passage establishing the reviewed point.",
            },
        )
    )

    assert result.relationship == "equivalent"
    assert captured["model"] == "gpt-5.4-mini"
    assert captured["reasoning"] == {"effort": "low"}


def test_openai_routes_sentence_audit_to_reasoning_model() -> None:
    provider = OpenAIStructuredModelProvider(
        api_key="test-secret",
        model="gpt-5.4-mini",
        fast_model="gpt-4o-mini",
    )

    assert provider.model_for_task(ModelTask.AUDIT_SENTENCE) == "gpt-5.4-mini"


def test_openai_records_usage_latency_and_versioned_cost_estimate() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        content = {
            "text": "A normalized factual claim.",
            "claim_type": "factual",
            "entities": [],
            "quantities": [],
            "reference_date": None,
            "geography": None,
            "ambiguities": [],
            "checkworthiness": 0.8,
        }
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "usage": {
                    "input_tokens": 1_000,
                    "input_tokens_details": {"cached_tokens": 200},
                    "output_tokens": 500,
                },
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": json.dumps(content)}],
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
    asyncio.run(
        provider.generate(
            task=ModelTask.NORMALIZE_CLAIM,
            response_model=AtomicClaim,
            inputs={"claim_text": "A factual claim."},
        )
    )
    usage = provider.take_last_usage()

    assert usage is not None
    assert usage.model == "gpt-4o-mini"
    assert usage.input_tokens == 1_000
    assert usage.cached_input_tokens == 200
    assert usage.output_tokens == 500
    assert usage.estimated_cost_usd == pytest.approx(0.000435)
    assert usage.pricing_version == "openai-list-prices-2026-07-26"
    assert usage.output_valid is True
    assert usage.duration_seconds >= 0
    assert provider.take_last_usage() is None


@pytest.mark.parametrize(
    "response_payload",
    [
        {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}},
        {
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "refusal", "refusal": "Cannot comply"}],
                }
            ],
        },
    ],
)
def test_openai_rejects_incomplete_or_refused_output(response_payload: object) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json=response_payload)

    provider = OpenAIStructuredModelProvider(
        api_key="test-secret",
        model="gpt-test",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ModelOutputError):
        asyncio.run(
            provider.generate(
                task=ModelTask.NORMALIZE_CLAIM,
                response_model=AtomicClaim,
                inputs={"claim_text": "A factual claim."},
            )
        )


@pytest.mark.parametrize(
    ("api_key", "model", "timeout"),
    [
        ("", "gpt-test", 60),
        ("key", "", 60),
        ("key", "model with spaces", 60),
        ("key", "gpt-test", 0),
    ],
)
def test_openai_rejects_invalid_configuration(
    api_key: str,
    model: str,
    timeout: float,
) -> None:
    with pytest.raises(ValueError):
        OpenAIStructuredModelProvider(
            api_key=api_key,
            model=model,
            timeout_seconds=timeout,
        )


def test_openai_rejects_invalid_fast_model() -> None:
    with pytest.raises(ValueError, match="fast model"):
        OpenAIStructuredModelProvider(
            api_key="key",
            model="gpt-5.4-mini",
            fast_model="invalid model",
        )
