"""Frozen Stage 7.3 citation-assurance and review-routing evaluation."""

import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field

from claim_polygraph_ng.analysis import audit_structured_assertions, route_human_review
from claim_polygraph_ng.domain import (
    CitationAssuranceStatus,
    Evidence,
    EvidenceStance,
    JudgmentReadinessState,
    ProvenanceRequirementState,
    ReviewRiskLevel,
    ReviewRoutingContext,
    StructuredReportAssertion,
)
from claim_polygraph_ng.domain.base import DomainModel


class Phase7AssuranceCaseResult(DomainModel):
    case_id: str
    expected_status: CitationAssuranceStatus
    observed_status: CitationAssuranceStatus
    citation_correct: bool
    expected_review: bool
    observed_review: bool
    route_correct: bool
    critical_route_required: bool


class Phase7AssuranceEvaluation(DomainModel):
    evaluation_id: str = "phase7-stage7.3-assurance-routing-v1"
    dataset_id: str
    dataset_version: int = Field(ge=1)
    case_count: int = Field(ge=1)
    citation_accuracy: float = Field(ge=0, le=1)
    critical_route_recall: float = Field(ge=0, le=1)
    route_accuracy: float = Field(ge=0, le=1)
    unsupported_marked_supported_count: int = Field(ge=0)
    results: tuple[Phase7AssuranceCaseResult, ...]
    promotion_gate_passed: bool
    model_calls: int = 0
    network_calls: int = 0
    pdf_downloads: int = 0


def evaluate_phase7_assurance(path: str | Path) -> Phase7AssuranceEvaluation:
    benchmark = json.loads(Path(path).read_text(encoding="utf-8"))
    results = tuple(_evaluate_case(item) for item in benchmark["cases"])
    critical = [item for item in results if item.critical_route_required]
    critical_recall = (
        sum(item.observed_review for item in critical) / len(critical)
        if critical
        else 1.0
    )
    citation_accuracy = sum(item.citation_correct for item in results) / len(results)
    route_accuracy = sum(item.route_correct for item in results) / len(results)
    false_supported = sum(
        item.expected_status is not CitationAssuranceStatus.SUPPORTED
        and item.observed_status is CitationAssuranceStatus.SUPPORTED
        for item in results
    )
    return Phase7AssuranceEvaluation(
        dataset_id=benchmark["dataset_id"],
        dataset_version=benchmark["version"],
        case_count=len(results),
        citation_accuracy=citation_accuracy,
        critical_route_recall=critical_recall,
        route_accuracy=route_accuracy,
        unsupported_marked_supported_count=false_supported,
        results=results,
        promotion_gate_passed=(
            citation_accuracy >= 0.95
            and critical_recall == 1
            and false_supported == 0
        ),
    )


def export_phase7_assurance(
    evaluation: Phase7AssuranceEvaluation, path: str | Path
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(evaluation.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return target


def _evaluate_case(item: dict) -> Phase7AssuranceCaseResult:
    case_id = item["case_id"]
    claim_id = uuid5(NAMESPACE_URL, f"phase7-assurance/{case_id}/claim")
    evidence_id = uuid5(NAMESPACE_URL, f"phase7-assurance/{case_id}/evidence")
    cited_ids = {
        "approved": (evidence_id,),
        "missing": (),
        "outside": (
            uuid5(NAMESPACE_URL, f"phase7-assurance/{case_id}/outside"),
        ),
    }[item["citation_mode"]]
    evidence = Evidence(
        evidence_id=evidence_id,
        claim_id=claim_id,
        source_id=uuid5(NAMESPACE_URL, f"phase7-assurance/{case_id}/source"),
        passage=item["passage"],
        stance=EvidenceStance(item["evidence_stance"]),
        relevance_score=1,
    )
    assertion = StructuredReportAssertion(
        claim_id=claim_id,
        sentence=f"Structured fixture assertion for {case_id}.",
        cited_evidence_ids=cited_ids,
        asserted_stance=EvidenceStance(item["asserted_stance"]),
        required_phrases=tuple(item["required_phrases"]),
        critical=item["critical_assertion"],
    )
    packet = audit_structured_assertions(
        claim_id=claim_id,
        assertions=(assertion,),
        evidence=(evidence,),
        approved_evidence_ids=(evidence_id,),
    )
    decision = route_human_review(
        ReviewRoutingContext(
            claim_id=claim_id,
            risk_level=ReviewRiskLevel(item["risk"]),
            citation_assurance=packet,
            readiness_state=JudgmentReadinessState(item["readiness"]),
            provenance_state=ProvenanceRequirementState(item["provenance"]),
            policy_disagreement=item.get("policy_disagreement", False),
        )
    )
    expected_status = CitationAssuranceStatus(item["expected_status"])
    observed_status = packet.findings[0].status
    return Phase7AssuranceCaseResult(
        case_id=case_id,
        expected_status=expected_status,
        observed_status=observed_status,
        citation_correct=observed_status is expected_status,
        expected_review=item["expected_review"],
        observed_review=decision.review_required,
        route_correct=decision.review_required is item["expected_review"],
        critical_route_required=item["critical_route_required"],
    )
