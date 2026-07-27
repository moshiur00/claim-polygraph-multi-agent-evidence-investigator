import pytest

from claim_polygraph_ng.analysis.evidence_families import (
    FamilySourceRecord,
    infer_evidence_families,
)
from claim_polygraph_ng.analysis.independence_features import (
    IndependenceRequirementState,
    calculate_independence_features,
)


def _record(source_id: str, text: str, url: str):
    return FamilySourceRecord(source_id=source_id, text=text, url=url)


def test_unresolved_pair_produces_an_uncertain_interval():
    inference = infer_evidence_families(
        "component",
        (
            _record("A", "Inspectors observed shallow surface cracks.", "https://a.test"),
            _record("B", "An examination found minor cracking.", "https://b.test"),
        ),
    )

    features = calculate_independence_features(
        inference, raw_source_count=2, required_independent_families=2
    )

    assert features.confirmed_independent_lower_bound == 1
    assert features.possible_independent_upper_bound == 2
    assert features.uncertainty_width == 1
    assert features.requirement_state is IndependenceRequirementState.UNCERTAIN
    assert features.confidence_score is None


def test_explicit_independence_meets_two_family_requirement():
    inference = infer_evidence_families(
        "component",
        (
            _record("A", "Our gauge measured 84 millimetres.", "https://a.test"),
            _record("B", "Our separate station measured 82 millimetres.", "https://b.test"),
        ),
    )

    features = calculate_independence_features(
        inference, raw_source_count=2, required_independent_families=2
    )

    assert features.confirmed_independent_lower_bound == 2
    assert features.possible_independent_upper_bound == 2
    assert features.requirement_state is IndependenceRequirementState.MET


def test_duplicate_sources_cannot_meet_two_family_requirement():
    inference = infer_evidence_families(
        "component",
        (
            _record("A", "The result was 42.", "https://a.test"),
            _record("B", "the result was 42.", "https://b.test"),
        ),
    )

    features = calculate_independence_features(
        inference, raw_source_count=2, required_independent_families=2
    )

    assert features.grouped_family_count == 1
    assert features.dependent_repetition_count == 1
    assert features.requirement_state is IndependenceRequirementState.NOT_MET


def test_raw_source_count_cannot_be_below_family_count():
    inference = infer_evidence_families(
        "component",
        (_record("A", "One source.", "https://a.test"),),
    )

    with pytest.raises(ValueError, match="raw source"):
        calculate_independence_features(
            inference, raw_source_count=0, required_independent_families=1
        )
