"""Deterministic document chunking, deduplication, and BM25-style ranking."""

import hashlib
import math
import re
from collections import Counter
from uuid import UUID

from claim_polygraph_ng.domain import ResearchPath
from claim_polygraph_ng.retrieval.models import (
    ChunkingPolicy,
    DocumentChunk,
    RankedPassage,
)

_TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)
_PARAGRAPH_PATTERN = re.compile(r"\S(?:.*?\S)?(?=\n{2,}|\Z)", re.DOTALL)
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "to",
        "was",
        "were",
        "with",
    }
)


def segment_document(
    *,
    source_id: UUID,
    research_path: ResearchPath,
    text: str,
    policy: ChunkingPolicy | None = None,
) -> tuple[DocumentChunk, ...]:
    """Split normalized document text into exact, bounded source spans."""
    active_policy = policy or ChunkingPolicy()
    spans: list[tuple[int, int]] = []

    for paragraph in _PARAGRAPH_PATTERN.finditer(text):
        spans.extend(
            _split_span(
                text,
                paragraph.start(),
                paragraph.end(),
                active_policy.maximum_characters,
                active_policy.minimum_characters,
            )
        )

    packed = _pack_spans(text, spans, active_policy.maximum_characters)
    chunks = []
    for ordinal, (start, end) in enumerate(packed):
        chunk_text = text[start:end]
        chunks.append(
            DocumentChunk(
                source_id=source_id,
                research_path=research_path,
                ordinal=ordinal,
                text=chunk_text,
                start_char=start,
                end_char=end,
                content_hash=hashlib.sha256(
                    _normalized_duplicate_key(chunk_text).encode("utf-8")
                ).hexdigest(),
            )
        )
    return tuple(chunks)


def deduplicate_chunks(
    chunks: tuple[DocumentChunk, ...],
) -> tuple[DocumentChunk, ...]:
    """Remove exact normalized duplicate passages while preserving order."""
    seen: set[str] = set()
    unique: list[DocumentChunk] = []
    for chunk in chunks:
        if chunk.content_hash in seen:
            continue
        seen.add(chunk.content_hash)
        unique.append(chunk)
    return tuple(unique)


def rank_passages(
    query: str,
    chunks: tuple[DocumentChunk, ...],
    *,
    top_k: int = 5,
    k1: float = 1.5,
    length_normalization: float = 0.75,
) -> tuple[RankedPassage, ...]:
    """Rank chunks with a small deterministic BM25 implementation."""
    if top_k < 1:
        raise ValueError("top_k must be at least one")
    if not chunks:
        return ()

    query_terms = tuple(dict.fromkeys(_tokenize(query)))
    document_terms = [_tokenize(chunk.text) for chunk in chunks]
    average_length = sum(len(terms) for terms in document_terms) / len(chunks)
    average_length = average_length or 1.0

    document_frequency = {
        term: sum(term in terms for terms in document_terms) for term in query_terms
    }
    scored: list[tuple[float, tuple[str, ...], DocumentChunk]] = []

    for chunk, terms in zip(chunks, document_terms, strict=True):
        frequencies = Counter(terms)
        matched = tuple(term for term in query_terms if frequencies[term])
        score = 0.0
        for term in matched:
            frequency = frequencies[term]
            frequency_in_documents = document_frequency[term]
            inverse_document_frequency = math.log(
                1 + (len(chunks) - frequency_in_documents + 0.5) / (frequency_in_documents + 0.5)
            )
            denominator = frequency + k1 * (
                1 - length_normalization + length_normalization * len(terms) / average_length
            )
            score += inverse_document_frequency * (frequency * (k1 + 1) / denominator)
        scored.append((score, matched, chunk))

    scored.sort(
        key=lambda item: (
            -item[0],
            item[2].ordinal,
            str(item[2].source_id),
        )
    )
    return tuple(
        RankedPassage(
            chunk=chunk,
            rank=rank,
            score=round(score, 6),
            matched_terms=matched,
        )
        for rank, (score, matched, chunk) in enumerate(scored[:top_k], start=1)
    )


def _tokenize(value: str) -> list[str]:
    return [
        token
        for token in (match.group(0).casefold() for match in _TOKEN_PATTERN.finditer(value))
        if token not in _STOP_WORDS and len(token) > 1
    ]


def _split_span(
    text: str,
    start: int,
    end: int,
    maximum_characters: int,
    minimum_characters: int,
) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cursor = start
    while end - cursor > maximum_characters:
        target = cursor + maximum_characters
        split = _best_boundary(text, cursor, target, minimum_characters)
        spans.append(_trim_span(text, cursor, split))
        cursor = split
        while cursor < end and text[cursor].isspace():
            cursor += 1
    if cursor < end:
        spans.append(_trim_span(text, cursor, end))
    return [span for span in spans if span[0] < span[1]]


def _best_boundary(
    text: str,
    start: int,
    target: int,
    minimum_characters: int,
) -> int:
    minimum = min(target, start + minimum_characters)
    candidates = [
        text.rfind(marker, minimum, target) for marker in (". ", "! ", "? ", "; ", ", ", " ")
    ]
    boundary = max(candidates)
    if boundary < minimum:
        return target
    return boundary + 1


def _trim_span(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _pack_spans(
    text: str,
    spans: list[tuple[int, int]],
    maximum_characters: int,
) -> list[tuple[int, int]]:
    if not spans:
        return []

    packed: list[tuple[int, int]] = []
    current_start, current_end = spans[0]
    for start, end in spans[1:]:
        if end - current_start <= maximum_characters:
            current_end = end
            continue
        packed.append(_trim_span(text, current_start, current_end))
        current_start, current_end = start, end
    packed.append(_trim_span(text, current_start, current_end))
    return packed


def _normalized_duplicate_key(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()
