"""Audit the bounded V4.6 real-provider canary without another call."""

import hashlib
import json
from pathlib import Path


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    root = Path(__file__).parents[1]
    evaluations = root / "artifacts/evaluations"
    manifest_path = evaluations / "verification-construction-v4-stage6-canary-manifest-v1.json"
    result_path = evaluations / "verification-construction-v4-stage6-canary-result-v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    by_id = {item["canary_id"]: item for item in result["results"]}
    scalar = by_id["v4.6-synthetic-scalar-canary-v1"]
    temporal = by_id["v4.6-synthetic-temporal-canary-v1"]

    safety_gates = {
        "manifest_frozen_before_execution": (
            manifest["status"] == "frozen" and result["manifest_sha256"] == _hash(manifest_path)
        ),
        "provider_attempt_ceiling_respected": (
            result["provider_attempts"] <= manifest["maximum_provider_attempts"] == 2
        ),
        "no_automatic_retry": result["provider_attempts"] == 2,
        "all_attempts_cost_observable": (
            len(result["usage_dispositions"]) == 2
            and all(
                item in {"measured", "unknown_with_upper_bound"}
                for item in result["usage_dispositions"]
            )
        ),
        "cost_within_stage_ceiling": (
            result["estimated_cost_upper_bound_usd"] <= manifest["maximum_total_cost_usd"]
        ),
        "scalar_schema_validated": (
            scalar["disposition"] == "validated_proposal"
            and scalar["proposal"]["kind"] == "numerical_scalar"
        ),
        "scalar_cached_replay_without_duplicate": scalar["cached_replay_equal"],
        "temporal_failure_was_fail_closed": (
            temporal["disposition"] == "safe_failure" and temporal["error_type"] == "ValueError"
        ),
        "cancellation_before_reservation": (
            result["cancellation"]["error_type"] == "AssistedConstructionCancelled"
            and not result["cancellation"]["created_receipt"]
        ),
        "duplicate_paid_operations_zero": (
            result["provider_attempts"] == result["completed_paid_operations"] == 2
        ),
        "benchmark_exposure_zero": not any(result["dataset_exposure"].values()),
    }
    promotion_gates = {
        **safety_gates,
        "both_branch_schemas_validate": (
            scalar["disposition"] == "validated_proposal"
            and temporal["disposition"] == "validated_proposal"
        ),
    }
    paths = (
        Path("scripts/freeze_v4_stage6_canary.py"),
        Path("scripts/run_v4_stage6_canary.py"),
        Path("scripts/audit_v4_stage6_canary.py"),
        Path("src/claim_polygraph_ng/analysis/assisted_verification_construction.py"),
        Path("src/claim_polygraph_ng/analysis/bounded_assisted_construction.py"),
        Path("src/claim_polygraph_ng/providers/idempotent.py"),
        Path("src/claim_polygraph_ng/providers/openai.py"),
        Path("artifacts/evaluations/verification-construction-v4-stage5-offline-gate-v1.json"),
        manifest_path.relative_to(root),
        result_path.relative_to(root),
    )
    audit = {
        "audit_id": "verification-construction-v4-stage6-canary-audit-v1",
        "status": ("passed" if all(promotion_gates.values()) else "failed_safe"),
        "exit_criterion_met": all(promotion_gates.values()),
        "safety_boundary_passed": all(safety_gates.values()),
        "provider_attempts": result["provider_attempts"],
        "completed_paid_operations": result["completed_paid_operations"],
        "duplicate_provider_attempts": 0,
        "estimated_cost_usd": result["estimated_cost_usd"],
        "estimated_cost_upper_bound_usd": result["estimated_cost_upper_bound_usd"],
        "failure": {
            "canary_id": temporal["canary_id"],
            "layer": "deterministic_post_provider_validation",
            "error_type": temporal["error_type"],
            "safe_error": temporal["error"],
            "diagnosis": (
                "The temporal wire fallback copied claimed_status into a "
                "date-only evidence binding. Deterministic grounding correctly "
                "rejected that status because it was outside the exact quote."
            ),
            "paid_receipt_disposition": "completed_measured",
            "retry_permitted": False,
        },
        "gates": promotion_gates,
        "artifacts": [
            {
                "path": path.as_posix(),
                "sha256": _hash(root / path),
                "bytes": (root / path).stat().st_size,
            }
            for path in paths
        ],
        "next_stage": (
            "V4.6a temporal binding remediation using offline fixtures, "
            "followed by a fresh synthetic canary identity"
        ),
    }
    destination = evaluations / "verification-construction-v4-stage6-canary-audit-v1.json"
    destination.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print(
        f"status={audit['status']} safety={audit['safety_boundary_passed']} "
        f"attempts={audit['provider_attempts']} "
        f"cost_usd={audit['estimated_cost_usd']:.8f}"
    )


if __name__ == "__main__":
    main()
