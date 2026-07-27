"""Load and run versioned local evaluation datasets."""

import json
import re
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from claim_polygraph_ng.application import ComplexInvestigationService, InvestigationService
from claim_polygraph_ng.domain import (
    ClaimDecomposition,
    ComponentStatus,
    ModelCallUsage,
    SupportLevel,
)
from claim_polygraph_ng.evaluation.models import (
    AnnotationStatus,
    BenchmarkCase,
    BenchmarkDataset,
    ComplexEvaluationCaseResult,
    ComplexEvaluationSummary,
    EvaluationCaseResult,
    EvaluationCategory,
    EvaluationSummary,
)

ServiceFactory = Callable[[BenchmarkCase], InvestigationService]
ComplexServiceFactory = Callable[[BenchmarkCase], ComplexInvestigationService]


def load_benchmark(path: str | Path) -> BenchmarkDataset:
    """Load and validate a benchmark JSON document."""
    return BenchmarkDataset.model_validate_json(Path(path).read_text(encoding="utf-8"))


def validate_initial_benchmark(dataset: BenchmarkDataset) -> None:
    """Enforce the charter's initial 20-claim coverage requirement."""
    if len(dataset.cases) != 20:
        raise ValueError("the initial benchmark must contain exactly 20 cases")
    present = {category for case in dataset.cases for category in case.categories}
    missing = set(EvaluationCategory) - present
    if missing:
        joined = ", ".join(sorted(category.value for category in missing))
        raise ValueError(f"the initial benchmark is missing categories: {joined}")


async def run_evaluation(
    dataset: BenchmarkDataset,
    service_factory: ServiceFactory,
    *,
    provider_mode: str,
    limit: int | None = None,
) -> EvaluationSummary:
    """Run claims independently and aggregate structural baseline metrics."""
    if limit is not None and limit < 1:
        raise ValueError("evaluation limit must be at least one")
    cases = dataset.cases[:limit]
    started_at = datetime.now(UTC)
    run_started = perf_counter()
    results: list[EvaluationCaseResult] = []

    for case in cases:
        case_started = perf_counter()
        service = service_factory(case)
        ai_provisional_verdict = (
            case.ai_review.provisional_verdict if case.ai_review is not None else None
        )
        try:
            report = await service.investigate(case.claim)
        except Exception as error:
            usage = service.model_usage
            results.append(
                EvaluationCaseResult(
                    case_id=case.case_id,
                    completed=False,
                    expected_verdict=case.expected_verdict,
                    ai_provisional_verdict=ai_provisional_verdict,
                    source_count=0,
                    evidence_count=0,
                    full_audit_count=0,
                    audit_count=0,
                    duration_seconds=round(perf_counter() - case_started, 6),
                    **_usage_metrics(usage),
                    error_type=type(error).__name__,
                    error_message=str(error),
                )
            )
            continue

        verdict_matches = (
            report.verdict.label is case.expected_verdict
            if case.expected_verdict is not None
            else None
        )
        results.append(
            EvaluationCaseResult(
                case_id=case.case_id,
                completed=True,
                investigation_id=report.investigation.investigation_id,
                verdict_label=report.verdict.label,
                expected_verdict=case.expected_verdict,
                verdict_matches=verdict_matches,
                ai_provisional_verdict=ai_provisional_verdict,
                verdict_matches_ai_provisional=(
                    report.verdict.label is ai_provisional_verdict
                    if ai_provisional_verdict is not None
                    else None
                ),
                source_count=len(report.sources),
                evidence_count=len(report.evidence),
                full_audit_count=sum(
                    audit.support_level is SupportLevel.FULL for audit in report.audits
                ),
                audit_count=len(report.audits),
                duration_seconds=round(perf_counter() - case_started, 6),
                **_usage_metrics(service.model_usage),
            )
        )

    completed = tuple(result for result in results if result.completed)
    reviewed = tuple(case for case in cases if case.annotation_status is AnnotationStatus.REVIEWED)
    ai_reviewed = tuple(
        case for case in cases if case.annotation_status is AnnotationStatus.AI_REVIEWED
    )
    scored = tuple(result for result in results if result.verdict_matches is not None)
    ai_compared = tuple(
        result for result in results if result.verdict_matches_ai_provisional is not None
    )
    audit_count = sum(result.audit_count for result in completed)
    full_audit_count = sum(result.full_audit_count for result in completed)
    distribution = Counter(
        result.verdict_label.value for result in completed if result.verdict_label is not None
    )
    total_estimated_cost = round(
        sum(result.estimated_model_cost_usd for result in results),
        9,
    )

    limitations = [
        "Cases without human-reviewed labels do not contribute to verdict accuracy.",
        "AI-provisional agreement is a development diagnostic, not accuracy or ground truth.",
        "Structural citation status does not measure semantic citation entailment.",
        "Model costs are estimates based on versioned list prices, not billing records.",
    ]
    if provider_mode.startswith("benchmark_evidence"):
        limitations.append(
            "Benchmark-evidence mode is an evidence-oracle test of reasoning and citation; "
            "it does not measure search or retrieval quality."
        )
    if provider_mode.startswith("deterministic_retrieval"):
        limitations.append(
            "Deterministic retrieval uses synthetic evidence and does not measure factual quality."
        )
    if provider_mode.endswith("deterministic_reasoning"):
        limitations.append(
            "Deterministic provider verdicts are workflow baselines, not factual conclusions."
        )

    return EvaluationSummary(
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.version,
        provider_mode=provider_mode,
        started_at=started_at,
        duration_seconds=round(perf_counter() - run_started, 6),
        case_count=len(cases),
        reviewed_case_count=len(reviewed),
        ai_reviewed_case_count=len(ai_reviewed),
        completed_case_count=len(completed),
        completion_rate=round(len(completed) / len(cases), 6),
        mean_sources_per_completed_case=_mean(tuple(result.source_count for result in completed)),
        mean_evidence_per_completed_case=_mean(
            tuple(result.evidence_count for result in completed)
        ),
        citation_full_rate=(round(full_audit_count / audit_count, 6) if audit_count else None),
        verdict_accuracy=(
            round(sum(result.verdict_matches is True for result in scored) / len(scored), 6)
            if scored
            else None
        ),
        ai_provisional_comparison_count=len(ai_compared),
        ai_provisional_agreement_rate=(
            round(
                sum(result.verdict_matches_ai_provisional is True for result in ai_compared)
                / len(ai_compared),
                6,
            )
            if ai_compared
            else None
        ),
        metered_model_call_count=sum(result.metered_model_call_count for result in results),
        priced_model_call_count=sum(result.priced_model_call_count for result in results),
        input_tokens=sum(result.input_tokens for result in results),
        cached_input_tokens=sum(result.cached_input_tokens for result in results),
        output_tokens=sum(result.output_tokens for result in results),
        estimated_model_cost_usd=total_estimated_cost,
        mean_estimated_model_cost_per_completed_case_usd=(
            round(total_estimated_cost / len(completed), 9) if completed else 0.0
        ),
        verdict_distribution=dict(sorted(distribution.items())),
        results=tuple(results),
        limitations=tuple(limitations),
    )


async def run_complex_evaluation(
    dataset: BenchmarkDataset,
    service_factory: ComplexServiceFactory,
    *,
    provider_mode: str,
    limit: int | None = None,
) -> ComplexEvaluationSummary:
    """Run only declared complex cases and measure Phase 3 contracts."""
    if limit is not None and limit < 1:
        raise ValueError("evaluation limit must be at least one")
    complex_cases = tuple(case for case in dataset.cases if len(case.expected_components) >= 2)
    cases = complex_cases[:limit]
    if not cases:
        raise ValueError("complex evaluation requires cases with expected_components")
    started_at = datetime.now(UTC)
    run_started = perf_counter()
    results: list[ComplexEvaluationCaseResult] = []

    for case in cases:
        case_started = perf_counter()
        service = service_factory(case)
        try:
            report = await service.investigate(case.claim)
        except Exception as error:
            results.append(
                ComplexEvaluationCaseResult(
                    case_id=case.case_id,
                    completed=False,
                    expected_component_count=len(case.expected_components),
                    observed_component_count=0,
                    matched_expected_component_count=0,
                    component_recall=0.0,
                    material_coverage_rate=0.0,
                    parent_full_audit_count=0,
                    parent_audit_count=0,
                    completed_component_count=0,
                    failed_or_unresolved_component_count=0,
                    duration_seconds=round(perf_counter() - case_started, 6),
                    **_usage_metrics(service.model_usage),
                    error_type=type(error).__name__,
                    error_message=str(error),
                )
            )
            continue

        decomposition = report.decomposition
        matched_count = _matched_component_count(
            case.expected_components,
            tuple(component.text for component in decomposition.components),
        )
        linkage_valid = all(
            component.parent_claim_id == decomposition.root_claim.claim_id
            for component in decomposition.components
        )
        context_valid = _context_contract_valid(report.decomposition)
        parent_full_audit_count = sum(
            audit.support_level is SupportLevel.FULL for audit in report.audits
        )
        completed_components = sum(
            outcome.status is ComponentStatus.COMPLETED for outcome in report.coverage.outcomes
        )
        unresolved_components = sum(
            outcome.status in {ComponentStatus.UNRESOLVED, ComponentStatus.FAILED}
            for outcome in report.coverage.outcomes
        )
        results.append(
            ComplexEvaluationCaseResult(
                case_id=case.case_id,
                completed=True,
                investigation_id=report.investigation.investigation_id,
                expected_component_count=len(case.expected_components),
                observed_component_count=len(decomposition.components),
                observed_components=tuple(component.text for component in decomposition.components),
                matched_expected_component_count=matched_count,
                component_recall=round(matched_count / len(case.expected_components), 6),
                parent_linkage_valid=linkage_valid,
                context_contract_valid=context_valid,
                material_coverage_rate=report.coverage.material_coverage_rate,
                verdict_label=report.verdict.label,
                expected_verdict=case.expected_verdict,
                verdict_matches=(
                    report.verdict.label is case.expected_verdict
                    if case.expected_verdict is not None
                    else None
                ),
                parent_full_audit_count=parent_full_audit_count,
                parent_audit_count=len(report.audits),
                completed_component_count=completed_components,
                failed_or_unresolved_component_count=unresolved_components,
                duration_seconds=round(perf_counter() - case_started, 6),
                **_usage_metrics(service.model_usage),
            )
        )

    completed = tuple(item for item in results if item.completed)
    scored = tuple(item for item in completed if item.verdict_matches is not None)
    parent_audit_count = sum(item.parent_audit_count for item in completed)
    full_parent_audit_count = sum(item.parent_full_audit_count for item in completed)
    completed_component_count = sum(item.completed_component_count for item in completed)
    total_cost = round(sum(item.estimated_model_cost_usd for item in results), 9)
    reviewed_count = sum(case.annotation_status is AnnotationStatus.REVIEWED for case in cases)
    limitations = (
        "Expected-component matching is a deterministic token-overlap diagnostic, "
        "not a semantic decomposition judgment.",
        "Draft and AI-reviewed cases do not contribute to verdict accuracy.",
        "Benchmark-evidence mode is an evidence-oracle reasoning test and does not "
        "measure live retrieval.",
        "Model costs are estimates based on versioned list prices, not billing records.",
    )
    return ComplexEvaluationSummary(
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.version,
        provider_mode=provider_mode,
        started_at=started_at,
        duration_seconds=round(perf_counter() - run_started, 6),
        case_count=len(cases),
        reviewed_case_count=reviewed_count,
        completed_case_count=len(completed),
        completion_rate=round(len(completed) / len(cases), 6),
        mean_component_recall=_mean_float(tuple(item.component_recall for item in completed)),
        parent_linkage_valid_rate=_true_rate(
            tuple(item.parent_linkage_valid for item in completed)
        ),
        context_contract_valid_rate=_true_rate(
            tuple(item.context_contract_valid for item in completed)
        ),
        material_component_coverage_rate=_mean_float(
            tuple(item.material_coverage_rate for item in completed)
        ),
        parent_citation_full_rate=(
            round(full_parent_audit_count / parent_audit_count, 6) if parent_audit_count else None
        ),
        verdict_accuracy=(
            round(sum(item.verdict_matches is True for item in scored) / len(scored), 6)
            if scored
            else None
        ),
        metered_model_call_count=sum(item.metered_model_call_count for item in results),
        priced_model_call_count=sum(item.priced_model_call_count for item in results),
        input_tokens=sum(item.input_tokens for item in results),
        cached_input_tokens=sum(item.cached_input_tokens for item in results),
        output_tokens=sum(item.output_tokens for item in results),
        estimated_model_cost_usd=total_cost,
        mean_estimated_model_cost_per_completed_component_usd=(
            round(total_cost / completed_component_count, 9) if completed_component_count else 0.0
        ),
        results=tuple(results),
        limitations=limitations,
    )


def export_evaluation(summary: EvaluationSummary, path: str | Path) -> Path:
    """Write one machine-readable evaluation summary."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(summary.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output


def export_complex_evaluation(
    summary: ComplexEvaluationSummary,
    path: str | Path,
) -> Path:
    """Write one machine-readable complex-claim evaluation summary."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(summary.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output


def merge_complex_evaluations(
    dataset: BenchmarkDataset,
    base: ComplexEvaluationSummary,
    patches: tuple[ComplexEvaluationSummary, ...],
) -> ComplexEvaluationSummary:
    """Replace selected case results and recompute every aggregate metric."""
    summaries = (base, *patches)
    for summary in summaries:
        if summary.dataset_id != dataset.dataset_id or summary.dataset_version != dataset.version:
            raise ValueError("complex evaluation does not match the benchmark identity")
        if summary.provider_mode != base.provider_mode:
            raise ValueError("complex evaluation provider modes do not match")

    case_by_id = {case.case_id: case for case in dataset.cases}
    ordered_ids = tuple(result.case_id for result in base.results)
    results_by_id = {result.case_id: result for result in base.results}
    for patch in patches:
        for result in patch.results:
            if result.case_id not in results_by_id:
                raise ValueError(f"patch contains case outside base run: {result.case_id}")
            results_by_id[result.case_id] = result

    results: list[ComplexEvaluationCaseResult] = []
    for case_id in ordered_ids:
        case = case_by_id.get(case_id)
        if case is None:
            raise ValueError(f"benchmark is missing merged case: {case_id}")
        result = results_by_id[case_id]
        matched_count = (
            _matched_component_count(case.expected_components, result.observed_components)
            if result.completed
            else 0
        )
        results.append(
            result.model_copy(
                update={
                    "expected_component_count": len(case.expected_components),
                    "matched_expected_component_count": matched_count,
                    "component_recall": (
                        round(matched_count / len(case.expected_components), 6)
                        if result.completed
                        else 0.0
                    ),
                    "expected_verdict": case.expected_verdict,
                    "verdict_matches": (
                        result.verdict_label is case.expected_verdict
                        if result.completed
                        and result.verdict_label is not None
                        and case.expected_verdict is not None
                        else None
                    ),
                }
            )
        )

    completed = tuple(item for item in results if item.completed)
    scored = tuple(item for item in completed if item.verdict_matches is not None)
    parent_audit_count = sum(item.parent_audit_count for item in completed)
    full_parent_audit_count = sum(item.parent_full_audit_count for item in completed)
    completed_component_count = sum(item.completed_component_count for item in completed)
    total_cost = round(sum(item.estimated_model_cost_usd for item in results), 9)
    selected_cases = tuple(case_by_id[case_id] for case_id in ordered_ids)
    return ComplexEvaluationSummary(
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.version,
        provider_mode=base.provider_mode,
        started_at=min(summary.started_at for summary in summaries),
        duration_seconds=round(sum(summary.duration_seconds for summary in summaries), 6),
        case_count=len(results),
        reviewed_case_count=sum(
            case.annotation_status is AnnotationStatus.REVIEWED for case in selected_cases
        ),
        completed_case_count=len(completed),
        completion_rate=round(len(completed) / len(results), 6),
        mean_component_recall=_mean_float(tuple(item.component_recall for item in completed)),
        parent_linkage_valid_rate=_true_rate(
            tuple(item.parent_linkage_valid for item in completed)
        ),
        context_contract_valid_rate=_true_rate(
            tuple(item.context_contract_valid for item in completed)
        ),
        material_component_coverage_rate=_mean_float(
            tuple(item.material_coverage_rate for item in completed)
        ),
        parent_citation_full_rate=(
            round(full_parent_audit_count / parent_audit_count, 6) if parent_audit_count else None
        ),
        verdict_accuracy=(
            round(sum(item.verdict_matches is True for item in scored) / len(scored), 6)
            if scored
            else None
        ),
        metered_model_call_count=sum(item.metered_model_call_count for item in results),
        priced_model_call_count=sum(item.priced_model_call_count for item in results),
        input_tokens=sum(item.input_tokens for item in results),
        cached_input_tokens=sum(item.cached_input_tokens for item in results),
        output_tokens=sum(item.output_tokens for item in results),
        estimated_model_cost_usd=total_cost,
        mean_estimated_model_cost_per_completed_component_usd=(
            round(total_cost / completed_component_count, 9) if completed_component_count else 0.0
        ),
        results=tuple(results),
        limitations=(
            *base.limitations,
            "Selected case results were replaced by declared sequential patch runs; "
            "all aggregate metrics were recomputed from the merged case set.",
        ),
    )


def _mean(values: tuple[int, ...]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


def _mean_float(values: tuple[float, ...]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


def _true_rate(values: tuple[bool, ...]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


def _normalized_tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.casefold()))


def _matched_component_count(
    expected: tuple[str, ...],
    observed: tuple[str, ...],
    *,
    threshold: float = 0.5,
) -> int:
    """Greedily match expected and observed components by token Jaccard overlap."""
    candidates: list[tuple[float, int, int]] = []
    for expected_index, expected_text in enumerate(expected):
        expected_tokens = _normalized_tokens(expected_text)
        for observed_index, observed_text in enumerate(observed):
            observed_tokens = _normalized_tokens(observed_text)
            intersection = expected_tokens & observed_tokens
            union = expected_tokens | observed_tokens
            jaccard = len(intersection) / len(union) if union else 0.0
            shorter = min(len(expected_tokens), len(observed_tokens))
            containment = len(intersection) / shorter if shorter else 0.0
            score = max(jaccard, containment * 0.8)
            candidates.append((score, expected_index, observed_index))
    matched_expected: set[int] = set()
    matched_observed: set[int] = set()
    for score, expected_index, observed_index in sorted(candidates, reverse=True):
        if score < threshold:
            break
        if expected_index in matched_expected or observed_index in matched_observed:
            continue
        matched_expected.add(expected_index)
        matched_observed.add(observed_index)
    return len(matched_expected)


def _context_contract_valid(decomposition: ClaimDecomposition) -> bool:
    """Check immutable linkage and application-protected parent context."""
    root = decomposition.root_claim
    protected_context = f"Submitted parent claim: {root.text}"
    for component in decomposition.components:
        if component.parent_claim_id != root.claim_id:
            return False
        if root.reference_date is not None and component.reference_date != root.reference_date:
            return False
        if root.geography is not None and component.geography != root.geography:
            return False
        if protected_context not in component.retained_context:
            return False
    return True


def _usage_metrics(usage: tuple[ModelCallUsage, ...]) -> dict[str, int | float]:
    return {
        "metered_model_call_count": len(usage),
        "priced_model_call_count": sum(item.estimated_cost_usd is not None for item in usage),
        "input_tokens": sum(item.input_tokens or 0 for item in usage),
        "cached_input_tokens": sum(item.cached_input_tokens or 0 for item in usage),
        "output_tokens": sum(item.output_tokens or 0 for item in usage),
        "estimated_model_cost_usd": round(
            sum(item.estimated_cost_usd or 0.0 for item in usage),
            9,
        ),
    }
