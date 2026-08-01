"""Audit the frozen zero-cost V4.0 governance boundary."""

import hashlib
import json
from pathlib import Path

from claim_polygraph_ng.evaluation.v4_manifest import (
    V4FailureCategory,
    V4StageZeroManifest,
    verify_v4_manifest,
)


def main() -> None:
    root = Path(__file__).parents[1]
    evaluations = root / "artifacts/evaluations"
    manifest_path = (
        evaluations / "verification-construction-v4-stage0-manifest-v1.json"
    )
    manifest = V4StageZeroManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    errors = list(verify_v4_manifest(manifest, root))
    taxonomy = json.loads(
        (root / manifest.failure_taxonomy.path).read_text(encoding="utf-8")
    )
    categories = [
        V4FailureCategory.model_validate(item) for item in taxonomy["categories"]
    ]
    if len(categories) != 15:
        errors.append("failure taxonomy must contain 15 categories")
    if any(item.may_use_v3_held_out_text for item in categories):
        errors.append("a failure category permits V3 held-out text reuse")
    policy = json.loads(
        (root / manifest.dataset_nonreuse_policy.path).read_text(encoding="utf-8")
    )
    if any(
        value != "prohibited"
        for key, value in policy["v3_held_out"].items()
        if key != "category_level_failure_lessons"
    ):
        errors.append("V3 held-out policy is not fully retired")
    if policy["v3_held_out"]["category_level_failure_lessons"] != "permitted":
        errors.append("abstract failure lessons should remain permitted")

    audit = {
        "audit_id": "verification-construction-v4-stage0-audit-v1",
        "status": "passed" if not errors else "failed",
        "valid": not errors,
        "errors": errors,
        "failure_categories": len(categories),
        "retired_v3_benchmark_artifacts": len(
            policy["retired_v3_benchmark_artifacts"]
        ),
        "provider_selected": manifest.provider_selected,
        "model_calls": manifest.model_calls,
        "network_calls": manifest.network_calls,
        "search_calls": manifest.search_calls,
        "paid_operations": manifest.paid_operations,
        "fresh_calibration_cases_collected": (
            manifest.fresh_calibration_cases_collected
        ),
        "fresh_held_out_cases_collected": manifest.fresh_held_out_cases_collected,
        "manifest": {
            "path": manifest_path.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        },
        "exit_criterion_met": not errors,
    }
    destination = (
        evaluations / "verification-construction-v4-stage0-audit-v1.json"
    )
    destination.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print(f"status={audit['status']} errors={len(errors)} external_calls=0")


if __name__ == "__main__":
    main()
