"""Tests for bounded evidence-grounded temporal construction."""

from datetime import UTC, datetime

from claim_polygraph_ng.analysis.temporal_construction import (
    construct_temporal_comparison,
)
from claim_polygraph_ng.domain import (
    AssertionConstructionState,
    AssertionVerificationState,
    AtomicClaim,
    Evidence,
    EvidenceStance,
    ExtractionStatus,
    Source,
    SourceType,
    TemporalRelation,
)


def _evidence(claim: AtomicClaim, passage: str) -> Evidence:
    source = Source(
        title="Official chronology",
        url="https://example.test/chronology",
        canonical_url="https://example.test/chronology",
        source_type=SourceType.OFFICIAL,
        retrieved_at=datetime.now(UTC),
        extraction_status=ExtractionStatus.EXTRACTED,
    )
    return Evidence(
        claim_id=claim.claim_id,
        source_id=source.source_id,
        passage=passage,
        stance=EvidenceStance.CONTEXT,
        relevance_score=1.0,
    )


def test_temporal_comparison_binds_dates_and_verifies_before() -> None:
    claim = AtomicClaim(
        text="Event A occurred before Event B.",
        checkworthiness=1.0,
    )
    evidence = _evidence(
        claim,
        "Event A occurred on 2020-01-02 while Event B occurred on 2021-03-04.",
    )

    construction, assertion, finding = construct_temporal_comparison(
        claim=claim,
        evidence=(evidence,),
    )

    assert finding is None
    assert construction is not None
    assert construction.state is AssertionConstructionState.CONSTRUCTED
    assert construction.relation is TemporalRelation.BEFORE
    assert assertion is not None
    assert assertion.state is AssertionVerificationState.VERIFIED


def test_temporal_comparison_fails_closed_without_two_bound_dates() -> None:
    claim = AtomicClaim(
        text="Event A happened after Event B.",
        checkworthiness=1.0,
    )

    construction, assertion, finding = construct_temporal_comparison(
        claim=claim,
        evidence=(_evidence(claim, "Event A happened in 2024."),),
    )

    assert assertion is None
    assert construction is not None
    assert construction.state is AssertionConstructionState.FAILED
    assert construction.failure_code == "temporal_comparison_dates_missing"
    assert finding is not None
