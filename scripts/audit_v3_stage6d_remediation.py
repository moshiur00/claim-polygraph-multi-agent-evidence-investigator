"""Audit V3.6d using synthetic fixtures and exposed V3.6c cases only."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path
from uuid import uuid4

from claim_polygraph_ng.analysis.assisted_verification_construction import (
    AssistedConstructionEligibility,
    AssistedTemporalProviderProposal,
    classify_assisted_eligibility,
)
from claim_polygraph_ng.domain import DatePrecision, TemporalInstant
from claim_polygraph_ng.evaluation.v3_annotation import (
    load_replacement_calibration_workbook,
)
from claim_polygraph_ng.evaluation.v3_manifest import V3ConstructionGoldLabel

CALLABLE = {
    AssistedConstructionEligibility.NUMERICAL,
    AssistedConstructionEligibility.NUMERICAL_SCALAR,
    AssistedConstructionEligibility.NUMERICAL_RANGE,
    AssistedConstructionEligibility.NUMERICAL_CONVERSION,
    AssistedConstructionEligibility.TEMPORAL,
}


def _temporal_wire(value: str) -> TemporalInstant:
    passage = f"The event occurred on {value}."
    proposal = AssistedTemporalProviderProposal.model_validate(
        {
            "failed_construction_id": str(uuid4()),
            "claim_text_span": passage,
            "temporal_relation": "on",
            "reference_date": {"value": value, "precision": "day"},
            "claimed_interval": None,
            "requires_reference_date": False,
            "claimed_status": None,
            "temporal_bindings": [
                {
                    "evidence_id": str(uuid4()),
                    "start_char": 0,
                    "end_char": len(passage),
                    "quoted_text": passage,
                    "effective_interval": None,
                    "observed_status": None,
                    "retrospective": False,
                }
            ],
        }
    ).to_proposal()
    assert proposal.reference_date is not None
    return proposal.reference_date


def main() -> None:
    root = Path(__file__).parents[1]
    workbook_path = (
        root
        / "benchmarks/"
        "verification_construction_v3_stage6c_fresh_calibration_workbook_v1_APPROVED.json"
    )
    synthetic_path = (
        root / "benchmarks/verification_construction_v3_stage6b_synthetic_fixtures_v1.json"
    )
    workbook = load_replacement_calibration_workbook(workbook_path)
    synthetic = json.loads(synthetic_path.read_text(encoding="utf-8"))

    classifications = {
        case.case_id: classify_assisted_eligibility(case.claim_text)
        for case in workbook.cases
    }
    positives = [
        case
        for case in workbook.cases
        if case.annotation
        and case.annotation.gold_label
        in {
            V3ConstructionGoldLabel.DETERMINISTIC_CONSTRUCTIBLE,
            V3ConstructionGoldLabel.FALLBACK_ELIGIBLE,
        }
    ]
    negatives = [case for case in workbook.cases if case not in positives]
    positive_routing = sum(
        classifications[case.case_id] in CALLABLE for case in positives
    )
    negative_exclusions = sum(
        classifications[case.case_id]
        is AssistedConstructionEligibility.EXCLUDED_QUALITATIVE
        for case in negatives
    )
    synthetic_matches = {
        case["case_id"]: (
            classify_assisted_eligibility(case["claim"]).value
            == case["expected_eligibility"]
        )
        for case in synthetic["cases"]
    }
    temporal_checks = {
        "month_first_2024": _temporal_wire("June 6, 2024")
        == TemporalInstant(value=date(2024, 6, 6), precision=DatePrecision.DAY),
        "month_first_1913": _temporal_wire("December 23, 1913")
        == TemporalInstant(value=date(1913, 12, 23), precision=DatePrecision.DAY),
        "historical_day_first": _temporal_wire("24 April 1800")
        == TemporalInstant(value=date(1800, 4, 24), precision=DatePrecision.DAY),
    }
    gates = {
        "all_exposed_positive_cases_callable": positive_routing == len(positives),
        "all_exposed_negative_cases_excluded": negative_exclusions == len(negatives),
        "synthetic_eligibility_regressions": all(synthetic_matches.values()),
        "temporal_precision_normalization": all(temporal_checks.values()),
        "no_model_calls": True,
        "original_held_out_remained_sealed": True,
    }
    artifact = {
        "audit_id": "verification-construction-v3-stage6d-remediation-audit-v1",
        "status": "passed" if all(gates.values()) else "failed",
        "allowed_inputs": [
            "development fixtures",
            "synthetic fixtures",
            "now-exposed V3.6c workbook and diagnostics",
        ],
        "v36c_cases": len(workbook.cases),
        "v36c_positive_cases": len(positives),
        "v36c_positive_cases_callable": positive_routing,
        "v36c_negative_cases": len(negatives),
        "v36c_negative_cases_excluded": negative_exclusions,
        "eligibility_counts": dict(
            sorted(Counter(value.value for value in classifications.values()).items())
        ),
        "synthetic_checks": synthetic_matches,
        "temporal_checks": temporal_checks,
        "gates": gates,
        "controls": {
            "model_calls": 0,
            "estimated_cost_usd": 0.0,
            "original_held_out_cases_loaded": 0,
            "original_held_out_cases_exposed_to_model": 0,
            "v36c_results_used_for_tuning": True,
        },
    }
    destination = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage6d-remediation-audit-v1.json"
    )
    destination.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    if not all(gates.values()):
        failed = [name for name, passed in gates.items() if not passed]
        raise ValueError(f"V3.6d remediation audit failed: {failed}")
    print(destination.relative_to(root))
    print(
        f"status=passed callable={positive_routing}/{len(positives)} "
        "model_calls=0 held_out=0"
    )


if __name__ == "__main__":
    main()
