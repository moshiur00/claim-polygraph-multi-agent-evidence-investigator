"""Freeze Verification Construction V4.0 without external calls."""

import hashlib
import json
from pathlib import Path

from claim_polygraph_ng.evaluation.v4_manifest import V4StageZeroManifest


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact(root: Path, relative: str) -> dict[str, str]:
    path = root / relative
    return {"path": relative, "sha256": _hash(path)}


def main() -> None:
    root = Path(__file__).parents[1]
    evaluations = root / "artifacts/evaluations"
    taxonomy_path = (
        evaluations / "verification-construction-v4-failure-taxonomy-v1.json"
    )
    nonreuse_path = (
        evaluations / "verification-construction-v4-dataset-nonreuse-policy-v1.json"
    )

    taxonomy = {
        "taxonomy_id": "verification-construction-v4-failure-taxonomy-v1",
        "derived_from": (
            "verification-construction-v3-stage8-eligibility-analysis-v1"
        ),
        "v3_held_out_claim_text_copied_into_v4_fixtures": 0,
        "categories": [
            {"category_id": "V4-F01", "layer": "eligibility", "name": "quantified exact count", "remediation_contract": "Recognize explicit counts even when universal or approximate quantifiers require qualification."},
            {"category_id": "V4-F02", "layer": "eligibility", "name": "ordinal ranking with time", "remediation_contract": "Represent rank, population, measure and reference period as typed operands."},
            {"category_id": "V4-F03", "layer": "eligibility", "name": "absence or zero-use status", "remediation_contract": "Recognize absence claims when retained evidence can bind a nonzero counterexample or status."},
            {"category_id": "V4-F04", "layer": "eligibility", "name": "relative measurement", "remediation_contract": "Recognize ordinary comparative language grounded by explicit measurements and reference populations."},
            {"category_id": "V4-F05", "layer": "extraction", "name": "paired-value comparison", "remediation_contract": "Extract both values, units, subjects and the comparison relation."},
            {"category_id": "V4-F06", "layer": "extraction", "name": "multiplicative comparison", "remediation_contract": "Extract ratio or multiplicative language and bind both comparison values."},
            {"category_id": "V4-F07", "layer": "extraction", "name": "dated projection", "remediation_contract": "Preserve start value/date, end value/date and projection modality."},
            {"category_id": "V4-F08", "layer": "extraction", "name": "dated scalar", "remediation_contract": "Bind the scalar value and its material reference date in one linked construction."},
            {"category_id": "V4-F09", "layer": "construction", "name": "compound conditions", "remediation_contract": "Create linked assertions for every threshold, duration, scope and consequence."},
            {"category_id": "V4-F10", "layer": "construction", "name": "material qualifier loss", "remediation_contract": "Reject claim spans or evidence bindings that omit a material qualifier or scope."},
            {"category_id": "V4-F11", "layer": "construction", "name": "decisive evidence omission", "remediation_contract": "Require bindings for support, contradiction or qualification needed by deterministic verification."},
            {"category_id": "V4-F12", "layer": "validation", "name": "scalar normalization mismatch", "remediation_contract": "Normalize compatible magnitude and unit forms before explicit-binding validation."},
            {"category_id": "V4-F13", "layer": "validation", "name": "invalid scale", "remediation_contract": "Fail closed on nonpositive scales and preserve the terminal receipt and safe error."},
            {"category_id": "V4-F14", "layer": "eligibility", "name": "open-world or causal exclusion", "remediation_contract": "Continue excluding unsupported superlative, causal and universal generalization claims."},
            {"category_id": "V4-F15", "layer": "observability", "name": "failed response usage gap", "remediation_contract": "Persist provider usage or explicit unknown usage plus a conservative cost upper bound for every attempted response."},
        ],
    }
    taxonomy_path.write_text(json.dumps(taxonomy, indent=2) + "\n", encoding="utf-8")

    predecessor = (
        evaluations / "verification-construction-v3-stage9-final-audit-v1.json"
    )
    json.loads(predecessor.read_text(encoding="utf-8"))
    retired_hashes = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": _hash(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(
            (root / "benchmarks").glob("verification_construction_v3*.json")
        )
    ]
    policy = {
        "policy_id": "verification-construction-v4-dataset-nonreuse-policy-v1",
        "status": "frozen",
        "v3_held_out": {
            "development_use": "prohibited",
            "tuning_use": "prohibited",
            "calibration_use": "prohibited",
            "held_out_use": "prohibited",
            "exact_claim_text_in_synthetic_fixtures": "prohibited",
            "category_level_failure_lessons": "permitted",
        },
        "v3_development_and_exposed_calibration": {
            "non_promotional_diagnostics": "permitted_with_label",
            "promotion_metrics": "prohibited",
            "fresh_v4_calibration_or_held_out": "prohibited",
        },
        "fresh_v4_evaluation": {
            "exclude_all_v3_exact_claims": True,
            "exclude_all_v3_origin_families": True,
            "calibration_and_held_out_origin_families_disjoint": True,
            "split_frozen_before_model_execution": True,
            "human_annotation_required": True,
            "distinct_approval_required": True,
        },
        "retired_v3_benchmark_artifacts": retired_hashes,
    }
    nonreuse_path.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "manifest_id": "verification-construction-v4-stage0-manifest-v1",
        "schema_version": 1,
        "status": "frozen",
        "plan": _artifact(
            root, "docs/private/verification-construction-v4-remediation-plan.md"
        ),
        "failure_taxonomy": _artifact(
            root,
            "artifacts/evaluations/verification-construction-v4-failure-taxonomy-v1.json",
        ),
        "dataset_nonreuse_policy": _artifact(
            root,
            "artifacts/evaluations/verification-construction-v4-dataset-nonreuse-policy-v1.json",
        ),
        "predecessor_closure": _artifact(
            root,
            "artifacts/evaluations/verification-construction-v3-stage9-final-audit-v1.json",
        ),
        "contract": _artifact(
            root, "src/claim_polygraph_ng/evaluation/v4_manifest.py"
        ),
        "budget": {
            "stage_v4_0_model_calls": 0,
            "stage_v4_0_network_calls": 0,
            "stage_v4_0_search_calls": 0,
            "stage_v4_0_paid_operations": 0,
            "maximum_synthetic_canary_calls": 2,
            "maximum_development_calls": 20,
            "maximum_calibration_calls": 20,
            "maximum_held_out_calls": 20,
            "maximum_total_calls": 62,
            "maximum_input_tokens_per_call": 6000,
            "maximum_output_tokens_per_call": 900,
            "maximum_total_cost_usd": 1.25,
            "maximum_cost_per_recovered_assertion_usd": 0.05,
            "retries_after_valid_paid_receipt": 0,
        },
        "offline_promotion_gates": {
            "minimum_constructible_eligibility_recall": 1.0,
            "minimum_negative_exclusion_precision": 1.0,
            "minimum_compound_operand_preservation": 1.0,
            "minimum_exact_span_validity": 1.0,
            "minimum_schema_validity": 1.0,
            "maximum_unsafe_accepted_constructions": 0,
            "minimum_human_review_routing_recall": 1.0,
            "maximum_publication_safety_regressions": 0,
            "maximum_duplicate_paid_operations": 0,
            "minimum_failed_response_cost_observability": 1.0,
            "maximum_v3_held_out_texts_loaded": 0,
            "cancellation_before_reservation_required": True,
            "restart_reconstruction_required": True,
        },
        "provider_selected": False,
        "model_calls": 0,
        "network_calls": 0,
        "search_calls": 0,
        "paid_operations": 0,
        "fresh_calibration_cases_collected": 0,
        "fresh_held_out_cases_collected": 0,
    }
    validated = V4StageZeroManifest.model_validate(manifest)
    destination = (
        evaluations / "verification-construction-v4-stage0-manifest-v1.json"
    )
    if destination.exists():
        raise FileExistsError("V4.0 manifest already exists")
    destination.write_text(
        json.dumps(validated.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    print(destination.relative_to(root))
    print("status=frozen failures=15 model_calls=0 network_calls=0")


if __name__ == "__main__":
    main()
