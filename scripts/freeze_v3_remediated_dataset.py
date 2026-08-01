"""Freeze the fully approved V3 dataset under the approved quota amendment."""

import hashlib
import json
from collections import Counter
from pathlib import Path

from claim_polygraph_ng.evaluation.v3_annotation import (
    V3ReviewDecision,
    audit_annotation_workbook,
    load_annotation_workbook,
    project_approved_dataset,
)


SOURCE = Path(
    r"C:\Users\moshi\Downloads"
    r"\verification_construction_v3_annotation_workbook_v1_APPROVED_WITH_QUOTA_DEVIATION (1).json"
)
REMEDIATION_IDS = ("V3-009", "V3-022", "V3-031", "V3-045", "V3-053")
REMEDIATION_DIMENSIONS = ("pressure", "pressure", "pressure", "currency", "currency")


def main() -> None:
    root = Path(__file__).parents[1]
    workbook = load_annotation_workbook(SOURCE)
    audit = audit_annotation_workbook(workbook)
    if not audit.ready_to_freeze:
        raise ValueError(f"human-review gate failed: {audit.blocking_reasons}")
    if audit.split_counts != {
        "calibration": 20,
        "development": 20,
        "held_out": 20,
    }:
        raise ValueError("the frozen 20/20/20 split was not preserved")

    by_id = {case.case_id: case for case in workbook.cases}
    observed_dimensions = tuple(
        by_id[case_id].annotation.dimension_bucket for case_id in REMEDIATION_IDS
    )
    if observed_dimensions != REMEDIATION_DIMENSIONS:
        raise ValueError("the approved remediation dimensions do not match the amendment")
    if any(
        by_id[case_id].approval.decision is not V3ReviewDecision.APPROVE
        for case_id in REMEDIATION_IDS
    ):
        raise ValueError("every remediation case requires explicit approval")

    dimension_counts = Counter(
        case.annotation.dimension_bucket for case in workbook.cases
    )
    required_dimensions = {
        "percentage_or_rate",
        "count",
        "pressure",
        "currency",
        "speed",
        "temperature",
        "duration",
        "distance_or_mass",
        "temporal_instant",
        "temporal_interval_or_status",
    }
    below_minimum = {
        dimension: dimension_counts.get(dimension, 0)
        for dimension in required_dimensions
        if dimension_counts.get(dimension, 0) < 3
    }
    if below_minimum:
        raise ValueError(f"amended dimension minimum failed: {below_minimum}")

    frozen_workbook = workbook.model_copy(update={"frozen": True})
    workbook_path = (
        root / "benchmarks/verification_construction_v3_approved_frozen_v2.json"
    )
    workbook_path.write_text(
        frozen_workbook.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    dataset = project_approved_dataset(
        frozen_workbook,
        evidence_packet_path=workbook_path.relative_to(root).as_posix(),
    )
    dataset_path = (
        root / "benchmarks/verification_construction_real_world_v3_frozen.json"
    )
    dataset_path.write_text(dataset.model_dump_json(indent=2) + "\n", encoding="utf-8")

    artifact_paths = (
        workbook_path,
        dataset_path,
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-sampling-policy-amendment-v2.json",
        root
        / "benchmarks/"
        "verification_construction_v3_quota_remediation_candidates_v1.json",
    )
    freeze_audit = {
        "audit_id": "verification-construction-v3-stage2b-final-freeze-v2",
        "status": "passed",
        "frozen": True,
        "case_count": len(frozen_workbook.cases),
        "annotated_cases": audit.annotated_cases,
        "approved_cases": audit.approved_cases,
        "returned_cases": audit.returned_cases,
        "exact_span_failures": audit.exact_span_failures,
        "distinct_approval_failures": audit.distinct_approval_failures,
        "split_counts": audit.split_counts,
        "dimension_counts": dict(sorted(dimension_counts.items())),
        "gold_label_counts": audit.gold_label_counts,
        "amended_minimum_cases_per_dimension": 3,
        "remediation_case_ids": list(REMEDIATION_IDS),
        "artifacts": [
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in artifact_paths
        ],
        "controls": {
            "human_decisions_modified": 0,
            "model_calls": 0,
            "paid_operations": 0,
            "pdf_downloads": 0,
        },
    }
    audit_path = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage2b-final-freeze-v2.json"
    )
    audit_path.write_text(json.dumps(freeze_audit, indent=2) + "\n", encoding="utf-8")
    print(workbook_path.relative_to(root))
    print(dataset_path.relative_to(root))
    print(audit_path.relative_to(root))
    print("status=passed cases=60 approved=60 frozen=true model_calls=0")


if __name__ == "__main__":
    main()
