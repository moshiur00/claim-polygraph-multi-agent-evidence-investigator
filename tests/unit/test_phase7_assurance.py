"""Locked Stage 7.3 assurance and routing gate."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase7_assurance import evaluate_phase7_assurance


def test_repository_phase7_assurance_gate_passes() -> None:
    root = Path(__file__).parents[2]
    result = evaluate_phase7_assurance(
        root / "benchmarks/phase7_citation_routing_v1.json"
    )

    assert result.case_count == 10
    assert result.citation_accuracy >= 0.95
    assert result.critical_route_recall == 1
    assert result.unsupported_marked_supported_count == 0
    assert result.promotion_gate_passed
