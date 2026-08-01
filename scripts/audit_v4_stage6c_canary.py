"""Audit and close the final V4 synthetic temporal canary."""

import hashlib
import json
from pathlib import Path


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    root = Path(__file__).parents[1]
    evaluations = root / "artifacts/evaluations"
    manifest_path = evaluations / "verification-construction-v4-stage6c-canary-manifest-v1.json"
    result_path = evaluations / "verification-construction-v4-stage6c-canary-result-v1.json"
    amendment_path = evaluations / "verification-construction-v4-canary-budget-amendment-v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    amendment = json.loads(amendment_path.read_text(encoding="utf-8"))
    proposal = result["result"]["proposal"]
    binding = proposal["temporal_bindings"][0]
    evidence = manifest["fixture"]["evidence_text"]
    previous_results = [
        json.loads(
            (evaluations / "verification-construction-v4-stage6-canary-result-v1.json").read_text(
                encoding="utf-8"
            )
        ),
        json.loads(
            (evaluations / "verification-construction-v4-stage6a-canary-result-v1.json").read_text(
                encoding="utf-8"
            )
        ),
    ]
    cumulative_calls = result["provider_attempts"] + sum(
        item["provider_attempts"] for item in previous_results
    )
    cumulative_cost = result["estimated_cost_usd"] + sum(
        item["estimated_cost_usd"] for item in previous_results
    )
    gates = {
        "manifest_frozen_and_hash_matched": (
            manifest["status"] == "frozen" and result["manifest_sha256"] == _hash(manifest_path)
        ),
        "final_call_was_authorized": (
            amendment["final_canary_authorized"] and amendment["final_canary_maximum_calls"] == 1
        ),
        "one_call_ceiling_respected": result["provider_attempts"] == 1,
        "no_automatic_retry": result["provider_attempts"] == 1,
        "receipt_completed_and_measured": (
            result["receipt_statuses"] == ["completed"]
            and result["usage_dispositions"] == ["measured"]
        ),
        "temporal_proposal_validated": (
            result["status"] == "passed" and result["result"]["disposition"] == "validated_proposal"
        ),
        "unique_date_reconstructed": (
            proposal["reference_date"] == {"value": "2020-04-06", "precision": "day"}
        ),
        "evidence_interval_reconstructed": (
            binding["effective_interval"]["start"] == {"value": "2020-04-06", "precision": "day"}
            and binding["effective_interval"]["end"] == {"value": "2020-04-06", "precision": "day"}
        ),
        "exact_evidence_span_valid": (
            evidence[binding["start_char"] : binding["end_char"]]
            == binding["quoted_text"]
            == "6 April 2020"
        ),
        "cached_replay_without_duplicate": result["result"]["cached_replay_equal"],
        "dataset_exposure_zero": not any(result["dataset_exposure"].values()),
        "cumulative_canary_allocation_exhausted_exactly": (
            cumulative_calls == amendment["effective_budget"]["maximum_synthetic_canary_calls"] == 4
        ),
        "cumulative_cost_within_v4_ceiling": (
            cumulative_cost <= amendment["effective_budget"]["maximum_total_cost_usd"]
        ),
    }
    paths = (
        Path("scripts/freeze_v4_stage6c_canary.py"),
        Path("scripts/run_v4_stage6c_canary.py"),
        Path("scripts/audit_v4_stage6c_canary.py"),
        Path("src/claim_polygraph_ng/analysis/assisted_verification_construction.py"),
        Path("tests/unit/test_v3_assisted_boundary.py"),
        amendment_path.relative_to(root),
        manifest_path.relative_to(root),
        result_path.relative_to(root),
        Path("artifacts/evaluations/verification-construction-v4-stage6b-temporal-wire-v1.json"),
    )
    audit = {
        "audit_id": "verification-construction-v4-stage6c-canary-audit-v1",
        "status": "passed" if all(gates.values()) else "failed",
        "exit_criterion_met": all(gates.values()),
        "provider_attempts": result["provider_attempts"],
        "completed_paid_operations": result["completed_paid_operations"],
        "duplicate_provider_attempts": 0,
        "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"],
        "estimated_cost_usd": result["estimated_cost_usd"],
        "cumulative_synthetic_calls": cumulative_calls,
        "remaining_synthetic_calls": 0,
        "cumulative_synthetic_cost_usd": cumulative_cost,
        "gates": gates,
        "artifacts": [
            {
                "path": path.as_posix(),
                "sha256": _hash(root / path),
                "bytes": (root / path).stat().st_size,
            }
            for path in paths
        ],
        "next_stage": "V4.7 development evaluation with maximum 18 calls",
    }
    destination = evaluations / "verification-construction-v4-stage6c-canary-audit-v1.json"
    destination.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print(
        f"status={audit['status']} attempts=1 cumulative_calls={cumulative_calls} "
        f"remaining=0 cost_usd={result['estimated_cost_usd']:.8f}"
    )


if __name__ == "__main__":
    main()
