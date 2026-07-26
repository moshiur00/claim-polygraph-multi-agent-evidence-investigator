"""Validated runtime configuration independent of concrete providers."""

from enum import StrEnum

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel


class OperatingMode(StrEnum):
    """Deployment policy controlling external and paid providers."""

    FULLY_LOCAL = "fully_local"
    HYBRID = "hybrid"
    HOSTED_BENCHMARK = "hosted_benchmark"


class CostClass(StrEnum):
    """Provider cost and locality classification."""

    LOCAL = "local"
    FREE_PUBLIC_API = "free_public_api"
    HOSTED_FREE_TIER = "hosted_free_tier"
    CHEAP_PAID = "cheap_paid"
    PREMIUM_PAID = "premium_paid"


class ExecutionBudget(DomainModel):
    """Hard limits applied to one atomic-claim investigation."""

    maximum_llm_calls: int = Field(default=8, ge=0, le=100)
    maximum_search_calls: int = Field(default=6, ge=1, le=100)
    maximum_pages_fetched: int = Field(default=10, ge=1, le=500)
    maximum_research_rounds: int = Field(default=2, ge=1, le=10)
    maximum_runtime_seconds: int = Field(default=300, ge=10, le=86_400)
    maximum_cost_usd: float = Field(default=0.0, ge=0.0, le=1_000.0)


class ProviderDefinition(DomainModel):
    """Policy-relevant provider metadata."""

    provider_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9_-]+$")
    cost_class: CostClass
    enabled: bool = True


class RuntimePolicy(DomainModel):
    """Mode policy that prevents silent paid or hosted fallback."""

    operating_mode: OperatingMode = OperatingMode.FULLY_LOCAL
    allow_external_free_apis: bool = True
    allowed_cost_classes: frozenset[CostClass] = frozenset(
        {CostClass.LOCAL, CostClass.FREE_PUBLIC_API}
    )
    budget: ExecutionBudget = Field(default_factory=ExecutionBudget)
    providers: tuple[ProviderDefinition, ...] = ()

    @model_validator(mode="after")
    def enforce_mode_policy(self) -> "RuntimePolicy":
        """Reject unsafe or ambiguous mode configurations at startup."""
        paid = {CostClass.CHEAP_PAID, CostClass.PREMIUM_PAID}
        hosted = {
            CostClass.HOSTED_FREE_TIER,
            CostClass.CHEAP_PAID,
            CostClass.PREMIUM_PAID,
        }

        if self.operating_mode is OperatingMode.FULLY_LOCAL:
            if self.allowed_cost_classes & hosted:
                raise ValueError("fully_local mode cannot allow hosted cost classes")
            if not self.allow_external_free_apis and CostClass.FREE_PUBLIC_API in (
                self.allowed_cost_classes
            ):
                raise ValueError(
                    "free public APIs cannot be allowed when external APIs are disabled"
                )
            if self.budget.maximum_cost_usd != 0:
                raise ValueError("fully_local mode requires maximum_cost_usd to be zero")

        if self.budget.maximum_cost_usd == 0 and self.allowed_cost_classes & paid:
            raise ValueError("paid providers require a positive maximum_cost_usd")

        provider_ids = [provider.provider_id for provider in self.providers]
        if len(provider_ids) != len(set(provider_ids)):
            raise ValueError("provider_id values must be unique")

        disallowed_enabled = [
            provider.provider_id
            for provider in self.providers
            if provider.enabled and provider.cost_class not in self.allowed_cost_classes
        ]
        if disallowed_enabled:
            joined = ", ".join(sorted(disallowed_enabled))
            raise ValueError(f"enabled providers are disallowed by mode policy: {joined}")

        return self
