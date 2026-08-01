"""V4.3 linked compound-assertion construction."""

import pytest
from pydantic import ValidationError

from claim_polygraph_ng.analysis import (
    LINKED_ASSERTION_CONSTRUCTION_VERSION,
    construct_linked_assertions,
    extract_verification_candidates,
)
from claim_polygraph_ng.domain import (
    LinkedAssertionComponentKind,
    LinkedAssertionConstruction,
    LinkedAssertionConstructionState,
    LinkedAssertionRelation,
)


@pytest.mark.parametrize(
    ("text", "group_kind", "relation"),
    [
        (
            "The rotation takes 18 hours, longer than the 12-hour cycle.",
            "comparison",
            LinkedAssertionRelation.COMPARES_TO,
        ),
        (
            "The safe range is between 18 hours and 27 hours.",
            "range",
            LinkedAssertionRelation.RANGE_BOUNDS,
        ),
        (
            "Region Z ranked fourth-largest by measured output in 2024.",
            "ranking",
            LinkedAssertionRelation.QUALIFIES,
        ),
        (
            "The share is projected to rise from 18% in 2022 to 27% in 2040.",
            "projection",
            LinkedAssertionRelation.PROJECTS_TO,
        ),
    ],
)
def test_supported_groups_construct_linked_assertions(
    text: str,
    group_kind: str,
    relation: LinkedAssertionRelation,
) -> None:
    packet = construct_linked_assertions(text, extract_verification_candidates(text))
    construction = next(item for item in packet.constructions if item.group_kind == group_kind)

    assert construction.state is LinkedAssertionConstructionState.CONSTRUCTED
    assert any(edge.relation is relation for edge in construction.edges)
    assert {
        candidate_id
        for component in construction.components
        for candidate_id in component.candidate_ids
    } == set(construction.required_candidate_ids)


def test_compound_conditions_preserve_conditions_and_consequence() -> None:
    text = "Discard the sample after it remains above 45 kilograms for at least 3 hours."
    packet = construct_linked_assertions(text, extract_verification_candidates(text))
    construction = next(
        item for item in packet.constructions if item.group_kind == "compound_condition"
    )

    assert construction.state is LinkedAssertionConstructionState.CONSTRUCTED
    values = [
        item
        for item in construction.components
        if item.kind is LinkedAssertionComponentKind.VALUE_CONDITION
    ]
    consequence = next(
        item
        for item in construction.components
        if item.kind is LinkedAssertionComponentKind.CONSEQUENCE
    )
    assert {str(item.decimal_value) for item in values} == {"45", "3"}
    assert consequence.quoted_text == "Discard the sample"
    assert any(edge.relation is LinkedAssertionRelation.IMPLIES for edge in construction.edges)
    assert packet.material_coverage == 1
    assert not packet.requires_human_review


def test_every_component_has_an_exact_source_span() -> None:
    text = "The share is projected to rise from 18% in 2022 to 27% in 2040."
    packet = construct_linked_assertions(text, extract_verification_candidates(text))

    assert packet.constructions
    assert all(
        text[item.start_char : item.end_char] == item.quoted_text
        for construction in packet.constructions
        for item in construction.components
    )


def test_projection_components_never_use_date_tokens_as_values() -> None:
    text = "Growth was 1.5% in 2025 and is projected at 1.6% in 2026."
    packet = construct_linked_assertions(text, extract_verification_candidates(text))
    construction = next(item for item in packet.constructions if item.group_kind == "projection")
    values = {
        str(item.decimal_value)
        for item in construction.components
        if item.kind is LinkedAssertionComponentKind.VALUE_CONDITION
    }

    assert values == {"1.5", "1.6"}


def test_incomplete_group_fails_closed_without_partial_components() -> None:
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

    packet = construct_linked_assertions(text, incomplete)
    construction = packet.constructions[0]

    assert construction.state is LinkedAssertionConstructionState.UNCONSTRUCTED
    assert construction.failure_code == "missing_material_value"
    assert construction.components == ()
    assert construction.edges == ()
    assert packet.requires_human_review


def test_contract_rejects_omitted_or_duplicate_material_operands() -> None:
    text = "The rotation takes 18 hours, longer than the 12-hour cycle."
    construction = construct_linked_assertions(
        text, extract_verification_candidates(text)
    ).constructions[0]
    first, second = construction.components

    omitted_ids = first.candidate_ids[:-1]
    assert omitted_ids
    with pytest.raises(ValidationError, match="cover every material candidate"):
        LinkedAssertionConstruction.model_validate(
            construction.model_copy(
                update={
                    "components": (
                        first.model_copy(update={"candidate_ids": omitted_ids}),
                        second,
                    )
                }
            ).model_dump()
        )

    duplicated = second.model_copy(
        update={
            "candidate_ids": (
                *second.candidate_ids,
                first.candidate_ids[0],
            )
        }
    )
    with pytest.raises(ValidationError, match="assigned exactly once"):
        LinkedAssertionConstruction.model_validate(
            construction.model_copy(update={"components": (first, duplicated)}).model_dump()
        )


def test_packet_rejects_candidate_data_from_another_claim() -> None:
    extraction = extract_verification_candidates(
        "The rotation takes 18 hours, longer than the 12-hour cycle."
    )

    with pytest.raises(ValueError, match="different claim text"):
        construct_linked_assertions("A different claim.", extraction)


def test_contract_has_no_verdict_or_publication_authority() -> None:
    fields = LinkedAssertionConstruction.model_fields

    assert LINKED_ASSERTION_CONSTRUCTION_VERSION.endswith("-v1")
    assert "verdict" not in fields
    assert "verification_state" not in fields
    assert "readiness" not in fields
    assert "publication" not in fields
