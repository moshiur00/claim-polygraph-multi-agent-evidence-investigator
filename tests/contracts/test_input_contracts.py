"""Input and extracted-claim provenance contracts."""

import pytest
from pydantic import TypeAdapter, ValidationError

from claim_polygraph_ng.domain.input import (
    ClaimExtractionPacket,
    ExtractedClaimCandidate,
    InvestigationInput,
)


def test_input_union_is_discriminated() -> None:
    adapter = TypeAdapter(InvestigationInput)
    article = adapter.validate_python(
        {"kind": "article_text", "text": "This sufficiently long article states a fact."}
    )
    url = adapter.validate_python({"kind": "public_url", "url": "https://example.org/news"})

    assert article.kind.value == "article_text"
    assert str(url.url) == "https://example.org/news"


def test_candidate_offsets_and_automatic_start_fail_closed() -> None:
    with pytest.raises(ValidationError, match="offsets"):
        ExtractedClaimCandidate(
            text="A factual claim.",
            start_char=0,
            end_char=3,
            checkworthiness=0.8,
            rank=1,
        )
    candidate = ExtractedClaimCandidate(
        text="A factual claim.",
        start_char=0,
        end_char=16,
        checkworthiness=0.8,
        rank=1,
    )
    with pytest.raises(ValidationError, match="cannot automatically start"):
        ClaimExtractionPacket(
            input_kind="article_text",
            content_hash="a" * 64,
            content_length=16,
            candidates=(candidate,),
            automatic_investigation_started=True,
        )
