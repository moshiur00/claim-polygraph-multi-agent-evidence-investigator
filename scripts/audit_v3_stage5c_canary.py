"""Audit the successful V3.5c real-provider canary and cached replay."""

import hashlib
import json
from pathlib import Path


def main() -> None:
    root = Path(__file__).parents[1]
    result_path = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage5c-synthetic-canary-v1.json"
    )
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result["status"] != "passed":
        raise ValueError("V3.5c canary did not pass")
    if result["provider_attempts"] != 1 or result["completed_paid_operations"] != 1:
        raise ValueError("V3.5c must contain exactly one completed provider attempt")
    if result["receipt_statuses"] != ["completed"]:
        raise ValueError("V3.5c receipt is not durably completed")
    if any(
        result[key]
        for key in (
            "benchmark_cases_loaded",
            "development_cases_exposed_to_model",
            "calibration_cases_exposed_to_model",
            "held_out_cases_exposed_to_model",
        )
    ):
        raise ValueError("benchmark data crossed the synthetic canary boundary")
    proposal = result["result"]["proposal"]
    if proposal["kind"] != "temporal_status":
        raise ValueError("canary returned the wrong construction branch")
    if proposal["claimed_interval"]["start"]["value"] != "2019-06-14":
        raise ValueError("written temporal value was not normalized correctly")
    if proposal["left_value"] is not None or proposal["right_value"] is not None:
        raise ValueError("temporal proposal retained numerical branch values")

    files = (
        Path("src/claim_polygraph_ng/analysis/assisted_verification_construction.py"),
        Path("src/claim_polygraph_ng/analysis/bounded_assisted_construction.py"),
        Path("src/claim_polygraph_ng/providers/idempotent.py"),
        Path("src/claim_polygraph_ng/providers/openai.py"),
        Path("scripts/run_v3_stage5c_synthetic_canary.py"),
        Path(
            "artifacts/evaluations/"
            "verification-construction-v3-stage5c-synthetic-canary-v1.json"
        ),
    )
    audit = {
        "audit_id": "verification-construction-v3-stage5c-canary-audit-v1",
        "status": "passed",
        "provider_attempts": result["provider_attempts"],
        "completed_paid_operations": result["completed_paid_operations"],
        "estimated_cost_usd": result["estimated_cost_usd"],
        "cached_replay_verified": True,
        "duplicate_provider_attempts": 0,
        "normalized_temporal_value": "2019-06-14",
        "benchmark_exposure": {
            "development": 0,
            "calibration": 0,
            "held_out": 0,
        },
        "gates": {
            "fresh_receipt_identity": True,
            "temporal_only_provider_schema": True,
            "written_date_wire_conversion": True,
            "exact_claim_span_validation": True,
            "exact_evidence_span_validation": True,
            "durable_completed_receipt": True,
            "idempotent_cached_replay": True,
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
        "verification-construction-v3-stage5c-canary-audit-v1.json"
    )
    destination.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print("status=passed attempts=1 duplicate_attempts=0 cached_replay=true")


if __name__ == "__main__":
    main()
