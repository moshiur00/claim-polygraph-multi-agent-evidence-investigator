"""Evaluate Stage 5.1 URL canonicalization on the locked fixture."""

import json
from pathlib import Path

from pydantic import Field

from claim_polygraph_ng.analysis.canonicalization import (
    CANONICALIZATION_VERSION,
    canonicalize_url,
)
from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.evaluation.phase5_manifest import ProvenanceBenchmark


class CanonicalizationCaseResult(DomainModel):
    case_id: str
    left_source_id: str
    right_source_id: str
    expected_same: bool
    predicted_same: bool
    correct: bool
    left_canonical_url: str
    right_canonical_url: str


class CanonicalizationEvaluation(DomainModel):
    dataset_id: str
    dataset_version: int
    canonicalization_version: str
    pair_count: int = Field(ge=0)
    true_positive_count: int = Field(ge=0)
    false_positive_count: int = Field(ge=0)
    false_negative_count: int = Field(ge=0)
    true_negative_count: int = Field(ge=0)
    precision: float | None = Field(default=None, ge=0, le=1)
    recall: float | None = Field(default=None, ge=0, le=1)
    valid: bool
    results: tuple[CanonicalizationCaseResult, ...]
    limitations: tuple[str, ...]


def evaluate_canonicalization(
    benchmark: ProvenanceBenchmark, *, required_precision: float
) -> CanonicalizationEvaluation:
    """Score URL equality conservatively; mirrors remain a later relationship task."""
    source_lookup = {
        source.source_id: source for case in benchmark.cases for source in case.sources
    }
    results = []
    for case in benchmark.cases:
        for relationship in case.expected_relationships:
            left = canonicalize_url(source_lookup[relationship.left_source_id].url)
            right = canonicalize_url(source_lookup[relationship.right_source_id].url)
            predicted = left.canonical_value == right.canonical_value
            results.append(
                CanonicalizationCaseResult(
                    case_id=case.case_id,
                    left_source_id=relationship.left_source_id,
                    right_source_id=relationship.right_source_id,
                    expected_same=relationship.same_canonical_document,
                    predicted_same=predicted,
                    correct=predicted == relationship.same_canonical_document,
                    left_canonical_url=left.canonical_value,
                    right_canonical_url=right.canonical_value,
                )
            )
    tp = sum(item.expected_same and item.predicted_same for item in results)
    fp = sum(not item.expected_same and item.predicted_same for item in results)
    fn = sum(item.expected_same and not item.predicted_same for item in results)
    tn = sum(not item.expected_same and not item.predicted_same for item in results)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return CanonicalizationEvaluation(
        dataset_id=benchmark.dataset_id,
        dataset_version=benchmark.version,
        canonicalization_version=CANONICALIZATION_VERSION,
        pair_count=len(results),
        true_positive_count=tp,
        false_positive_count=fp,
        false_negative_count=fn,
        true_negative_count=tn,
        precision=precision,
        recall=recall,
        valid=precision is not None and precision >= required_precision,
        results=tuple(results),
        limitations=(
            "Cross-host mirrors require explicit provenance signals and are not merged by URL "
            "normalization alone.",
            "Language-path removal is conservative but must be disabled for sites where the "
            "language path identifies materially different documents.",
        ),
    )


def export_canonicalization_evaluation(
    evaluation: CanonicalizationEvaluation, path: str | Path
) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evaluation.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output
