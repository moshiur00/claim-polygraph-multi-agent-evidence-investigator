"""Stable serialization behavior for stored and handed-off artifacts."""

from uuid import uuid4

from claim_polygraph_ng.domain import (
    AtomicClaim,
    ClaimType,
    Evidence,
    EvidenceStance,
)


def test_claim_round_trip_preserves_typed_values() -> None:
    claim = AtomicClaim(
        text="Global temperature in 2025 exceeded the 2024 value.",
        claim_type=ClaimType.COMPARATIVE,
        entities=("global temperature",),
        quantities=("2025", "2024"),
        ambiguities=("temperature dataset is unspecified",),
        checkworthiness=0.95,
    )

    restored = AtomicClaim.model_validate_json(claim.model_dump_json())

    assert restored == claim
    assert restored.claim_type is ClaimType.COMPARATIVE


def test_evidence_json_uses_string_enums_and_identifiers() -> None:
    evidence = Evidence(
        claim_id=uuid4(),
        source_id=uuid4(),
        passage="The report records the relevant measurement.",
        stance=EvidenceStance.SUPPORTS,
        relevance_score=0.91,
        entailment_score=0.82,
    )

    payload = evidence.model_dump(mode="json")

    assert payload["stance"] == "supports"
    assert isinstance(payload["evidence_id"], str)
    assert isinstance(payload["claim_id"], str)
