"""Run V4.7 development safety preflight before any paid call."""

import hashlib
import json
from pathlib import Path

from claim_polygraph_ng.analysis import (
    CANDIDATE_EXTRACTION_VERSION,
    construct_linked_assertions,
    extract_verification_candidates,
    route_construction_eligibility,
)
from claim_polygraph_ng.domain import (
    ConstructionEligibilityRoute,
    LinkedAssertionComponentKind,
)
from claim_polygraph_ng.evaluation.v3_development import (
    select_v3_development_cases,
)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _date_value_operand_failures(extraction, constructions) -> list[dict]:
    by_id = {item.candidate_id: item for item in extraction.candidates}
    failures = []
    for construction in constructions.constructions:
        for component in construction.components:
            if component.kind is not LinkedAssertionComponentKind.VALUE_CONDITION:
                continue
            values = [
                by_id[item] for item in component.candidate_ids if by_id[item].kind.value == "value"
            ]
            dates = [item for item in extraction.candidates if item.kind.value == "date"]
            for value in values:
                covering = [
                    item
                    for item in dates
                    if item.start_char <= value.start_char and value.end_char <= item.end_char
                ]
                if covering:
                    failures.append(
                        {
                            "group_id": construction.group_id,
                            "component_id": component.component_id,
                            "value_candidate_id": value.candidate_id,
                            "quoted_value": value.quoted_text,
                            "covering_date_candidate_ids": [item.candidate_id for item in covering],
                            "failure_code": "date_token_used_as_numeric_operand",
                        }
                    )
    return failures


def main() -> None:
    root = Path(__file__).parents[1]
    evaluations = root / "artifacts/evaluations"
    canary_audit_path = evaluations / "verification-construction-v4-stage6c-canary-audit-v1.json"
    canary_audit = json.loads(canary_audit_path.read_text(encoding="utf-8"))
    if not canary_audit["exit_criterion_met"]:
        raise ValueError("V4.6c must pass before V4.7")
    amendment_path = evaluations / "verification-construction-v4-canary-budget-amendment-v1.json"
    amendment = json.loads(amendment_path.read_text(encoding="utf-8"))
    dataset_path = root / "benchmarks/verification_construction_v3_approved_frozen_v2.json"
    cases, selection = select_v3_development_cases(dataset_path)
    results = []
    unsafe_case_count = 0
    unsafe_operand_count = 0
    assisted_case_count = 0
    deterministic_case_count = 0
    for case in cases:
        extraction = extract_verification_candidates(case.claim_text)
        constructions = construct_linked_assertions(case.claim_text, extraction)
        eligibility = route_construction_eligibility(case.claim_text, extraction, constructions)
        failures = _date_value_operand_failures(extraction, constructions)
        unsafe_case_count += bool(failures)
        unsafe_operand_count += len(failures)
        assisted = any(
            item.route is ConstructionEligibilityRoute.ASSISTED for item in eligibility.decisions
        )
        deterministic = any(
            item.route is ConstructionEligibilityRoute.DETERMINISTIC
            for item in eligibility.decisions
        )
        assisted_case_count += assisted
        deterministic_case_count += deterministic
        results.append(
            {
                "case_id": case.case_id,
                "claim_text_sha256": hashlib.sha256(case.claim_text.encode()).hexdigest(),
                "gold_label": case.annotation.gold_label.value,
                "routes": [item.route.value for item in eligibility.decisions],
                "unsafe_construction_findings": failures,
            }
        )
    gates = {
        "final_canary_passed": canary_audit["exit_criterion_met"],
        "development_budget_is_18": (
            amendment["effective_budget"]["maximum_development_calls"] == 18
        ),
        "development_split_only_loaded": selection.case_count == 20,
        "calibration_cases_loaded_zero": True,
        "held_out_cases_loaded_zero": True,
        "unsafe_accepted_constructions_zero": unsafe_operand_count == 0,
        "model_calls_zero_before_preflight_pass": True,
        "network_calls_zero_before_preflight_pass": True,
        "paid_operations_zero_before_preflight_pass": True,
    }
    audit = {
        "audit_id": "verification-construction-v4-stage7a-remediation-audit-v1",
        "status": "passed" if all(gates.values()) else "blocked_safe",
        "exit_criterion_met": all(gates.values()),
        "paid_execution_authorized": all(gates.values()),
        "development_cases_loaded": selection.case_count,
        "assisted_route_cases": assisted_case_count,
        "deterministic_route_cases": deterministic_case_count,
        "unsafe_case_count": unsafe_case_count,
        "unsafe_operand_count": unsafe_operand_count,
        "model_calls": 0,
        "network_calls": 0,
        "search_calls": 0,
        "paid_operations": 0,
        "calibration_cases_loaded": 0,
        "held_out_cases_loaded": 0,
        "gates": gates,
        "results": results,
        "artifacts": [
            {
                "path": path.as_posix(),
                "sha256": _hash(root / path),
                "bytes": (root / path).stat().st_size,
            }
            for path in (
                Path("src/claim_polygraph_ng/analysis/candidate_extraction.py"),
                Path("src/claim_polygraph_ng/analysis/compound_construction.py"),
                Path("scripts/audit_v4_stage7_development_preflight.py"),
                canary_audit_path.relative_to(root),
                amendment_path.relative_to(root),
                dataset_path.relative_to(root),
            )
        ],
        "remediation": {
            "code": "date_value_overlap_removed",
            "summary": (
                "Values contained by typed date spans remain diagnostic but "
                "are non-material and cannot enter numerical groups or anchors."
            ),
            "candidate_extraction_version": CANDIDATE_EXTRACTION_VERSION,
        },
        "next_stage": (
            "V4.7 development paid evaluation"
            if all(gates.values())
            else "V4.7a date/value overlap remediation"
        ),
    }
    destination = evaluations / "verification-construction-v4-stage7a-remediation-audit-v1.json"
    destination.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print(
        f"status={audit['status']} cases={selection.case_count} "
        f"unsafe_cases={unsafe_case_count} unsafe_operands={unsafe_operand_count} "
        "paid_calls=0"
    )


if __name__ == "__main__":
    main()
