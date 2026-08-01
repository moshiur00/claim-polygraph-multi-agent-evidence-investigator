"""Bounded construction of evidence-grounded temporal comparisons."""

import re
from datetime import date
from uuid import NAMESPACE_URL, UUID, uuid5

from claim_polygraph_ng.analysis.temporal_verification import (
    TemporalEvidenceFact,
    TemporalVerificationRequest,
    verify_temporal_assertion,
)
from claim_polygraph_ng.domain import (
    AssertionConstructionState,
    AtomicClaim,
    DatePrecision,
    Evidence,
    TemporalAssertionConstruction,
    TemporalAssertionVerification,
    TemporalInstant,
    TemporalInterval,
    TemporalRelation,
    VerificationIssueFinding,
    VerificationIssueSeverity,
    VerificationReadinessImpact,
)

TEMPORAL_CONSTRUCTOR_VERSION = "temporal-comparison-constructor-v1"

_CLAIM_PATTERN = re.compile(
    r"^\s*(?P<left>.+?)\s+(?:occurred|happened|started|ended|took place)\s+"
    r"(?P<relation>before|after)\s+(?P<right>.+?)[.!?]?\s*$",
    re.IGNORECASE,
)
_ISO_DATE_PATTERN = re.compile(
    r"(?<!\d)(?P<year>\d{4})-(?P<month>0[1-9]|1[0-2])-"
    r"(?P<day>0[1-9]|[12]\d|3[01])(?!\d)"
)
_YEAR_PATTERN = re.compile(r"(?<!\d)(?P<year>1\d{3}|20\d{2}|21\d{2})(?!\d)")
_STOPWORDS = {"a", "an", "event", "the"}


def is_temporal_comparison(value: str) -> bool:
    return _CLAIM_PATTERN.match(value) is not None


def construct_temporal_comparison(
    *,
    claim: AtomicClaim,
    evidence: tuple[Evidence, ...],
) -> tuple[
    TemporalAssertionConstruction | None,
    TemporalAssertionVerification | None,
    VerificationIssueFinding | None,
]:
    match = _CLAIM_PATTERN.match(claim.text)
    if match is None:
        return None, None, None
    left = match.group("left").strip()
    right = match.group("right").strip()
    relation = TemporalRelation(match.group("relation").casefold())
    construction_id = uuid5(
        NAMESPACE_URL,
        f"{claim.claim_id}/temporal-comparison/{left}/{relation.value}/{right}",
    )
    bound = _bind_dates(left=left, right=right, evidence=evidence)
    if bound is None:
        message = (
            "The temporal comparison was detected, but dates for both subjects "
            "were not found together in one approved evidence sentence."
        )
        return (
            TemporalAssertionConstruction(
                construction_id=construction_id,
                claim_id=claim.claim_id,
                claim_text_span=claim.text,
                left_subject=left,
                right_subject=right,
                relation=relation,
                state=AssertionConstructionState.FAILED,
                failure_code="temporal_comparison_dates_missing",
                explanation=message,
            ),
            None,
            VerificationIssueFinding(
                code="temporal_comparison_dates_missing",
                severity=VerificationIssueSeverity.BLOCKING,
                message=message,
                recommended_action=(
                    "Retrieve an approved passage that dates both named subjects, "
                    "or record a reviewed typed temporal assertion."
                ),
                readiness_impact=VerificationReadinessImpact.HUMAN_REVIEW,
            ),
        )

    evidence_id, left_date, right_date = bound
    assertion_id = uuid5(NAMESPACE_URL, f"{construction_id}/assertion")
    assertion = verify_temporal_assertion(
        TemporalVerificationRequest(
            claim_id=claim.claim_id,
            claim_text_span=claim.text,
            relation=relation,
            reference_date=right_date,
            facts=(
                TemporalEvidenceFact(
                    evidence_id=evidence_id,
                    effective_interval=TemporalInterval(
                        start=left_date,
                        end=left_date,
                    ),
                ),
            ),
        )
    ).model_copy(update={"assertion_id": assertion_id})
    return (
        TemporalAssertionConstruction(
            construction_id=construction_id,
            claim_id=claim.claim_id,
            claim_text_span=claim.text,
            left_subject=left,
            right_subject=right,
            relation=relation,
            state=AssertionConstructionState.CONSTRUCTED,
            assertion_id=assertion_id,
            evidence_ids=(evidence_id,),
            explanation=(
                "Both subjects were bound to dated facts within one approved "
                "evidence sentence."
            ),
        ),
        assertion,
        None,
    )


def _bind_dates(
    *,
    left: str,
    right: str,
    evidence: tuple[Evidence, ...],
) -> tuple[UUID, TemporalInstant, TemporalInstant] | None:
    left_terms = _subject_terms(left)
    right_terms = _subject_terms(right)
    for item in evidence:
        for sentence in _sentences(item.passage):
            normalized = sentence.casefold()
            if not _mentions(normalized, left_terms) or not _mentions(
                normalized, right_terms
            ):
                continue
            dates = _dates(sentence)
            if len(dates) >= 2:
                return item.evidence_id, dates[0], dates[1]
    return None


def _dates(value: str) -> tuple[TemporalInstant, ...]:
    found: list[tuple[int, TemporalInstant]] = []
    occupied: list[tuple[int, int]] = []
    for match in _ISO_DATE_PATTERN.finditer(value):
        found.append(
            (
                match.start(),
                TemporalInstant(
                    value=date(
                        int(match.group("year")),
                        int(match.group("month")),
                        int(match.group("day")),
                    ),
                    precision=DatePrecision.DAY,
                ),
            )
        )
        occupied.append(match.span())
    for match in _YEAR_PATTERN.finditer(value):
        if any(start <= match.start() < end for start, end in occupied):
            continue
        found.append(
            (
                match.start(),
                TemporalInstant(
                    value=date(int(match.group("year")), 1, 1),
                    precision=DatePrecision.YEAR,
                ),
            )
        )
    return tuple(item for _, item in sorted(found, key=lambda pair: pair[0]))


def _subject_terms(value: str) -> tuple[str, ...]:
    terms = re.findall(r"[a-z0-9]+", value.casefold())
    meaningful = tuple(term for term in terms if term not in _STOPWORDS)
    return meaningful or tuple(terms)


def _mentions(sentence: str, terms: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(term)}\b", sentence) for term in terms)


def _sentences(value: str) -> tuple[str, ...]:
    normalized = re.sub(r"\s+", " ", value)
    return tuple(
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", normalized)
        if sentence.strip()
    )
