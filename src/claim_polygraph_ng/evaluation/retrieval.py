"""Evaluate claim-only search candidates against reviewed evidence packets."""

import asyncio
import json
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from claim_polygraph_ng.domain import ResearchPath, SearchRequest, SearchResult, SourceType
from claim_polygraph_ng.evaluation.models import (
    BenchmarkDataset,
    BenchmarkEvidenceAnnotation,
    RetrievalCandidate,
    RetrievalCaseResult,
    RetrievalEvaluationSummary,
    RetrievalQueryStrategy,
    RetrievalReferenceResult,
)
from claim_polygraph_ng.providers.base import SearchProvider

_PRIMARY_TYPES = {
    SourceType.OFFICIAL,
    SourceType.PRIMARY_DOCUMENT,
    SourceType.DATASET,
    SourceType.LAW_OR_REGULATION,
}
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "because",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "with",
}
_SOCIAL_HOSTS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "tiktok.com",
    "x.com",
    "youtube.com",
}
_FORUM_HOSTS = {
    "boards.straightdope.com",
    "quora.com",
    "reddit.com",
    "stackexchange.com",
}
_SECONDARY_REFERENCE_HOSTS = {
    "wikipedia.org",
}


async def run_retrieval_evaluation(
    dataset: BenchmarkDataset,
    provider: SearchProvider,
    *,
    limit: int | None = None,
    top_k: int = 10,
    lexical_threshold: float = 0.3,
    query_strategy: RetrievalQueryStrategy | str = RetrievalQueryStrategy.CLAIM_ONLY,
    empty_result_retries: int = 0,
    retry_delay_seconds: float = 0.0,
) -> RetrievalEvaluationSummary:
    """Run a bounded non-oracle query strategy and aggregate recall metrics."""
    if limit is not None and limit < 1:
        raise ValueError("retrieval evaluation limit must be at least one")
    if not 1 <= top_k <= 20:
        raise ValueError("retrieval top-k must be between 1 and 20")
    if not 0.0 <= lexical_threshold <= 1.0:
        raise ValueError("lexical threshold must be between zero and one")
    if not 0 <= empty_result_retries <= 5:
        raise ValueError("empty-result retries must be between zero and five")
    if not 0.0 <= retry_delay_seconds <= 30.0:
        raise ValueError("retry delay must be between zero and 30 seconds")
    strategy = RetrievalQueryStrategy(query_strategy)

    cases = dataset.cases[:limit]
    started_at = datetime.now(UTC)
    run_started = perf_counter()
    case_results: list[RetrievalCaseResult] = []
    provider_calls = 0

    for case in cases:
        case_started = perf_counter()
        queries = _queries_for(case.claim, strategy)
        query_results: list[tuple[str, tuple[SearchResult, ...]]] = []
        query_errors: dict[str, str] = {}
        for query in queries:
            request = SearchRequest(
                claim_id=uuid4(),
                query=query,
                research_path=ResearchPath.GENERAL,
                maximum_results=top_k,
            )
            try:
                results: tuple[SearchResult, ...] = ()
                for attempt in range(empty_result_retries + 1):
                    provider_calls += 1
                    results = await provider.search(request)
                    if results or attempt >= empty_result_retries:
                        break
                    if retry_delay_seconds:
                        await asyncio.sleep(retry_delay_seconds)
                query_results.append((query, results))
                if retry_delay_seconds:
                    await asyncio.sleep(retry_delay_seconds)
            except Exception as error:
                query_errors[query] = f"{type(error).__name__}: {error}"

        if not query_results:
            case_results.append(
                RetrievalCaseResult(
                    case_id=case.case_id,
                    queries=queries,
                    query_errors=query_errors,
                    result_count=0,
                    reference_count=len(case.candidate_evidence),
                    exact_url_hit_count=0,
                    reviewed_host_hit_count=0,
                    lexical_hit_count=0,
                    reciprocal_rank_exact_url=0.0,
                    reciprocal_rank_reviewed_host=0.0,
                    candidates=(),
                    references=tuple(
                        _match_reference(annotation, (), lexical_threshold)
                        for annotation in case.candidate_evidence
                    ),
                    duration_seconds=round(perf_counter() - case_started, 6),
                    error_type="SearchProviderError",
                    error_message="all retrieval queries failed",
                )
            )
            continue

        results, candidate_metadata = _fuse_results(
            query_results,
            top_k,
            strategy,
            case.claim,
        )
        references = tuple(
            _match_reference(annotation, results, lexical_threshold)
            for annotation in case.candidate_evidence
        )
        exact_ranks = tuple(
            reference.exact_url_rank
            for reference in references
            if reference.exact_url_rank is not None
        )
        host_ranks = tuple(
            reference.reviewed_host_rank
            for reference in references
            if reference.reviewed_host_rank is not None
        )
        first_exact = min(exact_ranks, default=None)
        first_host = min(host_ranks, default=None)
        case_results.append(
            RetrievalCaseResult(
                case_id=case.case_id,
                queries=queries,
                query_errors=query_errors,
                result_count=len(results),
                reference_count=len(references),
                exact_url_hit_count=len(exact_ranks),
                reviewed_host_hit_count=len(host_ranks),
                lexical_hit_count=sum(
                    reference.lexical_rank is not None for reference in references
                ),
                first_exact_url_rank=first_exact,
                first_reviewed_host_rank=first_host,
                reciprocal_rank_exact_url=_reciprocal_rank(first_exact),
                reciprocal_rank_reviewed_host=_reciprocal_rank(first_host),
                candidates=tuple(
                    RetrievalCandidate(
                        rank=rank,
                        url=result.url,
                        title=result.title,
                        snippet=result.snippet,
                        source_type=result.source_type,
                        publisher=result.publisher,
                        fusion_score=candidate_metadata[_normalized_url(str(result.url))][0],
                        query_ranks=candidate_metadata[_normalized_url(str(result.url))][1],
                        quality_score=candidate_metadata[_normalized_url(str(result.url))][2],
                        quality_features=candidate_metadata[_normalized_url(str(result.url))][3],
                    )
                    for rank, result in enumerate(results, start=1)
                ),
                references=references,
                duration_seconds=round(perf_counter() - case_started, 6),
            )
        )

    completed = tuple(result for result in case_results if result.error_type is None)
    references = tuple(reference for result in case_results for reference in result.references)
    primary_references = tuple(
        reference for reference in references if reference.source_type in _PRIMARY_TYPES
    )
    successful_cases = sum(result.first_reviewed_host_rank is not None for result in case_results)
    candidates = tuple(candidate for result in case_results for candidate in result.candidates)
    unique_host_total = sum(
        len({_normalized_host(str(candidate.url)) for candidate in result.candidates})
        for result in case_results
    )

    return RetrievalEvaluationSummary(
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.version,
        provider_id=provider.provider_id,
        query_strategy=strategy,
        started_at=started_at,
        duration_seconds=round(perf_counter() - run_started, 6),
        case_count=len(cases),
        completed_case_count=len(completed),
        completion_rate=round(len(completed) / len(cases), 6),
        top_k=top_k,
        search_call_count=provider_calls,
        lexical_threshold=lexical_threshold,
        reference_count=len(references),
        exact_url_recall_at_k=_recall(
            sum(reference.exact_url_rank is not None for reference in references),
            len(references),
        ),
        reviewed_host_recall_at_k=_recall(
            sum(reference.reviewed_host_rank is not None for reference in references),
            len(references),
        ),
        lexical_proxy_recall_at_k=_recall(
            sum(reference.lexical_rank is not None for reference in references),
            len(references),
        ),
        exact_url_mrr=_mean(tuple(result.reciprocal_rank_exact_url for result in case_results)),
        reviewed_host_mrr=_mean(
            tuple(result.reciprocal_rank_reviewed_host for result in case_results)
        ),
        case_success_at_k=round(successful_cases / len(cases), 6),
        reviewed_primary_host_recall_at_k=_recall(
            sum(reference.reviewed_host_rank is not None for reference in primary_references),
            len(primary_references),
        ),
        mean_candidate_quality_score=_mean(
            tuple(candidate.quality_score for candidate in candidates)
        ),
        low_quality_candidate_rate=(
            round(
                sum(candidate.quality_features["low_quality_risk"] > 0 for candidate in candidates)
                / len(candidates),
                6,
            )
            if candidates
            else 0.0
        ),
        unique_host_rate=(round(unique_host_total / len(candidates), 6) if candidates else 0.0),
        results=tuple(case_results),
        limitations=(
            "Queries are generated from the benchmark claim and strategy templates only; they "
            "do not use reviewed evidence metadata.",
            "Balanced results use reciprocal-rank fusion and retain the same final top-K "
            "candidate budget as the claim-only control.",
            "Guarded fusion preserves the leading claim-only results and limits query-expansion "
            "candidates to three tail positions in the same final top-K budget.",
            "Quality scores are deterministic engineering features, not verified source truth "
            "or semantic evidence judgments.",
            "Exact-URL recall is strict; reviewed-host recall can credit an unrelated page.",
            "Lexical proxy recall compares search titles/snippets with reviewed excerpts and "
            "summaries; it is not semantic entailment or passage recall.",
            "This search-candidate evaluation does not measure page access, extraction, "
            "reranking, evidence classification, or verdict quality.",
        ),
    )


def _queries_for(
    claim: str,
    strategy: RetrievalQueryStrategy,
) -> tuple[str, ...]:
    if strategy is RetrievalQueryStrategy.CLAIM_ONLY:
        return (claim,)
    shape_terms = _claim_shape_terms(claim)
    return (
        claim,
        f"{claim} official authoritative source {shape_terms[0]}",
        f"{claim} counterevidence fact check {shape_terms[1]}",
    )


def _claim_shape_terms(claim: str) -> tuple[str, str]:
    normalized = claim.casefold()
    numerical = bool(re.search(r"(?<![\w-])\d+(?:[.,]\d+)?", normalized))
    universal = bool(re.search(r"\b(always|all|every|exactly|never|only)\b", normalized))
    temporal = bool(
        re.search(r"\b(current|currently|today|now|still|as of|no longer)\b", normalized)
    )

    official_terms: list[str] = ["definition"]
    counter_terms: list[str] = ["limitations"]
    if numerical:
        official_terms.extend(("measurement", "standard", "units"))
        counter_terms.extend(("conditions", "convention", "range"))
    if universal:
        official_terms.append("typical")
        counter_terms.extend(("exceptions", "variability", "qualification"))
    if temporal:
        official_terms.extend(("current status", "dated statement"))
        counter_terms.extend(("ended", "superseded", "timeline"))
    return " ".join(official_terms), " ".join(counter_terms)


def _fuse_results(
    query_results: list[tuple[str, tuple[SearchResult, ...]]],
    top_k: int,
    strategy: RetrievalQueryStrategy,
    claim: str,
) -> tuple[
    tuple[SearchResult, ...],
    dict[str, tuple[float, dict[str, int], float, dict[str, float]]],
]:
    candidates: dict[str, SearchResult] = {}
    ranks_by_url: dict[str, dict[str, int]] = {}
    first_seen: dict[str, int] = {}
    seen_index = 0
    for query, results in query_results:
        for rank, result in enumerate(results, start=1):
            key = _normalized_url(str(result.url))
            if key not in candidates:
                candidates[key] = result
                first_seen[key] = seen_index
                seen_index += 1
            ranks_by_url.setdefault(key, {})[query] = rank

    query_weights = _query_weights(query_results, strategy)
    scores = {}
    for key, query_ranks in ranks_by_url.items():
        score = sum(query_weights[query] / (60 + rank) for query, rank in query_ranks.items())
        scores[key] = round(score, 9)
    max_fusion_score = max(scores.values(), default=0.0)
    quality = {
        key: _quality_features(
            candidates[key],
            claim,
            fusion_score=scores[key],
            max_fusion_score=max_fusion_score,
        )
        for key in candidates
    }
    ordered_keys = sorted(
        candidates,
        key=lambda key: (
            -scores[key],
            min(ranks_by_url[key].values()),
            first_seen[key],
        ),
    )
    if strategy is RetrievalQueryStrategy.GUARDED_FUSION:
        ordered_keys = _guarded_keys(
            query_results,
            ordered_keys,
            candidates,
            top_k,
        )
    elif strategy is RetrievalQueryStrategy.QUALITY_RERANK:
        ordered_keys = _quality_order(
            ordered_keys,
            candidates,
            quality,
            top_k,
        )
        ordered_keys = _ensure_quality_query_coverage(
            query_results,
            ordered_keys,
            quality,
            top_k,
        )
    else:
        ordered_keys = ordered_keys[:top_k]
    metadata = {
        key: (
            scores[key],
            ranks_by_url[key],
            quality[key][0],
            quality[key][1],
        )
        for key in ordered_keys
    }
    return tuple(candidates[key] for key in ordered_keys), metadata


def _query_weights(
    query_results: list[tuple[str, tuple[SearchResult, ...]]],
    strategy: RetrievalQueryStrategy,
) -> dict[str, float]:
    if strategy is not RetrievalQueryStrategy.GUARDED_FUSION:
        return {query: 1.0 for query, _ in query_results}
    weights = (3.0, 1.25, 1.0)
    return {
        query: weights[min(index, len(weights) - 1)]
        for index, (query, _) in enumerate(query_results)
    }


def _guarded_keys(
    query_results: list[tuple[str, tuple[SearchResult, ...]]],
    fused_keys: list[str],
    candidates: dict[str, SearchResult],
    top_k: int,
) -> list[str]:
    expansion_slots = min(3, top_k)
    preserved_count = top_k - expansion_slots
    claim_results = query_results[0][1]
    selected = [_normalized_url(str(result.url)) for result in claim_results[:preserved_count]]

    for _, expansion_results in query_results[1:3]:
        expansion_keys = {_normalized_url(str(result.url)) for result in expansion_results}
        expansion_key = next(
            (key for key in fused_keys if key in expansion_keys and key not in selected),
            None,
        )
        if expansion_key is not None and len(selected) < top_k:
            selected.append(expansion_key)

    for key in fused_keys:
        if len(selected) >= top_k:
            break
        if key not in selected:
            selected.append(key)

    return [key for key in selected if key in candidates]


def _quality_features(
    candidate: SearchResult,
    claim: str,
    *,
    fusion_score: float,
    max_fusion_score: float,
) -> tuple[float, dict[str, float]]:
    host = _normalized_host(str(candidate.url))
    relevance = _jaccard(
        _tokens(claim),
        _tokens(f"{candidate.title} {candidate.snippet or ''}"),
    )
    authority = _authority_score(host, candidate.source_type)
    primary_likelihood = _primary_likelihood(host, candidate.source_type)
    low_quality_risk = _low_quality_risk(host)
    fusion_signal = fusion_score / max_fusion_score if max_fusion_score else 0.0
    score = (
        0.38 * relevance
        + 0.28 * authority
        + 0.18 * primary_likelihood
        + 0.16 * fusion_signal
        - 0.35 * low_quality_risk
    )
    features = {
        "claim_relevance": round(relevance, 6),
        "authority": round(authority, 6),
        "primary_likelihood": round(primary_likelihood, 6),
        "fusion_signal": round(fusion_signal, 6),
        "low_quality_risk": round(low_quality_risk, 6),
    }
    return round(min(1.0, max(0.0, score)), 6), features


def _authority_score(host: str, source_type: SourceType) -> float:
    if source_type in {SourceType.OFFICIAL, SourceType.LAW_OR_REGULATION}:
        return 1.0
    if host.endswith(".gov") or ".gov." in host or host.endswith(".int"):
        return 1.0
    if source_type in {SourceType.ACADEMIC, SourceType.DATASET}:
        return 0.85
    if (
        host.endswith(".edu")
        or ".edu." in host
        or host.endswith(".ac.uk")
        or host.endswith(".ncbi.nlm.nih.gov")
    ):
        return 0.85
    if source_type is SourceType.NEWS:
        return 0.45
    if _host_matches(host, _SECONDARY_REFERENCE_HOSTS):
        return 0.35
    if _host_matches(host, _SOCIAL_HOSTS | _FORUM_HOSTS):
        return 0.1
    return 0.25


def _primary_likelihood(host: str, source_type: SourceType) -> float:
    if source_type in {
        SourceType.OFFICIAL,
        SourceType.PRIMARY_DOCUMENT,
        SourceType.DATASET,
        SourceType.LAW_OR_REGULATION,
    }:
        return 1.0
    if host.endswith(".gov") or ".gov." in host or host.endswith(".int"):
        return 0.9
    if source_type is SourceType.ACADEMIC or host.endswith(".ncbi.nlm.nih.gov"):
        return 0.7
    if host.endswith(".edu") or ".edu." in host or host.endswith(".ac.uk"):
        return 0.6
    return 0.2


def _low_quality_risk(host: str) -> float:
    if _host_matches(host, _SOCIAL_HOSTS):
        return 1.0
    if _host_matches(host, _FORUM_HOSTS):
        return 0.7
    if _host_matches(host, _SECONDARY_REFERENCE_HOSTS):
        return 0.2
    return 0.0


def _host_matches(host: str, domains: set[str]) -> bool:
    return any(host == domain or host.endswith(f".{domain}") for domain in domains)


def _quality_order(
    fused_keys: list[str],
    candidates: dict[str, SearchResult],
    quality: dict[str, tuple[float, dict[str, float]]],
    top_k: int,
) -> list[str]:
    selected: list[str] = []
    remaining = set(fused_keys)
    host_counts: dict[str, int] = {}
    fused_position = {key: index for index, key in enumerate(fused_keys)}

    while remaining and len(selected) < top_k:
        key = max(
            remaining,
            key=lambda item: (
                quality[item][0]
                - 0.08
                * host_counts.get(
                    _normalized_host(str(candidates[item].url)),
                    0,
                ),
                quality[item][1]["claim_relevance"],
                -fused_position[item],
            ),
        )
        selected.append(key)
        remaining.remove(key)
        host = _normalized_host(str(candidates[key].url))
        host_counts[host] = host_counts.get(host, 0) + 1
    return selected


def _ensure_quality_query_coverage(
    query_results: list[tuple[str, tuple[SearchResult, ...]]],
    ordered_keys: list[str],
    quality: dict[str, tuple[float, dict[str, float]]],
    top_k: int,
) -> list[str]:
    """Reserve early access for safe expansion paths already captured by search."""
    access_window = min(3, top_k)
    if access_window < 2:
        return ordered_keys

    leading = ordered_keys[:access_window]
    for _, expansion_results in query_results[1:3]:
        path_keys = [
            _normalized_url(str(result.url))
            for result in expansion_results
            if _normalized_url(str(result.url)) in quality
        ]
        if any(key in leading for key in path_keys):
            continue
        eligible = [
            key
            for key in path_keys
            if quality[key][0] >= 0.15 and quality[key][1]["low_quality_risk"] <= 0.2
        ]
        if not eligible:
            continue
        replacement = max(
            eligible,
            key=lambda key: (
                quality[key][0],
                quality[key][1]["claim_relevance"],
                -path_keys.index(key),
            ),
        )
        if replacement in leading:
            continue
        ordered_keys.remove(replacement)
        ordered_keys.insert(access_window - 1, replacement)
        leading = ordered_keys[:access_window]

    return ordered_keys[:top_k]


def export_retrieval_evaluation(
    summary: RetrievalEvaluationSummary,
    path: str | Path,
) -> Path:
    """Write one machine-readable retrieval evaluation summary."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(summary.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output


def load_retrieval_evaluation(path: str | Path) -> RetrievalEvaluationSummary:
    """Load and validate a retrieval evaluation summary."""
    return RetrievalEvaluationSummary.model_validate_json(Path(path).read_text(encoding="utf-8"))


def _match_reference(
    annotation: BenchmarkEvidenceAnnotation,
    results: tuple[SearchResult, ...],
    lexical_threshold: float,
) -> RetrievalReferenceResult:
    reference_url = _normalized_url(str(annotation.source_url))
    reference_host = _normalized_host(str(annotation.source_url))
    reference_tokens = _tokens(
        f"{annotation.source_title} {annotation.excerpt} {annotation.evidence_summary}"
    )
    exact_rank: int | None = None
    host_rank: int | None = None
    lexical_rank: int | None = None
    best_lexical_score = 0.0

    for rank, result in enumerate(results, start=1):
        result_url = str(result.url)
        if exact_rank is None and _normalized_url(result_url) == reference_url:
            exact_rank = rank
        if host_rank is None and _normalized_host(result_url) == reference_host:
            host_rank = rank
        score = _jaccard(
            reference_tokens,
            _tokens(f"{result.title} {result.snippet or ''}"),
        )
        best_lexical_score = max(best_lexical_score, score)
        if lexical_rank is None and score >= lexical_threshold:
            lexical_rank = rank

    return RetrievalReferenceResult(
        annotation_id=annotation.annotation_id,
        source_url=annotation.source_url,
        source_type=annotation.source_type,
        exact_url_rank=exact_rank,
        reviewed_host_rank=host_rank,
        lexical_rank=lexical_rank,
        best_lexical_score=round(best_lexical_score, 6),
    )


def _normalized_url(value: str) -> str:
    parsed = urlsplit(value)
    path = unquote(parsed.path).rstrip("/") or "/"
    return f"{_normalized_host(value)}{path.lower()}"


def _normalized_host(value: str) -> str:
    host = (urlsplit(value).hostname or "").lower()
    return host.removeprefix("www.")


def _tokens(value: str) -> frozenset[str]:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return frozenset(
        token
        for token in _TOKEN_PATTERN.findall(normalized.lower())
        if token not in _STOP_WORDS and len(token) > 1
    )


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _reciprocal_rank(rank: int | None) -> float:
    return round(1 / rank, 6) if rank is not None else 0.0


def _recall(hits: int, total: int) -> float | None:
    return round(hits / total, 6) if total else None


def _mean(values: tuple[float, ...]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0
