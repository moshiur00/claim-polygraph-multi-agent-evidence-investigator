"""Import a validated V3.2 human-reviewed workbook without hiding quota drift."""

import json
from collections import Counter
from pathlib import Path

from claim_polygraph_ng.evaluation.v3_annotation import (
    audit_annotation_workbook,
    load_annotation_workbook,
    load_sampling_quotas,
)


SOURCE = Path(
    r"C:\Users\moshi\Downloads"
    r"\verification_construction_v3_annotation_workbook_v1_APPROVED_WITH_QUOTA_DEVIATION.json"
)


def main() -> None:
    root = Path(__file__).parents[1]
    workbook = load_annotation_workbook(SOURCE)
    label_quotas, dimension_quotas = load_sampling_quotas(
        root / "artifacts/evaluations/verification-construction-v3-sampling-policy-v1.json"
    )
    audit = audit_annotation_workbook(
        workbook,
        expected_label_quotas=label_quotas,
        expected_dimension_quotas=dimension_quotas,
    )
    if audit.annotated_cases != 60 or audit.approved_cases != 60:
        raise ValueError("the imported workbook is not fully annotated and approved")
    if audit.exact_span_failures or audit.distinct_approval_failures:
        raise ValueError("the imported workbook failed a human-review integrity gate")

    destination = (
        root / "benchmarks/verification_construction_v3_human_reviewed_v1.json"
    )
    destination.write_text(
        workbook.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    audit_destination = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage2-human-review-audit-v1.json"
    )
    audit_destination.write_text(
        audit.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )

    dimensions = Counter(
        case.annotation.dimension_bucket
        for case in workbook.cases
        if case.annotation is not None
    )
    labels = Counter(
        case.annotation.gold_label.value
        for case in workbook.cases
        if case.annotation is not None
    )
    exact_dimension_replacements = sum(
        max(0, dimensions.get(name, 0) - target)
        for name, target in dimension_quotas.items()
    )
    minimum_three_deficits = {
        name: max(0, 3 - dimensions.get(name, 0))
        for name in dimension_quotas
        if dimensions.get(name, 0) < 3
    }
    remediation = {
        "remediation_id": "verification-construction-v3-stage2a-quota-remediation-v1",
        "human_review_preserved": True,
        "reviewed_case_count": 60,
        "annotated_by": sorted(
            {case.annotation.annotator_identity for case in workbook.cases if case.annotation}
        ),
        "approved_by": sorted(
            {case.approval.approver_identity for case in workbook.cases if case.approval}
        ),
        "observed_dimension_counts": dict(sorted(dimensions.items())),
        "observed_label_counts": dict(sorted(labels.items())),
        "original_policy": {
            "status": "not_met",
            "exact_dimension_replacements_required": exact_dimension_replacements,
            "dimension_deficits": {
                name: max(0, target - dimensions.get(name, 0))
                for name, target in dimension_quotas.items()
                if dimensions.get(name, 0) < target
            },
            "label_deltas": {
                name: target - labels.get(name, 0)
                for name, target in label_quotas.items()
                if labels.get(name, 0) != target
            },
        },
        "recommended_policy_amendment": {
            "description": (
                "Keep the 60 reviewed cases, replace only enough excess-dimension "
                "cases to establish a minimum of three cases per dimension, and "
                "report label-stratified metrics instead of forcing exact label counts."
            ),
            "minimum_cases_per_dimension": 3,
            "replacement_cases_required": sum(minimum_three_deficits.values()),
            "required_new_dimensions": minimum_three_deficits,
            "reason": (
                "Natural human labels should not be changed to satisfy quotas. "
                "No assisted-construction model calls have occurred, so a transparent "
                "pre-experiment sampling-policy amendment remains possible."
            ),
            "requires_explicit_owner_approval": True,
        },
        "controls": {
            "human_decisions_modified": 0,
            "model_calls": 0,
            "paid_operations": 0,
            "dataset_frozen": False,
        },
    }
    remediation_destination = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage2a-quota-remediation-v1.json"
    )
    remediation_destination.write_text(
        json.dumps(remediation, indent=2) + "\n",
        encoding="utf-8",
    )
    print(destination.relative_to(root))
    print(audit_destination.relative_to(root))
    print(remediation_destination.relative_to(root))
    print(
        f"reviewed=60 approved=60 exact_replacements={exact_dimension_replacements} "
        f"recommended_replacements={sum(minimum_three_deficits.values())}"
    )


if __name__ == "__main__":
    main()
