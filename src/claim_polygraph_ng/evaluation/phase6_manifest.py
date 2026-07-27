"""Offline Phase 6 baseline audit and content-addressed experiment manifest."""

import hashlib
import json
from pathlib import Path

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.evaluation.phase4_manifest import BaselineArtifact


class Phase6Thresholds(DomainModel):
    """Predeclared release gates for verification and judgment work."""

    maximum_verdict_regressions: int = Field(ge=0)
    minimum_required_check_trigger_recall: float = Field(ge=0, le=1)
    maximum_false_passed_incomplete_checks: int = Field(ge=0)
    minimum_numerical_operation_accuracy: float = Field(ge=0, le=1)
    minimum_temporal_relation_accuracy: float = Field(ge=0, le=1)
    maximum_out_of_packet_argument_references: int = Field(ge=0)
    maximum_unsupported_resolved_propositions: int = Field(ge=0)
    maximum_post_enforcement_constraint_violations: int = Field(ge=0)
    minimum_required_review_escalation_recall: float = Field(ge=0, le=1)
    minimum_citation_full_rate: float = Field(ge=0, le=1)
    maximum_added_deterministic_latency_ratio: float = Field(ge=0)
    maximum_added_deterministic_model_cost_usd: float = Field(ge=0)
    maximum_optional_model_cost_per_case_usd: float = Field(ge=0)


class Phase6CaseBaseline(DomainModel):
    """One immutable reviewed-case outcome from the existing default workflow."""

    case_id: str = Field(pattern=r"^CPNG-[0-9]{3}$")
    cohort: str = Field(pattern=r"^phase[23]$")
    expected_verdict: str
    observed_verdict: str
    verdict_matches: bool
    citation_fully_supported: bool
    duration_seconds: float = Field(ge=0)
    model_call_count: int = Field(ge=0)
    estimated_model_cost_usd: float = Field(ge=0)
    failure_class: str | None = None

    @model_validator(mode="after")
    def mismatch_requires_failure_class(self) -> "Phase6CaseBaseline":
        if self.verdict_matches == (self.failure_class is not None):
            raise ValueError("only verdict mismatches require a failure class")
        return self


class Phase6BaselineAudit(DomainModel):
    """Combined Phase 2 and Phase 3 baseline used by Phase 6."""

    audit_id: str = "phase6-stage6.0-baseline-v1"
    schema_version: int = 1
    dataset_id: str
    dataset_version: int = Field(ge=1)
    cases: tuple[Phase6CaseBaseline, ...] = Field(min_length=20, max_length=20)
    completed_case_count: int = Field(ge=0)
    correct_verdict_count: int = Field(ge=0)
    verdict_accuracy: float = Field(ge=0, le=1)
    citation_full_rate: float = Field(ge=0, le=1)
    duration_seconds: float = Field(ge=0)
    model_call_count: int = Field(ge=0)
    estimated_model_cost_usd: float = Field(ge=0)
    verification_metrics_available: bool = False
    measured_gaps: tuple[str, ...]
    limitations: tuple[str, ...]

    @model_validator(mode="after")
    def validate_aggregates(self) -> "Phase6BaselineAudit":
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValueError("baseline case IDs must be unique")
        if self.completed_case_count != len(self.cases):
            raise ValueError("completed count must match stored baseline cases")
        correct = sum(case.verdict_matches for case in self.cases)
        if self.correct_verdict_count != correct:
            raise ValueError("correct verdict count does not match cases")
        if abs(self.verdict_accuracy - correct / len(self.cases)) > 1e-9:
            raise ValueError("verdict accuracy does not match cases")
        citation_rate = sum(case.citation_fully_supported for case in self.cases) / len(self.cases)
        if abs(self.citation_full_rate - citation_rate) > 1e-9:
            raise ValueError("citation rate does not match cases")
        return self


class Phase6ExperimentManifest(DomainModel):
    """Locked inputs, baseline identity, and gates for Phase 6."""

    manifest_id: str = "phase6-verification-judgment-v1"
    schema_version: int = 1
    dataset_id: str
    dataset_version: int = Field(ge=1)
    benchmark_case_ids: tuple[str, ...] = Field(min_length=20, max_length=20)
    artifacts: tuple[BaselineArtifact, ...] = Field(min_length=6)
    baseline_audit_id: str
    thresholds: Phase6Thresholds
    paid_model_calls_authorized: bool = False
    live_retrieval_authorized: bool = False
    pdf_downloads_authorized: bool = False

    @model_validator(mode="after")
    def validate_locked_inputs(self) -> "Phase6ExperimentManifest":
        if len(set(self.benchmark_case_ids)) != 20:
            raise ValueError("exactly 20 distinct benchmark cases are required")
        if len({item.artifact_id for item in self.artifacts}) != len(self.artifacts):
            raise ValueError("artifact IDs must be unique")
        if len({item.path for item in self.artifacts}) != len(self.artifacts):
            raise ValueError("artifact paths must be unique")
        required = {"benchmark", "phase2_baseline", "phase3_baseline", "baseline_audit"}
        if not required.issubset(item.artifact_id for item in self.artifacts):
            raise ValueError("manifest is missing a required baseline artifact")
        return self


class Phase6ManifestVerification(DomainModel):
    """Offline Stage 6.0 verification result."""

    manifest_id: str
    valid: bool
    benchmark_reviewed: bool
    checked_artifact_count: int = Field(ge=0)
    errors: tuple[str, ...]


def load_phase6_baseline(path: str | Path) -> Phase6BaselineAudit:
    return Phase6BaselineAudit.model_validate_json(Path(path).read_text(encoding="utf-8"))


def load_phase6_manifest(path: str | Path) -> Phase6ExperimentManifest:
    return Phase6ExperimentManifest.model_validate_json(Path(path).read_text(encoding="utf-8"))


def verify_phase6_manifest(
    manifest: Phase6ExperimentManifest,
    project_root: str | Path,
) -> Phase6ManifestVerification:
    """Verify hashes and reviewed identities without network, PDF, or model access."""
    root = Path(project_root).resolve()
    errors: list[str] = []
    checked = 0
    paths: dict[str, Path] = {}
    for artifact in manifest.artifacts:
        candidate = (root / artifact.path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            errors.append(f"{artifact.artifact_id}: path escapes project root")
            continue
        paths[artifact.artifact_id] = candidate
        if not candidate.is_file():
            errors.append(f"{artifact.artifact_id}: file is missing")
            continue
        checked += 1
        if _sha256(candidate) != artifact.sha256:
            errors.append(f"{artifact.artifact_id}: SHA-256 mismatch")

    benchmark_reviewed = False
    benchmark_path = paths.get("benchmark")
    if benchmark_path and benchmark_path.is_file():
        try:
            benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
            if benchmark.get("dataset_id") != manifest.dataset_id:
                errors.append("benchmark: dataset_id mismatch")
            if benchmark.get("version") != manifest.dataset_version:
                errors.append("benchmark: dataset version mismatch")
            cases = benchmark.get("cases", [])
            ids = tuple(case.get("case_id") for case in cases)
            if ids != manifest.benchmark_case_ids:
                errors.append("benchmark: locked case IDs or order changed")
            benchmark_reviewed = bool(cases) and all(
                case.get("annotation_status") == "reviewed"
                and case.get("annotated_by")
                and case.get("approved_by")
                and str(case.get("annotated_by")).casefold()
                != str(case.get("approved_by")).casefold()
                for case in cases
            )
            if not benchmark_reviewed:
                errors.append("benchmark: human review or distinct approval is incomplete")
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"benchmark: cannot validate JSON ({exc})")

    baseline_path = paths.get("baseline_audit")
    if baseline_path and baseline_path.is_file():
        try:
            baseline = load_phase6_baseline(baseline_path)
            if baseline.audit_id != manifest.baseline_audit_id:
                errors.append("baseline_audit: audit_id mismatch")
            if baseline.dataset_id != manifest.dataset_id:
                errors.append("baseline_audit: dataset_id mismatch")
            if baseline.dataset_version != manifest.dataset_version:
                errors.append("baseline_audit: dataset version mismatch")
            if tuple(case.case_id for case in baseline.cases) != manifest.benchmark_case_ids:
                errors.append("baseline_audit: case IDs or order mismatch")
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"baseline_audit: cannot validate ({exc})")

    return Phase6ManifestVerification(
        manifest_id=manifest.manifest_id,
        valid=not errors,
        benchmark_reviewed=benchmark_reviewed,
        checked_artifact_count=checked,
        errors=tuple(errors),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
