"""Evaluate explicit provenance-link extraction on the locked fixture."""

import json
from pathlib import Path

from pydantic import Field

from claim_polygraph_ng.analysis.provenance_links import (
    ExtractedProvenanceLink,
    ProvenanceLinkType,
    extract_provenance_links,
)
from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.evaluation.phase5_manifest import (
    ProvenanceBenchmark,
    ProvenanceRelationship,
)


class ProvenanceLinkPairResult(DomainModel):
    case_id: str
    relationship: ProvenanceRelationship
    expected_explicit_link: bool
    predicted_explicit_link: bool
    correct: bool
    extracted_links: tuple[ExtractedProvenanceLink, ...]


class ProvenanceLinkEvaluation(DomainModel):
    dataset_id: str
    dataset_version: int
    pair_count: int = Field(ge=0)
    extracted_link_count: int = Field(ge=0)
    unresolved_link_count: int = Field(ge=0)
    true_positive_count: int = Field(ge=0)
    false_positive_count: int = Field(ge=0)
    false_negative_count: int = Field(ge=0)
    precision: float | None = Field(default=None, ge=0, le=1)
    recall: float | None = Field(default=None, ge=0, le=1)
    offsets_valid: bool
    retrieval_call_count: int = Field(ge=0)
    valid: bool
    results: tuple[ProvenanceLinkPairResult, ...]


def evaluate_provenance_links(
    benchmark: ProvenanceBenchmark,
    *,
    required_precision: float = 0.9,
) -> ProvenanceLinkEvaluation:
    """Score explicit relationship signals without resolving targets."""
    sources = {source.source_id: source for case in benchmark.cases for source in case.sources}
    results = []
    for case in benchmark.cases:
        for relationship in case.expected_relationships:
            left = sources[relationship.left_source_id]
            right = sources[relationship.right_source_id]
            links = (
                *extract_provenance_links(left.source_id, left.excerpt),
                *extract_provenance_links(right.source_id, right.excerpt),
            )
            expected_types = _expected_link_types(relationship)
            predicted = any(item.link_type in expected_types for item in links)
            expected = bool(expected_types)
            results.append(
                ProvenanceLinkPairResult(
                    case_id=case.case_id,
                    relationship=relationship.relationship,
                    expected_explicit_link=expected,
                    predicted_explicit_link=predicted,
                    correct=expected == predicted,
                    extracted_links=links,
                )
            )
    tp = sum(item.expected_explicit_link and item.predicted_explicit_link for item in results)
    fp = sum(not item.expected_explicit_link and item.predicted_explicit_link for item in results)
    fn = sum(item.expected_explicit_link and not item.predicted_explicit_link for item in results)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    all_links = tuple(link for result in results for link in result.extracted_links)
    offsets_valid = all(
        sources[link.source_id].excerpt[link.start_char : link.end_char] == link.exact_text
        for link in all_links
    )
    valid = (
        precision is not None
        and precision >= required_precision
        and offsets_valid
        and all(not link.retrieval_authorized for link in all_links)
    )
    return ProvenanceLinkEvaluation(
        dataset_id=benchmark.dataset_id,
        dataset_version=benchmark.version,
        pair_count=len(results),
        extracted_link_count=len(all_links),
        unresolved_link_count=sum(link.resolved_source_id is None for link in all_links),
        true_positive_count=tp,
        false_positive_count=fp,
        false_negative_count=fn,
        precision=precision,
        recall=recall,
        offsets_valid=offsets_valid,
        retrieval_call_count=0,
        valid=valid,
        results=tuple(results),
    )


def export_provenance_link_evaluation(
    evaluation: ProvenanceLinkEvaluation, path: str | Path
) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evaluation.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output


def _expected_link_types(relationship) -> set[ProvenanceLinkType]:
    if relationship.relationship is ProvenanceRelationship.SUMMARY_OF:
        return {ProvenanceLinkType.SUMMARY_OF}
    if relationship.relationship is ProvenanceRelationship.CITES:
        return {
            ProvenanceLinkType.CITES,
            ProvenanceLinkType.CONTROLLING_REFERENCE,
        }
    if (
        relationship.relationship is ProvenanceRelationship.COMMON_ORIGIN
        and relationship.same_evidence_family
    ):
        return {ProvenanceLinkType.COMMON_ANNOUNCEMENT}
    return set()
