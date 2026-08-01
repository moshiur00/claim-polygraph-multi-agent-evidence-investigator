"""Build the offline V3.8 adjudication workbook and ablation artifacts."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path


ATTEMPT_REVIEW = {
    "V3-001": (
        "revise",
        "The proposal binds only the Julian-year value and omits the decisive "
        "calendar-year and tropical-year qualification evidence.",
    ),
    "V3-011": (
        "accept",
        "The proposal captures the 100 percent electricity assertion and binds "
        "the passage containing the material almost-100-percent qualification.",
    ),
    "V3-012": (
        "accept",
        "The proposal captures the total-energy percentage and binds the passage "
        "showing about 85 percent plus continuing fossil-fuel use.",
    ),
    "V3-024": (
        "confirm_safe_failure",
        "No proposal passed validation because the proposed scalar was not "
        "explicitly bound to the approved evidence.",
    ),
    "V3-031": (
        "confirm_safe_failure",
        "No proposal passed schema validation because the provider emitted an "
        "invalid zero scale.",
    ),
    "V3-039": (
        "revise",
        "The construction captures the count but its claim span omits the 2020 "
        "reference and the four-infection scope that are material to the claim.",
    ),
    "V3-060": (
        "revise",
        "The construction captures the 40 degree threshold but omits the "
        "two-hour duration and discard condition in this compound rule.",
    ),
}

EXCLUSION_ANALYSIS = {
    "V3-003": ("false_exclusion", "exact_count_with_universal_quantifier"),
    "V3-006": ("false_exclusion", "ordinal_ranking_with_reference_year"),
    "V3-010": ("correct_exclusion", "qualitative_causal_prevention_claim"),
    "V3-013": ("false_exclusion", "zero_use_or_absence_status"),
    "V3-020": ("false_exclusion", "comparative_value_expressed_as_relative_stature"),
    "V3-021": ("false_exclusion", "accuracy_claim_grounded_by_comparative_measurement"),
    "V3-025": ("correct_exclusion", "global_superlative_requires_open_world_comparison"),
    "V3-030": ("correct_exclusion", "overbroad_causal_generalization"),
    "V3-032": ("false_exclusion", "comparison_between_two_explicit_durations"),
    "V3-033": ("false_exclusion", "multiplicative_comparison_between_values"),
    "V3-040": ("false_exclusion", "paired_percentage_projection_with_dates"),
    "V3-052": ("correct_exclusion", "reference_date_not_supported_by_evidence"),
    "V3-058": ("false_exclusion", "dated_scalar_percentage"),
}


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    root = Path(__file__).parents[1]
    result_path = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage7-held-out-v1.json"
    )
    audit_path = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage7-held-out-audit-v1.json"
    )
    dataset_path = (
        root / "benchmarks/verification_construction_v3_approved_frozen_v2.json"
    )
    result = json.loads(result_path.read_text(encoding="utf-8"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    cases = {
        case["case_id"]: case
        for case in dataset["cases"]
        if case["split"] == "held_out"
    }
    attempts = [item for item in result["results"] if item["provider_attempt"]]
    if len(attempts) != 7 or set(ATTEMPT_REVIEW) != {
        item["case_id"] for item in attempts
    }:
        raise ValueError("V3.8 attempt set differs from the frozen held-out result")

    workbook_cases = []
    for item in attempts:
        case = cases[item["case_id"]]
        recommendation, rationale = ATTEMPT_REVIEW[item["case_id"]]
        workbook_cases.append(
            {
                "case_id": item["case_id"],
                "claim_text": case["claim_text"],
                "gold_annotation": case["annotation"],
                "approved_evidence": case["evidence"],
                "held_out_disposition": item["disposition"],
                "validated_proposal": item.get("proposal"),
                "safe_failure": {
                    "error_type": item.get("error_type"),
                    "error": item.get("error"),
                }
                if not item["construction_succeeded"]
                else None,
                "prefilled_adjudication": {
                    "annotator_identity": "Md Moshiur Rahman",
                    "annotated_on": date.today().isoformat(),
                    "decision": recommendation,
                    "rationale": rationale,
                    "checked_claim_span": False,
                    "checked_evidence_bindings": False,
                    "checked_material_operands": False,
                    "checked_expected_state_compatibility": False,
                    "checked_fail_closed_behavior": False,
                    "notes": [],
                },
                "distinct_approval": {
                    "approver_identity": "Md Rashedul Islam",
                    "approved_on": date.today().isoformat(),
                    "decision": "pending",
                    "checked_adjudication": False,
                    "checked_rationale": False,
                    "checked_safety_effect": False,
                    "notes": [],
                },
            }
        )
    workbook = {
        "workbook_id": "verification-construction-v3-stage8-adjudication-workbook-v1",
        "schema_version": 1,
        "source_result_sha256": _hash(result_path),
        "model_calls": 0,
        "held_out_reruns": 0,
        "annotator_identity_prefill": "Md Moshiur Rahman",
        "distinct_approver_identity_prefill": "Md Rashedul Islam",
        "instructions": [
            "Review every prefilled decision against the frozen claim, approved evidence, gold annotation, and persisted provider result.",
            "Change any decision or rationale that you do not independently accept.",
            "Complete all five annotator checks.",
            "The distinct approver must independently review each decision and complete all three approval checks.",
            "Do not rerun or modify the held-out evaluation.",
        ],
        "allowed_adjudication_decisions": [
            "accept",
            "revise",
            "reject_unsafe",
            "confirm_safe_failure",
        ],
        "cases": workbook_cases,
    }
    workbook_path = (
        root
        / "benchmarks/"
        "verification_construction_v3_stage8_adjudication_workbook_v1.json"
    )
    workbook_path.write_text(json.dumps(workbook, indent=2) + "\n", encoding="utf-8")

    exclusions = []
    for item in result["results"]:
        if item.get("eligibility") != "excluded_qualitative":
            continue
        classification, gap = EXCLUSION_ANALYSIS[item["case_id"]]
        case = cases[item["case_id"]]
        exclusions.append(
            {
                "case_id": item["case_id"],
                "claim_text": case["claim_text"],
                "gold_label": case["annotation"]["gold_label"],
                "classification": classification,
                "eligibility_gap": gap,
                "safety_effect": (
                    "constructible_case_routed_to_human_review"
                    if classification == "false_exclusion"
                    else "non_constructible_case_correctly_routed_to_human_review"
                ),
            }
        )
    exclusion_path = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage8-eligibility-analysis-v1.json"
    )
    exclusion_artifact = {
        "analysis_id": "verification-construction-v3-stage8-eligibility-analysis-v1",
        "source_result_sha256": _hash(result_path),
        "model_calls": 0,
        "held_out_reruns": 0,
        "excluded_case_count": len(exclusions),
        "false_exclusions": sum(
            item["classification"] == "false_exclusion" for item in exclusions
        ),
        "correct_exclusions": sum(
            item["classification"] == "correct_exclusion" for item in exclusions
        ),
        "false_inclusions": 0,
        "analysis": exclusions,
        "conclusion": (
            "Eligibility is conservative and safe but materially under-covers "
            "constructible comparative, ranked, paired-value, zero-status, and "
            "dated-scalar claims."
        ),
    }
    exclusion_path.write_text(
        json.dumps(exclusion_artifact, indent=2) + "\n", encoding="utf-8"
    )

    ablation_path = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage8-ablation-v1.json"
    )
    ablation = {
        "evaluation_id": "verification-construction-v3-stage8-ablation-v1",
        "source_result_sha256": _hash(result_path),
        "source_audit_sha256": _hash(audit_path),
        "model_calls": 0,
        "held_out_reruns": 0,
        "case_count": result["case_count"],
        "positive_gold_cases": result["positive_gold_cases"],
        "variants": {
            "deterministic_only": {
                "correct_constructions": result["baseline_correct_constructions"],
                "construction_recall": result["baseline_construction_recall"],
                "paid_calls": 0,
                "estimated_cost_usd": 0.0,
            },
            "deterministic_plus_assisted": {
                "correct_constructions": result["correct_constructions"],
                "construction_recall": result["overall_construction_recall"],
                "construction_precision": result["construction_precision"],
                "recall_gain": result["incremental_recall_gain"],
                "paid_calls": result["provider_attempts"],
                "estimated_cost_usd": result["estimated_cost_usd"],
                "cost_per_recovered_assertion_usd": result[
                    "cost_per_recovered_assertion_usd"
                ],
                "unsafe_accepted_constructions": result[
                    "unsafe_accepted_constructions"
                ],
                "human_review_routing_recall": result[
                    "human_review_routing_recall"
                ],
            },
        },
        "attempt_level": {
            "eligible_attempts": result["provider_attempts"],
            "validated_constructions": result["constructions_succeeded"],
            "validated_rate": (
                result["constructions_succeeded"] / result["provider_attempts"]
            ),
            "safe_failures": result["provider_attempts"]
            - result["constructions_succeeded"],
        },
        "promotion_assessment": {
            "passed_gates": [
                name
                for name, passed in result["promotion_gates"].items()
                if passed
            ],
            "failed_gates": audit["failed_gates"],
            "promote": False,
            "reason": (
                "Assistance improved recall by 31.25 percentage points with "
                "perfect observed precision and no safety regression, but total "
                "held-out recall remained below the frozen 75 percent gate."
            ),
        },
    }
    ablation_path.write_text(json.dumps(ablation, indent=2) + "\n", encoding="utf-8")
    print(workbook_path.relative_to(root))
    print(exclusion_path.relative_to(root))
    print(ablation_path.relative_to(root))
    print("attempts=7 false_exclusions=9 held_out_reruns=0 model_calls=0")


if __name__ == "__main__":
    main()
