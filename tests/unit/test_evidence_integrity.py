from datetime import timedelta
from uuid import uuid4

from claim_polygraph_ng.domain import (
    Evidence,
    EvidenceDispositionKind,
    EvidenceDispositionRecord,
    EvidenceStance,
    EvidentiaryUse,
    PassageHygieneStatus,
    assess_evidence_integrity,
    assess_evidence_packet,
)


def test_contaminated_decisive_passage_blocks_and_returns_bounded_quote() -> None:
    evidence = Evidence(
        claim_id=uuid4(),
        source_id=uuid4(),
        passage=(
            "Skip to main content User account menu Log in Subscribe Product directory. "
            "Water expands by about nine percent when it freezes because its crystal "
            "structure occupies more volume. Privacy policy All rights reserved."
        ),
        stance=EvidenceStance.SUPPORTS,
        relevance_score=0.91,
        evidentiary_use=EvidentiaryUse.DECISIVE,
    )

    assessment = assess_evidence_integrity(
        evidence,
        claim_text="Water expands when it freezes.",
        decisive=True,
    )

    assert assessment.status is PassageHygieneStatus.CONTAMINATED
    assert assessment.publication_blocking
    assert not assessment.argument_eligible
    assert not assessment.citation_eligible
    assert not assessment.decisive_use_eligible
    assert "Water expands" in assessment.exact_quote
    assert "substantial_boilerplate_detected" in assessment.reason_codes
    assert assessment.excerpt_status.value == "bounded_diagnostic"
    assert "reextract_source" in assessment.remediation_actions


def test_unspecified_decisive_use_fails_closed_even_for_clean_passage() -> None:
    evidence = Evidence(
        claim_id=uuid4(),
        source_id=uuid4(),
        passage="The official series records a value of 12.3 units.",
        stance=EvidenceStance.SUPPORTS,
        relevance_score=0.9,
    )

    assessment = assess_evidence_integrity(
        evidence,
        claim_text="The value is 12.3 units.",
        decisive=True,
    )

    assert assessment.status is PassageHygieneStatus.CLEAN
    assert assessment.publication_blocking
    assert assessment.argument_eligible
    assert not assessment.citation_eligible
    assert not assessment.decisive_use_eligible
    assert "decisive_use_unspecified" in assessment.reason_codes
    assert assessment.remediation_actions == (
        "record_approved_use",
        "exclude_from_decisive_packet",
    )


def test_chunk_backed_excerpt_exposes_verified_source_offsets() -> None:
    passage = "Context sentence. The official value is 12.3 units. Closing context."
    evidence = Evidence(
        claim_id=uuid4(),
        source_id=uuid4(),
        chunk_id=uuid4(),
        passage=passage,
        passage_start_char=100,
        passage_end_char=100 + len(passage),
        stance=EvidenceStance.SUPPORTS,
        relevance_score=0.9,
        evidentiary_use=EvidentiaryUse.QUALIFIED_OBSERVATION,
    )

    assessment = assess_evidence_integrity(
        evidence,
        claim_text="The official value is 12.3 units.",
    )

    assert assessment.excerpt_status.value == "source_span_verified"
    assert assessment.excerpt_start_char == 118
    assert assessment.excerpt_end_char == 150


def test_latest_append_only_disposition_controls_effective_use() -> None:
    evidence = Evidence(
        claim_id=uuid4(),
        source_id=uuid4(),
        passage="The official series records a value of 12.3 units.",
        stance=EvidenceStance.SUPPORTS,
        relevance_score=0.9,
    )
    investigation_id = uuid4()
    approved = EvidenceDispositionRecord(
        investigation_id=investigation_id,
        evidence_id=evidence.evidence_id,
        kind=EvidenceDispositionKind.APPROVE_USE,
        approved_use=EvidentiaryUse.CONTEXT,
        reason="The source was inspected.",
        reviewer_identity="Reviewer One",
        approver_identity="Approver Two",
    )
    excluded = EvidenceDispositionRecord(
        investigation_id=investigation_id,
        evidence_id=evidence.evidence_id,
        kind=EvidenceDispositionKind.EXCLUDE,
        reason="The retained passage is unsuitable.",
        reviewer_identity="Reviewer One",
        approver_identity="Approver Two",
        created_at=approved.created_at + timedelta(microseconds=1),
    )

    assessment = assess_evidence_packet(
        (evidence,),
        claim_text="The value is 12.3 units.",
        decisive_evidence_ids=(evidence.evidence_id,),
        dispositions=(approved, excluded),
    )[0]

    assert assessment.disposition_id == excluded.disposition_id
    assert assessment.disposition_kind is EvidenceDispositionKind.EXCLUDE
    assert assessment.approved_use is EvidentiaryUse.EXCLUDED
    assert not assessment.argument_eligible
    assert assessment.publication_blocking
