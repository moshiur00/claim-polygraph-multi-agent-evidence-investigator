"""Versioned empirical confidence-calibration contracts."""

from enum import StrEnum

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel


class CalibrationSplit(StrEnum):
    FIT = "fit"
    EVALUATION = "evaluation"


class CalibrationStatus(StrEnum):
    INSUFFICIENT_DATA = "insufficient_data"
    NOT_PROMOTED = "not_promoted"
    PROMOTED = "promoted"


class CalibrationFeatureVector(DomainModel):
    """Frozen observable features; readiness state is intentionally absent."""

    evidence_quality: float = Field(ge=0, le=1)
    independent_family_count: int = Field(ge=0, le=100)
    contradiction_balance: float = Field(ge=-1, le=1)
    citation_support_rate: float = Field(ge=0, le=1)
    unresolved_verification_rate: float = Field(ge=0, le=1)
    retrieval_coverage: float = Field(ge=0, le=1)
    model_disagreement: float = Field(ge=0, le=1)


class CalibrationCase(DomainModel):
    case_id: str = Field(min_length=3, max_length=200)
    group_id: str = Field(min_length=3, max_length=200)
    domain: str = Field(min_length=2, max_length=100)
    predicted_label: str = Field(min_length=2, max_length=100)
    reference_label: str = Field(min_length=2, max_length=100)
    correct: bool
    split: CalibrationSplit
    features: CalibrationFeatureVector


class ConfidenceCalibrationDataset(DomainModel):
    dataset_id: str = Field(min_length=3, max_length=200)
    version: int = Field(ge=1)
    cases: tuple[CalibrationCase, ...]
    feature_version: str = Field(
        default="confidence-features-v1",
        pattern=r"^confidence-features-v1$",
    )

    @model_validator(mode="after")
    def validate_split_isolation(self) -> "ConfidenceCalibrationDataset":
        case_ids = [item.case_id for item in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("calibration case IDs must be unique")
        fit_groups = {item.group_id for item in self.cases if item.split is CalibrationSplit.FIT}
        evaluation_groups = {
            item.group_id for item in self.cases if item.split is CalibrationSplit.EVALUATION
        }
        if fit_groups & evaluation_groups:
            raise ValueError("claim groups cannot cross fit and evaluation splits")
        return self


class ReliabilityBin(DomainModel):
    lower_bound: float = Field(ge=0, le=1)
    upper_bound: float = Field(ge=0, le=1)
    count: int = Field(ge=0)
    mean_confidence: float | None = Field(default=None, ge=0, le=1)
    observed_accuracy: float | None = Field(default=None, ge=0, le=1)


class CalibrationMetrics(DomainModel):
    method: str
    evaluation_count: int = Field(ge=1)
    brier_score: float = Field(ge=0, le=1)
    expected_calibration_error: float = Field(ge=0, le=1)
    reliability_bins: tuple[ReliabilityBin, ...]
    abstention_threshold: float = Field(ge=0, le=1)
    coverage_under_abstention: float = Field(ge=0, le=1)
    accepted_accuracy: float | None = Field(default=None, ge=0, le=1)


class ConfidenceCalibrator(DomainModel):
    calibrator_version: str = Field(pattern=r"^confidence-calibrator-v1$")
    method: str
    feature_version: str = Field(pattern=r"^confidence-features-v1$")
    parameters: tuple[float, ...]
    observational_only: bool = True


class ConfidenceCalibrationResult(DomainModel):
    evaluation_id: str
    dataset_id: str
    dataset_version: int
    status: CalibrationStatus
    total_case_count: int = Field(ge=0)
    reviewed_candidate_count: int = Field(default=0, ge=0)
    excluded_incomplete_feature_count: int = Field(default=0, ge=0)
    compatible_public_case_count: int = Field(default=0, ge=0)
    fit_case_count: int = Field(ge=0)
    evaluation_case_count: int = Field(ge=0)
    domain_counts: dict[str, int]
    label_counts: dict[str, int]
    insufficiency_reasons: tuple[str, ...] = ()
    compared_metrics: tuple[CalibrationMetrics, ...] = ()
    selected_calibrator: ConfidenceCalibrator | None = None
    confidence_available: bool
    readiness_remains_distinct: bool = True
    model_calls: int = 0

    @model_validator(mode="after")
    def validate_promotion_state(self) -> "ConfidenceCalibrationResult":
        if self.excluded_incomplete_feature_count > self.reviewed_candidate_count:
            raise ValueError("excluded cases cannot exceed reviewed candidates")
        promoted = self.status is CalibrationStatus.PROMOTED
        if promoted != self.confidence_available:
            raise ValueError("confidence is available only for a promoted calibrator")
        if promoted != (self.selected_calibrator is not None):
            raise ValueError("only promotion may select a calibrator")
        if self.status is CalibrationStatus.INSUFFICIENT_DATA and not self.insufficiency_reasons:
            raise ValueError("insufficient calibration requires explicit reasons")
        return self


class CalibratedConfidence(DomainModel):
    """Provenanced probability kept separate from readiness."""

    probability: float = Field(ge=0, le=1)
    calibrator_version: str
    dataset_id: str
    dataset_version: int = Field(ge=1)
    feature_version: str
    observational_only: bool = True
