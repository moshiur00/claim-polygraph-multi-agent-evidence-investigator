from claim_polygraph_ng.analysis.source_quality import (
    QualityFinding,
    SourceQualityDimension,
    SourceQualityMetadata,
    assess_source_quality,
)
from claim_polygraph_ng.domain import SourceType


def _finding(assessment, dimension):
    return next(item for item in assessment.dimensions if item.dimension is dimension)


def test_sparse_metadata_preserves_unknowns_and_has_no_score():
    assessment = assess_source_quality(
        SourceQualityMetadata(
            source_type=SourceType.OFFICIAL,
            publisher_identified=True,
            author_identified=False,
        )
    )

    assert len(assessment.dimensions) == 8
    assert all(item.finding is QualityFinding.UNKNOWN for item in assessment.dimensions)
    assert "score" not in type(assessment).model_fields
    authority = _finding(assessment, SourceQualityDimension.AUTHORITY)
    assert authority.reason == "Source type does not establish claim-specific authority."


def test_explicit_observations_produce_dimension_findings():
    assessment = assess_source_quality(
        SourceQualityMetadata(
            source_type=SourceType.ACADEMIC,
            publisher_identified=True,
            author_identified=True,
            domain_relevance_confirmed=True,
            institutional_authority_confirmed=True,
            primary_for_assertion=True,
            methodology_disclosed=True,
            citations_disclosed=True,
            editorial_policy_disclosed=True,
            correction_policy_disclosed=True,
            interested_party=False,
            temporally_compatible=True,
        )
    )

    assert all(
        item.finding is QualityFinding.FAVORABLE
        for item in assessment.dimensions
        if item.dimension is not SourceQualityDimension.CONFLICT_OF_INTEREST
    )
    assert (
        _finding(assessment, SourceQualityDimension.CONFLICT_OF_INTEREST).finding
        is QualityFinding.UNKNOWN
    )


def test_interested_party_is_disclosed_without_rejecting_source():
    assessment = assess_source_quality(
        SourceQualityMetadata(
            source_type=SourceType.ORGANIZATION,
            publisher_identified=True,
            author_identified=False,
            primary_for_assertion=True,
            interested_party=True,
        )
    )

    assert (
        _finding(assessment, SourceQualityDimension.CONFLICT_OF_INTEREST).finding
        is QualityFinding.UNFAVORABLE
    )
    assert (
        _finding(assessment, SourceQualityDimension.DIRECTNESS).finding is QualityFinding.FAVORABLE
    )


def test_partial_accountability_and_disclosed_conflict_remain_uncertain():
    assessment = assess_source_quality(
        SourceQualityMetadata(
            source_type=SourceType.NEWS,
            publisher_identified=True,
            author_identified=True,
            editorial_policy_disclosed=True,
            conflict_disclosed=True,
        )
    )

    assert (
        _finding(assessment, SourceQualityDimension.EDITORIAL_ACCOUNTABILITY).finding
        is QualityFinding.UNKNOWN
    )
    assert (
        _finding(assessment, SourceQualityDimension.CONFLICT_OF_INTEREST).finding
        is QualityFinding.MIXED
    )
