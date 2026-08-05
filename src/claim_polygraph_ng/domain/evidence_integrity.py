"""Deterministic passage-hygiene and bounded-quote assessment."""

import re
from enum import StrEnum
from uuid import UUID

from pydantic import Field

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.enums import EvidentiaryUse
from claim_polygraph_ng.domain.evidence_disposition import (
    EvidenceDispositionKind,
    EvidenceDispositionRecord,
    apply_evidence_dispositions,
    latest_evidence_dispositions,
)
from claim_polygraph_ng.domain.models import Evidence


class PassageHygieneStatus(StrEnum):
    CLEAN = "clean"
    CAUTION = "caution"
    CONTAMINATED = "contaminated"


class EvidenceExcerptStatus(StrEnum):
    SOURCE_SPAN_VERIFIED = "source_span_verified"
    BOUNDED_DIAGNOSTIC = "bounded_diagnostic"


class EvidenceIntegrityAssessment(DomainModel):
    """Explain why a retained passage is safe, questionable, or blocking."""

    evidence_id: UUID
    status: PassageHygieneStatus
    reason_codes: tuple[str, ...] = ()
    matched_fragments: tuple[str, ...] = ()
    exact_quote: str = Field(min_length=1, max_length=1_200)
    excerpt_status: EvidenceExcerptStatus = EvidenceExcerptStatus.BOUNDED_DIAGNOSTIC
    excerpt_start_char: int | None = Field(default=None, ge=0)
    excerpt_end_char: int | None = Field(default=None, gt=0)
    context_before: str | None = Field(default=None, max_length=500)
    context_after: str | None = Field(default=None, max_length=500)
    decisive: bool = False
    approved_use: EvidentiaryUse = EvidentiaryUse.UNSPECIFIED
    requires_human_review: bool = False
    publication_blocking: bool = False
    argument_eligible: bool = True
    citation_eligible: bool = True
    decisive_use_eligible: bool = True
    disposition_id: UUID | None = None
    disposition_kind: EvidenceDispositionKind | None = None
    disposition_reason: str | None = Field(default=None, max_length=2_000)
    remediation_actions: tuple[str, ...] = ()


_BOILERPLATE_PHRASES = (
    "skip to main content",
    "user account menu",
    "log in",
    "sign in",
    "subscribe",
    "product directory",
    "download media pack",
    "contact us",
    "privacy policy",
    "cookie policy",
    "all rights reserved",
    "equal opportunity",
    "non discrimination",
    "accessibility",
    "printer-friendly",
    "follow us",
    "share this",
    "related reading",
)
_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
_SENTENCE = re.compile(r"\S(?:.*?\S)?(?=(?:[.!?](?:\s+|$))|\n{2,}|$)", re.DOTALL)
_STOP = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
        "is", "it", "of", "on", "or", "that", "the", "to", "was", "were", "with",
    }
)


def assess_evidence_integrity(
    evidence: Evidence,
    *,
    claim_text: str,
    decisive: bool = False,
) -> EvidenceIntegrityAssessment:
    """Assess stored text without treating relevance as truth or quality."""
    normalized = re.sub(r"\s+", " ", evidence.passage).strip()
    lowered = normalized.casefold()
    matches = tuple(phrase for phrase in _BOILERPLATE_PHRASES if phrase in lowered)
    reason_codes: list[str] = []
    mojibake = any(marker in evidence.passage for marker in ("Ã", "Â", "â€"))
    if matches:
        reason_codes.append("page_chrome_detected")
    if len(matches) >= 3:
        reason_codes.append("substantial_boilerplate_detected")
    if mojibake:
        reason_codes.append("encoding_corruption_detected")
    if len(normalized) > 4_000:
        reason_codes.append("unbounded_capture_detected")

    contaminated = mojibake or len(matches) >= 3
    caution = bool(reason_codes)
    status = (
        PassageHygieneStatus.CONTAMINATED
        if contaminated
        else PassageHygieneStatus.CAUTION
        if caution
        else PassageHygieneStatus.CLEAN
    )
    quote, before, after = _bounded_quote(evidence.passage, claim_text)
    relative_start = evidence.passage.find(quote)
    span_verified = (
        relative_start >= 0
        and evidence.passage_start_char is not None
        and evidence.passage_end_char is not None
    )
    excerpt_start = (
        evidence.passage_start_char + relative_start if span_verified else None
    )
    excerpt_end = excerpt_start + len(quote) if excerpt_start is not None else None
    excluded_use = evidence.evidentiary_use in {
        EvidentiaryUse.EXCLUDED,
        EvidentiaryUse.DISCOVERY_LEAD,
    }
    if excluded_use:
        reason_codes.append("evidentiary_use_not_argument_eligible")
    argument_eligible = not contaminated and not excluded_use
    unspecified_decisive = decisive and evidence.evidentiary_use is EvidentiaryUse.UNSPECIFIED
    if unspecified_decisive:
        reason_codes.append("decisive_use_unspecified")
    decisive_use_eligible = argument_eligible and not unspecified_decisive
    citation_eligible = (
        status is PassageHygieneStatus.CLEAN
        and not excluded_use
        and not unspecified_decisive
    )
    blocking = decisive and not decisive_use_eligible
    actions: list[str] = []
    if contaminated:
        actions.extend(("reextract_source", "request_replacement_evidence"))
    if unspecified_decisive:
        actions.append("record_approved_use")
    if excluded_use:
        actions.append("request_replacement_evidence")
    if blocking:
        actions.append("exclude_from_decisive_packet")
    return EvidenceIntegrityAssessment(
        evidence_id=evidence.evidence_id,
        status=status,
        reason_codes=tuple(reason_codes),
        matched_fragments=matches[:8],
        exact_quote=quote,
        excerpt_status=(
            EvidenceExcerptStatus.SOURCE_SPAN_VERIFIED
            if span_verified
            else EvidenceExcerptStatus.BOUNDED_DIAGNOSTIC
        ),
        excerpt_start_char=excerpt_start,
        excerpt_end_char=excerpt_end,
        context_before=before,
        context_after=after,
        decisive=decisive,
        approved_use=evidence.evidentiary_use,
        requires_human_review=status is not PassageHygieneStatus.CLEAN or unspecified_decisive,
        publication_blocking=blocking,
        argument_eligible=argument_eligible,
        citation_eligible=citation_eligible,
        decisive_use_eligible=decisive_use_eligible,
        remediation_actions=tuple(dict.fromkeys(actions)),
    )


def assess_evidence_packet(
    evidence: tuple[Evidence, ...],
    *,
    claim_text: str,
    decisive_evidence_ids: tuple[UUID, ...] = (),
    dispositions: tuple[EvidenceDispositionRecord, ...] = (),
) -> tuple[EvidenceIntegrityAssessment, ...]:
    decisive = set(decisive_evidence_ids)
    latest = latest_evidence_dispositions(dispositions)
    effective = apply_evidence_dispositions(evidence, dispositions)
    assessments = []
    for item in effective:
        assessment = assess_evidence_integrity(
            item,
            claim_text=claim_text,
            decisive=item.evidence_id in decisive,
        )
        disposition = latest.get(item.evidence_id)
        if disposition is not None:
            assessment = assessment.model_copy(
                update={
                    "disposition_id": disposition.disposition_id,
                    "disposition_kind": disposition.kind,
                    "disposition_reason": disposition.reason,
                    "reason_codes": tuple(
                        dict.fromkeys(
                            (
                                *assessment.reason_codes,
                                f"persisted_disposition_{disposition.kind.value}",
                            )
                        )
                    ),
                }
            )
        assessments.append(assessment)
    return tuple(assessments)


def _bounded_quote(passage: str, claim_text: str) -> tuple[str, str | None, str | None]:
    candidate_text = passage
    for phrase in _BOILERPLATE_PHRASES:
        candidate_text = re.sub(
            re.escape(phrase),
            "\n\n",
            candidate_text,
            flags=re.IGNORECASE,
        )
    candidates = [
        re.sub(r"\s+", " ", match.group(0)).strip()
        for match in _SENTENCE.finditer(candidate_text)
    ]
    candidates = [item for item in candidates if item]
    if not candidates:
        value = re.sub(r"\s+", " ", passage).strip()[:1_200]
        return value, None, None
    claim_terms = _terms(claim_text)
    ranked = sorted(
        enumerate(candidates),
        key=lambda item: (
            -len(_terms(item[1]) & claim_terms),
            sum(phrase in item[1].casefold() for phrase in _BOILERPLATE_PHRASES),
            abs(len(item[1]) - 320),
            item[0],
        ),
    )
    index = ranked[0][0]
    quote = re.sub(r"^[\s.!?]+", "", candidates[index][:1_200]).strip()
    if "\ufffd" in quote or any(marker in quote for marker in ("Ã", "Â", "â€")):
        quote = _clean_diagnostic_text(quote)
    before = candidates[index - 1][-500:] if index else None
    after = candidates[index + 1][:500] if index + 1 < len(candidates) else None
    return quote, before, after


def _clean_diagnostic_text(value: str) -> str:
    """Make a diagnostic excerpt readable without claiming source-span fidelity."""
    cleaned = value.replace("\ufffd", "").replace("Â", "")
    cleaned = re.sub(r"â[€™œ\x9d]", "", cleaned)
    cleaned = re.sub(r"^[\s?·|:;-]+", "", cleaned)
    return cleaned.strip() or "Stored passage contains unreadable encoding artifacts."


def _terms(value: str) -> set[str]:
    return {
        token
        for token in (match.group(0).casefold() for match in _TOKEN.finditer(value))
        if len(token) > 2 and token not in _STOP
    }
