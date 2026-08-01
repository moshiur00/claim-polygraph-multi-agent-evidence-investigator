"""Frozen V3.0 verification-construction experiment contracts."""

import hashlib
import json
from enum import StrEnum
from pathlib import Path

from pydantic import Field, model_validator

from claim_polygraph_ng.domain import NumericDimension
from claim_polygraph_ng.domain.base import DomainModel


class V3DatasetSplit(StrEnum):
    DEVELOPMENT = "development"
    CALIBRATION = "calibration"
    HELD_OUT = "held_out"


class V3ConstructionGoldLabel(StrEnum):
    DETERMINISTIC_CONSTRUCTIBLE = "deterministic_constructible"
    FALLBACK_ELIGIBLE = "fallback_eligible"
    UNCONSTRUCTIBLE = "unconstructible"
    NOT_APPLICABLE = "not_applicable"


class V3EvidenceSpan(DomainModel):
    evidence_id: str = Field(min_length=1, max_length=100)
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    quoted_text: str = Field(min_length=1, max_length=2_000)

    @model_validator(mode="after")
    def validate_offsets(self) -> "V3EvidenceSpan":
        if self.end_char <= self.start_char:
            raise ValueError("evidence span end must follow its start")
        return self


class V3BenchmarkCase(DomainModel):
    case_id: str = Field(pattern=r"^V3-[0-9]{3}$")
    split: V3DatasetSplit
    claim_text: str = Field(min_length=3, max_length=10_000)
    evidence_packet_path: str = Field(min_length=3, max_length=500)
    dimension: NumericDimension | None = None
    gold_label: V3ConstructionGoldLabel
    gold_claim_span: str | None = Field(default=None, min_length=1, max_length=2_000)
    gold_evidence_spans: tuple[V3EvidenceSpan, ...] = ()
    expected_verification_state: str | None = Field(
        default=None,
        pattern=r"^(verified|contradicted|qualified|insufficient|error)$",
    )
    ambiguity_notes: tuple[str, ...] = ()
    annotator_identity: str = Field(min_length=3, max_length=300)
    distinct_approver_identity: str = Field(min_length=3, max_length=300)

    @model_validator(mode="after")
    def validate_gold_annotation(self) -> "V3BenchmarkCase":
        constructible = self.gold_label in {
            V3ConstructionGoldLabel.DETERMINISTIC_CONSTRUCTIBLE,
            V3ConstructionGoldLabel.FALLBACK_ELIGIBLE,
        }
        if constructible != bool(
            self.gold_claim_span
            and self.gold_evidence_spans
            and self.expected_verification_state
        ):
            raise ValueError(
                "constructible cases require claim span, evidence spans, and outcome"
            )
        if (
            self.annotator_identity.casefold()
            == self.distinct_approver_identity.casefold()
        ):
            raise ValueError("benchmark annotation requires a distinct approver")
        return self


class V3BenchmarkDataset(DomainModel):
    dataset_id: str = Field(pattern=r"^verification-construction-real-world-v3$")
    schema_version: int = Field(ge=1)
    frozen: bool
    cases: tuple[V3BenchmarkCase, ...] = Field(min_length=50, max_length=100)

    @model_validator(mode="after")
    def validate_dataset(self) -> "V3BenchmarkDataset":
        ids = [case.case_id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("V3 benchmark case IDs must be unique")
        if not self.frozen:
            raise ValueError("evaluation requires a frozen benchmark")
        return self


class V3SamplingPolicy(DomainModel):
    target_case_count: int = Field(ge=50, le=100)
    split_quotas: dict[V3DatasetSplit, int]
    dimension_quotas: dict[str, int]
    construction_label_quotas: dict[V3ConstructionGoldLabel, int]
    source_class_quotas: dict[str, int]
    minimum_distinct_evidence_families: int = Field(ge=1)
    maximum_cases_per_origin_family: int = Field(ge=1)
    random_seed: int = Field(ge=0)
    selection_frozen_before_model_calls: bool

    @model_validator(mode="after")
    def validate_quotas(self) -> "V3SamplingPolicy":
        expected_splits = set(V3DatasetSplit)
        if set(self.split_quotas) != expected_splits:
            raise ValueError("every V3 dataset split requires a quota")
        for name, quotas in {
            "split": self.split_quotas,
            "dimension": self.dimension_quotas,
            "construction label": self.construction_label_quotas,
            "source class": self.source_class_quotas,
        }.items():
            if sum(quotas.values()) != self.target_case_count:
                raise ValueError(f"{name} quotas must sum to target_case_count")
        if not self.selection_frozen_before_model_calls:
            raise ValueError("sampling must be frozen before model calls")
        return self


class V3ExperimentBudget(DomainModel):
    stage_v3_0_model_calls: int = Field(ge=0)
    stage_v3_0_network_calls: int = Field(ge=0)
    maximum_assisted_calls_per_eligible_case: int = Field(ge=0, le=2)
    maximum_input_tokens_per_call: int = Field(ge=1)
    maximum_output_tokens_per_call: int = Field(ge=1)
    maximum_total_model_calls: int = Field(ge=0)
    maximum_total_cost_usd: float = Field(ge=0)
    maximum_cost_per_recovered_assertion_usd: float = Field(ge=0)
    search_calls_allowed: int = Field(ge=0)
    retries_after_valid_paid_receipt: int = Field(ge=0, le=1)

    @model_validator(mode="after")
    def keep_v3_0_zero_cost(self) -> "V3ExperimentBudget":
        if self.stage_v3_0_model_calls or self.stage_v3_0_network_calls:
            raise ValueError("Stage V3.0 must remain offline and zero-cost")
        return self


class V3PromotionThresholds(DomainModel):
    minimum_evidence_span_validity: float = Field(ge=0, le=1)
    maximum_unsafe_accepted_constructions: int = Field(ge=0)
    minimum_construction_precision: float = Field(ge=0, le=1)
    minimum_fallback_recall_gain: float = Field(ge=0, le=1)
    minimum_overall_construction_recall: float = Field(ge=0, le=1)
    minimum_human_review_routing_recall: float = Field(ge=0, le=1)
    maximum_publication_safety_regressions: int = Field(ge=0)
    maximum_verdict_regressions: int = Field(ge=0)
    maximum_duplicate_paid_operations: int = Field(ge=0)
    maximum_cost_per_recovered_assertion_usd: float = Field(ge=0)
    maximum_median_latency_overhead_seconds: float = Field(ge=0)
    maximum_p95_latency_overhead_seconds: float = Field(ge=0)
    distinct_human_approval_required: bool


class V3FrozenArtifact(DomainModel):
    artifact_id: str = Field(pattern=r"^[a-z0-9_]+$")
    path: str = Field(min_length=1, max_length=500)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class V3StageZeroManifest(DomainModel):
    manifest_id: str = Field(pattern=r"^verification-construction-v3-stage0$")
    schema_version: int = Field(ge=1)
    status: str = Field(pattern=r"^frozen$")
    artifacts: tuple[V3FrozenArtifact, ...] = Field(min_length=3)
    sampling_policy: V3SamplingPolicy
    budget: V3ExperimentBudget
    promotion_thresholds: V3PromotionThresholds
    model_provider_selected: bool
    model_calls_made: int = Field(ge=0)
    network_calls_made: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_freeze(self) -> "V3StageZeroManifest":
        if self.model_provider_selected:
            raise ValueError("V3.0 freezes policy before selecting a model provider")
        if self.model_calls_made or self.network_calls_made:
            raise ValueError("V3.0 cannot record external calls")
        if len({item.artifact_id for item in self.artifacts}) != len(self.artifacts):
            raise ValueError("V3 artifact IDs must be unique")
        return self


class V3ManifestAudit(DomainModel):
    manifest_id: str
    valid: bool
    checked_artifact_count: int = Field(ge=0)
    errors: tuple[str, ...]


def load_v3_manifest(path: str | Path) -> V3StageZeroManifest:
    return V3StageZeroManifest.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


def verify_v3_manifest(
    manifest: V3StageZeroManifest,
    project_root: str | Path,
) -> V3ManifestAudit:
    root = Path(project_root).resolve()
    errors: list[str] = []
    checked = 0
    for artifact in manifest.artifacts:
        candidate = (root / artifact.path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            errors.append(f"{artifact.artifact_id}: path escapes project root")
            continue
        if not candidate.is_file():
            errors.append(f"{artifact.artifact_id}: file is missing")
            continue
        checked += 1
        if hashlib.sha256(candidate.read_bytes()).hexdigest() != artifact.sha256:
            errors.append(f"{artifact.artifact_id}: SHA-256 mismatch")
    return V3ManifestAudit(
        manifest_id=manifest.manifest_id,
        valid=not errors,
        checked_artifact_count=checked,
        errors=tuple(errors),
    )


def load_json_object(path: str | Path) -> dict:
    """Read an auxiliary frozen JSON policy for tests and audit tooling."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("expected a JSON object")
    return payload
