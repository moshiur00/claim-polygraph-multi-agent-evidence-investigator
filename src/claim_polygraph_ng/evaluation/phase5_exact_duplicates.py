"""Evaluate exact duplicate detection on the locked Phase 5 fixture."""

import json
from pathlib import Path

from pydantic import Field

from claim_polygraph_ng.analysis.exact_duplicates import (
    EXACT_FINGERPRINT_VERSION,
    cluster_exact_duplicates,
)
from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.evaluation.phase5_manifest import (
    ProvenanceBenchmark,
    ProvenanceRelationship,
)

_EXPECTED_EXACT_RELATIONSHIPS = {
    ProvenanceRelationship.SAME_DOCUMENT,
    ProvenanceRelationship.MIRROR,
    ProvenanceRelationship.SYNDICATED_COPY,
}


class ExactDuplicatePairResult(DomainModel):
    case_id: str
    left_source_id: str
    right_source_id: str
    expected_exact: bool
    predicted_exact: bool
    correct: bool


class ExactDuplicateEvaluation(DomainModel):
    dataset_id: str
    dataset_version: int
    fingerprint_version: str
    source_count: int = Field(ge=0)
    cluster_count: int = Field(ge=0)
    pair_count: int = Field(ge=0)
    true_positive_count: int = Field(ge=0)
    false_positive_count: int = Field(ge=0)
    false_negative_count: int = Field(ge=0)
    precision: float | None = Field(default=None, ge=0, le=1)
    recall: float | None = Field(default=None, ge=0, le=1)
    valid: bool
    results: tuple[ExactDuplicatePairResult, ...]


def evaluate_exact_duplicates(
    benchmark: ProvenanceBenchmark,
    *,
    required_precision: float,
    required_recall: float,
) -> ExactDuplicateEvaluation:
    sources = {source.source_id: source for case in benchmark.cases for source in case.sources}
    clusters = cluster_exact_duplicates(
        tuple((source_id, source.excerpt) for source_id, source in sources.items())
    )
    cluster_by_source = {
        member: cluster.cluster_id for cluster in clusters for member in cluster.member_ids
    }
    results = []
    for case in benchmark.cases:
        for relationship in case.expected_relationships:
            expected = relationship.relationship in _EXPECTED_EXACT_RELATIONSHIPS
            predicted = relationship.left_source_id in cluster_by_source and cluster_by_source.get(
                relationship.left_source_id
            ) == cluster_by_source.get(relationship.right_source_id)
            results.append(
                ExactDuplicatePairResult(
                    case_id=case.case_id,
                    left_source_id=relationship.left_source_id,
                    right_source_id=relationship.right_source_id,
                    expected_exact=expected,
                    predicted_exact=predicted,
                    correct=expected == predicted,
                )
            )
    tp = sum(item.expected_exact and item.predicted_exact for item in results)
    fp = sum(not item.expected_exact and item.predicted_exact for item in results)
    fn = sum(item.expected_exact and not item.predicted_exact for item in results)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    valid = (
        precision is not None
        and recall is not None
        and precision >= required_precision
        and recall >= required_recall
    )
    return ExactDuplicateEvaluation(
        dataset_id=benchmark.dataset_id,
        dataset_version=benchmark.version,
        fingerprint_version=EXACT_FINGERPRINT_VERSION,
        source_count=len(sources),
        cluster_count=len(clusters),
        pair_count=len(results),
        true_positive_count=tp,
        false_positive_count=fp,
        false_negative_count=fn,
        precision=precision,
        recall=recall,
        valid=valid,
        results=tuple(results),
    )


def export_exact_duplicate_evaluation(
    evaluation: ExactDuplicateEvaluation, path: str | Path
) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evaluation.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output
