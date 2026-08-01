"""V4.2 deterministic typed candidate extraction."""

import hashlib

from claim_polygraph_ng.analysis import (
    CANDIDATE_EXTRACTION_VERSION,
    VerificationCandidateDatePrecision,
    VerificationCandidateExtraction,
    VerificationCandidateGroupKind,
    VerificationCandidateKind,
    extract_verification_candidates,
)


def _items(text: str, kind: VerificationCandidateKind):
    packet = extract_verification_candidates(text)
    return tuple(item for item in packet.candidates if item.kind is kind)


def test_values_units_dates_and_offsets_are_exact_and_stable() -> None:
    text = "District output was 1,250 tonnes in June 2024."
    first = extract_verification_candidates(text)
    second = extract_verification_candidates(text)

    assert first == second
    assert first.version == CANDIDATE_EXTRACTION_VERSION
    assert first.text_sha256 == hashlib.sha256(text.encode()).hexdigest()
    assert any(
        item.normalized_text == "1250"
        for item in first.candidates
        if item.kind is VerificationCandidateKind.VALUE
    )
    value = next(
        item
        for item in first.candidates
        if item.kind is VerificationCandidateKind.VALUE and item.normalized_text == "1250"
    )
    assert str(value.decimal_value) == "1250"
    assert str(value.decimal_scale) == "1"
    assert any(
        item.normalized_text == "tonne"
        for item in first.candidates
        if item.kind is VerificationCandidateKind.UNIT
    )
    assert any(
        item.quoted_text == "June 2024"
        for item in first.candidates
        if item.kind is VerificationCandidateKind.DATE
    )
    month = next(
        item
        for item in first.candidates
        if item.kind is VerificationCandidateKind.DATE and item.quoted_text == "June 2024"
    )
    assert month.date_value.isoformat() == "2024-06-01"
    assert month.date_precision is VerificationCandidateDatePrecision.MONTH
    assert all(
        text[item.start_char : item.end_char] == item.quoted_text for item in first.candidates
    )


def test_ordinal_ranking_and_reference_year_are_typed() -> None:
    text = "Region Z ranked fourth-largest by measured output in 2024."
    packet = extract_verification_candidates(text)

    rank = next(item for item in packet.candidates if item.kind is VerificationCandidateKind.RANK)
    assert rank.normalized_text == "4"
    assert rank.ordinal_rank == 4
    assert any(
        item.kind is VerificationCandidateKind.DATE and item.quoted_text == "2024"
        for item in packet.candidates
    )
    assert any(group.kind is VerificationCandidateGroupKind.RANKING for group in packet.groups)


def test_projection_preserves_paired_values_and_dates() -> None:
    text = "The share is projected to rise from 18% in 2022 to 27% in 2040."
    packet = extract_verification_candidates(text)

    assert len(_items(text, VerificationCandidateKind.VALUE)) == 4
    assert any(item.kind is VerificationCandidateKind.PROJECTION for item in packet.candidates)
    projection = next(
        group for group in packet.groups if group.kind is VerificationCandidateGroupKind.PROJECTION
    )
    assert len(projection.candidate_ids) >= 5


def test_date_contained_numbers_are_diagnostic_not_material_operands() -> None:
    text = "The share rose 1.5% in 2025 and is projected at 1.6% in 2026."
    packet = extract_verification_candidates(text)
    values = {
        item.quoted_text: item
        for item in packet.candidates
        if item.kind is VerificationCandidateKind.VALUE
    }

    assert values["1.5%"].material
    assert values["1.6%"].material
    assert not values["2025"].material
    assert not values["2026"].material
    projection = next(
        group for group in packet.groups if group.kind is VerificationCandidateGroupKind.PROJECTION
    )
    assert values["2025"].candidate_id not in projection.candidate_ids
    assert values["2026"].candidate_id not in projection.candidate_ids


def test_day_and_year_inside_named_date_cannot_create_false_projection() -> None:
    text = "The population was estimated at 452.0 million on 1 January 2026."
    packet = extract_verification_candidates(text)
    values = [item for item in packet.candidates if item.kind is VerificationCandidateKind.VALUE]

    assert [(item.quoted_text, item.material) for item in values] == [
        ("452.0 million", True),
        ("1", False),
        ("2026", False),
    ]
    assert not any(
        group.kind is VerificationCandidateGroupKind.PROJECTION for group in packet.groups
    )


def test_word_numbers_and_implicit_superlative_ranks_are_typed() -> None:
    distance = extract_verification_candidates("The plate moves about two inches per year.")
    ranking = extract_verification_candidates("The summit is the farthest point from the center.")

    two = next(item for item in distance.candidates if item.kind is VerificationCandidateKind.VALUE)
    assert two.decimal_value == 2
    assert two.material
    assert any(
        item.kind is VerificationCandidateKind.UNIT and item.unit == "inch"
        for item in distance.candidates
    )
    first = next(item for item in ranking.candidates if item.kind is VerificationCandidateKind.RANK)
    assert first.ordinal_rank == 1
    assert first.rule_id == "implicit_first_rank"


def test_comparison_detects_both_values_units_and_relation() -> None:
    text = "The rotation takes 18 hours, longer than the 12-hour cycle."
    packet = extract_verification_candidates(text)

    assert {
        item.normalized_text
        for item in packet.candidates
        if item.kind is VerificationCandidateKind.VALUE
    } >= {"18", "12"}
    assert any(
        item.normalized_text == "greater_than"
        for item in packet.candidates
        if item.kind is VerificationCandidateKind.COMPARATOR
    )
    assert any(group.kind is VerificationCandidateGroupKind.COMPARISON for group in packet.groups)


def test_status_absence_quantifiers_and_material_qualifiers_are_separate() -> None:
    text = "Every ordinary unit is exactly 20 grams and is no longer active."
    packet = extract_verification_candidates(text)

    kinds = {item.kind for item in packet.candidates}
    assert VerificationCandidateKind.QUANTIFIER in kinds
    assert VerificationCandidateKind.STATUS in kinds
    assert VerificationCandidateKind.MATERIAL_QUALIFIER in kinds
    assert {
        item.normalized_text
        for item in packet.candidates
        if item.kind is VerificationCandidateKind.STATUS
    } == {"inactive"}


def test_compound_conditions_are_flagged_for_future_multi_assertion() -> None:
    text = "Discard the sample after it remains above 45°C for at least 3 hours."
    packet = extract_verification_candidates(text)

    assert packet.requires_multi_assertion
    group = next(
        item
        for item in packet.groups
        if item.kind is VerificationCandidateGroupKind.COMPOUND_CONDITION
    )
    assert len(group.candidate_ids) >= 5


def test_extraction_is_diagnostic_and_contains_no_decision_fields() -> None:
    fields = VerificationCandidateKind
    packet_fields = VerificationCandidateExtraction.model_fields

    assert fields.VALUE.value == "value"
    assert "verdict" not in packet_fields
    assert "verification_state" not in packet_fields
    assert "readiness" not in packet_fields
    assert "publication" not in packet_fields
