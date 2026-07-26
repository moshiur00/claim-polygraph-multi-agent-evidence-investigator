"""Tests for temporal and numerical context checks."""

from datetime import UTC, date, datetime

from claim_polygraph_ng.analysis import verify_claim_context
from claim_polygraph_ng.domain import (
    AtomicClaim,
    Evidence,
    EvidenceStance,
    ExtractionStatus,
    InvestigationPlan,
    ResearchPath,
    Source,
    SourceType,
    VerificationStatus,
)


def _plan(claim_id, *, numerical=False, temporal=False):
    return InvestigationPlan(
        claim_id=claim_id,
        required_research_paths=(ResearchPath.PRIMARY, ResearchPath.CONTRADICTION),
        requires_numerical_check=numerical,
        requires_temporal_check=temporal,
    )


def _source(publication_date=None):
    return Source(
        url="https://agency.gov/report",
        canonical_url="https://agency.gov/report",
        title="Agency report",
        source_type=SourceType.OFFICIAL,
        publication_date=publication_date,
        retrieved_at=datetime.now(UTC),
        extraction_status=ExtractionStatus.EXTRACTED,
    )


def test_flags_exact_numerical_wording_and_missing_units() -> None:
    claim = AtomicClaim(
        text="Every sample is exactly 100 degrees Celsius.",
        quantities=("100",),
        checkworthiness=1.0,
    )
    source = _source()
    evidence = Evidence(
        claim_id=claim.claim_id,
        source_id=source.source_id,
        passage="Tests reported values of 99.97 under standard conditions.",
        stance=EvidenceStance.QUALIFIES,
        relevance_score=1.0,
    )

    verification = verify_claim_context(
        claim=claim,
        plan=_plan(claim.claim_id, numerical=True),
        sources=(source,),
        evidence=(evidence,),
    )

    assert verification.numerical.status is VerificationStatus.QUALIFIED
    assert verification.numerical.claim_values == ("100",)
    assert verification.numerical.exactness_terms == ("every", "exactly")
    assert any("claim units" in issue for issue in verification.numerical.issues)


def test_temporal_check_detects_postdated_sources() -> None:
    claim = AtomicClaim(
        text="The designation is currently active.",
        reference_date=date(2023, 5, 5),
        checkworthiness=1.0,
    )
    source = _source(date(2024, 1, 1))

    verification = verify_claim_context(
        claim=claim,
        plan=_plan(claim.claim_id, temporal=True),
        sources=(source,),
        evidence=(),
    )

    assert verification.temporal.status is VerificationStatus.QUALIFIED
    assert any("postdate" in issue for issue in verification.temporal.issues)


def test_unneeded_checks_are_explicit() -> None:
    claim = AtomicClaim(text="The sky appears blue.", checkworthiness=0.8)

    verification = verify_claim_context(
        claim=claim,
        plan=_plan(claim.claim_id),
        sources=(),
        evidence=(),
    )

    assert verification.numerical.status is VerificationStatus.NOT_REQUIRED
    assert verification.temporal.status is VerificationStatus.NOT_REQUIRED


def test_hyphenated_entity_number_is_not_treated_as_a_quantity() -> None:
    claim = AtomicClaim(
        text="COVID-19 is still under the designation.",
        checkworthiness=0.9,
    )

    verification = verify_claim_context(
        claim=claim,
        plan=_plan(claim.claim_id),
        sources=(),
        evidence=(),
    )

    assert verification.numerical.claim_values == ()
    assert verification.numerical.status is VerificationStatus.NOT_REQUIRED
