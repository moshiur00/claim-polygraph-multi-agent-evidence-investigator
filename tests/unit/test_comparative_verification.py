"""Tests for bounded qualitative-comparison construction."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from claim_polygraph_ng.analysis.comparative_verification import (
    construct_comparative_assertion,
)
from claim_polygraph_ng.analysis.context import verify_claim_context
from claim_polygraph_ng.analysis.verification_bridge import bridge_legacy_verification
from claim_polygraph_ng.domain import (
    AssertionConstructionState,
    AssertionVerificationState,
    AtomicClaim,
    Evidence,
    EvidenceStance,
    ExtractionStatus,
    InvestigationPlan,
    NumericComparator,
    ResearchPath,
    Source,
    SourceType,
)


def test_temperature_comparison_binds_shared_value_and_is_contradicted() -> None:
    claim = AtomicClaim(
        text="Earth's core is hotter than the surface of the sun.",
        checkworthiness=1.0,
    )
    source = Source(
        title="Earth's core far hotter than thought",
        url="https://example.test/core",
        canonical_url="https://example.test/core",
        source_type=SourceType.NEWS,
        retrieved_at=datetime.now(UTC),
        extraction_status=ExtractionStatus.EXTRACTED,
    )
    evidence = Evidence(
        claim_id=claim.claim_id,
        source_id=source.source_id,
        passage=(
            "New measurements put the Earth's inner core at 6,000C - "
            "as hot as the Sun's surface."
        ),
        stance=EvidenceStance.CONTRADICTS,
        relevance_score=1.0,
    )

    construction, assertion, finding = construct_comparative_assertion(
        claim=claim,
        evidence=(evidence,),
    )

    assert finding is None
    assert construction is not None
    assert construction.state is AssertionConstructionState.CONSTRUCTED
    assert construction.comparator is NumericComparator.GREATER_THAN
    assert assertion is not None
    assert assertion.state is AssertionVerificationState.CONTRADICTED
    assert assertion.normalized_result is not None
    assert assertion.normalized_result.value == 6000
    assert assertion.expected_values[0].value == 6000
    assert assertion.evidence_ids == (evidence.evidence_id,)


def test_detected_comparison_fails_closed_without_bound_operands() -> None:
    claim = AtomicClaim(
        text="Earth's core is hotter than the surface of the sun.",
        checkworthiness=1.0,
    )

    construction, assertion, finding = construct_comparative_assertion(
        claim=claim,
        evidence=(),
    )

    assert assertion is None
    assert construction is not None
    assert construction.state is AssertionConstructionState.FAILED
    assert construction.failure_code == "comparative_evidence_operands_missing"
    assert finding is not None
    assert finding.code == "comparative_evidence_operands_missing"


def test_comparison_flows_into_authoritative_verification_packet() -> None:
    claim = AtomicClaim(
        text="Earth's core is hotter than the surface of the sun.",
        checkworthiness=1.0,
    )
    source = Source(
        title="Temperature comparison",
        url="https://example.test/comparison",
        canonical_url="https://example.test/comparison",
        source_type=SourceType.NEWS,
        retrieved_at=datetime.now(UTC),
        extraction_status=ExtractionStatus.EXTRACTED,
    )
    evidence = Evidence(
        claim_id=claim.claim_id,
        source_id=source.source_id,
        passage=(
            "Measurements put the Earth's core at 6,000C, "
            "as hot as the Sun's surface."
        ),
        stance=EvidenceStance.CONTRADICTS,
        relevance_score=1.0,
    )
    plan = InvestigationPlan(
        claim_id=claim.claim_id,
        required_research_paths=(ResearchPath.PRIMARY, ResearchPath.CONTRADICTION),
        requires_numerical_check=True,
    )

    context = verify_claim_context(
        claim=claim,
        plan=plan,
        sources=(source,),
        evidence=(evidence,),
    )
    packet = bridge_legacy_verification(
        claim=claim,
        legacy=context,
        sources=(source,),
        evidence=(evidence,),
    )

    assert "claim_value_missing" not in {
        finding.code for finding in context.numerical.findings
    }
    assert len(packet.comparative_constructions) == 1
    assert packet.comparative_constructions[0].state is AssertionConstructionState.CONSTRUCTED
    assert len(packet.numerical_assertions) == 1
    assert packet.numerical_assertions[0].state is AssertionVerificationState.CONTRADICTED


@pytest.mark.parametrize(
    ("claim_text", "passage", "expected_state"),
    [
        (
            "Artifact A is older than Artifact B.",
            "Artifact A is 12 years old while Artifact B is 10 years old.",
            AssertionVerificationState.VERIFIED,
        ),
        (
            "Route A is longer than Route B.",
            "Route A is 5 kilometres long while Route B is 4000 metres long.",
            AssertionVerificationState.VERIFIED,
        ),
        (
            "Sample A is heavier than Sample B.",
            "Sample A weighs 2 kilograms while Sample B weighs 2500 grams.",
            AssertionVerificationState.CONTRADICTED,
        ),
        (
            "District A has a higher percentage than District B.",
            "District A recorded 62 percent while District B recorded 58 percent.",
            AssertionVerificationState.VERIFIED,
        ),
        (
            "Team A has a greater count than Team B.",
            "Team A has 12 members while Team B has 10 members.",
            AssertionVerificationState.VERIFIED,
        ),
        (
            "Chamber A has a higher pressure than Chamber B.",
            "Chamber A measured 110 kilopascals while Chamber B measured 1 atmosphere.",
            AssertionVerificationState.VERIFIED,
        ),
        (
            "Vehicle A is faster than Vehicle B.",
            "Vehicle A reached 100 kilometres per hour while Vehicle B reached 70 miles per hour.",
            AssertionVerificationState.CONTRADICTED,
        ),
        (
            "Plan A is more expensive than Plan B.",
            "Plan A costs $120 while Plan B costs 100 USD.",
            AssertionVerificationState.VERIFIED,
        ),
    ],
)
def test_allowlisted_comparison_dimensions(
    claim_text: str,
    passage: str,
    expected_state: AssertionVerificationState,
) -> None:
    claim = AtomicClaim(text=claim_text, checkworthiness=1.0)
    source = Source(
        title="Measurement record",
        url="https://example.test/measurements",
        canonical_url="https://example.test/measurements",
        source_type=SourceType.OFFICIAL,
        retrieved_at=datetime.now(UTC),
        extraction_status=ExtractionStatus.EXTRACTED,
    )
    evidence = Evidence(
        claim_id=claim.claim_id,
        source_id=source.source_id,
        passage=passage,
        stance=EvidenceStance.SUPPORTS,
        relevance_score=1.0,
    )

    construction, assertion, finding = construct_comparative_assertion(
        claim=claim,
        evidence=(evidence,),
    )

    assert construction is not None
    assert construction.state is AssertionConstructionState.CONSTRUCTED
    assert assertion is not None
    assert assertion.state is expected_state
    assert finding is None


def test_frozen_comparative_benchmark_matches_declared_outcomes() -> None:
    payload = json.loads(
        Path("benchmarks/comparative_verification_v1.json").read_text(encoding="utf-8")
    )
    assert payload["frozen"] is True
    assert len({case["case_id"] for case in payload["cases"]}) == len(payload["cases"])

    for case in payload["cases"]:
        claim = AtomicClaim(text=case["claim"], checkworthiness=1.0)
        source = Source(
            title=f"Fixture {case['case_id']}",
            url=f"https://example.test/{case['case_id'].lower()}",
            canonical_url=f"https://example.test/{case['case_id'].lower()}",
            source_type=SourceType.OFFICIAL,
            retrieved_at=datetime.now(UTC),
            extraction_status=ExtractionStatus.EXTRACTED,
        )
        evidence = Evidence(
            claim_id=claim.claim_id,
            source_id=source.source_id,
            passage=case["passage"],
            stance=EvidenceStance.CONTEXT,
            relevance_score=1.0,
        )
        construction, assertion, _ = construct_comparative_assertion(
            claim=claim,
            evidence=(evidence,),
        )

        assert construction is not None, case["case_id"]
        assert construction.state.value == case["expected_construction"], case["case_id"]
        observed = assertion.state.value if assertion else None
        assert observed == case["expected_verification"], case["case_id"]
