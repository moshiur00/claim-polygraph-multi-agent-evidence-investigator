"""Evaluate page access, extraction, and passage ranking for retrieved candidates."""

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from claim_polygraph_ng.domain import ResearchPath
from claim_polygraph_ng.evaluation.models import (
    BenchmarkCase,
    BenchmarkDataset,
    PageFetchCaseResult,
    PageFetchEvaluationResult,
    PageFetchEvaluationSummary,
    PageReferenceMatch,
    RetrievalEvaluationSummary,
)
from claim_polygraph_ng.retrieval import (
    ContentFetcher,
    extract_document_text,
    rank_passages,
    segment_document,
)

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_STOP_WORDS = {
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


async def run_page_fetch_evaluation(
    dataset: BenchmarkDataset,
    retrieval: RetrievalEvaluationSummary,
    fetcher: ContentFetcher,
    *,
    retrieval_input: str,
    candidate_top_n: int = 3,
    passage_top_k: int = 3,
    passage_lexical_threshold: float = 0.5,
) -> PageFetchEvaluationSummary:
    """Fetch and rank a bounded set of candidates from a retrieval result."""
    if not 1 <= candidate_top_n <= 10:
        raise ValueError("candidate top-n must be between 1 and 10")
    if not 1 <= passage_top_k <= 20:
        raise ValueError("passage top-k must be between 1 and 20")
    if not 0.0 <= passage_lexical_threshold <= 1.0:
        raise ValueError("passage lexical threshold must be between zero and one")
    if (
        retrieval.dataset_id != dataset.dataset_id
        or retrieval.dataset_version != dataset.version
    ):
        raise ValueError("retrieval evaluation does not match the benchmark dataset")

    cases_by_id = {case.case_id: case for case in dataset.cases}
    started_at = datetime.now(UTC)
    run_started = perf_counter()
    seen_content: dict[str, str] = {}
    case_results: list[PageFetchCaseResult] = []

    for retrieval_case in retrieval.results:
        case = cases_by_id.get(retrieval_case.case_id)
        if case is None:
            raise ValueError(
                f"retrieval case is absent from benchmark: {retrieval_case.case_id}"
            )
        pages: list[PageFetchEvaluationResult] = []
        for candidate in retrieval_case.candidates[:candidate_top_n]:
            page = await _evaluate_page(
                case,
                candidate.rank,
                str(candidate.url),
                fetcher,
                passage_top_k,
                passage_lexical_threshold,
                seen_content,
            )
            pages.append(page)

        matched_ids = {
            reference_id for page in pages for reference_id in page.matched_reference_ids
        }
        matching_ranks = tuple(
            page.candidate_rank for page in pages if page.matched_reference_ids
        )
        case_results.append(
            PageFetchCaseResult(
                case_id=case.case_id,
                attempted_count=len(pages),
                fetched_count=sum(page.fetched for page in pages),
                extracted_count=sum(page.extracted for page in pages),
                duplicate_count=sum(page.duplicate_of_url is not None for page in pages),
                reference_count=len(case.candidate_evidence),
                matched_reference_count=len(matched_ids),
                first_matching_candidate_rank=min(matching_ranks, default=None),
                pages=tuple(pages),
            )
        )

    attempted = sum(result.attempted_count for result in case_results)
    fetched = sum(result.fetched_count for result in case_results)
    extracted = sum(result.extracted_count for result in case_results)
    duplicates = sum(result.duplicate_count for result in case_results)
    reference_count = sum(result.reference_count for result in case_results)
    matched_reference_count = sum(
        result.matched_reference_count for result in case_results
    )
    successful_cases = sum(
        result.matched_reference_count > 0 for result in case_results
    )

    return PageFetchEvaluationSummary(
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.version,
        retrieval_input=retrieval_input,
        retrieval_strategy=retrieval.query_strategy,
        fetcher_id=fetcher.provider_id,
        started_at=started_at,
        duration_seconds=round(perf_counter() - run_started, 6),
        case_count=len(case_results),
        candidate_top_n=candidate_top_n,
        passage_top_k=passage_top_k,
        passage_lexical_threshold=passage_lexical_threshold,
        attempted_page_count=attempted,
        fetched_page_count=fetched,
        extracted_page_count=extracted,
        duplicate_page_count=duplicates,
        fetch_success_rate=_rate(fetched, attempted),
        extraction_success_rate=_rate(extracted, attempted),
        duplicate_content_rate=_rate(duplicates, extracted),
        reference_count=reference_count,
        matched_reference_count=matched_reference_count,
        passage_lexical_recall=(
            round(matched_reference_count / reference_count, 6)
            if reference_count
            else None
        ),
        case_passage_success_rate=_rate(successful_cases, len(case_results)),
        results=tuple(case_results),
        limitations=(
            "Passage matches use reference-token coverage over reviewed excerpts and "
            "summaries; they are not semantic entailment judgments.",
            "A fetched page may contain useful evidence that the bounded lexical ranker misses.",
            "HTTP failures combine publisher access policy, network conditions, content type, "
            "and the fetcher's safety limits; they are not search failures.",
            "Only the configured top-N candidates and top-K passages are evaluated.",
        ),
    )


async def _evaluate_page(
    case: BenchmarkCase,
    candidate_rank: int,
    url: str,
    fetcher: ContentFetcher,
    passage_top_k: int,
    passage_lexical_threshold: float,
    seen_content: dict[str, str],
) -> PageFetchEvaluationResult:
    try:
        document = await fetcher.fetch(url)
    except Exception as error:
        return PageFetchEvaluationResult(
            case_id=case.case_id,
            candidate_rank=candidate_rank,
            requested_url=url,
            fetched=False,
            extracted=False,
            best_reference_lexical_score=0.0,
            error_type=type(error).__name__,
            error_message=str(error),
        )

    try:
        readable = extract_document_text(document)
    except Exception as error:
        return PageFetchEvaluationResult(
            case_id=case.case_id,
            candidate_rank=candidate_rank,
            requested_url=document.requested_url,
            final_url=document.final_url,
            fetched=True,
            extracted=False,
            content_type=document.content_type,
            byte_length=document.byte_length,
            best_reference_lexical_score=0.0,
            error_type=type(error).__name__,
            error_message=str(error),
        )
    if not readable:
        return PageFetchEvaluationResult(
            case_id=case.case_id,
            candidate_rank=candidate_rank,
            requested_url=document.requested_url,
            final_url=document.final_url,
            fetched=True,
            extracted=False,
            content_type=document.content_type,
            byte_length=document.byte_length,
            best_reference_lexical_score=0.0,
            error_type="EmptyReadableText",
            error_message="fetched page contained no readable text",
        )

    content_hash = hashlib.sha256(
        re.sub(r"\s+", " ", readable).strip().casefold().encode("utf-8")
    ).hexdigest()
    duplicate_of = seen_content.get(content_hash)
    seen_content.setdefault(content_hash, str(document.final_url))
    chunks = segment_document(
        source_id=uuid4(),
        research_path=ResearchPath.GENERAL,
        text=readable,
    )
    ranked = rank_passages(case.claim, chunks, top_k=passage_top_k)
    reference_matches: list[PageReferenceMatch] = []
    for reference in case.candidate_evidence:
        scored_passages = tuple(
            (
                max(
                    _reference_coverage(
                        _tokens(reference.excerpt),
                        _tokens(passage.chunk.text),
                    ),
                    _reference_coverage(
                        _tokens(reference.evidence_summary),
                        _tokens(passage.chunk.text),
                    ),
                ),
                passage,
            )
            for passage in ranked
        )
        if scored_passages:
            score, best_reference_passage = max(
                scored_passages,
                key=lambda item: (item[0], -item[1].rank),
            )
            passage_rank = best_reference_passage.rank
            passage_text = best_reference_passage.chunk.text
        else:
            score = 0.0
            passage_rank = None
            passage_text = None
        reference_matches.append(
            PageReferenceMatch(
                annotation_id=reference.annotation_id,
                lexical_score=round(score, 6),
                passage_rank=passage_rank,
                passage_text=passage_text,
                lexical_match=score >= passage_lexical_threshold,
            )
        )
    matched = tuple(
        item.annotation_id for item in reference_matches if item.lexical_match
    )
    best_reference_score = max(
        (item.lexical_score for item in reference_matches),
        default=0.0,
    )
    best_passage = ranked[0] if ranked else None

    return PageFetchEvaluationResult(
        case_id=case.case_id,
        candidate_rank=candidate_rank,
        requested_url=document.requested_url,
        final_url=document.final_url,
        fetched=True,
        extracted=True,
        content_type=document.content_type,
        byte_length=document.byte_length,
        readable_character_count=len(readable),
        chunk_count=len(chunks),
        ranked_passage_count=len(ranked),
        best_passage_score=best_passage.score if best_passage else 0.0,
        best_passage_text=best_passage.chunk.text if best_passage else None,
        content_hash=content_hash,
        duplicate_of_url=duplicate_of,
        reference_matches=tuple(reference_matches),
        matched_reference_ids=matched,
        best_reference_lexical_score=round(best_reference_score, 6),
    )


def export_page_fetch_evaluation(
    summary: PageFetchEvaluationSummary,
    path: str | Path,
) -> Path:
    """Write one page-fetch evaluation summary."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(summary.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output


def load_page_fetch_evaluation(path: str | Path) -> PageFetchEvaluationSummary:
    """Load and validate a page-fetch evaluation summary."""
    return PageFetchEvaluationSummary.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


def _tokens(value: str) -> frozenset[str]:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return frozenset(
        token
        for token in _TOKEN_PATTERN.findall(normalized.lower())
        if token not in _STOP_WORDS and len(token) > 1
    )


def _reference_coverage(reference: frozenset[str], passage: frozenset[str]) -> float:
    return len(reference & passage) / len(reference) if reference else 0.0


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0
