"""Fail-closed deterministic assurance for structured report assertions."""

import re
from uuid import NAMESPACE_URL, UUID, uuid5

from claim_polygraph_ng.domain.citation import (
    AssertionEvidenceLink,
    CitationAssuranceFinding,
    CitationAssurancePacket,
    CitationAssuranceStatus,
    CitationIssueCode,
    CitationRevision,
    FullReportCitationAssurance,
    PublicationGateStatus,
    ReportAssertionSection,
    StructuredReportAssertion,
)
from claim_polygraph_ng.domain.enums import EvidenceStance, VerdictLabel
from claim_polygraph_ng.domain.evidence_integrity import assess_evidence_packet
from claim_polygraph_ng.domain.models import Evidence, Verdict

_NON_WORD = re.compile(r"[^\w]+", re.UNICODE)
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_MATERIAL_CLAUSE_BOUNDARY = re.compile(
    r"(?:;|,\s+|\s+)\b(?:but|although|however|while|whereas)\b\s*",
    re.IGNORECASE,
)


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
        _audit_one(assertion, approved=approved, records=records) for assertion in assertions
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


def assure_full_report(
    *,
    claim_id: UUID,
    verdict: Verdict,
    evidence: tuple[Evidence, ...],
    approved_evidence_ids: tuple[UUID, ...],
    maximum_revision_attempts: int = 2,
    claim_text: str = "",
) -> FullReportCitationAssurance:
    """Inventory, audit, revise and gate every material narrative sentence."""
    if verdict.claim_id != claim_id:
        raise ValueError("verdict must match the assured report claim")
    if maximum_revision_attempts < 0 or maximum_revision_attempts > 2:
        raise ValueError("full-report revision attempts must be between zero and two")
    requested_approved = set(approved_evidence_ids)
    supplied = {item.evidence_id: item for item in evidence}
    if not requested_approved <= set(supplied):
        raise ValueError("every approved evidence ID requires a supplied record")
    integrity = assess_evidence_packet(
        evidence,
        claim_text=claim_text,
        decisive_evidence_ids=tuple(
            dict.fromkeys(
                (*verdict.decisive_evidence_ids, *verdict.contradictory_evidence_ids)
            )
        ),
    )
    eligible_ids = {
        item.evidence_id
        for item in integrity
        if item.citation_eligible and item.evidence_id in requested_approved
    }
    eligible_approved = tuple(
        evidence_id for evidence_id in approved_evidence_ids if evidence_id in eligible_ids
    )
    records = tuple(item for item in evidence if item.evidence_id in eligible_ids)
    original = _material_assertions(claim_id, verdict, records)
    initial = audit_structured_assertions(
        claim_id=claim_id,
        assertions=original,
        evidence=records,
        approved_evidence_ids=eligible_approved,
    )
    current = original
    audit = initial
    revisions: list[CitationRevision] = []
    for attempt in range(1, maximum_revision_attempts + 1):
        failed = {
            item.assertion_id
            for item in audit.findings
            if item.material and item.status is not CitationAssuranceStatus.SUPPORTED
        }
        if not failed:
            break
        revised = tuple(
            _revise_assertion(item, records, attempt, revisions)
            if item.assertion_id in failed
            else item
            for item in current
        )
        if revised == current:
            break
        current = revised
        audit = audit_structured_assertions(
            claim_id=claim_id,
            assertions=current,
            evidence=records,
            approved_evidence_ids=eligible_approved,
        )
    critical_failures = sum(
        item.critical and item.status is not CitationAssuranceStatus.SUPPORTED
        for item in audit.findings
    )
    reasons = []
    if critical_failures:
        reasons.append(f"{critical_failures} critical material assertion(s) remain unsupported.")
    if audit.full_support_rate < 0.95:
        reasons.append(
            "Full-report material sentence support remains below the 95% publication threshold."
        )
    material_count = sum(item.material for item in current)
    return FullReportCitationAssurance(
        claim_id=claim_id,
        original_assertions=original,
        final_assertions=current,
        initial_audit=initial,
        final_audit=audit,
        revisions=tuple(revisions),
        material_sentence_count=material_count,
        audited_material_sentence_count=len([item for item in audit.findings if item.material]),
        critical_failure_count=critical_failures,
        publication_status=(
            PublicationGateStatus.BLOCKED if reasons else PublicationGateStatus.READY
        ),
        blocking_reasons=tuple(reasons),
        maximum_revision_attempts=maximum_revision_attempts,
    )


def reassess_full_report_assurance(
    *,
    historical: FullReportCitationAssurance,
    evidence: tuple[Evidence, ...],
    approved_evidence_ids: tuple[UUID, ...],
) -> FullReportCitationAssurance:
    """Re-audit persisted final report clauses without rewriting audit history."""
    records = {item.evidence_id: item for item in evidence}
    assertions = []
    for historical_assertion in historical.final_assertions:
        if historical_assertion.section is ReportAssertionSection.EVIDENCE_FINDING:
            continue
        candidate_records = tuple(
            records[evidence_id]
            for evidence_id in historical_assertion.cited_evidence_ids
            if evidence_id in records
        )
        for clause_ordinal, clause in enumerate(
            _material_clauses(historical_assertion.sentence)
        ):
            assertions.append(
                StructuredReportAssertion(
                    assertion_id=uuid5(
                        NAMESPACE_URL,
                        (
                            f"{historical.claim_id}/effective/"
                            f"{historical_assertion.section.value}/"
                            f"{historical_assertion.ordinal}/{clause_ordinal}/{clause}"
                        ),
                    ),
                    claim_id=historical.claim_id,
                    sentence=clause,
                    cited_evidence_ids=historical_assertion.cited_evidence_ids,
                    asserted_stance=_assertion_stance(
                        clause,
                        candidate_records,
                        fallback=historical_assertion.asserted_stance,
                    ),
                    required_phrases=_required_phrases(clause, candidate_records),
                    material=historical_assertion.material,
                    critical=historical_assertion.critical,
                    section=historical_assertion.section,
                    ordinal=historical_assertion.ordinal * 100 + clause_ordinal,
                )
            )
    assertions = tuple(assertions)
    if not assertions:
        raise ValueError("effective citation assurance requires report assertions")
    audit = audit_structured_assertions(
        claim_id=historical.claim_id,
        assertions=assertions,
        evidence=evidence,
        approved_evidence_ids=approved_evidence_ids,
    )
    critical_failures = sum(
        item.critical and item.status is not CitationAssuranceStatus.SUPPORTED
        for item in audit.findings
    )
    reasons = []
    if critical_failures:
        reasons.append(f"{critical_failures} critical material assertion(s) remain unsupported.")
    if audit.full_support_rate < 0.95:
        reasons.append(
            "Full-report material clause support remains below the 95% publication threshold."
        )
    return FullReportCitationAssurance(
        claim_id=historical.claim_id,
        original_assertions=assertions,
        final_assertions=assertions,
        initial_audit=audit,
        final_audit=audit,
        revisions=(),
        material_sentence_count=len(assertions),
        audited_material_sentence_count=len(assertions),
        critical_failure_count=critical_failures,
        publication_status=(
            PublicationGateStatus.BLOCKED if reasons else PublicationGateStatus.READY
        ),
        blocking_reasons=tuple(reasons),
        maximum_revision_attempts=0,
    )


def _material_assertions(
    claim_id: UUID,
    verdict: Verdict,
    evidence: tuple[Evidence, ...],
) -> tuple[StructuredReportAssertion, ...]:
    stance = _verdict_stance(verdict.label)
    records = {item.evidence_id: item for item in evidence}
    verdict_citations = tuple(
        evidence_id
        for evidence_id in dict.fromkeys(
            (*verdict.decisive_evidence_ids, *verdict.contradictory_evidence_ids)
        )
        if evidence_id in records
    )
    assertions = []
    for section, text, critical in (
        (
            ReportAssertionSection.VERDICT_SUMMARY,
            verdict.concise_explanation,
            True,
        ),
        (
            ReportAssertionSection.DETAILED_REASONING,
            verdict.detailed_reasoning,
            False,
        ),
        ):
        clauses = tuple(
            clause
            for sentence in _sentences(text)
            for clause in _material_clauses(sentence)
        )
        for ordinal, sentence in enumerate(clauses):
            candidate_records = tuple(records[item] for item in verdict_citations)
            required_phrases = _required_phrases(sentence, candidate_records)
            cited_evidence_ids = tuple(
                item.evidence_id
                for item in candidate_records
                if any(
                    _normalize(phrase) in _normalize(item.passage)
                    for phrase in required_phrases
                )
            )
            assertions.append(
                StructuredReportAssertion(
                    assertion_id=uuid5(
                        NAMESPACE_URL,
                        f"{claim_id}/{section.value}/{ordinal}/{sentence}",
                    ),
                    claim_id=claim_id,
                    sentence=sentence,
                    cited_evidence_ids=cited_evidence_ids,
                    asserted_stance=_assertion_stance(
                        sentence,
                        candidate_records,
                        fallback=stance,
                    ),
                    required_phrases=required_phrases,
                    critical=critical,
                    section=section,
                    ordinal=ordinal,
                )
            )
    return tuple(assertions)


def _material_clauses(sentence: str) -> tuple[str, ...]:
    """Split contrastive report sentences so one match cannot certify another clause."""
    clauses = tuple(
        item.strip(" ,;:")
        for item in _MATERIAL_CLAUSE_BOUNDARY.split(sentence)
        if len(_normalize(item).split()) >= 3
    )
    if any(_normalize(item).endswith(("because", "although", "while")) for item in clauses):
        return (sentence,)
    return clauses or (sentence,)


def _assertion_stance(
    sentence: str,
    evidence: tuple[Evidence, ...],
    *,
    fallback: EvidenceStance,
) -> EvidenceStance:
    """Infer a bounded clause stance instead of copying the verdict-wide stance."""
    lowered = _normalize(sentence)
    qualification_markers = (
        "although",
        "however",
        "may not",
        "not universally",
        "exception",
        "misleading",
        "condition",
        "qualif",
    )
    if any(marker in lowered for marker in qualification_markers):
        return EvidenceStance.QUALIFIES
    if not evidence:
        return fallback
    sentence_tokens = set(lowered.split())
    ranked = sorted(
        evidence,
        key=lambda item: (
            len(sentence_tokens & set(_normalize(item.passage).split())),
            item.relevance_score,
        ),
        reverse=True,
    )
    return ranked[0].stance if ranked else fallback


def _revise_assertion(assertion, evidence, attempt, revisions):
    candidates = tuple(item for item in evidence if item.stance is assertion.asserted_stance)
    cited_candidates = tuple(
        item for item in candidates if item.evidence_id in assertion.cited_evidence_ids
    )
    selected = cited_candidates or candidates
    if not selected:
        return assertion
    item = selected[0]
    excerpt = _passage_excerpt(item.passage)
    revised_sentence = f"The approved evidence states: {excerpt}"
    revised = assertion.model_copy(
        update={
            "sentence": revised_sentence,
            "cited_evidence_ids": (item.evidence_id,),
            "required_phrases": (excerpt,),
        }
    )
    revisions.append(
        CitationRevision(
            assertion_id=assertion.assertion_id,
            attempt_number=attempt,
            original_sentence=assertion.sentence,
            revised_sentence=revised_sentence,
            cited_evidence_ids=(item.evidence_id,),
            rationale=(
                "Unsupported wording was narrowed to an exact approved passage "
                "without changing the verdict label."
            ),
        )
    )
    return revised


def _required_phrases(sentence: str, evidence: tuple[Evidence, ...]) -> tuple[str, ...]:
    clauses = tuple(
        item.strip()
        for item in _MATERIAL_CLAUSE_BOUNDARY.split(sentence)
        if len(_normalize(item).split()) >= 3
    ) or (sentence,)
    phrases = tuple(_required_phrase(clause, evidence) for clause in clauses)
    return tuple(dict.fromkeys(phrases))


def _required_phrase(sentence: str, evidence: tuple[Evidence, ...]) -> str:
    words = _normalize(sentence).split()
    passages = tuple(_normalize(item.passage) for item in evidence)
    for width in range(min(10, len(words)), 3, -1):
        for start in range(len(words) - width + 1):
            phrase = " ".join(words[start : start + width])
            if any(phrase in passage for passage in passages):
                return phrase
    return " ".join(words[: min(8, len(words))])


def _passage_excerpt(passage: str) -> str:
    normalized = " ".join(passage.split())
    if len(normalized) <= 240:
        return normalized
    return normalized[:240].rsplit(" ", 1)[0]


def _sentences(text: str) -> tuple[str, ...]:
    return tuple(
        item.strip()
        for item in _SENTENCE_BOUNDARY.split(" ".join(text.split()))
        if item.strip()
    )


def _verdict_stance(label: VerdictLabel) -> EvidenceStance:
    if label in {VerdictLabel.SUPPORTED, VerdictLabel.MOSTLY_SUPPORTED}:
        return EvidenceStance.SUPPORTS
    if label in {VerdictLabel.CONTRADICTED, VerdictLabel.UNSUPPORTED}:
        return EvidenceStance.CONTRADICTS
    if label in {
        VerdictLabel.MIXED,
        VerdictLabel.MISLEADING,
        VerdictLabel.OUTDATED,
    }:
        return EvidenceStance.QUALIFIES
    return EvidenceStance.CONTEXT


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
        evidence_id for evidence_id in assertion.cited_evidence_ids if evidence_id not in records
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
                "Every required phrase occurs in an exact cited passage with matching stance."
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
