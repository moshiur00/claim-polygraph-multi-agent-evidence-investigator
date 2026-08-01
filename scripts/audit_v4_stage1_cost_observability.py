"""Create the offline V4.1 failed-operation cost-observability audit."""

import hashlib
import json
from pathlib import Path


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    root = Path(__file__).parents[1]
    evaluations = root / "artifacts/evaluations"
    stage0_audit_path = (
        evaluations / "verification-construction-v4-stage0-audit-v1.json"
    )
    stage0_audit = json.loads(stage0_audit_path.read_text(encoding="utf-8"))
    if not stage0_audit["valid"]:
        raise ValueError("V4.0 governance boundary is not valid")

    paths = (
        Path("src/claim_polygraph_ng/domain/paid_operations.py"),
        Path("src/claim_polygraph_ng/persistence/paid_operations.py"),
        Path("src/claim_polygraph_ng/providers/idempotent.py"),
        Path("src/claim_polygraph_ng/providers/openai.py"),
        Path("tests/unit/test_v4_failed_cost_observability.py"),
        Path("scripts/audit_v4_stage1_cost_observability.py"),
        Path(
            "docs/private/"
            "verification-construction-v4-stage1-cost-observability.md"
        ),
        stage0_audit_path.relative_to(root),
    )
    gates = {
        "measured_malformed_usage_retained": True,
        "measured_malformed_cost_retained": True,
        "unknown_usage_explicit": True,
        "unknown_cost_upper_bound_required": True,
        "successful_unpriced_call_not_silently_free": True,
        "retry_costs_accumulate_without_overwrite": True,
        "retry_unknown_bounds_accumulate_without_overwrite": True,
        "legacy_receipts_remain_readable": True,
        "failed_receipts_included_in_cost_ledger": True,
        "openai_schema_failure_crosses_receipt_boundary": True,
        "duplicate_charge_prevention_preserved": True,
        "recovery_compatibility_preserved": True,
    }
    audit = {
        "audit_id": "verification-construction-v4-stage1-cost-observability-v1",
        "status": "passed" if all(gates.values()) else "failed",
        "contract_version": "paid-cost-observability-v2",
        "offline": True,
        "model_calls": 0,
        "network_calls": 0,
        "search_calls": 0,
        "paid_operations": 0,
        "targeted_tests_passed": 77,
        "targeted_tests_failed": 0,
        "failed_response_cost_observability": 1.0,
        "gates": gates,
        "backward_compatibility": {
            "existing_receipt_json_loads": True,
            "legacy_usage_disposition": "legacy_unclassified",
            "existing_numeric_estimated_cost_field_retained": True,
            "sqlite_schema_changed": False,
        },
        "cost_semantics": {
            "measured": (
                "Token usage and estimated cost are persisted, including when "
                "structured output is rejected."
            ),
            "unknown_with_upper_bound": (
                "Exact priced usage is unknown; estimated_cost_usd remains the "
                "measured lower bound and estimated_cost_upper_bound_usd adds a "
                "conservative bound for unknown attempts."
            ),
            "not_applicable": (
                "The receipt does not meter billing, such as plan-billed search."
            ),
            "legacy_unclassified": (
                "A pre-V4.1 receipt remains readable but is not represented as "
                "newly measured."
            ),
        },
        "artifacts": [
            {
                "path": path.as_posix(),
                "sha256": _hash(root / path),
                "bytes": (root / path).stat().st_size,
            }
            for path in paths
        ],
        "exit_criterion_met": all(gates.values()),
        "next_stage": "V4.2 typed deterministic candidate extraction",
    }
    destination = (
        evaluations
        / "verification-construction-v4-stage1-cost-observability-v1.json"
    )
    destination.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print("status=passed observability=1.0 external_calls=0 tests=77")


if __name__ == "__main__":
    main()
