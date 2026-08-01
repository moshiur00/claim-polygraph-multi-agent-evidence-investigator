"""V3.2 human annotation and distinct-approval gate tests."""

import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from claim_polygraph_ng.evaluation.v3_annotation import (
    V3AnnotationCase,
    V3DistinctApproval,
    V3HumanAnnotation,
    V3ReviewDecision,
    audit_annotation_workbook,
    load_annotation_workbook,
    load_sampling_quotas,
    load_v4_fresh_held_out_workbook,
    project_approved_dataset,
)
from claim_polygraph_ng.evaluation.v3_manifest import V3BenchmarkDataset, V3ConstructionGoldLabel


def test_generated_workbook_has_exact_machine_spans_and_no_fake_reviews() -> None:
    root = Path(__file__).parents[2]
    workbook = load_annotation_workbook(
        root / "benchmarks/verification_construction_v3_annotation_workbook_v1.json"
    )
    assert len(workbook.cases) == 60
    assert all(item.annotation is None for item in workbook.cases)
    assert all(item.approval is None for item in workbook.cases)
    assert all(item.proposal.model_calls == 0 for item in workbook.cases)
    assert all(
        item.claim_text[
            item.proposal.claim_span.start_char : item.proposal.claim_span.end_char
        ]
        == item.proposal.claim_span.quoted_text
        for item in workbook.cases
    )


def test_v4_stage10_workbook_is_sealed_held_out_and_unreviewed() -> None:
    root = Path(__file__).parents[2]
    workbook = load_v4_fresh_held_out_workbook(
        root / "benchmarks/verification_construction_v4_stage10_fresh_held_out_workbook_v1.json"
    )

    assert len(workbook.cases) == 20
    assert len({case.origin_family_id for case in workbook.cases}) == 10
    assert all(case.split.value == "held_out" for case in workbook.cases)
    assert all(case.annotation is None and case.approval is None for case in workbook.cases)
    assert all(case.proposal.model_calls == 0 for case in workbook.cases)

def test_pending_workbook_fails_closed_at_the_human_gate() -> None:
    root = Path(__file__).parents[2]
    workbook = load_annotation_workbook(
        root / "benchmarks/verification_construction_v3_annotation_workbook_v1.json"
    )
    label_quotas, dimension_quotas = load_sampling_quotas(
        root / "artifacts/evaluations/verification-construction-v3-sampling-policy-v1.json"
    )
    audit = audit_annotation_workbook(
        workbook,
        expected_label_quotas=label_quotas,
        expected_dimension_quotas=dimension_quotas,
    )

    assert audit.annotated_cases == 0
    assert audit.approved_cases == 0
    assert audit.ready_to_freeze is False
    assert audit.controls["fabricated_human_decisions"] == 0
    with pytest.raises(ValueError, match="not fully annotated and approved"):
        project_approved_dataset(
            workbook,
            evidence_packet_path="benchmarks/verification_construction_v3_annotation_workbook_v1.json",
        )


def test_same_person_cannot_annotate_and_approve() -> None:
    root = Path(__file__).parents[2]
    workbook = load_annotation_workbook(
        root / "benchmarks/verification_construction_v3_annotation_workbook_v1.json"
    )
    case = workbook.cases[0]
    annotation = V3HumanAnnotation(
        annotator_identity="Reviewer One",
        annotated_on=date(2026, 7, 30),
        dimension_bucket="duration",
        comparator_or_relation="equal",
        gold_label=V3ConstructionGoldLabel.DETERMINISTIC_CONSTRUCTIBLE,
        claim_span=case.proposal.claim_span,
        evidence_spans=case.proposal.evidence_spans,
        expected_verification_state="qualified",
    )
    approval = V3DistinctApproval(
        approver_identity="Reviewer One",
        approved_on=date(2026, 7, 30),
        decision=V3ReviewDecision.APPROVE,
        checked_dimension=True,
        checked_relation=True,
        checked_claim_span=True,
        checked_evidence_spans=True,
        checked_gold_label=True,
        checked_expected_state=True,
    )

    with pytest.raises(ValidationError, match="distinct person"):
        V3AnnotationCase.model_validate(
            {
                **case.model_dump(mode="json"),
                "annotation": annotation.model_dump(mode="json"),
                "approval": approval.model_dump(mode="json"),
            }
        )


def test_persisted_stage2_audit_matches_pending_workbook() -> None:
    root = Path(__file__).parents[2]
    workbook = load_annotation_workbook(
        root / "benchmarks/verification_construction_v3_annotation_workbook_v1.json"
    )
    label_quotas, dimension_quotas = load_sampling_quotas(
        root / "artifacts/evaluations/verification-construction-v3-sampling-policy-v1.json"
    )
    computed = audit_annotation_workbook(
        workbook,
        expected_label_quotas=label_quotas,
        expected_dimension_quotas=dimension_quotas,
    )
    persisted = json.loads(
        (
            root
            / "artifacts/evaluations/"
            "verification-construction-v3-stage2-annotation-gate-v1.json"
        ).read_text(encoding="utf-8")
    )

    assert persisted == computed.model_dump(mode="json")


def test_human_reviewed_workbook_preserves_approvals_and_quota_blocker() -> None:
    root = Path(__file__).parents[2]
    workbook = load_annotation_workbook(
        root / "benchmarks/verification_construction_v3_human_reviewed_v1.json"
    )
    label_quotas, dimension_quotas = load_sampling_quotas(
        root / "artifacts/evaluations/verification-construction-v3-sampling-policy-v1.json"
    )
    computed = audit_annotation_workbook(
        workbook,
        expected_label_quotas=label_quotas,
        expected_dimension_quotas=dimension_quotas,
    )
    persisted = json.loads(
        (
            root
            / "artifacts/evaluations/"
            "verification-construction-v3-stage2-human-review-audit-v1.json"
        ).read_text(encoding="utf-8")
    )
    remediation = json.loads(
        (
            root
            / "artifacts/evaluations/"
            "verification-construction-v3-stage2a-quota-remediation-v1.json"
        ).read_text(encoding="utf-8")
    )

    assert computed.annotated_cases == 60
    assert computed.approved_cases == 60
    assert computed.returned_cases == 0
    assert computed.exact_span_failures == 0
    assert computed.distinct_approval_failures == 0
    assert computed.ready_to_freeze is False
    assert persisted == computed.model_dump(mode="json")
    assert remediation["human_review_preserved"] is True
    assert remediation["controls"] == {
        "human_decisions_modified": 0,
        "model_calls": 0,
        "paid_operations": 0,
        "dataset_frozen": False,
    }
    assert remediation["recommended_policy_amendment"][
        "replacement_cases_required"
    ] == 5


def test_quota_remediation_preserves_reviews_and_limits_new_work_to_five() -> None:
    root = Path(__file__).parents[2]
    workbook = load_annotation_workbook(
        root / "benchmarks/verification_construction_v3_remediation_workbook_v2.json"
    )
    amendment = json.loads(
        (
            root
            / "artifacts/evaluations/"
            "verification-construction-v3-sampling-policy-amendment-v2.json"
        ).read_text(encoding="utf-8")
    )
    pending = [case for case in workbook.cases if case.annotation is None]
    approved = [case for case in workbook.cases if case.approval is not None]

    assert len(workbook.cases) == 60
    assert len(approved) == 55
    assert [case.case_id for case in pending] == amendment["replacement_policy"][
        "retired_case_ids"
    ]
    assert [case.proposal.dimension_bucket for case in pending] == [
        "pressure",
        "pressure",
        "pressure",
        "currency",
        "currency",
    ]
    assert all(case.proposal.model_calls == 0 for case in pending)
    assert Counter(case.split.value for case in workbook.cases) == {
        "calibration": 20,
        "development": 20,
        "held_out": 20,
    }
    assert Counter(case.origin_family_id for case in pending).most_common(1)[0][1] <= 2


def test_final_v3_freeze_is_complete_and_hash_verified() -> None:
    root = Path(__file__).parents[2]
    workbook = load_annotation_workbook(
        root / "benchmarks/verification_construction_v3_approved_frozen_v2.json"
    )
    dataset = V3BenchmarkDataset.model_validate_json(
        (
            root / "benchmarks/verification_construction_real_world_v3_frozen.json"
        ).read_text(encoding="utf-8")
    )
    audit = json.loads(
        (
            root
            / "artifacts/evaluations/"
            "verification-construction-v3-stage2b-final-freeze-v2.json"
        ).read_text(encoding="utf-8")
    )

    assert workbook.frozen is True
    assert dataset.frozen is True
    assert len(dataset.cases) == 60
    assert audit["status"] == "passed"
    assert audit["approved_cases"] == 60
    assert audit["controls"]["human_decisions_modified"] == 0
    for artifact in audit["artifacts"]:
        candidate = root / artifact["path"]
        assert hashlib.sha256(candidate.read_bytes()).hexdigest() == artifact["sha256"]
