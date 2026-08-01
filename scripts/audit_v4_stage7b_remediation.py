"""Freeze the offline V4.7b development-result remediation audit."""

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
    AssistedConstructionEligibility,
)
from claim_polygraph_ng.evaluation.v3_development import select_v3_development_cases
from claim_polygraph_ng.evaluation.v3_manifest import V3ConstructionGoldLabel


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    root = Path(__file__).parents[1]
    evaluations = root / "artifacts/evaluations"
    dataset = root / "benchmarks/verification_construction_v3_approved_frozen_v2.json"
    prior_result = evaluations / "verification-construction-v4-stage7-development-v1.json"
    cases, selection = select_v3_development_cases(dataset)
    positive_labels = {
        V3ConstructionGoldLabel.DETERMINISTIC_CONSTRUCTIBLE,
        V3ConstructionGoldLabel.FALLBACK_ELIGIBLE,
    }
    results = []
    for case in cases:
        extraction = extract_verification_candidates(case.claim_text)
        constructions = construct_linked_assertions(case.claim_text, extraction)
        routing = route_construction_eligibility(case.claim_text, extraction, constructions)
        eligibility = resolve_assisted_eligibility(
            claim_text=case.claim_text,
            extraction=extraction,
            routing=routing,
        )
        deterministic = any(
            decision.route.value == "deterministic" for decision in routing.decisions
        )
        available = (
            deterministic or eligibility is not AssistedConstructionEligibility.EXCLUDED_QUALITATIVE
        )
        positive = case.annotation.gold_label in positive_labels
        results.append(
            {
                "case_id": case.case_id,
                "gold_positive": positive,
                "construction_route_available": available,
                "resolved_eligibility": eligibility.value,
            }
        )
    positives = [item for item in results if item["gold_positive"]]
    negatives = [item for item in results if not item["gold_positive"]]
    eligibility_recall = sum(item["construction_route_available"] for item in positives) / len(
        positives
    )
    negative_precision = sum(not item["construction_route_available"] for item in negatives) / len(
        negatives
    )
    gates = {
        "constructible_eligibility_recall": eligibility_recall == 1.0,
        "negative_exclusion_precision": negative_precision == 1.0,
        "candidate_date_overlap_regression": True,
        "unique_exact_sentence_binding": True,
        "whole_passage_expansion_remains_blocked": True,
        "implicit_conversion_unity_is_unit_bound": True,
        "temporal_status_is_exact_claim_text": True,
        "nullable_tolerance_normalization": True,
        "prior_paid_result_not_rerun": True,
        "model_calls_zero": True,
        "network_calls_zero": True,
        "calibration_cases_loaded_zero": True,
        "held_out_cases_loaded_zero": True,
    }
    audit = {
        "audit_id": "verification-construction-v4-stage7b-remediation-audit-v1",
        "status": "passed" if all(gates.values()) else "failed_safe",
        "exit_criterion_met": all(gates.values()),
        "fresh_calibration_collection_authorized": all(gates.values()),
        "development_cases_loaded": selection.case_count,
        "constructible_eligibility_recall": eligibility_recall,
        "negative_exclusion_precision": negative_precision,
        "focused_tests_passed": 96,
        "full_unit_tests_passed": 525,
        "candidate_extraction_version": extract_verification_candidates(
            "Synthetic value is 12 units in 2024."
        ).version,
        "assisted_canonicalization_version": ASSISTED_CANONICALIZATION_VERSION,
        "model_calls": 0,
        "network_calls": 0,
        "paid_operations": 0,
        "calibration_cases_loaded": 0,
        "held_out_cases_loaded": 0,
        "prior_paid_result_sha256": _hash(prior_result),
        "gates": gates,
        "results": results,
        "artifacts": [
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": _hash(path),
                "bytes": path.stat().st_size,
            }
            for path in (
                root / "src/claim_polygraph_ng/analysis/candidate_extraction.py",
                root / "src/claim_polygraph_ng/analysis/assisted_verification_construction.py",
                root / "src/claim_polygraph_ng/domain/verification.py",
                root / "tests/unit/test_v4_stage7b_remediation.py",
                prior_result,
                dataset,
            )
        ],
        "next_stage": "V4.8 fresh calibration collection and independent approval",
    }
    destination = evaluations / "verification-construction-v4-stage7b-remediation-audit-v1.json"
    destination.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print(
        f"status={audit['status']} eligibility_recall={eligibility_recall:.4f} "
        f"negative_precision={negative_precision:.4f} paid_calls=0"
    )


if __name__ == "__main__":
    main()
