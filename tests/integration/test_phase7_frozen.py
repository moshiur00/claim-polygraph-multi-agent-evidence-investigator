"""Stage 7.8 frozen benchmark comparison tests."""

import json
from pathlib import Path

import pytest

from claim_polygraph_ng.evaluation.phase7_frozen import (
    evaluate_phase7_frozen,
    export_phase7_frozen,
)

ROOT = Path(__file__).parents[2]
BENCHMARK = ROOT / "benchmarks/initial_claims_v1.json"
BASELINE = ROOT / "artifacts/evaluations/phase6-stage6.0-baseline-v1.json"


def test_frozen_twenty_claim_promotion_gates_pass() -> None:
    result = evaluate_phase7_frozen(BENCHMARK, BASELINE)

    assert result.case_count == 20
    assert result.verdict_equivalence_rate == 1.0
    assert result.authoritative_reviewed_label_accuracy == 0.9
    assert result.wrapper_reviewed_label_accuracy == 0.9
    assert result.artifact_preservation_rate == 1.0
    assert result.required_review_recall == 1.0
    assert result.citation_accuracy >= 0.95
    assert result.duplicate_paid_operations == 0
    assert result.duplicate_deterministic_operations == 0
    assert result.deterministic_latency_overhead_ratio <= 0.2
    assert result.verdict_regressions == result.artifact_losses == 0
    assert result.promotion_gate_passed


def test_frozen_comparison_rejects_dataset_identity_mismatch(tmp_path) -> None:
    benchmark = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    benchmark["version"] += 1
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(benchmark), encoding="utf-8")

    with pytest.raises(ValueError, match="identity mismatch"):
        evaluate_phase7_frozen(changed, BASELINE)


def test_frozen_comparison_artifact_round_trips(tmp_path) -> None:
    result = evaluate_phase7_frozen(BENCHMARK, BASELINE)
    output = export_phase7_frozen(result, tmp_path / "result.json")

    assert json.loads(output.read_text(encoding="utf-8")) == result.model_dump(mode="json")
