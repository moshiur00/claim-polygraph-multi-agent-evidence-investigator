"""Frozen 20-claim comparison of the authoritative baseline and LangGraph wrapper."""

import hashlib
import json
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field, model_validator

from claim_polygraph_ng.application import DurableFixtureLangGraphWorkflow
from claim_polygraph_ng.domain import (
    FixtureGraphRequest,
    ReviewDecision,
    ReviewDecisionKind,
    VerdictLabel,
)
from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.evaluation.phase6_manifest import load_phase6_baseline


class Phase7FrozenCaseResult(DomainModel):
    case_id: str = Field(pattern=r"^CPNG-[0-9]{3}$")
    authoritative_verdict: VerdictLabel
    wrapper_verdict: VerdictLabel
    verdict_equivalent: bool
    artifact_preserved: bool
    citation_fully_supported: bool
    review_required: bool
    review_routed: bool
    duplicate_operations: int = Field(ge=0)
    wrapper_latency_seconds: float = Field(ge=0)


class Phase7FrozenEvaluation(DomainModel):
    evaluation_id: str = "phase7-stage7.8-frozen-comparison-v1"
    dataset_id: str
    dataset_version: int
    case_count: int = Field(ge=1)
    results: tuple[Phase7FrozenCaseResult, ...]
    verdict_equivalence_rate: float = Field(ge=0, le=1)
    authoritative_reviewed_label_accuracy: float = Field(ge=0, le=1)
    wrapper_reviewed_label_accuracy: float = Field(ge=0, le=1)
    artifact_preservation_rate: float = Field(ge=0, le=1)
    required_review_recall: float = Field(ge=0, le=1)
    citation_accuracy: float = Field(ge=0, le=1)
    duplicate_paid_operations: int = Field(ge=0)
    duplicate_deterministic_operations: int = Field(ge=0)
    authoritative_median_latency_seconds: float = Field(ge=0)
    wrapper_median_latency_seconds: float = Field(ge=0)
    deterministic_latency_overhead_ratio: float = Field(ge=0)
    verdict_regressions: int = Field(ge=0)
    artifact_losses: int = Field(ge=0)
    promotion_gate_passed: bool
    model_calls: int = 0
    search_calls: int = 0
    network_calls: int = 0
    pdf_downloads: int = 0
    estimated_cost_usd: float = 0.0
    limitations: tuple[str, ...]

    @model_validator(mode="after")
    def validate_aggregates(self) -> "Phase7FrozenEvaluation":
        if self.case_count != len(self.results):
            raise ValueError("case count does not match results")
        expected = {
            "verdict_equivalence_rate": sum(item.verdict_equivalent for item in self.results)
            / self.case_count,
            "artifact_preservation_rate": sum(item.artifact_preserved for item in self.results)
            / self.case_count,
            "citation_accuracy": sum(item.citation_fully_supported for item in self.results)
            / self.case_count,
        }
        required = [item for item in self.results if item.review_required]
        expected["required_review_recall"] = (
            sum(item.review_routed for item in required) / len(required) if required else 1.0
        )
        for field, value in expected.items():
            if abs(getattr(self, field) - value) > 1e-9:
                raise ValueError(f"{field} does not match results")
        return self


def evaluate_phase7_frozen(
    benchmark_path: str | Path,
    baseline_path: str | Path,
) -> Phase7FrozenEvaluation:
    """Replay approved packets through the zero-cost durable wrapper."""
    benchmark_file = Path(benchmark_path)
    benchmark = json.loads(benchmark_file.read_text(encoding="utf-8"))
    baseline = load_phase6_baseline(baseline_path)
    if (
        benchmark["dataset_id"] != baseline.dataset_id
        or benchmark["version"] != baseline.dataset_version
    ):
        raise ValueError("benchmark and authoritative baseline identity mismatch")
    cases = {item["case_id"]: item for item in benchmark["cases"]}
    if set(cases) != {item.case_id for item in baseline.cases}:
        raise ValueError("benchmark and baseline case sets differ")

    results: list[Phase7FrozenCaseResult] = []
    with TemporaryDirectory(prefix="claim-polygraph-stage7.8-") as temporary:
        checkpoint = Path(temporary) / "langgraph.db"
        with DurableFixtureLangGraphWorkflow(checkpoint, enabled=True) as workflow:
            for authoritative in baseline.cases:
                case = cases[authoritative.case_id]
                evidence_ids = tuple(
                    uuid5(
                        NAMESPACE_URL,
                        f"claim-polygraph/{authoritative.case_id}/{item['annotation_id']}",
                    )
                    for item in case["candidate_evidence"]
                )
                packet_hash_before = _case_hash(case)
                request = FixtureGraphRequest(
                    graph_run_id=uuid5(
                        NAMESPACE_URL,
                        f"claim-polygraph/phase7.8/{authoritative.case_id}/graph",
                    ),
                    claim_text=case["claim"],
                    approved_evidence_ids=evidence_ids,
                    authoritative_verdict=VerdictLabel(authoritative.observed_verdict),
                    review_required=case["ai_review"]["requires_human_review"],
                    review_reason=(
                        "The frozen reviewed packet requires human confirmation."
                        if case["ai_review"]["requires_human_review"]
                        else None
                    ),
                )
                started_at = perf_counter()
                snapshot = workflow.start(request)
                review_routed = snapshot.status.value == "review_required"
                if review_routed:
                    snapshot = workflow.resume(
                        str(request.graph_run_id),
                        ReviewDecision(
                            decision_id=uuid5(
                                NAMESPACE_URL,
                                (f"claim-polygraph/phase7.8/{authoritative.case_id}/decision"),
                            ),
                            kind=ReviewDecisionKind.APPROVE,
                            reviewer_identity="Stage 7.8 frozen replay",
                            rationale=(
                                "Replay the authoritative reviewed verdict without "
                                "changing benchmark truth."
                            ),
                        ),
                    )
                wrapper_latency = perf_counter() - started_at
                duplicates = sum(max(0, count - 1) for count in snapshot.operation_counts.values())
                results.append(
                    Phase7FrozenCaseResult(
                        case_id=authoritative.case_id,
                        authoritative_verdict=VerdictLabel(authoritative.observed_verdict),
                        wrapper_verdict=snapshot.final_verdict,
                        verdict_equivalent=(
                            snapshot.final_verdict.value == authoritative.observed_verdict
                        ),
                        artifact_preserved=(
                            _case_hash(case) == packet_hash_before
                            and snapshot.approved_evidence_ids == evidence_ids
                        ),
                        citation_fully_supported=(authoritative.citation_fully_supported),
                        review_required=case["ai_review"]["requires_human_review"],
                        review_routed=review_routed,
                        duplicate_operations=duplicates,
                        wrapper_latency_seconds=round(wrapper_latency, 6),
                    )
                )

    case_count = len(results)
    authoritative_median = median(item.duration_seconds for item in baseline.cases)
    wrapper_median = median(item.wrapper_latency_seconds for item in results)
    overhead = wrapper_median / authoritative_median if authoritative_median else 0.0
    verdict_rate = sum(item.verdict_equivalent for item in results) / case_count
    authoritative_accuracy = sum(item.verdict_matches for item in baseline.cases) / case_count
    wrapper_accuracy = (
        sum(
            result.wrapper_verdict.value == authoritative.expected_verdict
            for result, authoritative in zip(results, baseline.cases, strict=True)
        )
        / case_count
    )
    artifact_rate = sum(item.artifact_preserved for item in results) / case_count
    required = [item for item in results if item.review_required]
    review_recall = sum(item.review_routed for item in required) / len(required)
    citation_accuracy = sum(item.citation_fully_supported for item in results) / case_count
    duplicate_operations = sum(item.duplicate_operations for item in results)
    regressions = sum(not item.verdict_equivalent for item in results)
    losses = sum(not item.artifact_preserved for item in results)
    gate = all(
        (
            regressions == 0,
            losses == 0,
            review_recall == 1.0,
            citation_accuracy >= 0.95,
            duplicate_operations == 0,
            overhead <= 0.2,
        )
    )
    return Phase7FrozenEvaluation(
        dataset_id=baseline.dataset_id,
        dataset_version=baseline.dataset_version,
        case_count=case_count,
        results=tuple(results),
        verdict_equivalence_rate=verdict_rate,
        authoritative_reviewed_label_accuracy=authoritative_accuracy,
        wrapper_reviewed_label_accuracy=wrapper_accuracy,
        artifact_preservation_rate=artifact_rate,
        required_review_recall=review_recall,
        citation_accuracy=citation_accuracy,
        duplicate_paid_operations=0,
        duplicate_deterministic_operations=duplicate_operations,
        authoritative_median_latency_seconds=round(authoritative_median, 6),
        wrapper_median_latency_seconds=round(wrapper_median, 6),
        deterministic_latency_overhead_ratio=round(overhead, 6),
        verdict_regressions=regressions,
        artifact_losses=losses,
        promotion_gate_passed=gate,
        limitations=(
            "The wrapper replays saved authoritative verdicts and approved evidence "
            "identities; it does not regenerate verdicts.",
            "The frozen aggregate baseline stores citation-full flags rather than "
            "sentence text, so citation accuracy measures preservation of its 20 "
            "authoritative sentence-audit outcomes.",
            "Artifact preservation hashes each reviewed benchmark packet and verifies "
            "that every approved evidence identity reaches the wrapper unchanged; "
            "the wrapper does not copy or rewrite authoritative repository artifacts.",
            "Latency is a local deterministic wrapper measurement divided by the "
            "saved authoritative median; it is not a provider-performance benchmark.",
            "All 20 frozen packets require review, so this replay measures required-"
            "review recall but cannot measure over-routing specificity.",
            "The authoritative baseline and wrapper both retain the two documented "
            "reviewed-label mismatches, CPNG-006 and CPNG-019; equivalence means the "
            "wrapper introduced no new regression, not that baseline accuracy is 100%.",
        ),
    )


def export_phase7_frozen(evaluation: Phase7FrozenEvaluation, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evaluation.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    return output


def _case_hash(case: dict[str, object]) -> str:
    payload = json.dumps(case, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()
