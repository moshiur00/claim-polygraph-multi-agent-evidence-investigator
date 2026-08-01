"""Audit V4.6a without retrying its consumed temporal fixture."""

import hashlib
import json
from pathlib import Path

from freeze_v4_stage6a_canary import PRESERVED_HASHES


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    root = Path(__file__).parents[1]
    evaluations = root / "artifacts/evaluations"
    offline_path = evaluations / "verification-construction-v4-stage6a-offline-remediation-v1.json"
    manifest_path = evaluations / "verification-construction-v4-stage6a-canary-manifest-v1.json"
    result_path = evaluations / "verification-construction-v4-stage6a-canary-result-v1.json"
    offline = json.loads(offline_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    preserved = all(_hash(root / path) == digest for path, digest in PRESERVED_HASHES.items())
    safety_gates = {
        "offline_remediation_passed": offline["exit_criterion_met"],
        "consumed_v4_6_evidence_preserved": preserved,
        "fresh_receipt_identity": manifest["fresh_receipt_identity"],
        "one_call_ceiling_respected": (
            result["provider_attempts"] <= manifest["maximum_provider_attempts"] == 1
        ),
        "no_automatic_retry": result["provider_attempts"] == 1,
        "attempt_cost_observable": result["usage_dispositions"] == ["measured"],
        "cost_within_ceiling": (
            result["estimated_cost_upper_bound_usd"] <= manifest["maximum_total_cost_usd"]
        ),
        "failure_was_fail_closed": (
            result["result"]["disposition"] == "safe_failure"
            and result["result"]["error_type"] == "ValidationError"
        ),
        "duplicate_paid_operations_zero": (
            result["provider_attempts"] == result["completed_paid_operations"] == 1
        ),
        "dataset_exposure_zero": not any(result["dataset_exposure"].values()),
    }
    promotion_gates = {
        **safety_gates,
        "fresh_temporal_schema_validated": (
            result["result"]["disposition"] == "validated_proposal"
        ),
        "cached_replay_validated": result["result"]["cached_replay_equal"],
    }
    paths = (
        Path("src/claim_polygraph_ng/analysis/assisted_verification_construction.py"),
        Path("tests/unit/test_v3_assisted_boundary.py"),
        Path("scripts/freeze_v4_stage6a_canary.py"),
        Path("scripts/run_v4_stage6a_canary.py"),
        Path("scripts/audit_v4_stage6a_canary.py"),
        offline_path.relative_to(root),
        manifest_path.relative_to(root),
        result_path.relative_to(root),
    )
    audit = {
        "audit_id": "verification-construction-v4-stage6a-canary-audit-v1",
        "status": ("passed" if all(promotion_gates.values()) else "failed_safe"),
        "exit_criterion_met": all(promotion_gates.values()),
        "safety_boundary_passed": all(safety_gates.values()),
        "provider_attempts": result["provider_attempts"],
        "completed_paid_operations": result["completed_paid_operations"],
        "duplicate_provider_attempts": 0,
        "estimated_cost_usd": result["estimated_cost_usd"],
        "failure": {
            "layer": "temporal_provider_wire_to_domain_conversion",
            "error_type": result["result"]["error_type"],
            "safe_error": result["result"]["error"],
            "diagnosis": (
                "The provider returned an exact date quote but omitted "
                "reference_date, claimed_interval, effective_interval and "
                "observed_status. The wire schema admitted a temporal binding "
                "with no typed temporal fact; the domain contract rejected it."
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
            "V4.6b temporal wire completeness remediation using offline "
            "fixtures before any fresh canary decision"
        ),
    }
    destination = evaluations / "verification-construction-v4-stage6a-canary-audit-v1.json"
    destination.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print(
        f"status={audit['status']} safety={audit['safety_boundary_passed']} "
        f"attempts={audit['provider_attempts']} "
        f"cost_usd={audit['estimated_cost_usd']:.8f}"
    )


if __name__ == "__main__":
    main()
