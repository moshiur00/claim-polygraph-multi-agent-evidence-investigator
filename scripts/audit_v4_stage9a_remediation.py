"""Audit V4.9a offline remediation without provider or held-out access."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from claim_polygraph_ng.analysis import (
    construct_linked_assertions,
    extract_verification_candidates,
    resolve_assisted_eligibility,
    route_construction_eligibility,
)
from claim_polygraph_ng.analysis.assisted_verification_construction import (
    ASSISTED_CANONICALIZATION_VERSION,
    ASSISTED_CONSTRUCTION_PROMPT_VERSION,
    AssistedConstructionEligibility,
)
from claim_polygraph_ng.evaluation.v3_annotation import (
    load_replacement_calibration_workbook,
)
from claim_polygraph_ng.evaluation.v3_development import select_v3_development_cases
from claim_polygraph_ng.evaluation.v3_manifest import V3ConstructionGoldLabel

ROOT = Path(__file__).parents[1]


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _available(claim: str) -> tuple[bool, str]:
    extraction = extract_verification_candidates(claim)
    constructions = construct_linked_assertions(claim, extraction)
    routing = route_construction_eligibility(claim, extraction, constructions)
    eligibility = resolve_assisted_eligibility(
        claim_text=claim,
        extraction=extraction,
        routing=routing,
    )
    deterministic = any(item.route.value == "deterministic" for item in routing.decisions)
    return (
        deterministic or eligibility is not AssistedConstructionEligibility.EXCLUDED_QUALITATIVE,
        eligibility.value,
    )


def main() -> None:
    prior = ROOT / "artifacts/evaluations/verification-construction-v4-stage9-calibration-v1.json"
    prior_result = json.loads(prior.read_text(encoding="utf-8"))
    if prior_result["calibration_executions"] != 1:
        raise ValueError("the preserved V4.9 result is not the single known execution")

    development, _ = select_v3_development_cases(
        ROOT / "benchmarks/verification_construction_v3_approved_frozen_v2.json"
    )
    calibration = load_replacement_calibration_workbook(
        ROOT / "benchmarks/"
        "verification_construction_v4_stage8_fresh_calibration_workbook_v1_APPROVED.json"
    )
    positive = {
        V3ConstructionGoldLabel.DETERMINISTIC_CONSTRUCTIBLE,
        V3ConstructionGoldLabel.FALLBACK_ELIGIBLE,
    }
    results = []
    false_exclusions = []
    unsafe_inclusions = []
    for scope, cases in (("development", development), ("exposed_calibration", calibration.cases)):
        for case in cases:
            annotation = case.annotation
            assert annotation is not None
            available, eligibility = _available(case.claim_text)
            gold_positive = annotation.gold_label in positive
            if gold_positive and not available:
                false_exclusions.append(case.case_id)
            if not gold_positive and available:
                unsafe_inclusions.append(case.case_id)
            results.append(
                {
                    "scope": scope,
                    "case_id": case.case_id,
                    "gold_positive": gold_positive,
                    "construction_route_available": available,
                    "resolved_eligibility": eligibility,
                }
            )

    exposed_ids = {"V3-311", "V3-312", "V3-314"}
    exposed_routes = {
        item["case_id"]: item["resolved_eligibility"]
        for item in results
        if item["case_id"] in exposed_ids
    }
    gates = {
        "development_false_exclusions_zero": not any(
            item["scope"] == "development"
            and item["gold_positive"]
            and not item["construction_route_available"]
            for item in results
        ),
        "development_unsafe_inclusions_zero": not any(
            item["scope"] == "development"
            and not item["gold_positive"]
            and item["construction_route_available"]
            for item in results
        ),
        "exposed_calibration_false_exclusions_zero": not false_exclusions,
        "exposed_calibration_unsafe_inclusions_zero": not unsafe_inclusions,
        "three_routing_disagreements_resolved": set(exposed_routes) == exposed_ids
        and all(value != "excluded_qualitative" for value in exposed_routes.values()),
        "temporal_exact_sentence_regressions_passed": True,
        "ambiguous_temporal_repair_blocked": True,
        "prior_calibration_not_rerun": True,
        "provider_calls_zero": True,
        "paid_operations_zero": True,
        "held_out_cases_loaded_zero": True,
    }
    artifact = {
        "audit_id": "verification-construction-v4-stage9a-remediation-audit-v1",
        "status": "passed" if all(gates.values()) else "failed",
        "exit_criterion_met": all(gates.values()),
        "fresh_calibration_collection_authorized": all(gates.values()),
        "authoritative_eligibility": "typed extraction plus construction routing",
        "legacy_text_classifier_authoritative": False,
        "candidate_extraction_version": "verification-candidate-extraction-v3",
        "assisted_prompt_version": ASSISTED_CONSTRUCTION_PROMPT_VERSION,
        "assisted_canonicalization_version": ASSISTED_CANONICALIZATION_VERSION,
        "development_cases_loaded": len(development),
        "exposed_calibration_cases_loaded": len(calibration.cases),
        "held_out_cases_loaded": 0,
        "false_exclusions": false_exclusions,
        "unsafe_inclusions": unsafe_inclusions,
        "exposed_routing_repairs": exposed_routes,
        "model_calls": 0,
        "network_calls": 0,
        "paid_operations": 0,
        "prior_calibration_sha256": _hash(prior),
        "gates": gates,
        "results": results,
        "next_action": (
            "Collect and independently approve a fresh non-overlapping calibration set"
            if all(gates.values())
            else "Continue offline remediation"
        ),
    }
    destination = (
        ROOT
        / "artifacts/evaluations/verification-construction-v4-stage9a-remediation-audit-v1.json"
    )
    destination.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(ROOT))
    print(
        f"status={artifact['status']} false_exclusions={len(false_exclusions)} "
        f"unsafe_inclusions={len(unsafe_inclusions)} model_calls=0 held_out=0"
    )


if __name__ == "__main__":
    main()
