"""Offline regression tests for the V4.9a exposed calibration failures."""

from datetime import date
from pathlib import Path
from uuid import uuid4

from claim_polygraph_ng.analysis import (
    construct_linked_assertions,
    extract_verification_candidates,
    route_construction_eligibility,
)
from claim_polygraph_ng.analysis.assisted_verification_construction import (
    AssistedConstructionEligibility,
    AssistedConstructionKind,
    AssistedConstructionProposal,
    AssistedTemporalEvidenceBinding,
    canonicalize_assisted_proposal,
    resolve_assisted_eligibility,
)
from claim_polygraph_ng.domain import (
    DatePrecision,
    Evidence,
    EvidenceStance,
    TemporalInstant,
    TemporalInterval,
    TemporalRelation,
)
from claim_polygraph_ng.evaluation.v3_annotation import (
    load_replacement_calibration_workbook,
)

ROOT = Path(__file__).parents[2]


def _resolved(claim: str) -> AssistedConstructionEligibility:
    extraction = extract_verification_candidates(claim)
    constructions = construct_linked_assertions(claim, extraction)
    routing = route_construction_eligibility(claim, extraction, constructions)
    return resolve_assisted_eligibility(
        claim_text=claim,
        extraction=extraction,
        routing=routing,
    )


def test_exposed_classifier_disagreements_use_the_authoritative_typed_route() -> None:
    workbook = load_replacement_calibration_workbook(
        ROOT / "benchmarks/"
        "verification_construction_v4_stage8_fresh_calibration_workbook_v1_APPROVED.json"
    )
    expected = {
        "V3-311": AssistedConstructionEligibility.TEMPORAL,
        "V3-312": AssistedConstructionEligibility.NUMERICAL_SCALAR,
        "V3-314": AssistedConstructionEligibility.NUMERICAL_SCALAR,
    }
    cases = {case.case_id: case for case in workbook.cases}

    assert {case_id: _resolved(cases[case_id].claim_text) for case_id in expected} == expected


def test_temporal_quote_repair_uses_one_explicit_date_and_status_sentence() -> None:
    claim_id = uuid4()
    passage = (
        "Background context. On March 31, 1995 at a ceremony at SSA Headquarters in "
        "Baltimore, SSA once again became an independent agency."
    )
    evidence = Evidence(
        claim_id=claim_id,
        source_id=uuid4(),
        passage=passage,
        stance=EvidenceStance.CONTEXT,
        relevance_score=1,
    )
    instant = TemporalInstant(value=date(1995, 3, 31), precision=DatePrecision.DAY)
    proposal = AssistedConstructionProposal(
        kind=AssistedConstructionKind.TEMPORAL_STATUS,
        failed_construction_id=uuid4(),
        claim_text_span="SSA returned to independent agency status on March 31, 1995.",
        temporal_relation=TemporalRelation.CHANGED_STATUS,
        reference_date=instant,
        claimed_status="independent agency status",
        temporal_bindings=(
            AssistedTemporalEvidenceBinding(
                evidence_id=evidence.evidence_id,
                start_char=0,
                end_char=5,
                quoted_text="wrong",
                effective_interval=TemporalInterval(start=instant, end=instant),
                observed_status="independent agency status",
            ),
        ),
    )

    repaired = canonicalize_assisted_proposal(proposal=proposal, evidence=(evidence,))
    binding = repaired.temporal_bindings[0]

    assert binding.quoted_text == passage[binding.start_char : binding.end_char]
    assert binding.observed_status == "once again became an independent agency"
    assert binding.observed_status in binding.quoted_text


def test_ambiguous_temporal_sentences_remain_unrepaired() -> None:
    claim_id = uuid4()
    passage = (
        "On March 31, 1995, Alpha became independent. On March 31, 1995, Beta became independent."
    )
    evidence = Evidence(
        claim_id=claim_id,
        source_id=uuid4(),
        passage=passage,
        stance=EvidenceStance.CONTEXT,
        relevance_score=1,
    )
    instant = TemporalInstant(value=date(1995, 3, 31), precision=DatePrecision.DAY)
    proposal = AssistedConstructionProposal(
        kind=AssistedConstructionKind.TEMPORAL_STATUS,
        failed_construction_id=uuid4(),
        claim_text_span="Alpha changed status on March 31, 1995.",
        temporal_relation=TemporalRelation.CHANGED_STATUS,
        reference_date=instant,
        claimed_status="changed status",
        temporal_bindings=(
            AssistedTemporalEvidenceBinding(
                evidence_id=evidence.evidence_id,
                start_char=0,
                end_char=5,
                quoted_text="wrong",
                effective_interval=TemporalInterval(start=instant, end=instant),
                observed_status="became independent",
            ),
        ),
    )

    repaired = canonicalize_assisted_proposal(proposal=proposal, evidence=(evidence,))

    assert repaired.temporal_bindings[0].quoted_text == "wrong"
