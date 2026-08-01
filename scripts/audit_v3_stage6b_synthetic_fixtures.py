"""Audit V3.6b routing against synthetic fixtures without model calls."""

import json
from pathlib import Path

from claim_polygraph_ng.analysis.assisted_verification_construction import (
    classify_assisted_eligibility,
)


def main() -> None:
    root = Path(__file__).parents[1]
    source = (
        root
        / "benchmarks/verification_construction_v3_stage6b_synthetic_fixtures_v1.json"
    )
    payload = json.loads(source.read_text(encoding="utf-8"))
    results = []
    for case in payload["cases"]:
        observed = classify_assisted_eligibility(case["claim"]).value
        results.append(
            {
                "case_id": case["case_id"],
                "focus": case["focus"],
                "expected": case["expected_eligibility"],
                "observed": observed,
                "passed": observed == case["expected_eligibility"],
            }
        )
    failed = [item for item in results if not item["passed"]]
    artifact = {
        "audit_id": "verification-construction-v3-stage6b-synthetic-audit-v1",
        "status": "passed" if not failed else "failed",
        "case_count": len(results),
        "passed_count": len(results) - len(failed),
        "failed_count": len(failed),
        "development_or_synthetic_only": True,
        "model_calls": 0,
        "original_calibration_cases_loaded": 0,
        "replacement_calibration_cases_loaded": 0,
        "original_held_out_cases_loaded": 0,
        "results": results,
    }
    destination = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage6b-synthetic-audit-v1.json"
    )
    destination.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    if failed:
        raise ValueError(f"V3.6b synthetic routing failures: {failed}")
    print(destination.relative_to(root))
    print(f"status=passed cases={len(results)} model_calls=0")


if __name__ == "__main__":
    main()
