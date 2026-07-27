"""Immutable Phase 3 baseline manifest used by Phase 4 experiments."""

import hashlib
import json
from pathlib import Path

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel


class BaselineArtifact(DomainModel):
    """One content-addressed input to the Phase 4 comparison."""

    artifact_id: str = Field(pattern=r"^[a-z0-9_]+$")
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PilotGate(DomainModel):
    """Predeclared pilot limits that prevent result-dependent evaluation changes."""

    minimum_improved_cases: int = Field(ge=1)
    maximum_mean_cost_ratio: float = Field(gt=0)
    maximum_median_latency_ratio: float = Field(gt=0)
    verdict_regressions_allowed: int = Field(ge=0)
    provenance_regressions_allowed: int = Field(ge=0)


class Phase4ExperimentManifest(DomainModel):
    """Frozen baseline identity and experiment-selection contract."""

    manifest_id: str = Field(pattern=r"^[a-z0-9_-]+$")
    schema_version: int = Field(ge=1)
    dataset_id: str
    dataset_version: int = Field(ge=1)
    benchmark_case_ids: tuple[str, ...]
    pilot_case_ids: tuple[str, ...]
    pilot_selection_rationale: dict[str, str]
    artifacts: tuple[BaselineArtifact, ...]
    phase3_metrics: dict[str, float]
    pilot_gate: PilotGate

    @model_validator(mode="after")
    def validate_selection(self) -> "Phase4ExperimentManifest":
        if len(self.pilot_case_ids) != 3 or len(set(self.pilot_case_ids)) != 3:
            raise ValueError("pilot_case_ids must contain exactly three distinct cases")
        if not set(self.pilot_case_ids).issubset(self.benchmark_case_ids):
            raise ValueError("pilot cases must be members of the declared benchmark")
        if set(self.pilot_selection_rationale) != set(self.pilot_case_ids):
            raise ValueError("every pilot case requires one selection rationale")
        if len({item.artifact_id for item in self.artifacts}) != len(self.artifacts):
            raise ValueError("artifact IDs must be unique")
        if len({item.path for item in self.artifacts}) != len(self.artifacts):
            raise ValueError("artifact paths must be unique")
        return self


class ManifestVerification(DomainModel):
    """Offline verification result for a Phase 4 experiment manifest."""

    manifest_id: str
    valid: bool
    checked_artifact_count: int = Field(ge=0)
    errors: tuple[str, ...]


def load_phase4_manifest(path: str | Path) -> Phase4ExperimentManifest:
    """Load and validate the frozen experiment manifest."""
    return Phase4ExperimentManifest.model_validate_json(Path(path).read_text(encoding="utf-8"))


def verify_phase4_manifest(
    manifest: Phase4ExperimentManifest,
    project_root: str | Path,
) -> ManifestVerification:
    """Verify hashes and benchmark identities without network or model access."""
    root = Path(project_root).resolve()
    errors: list[str] = []
    checked = 0
    artifact_paths: dict[str, Path] = {}

    for artifact in manifest.artifacts:
        candidate = (root / artifact.path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            errors.append(f"{artifact.artifact_id}: path escapes project root")
            continue
        artifact_paths[artifact.artifact_id] = candidate
        if not candidate.is_file():
            errors.append(f"{artifact.artifact_id}: file is missing")
            continue
        checked += 1
        observed = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if observed != artifact.sha256:
            errors.append(f"{artifact.artifact_id}: SHA-256 mismatch")

    dataset_path = artifact_paths.get("benchmark")
    if dataset_path and dataset_path.is_file():
        try:
            dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
            if dataset.get("dataset_id") != manifest.dataset_id:
                errors.append("benchmark: dataset_id mismatch")
            if dataset.get("version") != manifest.dataset_version:
                errors.append("benchmark: dataset version mismatch")
            available_ids = {case.get("case_id") for case in dataset.get("cases", [])}
            missing = sorted(set(manifest.benchmark_case_ids) - available_ids)
            if missing:
                errors.append(f"benchmark: missing declared cases {', '.join(missing)}")
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"benchmark: cannot validate JSON ({exc})")

    gate_path = artifact_paths.get("phase3_gate_audit")
    if gate_path and gate_path.is_file():
        try:
            gate = json.loads(gate_path.read_text(encoding="utf-8"))
            if gate.get("dataset_id") != manifest.dataset_id:
                errors.append("phase3_gate_audit: dataset_id mismatch")
            if gate.get("dataset_version") != manifest.dataset_version:
                errors.append("phase3_gate_audit: dataset version mismatch")
            if gate.get("release_ready") is not True:
                errors.append("phase3_gate_audit: baseline is not release-ready")
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"phase3_gate_audit: cannot validate JSON ({exc})")

    return ManifestVerification(
        manifest_id=manifest.manifest_id,
        valid=not errors,
        checked_artifact_count=checked,
        errors=tuple(errors),
    )
