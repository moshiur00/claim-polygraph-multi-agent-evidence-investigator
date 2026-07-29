"""Stage 9.12 frozen workflow comparison and declared release result."""

import asyncio
from pathlib import Path

from claim_polygraph_ng.evaluation.phase9_comparison import (
    Phase9ComparisonEvaluation,
    evaluate_phase9_comparison,
)


def test_small_comparison_executes_all_four_real_paths(tmp_path) -> None:
    root = Path(__file__).parents[2]
    result = asyncio.run(evaluate_phase9_comparison(root, tmp_path, limit=1))

    assert result.case_count == 1
    assert result.direct.completion_rate == 1
    assert result.previous_wrapper.direct_verdict_equivalence == 1
    assert result.unified.completion_rate == 1
    assert result.minus_challenger.completion_rate == 1
    assert result.unified.duplicate_paid_operations == 0
    assert result.external_model_calls == result.live_search_calls == 0


def test_repository_comparison_records_remediation_and_ablation_honestly() -> None:
    root = Path(__file__).parents[2]
    result = Phase9ComparisonEvaluation.model_validate_json(
        (
            root
            / "artifacts/evaluations/phase9-stage9.12-frozen-comparison-v1.json"
        ).read_text(encoding="utf-8")
    )

    assert result.case_count == 20
    assert result.direct.completion_rate == 1
    assert result.previous_wrapper.direct_verdict_equivalence == 1
    assert result.unified.direct_verdict_equivalence == 1
    assert result.unified.reviewed_label_accuracy == result.direct.reviewed_label_accuracy
    assert result.unified.mean_evidence_coverage_ratio >= 1
    assert (
        result.unified.mean_evidence_coverage_ratio
        > result.minus_challenger.mean_evidence_coverage_ratio
    )
    assert (
        result.unified.mean_family_coverage_ratio
        > result.minus_challenger.mean_family_coverage_ratio
    )
    assert result.unified.citation_support_rate == 1
    assert result.unified.duplicate_paid_operations == 0
    assert result.challenger_material_gain_cases == 7
    assert result.unified.challenge_coverage_rate == 1
    assert (
        result.unified.challenge_coverage_rate
        > result.minus_challenger.challenge_coverage_rate
    )
    assert result.unified.review_routing_recall == 1
    assert result.mandatory_gates_passed
    assert result.recommended_disposition == "eligible_for_stage9_13_audit"
    assert result.failed_gates == ()
