"""Record the named annotator's review of all V3.8 adjudication records."""

import json
from pathlib import Path


def main() -> None:
    root = Path(__file__).parents[1]
    path = (
        root
        / "benchmarks/"
        "verification_construction_v3_stage8_adjudication_workbook_v1.json"
    )
    workbook = json.loads(path.read_text(encoding="utf-8"))
    if len(workbook["cases"]) != 7:
        raise ValueError("V3.8 adjudication requires exactly seven records")
    for case in workbook["cases"]:
        review = case["prefilled_adjudication"]
        if review["annotator_identity"] != "Md Moshiur Rahman":
            raise ValueError("unexpected V3.8 annotator identity")
        review.update(
            {
                "annotated_on": "2026-07-31",
                "review_status": "reviewed_and_accepted",
                "checked_claim_span": True,
                "checked_evidence_bindings": True,
                "checked_material_operands": True,
                "checked_expected_state_compatibility": True,
                "checked_fail_closed_behavior": True,
            }
        )
    workbook["annotation_status"] = "complete"
    workbook["distinct_approval_status"] = "pending"
    path.write_text(json.dumps(workbook, indent=2) + "\n", encoding="utf-8")
    print(path.relative_to(root))
    print("annotated=7 distinct_approval=pending")


if __name__ == "__main__":
    main()
