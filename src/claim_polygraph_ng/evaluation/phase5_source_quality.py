"""Structural evaluation of Stage 5.2 source-quality output."""

import json
from pathlib import Path

from pydantic import Field

from claim_polygraph_ng.analysis.source_quality import (
    QualityFinding,
    SourceQualityMetadata,
    assess_source_quality,
)
from claim_polygraph_ng.domain import SourceType
from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.evaluation.phase5_manifest import ProvenanceBenchmark


class SourceQualityFixtureResult(DomainModel):
    case_id: str
    source_id: str
    dimension_count: int = Field(ge=0)
    unknown_count: int = Field(ge=0)
    all_reasons_present: bool
    aggregate_score_present: bool


class SourceQualityEvaluation(DomainModel):
    dataset_id: str
    dataset_version: int
    source_count: int = Field(ge=0)
    complete_assessment_rate: float = Field(ge=0, le=1)
    explained_dimension_rate: float = Field(ge=0, le=1)
    unknown_preservation_rate: float = Field(ge=0, le=1)
    aggregate_score_count: int = Field(ge=0)
    valid: bool
    results: tuple[SourceQualityFixtureResult, ...]
    limitations: tuple[str, ...]


def evaluate_source_quality_structure(
    benchmark: ProvenanceBenchmark,
) -> SourceQualityEvaluation:
    """Ensure sparse fixture metadata is explained rather than guessed."""
    results = []
    for case in benchmark.cases:
        for source in case.sources:
            assessment = assess_source_quality(
                SourceQualityMetadata(
                    source_type=SourceType.OTHER,
                    publisher_identified=bool(source.publisher),
                    author_identified=False,
                    publication_date=source.published_at,
                )
            )
            unknown = sum(item.finding is QualityFinding.UNKNOWN for item in assessment.dimensions)
            results.append(
                SourceQualityFixtureResult(
                    case_id=case.case_id,
                    source_id=source.source_id,
                    dimension_count=len(assessment.dimensions),
                    unknown_count=unknown,
                    all_reasons_present=all(bool(item.reason) for item in assessment.dimensions),
                    aggregate_score_present="score" in assessment.model_fields_set,
                )
            )
    count = len(results)
    complete = sum(item.dimension_count == 8 for item in results) / count
    explained = sum(item.all_reasons_present for item in results) / count
    unknown_preserved = sum(item.unknown_count > 0 for item in results) / count
    score_count = sum(item.aggregate_score_present for item in results)
    return SourceQualityEvaluation(
        dataset_id=benchmark.dataset_id,
        dataset_version=benchmark.version,
        source_count=count,
        complete_assessment_rate=complete,
        explained_dimension_rate=explained,
        unknown_preservation_rate=unknown_preserved,
        aggregate_score_count=score_count,
        valid=complete == 1 and explained == 1 and unknown_preserved == 1 and score_count == 0,
        results=tuple(results),
        limitations=(
            "The locked provenance fixture has not yet been annotated for quality dimensions.",
            "This stage validates typed output and conservative unknown handling, not agreement "
            "with human quality judgments.",
        ),
    )


def export_source_quality_evaluation(evaluation: SourceQualityEvaluation, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evaluation.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output
