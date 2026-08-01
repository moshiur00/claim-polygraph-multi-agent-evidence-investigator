"""Audit the failed-safe V3.5b canary and its offline remediation."""

import hashlib
import json
from pathlib import Path

from claim_polygraph_ng.analysis.assisted_verification_construction import (
    ASSISTED_CONSTRUCTION_PROMPT_VERSION,
    AssistedTemporalInstantWire,
)
from claim_polygraph_ng.domain import DatePrecision


def main() -> None:
    root = Path(__file__).parents[1]
    run_path = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage5b-synthetic-canary-v1.json"
    )
    run = json.loads(run_path.read_text(encoding="utf-8"))
    if run["status"] != "failed_safe":
        raise ValueError("the first synthetic canary outcome changed")
    if any(
        run[key]
        for key in (
            "benchmark_cases_loaded",
            "development_cases_exposed_to_model",
            "calibration_cases_exposed_to_model",
            "held_out_cases_exposed_to_model",
        )
    ):
        raise ValueError("benchmark data crossed the synthetic canary boundary")
    converted = AssistedTemporalInstantWire(
        value="25 May 2018",
        precision=DatePrecision.DAY,
    ).to_domain()
    if converted.value.isoformat() != "2018-05-25":
        raise ValueError("written date remediation is not deterministic")

    files = (
        Path("src/claim_polygraph_ng/analysis/assisted_verification_construction.py"),
        Path("src/claim_polygraph_ng/analysis/bounded_assisted_construction.py"),
        Path("src/claim_polygraph_ng/providers/openai.py"),
        Path("scripts/run_v3_stage5b_synthetic_canary.py"),
        Path(
            "artifacts/evaluations/"
            "verification-construction-v3-stage5b-synthetic-canary-v1.json"
        ),
    )
    audit = {
        "audit_id": "verification-construction-v3-stage5b-canary-audit-v1",
        "status": "remediated_offline_recanary_required",
        "original_canary_status": run["status"],
        "original_provider_attempts": run["provider_attempts"],
        "original_completed_paid_operations": run["completed_paid_operations"],
        "original_estimated_cost_usd": run["estimated_cost_usd"],
        "current_prompt_version": ASSISTED_CONSTRUCTION_PROMPT_VERSION,
        "root_cause": (
            "Provider returned an explicit written date while the canonical domain "
            "contract expected an ISO-parsed date."
        ),
        "remediation": (
            "A provider-facing date wire type now parses explicit written or ISO dates "
            "and deterministically converts them to TemporalInstant."
        ),
        "second_provider_call_made": False,
        "benchmark_exposure": {
            "development": 0,
            "calibration": 0,
            "held_out": 0,
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
        "verification-construction-v3-stage5b-canary-audit-v1.json"
    )
    destination.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print("status=remediated_offline_recanary_required second_provider_call=false")


if __name__ == "__main__":
    main()
