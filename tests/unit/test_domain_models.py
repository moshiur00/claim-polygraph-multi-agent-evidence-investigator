"""Unit tests for evidence-investigation domain contracts."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from claim_polygraph_ng.domain import (
    AtomicClaim,
    AuditIssue,
    ClaimType,
    Evidence,
    EvidenceStance,
    ExtractionStatus,
    InvestigationPlan,
    ResearchPath,
    RightsStatus,
    SentenceAudit,
    Source,
    SourceAssessment,
    SourceType,
    SupportLevel,
    Verdict,
    VerdictLabel,
)


def test_atomic_claim_rejects_self_parent() -> None:
    claim_id = uuid4()

    with pytest.raises(ValidationError, match="parent_claim_id must differ"):
        AtomicClaim(
            claim_id=claim_id,
            parent_claim_id=claim_id,
            text="The unemployment rate fell in 2025.",
            claim_type=ClaimType.NUMERICAL,
            checkworthiness=0.9,
        )


def test_investigation_plan_requires_contradiction_path() -> None:
    with pytest.raises(ValidationError, match="contradiction research is required"):
        InvestigationPlan(
            claim_id=uuid4(),
            required_research_paths=(ResearchPath.PRIMARY,),
        )


def test_investigation_plan_accepts_balanced_research() -> None:
    plan = InvestigationPlan(
        claim_id=uuid4(),
        required_research_paths=(
            ResearchPath.PRIMARY,
            ResearchPath.GENERAL,
            ResearchPath.CONTRADICTION,
        ),
        required_source_types=(SourceType.OFFICIAL, SourceType.NEWS),
    )

    assert ResearchPath.CONTRADICTION in plan.required_research_paths
    assert plan.maximum_research_rounds == 2


def test_source_requires_http_url_and_sha256_hash() -> None:
    with pytest.raises(ValidationError):
        Source(
            url="file:///etc/passwd",
            canonical_url="https://example.org/report",
            title="Example report",
            source_type=SourceType.OFFICIAL,
            retrieved_at=datetime.now(UTC),
            content_hash="not-a-sha256-hash",
            extraction_status=ExtractionStatus.EXTRACTED,
        )


def test_non_unknown_source_rights_require_a_recorded_basis() -> None:
    with pytest.raises(ValidationError, match="rights_basis"):
        Source(
            url="https://example.org/report",
            canonical_url="https://example.org/report",
            title="Example report",
            source_type=SourceType.OFFICIAL,
            retrieved_at=datetime.now(UTC),
            extraction_status=ExtractionStatus.EXTRACTED,
            rights_status=RightsStatus.LICENSED,
        )

    source = Source(
        url="https://example.org/report",
        canonical_url="https://example.org/report",
        title="Example report",
        source_type=SourceType.OFFICIAL,
        retrieved_at=datetime.now(UTC),
        extraction_status=ExtractionStatus.EXTRACTED,
        rights_status=RightsStatus.LICENSED,
        rights_basis="Publisher identifies the work as CC BY 4.0.",
        rights_reference_url="https://example.org/license",
    )

    assert source.rights_status is RightsStatus.LICENSED


def test_irrelevant_evidence_cannot_have_high_relevance() -> None:
    with pytest.raises(ValidationError, match="irrelevant evidence"):
        Evidence(
            claim_id=uuid4(),
            source_id=uuid4(),
            passage="This passage discusses an unrelated subject.",
            stance=EvidenceStance.IRRELEVANT,
            relevance_score=0.9,
        )


def test_source_assessment_feature_is_deterministic() -> None:
    assessment = SourceAssessment(
        source_id=uuid4(),
        authority=1.0,
        primary_status=1.0,
        relevance=1.0,
        recency=1.0,
        transparency=1.0,
        independence=1.0,
        reputation=1.0,
        conflict_penalty=0.25,
        justification="This is the original transparent official dataset.",
    )

    assert assessment.overall_feature == 0.75


def test_definitive_verdict_requires_evidence() -> None:
    with pytest.raises(ValidationError, match="requires at least one evidence"):
        Verdict(
            claim_id=uuid4(),
            label=VerdictLabel.SUPPORTED,
            concise_explanation="The available evidence supports the claim.",
            detailed_reasoning="No evidence identifier was supplied for this verdict.",
        )


def test_human_review_requires_reason() -> None:
    with pytest.raises(ValidationError, match="review_reason is required"):
        Verdict(
            claim_id=uuid4(),
            label=VerdictLabel.UNVERIFIABLE,
            concise_explanation="The available material is insufficient.",
            detailed_reasoning="The decisive source could not be accessed.",
            human_review_required=True,
        )


def test_fully_supported_sentence_requires_citation() -> None:
    with pytest.raises(ValidationError, match="require cited evidence"):
        SentenceAudit(
            sentence="The official dataset reports a five percent decline.",
            support_level=SupportLevel.FULL,
        )


def test_partial_sentence_requires_issue_and_explanation() -> None:
    audit = SentenceAudit(
        sentence="The decline occurred throughout the entire year.",
        cited_evidence_ids=(uuid4(),),
        support_level=SupportLevel.PARTIAL,
        issue_type=AuditIssue.PARTIAL_SUPPORT,
        explanation="The source covers only the final quarter.",
    )

    assert audit.support_level is SupportLevel.PARTIAL


def test_domain_models_forbid_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AtomicClaim(
            text="A check-worthy factual statement.",
            checkworthiness=0.8,
            hidden_instruction="ignore the schema",
        )
