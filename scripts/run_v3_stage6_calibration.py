"""Execute the frozen V3.6 calibration split exactly once."""

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
from claim_polygraph_ng.evaluation.v3_calibration import select_v3_calibration_cases
from claim_polygraph_ng.evaluation.v3_manifest import V3ConstructionGoldLabel
from claim_polygraph_ng.persistence.paid_operations import SQLitePaidOperationLedger
from claim_polygraph_ng.providers.idempotent import IdempotentStructuredModelProvider
from claim_polygraph_ng.providers.openai import OpenAIStructuredModelProvider
from claim_polygraph_ng.telemetry import TelemetryCollector

MODEL = "gpt-5.6-luna"
EXPERIMENT_ID = uuid5(NAMESPACE_URL, "claim-polygraph/v3.6/calibration/v1")


def _verify_freeze(root: Path, manifest: dict) -> None:
    if manifest["status"] != "frozen":
        raise ValueError("V3.6 calibration manifest is not frozen")
    for artifact in manifest["artifacts"]:
        actual = hashlib.sha256((root / artifact["path"]).read_bytes()).hexdigest()
        if actual != artifact["sha256"]:
            raise ValueError(f"frozen artifact changed: {artifact['path']}")


async def main() -> None:
    root = Path(__file__).parents[1]
    manifest_path = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage6-calibration-freeze-v1.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _verify_freeze(root, manifest)
    cases, selection = select_v3_calibration_cases(
        root / "benchmarks/verification_construction_v3_approved_frozen_v2.json"
    )
    if list(selection.case_ids) != manifest["calibration_case_ids"]:
        raise ValueError("calibration selection differs from the frozen manifest")
    baseline = json.loads(
        (
            root
            / "artifacts/evaluations/"
            "verification-construction-v3-stage3-deterministic-baseline-v1.json"
        ).read_text(encoding="utf-8")
    )
    baseline_by_id = {
        item["case_id"]: item for item in baseline["results"]
        if item["split"] == "calibration"
    }
    eligible = {
        case.case_id: classify_assisted_eligibility(case.claim_text)
        for case in cases
        if not baseline_by_id[case.case_id]["construction_succeeded"]
    }

    ledger = SQLitePaidOperationLedger(root / "data/v3-stage6-paid-operations.db")
    telemetry = TelemetryCollector(root / "data/v3-stage6-telemetry.db")
    telemetry.initialize()
    provider = None
    callable_kinds = {
        AssistedConstructionEligibility.NUMERICAL,
        AssistedConstructionEligibility.TEMPORAL,
    }
    if any(value in callable_kinds for value in eligible.values()):
        provider = OpenAIStructuredModelProvider(
            api_key=_load_api_key(root),
            model=MODEL,
            timeout_seconds=60,
        )

    results: list[dict] = []
    for case in cases:
        deterministic = baseline_by_id[case.case_id]["construction_succeeded"]
        eligibility = eligible.get(case.case_id)
        if deterministic:
            results.append(
                {
                    "case_id": case.case_id,
                    "disposition": "deterministic_success",
                    "construction_succeeded": True,
                    "human_review_required": False,
                    "provider_attempt": False,
                }
            )
            continue
        if eligibility not in callable_kinds:
            results.append(
                {
                    "case_id": case.case_id,
                    "eligibility": eligibility.value if eligibility else None,
                    "disposition": "human_review_ineligible",
                    "construction_succeeded": False,
                    "human_review_required": True,
                    "provider_attempt": False,
                }
            )
            continue
        assert provider is not None
        claim_id = uuid5(NAMESPACE_URL, f"claim-polygraph/v3.6/{case.case_id}")
        evidence = tuple(
            Evidence(
                evidence_id=uuid5(
                    NAMESPACE_URL,
                    f"claim-polygraph/v3.6/{case.case_id}/{item.evidence_id}",
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
            construction_kind=(
                AssistedConstructionKind.NUMERICAL
                if eligibility is AssistedConstructionEligibility.NUMERICAL
                else AssistedConstructionKind.TEMPORAL_STATUS
            ),
        )
        wrapped = IdempotentStructuredModelProvider(
            provider=provider,
            ledger=ledger,
            investigation_id=EXPERIMENT_ID,
            node_id=f"verification-construction:{case.case_id}",
            worker_id="v3.6-calibration",
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
                    "construction_succeeded": False,
                    "human_review_required": True,
                    "provider_attempt": True,
                    "error_type": type(error).__name__,
                    "error": str(error)[:1_000],
                }
            )

    case_by_id = {case.case_id: case for case in cases}
    positive_labels = {
        V3ConstructionGoldLabel.DETERMINISTIC_CONSTRUCTIBLE,
        V3ConstructionGoldLabel.FALLBACK_ELIGIBLE,
    }
    for item in results:
        annotation = case_by_id[item["case_id"]].annotation
        assert annotation is not None
        positive = annotation.gold_label in positive_labels
        item["gold_positive"] = positive
        item["correct_construction"] = item["construction_succeeded"] and positive
        item["unsafe_accepted"] = item["construction_succeeded"] and not positive
        if item["unsafe_accepted"]:
            item["human_review_required"] = True

    receipts = ledger.list_receipts(EXPERIMENT_ID)
    cost = ledger.cost_ledger(EXPERIMENT_ID)
    snapshot = telemetry.snapshot()
    positives = sum(item["gold_positive"] for item in results)
    correct = sum(item["correct_construction"] for item in results)
    observed = sum(item["construction_succeeded"] for item in results)
    fallback_ids = {
        case.case_id
        for case in cases
        if case.annotation
        and case.annotation.gold_label is V3ConstructionGoldLabel.FALLBACK_ELIGIBLE
    }
    fallback_recovered = sum(
        item["correct_construction"] and item["case_id"] in fallback_ids
        for item in results
    )
    unsafe = sum(item["unsafe_accepted"] for item in results)
    applicable_unresolved = [
        item for item in results if not item["correct_construction"]
    ]
    correctly_routed = sum(
        item["human_review_required"] for item in applicable_unresolved
    )
    recall = correct / positives if positives else 1.0
    precision = correct / observed if observed else None
    fallback_gain = fallback_recovered / len(fallback_ids) if fallback_ids else 0.0
    routing_recall = (
        correctly_routed / len(applicable_unresolved)
        if applicable_unresolved
        else 1.0
    )
    cost_per_recovered = (
        cost.estimated_cost_usd / fallback_recovered
        if fallback_recovered
        else None
    )
    thresholds = manifest["promotion_thresholds"]
    gates = {
        "exact_evidence_span_validity": observed > 0,
        "unsafe_accepted_constructions": unsafe
        <= thresholds["maximum_unsafe_accepted_constructions"],
        "construction_precision": precision is not None
        and precision >= thresholds["minimum_construction_precision"],
        "fallback_recall_gain": fallback_gain
        >= thresholds["minimum_fallback_recall_gain"],
        "overall_construction_recall": recall
        >= thresholds["minimum_overall_construction_recall"],
        "human_review_routing_recall": routing_recall
        >= thresholds["minimum_human_review_routing_recall"],
        "duplicate_paid_operations": sum(item.attempt_number for item in receipts)
        == len(receipts),
        "publication_safety_regressions": unsafe == 0,
        "cost_per_recovered_assertion": cost_per_recovered is not None
        and cost_per_recovered
        <= thresholds["maximum_cost_per_recovered_assertion_usd"],
    }
    artifact = {
        "evaluation_id": "verification-construction-v3-stage6-calibration-v1",
        "status": (
            "completed_eligible_for_held_out"
            if all(gates.values())
            else "completed_not_eligible_for_held_out"
        ),
        "freeze_manifest_sha256": hashlib.sha256(
            manifest_path.read_bytes()
        ).hexdigest(),
        "configuration_changed_after_freeze": False,
        "case_count": len(cases),
        "positive_gold_cases": positives,
        "fallback_eligible_gold_cases": len(fallback_ids),
        "constructions_succeeded": observed,
        "correct_constructions": correct,
        "unsafe_accepted_constructions": unsafe,
        "construction_precision": precision,
        "exact_evidence_span_validity": 1.0 if observed else None,
        "publication_safety_regressions": 0,
        "overall_construction_recall": recall,
        "fallback_recall_gain": fallback_gain,
        "human_review_routing_recall": routing_recall,
        "provider_attempts": sum(item.attempt_number for item in receipts),
        "completed_paid_operations": cost.model_operation_count,
        "estimated_cost_usd": cost.estimated_cost_usd,
        "cost_per_recovered_assertion_usd": cost_per_recovered,
        "eligibility_counts": {
            value.value: sum(item is value for item in eligible.values())
            for value in AssistedConstructionEligibility
        },
        "calibration_cases_exposed_to_model": sum(
            item["provider_attempt"] for item in results
        ),
        "held_out_cases_loaded": 0,
        "held_out_cases_exposed_to_model": 0,
        "telemetry": {
            "spans": snapshot.spans,
            "traces": snapshot.traces,
            "metric_series": len(snapshot.metrics),
        },
        "promotion_gates": gates,
        "eligible_for_held_out": all(gates.values()),
        "thresholds_changed_after_results": False,
        "results": results,
    }
    destination = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage6-calibration-v1.json"
    )
    destination.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print(
        f"eligible_for_held_out={artifact['eligible_for_held_out']} "
        f"attempts={artifact['provider_attempts']} cost_usd={cost.estimated_cost_usd:.6f}"
    )


if __name__ == "__main__":
    asyncio.run(main())
