"""Locked Stage 5.8 evaluation of uncertainty-aware independence features."""

import json
from datetime import date
from pathlib import Path

from pydantic import Field

from claim_polygraph_ng.analysis.evidence_families import (
    FamilySourceRecord,
    infer_evidence_families,
)
from claim_polygraph_ng.analysis.independence_features import (
    IndependenceRequirementState,
    calculate_independence_features,
)
from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.evaluation.phase5_manifest import ProvenanceBenchmark


class IndependenceFeatureCaseResult(DomainModel):
    case_id: str
    expected_same_family: bool
    lower_bound: int = Field(ge=1)
    upper_bound: int = Field(ge=1)
    unresolved_count: int = Field(ge=0)
    requirement_state: IndependenceRequirementState
    false_confirmed_independence: bool


class IndependenceFeatureEvaluation(DomainModel):
    dataset_id: str
    dataset_version: int
    case_count: int = Field(ge=0)
    false_confirmed_independent_count: int = Field(ge=0)
    expected_dependent_count: int = Field(ge=0)
    false_confirmed_independent_rate: float = Field(ge=0, le=1)
    unknown_pairs_counted_as_confirmed: int = Field(ge=0)
    family_accuracy: float = Field(ge=0, le=1)
    family_accuracy_gate_passed: bool
    false_independence_gate_passed: bool
    valid: bool
    results: tuple[IndependenceFeatureCaseResult, ...]


def evaluate_independence_features(
    benchmark: ProvenanceBenchmark,
    *,
    required_family_accuracy: float,
    maximum_false_independent_rate: float,
) -> IndependenceFeatureEvaluation:
    results = []
    correct_families = 0
    for case in benchmark.cases:
        relationship = case.expected_relationships[0]
        inference = infer_evidence_families(
            case.case_id,
            tuple(
                FamilySourceRecord(
                    source_id=source.source_id,
                    url=source.url,
                    text=source.excerpt,
                    published_at=date.fromisoformat(source.published_at),
                )
                for source in case.sources
            ),
        )
        predicted_same = len(inference.families) == 1
        correct_families += predicted_same == relationship.same_evidence_family
        features = calculate_independence_features(
            inference,
            raw_source_count=len(case.sources),
            required_independent_families=2,
        )
        false_confirmed = (
            relationship.same_evidence_family and features.confirmed_independent_lower_bound >= 2
        )
        results.append(
            IndependenceFeatureCaseResult(
                case_id=case.case_id,
                expected_same_family=relationship.same_evidence_family,
                lower_bound=features.confirmed_independent_lower_bound,
                upper_bound=features.possible_independent_upper_bound,
                unresolved_count=features.unresolved_dependency_count,
                requirement_state=features.requirement_state,
                false_confirmed_independence=false_confirmed,
            )
        )
    expected_dependent = sum(item.expected_same_family for item in results)
    false_count = sum(item.false_confirmed_independence for item in results)
    false_rate = false_count / expected_dependent
    family_accuracy = correct_families / len(results)
    accuracy_passed = family_accuracy >= required_family_accuracy
    false_passed = false_rate <= maximum_false_independent_rate
    unknown_counted = sum(
        item.unresolved_count > 0 and item.lower_bound == item.upper_bound for item in results
    )
    return IndependenceFeatureEvaluation(
        dataset_id=benchmark.dataset_id,
        dataset_version=benchmark.version,
        case_count=len(results),
        false_confirmed_independent_count=false_count,
        expected_dependent_count=expected_dependent,
        false_confirmed_independent_rate=false_rate,
        unknown_pairs_counted_as_confirmed=unknown_counted,
        family_accuracy=family_accuracy,
        family_accuracy_gate_passed=accuracy_passed,
        false_independence_gate_passed=false_passed,
        valid=accuracy_passed and false_passed and unknown_counted == 0,
        results=tuple(results),
    )


def export_independence_feature_evaluation(
    evaluation: IndependenceFeatureEvaluation, path: str | Path
) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evaluation.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output
