"""Locked evaluation for Stage 5.4 derivative detection."""

import json
from datetime import date
from pathlib import Path

from pydantic import Field

from claim_polygraph_ng.analysis.near_duplicates import (
    NearDuplicateLabel,
    assess_near_duplicate,
)
from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.evaluation.phase5_manifest import (
    ProvenanceBenchmark,
    ProvenanceRelationship,
)

_POSITIVE = {
    ProvenanceRelationship.SUMMARY_OF,
    ProvenanceRelationship.CITES,
}
_EXCLUDED = {
    ProvenanceRelationship.SAME_DOCUMENT,
    ProvenanceRelationship.MIRROR,
    ProvenanceRelationship.SYNDICATED_COPY,
    ProvenanceRelationship.TRANSLATION,
    ProvenanceRelationship.UNRESOLVED,
}


class NearDuplicatePairResult(DomainModel):
    case_id: str
    relationship: ProvenanceRelationship
    expected_derivative: bool
    predicted_derivative: bool
    label: NearDuplicateLabel
    correct: bool


class NearDuplicateEvaluation(DomainModel):
    dataset_id: str
    dataset_version: int
    evaluated_pair_count: int = Field(ge=0)
    excluded_pair_count: int = Field(ge=0)
    true_positive_count: int = Field(ge=0)
    false_positive_count: int = Field(ge=0)
    false_negative_count: int = Field(ge=0)
    precision: float | None = Field(default=None, ge=0, le=1)
    recall: float | None = Field(default=None, ge=0, le=1)
    precision_gate_passed: bool
    recall_gate_passed: bool
    automatic_independence_use_allowed: bool
    valid: bool
    results: tuple[NearDuplicatePairResult, ...]
    exclusions: tuple[str, ...]


def evaluate_near_duplicates(
    benchmark: ProvenanceBenchmark,
    *,
    required_precision: float,
    required_recall: float,
) -> NearDuplicateEvaluation:
    sources = {source.source_id: source for case in benchmark.cases for source in case.sources}
    results = []
    excluded = []
    for case in benchmark.cases:
        for relationship in case.expected_relationships:
            if relationship.relationship in _EXCLUDED:
                excluded.append(f"{case.case_id}:{relationship.relationship.value}")
                continue
            left = sources[relationship.left_source_id]
            right = sources[relationship.right_source_id]
            assessment = assess_near_duplicate(
                left_record_id=left.source_id,
                left_text=left.excerpt,
                right_record_id=right.source_id,
                right_text=right.excerpt,
                left_published=date.fromisoformat(left.published_at),
                right_published=date.fromisoformat(right.published_at),
            )
            # Common-origin cases are positive only when the reviewed family label says the
            # reports are dependent. Shared data with independent analysis remains negative.
            expected = relationship.relationship in _POSITIVE or (
                relationship.relationship is ProvenanceRelationship.COMMON_ORIGIN
                and relationship.same_evidence_family
            )
            predicted = assessment.label is NearDuplicateLabel.LIKELY_DERIVATIVE
            results.append(
                NearDuplicatePairResult(
                    case_id=case.case_id,
                    relationship=relationship.relationship,
                    expected_derivative=expected,
                    predicted_derivative=predicted,
                    label=assessment.label,
                    correct=expected == predicted,
                )
            )
    tp = sum(item.expected_derivative and item.predicted_derivative for item in results)
    fp = sum(not item.expected_derivative and item.predicted_derivative for item in results)
    fn = sum(item.expected_derivative and not item.predicted_derivative for item in results)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    precision_passed = precision is not None and precision >= required_precision
    recall_passed = recall is not None and recall >= required_recall
    valid = precision_passed and recall_passed
    return NearDuplicateEvaluation(
        dataset_id=benchmark.dataset_id,
        dataset_version=benchmark.version,
        evaluated_pair_count=len(results),
        excluded_pair_count=len(excluded),
        true_positive_count=tp,
        false_positive_count=fp,
        false_negative_count=fn,
        precision=precision,
        recall=recall,
        precision_gate_passed=precision_passed,
        recall_gate_passed=recall_passed,
        automatic_independence_use_allowed=valid,
        valid=valid,
        results=tuple(results),
        exclusions=tuple(excluded),
    )


def export_near_duplicate_evaluation(evaluation: NearDuplicateEvaluation, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evaluation.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output
