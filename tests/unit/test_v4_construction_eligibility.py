"""V4.4 typed candidate-driven construction eligibility."""

import pytest

from claim_polygraph_ng.analysis import (
    CONSTRUCTION_ELIGIBILITY_VERSION,
    construct_linked_assertions,
    extract_verification_candidates,
    route_construction_eligibility,
)
from claim_polygraph_ng.domain import (
    ConstructionEligibilityDecision,
    ConstructionEligibilityReason,
    ConstructionEligibilityRoute,
)


def _route(text: str):
    extraction = extract_verification_candidates(text)
    constructions = construct_linked_assertions(text, extraction)
    return route_construction_eligibility(text, extraction, constructions)


@pytest.mark.parametrize(
    "text",
    [
        "The package contains 24 bones.",
        "Every ordinary adult has exactly 206 bones.",
        "The rule took effect on 25 May 2018.",
        "The local system no longer uses 20 vehicles as of 2021.",
    ],
)
def test_ordinary_typed_language_is_not_broadly_excluded(text: str) -> None:
    packet = _route(text)

    assert packet.assisted_count >= 1
    assert packet.not_applicable_count == 0


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        (
            "Using the device causes better health outcomes.",
            ConstructionEligibilityReason.CAUSAL_CLAIM,
        ),
        (
            "This is the best public policy.",
            ConstructionEligibilityReason.OPEN_WORLD_SUPERLATIVE,
        ),
        (
            "Everyone always prefers this design.",
            ConstructionEligibilityReason.QUALITATIVE_GENERALIZATION,
        ),
        (
            "Tall structures do not need protection against repeated strikes.",
            ConstructionEligibilityReason.QUALITATIVE_GENERALIZATION,
        ),
    ],
)
def test_open_world_causal_and_qualitative_claims_remain_excluded(
    text: str,
    reason: ConstructionEligibilityReason,
) -> None:
    decision = _route(text).decisions[0]

    assert decision.route is ConstructionEligibilityRoute.NOT_APPLICABLE
    assert reason in decision.reasons


def test_complete_linked_group_routes_to_deterministic_construction() -> None:
    text = "The rotation takes 18 hours, longer than the 12-hour cycle."
    packet = _route(text)
    decision = next(item for item in packet.decisions if item.group_id is not None)

    assert decision.route is ConstructionEligibilityRoute.DETERMINISTIC
    assert decision.linked_construction_id is not None
    assert ConstructionEligibilityReason.COMPLETE_LINKED_GROUP in decision.reasons


def test_explicit_ordinal_rank_is_not_an_open_world_superlative() -> None:
    packet = _route("Region Z ranked fourth-largest by measured output in 2024.")

    assert packet.deterministic_count == 1
    assert packet.not_applicable_count == 0


def test_incomplete_group_with_typed_basis_routes_to_assistance() -> None:
    text = "The rotation takes 18 hours, longer than the 12-hour cycle."
    extraction = extract_verification_candidates(text)
    group = extraction.groups[0]
    value_ids = [item.candidate_id for item in extraction.candidates if item.kind.value == "value"]
    incomplete = extraction.model_copy(
        update={
            "groups": (
                group.model_copy(
                    update={
                        "candidate_ids": tuple(
                            item for item in group.candidate_ids if item != value_ids[-1]
                        )
                    }
                ),
            )
        }
    )
    constructions = construct_linked_assertions(text, incomplete)

    decision = route_construction_eligibility(text, incomplete, constructions).decisions[0]

    assert decision.route is ConstructionEligibilityRoute.ASSISTED
    assert ConstructionEligibilityReason.BOUNDED_CONSTRUCTION_AMBIGUITY in decision.reasons


def test_incomplete_group_without_typed_basis_routes_to_human_review() -> None:
    text = "The rotation takes 18 hours, longer than the 12-hour cycle."
    extraction = extract_verification_candidates(text)
    group = extraction.groups[0]
    non_values = tuple(
        item.candidate_id
        for item in extraction.candidates
        if item.kind.value not in {"value", "date", "rank", "status"}
    )
    incomplete = extraction.model_copy(
        update={"groups": (group.model_copy(update={"candidate_ids": non_values}),)}
    )
    constructions = construct_linked_assertions(text, incomplete)

    packet = route_construction_eligibility(text, incomplete, constructions)
    decision = packet.decisions[0]

    assert decision.route is ConstructionEligibilityRoute.HUMAN_REVIEW
    assert decision.requires_human_review
    assert packet.requires_human_review


def test_packets_from_different_claims_are_rejected() -> None:
    text = "The package contains 24 bones."
    extraction = extract_verification_candidates(text)
    constructions = construct_linked_assertions(text, extraction)

    with pytest.raises(ValueError, match="different claim text"):
        route_construction_eligibility("A different claim.", extraction, constructions)


def test_eligibility_has_no_truth_or_publication_authority() -> None:
    fields = ConstructionEligibilityDecision.model_fields

    assert CONSTRUCTION_ELIGIBILITY_VERSION.endswith("-v1")
    assert "verdict" not in fields
    assert "verification_state" not in fields
    assert "readiness" not in fields
    assert "publication" not in fields
