"""Tests for conservative complex-claim verdict aggregation."""

from uuid import uuid4

from claim_polygraph_ng.analysis import aggregate_component_label, constrain_parent_verdict
from claim_polygraph_ng.domain import Verdict, VerdictLabel


def _verdict(label: VerdictLabel) -> Verdict:
    evidence_ids = (
        () if label in {VerdictLabel.UNSUPPORTED, VerdictLabel.UNVERIFIABLE} else (uuid4(),)
    )
    return Verdict(
        claim_id=uuid4(),
        label=label,
        concise_explanation="The component has a sufficiently explained provisional result.",
        detailed_reasoning="The result is created for deterministic aggregation contract testing.",
        decisive_evidence_ids=evidence_ids,
    )


def test_all_supported_components_produce_supported_parent() -> None:
    assert (
        aggregate_component_label(
            [_verdict(VerdictLabel.SUPPORTED), _verdict(VerdictLabel.SUPPORTED)]
        )
        is VerdictLabel.SUPPORTED
    )


def test_supported_and_contradicted_components_produce_mixed_parent() -> None:
    assert (
        aggregate_component_label(
            [_verdict(VerdictLabel.SUPPORTED), _verdict(VerdictLabel.CONTRADICTED)]
        )
        is VerdictLabel.MIXED
    )


def test_misleading_component_constrains_parent_to_misleading() -> None:
    assert (
        aggregate_component_label(
            [_verdict(VerdictLabel.MISLEADING), _verdict(VerdictLabel.CONTRADICTED)]
        )
        is VerdictLabel.MISLEADING
    )


def test_supported_and_misleading_components_produce_misleading_parent() -> None:
    assert (
        aggregate_component_label(
            [_verdict(VerdictLabel.SUPPORTED), _verdict(VerdictLabel.MISLEADING)]
        )
        is VerdictLabel.MISLEADING
    )


def test_one_misleading_component_does_not_mask_multiple_contradictions() -> None:
    assert (
        aggregate_component_label(
            [
                _verdict(VerdictLabel.MISLEADING),
                _verdict(VerdictLabel.CONTRADICTED),
                _verdict(VerdictLabel.CONTRADICTED),
            ]
        )
        is VerdictLabel.MIXED
    )


def test_unverifiable_material_component_prevents_supported_parent() -> None:
    assert (
        aggregate_component_label(
            [_verdict(VerdictLabel.SUPPORTED), _verdict(VerdictLabel.UNVERIFIABLE)]
        )
        is VerdictLabel.MIXED
    )


def test_parent_verdict_is_constrained_and_flagged_for_review() -> None:
    proposed = _verdict(VerdictLabel.SUPPORTED)
    constrained = constrain_parent_verdict(
        proposed,
        [_verdict(VerdictLabel.SUPPORTED), _verdict(VerdictLabel.CONTRADICTED)],
    )

    assert constrained.label is VerdictLabel.MIXED
    assert constrained.human_review_required is True
    assert constrained.review_reason is not None
    assert "constrained from supported to mixed" in constrained.review_reason
