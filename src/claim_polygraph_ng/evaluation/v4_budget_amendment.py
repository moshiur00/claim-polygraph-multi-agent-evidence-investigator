"""Non-destructive amendments to the frozen V4 execution budget."""

from __future__ import annotations

import hashlib
from pathlib import Path

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel


class V4AmendedBudget(DomainModel):
    maximum_synthetic_canary_calls: int = Field(ge=0, le=4)
    maximum_development_calls: int = Field(ge=0, le=20)
    maximum_calibration_calls: int = Field(ge=0, le=20)
    maximum_held_out_calls: int = Field(ge=0, le=20)
    maximum_total_calls: int = Field(ge=0, le=62)
    maximum_input_tokens_per_call: int = Field(ge=1, le=6000)
    maximum_output_tokens_per_call: int = Field(ge=1, le=900)
    maximum_total_cost_usd: float = Field(ge=0, le=1.25)
    retries_after_valid_paid_receipt: int = Field(ge=0, le=0)

    @model_validator(mode="after")
    def preserve_total_allocation(self) -> V4AmendedBudget:
        allocated = (
            self.maximum_synthetic_canary_calls
            + self.maximum_development_calls
            + self.maximum_calibration_calls
            + self.maximum_held_out_calls
        )
        if allocated != self.maximum_total_calls:
            raise ValueError("amended V4 allocations must equal the total")
        return self


class V4CanaryBudgetAmendment(DomainModel):
    amendment_id: str = Field(pattern=r"^verification-construction-v4-canary-budget-amendment-v1$")
    status: str = Field(pattern=r"^frozen$")
    predecessor_manifest_path: str
    predecessor_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    effective_budget: V4AmendedBudget
    synthetic_calls_consumed: int = Field(ge=0, le=4)
    synthetic_calls_remaining: int = Field(ge=0, le=4)
    consumed_cost_usd: float = Field(ge=0)
    final_canary_authorized: bool
    final_canary_maximum_calls: int = Field(ge=0, le=1)
    authorization_scope: str = Field(min_length=20, max_length=500)
    model_calls_during_amendment: int = Field(ge=0, le=0)
    network_calls_during_amendment: int = Field(ge=0, le=0)
    paid_operations_during_amendment: int = Field(ge=0, le=0)

    @model_validator(mode="after")
    def validate_amendment(self) -> V4CanaryBudgetAmendment:
        if (
            self.synthetic_calls_consumed + self.synthetic_calls_remaining
            != self.effective_budget.maximum_synthetic_canary_calls
        ):
            raise ValueError("consumed and remaining canary calls must match allocation")
        if self.final_canary_authorized != bool(self.final_canary_maximum_calls):
            raise ValueError("final canary authorization is inconsistent")
        if self.final_canary_maximum_calls > self.synthetic_calls_remaining:
            raise ValueError("final canary exceeds the remaining allocation")
        if self.consumed_cost_usd > self.effective_budget.maximum_total_cost_usd:
            raise ValueError("consumed cost exceeds the unchanged V4 ceiling")
        return self


def verify_v4_budget_amendment(
    amendment: V4CanaryBudgetAmendment,
    project_root: str | Path,
) -> tuple[str, ...]:
    root = Path(project_root).resolve()
    predecessor = (root / amendment.predecessor_manifest_path).resolve()
    try:
        predecessor.relative_to(root)
    except ValueError:
        return ("predecessor manifest escapes project root",)
    if not predecessor.is_file():
        return ("predecessor manifest is missing",)
    if hashlib.sha256(predecessor.read_bytes()).hexdigest() != (
        amendment.predecessor_manifest_sha256
    ):
        return ("predecessor manifest hash mismatch",)
    return ()
