"""Deterministic, provenance-preserving claim candidate extraction."""

import hashlib
import re
from collections.abc import Awaitable, Callable

from claim_polygraph_ng.domain.input import (
    ArticleTextInput,
    ClaimExtractionPacket,
    ExtractedClaimCandidate,
    InvestigationInput,
    InvestigationInputKind,
    ManualClaimInput,
    PublicUrlInput,
)
from claim_polygraph_ng.retrieval import FetchedDocument, extract_document_text

_SENTENCE = re.compile(r"[^.!?\n]+(?:[.!?]+(?=\s|$)|(?=\n|$))", re.MULTILINE)
_NUMBER = re.compile(r"\b\d+(?:[.,]\d+)?(?:%|\b)")
_DATE = re.compile(
    r"\b(?:19|20)\d{2}\b|\b(?:january|february|march|april|may|june|july|"
    r"august|september|october|november|december)\b",
    re.IGNORECASE,
)
_FACTUAL_VERB = re.compile(
    r"\b(?:is|are|was|were|has|have|had|will|increased|decreased|"
    r"caused|reported|announced|founded|launched|entered|ended)\b",
    re.IGNORECASE,
)


class ClaimExtractionService:
    """Extract ranked candidates without judging truth or starting research."""

    def __init__(
        self,
        fetch: Callable[[str], Awaitable[FetchedDocument]] | None = None,
        *,
        maximum_candidates: int = 20,
    ) -> None:
        if maximum_candidates < 1 or maximum_candidates > 100:
            raise ValueError("maximum_candidates must be between 1 and 100")
        self._fetch = fetch
        self._maximum_candidates = maximum_candidates

    async def extract(self, supplied: InvestigationInput) -> ClaimExtractionPacket:
        if isinstance(supplied, ManualClaimInput):
            text = supplied.claim.strip()
            candidates = (_manual_candidate(text),)
            return _packet(
                kind=InvestigationInputKind.MANUAL_CLAIM,
                text=text,
                candidates=candidates,
            )
        if isinstance(supplied, ArticleTextInput):
            text = supplied.text
            return _packet(
                kind=InvestigationInputKind.ARTICLE_TEXT,
                text=text,
                title=supplied.title,
                candidates=self._extract_candidates(text),
            )
        if not isinstance(supplied, PublicUrlInput):
            raise TypeError("unsupported investigation input")
        if self._fetch is None:
            raise RuntimeError("public URL extraction is not configured")
        document = await self._fetch(str(supplied.url))
        text = extract_document_text(document)
        if len(text) < 20:
            raise ValueError("public URL did not contain enough readable text")
        if len(text) > 500_000:
            raise ValueError("extracted public URL text exceeds 500,000 characters")
        return _packet(
            kind=InvestigationInputKind.PUBLIC_URL,
            text=text,
            source_url=document.requested_url,
            canonical_url=document.final_url,
            retrieved_at=document.retrieved_at,
            candidates=self._extract_candidates(text),
        )

    def _extract_candidates(self, text: str) -> tuple[ExtractedClaimCandidate, ...]:
        ranked: list[tuple[float, int, int, str, tuple[str, ...]]] = []
        seen: set[str] = set()
        for match in _SENTENCE.finditer(text):
            raw = match.group()
            left_trim = len(raw) - len(raw.lstrip())
            sentence = raw.strip()
            start = match.start() + left_trim
            end = start + len(sentence)
            normalized = " ".join(sentence.casefold().split())
            if len(sentence) < 20 or len(sentence) > 2_000 or normalized in seen:
                continue
            seen.add(normalized)
            score, reasons = _score(sentence)
            if score < 0.35:
                continue
            ranked.append((score, start, end, sentence, reasons))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        selected = ranked[: self._maximum_candidates]
        return tuple(
            ExtractedClaimCandidate(
                text=sentence,
                start_char=start,
                end_char=end,
                context_before=text[max(0, start - 240) : start],
                context_after=text[end : min(len(text), end + 240)],
                checkworthiness=score,
                ranking_reasons=reasons,
                rank=rank,
            )
            for rank, (score, start, end, sentence, reasons) in enumerate(selected, 1)
        )


def _manual_candidate(text: str) -> ExtractedClaimCandidate:
    score, reasons = _score(text)
    return ExtractedClaimCandidate(
        text=text,
        start_char=0,
        end_char=len(text),
        checkworthiness=max(score, 0.5),
        ranking_reasons=reasons or ("manual_submission",),
        rank=1,
    )


def _score(sentence: str) -> tuple[float, tuple[str, ...]]:
    score = 0.25
    reasons = []
    if _FACTUAL_VERB.search(sentence):
        score += 0.3
        reasons.append("factual_predicate")
    if _NUMBER.search(sentence):
        score += 0.2
        reasons.append("quantity")
    if _DATE.search(sentence):
        score += 0.15
        reasons.append("date")
    if any(character.isupper() for character in sentence[1:]):
        score += 0.1
        reasons.append("named_entity_signal")
    if sentence.endswith("?"):
        score -= 0.2
    return min(max(round(score, 3), 0), 1), tuple(reasons)


def _packet(
    *,
    kind: InvestigationInputKind,
    text: str,
    candidates: tuple[ExtractedClaimCandidate, ...],
    title: str | None = None,
    source_url=None,
    canonical_url=None,
    retrieved_at=None,
) -> ClaimExtractionPacket:
    return ClaimExtractionPacket(
        input_kind=kind,
        source_url=source_url,
        canonical_url=canonical_url,
        title=title,
        content_hash=hashlib.sha256(text.encode()).hexdigest(),
        content_length=len(text),
        retrieved_at=retrieved_at,
        candidates=candidates,
    )
