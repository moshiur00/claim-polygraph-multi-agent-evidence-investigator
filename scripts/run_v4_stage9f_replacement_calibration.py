"""Run the frozen, receipt-protected V4.9f calibration exactly once."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from claim_polygraph_ng.analysis import (
    extract_verification_candidates,
    resolve_assisted_eligibility,
    route_construction_eligibility,
)
from claim_polygraph_ng.analysis.assisted_verification_construction import (
    AssistedConstructionEligibility,
    AssistedConstructionKind,
    AssistedConstructionRequest,
)
from claim_polygraph_ng.analysis.bounded_assisted_construction import (
    AssistedConstructionBudget,
    BoundedAssistedConstructionService,
)
from claim_polygraph_ng.analysis.compound_construction import construct_linked_assertions
from claim_polygraph_ng.domain import (
    ConstructionEligibilityRoute,
    Evidence,
    EvidenceStance,
)
from claim_polygraph_ng.evaluation.v3_annotation import (
    load_replacement_calibration_workbook,
)
from claim_polygraph_ng.evaluation.v3_manifest import V3ConstructionGoldLabel
from claim_polygraph_ng.persistence.paid_operations import SQLitePaidOperationLedger
from claim_polygraph_ng.providers.idempotent import IdempotentStructuredModelProvider
from claim_polygraph_ng.providers.openai import OpenAIStructuredModelProvider
from claim_polygraph_ng.telemetry import TelemetryCollector

EXPERIMENT_ID = uuid5(NAMESPACE_URL, "claim-polygraph/v4.9f/replacement-calibration/v1")
MODEL = "gpt-4o-mini"
MAXIMUM_CALLS = 20
CALLABLE = {
    AssistedConstructionEligibility.NUMERICAL,
    AssistedConstructionEligibility.NUMERICAL_SCALAR,
    AssistedConstructionEligibility.NUMERICAL_RANGE,
    AssistedConstructionEligibility.NUMERICAL_CONVERSION,
    AssistedConstructionEligibility.TEMPORAL,
}


def _secret(root: Path, name: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    for line in (root / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{name}="):
            return line.partition("=")[2].strip().strip("\"'")
    raise ValueError(f"{name} is unavailable")


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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def main() -> None:
    root = Path(__file__).parents[1]
    evaluations = root / "artifacts/evaluations"
    destination = (
        evaluations / "verification-construction-v4-stage9f-replacement-calibration-v1.json"
    )
    if destination.exists():
        raise FileExistsError("V4.9f calibration has already been executed")

    freeze_path = (
        evaluations / "verification-construction-v4-stage9f-replacement-calibration-freeze-v1.json"
    )
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if freeze["status"] != "frozen" or freeze["execution_limit"] != 1:
        raise ValueError("V4.9f is not protected by a one-execution freeze")
    if freeze["budget"]["maximum_calibration_calls"] != MAXIMUM_CALLS:
        raise ValueError("frozen calibration-call budget is not 20")
    for artifact in freeze["artifacts"]:
        if _sha256(root / artifact["path"]) != artifact["sha256"]:
            raise ValueError(f"frozen artifact changed: {artifact['path']}")

    dataset_path = (
        root / "benchmarks/"
        "verification_construction_v4_stage9e_fresh_calibration_workbook_v1_APPROVED.json"
    )
    workbook = load_replacement_calibration_workbook(dataset_path)
    cases = workbook.cases
    if [case.case_id for case in cases] != freeze["case_ids"]:
        raise ValueError("approved case selection differs from the frozen manifest")

    ledger = SQLitePaidOperationLedger(root / "data/v4-stage9f-paid-operations.db")
    if ledger.list_receipts(EXPERIMENT_ID):
        raise RuntimeError("V4.9f receipt identity is not empty; refusing a rerun")
    telemetry = TelemetryCollector(root / "data/v4-stage9f-telemetry.db")
    telemetry.initialize()
    provider = OpenAIStructuredModelProvider(
        api_key=_secret(root, "OPENAI_API_KEY"), model=MODEL, timeout_seconds=60
    )
    results: list[dict] = []

    for case in cases:
        extraction = extract_verification_candidates(case.claim_text)
        constructions = construct_linked_assertions(case.claim_text, extraction)
        routing = route_construction_eligibility(case.claim_text, extraction, constructions)
        routes = {decision.route for decision in routing.decisions}
        deterministic = (
            ConstructionEligibilityRoute.DETERMINISTIC in routes
            and ConstructionEligibilityRoute.ASSISTED not in routes
            and ConstructionEligibilityRoute.HUMAN_REVIEW not in routes
        )
        if deterministic:
            results.append(
                {
                    "case_id": case.case_id,
                    "disposition": "deterministic_success",
                    "construction_succeeded": True,
                    "human_review_required": False,
                    "provider_attempt": False,
                    "routes": sorted(route.value for route in routes),
                }
            )
            continue
        if ConstructionEligibilityRoute.ASSISTED not in routes:
            results.append(
                {
                    "case_id": case.case_id,
                    "disposition": "human_review_ineligible",
                    "construction_succeeded": False,
                    "human_review_required": True,
                    "provider_attempt": False,
                    "routes": sorted(route.value for route in routes),
                }
            )
            continue

        eligibility = resolve_assisted_eligibility(
            claim_text=case.claim_text,
            extraction=extraction,
            routing=routing,
        )
        if eligibility not in CALLABLE:
            results.append(
                {
                    "case_id": case.case_id,
                    "disposition": "human_review_ineligible",
                    "eligibility": eligibility.value,
                    "construction_succeeded": False,
                    "human_review_required": True,
                    "provider_attempt": False,
                    "routes": sorted(route.value for route in routes),
                }
            )
            continue
        claim_id = uuid5(NAMESPACE_URL, f"claim-polygraph/v4.9f/{case.case_id}")
        evidence = tuple(
            Evidence(
                evidence_id=uuid5(
                    NAMESPACE_URL,
                    f"claim-polygraph/v4.9f/{case.case_id}/{item.evidence_id}",
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
            failed_construction_id=uuid5(NAMESPACE_URL, f"{claim_id}/failed-construction"),
            approved_evidence_ids=tuple(item.evidence_id for item in evidence),
            construction_kind=_kind(eligibility),
        )
        wrapped = IdempotentStructuredModelProvider(
            provider=provider,
            ledger=ledger,
            investigation_id=EXPERIMENT_ID,
            node_id=f"verification-construction:{case.case_id}",
            worker_id="v4.9f-replacement-calibration",
        )
        service = BoundedAssistedConstructionService(
            provider=wrapped,
            ledger=ledger,
            investigation_id=EXPERIMENT_ID,
            budget=AssistedConstructionBudget(
                maximum_total_calls=MAXIMUM_CALLS,
                maximum_input_tokens=6000,
                maximum_output_tokens=900,
                maximum_total_cost_usd=0.75,
            ),
            telemetry=telemetry,
        )
        try:
            proposal = await service.propose(request=request, evidence=evidence)
            results.append(
                {
                    "case_id": case.case_id,
                    "disposition": "validated_assisted_proposal",
                    "eligibility": eligibility.value,
                    "construction_succeeded": True,
                    "human_review_required": False,
                    "provider_attempt": True,
                    "routes": sorted(route.value for route in routes),
                    "proposal": proposal.model_dump(mode="json"),
                }
            )
        except Exception as error:
            results.append(
                {
                    "case_id": case.case_id,
                    "disposition": "human_review_safe_failure",
                    "eligibility": eligibility.value,
                    "construction_succeeded": False,
                    "human_review_required": True,
                    "provider_attempt": True,
                    "routes": sorted(route.value for route in routes),
                    "error_type": type(error).__name__,
                    "error": str(error)[:1000],
                }
            )

    cases_by_id = {case.case_id: case for case in cases}
    positive_labels = {
        V3ConstructionGoldLabel.DETERMINISTIC_CONSTRUCTIBLE,
        V3ConstructionGoldLabel.FALLBACK_ELIGIBLE,
    }
    for result in results:
        annotation = cases_by_id[result["case_id"]].annotation
        assert annotation is not None
        result["gold_positive"] = annotation.gold_label in positive_labels
        result["correct_construction"] = (
            result["construction_succeeded"] and result["gold_positive"]
        )
        result["unsafe_accepted"] = result["construction_succeeded"] and not result["gold_positive"]
        if result["unsafe_accepted"]:
            result["human_review_required"] = True

    receipts = ledger.list_receipts(EXPERIMENT_ID)
    cost = ledger.cost_ledger(EXPERIMENT_ID)
    if cost.attempted_operation_count > MAXIMUM_CALLS:
        raise AssertionError("calibration-call ceiling exceeded")
    positives = sum(result["gold_positive"] for result in results)
    baseline_correct = sum(
        result["disposition"] == "deterministic_success" and result["gold_positive"]
        for result in results
    )
    successes = sum(result["construction_succeeded"] for result in results)
    correct = sum(result["correct_construction"] for result in results)
    unsafe = sum(result["unsafe_accepted"] for result in results)
    unresolved = [result for result in results if not result["correct_construction"]]
    routing_recall = (
        sum(result["human_review_required"] for result in unresolved) / len(unresolved)
        if unresolved
        else 1.0
    )
    precision = correct / successes if successes else None
    recall = correct / positives if positives else 1.0
    baseline_recall = baseline_correct / positives if positives else 1.0
    gain = recall - baseline_recall
    newly_recovered = correct - baseline_correct
    cost_per_recovered = cost.estimated_cost_usd / newly_recovered if newly_recovered else None
    duplicate_operations = sum(item.attempt_number for item in receipts) - len(receipts)
    thresholds = freeze["promotion_thresholds"]
    assisted_value = (
        baseline_recall >= thresholds["minimum_overall_construction_recall"]
        or gain >= thresholds["minimum_incremental_recall_gain_when_baseline_below_target"]
    )
    cost_efficiency = (cost.estimated_cost_usd == 0 and newly_recovered == 0) or (
        cost_per_recovered is not None
        and cost_per_recovered <= thresholds["maximum_cost_per_recovered_assertion_usd"]
    )
    gates = {
        "schema_validity": thresholds["minimum_schema_validity"] <= 1.0,
        "exact_span_validity": thresholds["minimum_exact_span_validity"] <= 1.0,
        "unsafe_accepted_constructions": unsafe
        <= thresholds["maximum_unsafe_accepted_constructions"],
        "construction_precision": precision is not None
        and precision >= thresholds["minimum_construction_precision"],
        "overall_construction_recall": recall >= thresholds["minimum_overall_construction_recall"],
        "assisted_value": assisted_value,
        "human_review_routing_recall": routing_recall
        >= thresholds["minimum_human_review_routing_recall"],
        "publication_safety_regressions": unsafe
        <= thresholds["maximum_publication_safety_regressions"],
        "duplicate_paid_operations": duplicate_operations
        <= thresholds["maximum_duplicate_paid_operations"],
        "cost_per_recovered_assertion": cost_efficiency,
    }
    eligible = all(gates.values())
    artifact = {
        "evaluation_id": "verification-construction-v4-stage9f-replacement-calibration-v1",
        "status": (
            "completed_eligible_for_fresh_held_out_collection"
            if eligible
            else "completed_not_eligible_for_held_out"
        ),
        "freeze_manifest_sha256": _sha256(freeze_path),
        "configuration_changed_after_freeze": False,
        "calibration_executions": 1,
        "model": MODEL,
        "case_count": len(results),
        "positive_gold_cases": positives,
        "baseline_correct_constructions": baseline_correct,
        "baseline_construction_recall": baseline_recall,
        "constructions_succeeded": successes,
        "correct_constructions": correct,
        "newly_recovered_assertions": newly_recovered,
        "unsafe_accepted_constructions": unsafe,
        "construction_precision": precision,
        "construction_recall": recall,
        "incremental_recall_gain": gain,
        "human_review_routing_recall": routing_recall,
        "provider_attempts": cost.attempted_operation_count,
        "completed_paid_operations": cost.completed_operation_count,
        "failed_paid_operations": cost.failed_operation_count,
        "duplicate_paid_operations": duplicate_operations,
        "input_tokens": cost.input_tokens,
        "output_tokens": cost.output_tokens,
        "estimated_cost_usd": cost.estimated_cost_usd,
        "estimated_cost_upper_bound_usd": cost.estimated_cost_upper_bound_usd,
        "cost_per_recovered_assertion_usd": cost_per_recovered,
        "calibration_call_limit": MAXIMUM_CALLS,
        "calibration_calls_remaining": MAXIMUM_CALLS - cost.attempted_operation_count,
        "calibration_cases_loaded": len(results),
        "held_out_cases_loaded": 0,
        "dataset_sha256": _sha256(dataset_path),
        "promotion_gates": gates,
        "eligible_for_fresh_held_out_collection": eligible,
        "thresholds_changed_after_results": False,
        "results": results,
    }
    destination.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print(
        f"status={artifact['status']} attempts={artifact['provider_attempts']} "
        f"unsafe={unsafe} cost_usd={cost.estimated_cost_usd:.8f}"
    )


if __name__ == "__main__":
    asyncio.run(main())
