"""Bounded Stage 5.7 classifier and post-classification gate audit."""

import json
from enum import StrEnum
from pathlib import Path

from pydantic import Field

from claim_polygraph_ng.domain import ModelCallUsage
from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.evaluation.phase5_evidence_families import (
    EvidenceFamilyEvaluation,
)


class AmbiguousDependencyLabel(StrEnum):
    """Allowed model result for one deterministically unresolved pair."""

    LIKELY_DEPENDENT = "likely_dependent"
    LIKELY_INDEPENDENT = "likely_independent"
    UNKNOWN = "unknown"


class AmbiguousDependencyClassification(DomainModel):
    """Schema-constrained semantic comparison with no application-owned IDs."""

    label: AmbiguousDependencyLabel
    confidence: float = Field(ge=0, le=1)
    shared_assertions: tuple[str, ...]
    dependency_evidence: tuple[str, ...]
    independence_evidence: tuple[str, ...]
    explanation: str = Field(min_length=20, max_length=2_000)
    human_review_required: bool


class AmbiguousClassifierPreflight(DomainModel):
    """Zero-cost authorization boundary for Stage 5.7."""

    eligible_case_ids: tuple[str, ...]
    eligible_pair_count: int = Field(ge=0)
    maximum_model_calls: int = Field(ge=0)
    maximum_cost_usd: float = Field(ge=0)
    mock_schema_valid: bool
    paid_call_authorized: bool = False
    valid: bool


class Phase5ClassifierResult(DomainModel):
    """Stored single-call output and recomputed family gate."""

    case_id: str
    model: str
    call_count: int = Field(ge=0, le=1)
    estimated_cost_usd: float = Field(ge=0)
    maximum_cost_usd: float = Field(ge=0)
    usage: ModelCallUsage
    classification: AmbiguousDependencyClassification
    post_family_accuracy: float = Field(ge=0, le=1)
    post_false_independent_rate: float = Field(ge=0, le=1)
    family_accuracy_gate_passed: bool
    false_independence_gate_passed: bool
    valid: bool
    retrieval_call_count: int = Field(default=0, ge=0)
    limitations: tuple[str, ...]


def build_classifier_preflight(
    baseline: EvidenceFamilyEvaluation,
    *,
    maximum_cost_usd: float = 0.01,
) -> AmbiguousClassifierPreflight:
    eligible = tuple(
        result.case_id
        for result in baseline.results
        if result.dependency_status.value == "unknown" and not result.correct
    )
    mock = AmbiguousDependencyClassification(
        label=AmbiguousDependencyLabel.UNKNOWN,
        confidence=0,
        shared_assertions=(),
        dependency_evidence=(),
        independence_evidence=(),
        explanation="The mock preflight preserves uncertainty and performs no provider call.",
        human_review_required=True,
    )
    return AmbiguousClassifierPreflight(
        eligible_case_ids=eligible,
        eligible_pair_count=len(eligible),
        maximum_model_calls=1,
        maximum_cost_usd=maximum_cost_usd,
        mock_schema_valid=bool(mock.explanation),
        valid=len(eligible) == 1 and eligible == ("PROV-012",),
    )


def audit_classifier_result(
    *,
    baseline: EvidenceFamilyEvaluation,
    case_id: str,
    classification: AmbiguousDependencyClassification,
    usage: ModelCallUsage,
    maximum_cost_usd: float,
    required_accuracy: float,
    maximum_false_independent_rate: float,
) -> Phase5ClassifierResult:
    """Recompute only the one stored unresolved result, with no provider call."""
    if usage.estimated_cost_usd is None:
        raise ValueError("model usage must include an estimated cost")
    if usage.estimated_cost_usd > maximum_cost_usd:
        raise ValueError("model call exceeded the hard Stage 5.7 cost ceiling")
    results = list(baseline.results)
    target = next((item for item in results if item.case_id == case_id), None)
    if target is None or target.dependency_status.value != "unknown":
        raise ValueError("classifier output can update only a stored unresolved case")
    predicted_same = classification.label is AmbiguousDependencyLabel.LIKELY_DEPENDENT
    corrected = target.model_copy(
        update={
            "predicted_same_family": predicted_same,
            "correct": predicted_same == target.expected_same_family,
        }
    )
    results[results.index(target)] = corrected
    accuracy = sum(item.correct for item in results) / len(results)
    expected_dependent = sum(item.expected_same_family for item in results)
    false_independent = sum(
        item.expected_same_family and not item.predicted_same_family for item in results
    )
    false_rate = false_independent / expected_dependent
    accuracy_passed = accuracy >= required_accuracy
    false_passed = false_rate <= maximum_false_independent_rate
    return Phase5ClassifierResult(
        case_id=case_id,
        model=usage.model,
        call_count=1,
        estimated_cost_usd=usage.estimated_cost_usd,
        maximum_cost_usd=maximum_cost_usd,
        usage=usage,
        classification=classification,
        post_family_accuracy=accuracy,
        post_false_independent_rate=false_rate,
        family_accuracy_gate_passed=accuracy_passed,
        false_independence_gate_passed=false_passed,
        valid=accuracy_passed and false_passed,
        limitations=(
            "The classifier was evaluated on one predeclared unresolved synthetic pair.",
            "The result may not be generalized to deterministically resolved pairs.",
            "No retrieval, URL resolution, or evidence creation was permitted.",
        ),
    )


def export_ambiguous_classifier_artifact(artifact: DomainModel, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(artifact.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output
