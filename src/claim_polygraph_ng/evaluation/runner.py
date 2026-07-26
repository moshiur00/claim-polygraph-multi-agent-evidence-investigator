"""Load and run versioned local evaluation datasets."""

import json
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from claim_polygraph_ng.application import InvestigationService
from claim_polygraph_ng.domain import ModelCallUsage, SupportLevel
from claim_polygraph_ng.evaluation.models import (
    AnnotationStatus,
    BenchmarkCase,
    BenchmarkDataset,
    EvaluationCaseResult,
    EvaluationCategory,
    EvaluationSummary,
)

ServiceFactory = Callable[[BenchmarkCase], InvestigationService]


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


def export_evaluation(summary: EvaluationSummary, path: str | Path) -> Path:
    """Write one machine-readable evaluation summary."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(summary.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output


def _mean(values: tuple[int, ...]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


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
