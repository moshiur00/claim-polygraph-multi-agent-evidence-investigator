"""Fail-closed deterministic assurance for structured report assertions."""

import re
from uuid import UUID

from claim_polygraph_ng.domain.citation import (
    AssertionEvidenceLink,
    CitationAssuranceFinding,
    CitationAssurancePacket,
    CitationAssuranceStatus,
    CitationIssueCode,
    StructuredReportAssertion,
)
from claim_polygraph_ng.domain.enums import EvidenceStance
from claim_polygraph_ng.domain.models import Evidence

_NON_WORD = re.compile(r"[^\w]+", re.UNICODE)


def audit_structured_assertions(
    *,
    claim_id: UUID,
    assertions: tuple[StructuredReportAssertion, ...],
    evidence: tuple[Evidence, ...],
    approved_evidence_ids: tuple[UUID, ...],
) -> CitationAssurancePacket:
    """Audit exact citations without inventing evidence or semantic entailment."""
    if not assertions:
        raise ValueError("at least one structured assertion is required")
    if any(item.claim_id != claim_id for item in assertions):
        raise ValueError("all assertions must match the audited claim")
    approved = set(approved_evidence_ids)
    records = {item.evidence_id: item for item in evidence}
    findings = tuple(
        _audit_one(assertion, approved=approved, records=records)
        for assertion in assertions
    )
    statuses = [item.status for item in findings]
    supported = statuses.count(CitationAssuranceStatus.SUPPORTED)
    return CitationAssurancePacket(
        claim_id=claim_id,
        approved_evidence_ids=approved_evidence_ids,
        findings=findings,
        supported_count=supported,
        partial_count=statuses.count(CitationAssuranceStatus.PARTIAL),
        unsupported_count=statuses.count(CitationAssuranceStatus.UNSUPPORTED),
        contradictory_count=statuses.count(CitationAssuranceStatus.CONTRADICTORY),
        out_of_packet_count=statuses.count(CitationAssuranceStatus.OUT_OF_PACKET),
        full_support_rate=supported / len(findings),
    )


def _audit_one(
    assertion: StructuredReportAssertion,
    *,
    approved: set[UUID],
    records: dict[UUID, Evidence],
) -> CitationAssuranceFinding:
    if not assertion.cited_evidence_ids:
        return _finding(
            assertion,
            status=CitationAssuranceStatus.UNSUPPORTED,
            issues=(CitationIssueCode.MISSING_CITATION,),
            explanation="The material assertion has no evidence citation.",
        )
    outside = set(assertion.cited_evidence_ids) - approved
    if outside:
        return _finding(
            assertion,
            status=CitationAssuranceStatus.OUT_OF_PACKET,
            issues=(CitationIssueCode.OUT_OF_PACKET,),
            explanation="The assertion cites evidence outside the approved packet.",
        )
    missing_records = [
        evidence_id
        for evidence_id in assertion.cited_evidence_ids
        if evidence_id not in records
    ]
    if missing_records:
        return _finding(
            assertion,
            status=CitationAssuranceStatus.OUT_OF_PACKET,
            issues=(CitationIssueCode.EVIDENCE_RECORD_MISSING,),
            explanation="An approved citation has no supplied evidence record.",
        )

    required = tuple(_normalize(item) for item in assertion.required_phrases)
    links = []
    matched: set[str] = set()
    stances = []
    for evidence_id in assertion.cited_evidence_ids:
        item = records[evidence_id]
        normalized_passage = _normalize(item.passage)
        item_matches = tuple(
            phrase
            for source, phrase in zip(assertion.required_phrases, required, strict=True)
            if phrase in normalized_passage
        )
        matched.update(_normalize(item_match) for item_match in item_matches)
        stances.append(item.stance)
        links.append(
            AssertionEvidenceLink(
                evidence_id=item.evidence_id,
                passage=item.passage,
                stance=item.stance,
                matched_phrases=item_matches,
            )
        )
    missing = tuple(
        source
        for source, normalized in zip(assertion.required_phrases, required, strict=True)
        if normalized not in matched
    )
    stance_match = any(item is assertion.asserted_stance for item in stances)
    opposite = _opposite(assertion.asserted_stance)
    if not missing and stance_match:
        return _finding(
            assertion,
            status=CitationAssuranceStatus.SUPPORTED,
            links=tuple(links),
            explanation=(
                "Every required phrase occurs in an exact cited passage "
                "with matching stance."
            ),
        )
    if opposite is not None and all(item is opposite for item in stances):
        return _finding(
            assertion,
            status=CitationAssuranceStatus.CONTRADICTORY,
            links=tuple(links),
            missing=missing,
            issues=(CitationIssueCode.STANCE_MISMATCH,),
            explanation="The cited evidence has the opposite stance to the assertion.",
        )
    issues = []
    if missing:
        issues.append(CitationIssueCode.MISSING_REQUIRED_PHRASE)
    if not stance_match:
        issues.append(CitationIssueCode.STANCE_MISMATCH)
    status = CitationAssuranceStatus.PARTIAL if matched else CitationAssuranceStatus.UNSUPPORTED
    return _finding(
        assertion,
        status=status,
        links=tuple(links),
        missing=missing,
        issues=tuple(issues),
        explanation=(
            "The citations match only part of the declared phrase and stance requirements."
            if status is CitationAssuranceStatus.PARTIAL
            else "The citations do not satisfy the declared phrase and stance requirements."
        ),
    )


def _finding(
    assertion: StructuredReportAssertion,
    *,
    status: CitationAssuranceStatus,
    issues: tuple[CitationIssueCode, ...] = (),
    explanation: str,
    links: tuple[AssertionEvidenceLink, ...] = (),
    missing: tuple[str, ...] = (),
) -> CitationAssuranceFinding:
    return CitationAssuranceFinding(
        assertion_id=assertion.assertion_id,
        sentence=assertion.sentence,
        material=assertion.material,
        critical=assertion.critical,
        status=status,
        links=links,
        missing_phrases=missing,
        issue_codes=issues,
        explanation=explanation,
    )


def _normalize(value: str) -> str:
    return " ".join(_NON_WORD.sub(" ", value.casefold()).split())


def _opposite(stance: EvidenceStance) -> EvidenceStance | None:
    if stance is EvidenceStance.SUPPORTS:
        return EvidenceStance.CONTRADICTS
    if stance is EvidenceStance.CONTRADICTS:
        return EvidenceStance.SUPPORTS
    return None
