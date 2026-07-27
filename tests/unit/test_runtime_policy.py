"""Tests for execution budgets and provider policy enforcement."""

import pytest
from pydantic import ValidationError

from claim_polygraph_ng.config import (
    CostClass,
    ExecutionBudget,
    OperatingMode,
    ProviderDefinition,
    RuntimePolicy,
)


def test_default_policy_is_local_and_zero_cost() -> None:
    policy = RuntimePolicy()

    assert policy.operating_mode is OperatingMode.FULLY_LOCAL
    assert policy.budget.maximum_llm_calls == 12
    assert policy.budget.maximum_cost_usd == 0
    assert CostClass.CHEAP_PAID not in policy.allowed_cost_classes


def test_local_mode_rejects_hosted_cost_class() -> None:
    with pytest.raises(ValidationError, match="cannot allow hosted cost classes"):
        RuntimePolicy(allowed_cost_classes=frozenset({CostClass.LOCAL, CostClass.HOSTED_FREE_TIER}))


def test_zero_budget_rejects_paid_provider_class() -> None:
    with pytest.raises(ValidationError, match="paid providers require"):
        RuntimePolicy(
            operating_mode=OperatingMode.HYBRID,
            allowed_cost_classes=frozenset({CostClass.LOCAL, CostClass.CHEAP_PAID}),
            budget=ExecutionBudget(maximum_cost_usd=0),
        )


def test_disabled_disallowed_provider_is_permitted() -> None:
    policy = RuntimePolicy(
        providers=(
            ProviderDefinition(
                provider_id="future-hosted-provider",
                cost_class=CostClass.PREMIUM_PAID,
                enabled=False,
            ),
        )
    )

    assert not policy.providers[0].enabled


def test_enabled_disallowed_provider_is_rejected() -> None:
    with pytest.raises(ValidationError, match="disallowed by mode policy"):
        RuntimePolicy(
            providers=(
                ProviderDefinition(
                    provider_id="hosted-provider",
                    cost_class=CostClass.PREMIUM_PAID,
                    enabled=True,
                ),
            )
        )


def test_provider_identifiers_are_unique() -> None:
    provider = ProviderDefinition(
        provider_id="local-model",
        cost_class=CostClass.LOCAL,
    )

    with pytest.raises(ValidationError, match="provider_id values must be unique"):
        RuntimePolicy(providers=(provider, provider))


def test_budget_rejects_unbounded_research_rounds() -> None:
    with pytest.raises(ValidationError):
        ExecutionBudget(maximum_research_rounds=100)
