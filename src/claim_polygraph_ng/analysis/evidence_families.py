"""Component-specific evidence-family inference from approved deterministic signals."""

import hashlib
from datetime import date
from enum import StrEnum

from pydantic import AnyHttpUrl, Field

from claim_polygraph_ng.analysis.canonicalization import canonicalize_url
from claim_polygraph_ng.analysis.exact_duplicates import fingerprint_content
from claim_polygraph_ng.analysis.near_duplicates import (
    NearDuplicateLabel,
    assess_near_duplicate,
)
from claim_polygraph_ng.analysis.provenance_links import extract_provenance_links
from claim_polygraph_ng.domain.base import DomainModel

EVIDENCE_FAMILY_VERSION = "families-v1"


class DependencyStatus(StrEnum):
    """Conservative source-pair dependency result."""

    CONFIRMED_DEPENDENT = "confirmed_dependent"
    LIKELY_DEPENDENT = "likely_dependent"
    LIKELY_INDEPENDENT = "likely_independent"
    UNKNOWN = "unknown"


class FamilySourceRecord(DomainModel):
    """Minimum stored source information required for family inference."""

    source_id: str
    url: AnyHttpUrl
    text: str = Field(min_length=1)
    published_at: date | None = None
    related_source_ids: tuple[str, ...] = ()
    origin_urls: tuple[AnyHttpUrl, ...] = ()


class SourceDependencyEdge(DomainModel):
    """One auditable, component-specific pair judgment."""

    component_id: str
    left_source_id: str
    right_source_id: str
    status: DependencyStatus
    confidence: float = Field(ge=0, le=1)
    reasons: tuple[str, ...] = Field(min_length=1)
    inference_version: str = EVIDENCE_FAMILY_VERSION


class InferredEvidenceFamily(DomainModel):
    """One group that counts at most once for source independence."""

    family_id: str = Field(pattern=r"^family-[0-9a-f]{16}$")
    component_id: str
    source_ids: tuple[str, ...] = Field(min_length=1)
    grouping_reasons: tuple[str, ...]


class EvidenceFamilyInference(DomainModel):
    """Complete family graph for one material claim component."""

    component_id: str
    families: tuple[InferredEvidenceFamily, ...]
    dependency_edges: tuple[SourceDependencyEdge, ...]
    unresolved_pair_count: int = Field(ge=0)
    confirmed_independent_lower_bound: int = Field(ge=1)
    possible_independent_upper_bound: int = Field(ge=1)
    inference_version: str = EVIDENCE_FAMILY_VERSION
    limitations: tuple[str, ...]

    @property
    def independent_family_count(self) -> int:
        return len(self.families)


def infer_evidence_families(
    component_id: str, sources: tuple[FamilySourceRecord, ...]
) -> EvidenceFamilyInference:
    """Apply fixed signal precedence and never consult benchmark labels."""
    if len({source.source_id for source in sources}) != len(sources):
        raise ValueError("source IDs must be unique")
    ordered = tuple(sorted(sources, key=lambda item: item.source_id))
    parents = {source.source_id: source.source_id for source in ordered}
    group_reasons: dict[str, set[str]] = {source.source_id: set() for source in ordered}

    def find(source_id: str) -> str:
        while parents[source_id] != source_id:
            parents[source_id] = parents[parents[source_id]]
            source_id = parents[source_id]
        return source_id

    def union(left: str, right: str, reason: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root == right_root:
            group_reasons[left_root].add(reason)
            return
        representative, merged = sorted((left_root, right_root))
        parents[merged] = representative
        group_reasons[representative].update(group_reasons[merged])
        group_reasons[representative].add(reason)

    edges = []
    for index, left in enumerate(ordered):
        for right in ordered[index + 1 :]:
            edge = _dependency_edge(component_id, left, right)
            edges.append(edge)
            if edge.status in {
                DependencyStatus.CONFIRMED_DEPENDENT,
                DependencyStatus.LIKELY_DEPENDENT,
            }:
                union(left.source_id, right.source_id, *edge.reasons)

    groups: dict[str, list[str]] = {}
    for source in ordered:
        groups.setdefault(find(source.source_id), []).append(source.source_id)
    families = []
    for member_ids in groups.values():
        members = tuple(sorted(member_ids))
        digest = hashlib.sha256(f"{component_id}\0{'\0'.join(members)}".encode()).hexdigest()
        root = find(members[0])
        families.append(
            InferredEvidenceFamily(
                family_id=f"family-{digest[:16]}",
                component_id=component_id,
                source_ids=members,
                grouping_reasons=tuple(sorted(group_reasons[root])),
            )
        )
    source_family = {
        source_id: family.family_id for family in families for source_id in family.source_ids
    }
    lower_parents = {family.family_id: family.family_id for family in families}

    def lower_find(family_id: str) -> str:
        while lower_parents[family_id] != family_id:
            lower_parents[family_id] = lower_parents[lower_parents[family_id]]
            family_id = lower_parents[family_id]
        return family_id

    for edge in edges:
        if edge.status is not DependencyStatus.UNKNOWN:
            continue
        left_family = lower_find(source_family[edge.left_source_id])
        right_family = lower_find(source_family[edge.right_source_id])
        if left_family != right_family:
            representative, merged = sorted((left_family, right_family))
            lower_parents[merged] = representative
    lower_bound = len({lower_find(family_id) for family_id in lower_parents})
    return EvidenceFamilyInference(
        component_id=component_id,
        families=tuple(sorted(families, key=lambda item: item.family_id)),
        dependency_edges=tuple(edges),
        unresolved_pair_count=sum(edge.status is DependencyStatus.UNKNOWN for edge in edges),
        confirmed_independent_lower_bound=lower_bound,
        possible_independent_upper_bound=len(families),
        limitations=(
            "Unknown pairs remain separate to avoid unsupported dependency claims.",
            "Ambiguous paraphrases may therefore temporarily inflate independent-family counts.",
            "No benchmark relationship label or verdict is available to this inference.",
        ),
    )


def _dependency_edge(
    component_id: str, left: FamilySourceRecord, right: FamilySourceRecord
) -> SourceDependencyEdge:
    left_url = canonicalize_url(str(left.url)).canonical_value
    right_url = canonicalize_url(str(right.url)).canonical_value
    if (
        right.source_id in left.related_source_ids
        or left.source_id in right.related_source_ids
    ):
        return _edge(
            component_id,
            left,
            right,
            DependencyStatus.CONFIRMED_DEPENDENT,
            1,
            "resolved_original_source",
        )
    left_origins = {
        canonicalize_url(str(value)).canonical_value for value in left.origin_urls
    }
    right_origins = {
        canonicalize_url(str(value)).canonical_value for value in right.origin_urls
    }
    if left_origins & right_origins or right_url in left_origins or left_url in right_origins:
        return _edge(
            component_id,
            left,
            right,
            DependencyStatus.CONFIRMED_DEPENDENT,
            1,
            "shared_origin_url",
        )
    if left_url == right_url:
        return _edge(
            component_id, left, right, DependencyStatus.CONFIRMED_DEPENDENT, 1, "canonical_url"
        )
    left_hash = fingerprint_content(left.source_id, left.text).sha256
    right_hash = fingerprint_content(right.source_id, right.text).sha256
    if left_hash == right_hash:
        return _edge(
            component_id, left, right, DependencyStatus.CONFIRMED_DEPENDENT, 1, "exact_content"
        )
    near = assess_near_duplicate(
        left_record_id=left.source_id,
        left_text=left.text,
        right_record_id=right.source_id,
        right_text=right.text,
        left_published=left.published_at,
        right_published=right.published_at,
    )
    if near.label is NearDuplicateLabel.LIKELY_DERIVATIVE:
        return _edge(
            component_id,
            left,
            right,
            DependencyStatus.LIKELY_DEPENDENT,
            near.confidence,
            "precision_gated_near_duplicate",
        )
    left_links = extract_provenance_links(left.source_id, left.text)
    right_links = extract_provenance_links(right.source_id, right.text)
    if left_links or right_links:
        confidence = max(item.confidence for item in (*left_links, *right_links))
        return _edge(
            component_id,
            left,
            right,
            DependencyStatus.LIKELY_DEPENDENT,
            confidence,
            "explicit_provenance_link",
        )
    if near.signals.independence_markers:
        return _edge(
            component_id,
            left,
            right,
            DependencyStatus.LIKELY_INDEPENDENT,
            near.confidence,
            "explicit_independence_language",
        )
    return _edge(
        component_id,
        left,
        right,
        DependencyStatus.UNKNOWN,
        0,
        "insufficient_dependency_signals",
    )


def _edge(component_id, left, right, status, confidence, *reasons):
    return SourceDependencyEdge(
        component_id=component_id,
        left_source_id=left.source_id,
        right_source_id=right.source_id,
        status=status,
        confidence=confidence,
        reasons=reasons,
    )
