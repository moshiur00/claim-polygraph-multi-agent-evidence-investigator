"""Frozen replay and calibration tests for verification construction v2."""

import json
from datetime import UTC, datetime
from pathlib import Path

from claim_polygraph_ng.analysis.comparative_verification import (
    construct_comparative_assertion,
)
from claim_polygraph_ng.analysis.temporal_construction import (
    construct_temporal_comparison,
    is_temporal_comparison,
)
from claim_polygraph_ng.analysis.verification_calibration import (
    calculate_verification_calibration,
)
from claim_polygraph_ng.domain import (
    AtomicClaim,
    Evidence,
    EvidenceStance,
    ExtractionStatus,
    Source,
    SourceType,
)


def test_frozen_v2_construction_benchmark_has_perfect_safe_baseline() -> None:
    payload = json.loads(
        Path("benchmarks/verification_construction_v2.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["frozen"] is True
    assert payload["review_status"] == "approved_with_distinct_approval"
    assert payload["annotator_identity"] != payload["distinct_approver_identity"]
    outcomes = []
    for case in payload["cases"]:
        claim = AtomicClaim(text=case["claim"], checkworthiness=1.0)
        source = Source(
            title=case["case_id"],
            url=f"https://example.test/{case['case_id'].lower()}",
            canonical_url=f"https://example.test/{case['case_id'].lower()}",
            source_type=SourceType.OFFICIAL,
            retrieved_at=datetime.now(UTC),
            extraction_status=ExtractionStatus.EXTRACTED,
        )
        evidence = Evidence(
            claim_id=claim.claim_id,
            source_id=source.source_id,
            passage=case["passage"],
            stance=EvidenceStance.CONTEXT,
            relevance_score=1.0,
        )
        if is_temporal_comparison(claim.text):
            construction, assertion, _ = construct_temporal_comparison(
                claim=claim,
                evidence=(evidence,),
            )
        else:
            construction, assertion, _ = construct_comparative_assertion(
                claim=claim,
                evidence=(evidence,),
            )
        observed_constructed = (
            construction is not None and construction.state.value == "constructed"
        )
        outcomes.append(
            (
                observed_constructed,
                assertion.state.value if assertion else None,
                case["expected_constructed"],
                case["expected_state"],
            )
        )

    metrics = calculate_verification_calibration(tuple(outcomes))
    assert metrics.case_count == 12
    assert metrics.construction_recall == 1
    assert metrics.construction_precision == 1
    assert metrics.outcome_accuracy == 1
    assert metrics.unsafe_construction_count == 0
