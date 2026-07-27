"""Tests for reviewed complex-claim benchmark coverage contracts."""

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from claim_polygraph_ng.domain import (
    ClaimType,
    EvidenceStance,
    SourceType,
    VerdictLabel,
)
from claim_polygraph_ng.evaluation import (
    AnnotationStatus,
    BenchmarkCase,
    BenchmarkEvidenceAnnotation,
    EvaluationCategory,
    RiskLevel,
    load_benchmark,
)

BENCHMARK = Path(__file__).parents[2] / "benchmarks" / "initial_claims_v1.json"


def test_reviewed_complex_case_requires_evidence_for_every_material_component() -> None:
    payload = {
        "case_id": "CPNG-999",
        "claim": "The programme cut costs and increased output.",
        "categories": (EvaluationCategory.CORPORATE,),
        "expected_claim_type": ClaimType.FACTUAL,
        "risk_level": RiskLevel.MEDIUM,
        "annotation_status": AnnotationStatus.REVIEWED,
        "proposed_verdict": VerdictLabel.MIXED,
        "proposed_rationale": (
            "One material outcome is supported and the other remains unaddressed."
        ),
        "candidate_evidence": (
            BenchmarkEvidenceAnnotation(
                annotation_id="E1",
                source_url="https://example.org/report",
                source_title="Programme report",
                publisher="Example authority",
                source_type=SourceType.OFFICIAL,
                stance=EvidenceStance.SUPPORTS,
                excerpt="The programme reduced audited costs.",
                evidence_summary="The passage establishes only the cost component.",
                accessed_at=date(2026, 7, 27),
                independence_note="This is the primary programme report.",
                material_component_numbers=(1,),
            ),
        ),
        "expected_verdict": VerdictLabel.MIXED,
        "expected_components": (
            "The programme cut costs.",
            "The programme increased output.",
        ),
        "annotated_by": "Primary Annotator",
        "annotated_at": date(2026, 7, 27),
        "approved_by": "Independent Reviewer",
        "approved_at": date(2026, 7, 27),
        "reviewed_by": "Independent Reviewer",
        "reviewed_at": date(2026, 7, 27),
    }

    with pytest.raises(ValidationError, match="evidence for every component"):
        BenchmarkCase.model_validate(payload)

    payload["candidate_evidence"] = (
        payload["candidate_evidence"][0],
        BenchmarkEvidenceAnnotation(
            annotation_id="E2",
            source_url="https://independent.example/analysis",
            source_title="Independent output analysis",
            publisher="Independent analyst",
            source_type=SourceType.ORGANIZATION,
            stance=EvidenceStance.CONTRADICTS,
            excerpt="Audited output did not increase.",
            evidence_summary="The passage addresses the separate output component.",
            accessed_at=date(2026, 7, 27),
            independence_note="This analysis is organizationally independent.",
            material_component_numbers=(2,),
        ),
    )
    case = BenchmarkCase.model_validate(payload)
    assert len(case.expected_components) == 2


def test_reviewed_case_requires_a_distinct_typed_approver() -> None:
    payload = load_benchmark(BENCHMARK).cases[0].model_dump()
    payload["approved_by"] = payload["annotated_by"]
    payload["reviewed_by"] = payload["annotated_by"]

    with pytest.raises(ValidationError, match="distinct approver"):
        BenchmarkCase.model_validate(payload)


def test_legacy_review_fields_must_mirror_typed_approval() -> None:
    payload = load_benchmark(BENCHMARK).cases[0].model_dump()
    payload["reviewed_by"] = "Different person"

    with pytest.raises(ValidationError, match="legacy reviewer fields"):
        BenchmarkCase.model_validate(payload)
