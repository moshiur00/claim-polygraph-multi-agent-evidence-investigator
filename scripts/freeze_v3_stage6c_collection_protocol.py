"""Freeze V3.6c collection and execution controls before human review."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


def _digest(root: Path, relative: str) -> dict[str, str]:
    return {
        "path": relative,
        "sha256": hashlib.sha256((root / relative).read_bytes()).hexdigest(),
    }


def main() -> None:
    root = Path(__file__).parents[1]
    paths = (
        "benchmarks/"
        "verification_construction_v3_stage6c_fresh_calibration_workbook_v1.json",
        "artifacts/evaluations/"
        "verification-construction-v3-stage6c-collection-audit-v1.json",
        "artifacts/evaluations/"
        "verification-construction-v3-stage6b-remediation-manifest-v1.json",
        "src/claim_polygraph_ng/domain/verification.py",
        "src/claim_polygraph_ng/analysis/assisted_verification_construction.py",
        "src/claim_polygraph_ng/analysis/bounded_assisted_construction.py",
        "src/claim_polygraph_ng/providers/openai.py",
        "src/claim_polygraph_ng/providers/ollama.py",
    )
    manifest = {
        "manifest_id": "verification-construction-v3-stage6c-collection-protocol-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "status": "frozen_awaiting_human_annotation_and_distinct_approval",
        "case_count": 20,
        "minimum_origin_families": 10,
        "maximum_cases_per_family": 2,
        "accessible_html_only": True,
        "human_annotation_required": True,
        "distinct_approval_required": True,
        "calibration_execution_limit_after_approval": 1,
        "promotion_thresholds": {
            "minimum_evidence_span_validity": 1.0,
            "maximum_unsafe_accepted_constructions": 0,
            "minimum_construction_precision": 0.98,
            "minimum_incremental_recall_gain": 0.15,
            "minimum_overall_construction_recall": 0.75,
            "minimum_human_review_routing_recall": 1.0,
            "maximum_publication_safety_regressions": 0,
            "maximum_duplicate_paid_operations": 0,
            "maximum_cost_per_recovered_assertion_usd": 0.05,
        },
        "artifacts": [_digest(root, path) for path in paths],
        "controls": {
            "collection_model_calls": 0,
            "collection_cost_usd": 0.0,
            "original_held_out_cases_loaded": 0,
            "original_held_out_cases_exposed": 0,
            "held_out_open_condition": "all frozen calibration gates pass",
        },
    }
    destination = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage6c-collection-protocol-v1.json"
    )
    destination.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print("status=frozen awaiting_review=true held_out=0")


if __name__ == "__main__":
    main()
