"""Tests for declared complex-run stability comparison."""

from datetime import UTC, datetime

import pytest

from claim_polygraph_ng.evaluation import (
    ComplexEvaluationCaseResult,
    ComplexEvaluationSummary,
    compare_complex_evaluations,
    export_complex_evaluation,
    export_complex_stability,
    load_complex_evaluation,
)


def _case(
    case_id: str,
    verdict: str,
    components: tuple[str, ...],
) -> ComplexEvaluationCaseResult:
    return ComplexEvaluationCaseResult(
        case_id=case_id,
        completed=True,
        expected_component_count=2,
        observed_component_count=len(components),
        observed_components=components,
        matched_expected_component_count=2,
        component_recall=1.0,
        parent_linkage_valid=True,
        context_contract_valid=True,
        material_coverage_rate=1.0,
        verdict_label=verdict,
        parent_full_audit_count=1,
        parent_audit_count=1,
        completed_component_count=2,
        failed_or_unresolved_component_count=0,
        duration_seconds=1.0,
    )


def _summary(
    results: tuple[ComplexEvaluationCaseResult, ...],
) -> ComplexEvaluationSummary:
    return ComplexEvaluationSummary(
        dataset_id="phase3",
        dataset_version=5,
        provider_mode="benchmark_evidence+openai:test",
        started_at=datetime.now(UTC),
        duration_seconds=2.0,
        case_count=len(results),
        reviewed_case_count=len(results),
        completed_case_count=len(results),
        completion_rate=1.0,
        mean_component_recall=1.0,
        parent_linkage_valid_rate=1.0,
        context_contract_valid_rate=1.0,
        material_component_coverage_rate=1.0,
        parent_citation_full_rate=1.0,
        verdict_accuracy=1.0,
        results=results,
        limitations=(),
    )


def test_complex_stability_compares_exact_labels_and_component_sets(tmp_path) -> None:
    first = _summary(
        (
            _case("CPNG-011", "mixed", ("Alpha claim.", "Beta claim.")),
            _case("CPNG-012", "contradicted", ("Gamma claim.", "Delta claim.")),
        )
    )
    second = _summary(
        (
            _case("CPNG-011", "mixed", ("Beta claim.", "Alpha claim.")),
            _case("CPNG-012", "mixed", ("Gamma claim.", "Changed claim.")),
        )
    )

    summary = compare_complex_evaluations(first, second)
    output = export_complex_stability(summary, tmp_path / "stability.json")

    assert summary.completion_stability_rate == 1.0
    assert summary.verdict_comparison_count == 2
    assert summary.exact_verdict_stability_rate == 0.5
    assert summary.exact_component_set_stability_rate == 0.5
    assert output.exists()


def test_complex_evaluation_loader_and_case_mismatch_guard(tmp_path) -> None:
    first = _summary((_case("CPNG-011", "mixed", ("A claim.", "B claim.")),))
    second = _summary((_case("CPNG-012", "mixed", ("A claim.", "B claim.")),))
    first_path = export_complex_evaluation(first, tmp_path / "first.json")

    assert load_complex_evaluation(first_path) == first
    with pytest.raises(ValueError, match="different cases"):
        compare_complex_evaluations(first, second)
