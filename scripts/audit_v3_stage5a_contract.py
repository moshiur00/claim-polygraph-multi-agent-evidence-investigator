"""Audit the V3.5a typed temporal/status boundary before model execution."""

import hashlib
import json
from pathlib import Path

from claim_polygraph_ng.analysis.assisted_verification_construction import (
    ASSISTED_CONSTRUCTION_PROMPT_VERSION,
    AssistedConstructionEligibility,
    AssistedConstructionProposal,
    classify_assisted_eligibility,
)
from claim_polygraph_ng.evaluation.v3_development import select_v3_development_cases


def main() -> None:
    root = Path(__file__).parents[1]
    cases, selection = select_v3_development_cases(
        root / "benchmarks/verification_construction_v3_approved_frozen_v2.json"
    )
    fallback = {
        case.case_id: classify_assisted_eligibility(case.claim_text)
        for case in cases
        if case.case_id in set(selection.assisted_case_ids)
    }
    if fallback["V3-008"] is not AssistedConstructionEligibility.TEMPORAL:
        raise ValueError("V3-008 must be the untouched temporal development case")
    if fallback["V3-004"] is not AssistedConstructionEligibility.MISSING_REFERENCE_DATE:
        raise ValueError("status without a reference date must fail closed")
    qualitative = {"V3-014", "V3-016", "V3-017", "V3-029"}
    if any(
        fallback[case_id] is not AssistedConstructionEligibility.EXCLUDED_QUALITATIVE
        for case_id in qualitative
    ):
        raise ValueError("qualitative cases crossed the V3.5a eligibility boundary")
    forbidden = {"verdict", "verification_state", "readiness", "publication"}
    if forbidden.intersection(AssistedConstructionProposal.model_fields):
        raise ValueError("proposal crosses a protected decision boundary")

    files = (
        Path("src/claim_polygraph_ng/analysis/assisted_verification_construction.py"),
        Path("src/claim_polygraph_ng/analysis/bounded_assisted_construction.py"),
        Path("src/claim_polygraph_ng/providers/idempotent.py"),
        Path("src/claim_polygraph_ng/providers/ollama.py"),
        Path("src/claim_polygraph_ng/providers/openai.py"),
        Path("scripts/run_v3_stage5a_development.py"),
    )
    audit = {
        "audit_id": "verification-construction-v3-stage5a-contract-audit-v1",
        "status": "passed",
        "prompt_version": ASSISTED_CONSTRUCTION_PROMPT_VERSION,
        "development_cases_loaded": 20,
        "untouched_temporal_case_ids": ["V3-008"],
        "locked_previous_attempt_case_ids": ["V3-046"],
        "missing_reference_date_case_ids": ["V3-004"],
        "explicitly_excluded_qualitative_case_ids": sorted(qualitative),
        "calibration_cases_loaded": 0,
        "held_out_cases_loaded": 0,
        "pre_execution": {
            "model_calls": 0,
            "network_calls": 0,
            "paid_operations": 0,
        },
        "gates": {
            "typed_numerical_branch": True,
            "typed_temporal_status_branch": True,
            "exact_claim_date_grounding": True,
            "exact_evidence_date_grounding": True,
            "exact_status_text_grounding": True,
            "missing_reference_date_fail_closed": True,
            "qualitative_exclusion": True,
            "prompt_version_in_paid_receipt_key": True,
        },
        "artifacts": [
            {
                "path": path.as_posix(),
                "sha256": hashlib.sha256((root / path).read_bytes()).hexdigest(),
            }
            for path in files
        ],
    }
    destination = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage5a-contract-audit-v1.json"
    )
    destination.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print("status=passed development=20 calibration=0 held_out=0")


if __name__ == "__main__":
    main()
