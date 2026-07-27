"""Conservative, order-invariant evidence consolidation."""

from collections import defaultdict
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

from claim_polygraph_ng.analysis.exact_duplicates import normalize_exact_content
from claim_polygraph_ng.analysis.independence import analyze_source_independence
from claim_polygraph_ng.domain import Evidence, Source
from claim_polygraph_ng.domain.provenance import (
    ConsolidationDecision,
    ConsolidationReason,
    EvidenceConsolidation,
)


def consolidate_evidence(
    *,
    claim_id: UUID,
    sources: tuple[Source, ...],
    evidence: tuple[Evidence, ...],
    required_families: int,
) -> EvidenceConsolidation:
    """Canonicalize sources, group dependencies, and remove exact duplicates."""
    _validate_inputs(claim_id, sources, evidence)
    canonical_sources, source_aliases, source_decisions = _consolidate_sources(sources)
    aliased_evidence = tuple(
        item.model_copy(update={"source_id": source_aliases[item.source_id]})
        for item in sorted(evidence, key=lambda value: str(value.evidence_id))
    )

    family_evidence, independence = analyze_source_independence(
        claim_id=claim_id,
        sources=canonical_sources,
        evidence=aliased_evidence,
        required_families=required_families,
    )
    consolidated, evidence_decisions = _consolidate_exact_evidence(family_evidence)
    return EvidenceConsolidation(
        claim_id=claim_id,
        sources=canonical_sources,
        evidence=consolidated,
        independence=independence,
        source_decisions=source_decisions,
        evidence_decisions=evidence_decisions,
        input_source_count=len(sources),
        input_evidence_count=len(evidence),
    )


def _validate_inputs(
    claim_id: UUID,
    sources: tuple[Source, ...],
    evidence: tuple[Evidence, ...],
) -> None:
    source_ids = [source.source_id for source in sources]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("source identifiers must be unique")
    evidence_ids = [item.evidence_id for item in evidence]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("evidence identifiers must be unique")
    available = set(source_ids)
    if any(item.source_id not in available for item in evidence):
        raise ValueError("every evidence item must reference a supplied source")
    if any(item.claim_id != claim_id for item in evidence):
        raise ValueError("every evidence item must reference the consolidated claim")


def _consolidate_sources(
    sources: tuple[Source, ...],
) -> tuple[
    tuple[Source, ...],
    dict[UUID, UUID],
    tuple[ConsolidationDecision, ...],
]:
    groups: dict[str, list[Source]] = defaultdict(list)
    for source in sources:
        groups[_canonical_url(str(source.canonical_url))].append(source)

    representatives: list[Source] = []
    aliases: dict[UUID, UUID] = {}
    decisions: list[ConsolidationDecision] = []
    for group in groups.values():
        ordered = sorted(group, key=lambda item: str(item.source_id))
        representative = ordered[0]
        representatives.append(representative)
        aliases.update({item.source_id: representative.source_id for item in ordered})
        if len(ordered) > 1:
            decisions.append(
                ConsolidationDecision(
                    representative_id=representative.source_id,
                    merged_ids=tuple(item.source_id for item in ordered[1:]),
                    reasons=(ConsolidationReason.CANONICAL_URL,),
                )
            )
    return (
        tuple(sorted(representatives, key=lambda item: str(item.source_id))),
        aliases,
        tuple(sorted(decisions, key=lambda item: str(item.representative_id))),
    )


def _consolidate_exact_evidence(
    evidence: tuple[Evidence, ...],
) -> tuple[tuple[Evidence, ...], tuple[ConsolidationDecision, ...]]:
    groups: dict[tuple, list[Evidence]] = defaultdict(list)
    for item in evidence:
        # Stance is deliberately part of the key: conflicting interpretations
        # remain visible even when they quote the same passage.
        key = (
            item.claim_id,
            item.stance,
            _normalized_passage(item.passage),
            _normalized_passage(item.context or ""),
        )
        groups[key].append(item)

    representatives: list[Evidence] = []
    decisions: list[ConsolidationDecision] = []
    for group in groups.values():
        ordered = sorted(group, key=lambda item: str(item.evidence_id))
        representative = ordered[0]
        representatives.append(representative)
        if len(ordered) > 1:
            decisions.append(
                ConsolidationDecision(
                    representative_id=representative.evidence_id,
                    merged_ids=tuple(item.evidence_id for item in ordered[1:]),
                    reasons=(ConsolidationReason.EXACT_NORMALIZED_PASSAGE,),
                )
            )
    return (
        tuple(sorted(representatives, key=lambda item: str(item.evidence_id))),
        tuple(sorted(decisions, key=lambda item: str(item.representative_id))),
    )


def _normalized_passage(value: str) -> str:
    return normalize_exact_content(value)


def _canonical_url(value: str) -> str:
    parsed = urlsplit(value)
    scheme = parsed.scheme.casefold()
    host = (parsed.hostname or "").casefold().removeprefix("www.")
    port = parsed.port
    netloc = host
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    return urlunsplit((scheme, netloc, parsed.path or "/", query, ""))
