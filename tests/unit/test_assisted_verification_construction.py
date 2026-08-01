"""Safety tests for the disabled model-assisted construction boundary."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from claim_polygraph_ng.analysis.assisted_verification_construction import (
    AssistedConstructionProposal,
    AssistedConstructionRequest,
    AssistedEvidenceBinding,
    DisabledAssistedConstructionProvider,
    validate_assisted_proposal,
)
from claim_polygraph_ng.domain import (
    AtomicClaim,
    Evidence,
    EvidenceStance,
    ExtractionStatus,
    NormalizedNumericValue,
    NumericComparator,
    NumericDimension,
    Source,
    SourceType,
)


def test_assisted_proposal_requires_exact_approved_spans_and_has_no_verdict() -> None:
    claim = AtomicClaim(
        text="District A recorded 62 percent, higher than District B at 58 percent.",
        checkworthiness=1.0,
    )
    source = Source(
        title="Record",
        url="https://example.test/record",
        canonical_url="https://example.test/record",
        source_type=SourceType.OFFICIAL,
        retrieved_at=datetime.now(UTC),
        extraction_status=ExtractionStatus.EXTRACTED,
    )
    passage = "District A recorded 62 percent; District B recorded 58 percent."
    evidence = Evidence(
        claim_id=claim.claim_id,
        source_id=source.source_id,
        passage=passage,
        stance=EvidenceStance.CONTEXT,
        relevance_score=1.0,
    )
    request = AssistedConstructionRequest(
        claim_id=claim.claim_id,
        claim_text=claim.text,
        failed_construction_id=uuid4(),
        approved_evidence_ids=(evidence.evidence_id,),
    )
    quote = passage
    start = 0
    proposal = AssistedConstructionProposal(
        failed_construction_id=request.failed_construction_id,
        claim_text_span=claim.text,
        left_subject="District A",
        right_subject="District B",
        comparator=NumericComparator.GREATER_THAN,
        dimension=NumericDimension.PERCENTAGE,
        left_value=NormalizedNumericValue(
            value=Decimal(62),
            unit="percent",
            dimension=NumericDimension.PERCENTAGE,
        ),
        right_value=NormalizedNumericValue(
            value=Decimal(58),
            unit="percent",
            dimension=NumericDimension.PERCENTAGE,
        ),
        evidence_bindings=(
            AssistedEvidenceBinding(
                evidence_id=evidence.evidence_id,
                start_char=start,
                end_char=start + len(quote),
                quoted_text=quote,
            ),
        ),
    )

    assert validate_assisted_proposal(
        request=request,
        proposal=proposal,
        evidence=(evidence,),
    ) == proposal
    assert "verdict" not in AssistedConstructionProposal.model_fields
    assert "state" not in AssistedConstructionProposal.model_fields


def test_assisted_provider_is_disabled_by_default() -> None:
    with pytest.raises(RuntimeError, match="disabled"):
        DisabledAssistedConstructionProvider().propose(
            AssistedConstructionRequest(
                claim_id=uuid4(),
                claim_text="A claim with a failed typed construction.",
                failed_construction_id=uuid4(),
                approved_evidence_ids=(uuid4(),),
            )
        )
