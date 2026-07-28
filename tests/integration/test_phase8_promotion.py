"""Stage 8.13 controlled promotion experiment."""

import asyncio

from claim_polygraph_ng.evaluation.phase8_promotion import (
    evaluate_stage8_13_promotion,
)


def test_five_case_pilot_is_safe_and_does_not_self_approve(tmp_path) -> None:
    result = asyncio.run(evaluate_stage8_13_promotion(tmp_path))

    assert len(result.cases) == 5
    assert result.authoritative_regressions == 0
    assert result.citation_support_rate >= 0.95
    assert result.material_audit_coverage == 1
    assert result.invented_or_out_of_packet_evidence == 0
    assert result.duplicate_paid_operations == 0
    assert result.deterministic_termination_rate == 1
    assert result.recovery_journeys_passed == result.recovery_journeys_total == 8
    assert result.job_recovery_passed
    assert result.trace_continuity_passed
    assert result.specialist_escalation_passed
    assert result.integrated_path_passed
    if result.larger_comparison_authorized:
        assert result.larger_comparison is not None
        assert result.larger_comparison.case_count == 10
        assert result.larger_comparison.authoritative_regressions == 0
    else:
        assert result.larger_comparison is None
        assert "median latency ratio above 2x" in result.failed_gates
    assert result.mandatory_review_recall is None
    assert not result.multi_agent_research_promoted
    assert result.external_model_calls == result.live_search_calls == 0
