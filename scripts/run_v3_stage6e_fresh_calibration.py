"""Execute the approved V3.6e fresh calibration exactly once."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from run_v3_stage5_development import _load_api_key

from claim_polygraph_ng.analysis.assisted_verification_construction import (
    AssistedConstructionEligibility,
    AssistedConstructionKind,
    AssistedConstructionRequest,
    classify_assisted_eligibility,
)
from claim_polygraph_ng.analysis.bounded_assisted_construction import (
    BoundedAssistedConstructionService,
)
from claim_polygraph_ng.domain import Evidence, EvidenceStance
from claim_polygraph_ng.evaluation.v3_annotation import (
    load_replacement_calibration_workbook,
)
from claim_polygraph_ng.evaluation.v3_deterministic_baseline import _evaluate_case
from claim_polygraph_ng.evaluation.v3_manifest import V3ConstructionGoldLabel
from claim_polygraph_ng.persistence.paid_operations import SQLitePaidOperationLedger
from claim_polygraph_ng.providers.idempotent import IdempotentStructuredModelProvider
from claim_polygraph_ng.providers.openai import OpenAIStructuredModelProvider
from claim_polygraph_ng.telemetry import TelemetryCollector

MODEL = "gpt-5.6-luna"
EXPERIMENT_ID = uuid5(
    NAMESPACE_URL, "claim-polygraph/v3.6e/replacement-calibration/v1"
)


def _verify_freeze(root: Path, manifest: dict) -> None:
    if manifest["status"] != "frozen" or manifest["execution_limit"] != 1:
        raise ValueError("V3.6e fresh manifest is not a one-run freeze")
    for artifact in manifest["artifacts"]:
        actual = hashlib.sha256((root / artifact["path"]).read_bytes()).hexdigest()
        if actual != artifact["sha256"]:
            raise ValueError(f"frozen artifact changed: {artifact['path']}")


def _kind(eligibility: AssistedConstructionEligibility) -> AssistedConstructionKind:
    if eligibility is AssistedConstructionEligibility.NUMERICAL:
        return AssistedConstructionKind.NUMERICAL
    if eligibility in {
        AssistedConstructionEligibility.NUMERICAL_SCALAR,
        AssistedConstructionEligibility.NUMERICAL_RANGE,
        AssistedConstructionEligibility.NUMERICAL_CONVERSION,
    }:
        return AssistedConstructionKind.NUMERICAL_SCALAR
    return AssistedConstructionKind.TEMPORAL_STATUS


async def main() -> None:
    root = Path(__file__).parents[1]
    result_path = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage6e-fresh-calibration-v1.json"
    )
    if result_path.exists():
        raise FileExistsError("fresh calibration has already been executed")
    freeze_path = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage6e-fresh-calibration-freeze-v1.json"
    )
    manifest = json.loads(freeze_path.read_text(encoding="utf-8"))
    _verify_freeze(root, manifest)
    workbook_path = (
        root
        / "benchmarks/"
        "verification_construction_v3_stage6e_fresh_calibration_workbook_v1_APPROVED.json"
    )
    workbook = load_replacement_calibration_workbook(workbook_path)
    if [case.case_id for case in workbook.cases] != manifest["case_ids"]:
        raise ValueError("approved case selection differs from frozen manifest")

    deterministic = {case.case_id: _evaluate_case(case) for case in workbook.cases}
    callable_eligibility = {
        AssistedConstructionEligibility.NUMERICAL,
        AssistedConstructionEligibility.NUMERICAL_SCALAR,
        AssistedConstructionEligibility.NUMERICAL_RANGE,
        AssistedConstructionEligibility.NUMERICAL_CONVERSION,
        AssistedConstructionEligibility.TEMPORAL,
    }
    eligibilities = {
        case.case_id: classify_assisted_eligibility(case.claim_text)
        for case in workbook.cases
        if not deterministic[case.case_id].construction_succeeded
    }
    ledger = SQLitePaidOperationLedger(root / "data/v3-stage6e-paid-operations.db")
    if ledger.list_receipts(EXPERIMENT_ID):
        raise RuntimeError("V3.6e paid-operation ledger is not empty before first run")
    telemetry = TelemetryCollector(root / "data/v3-stage6e-telemetry.db")
    telemetry.initialize()
    provider = OpenAIStructuredModelProvider(
        api_key=_load_api_key(root), model=MODEL, timeout_seconds=60
    )

    results: list[dict] = []
    for case in workbook.cases:
        baseline = deterministic[case.case_id]
        if baseline.construction_succeeded:
            results.append(
                {
                    "case_id": case.case_id,
                    "disposition": "deterministic_success",
                    "baseline_success": True,
                    "construction_succeeded": True,
                    "human_review_required": False,
                    "provider_attempt": False,
                }
            )
            continue
        eligibility = eligibilities[case.case_id]
        if eligibility not in callable_eligibility:
            results.append(
                {
                    "case_id": case.case_id,
                    "eligibility": eligibility.value,
                    "disposition": "human_review_ineligible",
                    "baseline_success": False,
                    "construction_succeeded": False,
                    "human_review_required": True,
                    "provider_attempt": False,
                }
            )
            continue
        claim_id = uuid5(NAMESPACE_URL, f"claim-polygraph/v3.6e/{case.case_id}")
        evidence = tuple(
            Evidence(
                evidence_id=uuid5(
                    NAMESPACE_URL,
                    f"claim-polygraph/v3.6e/{case.case_id}/{item.evidence_id}",
                ),
                claim_id=claim_id,
                source_id=uuid5(NAMESPACE_URL, item.url),
                passage=item.passage,
                stance=EvidenceStance.CONTEXT,
                relevance_score=1,
            )
            for item in case.evidence
        )
        request = AssistedConstructionRequest(
            claim_id=claim_id,
            claim_text=case.claim_text,
            failed_construction_id=uuid5(
                NAMESPACE_URL, f"{claim_id}/failed-construction"
            ),
            approved_evidence_ids=tuple(item.evidence_id for item in evidence),
            construction_kind=_kind(eligibility),
        )
        wrapped = IdempotentStructuredModelProvider(
            provider=provider,
            ledger=ledger,
            investigation_id=EXPERIMENT_ID,
            node_id=f"verification-construction:{case.case_id}",
            worker_id="v3.6e-replacement-calibration",
        )
        service = BoundedAssistedConstructionService(
            provider=wrapped,
            ledger=ledger,
            investigation_id=EXPERIMENT_ID,
            telemetry=telemetry,
        )
        try:
            proposal = await service.propose(request=request, evidence=evidence)
            results.append(
                {
                    "case_id": case.case_id,
                    "eligibility": eligibility.value,
                    "disposition": "validated_assisted_proposal",
                    "baseline_success": False,
                    "construction_succeeded": True,
                    "human_review_required": False,
                    "provider_attempt": True,
                    "proposal": proposal.model_dump(mode="json"),
                }
            )
        except Exception as error:
            results.append(
                {
                    "case_id": case.case_id,
                    "eligibility": eligibility.value,
                    "disposition": "human_review_safe_failure",
                    "baseline_success": False,
                    "construction_succeeded": False,
                    "human_review_required": True,
                    "provider_attempt": True,
                    "error_type": type(error).__name__,
                    "error": str(error)[:1_000],
                }
            )

    cases = {case.case_id: case for case in workbook.cases}
    positive_labels = {
        V3ConstructionGoldLabel.DETERMINISTIC_CONSTRUCTIBLE,
        V3ConstructionGoldLabel.FALLBACK_ELIGIBLE,
    }
    for item in results:
        annotation = cases[item["case_id"]].annotation
        assert annotation is not None
        positive = annotation.gold_label in positive_labels
        item["gold_positive"] = positive
        item["correct_construction"] = item["construction_succeeded"] and positive
        item["unsafe_accepted"] = item["construction_succeeded"] and not positive
        if item["unsafe_accepted"]:
            item["human_review_required"] = True

    receipts = ledger.list_receipts(EXPERIMENT_ID)
    cost = ledger.cost_ledger(EXPERIMENT_ID)
    positives = sum(item["gold_positive"] for item in results)
    baseline_correct = sum(
        item["baseline_success"] and item["gold_positive"] for item in results
    )
    correct = sum(item["correct_construction"] for item in results)
    observed = sum(item["construction_succeeded"] for item in results)
    newly_recovered = correct - baseline_correct
    unsafe = sum(item["unsafe_accepted"] for item in results)
    unresolved = [item for item in results if not item["correct_construction"]]
    routing_recall = (
        sum(item["human_review_required"] for item in unresolved) / len(unresolved)
        if unresolved
        else 1.0
    )
    precision = correct / observed if observed else None
    recall = correct / positives if positives else 1.0
    baseline_recall = baseline_correct / positives if positives else 1.0
    gain = recall - baseline_recall
    cost_per_recovered = (
        cost.estimated_cost_usd / newly_recovered if newly_recovered else None
    )
    thresholds = manifest["promotion_thresholds"]
    duplicate_operations = sum(item.attempt_number for item in receipts) - len(receipts)
    gates = {
        "exact_evidence_span_validity": observed > 0,
        "unsafe_accepted_constructions": unsafe
        <= thresholds["maximum_unsafe_accepted_constructions"],
        "construction_precision": precision is not None
        and precision >= thresholds["minimum_construction_precision"],
        "incremental_recall_gain": gain
        >= thresholds["minimum_incremental_recall_gain"],
        "overall_construction_recall": recall
        >= thresholds["minimum_overall_construction_recall"],
        "human_review_routing_recall": routing_recall
        >= thresholds["minimum_human_review_routing_recall"],
        "duplicate_paid_operations": duplicate_operations
        <= thresholds["maximum_duplicate_paid_operations"],
        "publication_safety_regressions": unsafe == 0,
        "cost_per_recovered_assertion": cost_per_recovered is not None
        and cost_per_recovered
        <= thresholds["maximum_cost_per_recovered_assertion_usd"],
    }
    artifact = {
        "evaluation_id": (
            "verification-construction-v3-stage6e-fresh-calibration-v1"
        ),
        "status": (
            "completed_eligible_for_held_out"
            if all(gates.values())
            else "completed_not_eligible_for_held_out"
        ),
        "freeze_manifest_sha256": hashlib.sha256(freeze_path.read_bytes()).hexdigest(),
        "configuration_changed_after_freeze": False,
        "calibration_executions": 1,
        "case_count": len(results),
        "positive_gold_cases": positives,
        "baseline_correct_constructions": baseline_correct,
        "baseline_construction_recall": baseline_recall,
        "constructions_succeeded": observed,
        "correct_constructions": correct,
        "newly_recovered_assertions": newly_recovered,
        "unsafe_accepted_constructions": unsafe,
        "construction_precision": precision,
        "exact_evidence_span_validity": 1.0 if observed else None,
        "overall_construction_recall": recall,
        "incremental_recall_gain": gain,
        "human_review_routing_recall": routing_recall,
        "provider_attempts": sum(item.attempt_number for item in receipts),
        "completed_paid_operations": cost.model_operation_count,
        "duplicate_paid_operations": duplicate_operations,
        "estimated_cost_usd": cost.estimated_cost_usd,
        "cost_per_recovered_assertion_usd": cost_per_recovered,
        "eligibility_counts": {
            value.value: sum(item is value for item in eligibilities.values())
            for value in AssistedConstructionEligibility
        },
        "fresh_calibration_cases_exposed_to_model": sum(
            item["provider_attempt"] for item in results
        ),
        "original_held_out_cases_loaded": 0,
        "original_held_out_cases_exposed_to_model": 0,
        "promotion_gates": gates,
        "eligible_for_held_out": all(gates.values()),
        "thresholds_changed_after_results": False,
        "results": results,
    }
    result_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(result_path.relative_to(root))
    print(
        f"eligible_for_held_out={artifact['eligible_for_held_out']} "
        f"attempts={artifact['provider_attempts']} "
        f"cost_usd={cost.estimated_cost_usd:.6f}"
    )


if __name__ == "__main__":
    asyncio.run(main())


