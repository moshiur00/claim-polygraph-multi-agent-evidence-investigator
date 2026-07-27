"""Locked Stage 5.6 evidence-family evaluation."""

import json
from datetime import date
from pathlib import Path

from pydantic import Field

from claim_polygraph_ng.analysis.evidence_families import (
    DependencyStatus,
    FamilySourceRecord,
    infer_evidence_families,
)
from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.evaluation.phase5_manifest import ProvenanceBenchmark


class EvidenceFamilyCaseResult(DomainModel):
    case_id: str
    expected_same_family: bool
    predicted_same_family: bool
    correct: bool
    family_count: int = Field(ge=0)
    dependency_status: DependencyStatus


class EvidenceFamilyEvaluation(DomainModel):
    dataset_id: str
    dataset_version: int
    case_count: int = Field(ge=0)
    correct_count: int = Field(ge=0)
    family_accuracy: float = Field(ge=0, le=1)
    false_independent_count: int = Field(ge=0)
    expected_dependent_count: int = Field(ge=0)
    false_independent_rate: float = Field(ge=0, le=1)
    family_accuracy_gate_passed: bool
    false_independence_gate_passed: bool
    valid: bool
    results: tuple[EvidenceFamilyCaseResult, ...]
    next_action: str


def evaluate_evidence_families(
    benchmark: ProvenanceBenchmark,
    *,
    required_accuracy: float,
    maximum_false_independent_rate: float,
) -> EvidenceFamilyEvaluation:
    results = []
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
        family_by_source = {
            source_id: family.family_id
            for family in inference.families
            for source_id in family.source_ids
        }
        predicted = (
            family_by_source[relationship.left_source_id]
            == family_by_source[relationship.right_source_id]
        )
        results.append(
            EvidenceFamilyCaseResult(
                case_id=case.case_id,
                expected_same_family=relationship.same_evidence_family,
                predicted_same_family=predicted,
                correct=predicted == relationship.same_evidence_family,
                family_count=inference.independent_family_count,
                dependency_status=inference.dependency_edges[0].status,
            )
        )
    correct = sum(item.correct for item in results)
    accuracy = correct / len(results)
    expected_dependent = sum(item.expected_same_family for item in results)
    false_independent = sum(
        item.expected_same_family and not item.predicted_same_family for item in results
    )
    false_independent_rate = false_independent / expected_dependent
    accuracy_passed = accuracy >= required_accuracy
    false_independence_passed = false_independent_rate <= maximum_false_independent_rate
    valid = accuracy_passed and false_independence_passed
    return EvidenceFamilyEvaluation(
        dataset_id=benchmark.dataset_id,
        dataset_version=benchmark.version,
        case_count=len(results),
        correct_count=correct,
        family_accuracy=accuracy,
        false_independent_count=false_independent,
        expected_dependent_count=expected_dependent,
        false_independent_rate=false_independent_rate,
        family_accuracy_gate_passed=accuracy_passed,
        false_independence_gate_passed=false_independence_passed,
        valid=valid,
        results=tuple(results),
        next_action=(
            "Proceed to independence features."
            if valid
            else "Run the bounded Stage 5.7 classifier only on unresolved candidate pairs."
        ),
    )


def export_evidence_family_evaluation(
    evaluation: EvidenceFamilyEvaluation, path: str | Path
) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evaluation.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output
