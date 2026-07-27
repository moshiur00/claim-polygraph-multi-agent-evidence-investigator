"""Frozen 20-claim deterministic Phase 6 ablation evaluation."""

import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field

from claim_polygraph_ng.analysis import build_argument_ledger, enforce_judgment_policy
from claim_polygraph_ng.domain import (
    AtomicClaim,
    Evidence,
    EvidenceStance,
    Verdict,
    VerdictLabel,
)
from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.evaluation.phase6_manifest import Phase6BaselineAudit


class Phase6AblationCaseResult(DomainModel):
    case_id: str
    baseline_label: VerdictLabel
    full_policy_label: VerdictLabel
    expected_label: VerdictLabel
    baseline_correct: bool
    full_policy_correct: bool
    policy_changed: bool
    improved: bool
    regressed: bool
    argument_resolution: str
    challenger_finding_count: int = Field(ge=0)


class Phase6AblationEvaluation(DomainModel):
    evaluation_id: str = "phase6-stage6.8-frozen-ablation-v1"
    dataset_id: str
    dataset_version: int
    case_count: int
    baseline_accuracy: float = Field(ge=0, le=1)
    verification_only_accuracy: float = Field(ge=0, le=1)
    ledger_only_accuracy: float = Field(ge=0, le=1)
    full_policy_accuracy: float = Field(ge=0, le=1)
    improved_case_count: int = Field(ge=0)
    regressed_case_count: int = Field(ge=0)
    policy_override_count: int = Field(ge=0)
    citation_full_rate: float = Field(ge=0, le=1)
    numerical_fixture_accuracy: float = Field(ge=0, le=1)
    temporal_fixture_accuracy: float = Field(ge=0, le=1)
    results: tuple[Phase6AblationCaseResult, ...]
    promotion_gate_passed: bool
    limitations: tuple[str, ...]
    model_calls: int = 0
    network_calls: int = 0
    pdf_downloads: int = 0


def run_phase6_frozen_ablation(
    *,
    benchmark_path: str | Path,
    baseline_path: str | Path,
    numerical_evaluation_path: str | Path,
    temporal_evaluation_path: str | Path,
) -> Phase6AblationEvaluation:
    benchmark = json.loads(Path(benchmark_path).read_text(encoding="utf-8"))
    baseline = Phase6BaselineAudit.model_validate_json(
        Path(baseline_path).read_text(encoding="utf-8")
    )
    numerical = json.loads(Path(numerical_evaluation_path).read_text(encoding="utf-8"))
    temporal = json.loads(Path(temporal_evaluation_path).read_text(encoding="utf-8"))
    baseline_by_id = {item.case_id: item for item in baseline.cases}
    results = []
    for case in benchmark["cases"]:
        case_id = case["case_id"]
        baseline_case = baseline_by_id[case_id]
        claim_id = uuid5(NAMESPACE_URL, f"phase6-ablation/{case_id}/claim")
        claim = AtomicClaim(
            claim_id=claim_id,
            text=case["claim"],
            reference_date=case.get("reference_date"),
            geography=case.get("geography"),
            checkworthiness=1,
        )
        evidence = tuple(
            Evidence(
                evidence_id=uuid5(
                    NAMESPACE_URL, f"phase6-ablation/{case_id}/{item['annotation_id']}"
                ),
                claim_id=claim_id,
                source_id=uuid5(
                    NAMESPACE_URL,
                    f"phase6-ablation/{case_id}/source/{item['annotation_id']}",
                ),
                passage=item["excerpt"],
                stance=EvidenceStance(item["stance"]),
                relevance_score=1,
            )
            for item in case["candidate_evidence"]
        )
        ledger = build_argument_ledger(claim=claim, evidence=evidence)
        proposed = Verdict(
            claim_id=claim_id,
            label=VerdictLabel(baseline_case.observed_verdict),
            concise_explanation="Stored baseline label replayed for deterministic ablation.",
            detailed_reasoning=(
                "This evaluation-only verdict carries the stored baseline label and "
                "approved fixture evidence into the deterministic policy."
            ),
            decisive_evidence_ids=tuple(item.evidence_id for item in evidence),
        )
        enforced, trace = enforce_judgment_policy(proposed, ledger)
        expected = VerdictLabel(case["expected_verdict"])
        baseline_correct = proposed.label is expected
        full_correct = enforced.label is expected
        results.append(
            Phase6AblationCaseResult(
                case_id=case_id,
                baseline_label=proposed.label,
                full_policy_label=enforced.label,
                expected_label=expected,
                baseline_correct=baseline_correct,
                full_policy_correct=full_correct,
                policy_changed=trace.changed,
                improved=not baseline_correct and full_correct,
                regressed=baseline_correct and not full_correct,
                argument_resolution=ledger.arguments[0].resolution.value,
                challenger_finding_count=len(ledger.challenge_findings),
            )
        )
    baseline_accuracy = sum(item.baseline_correct for item in results) / len(results)
    full_accuracy = sum(item.full_policy_correct for item in results) / len(results)
    regressions = sum(item.regressed for item in results)
    return Phase6AblationEvaluation(
        dataset_id=benchmark["dataset_id"],
        dataset_version=benchmark["version"],
        case_count=len(results),
        baseline_accuracy=baseline_accuracy,
        verification_only_accuracy=baseline_accuracy,
        ledger_only_accuracy=baseline_accuracy,
        full_policy_accuracy=full_accuracy,
        improved_case_count=sum(item.improved for item in results),
        regressed_case_count=regressions,
        policy_override_count=sum(item.policy_changed for item in results),
        citation_full_rate=baseline.citation_full_rate,
        numerical_fixture_accuracy=numerical["accuracy"],
        temporal_fixture_accuracy=temporal["accuracy"],
        results=tuple(results),
        promotion_gate_passed=(
            regressions == 0
            and full_accuracy >= baseline_accuracy
            and baseline.citation_full_rate >= 0.95
            and numerical["accuracy"] >= 0.95
            and temporal["accuracy"] >= 0.95
        ),
        limitations=(
            "This is an offline deterministic replay, not a new retrieval or model run.",
            "Verification-only and ledger-only variants do not change labels by design.",
            "Reviewed expected labels are compared only after policy execution.",
        ),
    )


def export_phase6_ablation(
    evaluation: Phase6AblationEvaluation, path: str | Path
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(evaluation.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    return target
