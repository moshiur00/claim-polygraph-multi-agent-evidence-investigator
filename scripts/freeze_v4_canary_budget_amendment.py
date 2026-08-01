"""Freeze one final V4 canary call without changing total budget."""

import hashlib
import json
from pathlib import Path

from claim_polygraph_ng.evaluation.v4_budget_amendment import (
    V4CanaryBudgetAmendment,
    verify_v4_budget_amendment,
)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    root = Path(__file__).parents[1]
    evaluations = root / "artifacts/evaluations"
    predecessor = evaluations / "verification-construction-v4-stage0-manifest-v1.json"
    result_paths = (
        evaluations / "verification-construction-v4-stage6-canary-result-v1.json",
        evaluations / "verification-construction-v4-stage6a-canary-result-v1.json",
    )
    results = [json.loads(path.read_text(encoding="utf-8")) for path in result_paths]
    consumed_calls = sum(item["provider_attempts"] for item in results)
    consumed_cost = sum(item["estimated_cost_usd"] for item in results)
    payload = {
        "amendment_id": ("verification-construction-v4-canary-budget-amendment-v1"),
        "status": "frozen",
        "predecessor_manifest_path": predecessor.relative_to(root).as_posix(),
        "predecessor_manifest_sha256": _hash(predecessor),
        "effective_budget": {
            "maximum_synthetic_canary_calls": 4,
            "maximum_development_calls": 18,
            "maximum_calibration_calls": 20,
            "maximum_held_out_calls": 20,
            "maximum_total_calls": 62,
            "maximum_input_tokens_per_call": 6000,
            "maximum_output_tokens_per_call": 900,
            "maximum_total_cost_usd": 1.25,
            "retries_after_valid_paid_receipt": 0,
        },
        "synthetic_calls_consumed": consumed_calls,
        "synthetic_calls_remaining": 4 - consumed_calls,
        "consumed_cost_usd": consumed_cost,
        "final_canary_authorized": True,
        "final_canary_maximum_calls": 1,
        "authorization_scope": (
            "One fresh temporal canary after V4.6b only; no retry, benchmark "
            "reuse, calibration access, or expansion of total calls or cost."
        ),
        "model_calls_during_amendment": 0,
        "network_calls_during_amendment": 0,
        "paid_operations_during_amendment": 0,
    }
    amendment = V4CanaryBudgetAmendment.model_validate(payload)
    errors = verify_v4_budget_amendment(amendment, root)
    if errors:
        raise ValueError("; ".join(errors))
    destination = evaluations / "verification-construction-v4-canary-budget-amendment-v1.json"
    destination.write_text(amendment.model_dump_json(indent=2) + "\n", encoding="utf-8")
    audit = {
        "audit_id": "verification-construction-v4-canary-budget-amendment-audit-v1",
        "status": "passed",
        "valid": True,
        "errors": [],
        "original_v4_manifest_unchanged": True,
        "original_total_calls": 62,
        "amended_total_calls": 62,
        "original_total_cost_usd": 1.25,
        "amended_total_cost_usd": 1.25,
        "synthetic_calls_consumed": consumed_calls,
        "synthetic_calls_remaining": 4 - consumed_calls,
        "development_calls_reallocated": 2,
        "model_calls": 0,
        "network_calls": 0,
        "paid_operations": 0,
        "amendment": {
            "path": destination.relative_to(root).as_posix(),
            "sha256": _hash(destination),
        },
        "evidence": [
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": _hash(path),
            }
            for path in (
                predecessor,
                *result_paths,
                evaluations / "verification-construction-v4-stage6b-temporal-wire-v1.json",
            )
        ],
        "exit_criterion_met": True,
        "next_stage": "V4.6c one-call final temporal canary",
    }
    audit_path = evaluations / "verification-construction-v4-canary-budget-amendment-audit-v1.json"
    audit_path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print(audit_path.relative_to(root))
    print(
        f"status=passed consumed={consumed_calls} remaining={4 - consumed_calls} "
        "total_calls=62 total_cost_usd=1.25 external_calls=0"
    )


if __name__ == "__main__":
    main()
