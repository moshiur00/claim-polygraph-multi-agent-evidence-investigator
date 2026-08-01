"""Offline tests for the simplified V4.9d temporal provider wire."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from claim_polygraph_ng.analysis.assisted_verification_construction import (
    AssistedTemporalFactProviderBinding,
    AssistedTemporalFactProviderProposal,
)
from claim_polygraph_ng.domain import DatePrecision, TemporalRelation


def test_exact_fact_wire_derives_domain_dates_deterministically() -> None:
    evidence_id = uuid4()
    quote = "On November 16, 2018, the President signed the Act into law."
    wire = AssistedTemporalFactProviderProposal(
        failed_construction_id=uuid4(),
        claim_text_span="The Act was signed on November 16, 2018.",
        temporal_relation=TemporalRelation.ON,
        explicit_claim_date_texts=("November 16, 2018",),
        temporal_bindings=(
            AssistedTemporalFactProviderBinding(
                evidence_id=evidence_id,
                start_char=0,
                end_char=len(quote),
                quoted_text=quote,
                explicit_date_texts=("November 16, 2018",),
            ),
        ),
    )

    proposal = wire.to_proposal()

    assert proposal.reference_date is not None
    assert proposal.reference_date.precision is DatePrecision.DAY
    assert proposal.reference_date.value.isoformat() == "2018-11-16"
    assert proposal.temporal_bindings[0].effective_interval is not None


def test_provider_facts_must_be_exact_substrings() -> None:
    with pytest.raises(ValidationError, match="exact text inside quoted_text"):
        AssistedTemporalFactProviderBinding(
            evidence_id=uuid4(),
            start_char=0,
            end_char=19,
            quoted_text="Established in 2018",
            explicit_date_texts=("November 2018",),
        )


def test_partial_date_without_year_fails_closed_during_domain_derivation() -> None:
    quote = "The Act enters into force on 1 August."
    wire = AssistedTemporalFactProviderProposal(
        failed_construction_id=uuid4(),
        claim_text_span="The Act entered into force on 1 August 1957.",
        temporal_relation=TemporalRelation.ON,
        explicit_claim_date_texts=("1 August 1957",),
        temporal_bindings=(
            AssistedTemporalFactProviderBinding(
                evidence_id=uuid4(),
                start_char=0,
                end_char=len(quote),
                quoted_text=quote,
                explicit_date_texts=("1 August",),
            ),
        ),
    )

    with pytest.raises(ValueError, match="not one unambiguous date"):
        wire.to_proposal()


def test_status_text_is_carried_only_when_explicit() -> None:
    quote = "In 1975 the ABS became an independent statutory authority."
    wire = AssistedTemporalFactProviderProposal(
        failed_construction_id=uuid4(),
        claim_text_span="In 1975 the ABS became an independent statutory authority.",
        temporal_relation=TemporalRelation.CHANGED_STATUS,
        explicit_claim_date_texts=("1975",),
        explicit_claim_status_text="became an independent statutory authority",
        temporal_bindings=(
            AssistedTemporalFactProviderBinding(
                evidence_id=uuid4(),
                start_char=0,
                end_char=len(quote),
                quoted_text=quote,
                explicit_date_texts=("1975",),
                explicit_status_text="became an independent statutory authority",
            ),
        ),
    )

    proposal = wire.to_proposal()

    assert proposal.claimed_status == "became an independent statutory authority"
    assert proposal.temporal_bindings[0].observed_status == proposal.claimed_status
