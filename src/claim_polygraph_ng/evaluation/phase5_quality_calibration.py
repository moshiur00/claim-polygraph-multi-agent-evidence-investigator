"""Human-reviewable calibration contract for source-quality dimensions."""

import json
from pathlib import Path

from pydantic import Field, model_validator

from claim_polygraph_ng.analysis.source_quality import (
    QualityFinding,
    SourceQualityDimension,
    SourceQualityMetadata,
    assess_source_quality,
)
from claim_polygraph_ng.domain.base import DomainModel


class SourceQualityCalibrationCase(DomainModel):
    """One metadata scenario with proposed dimension-level gold labels."""

    case_id: str = Field(pattern=r"^QUAL-[0-9]{3}$")
    description: str
    metadata: SourceQualityMetadata
    expected_findings: dict[SourceQualityDimension, QualityFinding]
    rationale: str

    @model_validator(mode="after")
    def require_every_dimension(self) -> "SourceQualityCalibrationCase":
        if set(self.expected_findings) != set(SourceQualityDimension):
            raise ValueError("every source-quality dimension requires a calibration label")
        return self


class SourceQualityCalibrationSet(DomainModel):
    """Versioned calibration labels with a genuine human-review boundary."""

    dataset_id: str
    version: int = Field(ge=1)
    status: str = Field(pattern=r"^(ai_assisted_draft|reviewed)$")
    drafted_by: str
    annotated_by: str | None = None
    approved_by: str | None = None
    approval_date: str | None = None
    cases: tuple[SourceQualityCalibrationCase, ...] = Field(min_length=5)

    @model_validator(mode="after")
    def validate_review(self) -> "SourceQualityCalibrationSet":
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValueError("calibration case IDs must be unique")
        if self.status == "reviewed":
            if not all((self.annotated_by, self.approved_by, self.approval_date)):
                raise ValueError("reviewed calibration requires annotation and approval metadata")
            if self.annotated_by.casefold() == self.approved_by.casefold():
                raise ValueError("annotator and approver must be distinct")
        return self


class SourceQualityCalibrationResult(DomainModel):
    """Agreement result without conflating an AI draft with human validation."""

    dataset_id: str
    dataset_version: int
    review_status: str
    case_count: int = Field(ge=0)
    dimension_count: int = Field(ge=0)
    matching_dimension_count: int = Field(ge=0)
    agreement: float = Field(ge=0, le=1)
    minimum_agreement: float = Field(ge=0, le=1)
    agreement_gate_passed: bool
    human_review_gate_passed: bool
    valid: bool
    mismatches: tuple[str, ...]
    limitation: str


def load_source_quality_calibration(path: str | Path) -> SourceQualityCalibrationSet:
    return SourceQualityCalibrationSet.model_validate_json(Path(path).read_text(encoding="utf-8"))


def evaluate_source_quality_calibration(
    calibration: SourceQualityCalibrationSet, *, minimum_agreement: float = 0.85
) -> SourceQualityCalibrationResult:
    """Compare deterministic output with proposed labels and enforce human review."""
    matches = 0
    total = 0
    mismatches = []
    for case in calibration.cases:
        assessment = assess_source_quality(case.metadata)
        observed = {item.dimension: item.finding for item in assessment.dimensions}
        for dimension, expected in case.expected_findings.items():
            total += 1
            if observed[dimension] is expected:
                matches += 1
            else:
                mismatches.append(
                    f"{case.case_id}:{dimension.value}: "
                    f"expected {expected.value}, observed {observed[dimension].value}"
                )
    agreement = matches / total if total else 0
    agreement_passed = agreement >= minimum_agreement
    human_passed = calibration.status == "reviewed"
    return SourceQualityCalibrationResult(
        dataset_id=calibration.dataset_id,
        dataset_version=calibration.version,
        review_status=calibration.status,
        case_count=len(calibration.cases),
        dimension_count=total,
        matching_dimension_count=matches,
        agreement=agreement,
        minimum_agreement=minimum_agreement,
        agreement_gate_passed=agreement_passed,
        human_review_gate_passed=human_passed,
        valid=agreement_passed and human_passed,
        mismatches=tuple(mismatches),
        limitation=(
            "Agreement with an AI-assisted draft checks implementation consistency only; "
            "distinct human annotation and approval are required for calibration validity."
        ),
    )


def export_source_quality_calibration_result(
    result: SourceQualityCalibrationResult, path: str | Path
) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output
