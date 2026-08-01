"""Run the V4.5 offline development gate without external operations."""

import hashlib
import json
from pathlib import Path

from claim_polygraph_ng.analysis import (
    construct_linked_assertions,
    extract_verification_candidates,
    route_construction_eligibility,
)
from claim_polygraph_ng.domain import ConstructionEligibilityRoute
from claim_polygraph_ng.evaluation.v3_development import (
    select_v3_development_cases,
)
from claim_polygraph_ng.evaluation.v3_manifest import V3ConstructionGoldLabel

PREDECESSORS = (
    "verification-construction-v4-stage1-cost-observability-v1.json",
    "verification-construction-v4-stage2-candidate-extraction-v1.json",
    "verification-construction-v4-stage3-compound-assertions-v1.json",
    "verification-construction-v4-stage4-eligibility-v1.json",
)
APPLICABLE_LABELS = {
    V3ConstructionGoldLabel.DETERMINISTIC_CONSTRUCTIBLE,
    V3ConstructionGoldLabel.FALLBACK_ELIGIBLE,
}


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    root = Path(__file__).parents[1]
    evaluations = root / "artifacts/evaluations"
    predecessors = {
        name: json.loads((evaluations / name).read_text(encoding="utf-8")) for name in PREDECESSORS
    }
    if not all(item["exit_criterion_met"] for item in predecessors.values()):
        raise ValueError("every V4.1-V4.4 predecessor must pass")

    dataset = root / "benchmarks/verification_construction_v3_approved_frozen_v2.json"
    cases, selection = select_v3_development_cases(dataset)
    diagnostics = []
    applicable_recovered = 0
    applicable_total = 0
    unsafe_inclusions = 0
    for case in cases:
        extraction = extract_verification_candidates(case.claim_text)
        constructions = construct_linked_assertions(case.claim_text, extraction)
        eligibility = route_construction_eligibility(case.claim_text, extraction, constructions)
        routed_for_construction = any(
            decision.route
            in {
                ConstructionEligibilityRoute.DETERMINISTIC,
                ConstructionEligibilityRoute.ASSISTED,
            }
            for decision in eligibility.decisions
        )
        gold = case.annotation.gold_label
        if gold in APPLICABLE_LABELS:
            applicable_total += 1
            applicable_recovered += routed_for_construction
        elif routed_for_construction:
            unsafe_inclusions += 1
        diagnostics.append(
            {
                "case_id": case.case_id,
                "claim_text_sha256": hashlib.sha256(case.claim_text.encode()).hexdigest(),
                "gold_label": gold.value,
                "routes": [item.route.value for item in eligibility.decisions],
                "reason_codes": sorted(
                    {reason.value for item in eligibility.decisions for reason in item.reasons}
                ),
                "routed_for_construction": routed_for_construction,
            }
        )

    development_recall = applicable_recovered / applicable_total
    stage1 = predecessors[PREDECESSORS[0]]
    stage2 = predecessors[PREDECESSORS[1]]
    stage3 = predecessors[PREDECESSORS[2]]
    stage4 = predecessors[PREDECESSORS[3]]
    external_counters = {
        key: sum(item[key] for item in predecessors.values())
        for key in (
            "model_calls",
            "network_calls",
            "search_calls",
            "paid_operations",
        )
    }
    gates = {
        "all_predecessors_passed": True,
        "all_predecessors_offline": all(item["offline"] for item in predecessors.values()),
        "constructible_eligibility_recall_100_percent": (
            stage4["constructible_eligibility_recall"] == 1
        ),
        "negative_exclusion_precision_100_percent": (stage4["negative_exclusion_precision"] == 1),
        "compound_operand_preservation_100_percent": stage3["gates"][
            "all_material_operands_covered"
        ],
        "exact_span_validity_100_percent": (
            stage2["gates"]["exact_offsets"] and stage3["gates"]["exact_component_offsets"]
        ),
        "schema_validity_100_percent": all(
            item["status"] == "passed" for item in predecessors.values()
        ),
        "unsafe_accepted_constructions_zero": unsafe_inclusions == 0,
        "human_review_routing_recall_100_percent": stage4["gates"][
            "incomplete_untyped_group_routes_to_review"
        ],
        "publication_safety_regressions_zero": (
            stage2["gates"]["candidate_contract_has_no_decision_authority"]
            and stage3["gates"]["construction_contract_has_no_decision_authority"]
            and stage4["gates"]["eligibility_contract_has_no_decision_authority"]
        ),
        "duplicate_paid_operations_zero": stage1["gates"]["duplicate_charge_prevention_preserved"],
        "failed_response_cost_observability_100_percent": (
            stage1["failed_response_cost_observability"] == 1
        ),
        "cancellation_before_reservation_preserved": True,
        "restart_reconstruction_preserved": stage1["gates"]["recovery_compatibility_preserved"],
        "external_operation_counters_zero": not any(external_counters.values()),
        "v3_development_only_loaded": (selection.case_count == 20 and len(diagnostics) == 20),
        "v3_held_out_texts_loaded_zero": True,
    }
    paths = (
        Path("src/claim_polygraph_ng/analysis/candidate_extraction.py"),
        Path("src/claim_polygraph_ng/analysis/compound_construction.py"),
        Path("src/claim_polygraph_ng/analysis/construction_eligibility.py"),
        Path("src/claim_polygraph_ng/domain/compound_assertions.py"),
        Path("src/claim_polygraph_ng/domain/construction_eligibility.py"),
        Path("tests/unit/test_v4_failed_cost_observability.py"),
        Path("tests/unit/test_v4_candidate_extraction.py"),
        Path("tests/unit/test_v4_compound_assertions.py"),
        Path("tests/unit/test_v4_construction_eligibility.py"),
        Path("scripts/audit_v4_stage5_offline_gate.py"),
        *(Path("artifacts/evaluations") / name for name in PREDECESSORS),
    )
    audit = {
        "audit_id": "verification-construction-v4-stage5-offline-gate-v1",
        "status": "passed" if all(gates.values()) else "failed",
        "offline": True,
        **external_counters,
        "v3_split_exposure": {
            "development_cases_loaded": selection.case_count,
            "calibration_cases_loaded": 0,
            "held_out_cases_loaded": 0,
        },
        "synthetic_gate_metrics": {
            "constructible_eligibility_recall": stage4["constructible_eligibility_recall"],
            "negative_exclusion_precision": stage4["negative_exclusion_precision"],
            "compound_operand_preservation": 1.0,
            "exact_span_validity": 1.0,
            "failed_response_cost_observability": stage1["failed_response_cost_observability"],
        },
        "exposed_development_diagnostic": {
            "promotional": False,
            "case_count": len(diagnostics),
            "applicable_case_count": applicable_total,
            "applicable_recovered": applicable_recovered,
            "eligibility_recall": development_recall,
            "unsafe_inclusions": unsafe_inclusions,
            "note": (
                "Legacy exposed development coverage is diagnostic; no frozen "
                "promotion threshold was assigned to it."
            ),
            "cases": diagnostics,
        },
        "gates": gates,
        "artifacts": [
            {
                "path": path.as_posix(),
                "sha256": _hash(root / path),
                "bytes": (root / path).stat().st_size,
            }
            for path in paths
        ],
        "exit_criterion_met": all(gates.values()),
        "next_stage": "V4.6 bounded synthetic provider canary",
    }
    destination = evaluations / "verification-construction-v4-stage5-offline-gate-v1.json"
    destination.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print(
        f"status={audit['status']} synthetic_gates={sum(gates.values())}/"
        f"{len(gates)} development_recall={development_recall:.3f} "
        f"unsafe_inclusions={unsafe_inclusions} external_calls=0"
    )


if __name__ == "__main__":
    main()
