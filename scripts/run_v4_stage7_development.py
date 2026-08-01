"""Run the receipt-protected V4.7 development evaluation once."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from claim_polygraph_ng.analysis import (
    extract_verification_candidates,
    route_construction_eligibility,
)
from claim_polygraph_ng.analysis.assisted_verification_construction import (
    AssistedConstructionEligibility,
    AssistedConstructionKind,
    AssistedConstructionRequest,
    classify_assisted_eligibility,
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
from claim_polygraph_ng.evaluation.v3_development import select_v3_development_cases
from claim_polygraph_ng.evaluation.v3_manifest import V3ConstructionGoldLabel
from claim_polygraph_ng.persistence.paid_operations import SQLitePaidOperationLedger
from claim_polygraph_ng.providers.idempotent import IdempotentStructuredModelProvider
from claim_polygraph_ng.providers.openai import OpenAIStructuredModelProvider
from claim_polygraph_ng.telemetry import TelemetryCollector

EXPERIMENT_ID = uuid5(NAMESPACE_URL, "claim-polygraph/v4.7/development/v1")
MODEL = "gpt-4o-mini"
MAXIMUM_CALLS = 18
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
    destination = evaluations / "verification-construction-v4-stage7-development-v1.json"
    if destination.exists():
        raise FileExistsError("V4.7 development evaluation has already been executed")

    preflight_path = evaluations / "verification-construction-v4-stage7a-remediation-audit-v1.json"
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    if not preflight["paid_execution_authorized"]:
        raise ValueError("V4.7a did not authorize paid development execution")
    amendment_path = evaluations / "verification-construction-v4-canary-budget-amendment-v1.json"
    amendment = json.loads(amendment_path.read_text(encoding="utf-8"))
    if amendment["effective_budget"]["maximum_development_calls"] != MAXIMUM_CALLS:
        raise ValueError("effective development-call budget is not 18")

    dataset_path = root / "benchmarks/verification_construction_v3_approved_frozen_v2.json"
    cases, selection = select_v3_development_cases(dataset_path)
    if selection.case_count != 20:
        raise ValueError("frozen development selection must contain 20 cases")

    ledger = SQLitePaidOperationLedger(root / "data/v4-stage7-paid-operations.db")
    if ledger.list_receipts(EXPERIMENT_ID):
        raise RuntimeError("V4.7 requires an empty paid-operation receipt identity")
    telemetry = TelemetryCollector(root / "data/v4-stage7-telemetry.db")
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

        eligibility = classify_assisted_eligibility(case.claim_text)
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
        claim_id = uuid5(NAMESPACE_URL, f"claim-polygraph/v4.7/{case.case_id}")
        evidence = tuple(
            Evidence(
                evidence_id=uuid5(
                    NAMESPACE_URL, f"claim-polygraph/v4.7/{case.case_id}/{item.evidence_id}"
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
            worker_id="v4.7-development",
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
        raise AssertionError("development-call ceiling exceeded")
    positives = sum(result["gold_positive"] for result in results)
    successes = sum(result["construction_succeeded"] for result in results)
    correct = sum(result["correct_construction"] for result in results)
    unsafe = sum(result["unsafe_accepted"] for result in results)
    unresolved = [result for result in results if not result["correct_construction"]]
    routing_recall = (
        sum(result["human_review_required"] for result in unresolved) / len(unresolved)
        if unresolved
        else 1.0
    )
    artifact = {
        "evaluation_id": "verification-construction-v4-stage7-development-v1",
        "status": "completed_safe" if unsafe == 0 else "completed_not_promotable",
        "model": MODEL,
        "case_count": len(results),
        "positive_gold_cases": positives,
        "constructions_succeeded": successes,
        "correct_constructions": correct,
        "unsafe_accepted_constructions": unsafe,
        "construction_precision": correct / successes if successes else None,
        "construction_recall": correct / positives if positives else 1.0,
        "human_review_routing_recall": routing_recall,
        "provider_attempts": cost.attempted_operation_count,
        "completed_paid_operations": cost.completed_operation_count,
        "failed_paid_operations": cost.failed_operation_count,
        "duplicate_paid_operations": sum(item.attempt_number for item in receipts) - len(receipts),
        "input_tokens": cost.input_tokens,
        "output_tokens": cost.output_tokens,
        "estimated_cost_usd": cost.estimated_cost_usd,
        "estimated_cost_upper_bound_usd": cost.estimated_cost_upper_bound_usd,
        "development_call_limit": MAXIMUM_CALLS,
        "development_calls_remaining": MAXIMUM_CALLS - cost.attempted_operation_count,
        "calibration_cases_loaded": 0,
        "held_out_cases_loaded": 0,
        "preflight_sha256": _sha256(preflight_path),
        "budget_amendment_sha256": _sha256(amendment_path),
        "dataset_sha256": _sha256(dataset_path),
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
