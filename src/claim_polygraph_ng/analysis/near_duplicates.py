"""Precision-first lexical signals for derivatives and syndication."""

import re
from datetime import date
from enum import StrEnum

from pydantic import Field

from claim_polygraph_ng.analysis.exact_duplicates import normalize_exact_content
from claim_polygraph_ng.domain.base import DomainModel

NEAR_DUPLICATE_VERSION = "lexical-provenance-v1"
_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
_ATTRIBUTION_MARKERS = (
    "according to",
    "announcement",
    "as required",
    "reports that",
    "standard",
)
_INDEPENDENCE_MARKERS = ("independent", "independently", "separate", "separately")


class NearDuplicateLabel(StrEnum):
    """Conservative pair classification."""

    EXACT = "exact"
    LIKELY_DERIVATIVE = "likely_derivative"
    POSSIBLE_RELATED = "possible_related"
    DISTINCT = "distinct"


class NearDuplicateSignals(DomainModel):
    """Auditable lexical and contextual pair features."""

    token_jaccard: float = Field(ge=0, le=1)
    token_containment: float = Field(ge=0, le=1)
    shared_trigram_count: int = Field(ge=0)
    shared_numbers: tuple[str, ...] = ()
    shared_attribution_markers: tuple[str, ...] = ()
    independence_markers: tuple[str, ...] = ()
    publication_order: str


class NearDuplicateAssessment(DomainModel):
    """Pair decision that cannot silently alter evidence independence."""

    left_record_id: str
    right_record_id: str
    version: str = NEAR_DUPLICATE_VERSION
    label: NearDuplicateLabel
    confidence: float = Field(ge=0, le=1)
    signals: NearDuplicateSignals
    reasons: tuple[str, ...]
    automatic_independence_use_allowed: bool = False


def assess_near_duplicate(
    *,
    left_record_id: str,
    left_text: str,
    right_record_id: str,
    right_text: str,
    left_published: date | None = None,
    right_published: date | None = None,
) -> NearDuplicateAssessment:
    """Classify a pair using deterministic, explainable signals."""
    left_normalized = normalize_exact_content(left_text)
    right_normalized = normalize_exact_content(right_text)
    left_tokens = _tokens(left_normalized)
    right_tokens = _tokens(right_normalized)
    union = left_tokens | right_tokens
    intersection = left_tokens & right_tokens
    jaccard = len(intersection) / len(union) if union else 1
    minimum = min(len(left_tokens), len(right_tokens))
    containment = len(intersection) / minimum if minimum else 1
    shared_numbers = tuple(sorted(token for token in intersection if token.isdigit()))
    attribution = tuple(
        marker
        for marker in _ATTRIBUTION_MARKERS
        if marker in left_normalized or marker in right_normalized
    )
    independence = tuple(
        marker
        for marker in _INDEPENDENCE_MARKERS
        if marker in left_normalized or marker in right_normalized
    )
    trigrams = len(_shingles(left_normalized, 3) & _shingles(right_normalized, 3))
    signals = NearDuplicateSignals(
        token_jaccard=round(jaccard, 6),
        token_containment=round(containment, 6),
        shared_trigram_count=trigrams,
        shared_numbers=shared_numbers,
        shared_attribution_markers=attribution,
        independence_markers=independence,
        publication_order=_publication_order(left_published, right_published),
    )
    if left_normalized == right_normalized:
        label = NearDuplicateLabel.EXACT
        confidence = 1.0
        reasons = ("Normalized content is identical.",)
    elif independence:
        label = NearDuplicateLabel.DISTINCT
        confidence = 0.9
        reasons = ("The text explicitly describes independent or separate work.",)
    elif (
        jaccard >= 0.18
        and attribution
        and (shared_numbers or "standard" in attribution or "as required" in attribution)
    ):
        label = NearDuplicateLabel.LIKELY_DERIVATIVE
        confidence = min(0.99, 0.7 + jaccard / 2 + min(trigrams, 2) * 0.03)
        reasons = (
            "Material lexical overlap is combined with attribution and a shared "
            "number or controlling reference.",
        )
    elif jaccard >= 0.3 or containment >= 0.5 or trigrams >= 2:
        label = NearDuplicateLabel.POSSIBLE_RELATED
        confidence = min(0.8, max(jaccard, containment) + 0.15)
        reasons = ("Lexical overlap suggests a relationship but does not establish derivation.",)
    else:
        label = NearDuplicateLabel.DISTINCT
        confidence = min(0.9, 1 - jaccard)
        reasons = ("Available lexical signals do not establish a derivative relationship.",)
    return NearDuplicateAssessment(
        left_record_id=left_record_id,
        right_record_id=right_record_id,
        label=label,
        confidence=round(confidence, 6),
        signals=signals,
        reasons=reasons,
    )


def _tokens(value: str) -> set[str]:
    return set(_TOKEN.findall(value))


def _shingles(value: str, size: int) -> set[tuple[str, ...]]:
    tokens = _TOKEN.findall(value)
    return {tuple(tokens[index : index + size]) for index in range(len(tokens) - size + 1)}


def _publication_order(left: date | None, right: date | None) -> str:
    if left is None or right is None:
        return "unknown"
    if left < right:
        return "left_before_right"
    if right < left:
        return "right_before_left"
    return "same_date"
