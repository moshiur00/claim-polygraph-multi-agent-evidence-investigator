"""Offline Stage V3.3 deterministic-construction baseline."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from time import perf_counter
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field

from claim_polygraph_ng.analysis.comparative_verification import (
    construct_comparative_assertion,
)
from claim_polygraph_ng.analysis.temporal_construction import (
    construct_temporal_comparison,
)
from claim_polygraph_ng.domain import (
    AssertionConstructionState,
    AtomicClaim,
    Evidence,
    EvidenceStance,
)
from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.evaluation.v3_annotation import load_annotation_workbook
from claim_polygraph_ng.evaluation.v3_manifest import V3ConstructionGoldLabel


class V3DeterministicCaseResult(DomainModel):
    case_id: str
    split: str
    dimension: str
    gold_label: V3ConstructionGoldLabel
    construction_detected: bool
    construction_succeeded: bool
    construction_kind: str | None = None
    construction_state: str | None = None
    approved_evidence_binding_valid: bool | None = None
    exact_span_attribution_available: bool
    human_review_required: bool
    publication_blocked: bool
    unsafe_accepted: bool
    latency_ms: float = Field(ge=0)


class V3DeterministicBaseline(DomainModel):
    evaluation_id: str = "verification-construction-v3-stage3-deterministic-baseline-v1"
    dataset_path: str
    case_count: int
    constructible_gold_count: int
    deterministic_constructible_gold_count: int
    fallback_eligible_gold_count: int
    constructions_detected: int
    constructions_succeeded: int
    true_positive_constructions: int
    false_positive_constructions: int
    construction_recall: float
    deterministic_label_recall: float
    construction_precision: float | None
    exact_evidence_span_validity: float | None
    exact_span_attribution_supported: bool
    unsafe_accepted_constructions: int
    human_review_routing_recall: float
    publication_safety_regressions: int
    publication_blocks: int
    supported_dimension_count: int
    supported_dimensions: tuple[str, ...]
    median_latency_ms: float
    p95_latency_ms: float
    label_counts: dict[str, int]
    dimension_counts: dict[str, int]
    results: tuple[V3DeterministicCaseResult, ...]
    controls: dict[str, int | float | bool]
    interpretation: tuple[str, ...]


def run_v3_deterministic_baseline(
    workbook_path: str | Path,
    *,
    project_root: str | Path,
) -> V3DeterministicBaseline:
    """Replay the frozen workbook through existing constructors without I/O."""
    root = Path(project_root).resolve()
    path = Path(workbook_path).resolve()
    workbook = load_annotation_workbook(path)
    if not workbook.frozen:
        raise ValueError("V3.3 requires the frozen approved workbook")
    results = tuple(_evaluate_case(case) for case in workbook.cases)
    positive_labels = {
        V3ConstructionGoldLabel.DETERMINISTIC_CONSTRUCTIBLE,
        V3ConstructionGoldLabel.FALLBACK_ELIGIBLE,
    }
    positives = [item for item in results if item.gold_label in positive_labels]
    deterministic_positives = [
        item
        for item in results
        if item.gold_label is V3ConstructionGoldLabel.DETERMINISTIC_CONSTRUCTIBLE
    ]
    fallback_positives = [
        item
        for item in results
        if item.gold_label is V3ConstructionGoldLabel.FALLBACK_ELIGIBLE
    ]
    succeeded = [item for item in results if item.construction_succeeded]
    true_positives = [
        item for item in succeeded if item.gold_label in positive_labels
    ]
    false_positives = [
        item for item in succeeded if item.gold_label not in positive_labels
    ]
    review_required_gold = [
        item
        for item in results
        if item.gold_label is not V3ConstructionGoldLabel.NOT_APPLICABLE
        and not item.construction_succeeded
    ]
    correctly_routed = [item for item in review_required_gold if item.human_review_required]
    latencies = sorted(item.latency_ms for item in results)
    successful_dimensions = tuple(
        sorted({item.dimension for item in succeeded})
    )
    binding_results = [
        item.approved_evidence_binding_valid
        for item in succeeded
        if item.approved_evidence_binding_valid is not None
    ]
    return V3DeterministicBaseline(
        dataset_path=path.relative_to(root).as_posix(),
        case_count=len(results),
        constructible_gold_count=len(positives),
        deterministic_constructible_gold_count=len(deterministic_positives),
        fallback_eligible_gold_count=len(fallback_positives),
        constructions_detected=sum(item.construction_detected for item in results),
        constructions_succeeded=len(succeeded),
        true_positive_constructions=len(true_positives),
        false_positive_constructions=len(false_positives),
        construction_recall=_ratio(len(true_positives), len(positives)),
        deterministic_label_recall=_ratio(
            sum(item.construction_succeeded for item in deterministic_positives),
            len(deterministic_positives),
        ),
        construction_precision=(
            _ratio(len(true_positives), len(succeeded)) if succeeded else None
        ),
        exact_evidence_span_validity=(
            _ratio(sum(bool(item) for item in binding_results), len(binding_results))
            if binding_results
            else None
        ),
        exact_span_attribution_supported=all(
            item.exact_span_attribution_available for item in succeeded
        )
        if succeeded
        else False,
        unsafe_accepted_constructions=sum(item.unsafe_accepted for item in results),
        human_review_routing_recall=_ratio(
            len(correctly_routed), len(review_required_gold)
        ),
        publication_safety_regressions=sum(
            item.unsafe_accepted and not item.publication_blocked for item in results
        ),
        publication_blocks=sum(item.publication_blocked for item in results),
        supported_dimension_count=len(successful_dimensions),
        supported_dimensions=successful_dimensions,
        median_latency_ms=_percentile(latencies, 0.5),
        p95_latency_ms=_percentile(latencies, 0.95),
        label_counts=dict(sorted(Counter(item.gold_label.value for item in results).items())),
        dimension_counts=dict(sorted(Counter(item.dimension for item in results).items())),
        results=results,
        controls={
            "model_calls": 0,
            "network_calls": 0,
            "search_calls": 0,
            "paid_operations": 0,
            "benchmark_labels_used_as_constructor_inputs": 0,
        },
        interpretation=(
            "This measures the pre-existing deterministic constructors; no constructor "
            "was expanded while collecting the baseline.",
            "A missing construction on an applicable reviewed case is fail-closed and "
            "routes to human review.",
            "Exact span validity is not reported when no construction succeeds; "
            "absence is not converted into a perfect score.",
        ),
    )


def _evaluate_case(case) -> V3DeterministicCaseResult:
    assert case.annotation is not None
    started = perf_counter()
    claim = AtomicClaim(text=case.claim_text, checkworthiness=1.0)
    evidence_ids = {
        item.evidence_id: uuid5(NAMESPACE_URL, item.evidence_id)
        for item in case.evidence
    }
    evidence = tuple(
        Evidence(
            evidence_id=evidence_ids[item.evidence_id],
            claim_id=claim.claim_id,
            source_id=uuid5(NAMESPACE_URL, item.url),
            passage=item.passage,
            stance=EvidenceStance.CONTEXT,
            relevance_score=1.0,
        )
        for item in case.evidence
    )
    comparative, _, _ = construct_comparative_assertion(claim=claim, evidence=evidence)
    temporal, _, _ = construct_temporal_comparison(claim=claim, evidence=evidence)
    construction = comparative or temporal
    succeeded = bool(
        construction
        and construction.state is AssertionConstructionState.CONSTRUCTED
    )
    approved_ids = {
        evidence_ids[item.evidence_id] for item in case.annotation.evidence_spans
    }
    bound_ids = set(construction.evidence_ids) if succeeded else set()
    binding_valid = bound_ids.issubset(approved_ids) if succeeded else None
    positive = case.annotation.gold_label in {
        V3ConstructionGoldLabel.DETERMINISTIC_CONSTRUCTIBLE,
        V3ConstructionGoldLabel.FALLBACK_ELIGIBLE,
    }
    unsafe = succeeded and (not positive or not binding_valid)
    unresolved_applicable = (
        case.annotation.gold_label is not V3ConstructionGoldLabel.NOT_APPLICABLE
        and not succeeded
    )
    return V3DeterministicCaseResult(
        case_id=case.case_id,
        split=case.split.value,
        dimension=case.annotation.dimension_bucket,
        gold_label=case.annotation.gold_label,
        construction_detected=construction is not None,
        construction_succeeded=succeeded,
        construction_kind=(
            "comparative" if comparative else "temporal" if temporal else None
        ),
        construction_state=construction.state.value if construction else None,
        approved_evidence_binding_valid=binding_valid,
        exact_span_attribution_available=False,
        human_review_required=unresolved_applicable or unsafe,
        publication_blocked=unresolved_applicable or unsafe,
        unsafe_accepted=unsafe,
        latency_ms=round((perf_counter() - started) * 1000, 6),
    )


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 1.0


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    index = min(len(values) - 1, max(0, int((len(values) - 1) * fraction)))
    return round(values[index], 6)
