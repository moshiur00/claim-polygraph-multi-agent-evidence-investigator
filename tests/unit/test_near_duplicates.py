from datetime import date

from claim_polygraph_ng.analysis.near_duplicates import (
    NearDuplicateLabel,
    assess_near_duplicate,
)


def test_summary_with_attribution_and_shared_number_is_likely_derivative():
    result = assess_near_duplicate(
        left_record_id="study",
        left_text="We enrolled 240 participants and assigned them to two groups.",
        right_record_id="news",
        right_text="A published trial reports that researchers enrolled 240 participants.",
        left_published=date(2026, 1, 1),
        right_published=date(2026, 1, 2),
    )

    assert result.label is NearDuplicateLabel.LIKELY_DERIVATIVE
    assert result.signals.shared_numbers == ("240",)
    assert result.signals.publication_order == "left_before_right"
    assert not result.automatic_independence_use_allowed


def test_explicit_independent_analysis_prevents_derivative_label():
    result = assess_near_duplicate(
        left_record_id="A",
        left_text="Using public Series Z, our regression finds a downward trend.",
        right_record_id="B",
        right_text="Our independently written model of public Series Z finds a downward trend.",
    )

    assert result.label is NearDuplicateLabel.DISTINCT
    assert "independently" in result.signals.independence_markers


def test_topical_overlap_without_attribution_is_not_likely_derivative():
    result = assess_near_duplicate(
        left_record_id="A",
        left_text="Our gauge measured 84 millimetres of rainfall during the period.",
        right_record_id="B",
        right_text="Our separate station measured 82 millimetres during the period.",
    )

    assert result.label is NearDuplicateLabel.DISTINCT


def test_identical_normalized_text_is_exact():
    result = assess_near_duplicate(
        left_record_id="A",
        left_text=" The result was 42. ",
        right_record_id="B",
        right_text="the   result was 42.",
    )

    assert result.label is NearDuplicateLabel.EXACT
    assert result.confidence == 1


def test_moderate_overlap_without_provenance_is_only_possible():
    result = assess_near_duplicate(
        left_record_id="A",
        left_text="The public river sensor measured 42 units during January.",
        right_record_id="B",
        right_text="A river sensor measured 42 units during the winter period.",
    )

    assert result.label is NearDuplicateLabel.POSSIBLE_RELATED
