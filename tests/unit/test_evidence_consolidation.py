from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from claim_polygraph_ng.analysis import consolidate_evidence
from claim_polygraph_ng.domain import (
    ConsolidationReason,
    Evidence,
    EvidenceStance,
    ExtractionStatus,
    Source,
    SourceType,
)


def test_same_canonical_source_and_exact_evidence_are_consolidated() -> None:
    claim_id = uuid4()
    first = _source("https://www.example.org/report?b=2&a=1#top", "Publisher")
    second = _source("https://example.org/report?a=1&b=2", "Publisher")
    first_evidence = _evidence(
        claim_id,
        first.source_id,
        "The official total was 42 units.",
    )
    duplicate = _evidence(
        claim_id,
        second.source_id,
        "  the official total was 42 units. ",
    )

    result = consolidate_evidence(
        claim_id=claim_id,
        sources=(second, first),
        evidence=(duplicate, first_evidence),
        required_families=1,
    )

    assert len(result.sources) == 1
    assert len(result.evidence) == 1
    assert result.removed_source_count == 1
    assert result.removed_evidence_count == 1
    assert result.source_decisions[0].reasons == (ConsolidationReason.CANONICAL_URL,)
    assert result.evidence_decisions[0].reasons == (ConsolidationReason.EXACT_NORMALIZED_PASSAGE,)


def test_syndicated_near_duplicates_share_family_but_remain_auditable() -> None:
    claim_id = uuid4()
    wire = _source("https://wire.example/report", "Shared Wire")
    copy = _source("https://news.example/story", "Shared Wire")
    evidence = (
        _evidence(
            claim_id,
            wire.source_id,
            "The reviewed official measurement was exactly 42 units in 2025.",
        ),
        _evidence(
            claim_id,
            copy.source_id,
            "The reviewed official measurement was 42 units in 2025.",
        ),
    )

    result = consolidate_evidence(
        claim_id=claim_id,
        sources=(wire, copy),
        evidence=evidence,
        required_families=2,
    )

    assert len(result.evidence) == 2
    assert result.independence.independent_family_count == 1
    assert not result.independence.requirement_met
    assert "same_publisher" in result.independence.families[0].grouping_reasons


def test_identical_passage_with_conflicting_stances_is_not_merged() -> None:
    claim_id = uuid4()
    source = _source("https://example.org/ambiguous", "Independent")
    passage = "The reported association was not statistically significant."

    result = consolidate_evidence(
        claim_id=claim_id,
        sources=(source,),
        evidence=(
            _evidence(claim_id, source.source_id, passage, EvidenceStance.SUPPORTS),
            _evidence(claim_id, source.source_id, passage, EvidenceStance.CONTRADICTS),
        ),
        required_families=1,
    )

    assert len(result.evidence) == 2
    assert {item.stance for item in result.evidence} == {
        EvidenceStance.SUPPORTS,
        EvidenceStance.CONTRADICTS,
    }
    assert result.evidence_decisions == ()


def test_consolidation_is_invariant_to_input_order() -> None:
    claim_id = uuid4()
    sources = (
        _source("https://one.example/report", "One"),
        _source("https://two.example/report", "Two"),
        _source("https://three.example/report", "Three"),
    )
    evidence = tuple(
        _evidence(
            claim_id,
            source.source_id,
            f"Independent finding number {index} has distinct substantive details.",
        )
        for index, source in enumerate(sources, start=1)
    )

    forward = consolidate_evidence(
        claim_id=claim_id,
        sources=sources,
        evidence=evidence,
        required_families=2,
    )
    reverse = consolidate_evidence(
        claim_id=claim_id,
        sources=tuple(reversed(sources)),
        evidence=tuple(reversed(evidence)),
        required_families=2,
    )

    assert reverse == forward


def test_consolidation_rejects_unstored_source_reference() -> None:
    claim_id = uuid4()
    source = _source("https://example.org/report", "Publisher")

    with pytest.raises(ValueError, match="supplied source"):
        consolidate_evidence(
            claim_id=claim_id,
            sources=(source,),
            evidence=(_evidence(claim_id, uuid4(), "An orphaned evidence passage."),),
            required_families=1,
        )


def _source(url: str, publisher: str) -> Source:
    return Source(
        source_id=uuid4(),
        url=url,
        canonical_url=url,
        title=f"Source from {publisher}",
        source_type=SourceType.NEWS,
        publisher=publisher,
        retrieved_at=datetime.now(UTC),
        extraction_status=ExtractionStatus.EXTRACTED,
    )


def _evidence(
    claim_id: UUID,
    source_id: UUID,
    passage: str,
    stance: EvidenceStance = EvidenceStance.SUPPORTS,
) -> Evidence:
    return Evidence(
        evidence_id=uuid4(),
        claim_id=claim_id,
        source_id=source_id,
        passage=passage,
        stance=stance,
        relevance_score=0.9,
    )
