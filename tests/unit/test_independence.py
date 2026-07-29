"""Tests for deterministic evidence-family grouping."""

from datetime import UTC, datetime
from uuid import uuid4

from claim_polygraph_ng.analysis import analyze_source_independence
from claim_polygraph_ng.domain import (
    Evidence,
    EvidenceStance,
    ExtractionStatus,
    Source,
    SourceType,
)


def _source(url: str, publisher: str) -> Source:
    return Source(
        url=url,
        canonical_url=url,
        title=f"Source from {publisher}",
        source_type=SourceType.NEWS,
        publisher=publisher,
        retrieved_at=datetime.now(UTC),
        extraction_status=ExtractionStatus.EXTRACTED,
    )


def _evidence(claim_id, source, passage) -> Evidence:
    return Evidence(
        claim_id=claim_id,
        source_id=source.source_id,
        passage=passage,
        stance=EvidenceStance.SUPPORTS,
        relevance_score=0.9,
    )


def test_groups_shared_publishers_and_assigns_family_ids() -> None:
    claim_id = uuid4()
    original = _source("https://wire.example/report", "Shared Wire")
    republication = _source("https://news.example/story", "Shared Wire")
    independent = _source("https://agency.gov/record", "Public Agency")
    evidence = (
        _evidence(claim_id, original, "The reviewed measurement was 42 units."),
        _evidence(claim_id, republication, "The reviewed measurement was 42 units."),
        _evidence(claim_id, independent, "The agency independently reports 41.9 units."),
    )

    updated, analysis = analyze_source_independence(
        claim_id=claim_id,
        sources=(original, republication, independent),
        evidence=evidence,
        required_families=2,
    )

    assert analysis.independent_family_count == 2
    assert analysis.requirement_met
    assert all(item.evidence_family_id is not None for item in updated)
    assert updated[0].evidence_family_id == updated[1].evidence_family_id
    assert updated[2].evidence_family_id != updated[0].evidence_family_id
    shared = next(family for family in analysis.families if len(family.source_ids) == 2)
    assert "same_publisher" in shared.grouping_reasons
    assert "near_duplicate_passage" in shared.grouping_reasons


def test_groups_an_explicit_cross_citation() -> None:
    claim_id = uuid4()
    primary = _source("https://agency.gov/record", "Public Agency")
    secondary = _source("https://news.example/story", "Independent News")
    evidence = (
        _evidence(claim_id, primary, "The official record reports 42 units."),
        _evidence(
            claim_id,
            secondary,
            "This report relies on https://agency.gov/record for the measurement.",
        ),
    )

    _, analysis = analyze_source_independence(
        claim_id=claim_id,
        sources=(primary, secondary),
        evidence=evidence,
        required_families=2,
    )

    assert analysis.independent_family_count == 1
    assert not analysis.requirement_met
    assert "explicit_cross_citation" in analysis.families[0].grouping_reasons


def test_malformed_bracketed_url_in_passage_is_ignored() -> None:
    claim_id = uuid4()
    left = _source("https://one.example/report", "One Publisher")
    right = _source("https://two.example/report", "Two Publisher")
    evidence = (
        _evidence(
            claim_id,
            left,
            "Malformed citation https://example.org/[broken remains in text.",
        ),
        _evidence(claim_id, right, "Independent passage without a cross-citation."),
    )

    _, analysis = analyze_source_independence(
        claim_id=claim_id,
        sources=(left, right),
        evidence=evidence,
        required_families=2,
    )

    assert analysis.independent_family_count == 2
