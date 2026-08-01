"""Validate and preserve the human-approved V4.10 sealed held-out workbook."""

# ruff: noqa: E501 -- audit paths and exact-span checks are intentionally explicit.

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from claim_polygraph_ng.evaluation.v3_annotation import (
    V3ReviewDecision,
    load_v4_fresh_held_out_workbook,
)

ROOT = Path(__file__).parents[1]
SEED = ROOT / "benchmarks/verification_construction_v4_stage10_fresh_held_out_workbook_v1.json"
DESTINATION = ROOT / "benchmarks/verification_construction_v4_stage10_fresh_held_out_workbook_v1_APPROVED.json"
AUDIT = ROOT / "artifacts/evaluations/verification-construction-v4-stage10-review-gate-v1.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _immutable_case(case: object) -> dict[str, object]:
    payload = case.model_dump(mode="json")
    payload.pop("annotation", None)
    payload.pop("approval", None)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    seed = load_v4_fresh_held_out_workbook(SEED)
    submitted = load_v4_fresh_held_out_workbook(args.source)
    if len(submitted.cases) != 20:
        raise ValueError("V4.10 requires exactly 20 held-out cases")
    if [case.case_id for case in submitted.cases] != [case.case_id for case in seed.cases]:
        raise ValueError("submitted case identities differ from the collected packet")
    if any(
        _immutable_case(actual) != _immutable_case(expected)
        for actual, expected in zip(submitted.cases, seed.cases, strict=True)
    ):
        raise ValueError("a collected claim, source, proposal, or split was modified")

    label_counts: dict[str, int] = {}
    dimension_counts: dict[str, int] = {}
    annotation_dates: set[str] = set()
    approval_dates: set[str] = set()
    for case in submitted.cases:
        annotation = case.annotation
        approval = case.approval
        if annotation is None:
            raise ValueError(f"{case.case_id}: annotation missing")
        if approval is None or approval.decision is not V3ReviewDecision.APPROVE:
            raise ValueError(f"{case.case_id}: distinct approval missing")
        if annotation.annotator_identity != "Md Moshiur Rahman":
            raise ValueError(f"{case.case_id}: unexpected annotator identity")
        if approval.approver_identity != "Md Rashedul Islam":
            raise ValueError(f"{case.case_id}: unexpected approver identity")
        if annotation.annotator_identity == approval.approver_identity:
            raise ValueError(f"{case.case_id}: approval is not distinct")
        if not all((
            approval.checked_dimension,
            approval.checked_relation,
            approval.checked_claim_span,
            approval.checked_evidence_spans,
            approval.checked_gold_label,
            approval.checked_expected_state,
        )):
            raise ValueError(f"{case.case_id}: approval checklist incomplete")
        claim_span = annotation.claim_span
        if claim_span is not None and case.claim_text[claim_span.start_char:claim_span.end_char] != claim_span.quoted_text:
            raise ValueError(f"{case.case_id}: claim span is not exact")
        evidence_by_id = {item.evidence_id: item for item in case.evidence}
        for span in annotation.evidence_spans:
            evidence = evidence_by_id.get(span.evidence_id)
            if evidence is None or evidence.passage[span.start_char:span.end_char] != span.quoted_text:
                raise ValueError(f"{case.case_id}: evidence span is not exact")
        label = annotation.gold_label.value
        label_counts[label] = label_counts.get(label, 0) + 1
        dimension_counts[annotation.dimension_bucket] = dimension_counts.get(annotation.dimension_bucket, 0) + 1
        annotation_dates.add(annotation.annotated_on.isoformat())
        approval_dates.add(approval.approved_on.isoformat())

    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.source, DESTINATION)
    audit = {
        "audit_id": "verification-construction-v4-stage10-review-gate-v1",
        "status": "approved_awaiting_v4_11_freeze",
        "review_gate_passed": True,
        "held_out_execution_authorized": False,
        "approved_workbook": DESTINATION.relative_to(ROOT).as_posix(),
        "approved_workbook_sha256": _sha256(DESTINATION),
        "case_count": 20,
        "annotated_cases": 20,
        "distinctly_approved_cases": 20,
        "exact_span_failures": 0,
        "immutable_collection_changes": 0,
        "annotator": "Md Moshiur Rahman",
        "distinct_approver": "Md Rashedul Islam",
        "annotation_dates": sorted(annotation_dates),
        "approval_dates": sorted(approval_dates),
        "label_counts": dict(sorted(label_counts.items())),
        "dimension_counts": dict(sorted(dimension_counts.items())),
        "model_calls": 0,
        "paid_operations": 0,
        "held_out_cases_exposed_to_model": 0,
        "next_action": "Freeze the V4.11 held-out evaluation boundary before its one allowed execution",
    }
    AUDIT.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(DESTINATION.relative_to(ROOT))
    print(AUDIT.relative_to(ROOT))
    print("status=approved cases=20 approvals=20 model_calls=0")


if __name__ == "__main__":
    main()
