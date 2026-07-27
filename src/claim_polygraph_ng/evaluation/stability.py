"""Compare two declared complex evaluation runs for exact stability."""

import json
from pathlib import Path

from claim_polygraph_ng.evaluation.models import (
    ComplexEvaluationSummary,
    ComplexStabilityCaseResult,
    ComplexStabilitySummary,
)


def load_complex_evaluation(path: str | Path) -> ComplexEvaluationSummary:
    """Load and validate one complex evaluation result."""
    return ComplexEvaluationSummary.model_validate_json(Path(path).read_text(encoding="utf-8"))


def compare_complex_evaluations(
    first: ComplexEvaluationSummary,
    second: ComplexEvaluationSummary,
) -> ComplexStabilitySummary:
    """Compare the same declared cases without silently dropping mismatches."""
    if first.dataset_id != second.dataset_id or first.dataset_version != second.dataset_version:
        raise ValueError("complex runs use different benchmark identities or versions")
    first_by_id = {result.case_id: result for result in first.results}
    second_by_id = {result.case_id: result for result in second.results}
    if first_by_id.keys() != second_by_id.keys():
        missing_first = sorted(second_by_id.keys() - first_by_id.keys())
        missing_second = sorted(first_by_id.keys() - second_by_id.keys())
        raise ValueError(
            "complex runs contain different cases; "
            f"missing from first={missing_first}, missing from second={missing_second}"
        )

    results: list[ComplexStabilityCaseResult] = []
    for case_id in first_by_id:
        first_result = first_by_id[case_id]
        second_result = second_by_id[case_id]
        verdict_comparable = (
            first_result.completed
            and second_result.completed
            and first_result.verdict_label is not None
            and second_result.verdict_label is not None
        )
        components_comparable = (
            first_result.completed
            and second_result.completed
            and bool(first_result.observed_components)
            and bool(second_result.observed_components)
        )
        results.append(
            ComplexStabilityCaseResult(
                case_id=case_id,
                first_completed=first_result.completed,
                second_completed=second_result.completed,
                completion_matches=first_result.completed == second_result.completed,
                first_verdict=first_result.verdict_label,
                second_verdict=second_result.verdict_label,
                verdict_comparable=verdict_comparable,
                exact_verdict_match=(
                    first_result.verdict_label is second_result.verdict_label
                    if verdict_comparable
                    else None
                ),
                exact_component_set_match=(
                    _normalized_component_set(first_result.observed_components)
                    == _normalized_component_set(second_result.observed_components)
                    if components_comparable
                    else None
                ),
            )
        )

    verdict_results = tuple(result for result in results if result.exact_verdict_match is not None)
    component_results = tuple(
        result for result in results if result.exact_component_set_match is not None
    )
    return ComplexStabilitySummary(
        dataset_id=first.dataset_id,
        dataset_version=first.dataset_version,
        first_provider_mode=first.provider_mode,
        second_provider_mode=second.provider_mode,
        case_count=len(results),
        verdict_comparison_count=len(verdict_results),
        completion_stability_rate=round(
            sum(result.completion_matches for result in results) / len(results),
            6,
        ),
        exact_verdict_stability_rate=(
            round(
                sum(result.exact_verdict_match is True for result in verdict_results)
                / len(verdict_results),
                6,
            )
            if verdict_results
            else None
        ),
        exact_component_set_stability_rate=(
            round(
                sum(result.exact_component_set_match is True for result in component_results)
                / len(component_results),
                6,
            )
            if component_results
            else None
        ),
        results=tuple(results),
        limitations=(
            "Exact verdict stability measures repeatability, not factual correctness.",
            "Component stability is case-folded, whitespace-normalized, and order-independent; "
            "it does not credit semantic paraphrases.",
            "Only cases completed with verdicts in both runs contribute to verdict stability.",
        ),
    )


def export_complex_stability(
    summary: ComplexStabilitySummary,
    path: str | Path,
) -> Path:
    """Write one machine-readable two-run comparison."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(summary.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output


def _normalized_component_set(values: tuple[str, ...]) -> frozenset[str]:
    return frozenset(" ".join(value.casefold().split()) for value in values)
