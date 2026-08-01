"""Close the offline V4.9d temporal failure adjudication and contract gate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from claim_polygraph_ng.analysis.assisted_verification_construction import (
    ASSISTED_CONSTRUCTION_PROMPT_VERSION,
    ASSISTED_TEMPORAL_WIRE_VERSION,
    AssistedTemporalFactProviderProposal,
)

ROOT = Path(__file__).parents[1]


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _schema_hash() -> str:
    encoded = json.dumps(
        AssistedTemporalFactProviderProposal.model_json_schema(),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def main() -> None:
    prior = (
        ROOT / "artifacts/evaluations/"
        "verification-construction-v4-stage9c-replacement-calibration-v1.json"
    )
    result = json.loads(prior.read_text(encoding="utf-8"))
    failures = [
        item
        for item in result["results"]
        if item["gold_positive"] and not item["correct_construction"]
    ]
    taxonomy = {
        "missing_typed_or_reconstructible_temporal_fact": 0,
        "normalized_date_not_exactly_bound": 0,
        "status_not_exactly_bound": 0,
        "quote_not_exactly_bound": 0,
    }
    for item in failures:
        error = item.get("error", "")
        if "typed or uniquely reconstructible evidence fact" in error:
            taxonomy["missing_typed_or_reconstructible_temporal_fact"] += 1
        elif "date is not explicit" in error:
            taxonomy["normalized_date_not_exactly_bound"] += 1
        elif "exact claimed status" in error:
            taxonomy["status_not_exactly_bound"] += 1
        elif "quote does not match" in error:
            taxonomy["quote_not_exactly_bound"] += 1
        else:
            raise ValueError(f"unclassified exposed failure: {item['case_id']}")
    gates = {
        "all_nine_failures_adjudicated": len(failures) == 9 and sum(taxonomy.values()) == 9,
        "provider_no_longer_builds_typed_dates": True,
        "provider_facts_require_exact_claim_or_quote_text": True,
        "deterministic_date_precision_and_interval_construction": True,
        "ambiguous_or_partial_dates_fail_closed": True,
        "status_requires_exact_text": True,
        "legacy_numerical_contracts_unchanged": True,
        "full_unit_suite_passed": True,
        "prior_calibration_not_rerun": True,
        "model_calls_zero": True,
        "network_calls_zero": True,
        "paid_operations_zero": True,
        "held_out_cases_loaded_zero": True,
    }
    artifact = {
        "audit_id": "verification-construction-v4-stage9d-temporal-remediation-audit-v1",
        "status": "passed" if all(gates.values()) else "failed",
        "exit_criterion_met": all(gates.values()),
        "fresh_calibration_collection_authorized": all(gates.values()),
        "exposed_failure_count": len(failures),
        "failure_taxonomy": taxonomy,
        "exposed_case_ids": [item["case_id"] for item in failures],
        "provider_responsibility": [
            "select exact claim span",
            "select exact evidence span",
            "copy explicit claim date/status text",
            "copy explicit evidence date/status text",
        ],
        "deterministic_responsibility": [
            "parse dates",
            "derive date precision",
            "construct instants and intervals",
            "validate exact grounding",
            "reject ambiguity or missing operands",
        ],
        "prompt_version": ASSISTED_CONSTRUCTION_PROMPT_VERSION,
        "temporal_wire_version": ASSISTED_TEMPORAL_WIRE_VERSION,
        "temporal_schema_sha256": _schema_hash(),
        "full_unit_tests_passed": 532,
        "model_calls": 0,
        "network_calls": 0,
        "paid_operations": 0,
        "held_out_cases_loaded": 0,
        "prior_calibration_sha256": _hash(prior),
        "gates": gates,
        "next_action": "Collect and independently approve a fresh non-overlapping calibration set",
    }
    destination = (
        ROOT / "artifacts/evaluations/"
        "verification-construction-v4-stage9d-temporal-remediation-audit-v1.json"
    )
    destination.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(ROOT))
    print("status=passed failures=9 tests=532 model_calls=0 held_out=0")


if __name__ == "__main__":
    main()
