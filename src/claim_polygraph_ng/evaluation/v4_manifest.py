"""Frozen contracts for Verification Construction V4 governance."""

import hashlib
from enum import StrEnum
from pathlib import Path

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel


class V4FailureLayer(StrEnum):
    ELIGIBILITY = "eligibility"
    EXTRACTION = "extraction"
    CONSTRUCTION = "construction"
    VALIDATION = "validation"
    OBSERVABILITY = "observability"


class V4FailureCategory(DomainModel):
    category_id: str = Field(pattern=r"^V4-F[0-9]{2}$")
    layer: V4FailureLayer
    name: str = Field(min_length=3, max_length=100)
    remediation_contract: str = Field(min_length=10, max_length=500)
    synthetic_fixture_required: bool = True
    may_use_v3_held_out_text: bool = False


class V4Budget(DomainModel):
    stage_v4_0_model_calls: int = Field(ge=0)
    stage_v4_0_network_calls: int = Field(ge=0)
    stage_v4_0_search_calls: int = Field(ge=0)
    stage_v4_0_paid_operations: int = Field(ge=0)
    maximum_synthetic_canary_calls: int = Field(ge=0, le=2)
    maximum_development_calls: int = Field(ge=0, le=20)
    maximum_calibration_calls: int = Field(ge=0, le=20)
    maximum_held_out_calls: int = Field(ge=0, le=20)
    maximum_total_calls: int = Field(ge=0, le=62)
    maximum_input_tokens_per_call: int = Field(ge=1)
    maximum_output_tokens_per_call: int = Field(ge=1)
    maximum_total_cost_usd: float = Field(ge=0)
    maximum_cost_per_recovered_assertion_usd: float = Field(ge=0)
    retries_after_valid_paid_receipt: int = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_budget(self) -> "V4Budget":
        if any(
            (
                self.stage_v4_0_model_calls,
                self.stage_v4_0_network_calls,
                self.stage_v4_0_search_calls,
                self.stage_v4_0_paid_operations,
            )
        ):
            raise ValueError("V4.0 must remain zero-cost and offline")
        allocated = (
            self.maximum_synthetic_canary_calls
            + self.maximum_development_calls
            + self.maximum_calibration_calls
            + self.maximum_held_out_calls
        )
        if allocated != self.maximum_total_calls:
            raise ValueError("V4 call allocations must equal the total call budget")
        return self


class V4OfflineGates(DomainModel):
    minimum_constructible_eligibility_recall: float = Field(ge=0, le=1)
    minimum_negative_exclusion_precision: float = Field(ge=0, le=1)
    minimum_compound_operand_preservation: float = Field(ge=0, le=1)
    minimum_exact_span_validity: float = Field(ge=0, le=1)
    minimum_schema_validity: float = Field(ge=0, le=1)
    maximum_unsafe_accepted_constructions: int = Field(ge=0)
    minimum_human_review_routing_recall: float = Field(ge=0, le=1)
    maximum_publication_safety_regressions: int = Field(ge=0)
    maximum_duplicate_paid_operations: int = Field(ge=0)
    minimum_failed_response_cost_observability: float = Field(ge=0, le=1)
    maximum_v3_held_out_texts_loaded: int = Field(ge=0)
    cancellation_before_reservation_required: bool
    restart_reconstruction_required: bool


class V4FrozenArtifact(DomainModel):
    path: str = Field(min_length=1, max_length=500)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class V4StageZeroManifest(DomainModel):
    manifest_id: str = Field(
        pattern=r"^verification-construction-v4-stage0-manifest-v1$"
    )
    schema_version: int = 1
    status: str = Field(pattern=r"^frozen$")
    plan: V4FrozenArtifact
    failure_taxonomy: V4FrozenArtifact
    dataset_nonreuse_policy: V4FrozenArtifact
    predecessor_closure: V4FrozenArtifact
    contract: V4FrozenArtifact
    budget: V4Budget
    offline_promotion_gates: V4OfflineGates
    provider_selected: bool
    model_calls: int = Field(ge=0)
    network_calls: int = Field(ge=0)
    search_calls: int = Field(ge=0)
    paid_operations: int = Field(ge=0)
    fresh_calibration_cases_collected: int = Field(ge=0)
    fresh_held_out_cases_collected: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_freeze(self) -> "V4StageZeroManifest":
        if self.provider_selected:
            raise ValueError("provider selection is outside V4.0")
        if any(
            (
                self.model_calls,
                self.network_calls,
                self.search_calls,
                self.paid_operations,
                self.fresh_calibration_cases_collected,
                self.fresh_held_out_cases_collected,
            )
        ):
            raise ValueError("V4.0 cannot perform calls or collect evaluation data")
        return self


def verify_v4_manifest(
    manifest: V4StageZeroManifest, project_root: str | Path
) -> tuple[str, ...]:
    root = Path(project_root).resolve()
    errors = []
    for artifact in (
        manifest.plan,
        manifest.failure_taxonomy,
        manifest.dataset_nonreuse_policy,
        manifest.predecessor_closure,
        manifest.contract,
    ):
        candidate = (root / artifact.path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            errors.append(f"path escapes project root: {artifact.path}")
            continue
        if not candidate.is_file():
            errors.append(f"missing artifact: {artifact.path}")
        elif hashlib.sha256(candidate.read_bytes()).hexdigest() != artifact.sha256:
            errors.append(f"SHA-256 mismatch: {artifact.path}")
    return tuple(errors)
