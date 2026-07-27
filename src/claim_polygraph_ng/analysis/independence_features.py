"""Transparent independence features with explicit uncertainty bounds."""

from enum import StrEnum

from pydantic import Field

from claim_polygraph_ng.analysis.evidence_families import EvidenceFamilyInference
from claim_polygraph_ng.domain.base import DomainModel

INDEPENDENCE_FEATURE_VERSION = "independence-bounds-v1"


class IndependenceRequirementState(StrEnum):
    """Whether a family requirement is proven, disproven, or unresolved."""

    MET = "met"
    NOT_MET = "not_met"
    UNCERTAIN = "uncertain"


class IndependenceFeatures(DomainModel):
    """Reportable features; deliberately not a confidence or truth score."""

    component_id: str
    raw_source_count: int = Field(ge=0)
    grouped_family_count: int = Field(ge=0)
    confirmed_independent_lower_bound: int = Field(ge=0)
    possible_independent_upper_bound: int = Field(ge=0)
    unresolved_dependency_count: int = Field(ge=0)
    dependent_repetition_count: int = Field(ge=0)
    uncertainty_width: int = Field(ge=0)
    required_independent_families: int = Field(ge=1)
    requirement_state: IndependenceRequirementState
    feature_version: str = INDEPENDENCE_FEATURE_VERSION
    confidence_score: None = None
    limitations: tuple[str, ...]


def calculate_independence_features(
    inference: EvidenceFamilyInference,
    *,
    raw_source_count: int,
    required_independent_families: int,
) -> IndependenceFeatures:
    """Calculate bounds without converting unknown dependency into independence."""
    if raw_source_count < inference.possible_independent_upper_bound:
        raise ValueError("raw source count cannot be below the family upper bound")
    lower = inference.confirmed_independent_lower_bound
    upper = inference.possible_independent_upper_bound
    if lower >= required_independent_families:
        state = IndependenceRequirementState.MET
    elif upper < required_independent_families:
        state = IndependenceRequirementState.NOT_MET
    else:
        state = IndependenceRequirementState.UNCERTAIN
    return IndependenceFeatures(
        component_id=inference.component_id,
        raw_source_count=raw_source_count,
        grouped_family_count=len(inference.families),
        confirmed_independent_lower_bound=lower,
        possible_independent_upper_bound=upper,
        unresolved_dependency_count=inference.unresolved_pair_count,
        dependent_repetition_count=raw_source_count - len(inference.families),
        uncertainty_width=upper - lower,
        required_independent_families=required_independent_families,
        requirement_state=state,
        limitations=(
            "Unknown dependency contributes to the upper bound but not the confirmed lower bound.",
            "These features do not determine claim truth or verdict confidence.",
        ),
    )
