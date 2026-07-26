"""Group evidence sources that are demonstrably related."""

import re
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, UUID, uuid5

from claim_polygraph_ng.domain import Evidence, EvidenceFamily, IndependenceAnalysis, Source

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_URL_PATTERN = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)


def analyze_source_independence(
    *,
    claim_id: UUID,
    sources: tuple[Source, ...],
    evidence: tuple[Evidence, ...],
    required_families: int,
) -> tuple[tuple[Evidence, ...], IndependenceAnalysis]:
    """Assign deterministic families using hosts, publishers, citations, and duplicates."""
    sources_by_id = {source.source_id: source for source in sources}
    evidence_sources = tuple(
        sorted(
            {item.source_id for item in evidence if item.source_id in sources_by_id},
            key=str,
        )
    )
    parent = {source_id: source_id for source_id in evidence_sources}
    reasons: dict[frozenset[UUID], set[str]] = {}

    def find(source_id: UUID) -> UUID:
        while parent[source_id] != source_id:
            parent[source_id] = parent[parent[source_id]]
            source_id = parent[source_id]
        return source_id

    def union(left: UUID, right: UUID, reason: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root
        reasons.setdefault(frozenset({left, right}), set()).add(reason)

    for index, left_id in enumerate(evidence_sources):
        left_source = sources_by_id[left_id]
        left_evidence = tuple(item for item in evidence if item.source_id == left_id)
        for right_id in evidence_sources[index + 1 :]:
            right_source = sources_by_id[right_id]
            right_evidence = tuple(item for item in evidence if item.source_id == right_id)
            if _host(left_source) == _host(right_source):
                union(left_id, right_id, "same_host")
            if (
                left_source.publisher
                and right_source.publisher
                and left_source.publisher.casefold() == right_source.publisher.casefold()
            ):
                union(left_id, right_id, "same_publisher")
            if _passages_overlap(left_evidence, right_evidence):
                union(left_id, right_id, "near_duplicate_passage")
            if _cites_host(left_evidence, _host(right_source)) or _cites_host(
                right_evidence, _host(left_source)
            ):
                union(left_id, right_id, "explicit_cross_citation")

    grouped: dict[UUID, list[UUID]] = {}
    for source_id in evidence_sources:
        grouped.setdefault(find(source_id), []).append(source_id)

    families: list[EvidenceFamily] = []
    family_by_source: dict[UUID, UUID] = {}
    for source_ids in grouped.values():
        ordered_ids = tuple(sorted(source_ids, key=str))
        family_id = uuid5(
            NAMESPACE_URL,
            f"{claim_id}:" + ":".join(str(source_id) for source_id in ordered_ids),
        )
        family_reasons = {
            reason
            for pair, pair_reasons in reasons.items()
            if pair <= set(ordered_ids)
            for reason in pair_reasons
        }
        if not family_reasons:
            family_reasons.add("distinct_source")
        family_evidence = tuple(
            item.evidence_id for item in evidence if item.source_id in ordered_ids
        )
        families.append(
            EvidenceFamily(
                family_id=family_id,
                source_ids=ordered_ids,
                evidence_ids=family_evidence,
                hostnames=tuple(sorted({_host(sources_by_id[item]) for item in ordered_ids})),
                publishers=tuple(
                    sorted(
                        {
                            sources_by_id[item].publisher
                            for item in ordered_ids
                            if sources_by_id[item].publisher
                        }
                    )
                ),
                grouping_reasons=tuple(sorted(family_reasons)),
            )
        )
        family_by_source.update({source_id: family_id for source_id in ordered_ids})

    updated_evidence = tuple(
        item.model_copy(update={"evidence_family_id": family_by_source.get(item.source_id)})
        for item in evidence
    )
    analysis = IndependenceAnalysis(
        claim_id=claim_id,
        required_independent_families=required_families,
        families=tuple(sorted(families, key=lambda family: str(family.family_id))),
        limitations=(
            "Deterministic grouping detects shared hosts, publishers, near-duplicate passages, "
            "and explicit cross-citations only.",
            "Undisclosed syndication or reliance on the same offline authority may remain hidden.",
        ),
    )
    return updated_evidence, analysis


def _host(source: Source) -> str:
    return (urlsplit(str(source.canonical_url)).hostname or "").casefold().removeprefix("www.")


def _passages_overlap(
    left: tuple[Evidence, ...],
    right: tuple[Evidence, ...],
) -> bool:
    return any(
        _jaccard(_tokens(left_item.passage), _tokens(right_item.passage)) >= 0.9
        for left_item in left
        for right_item in right
    )


def _cites_host(items: tuple[Evidence, ...], host: str) -> bool:
    return any(
        host
        in {
            (urlsplit(url.rstrip(".,;")).hostname or "").casefold().removeprefix("www.")
            for url in _URL_PATTERN.findall(item.passage)
        }
        for item in items
    )


def _tokens(value: str) -> frozenset[str]:
    return frozenset(_TOKEN_PATTERN.findall(value.casefold()))


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    return len(left & right) / len(left | right) if left or right else 0.0
