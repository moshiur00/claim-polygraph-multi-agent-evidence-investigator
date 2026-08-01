"""V3.2 human annotation, distinct approval, and dataset-freeze contracts."""

import json
from collections import Counter
from datetime import date
from enum import StrEnum
from pathlib import Path

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.evaluation.v3_manifest import (
    V3BenchmarkCase,
    V3BenchmarkDataset,
    V3ConstructionGoldLabel,
    V3DatasetSplit,
    V3EvidenceSpan,
)


class V3ReviewDecision(StrEnum):
    APPROVE = "approve"
    RETURN_FOR_REVISION = "return_for_revision"


class V3ExactTextSpan(DomainModel):
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    quoted_text: str = Field(min_length=1, max_length=2_000)

    @model_validator(mode="after")
    def validate_length(self) -> "V3ExactTextSpan":
        if self.end_char <= self.start_char:
            raise ValueError("span end must follow span start")
        if self.end_char - self.start_char != len(self.quoted_text):
            raise ValueError("span offsets must match quoted text length")
        return self

    def validate_against(self, text: str) -> None:
        if text[self.start_char : self.end_char] != self.quoted_text:
            raise ValueError("quoted text does not match the exact source offsets")


class V3ReviewEvidence(DomainModel):
    evidence_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=500)
    url: str = Field(min_length=8, max_length=2_000)
    source_class: str = Field(min_length=2, max_length=100)
    passage: str = Field(min_length=1, max_length=10_000)


class V3MachinePreparedProposal(DomainModel):
    dimension_bucket: str | None = None
    comparator_or_relation: str | None = None
    claim_span: V3ExactTextSpan
    evidence_spans: tuple[V3EvidenceSpan, ...] = ()
    suggested_gold_label: V3ConstructionGoldLabel | None = None
    suggested_verification_state: str | None = None
    machine_notes: tuple[str, ...] = ()
    model_calls: int = Field(default=0, ge=0)


class V3HumanAnnotation(DomainModel):
    annotator_identity: str = Field(min_length=3, max_length=300)
    annotated_on: date
    dimension_bucket: str
    comparator_or_relation: str
    gold_label: V3ConstructionGoldLabel
    claim_span: V3ExactTextSpan | None = None
    evidence_spans: tuple[V3EvidenceSpan, ...] = ()
    expected_verification_state: str | None = Field(
        default=None,
        pattern=r"^(verified|contradicted|qualified|insufficient|error)$",
    )
    ambiguity_notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_constructible_fields(self) -> "V3HumanAnnotation":
        constructible = self.gold_label in {
            V3ConstructionGoldLabel.DETERMINISTIC_CONSTRUCTIBLE,
            V3ConstructionGoldLabel.FALLBACK_ELIGIBLE,
        }
        complete = bool(
            self.claim_span
            and self.evidence_spans
            and self.expected_verification_state
        )
        if constructible != complete:
            raise ValueError(
                "constructible annotations require exact claim/evidence spans and state"
            )
        return self


class V3DistinctApproval(DomainModel):
    approver_identity: str = Field(min_length=3, max_length=300)
    approved_on: date
    decision: V3ReviewDecision
    checked_dimension: bool
    checked_relation: bool
    checked_claim_span: bool
    checked_evidence_spans: bool
    checked_gold_label: bool
    checked_expected_state: bool
    notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def require_all_checks_for_approval(self) -> "V3DistinctApproval":
        checks = (
            self.checked_dimension,
            self.checked_relation,
            self.checked_claim_span,
            self.checked_evidence_spans,
            self.checked_gold_label,
            self.checked_expected_state,
        )
        if self.decision is V3ReviewDecision.APPROVE and not all(checks):
            raise ValueError("approval requires every V3.2 checkpoint")
        return self


class V3AnnotationCase(DomainModel):
    case_id: str = Field(pattern=r"^V3-[0-9]{3}$")
    source_candidate_id: str
    split: V3DatasetSplit
    origin_family_id: str
    claim_text: str = Field(min_length=3, max_length=10_000)
    evidence: tuple[V3ReviewEvidence, ...] = Field(min_length=1)
    proposal: V3MachinePreparedProposal
    annotation: V3HumanAnnotation | None = None
    approval: V3DistinctApproval | None = None

    @model_validator(mode="after")
    def validate_review_integrity(self) -> "V3AnnotationCase":
        self.proposal.claim_span.validate_against(self.claim_text)
        evidence_by_id = {item.evidence_id: item for item in self.evidence}
        for span in self.proposal.evidence_spans:
            evidence = evidence_by_id.get(span.evidence_id)
            if evidence is None:
                raise ValueError("proposal span references missing evidence")
            if evidence.passage[span.start_char : span.end_char] != span.quoted_text:
                raise ValueError("proposal evidence span offsets are invalid")
        if self.annotation:
            if self.annotation.claim_span:
                self.annotation.claim_span.validate_against(self.claim_text)
            for span in self.annotation.evidence_spans:
                evidence = evidence_by_id.get(span.evidence_id)
                if evidence is None:
                    raise ValueError("annotation span references missing evidence")
                if evidence.passage[span.start_char : span.end_char] != span.quoted_text:
                    raise ValueError("annotation evidence span offsets are invalid")
        if self.approval:
            if self.annotation is None:
                raise ValueError("approval requires a completed annotation")
            if (
                self.approval.approver_identity.casefold()
                == self.annotation.annotator_identity.casefold()
            ):
                raise ValueError("V3.2 approval must be performed by a distinct person")
        return self


class V3AnnotationWorkbook(DomainModel):
    workbook_id: str = "verification-construction-v3-annotation-workbook-v1"
    schema_version: int = 1
    frozen: bool = False
    cases: tuple[V3AnnotationCase, ...] = Field(min_length=50, max_length=100)

    @model_validator(mode="after")
    def validate_workbook(self) -> "V3AnnotationWorkbook":
        ids = [item.case_id for item in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("annotation case IDs must be unique")
        return self


class V3ReplacementCalibrationWorkbook(DomainModel):
    """A sealed replacement-calibration review packet for V3.6a.

    This is deliberately separate from the original 60-case workbook. It
    permits exactly twenty newly collected cases without weakening the frozen
    V3.2 workbook cardinality contract.
    """

    workbook_id: str = (
        "verification-construction-v3-stage6a-replacement-calibration-workbook-v1"
    )
    schema_version: int = 1
    frozen: bool = False
    cases: tuple[V3AnnotationCase, ...] = Field(min_length=20, max_length=20)

    @model_validator(mode="after")
    def validate_workbook(self) -> "V3ReplacementCalibrationWorkbook":
        ids = [item.case_id for item in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("replacement calibration case IDs must be unique")
        families = {item.origin_family_id for item in self.cases}
        if len(families) < 10:
            raise ValueError(
                "replacement calibration requires at least ten origin families"
            )
        if any(item.split is not V3DatasetSplit.CALIBRATION for item in self.cases):
            raise ValueError("replacement calibration cases must use calibration split")
        return self


def load_replacement_calibration_workbook(
    path: str | Path,
) -> V3ReplacementCalibrationWorkbook:
    return V3ReplacementCalibrationWorkbook.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


class V4FreshHeldOutWorkbook(DomainModel):
    """A sealed 20-case held-out review packet with independent origin families."""

    workbook_id: str = "verification-construction-v4-stage10-fresh-held-out-workbook-v1"
    schema_version: int = 1
    frozen: bool = False
    cases: tuple[V3AnnotationCase, ...] = Field(min_length=20, max_length=20)

    @model_validator(mode="after")
    def validate_workbook(self) -> "V4FreshHeldOutWorkbook":
        ids = [item.case_id for item in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("fresh held-out case IDs must be unique")
        if len({item.origin_family_id for item in self.cases}) < 10:
            raise ValueError("fresh held-out review requires at least ten origin families")
        if any(item.split is not V3DatasetSplit.HELD_OUT for item in self.cases):
            raise ValueError("fresh held-out cases must use held-out split")
        return self


def load_v4_fresh_held_out_workbook(path: str | Path) -> V4FreshHeldOutWorkbook:
    return V4FreshHeldOutWorkbook.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


class V3AnnotationGateAudit(DomainModel):
    audit_id: str = "verification-construction-v3-stage2-annotation-gate-v1"
    total_cases: int
    annotated_cases: int
    approved_cases: int
    returned_cases: int
    exact_span_failures: int
    distinct_approval_failures: int
    split_counts: dict[str, int]
    gold_label_counts: dict[str, int]
    dimension_counts: dict[str, int]
    ready_to_freeze: bool
    blocking_reasons: tuple[str, ...]
    controls: dict[str, int | float | bool]


def load_annotation_workbook(path: str | Path) -> V3AnnotationWorkbook:
    return V3AnnotationWorkbook.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


def audit_annotation_workbook(
    workbook: V3AnnotationWorkbook,
    *,
    expected_label_quotas: dict[str, int] | None = None,
    expected_dimension_quotas: dict[str, int] | None = None,
) -> V3AnnotationGateAudit:
    annotated = [item for item in workbook.cases if item.annotation is not None]
    approved = [
        item
        for item in workbook.cases
        if item.approval and item.approval.decision is V3ReviewDecision.APPROVE
    ]
    returned = [
        item
        for item in workbook.cases
        if item.approval
        and item.approval.decision is V3ReviewDecision.RETURN_FOR_REVISION
    ]
    label_counts = Counter(
        item.annotation.gold_label.value for item in annotated if item.annotation
    )
    dimension_counts = Counter(
        item.annotation.dimension_bucket for item in annotated if item.annotation
    )
    split_counts = Counter(item.split.value for item in workbook.cases)
    blockers: list[str] = []
    if len(annotated) != len(workbook.cases):
        blockers.append("Every case requires a completed human annotation.")
    if len(approved) != len(workbook.cases):
        blockers.append("Every case requires explicit distinct approval.")
    if returned:
        blockers.append("Returned cases must be revised and approved.")
    if expected_label_quotas and dict(label_counts) != expected_label_quotas:
        blockers.append("Construction-label quotas do not match the frozen policy.")
    if expected_dimension_quotas and dict(dimension_counts) != expected_dimension_quotas:
        blockers.append("Dimension quotas do not match the frozen policy.")
    return V3AnnotationGateAudit(
        total_cases=len(workbook.cases),
        annotated_cases=len(annotated),
        approved_cases=len(approved),
        returned_cases=len(returned),
        exact_span_failures=0,
        distinct_approval_failures=0,
        split_counts=dict(sorted(split_counts.items())),
        gold_label_counts=dict(sorted(label_counts.items())),
        dimension_counts=dict(sorted(dimension_counts.items())),
        ready_to_freeze=not blockers,
        blocking_reasons=tuple(blockers),
        controls={
            "model_calls": 0,
            "estimated_cost_usd": 0.0,
            "fabricated_human_decisions": 0,
        },
    )


def project_approved_dataset(
    workbook: V3AnnotationWorkbook,
    *,
    evidence_packet_path: str,
) -> V3BenchmarkDataset:
    audit = audit_annotation_workbook(workbook)
    if not audit.ready_to_freeze:
        raise ValueError("V3.2 workbook is not fully annotated and approved")
    cases: list[V3BenchmarkCase] = []
    for item in workbook.cases:
        assert item.annotation is not None
        assert item.approval is not None
        annotation = item.annotation
        cases.append(
            V3BenchmarkCase(
                case_id=item.case_id,
                split=item.split,
                claim_text=item.claim_text,
                evidence_packet_path=evidence_packet_path,
                dimension=_schema_dimension(annotation.dimension_bucket),
                gold_label=annotation.gold_label,
                gold_claim_span=(
                    annotation.claim_span.quoted_text
                    if annotation.claim_span
                    else None
                ),
                gold_evidence_spans=annotation.evidence_spans,
                expected_verification_state=annotation.expected_verification_state,
                ambiguity_notes=annotation.ambiguity_notes,
                annotator_identity=annotation.annotator_identity,
                distinct_approver_identity=item.approval.approver_identity,
            )
        )
    return V3BenchmarkDataset(
        dataset_id="verification-construction-real-world-v3",
        schema_version=1,
        frozen=True,
        cases=tuple(cases),
    )


def _schema_dimension(value: str):
    from claim_polygraph_ng.domain import NumericDimension

    mapping = {
        "percentage_or_rate": NumericDimension.PERCENTAGE,
        "count": NumericDimension.COUNT,
        "pressure": NumericDimension.PRESSURE,
        "currency": NumericDimension.CURRENCY,
        "speed": NumericDimension.SPEED,
        "temperature": NumericDimension.TEMPERATURE,
        "duration": NumericDimension.DURATION,
        "distance_or_mass": NumericDimension.UNKNOWN,
        "temporal_instant": None,
        "temporal_interval_or_status": None,
    }
    if value not in mapping:
        raise ValueError(f"unsupported V3 dimension bucket: {value}")
    return mapping[value]


def load_sampling_quotas(path: str | Path) -> tuple[dict[str, int], dict[str, int]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return payload["construction_label_quotas"], payload["dimension_quotas"]
