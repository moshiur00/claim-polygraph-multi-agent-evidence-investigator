"""Deterministic sentence-level citation assurance tests."""

from uuid import uuid4

from claim_polygraph_ng.analysis import audit_structured_assertions
from claim_polygraph_ng.domain import (
    CitationAssuranceStatus,
    CitationIssueCode,
    Evidence,
    EvidenceStance,
    StructuredReportAssertion,
)


def _evidence(claim_id, *, stance=EvidenceStance.CONTRADICTS, passage=None):
    return Evidence(
        claim_id=claim_id,
        source_id=uuid4(),
        passage=passage
        or "Normal human visual resolution cannot distinguish the Great Wall at lunar distance.",
        stance=stance,
        relevance_score=1,
    )


def test_exact_approved_passage_with_required_phrases_is_supported() -> None:
    claim_id = uuid4()
    evidence = _evidence(claim_id)
    assertion = StructuredReportAssertion(
        claim_id=claim_id,
        sentence="The wall cannot be distinguished at lunar distance.",
        cited_evidence_ids=(evidence.evidence_id,),
        asserted_stance=EvidenceStance.CONTRADICTS,
        required_phrases=("visual resolution", "lunar distance"),
        critical=True,
    )

    packet = audit_structured_assertions(
        claim_id=claim_id,
        assertions=(assertion,),
        evidence=(evidence,),
        approved_evidence_ids=(evidence.evidence_id,),
    )

    finding = packet.findings[0]
    assert finding.status is CitationAssuranceStatus.SUPPORTED
    assert finding.links[0].passage == evidence.passage
    assert packet.full_support_rate == 1


def test_missing_and_out_of_packet_citations_fail_closed() -> None:
    claim_id = uuid4()
    evidence = _evidence(claim_id)
    missing = StructuredReportAssertion(
        claim_id=claim_id,
        sentence="The wall cannot be distinguished.",
        asserted_stance=EvidenceStance.CONTRADICTS,
        required_phrases=("cannot distinguish",),
    )
    outside = missing.model_copy(
        update={"assertion_id": uuid4(), "cited_evidence_ids": (uuid4(),)}
    )

    packet = audit_structured_assertions(
        claim_id=claim_id,
        assertions=(missing, outside),
        evidence=(evidence,),
        approved_evidence_ids=(evidence.evidence_id,),
    )

    assert packet.findings[0].status is CitationAssuranceStatus.UNSUPPORTED
    assert CitationIssueCode.MISSING_CITATION in packet.findings[0].issue_codes
    assert packet.findings[1].status is CitationAssuranceStatus.OUT_OF_PACKET


def test_stance_mismatch_and_missing_phrase_are_not_supported() -> None:
    claim_id = uuid4()
    evidence = _evidence(
        claim_id,
        stance=EvidenceStance.SUPPORTS,
        passage="A long-lens photograph captured the wall from low Earth orbit.",
    )
    contradictory = StructuredReportAssertion(
        claim_id=claim_id,
        sentence="The evidence contradicts visibility.",
        cited_evidence_ids=(evidence.evidence_id,),
        asserted_stance=EvidenceStance.CONTRADICTS,
        required_phrases=("low Earth orbit",),
    )
    partial = contradictory.model_copy(
        update={
            "assertion_id": uuid4(),
            "asserted_stance": EvidenceStance.SUPPORTS,
            "required_phrases": ("long-lens photograph", "unaided eye"),
        }
    )

    packet = audit_structured_assertions(
        claim_id=claim_id,
        assertions=(contradictory, partial),
        evidence=(evidence,),
        approved_evidence_ids=(evidence.evidence_id,),
    )

    assert packet.findings[0].status is CitationAssuranceStatus.CONTRADICTORY
    assert packet.findings[1].status is CitationAssuranceStatus.PARTIAL
    assert packet.supported_count == 0
