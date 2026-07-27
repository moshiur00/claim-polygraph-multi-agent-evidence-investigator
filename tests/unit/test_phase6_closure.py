"""Tests for the Phase 6 targeted review and release closure."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase6_closure import (
    build_targeted_review,
    load_ablation,
    load_closure_audit,
    verify_closure_audit,
)


def test_targeted_review_contains_only_policy_changed_cases() -> None:
    root = Path(__file__).parents[2]
    ablation = load_ablation(
        root / "artifacts/evaluations/phase6-stage6.8-frozen-ablation-v1.json"
    )

    packet = build_targeted_review(ablation)

    assert packet.changed_policy_case_count == 6
    assert tuple(item.case_id for item in packet.cases) == (
        "CPNG-006",
        "CPNG-007",
        "CPNG-008",
        "CPNG-009",
        "CPNG-011",
        "CPNG-014",
    )
    assert not packet.benchmark_truth_changed
    assert not packet.human_reapproval_required


def test_repository_phase6_closure_audit_verifies() -> None:
    root = Path(__file__).parents[2]
    audit = load_closure_audit(
        root / "artifacts/evaluations/phase6-final-release-audit.json"
    )

    result = verify_closure_audit(audit, root)

    assert result.valid
    assert result.checked_artifact_count == 10
    assert audit.phase_complete
    assert not audit.deterministic_policy_promoted
    assert audit.failed_count == 1
    assert audit.skipped_count == 1
