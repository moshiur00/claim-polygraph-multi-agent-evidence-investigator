"""Build a persisted provenance packet from retained investigation artifacts."""

from collections import defaultdict
from uuid import UUID

from claim_polygraph_ng.analysis.evidence_families import (
    FamilySourceRecord,
    infer_evidence_families,
)
from claim_polygraph_ng.analysis.independence_features import calculate_independence_features
from claim_polygraph_ng.analysis.source_quality import (
    SourceQualityMetadata,
    assess_source_quality,
)
from claim_polygraph_ng.domain import (
    Evidence,
    InvestigationPlan,
    InvestigationProvenance,
    ProvenanceDependency,
    ProvenanceFamily,
    ProvenanceQualityDimension,
    ProvenanceRequirementState,
    ProvenanceSourceQuality,
    Source,
)


def build_investigation_provenance(
    *,
    plan: InvestigationPlan,
    sources: tuple[Source, ...],
    evidence: tuple[Evidence, ...],
) -> InvestigationProvenance:
    """Build deterministic, uncertainty-preserving provenance without model calls."""
    passages: dict[object, list[str]] = defaultdict(list)
    for item in evidence:
        passages[item.source_id].append(item.passage)

    usable_sources = tuple(
        source for source in sources if passages[source.source_id]
    )
    records = tuple(
        FamilySourceRecord(
            source_id=str(source.source_id),
            url=source.canonical_url,
            text="\n\n".join(passages[source.source_id]),
            published_at=source.publication_date,
        )
        for source in usable_sources
    )

    if records:
        inference = infer_evidence_families(str(plan.claim_id), records)
        features = calculate_independence_features(
            inference,
            raw_source_count=len(records),
            required_independent_families=plan.minimum_independent_families,
        )
        families = tuple(
            ProvenanceFamily(
                family_id=family.family_id,
                source_ids=tuple(_uuid(source_id) for source_id in family.source_ids),
                grouping_reasons=family.grouping_reasons,
            )
            for family in inference.families
        )
        dependencies = tuple(
            ProvenanceDependency(
                left_source_id=_uuid(edge.left_source_id),
                right_source_id=_uuid(edge.right_source_id),
                status=edge.status.value,
                confidence=edge.confidence,
                reasons=edge.reasons,
            )
            for edge in inference.dependency_edges
        )
        lower = features.confirmed_independent_lower_bound
        upper = features.possible_independent_upper_bound
        unresolved = features.unresolved_dependency_count
        state = ProvenanceRequirementState(features.requirement_state.value)
        inference_limitations = inference.limitations + features.limitations
    else:
        families = ()
        dependencies = ()
        lower = upper = unresolved = 0
        state = ProvenanceRequirementState.NOT_MET
        inference_limitations = (
            "No extracted evidence passages were available for family inference.",
        )

    quality = tuple(
        _quality_record(source)
        for source in usable_sources
    )
    omitted = len(sources) - len(usable_sources)
    limitations = (
        *inference_limitations,
        "Source-quality dimensions use only metadata retained by this workflow.",
        "This packet is explanatory and is not an input to the stored verdict.",
    )
    if omitted:
        limitations = (
            *limitations,
            f"{omitted} source record(s) without retained evidence passages were excluded.",
        )
    return InvestigationProvenance(
        claim_id=plan.claim_id,
        source_ids=tuple(source.source_id for source in usable_sources),
        families=families,
        dependencies=dependencies,
        source_quality=quality,
        confirmed_independent_lower_bound=lower,
        possible_independent_upper_bound=upper,
        unresolved_dependency_count=unresolved,
        required_independent_families=plan.minimum_independent_families,
        requirement_state=state,
        limitations=limitations,
    )


def _quality_record(source: Source) -> ProvenanceSourceQuality:
    assessment = assess_source_quality(
        SourceQualityMetadata(
            source_id=source.source_id,
            source_type=source.source_type,
            publisher_identified=source.publisher is not None,
            author_identified=source.author is not None,
            publication_date=source.publication_date,
        )
    )
    return ProvenanceSourceQuality(
        source_id=source.source_id,
        dimensions=tuple(
            ProvenanceQualityDimension(
                dimension=item.dimension.value,
                finding=item.finding.value,
                reason=item.reason,
                signals=item.signals,
            )
            for item in assessment.dimensions
        ),
        limitations=assessment.limitations,
    )


def _uuid(value: str) -> UUID:
    return UUID(value)
