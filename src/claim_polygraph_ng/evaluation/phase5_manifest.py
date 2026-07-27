"""Locked experiment and fixture contracts for Phase 5 provenance work."""

import hashlib
import json
from enum import StrEnum
from pathlib import Path

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.evaluation.phase4_manifest import BaselineArtifact


class ProvenanceRelationship(StrEnum):
    """Reviewed relationship between two fixture sources."""

    SAME_DOCUMENT = "same_document"
    MIRROR = "mirror"
    SYNDICATED_COPY = "syndicated_copy"
    TRANSLATION = "translation"
    SUMMARY_OF = "summary_of"
    CITES = "cites"
    DERIVED_FROM = "derived_from"
    COMMON_ORIGIN = "common_origin"
    INDEPENDENT = "independent"
    UNRESOLVED = "unresolved"


class ProvenanceFixtureSource(DomainModel):
    """Small rights-safe source representation used for provenance evaluation."""

    source_id: str = Field(pattern=r"^SRC-[0-9]{3}$")
    url: str
    title: str
    publisher: str
    published_at: str
    excerpt: str = Field(min_length=20)
    rights_basis: str = Field(pattern=r"^synthetic_project_authored$")


class ProvenanceFixtureRelationship(DomainModel):
    """Expected pair-level relationship and evidence-family membership."""

    left_source_id: str
    right_source_id: str
    relationship: ProvenanceRelationship
    same_canonical_document: bool
    same_evidence_family: bool
    rationale: str


class ProvenanceFixtureCase(DomainModel):
    """One predeclared provenance scenario."""

    case_id: str = Field(pattern=r"^PROV-[0-9]{3}$")
    scenario: str
    component_claim: str
    sources: tuple[ProvenanceFixtureSource, ...] = Field(min_length=2)
    expected_relationships: tuple[ProvenanceFixtureRelationship, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_references(self) -> "ProvenanceFixtureCase":
        source_ids = {source.source_id for source in self.sources}
        if len(source_ids) != len(self.sources):
            raise ValueError("fixture source IDs must be unique within a case")
        for relationship in self.expected_relationships:
            if relationship.left_source_id not in source_ids:
                raise ValueError("left relationship source is missing")
            if relationship.right_source_id not in source_ids:
                raise ValueError("right relationship source is missing")
            if relationship.left_source_id == relationship.right_source_id:
                raise ValueError("a source cannot be related to itself")
        return self


class ProvenanceBenchmark(DomainModel):
    """Frozen, rights-safe Phase 5 evaluation dataset."""

    dataset_id: str
    version: int = Field(ge=1)
    status: str = Field(pattern=r"^(draft|reviewed)$")
    annotated_by: str | None = None
    approved_by: str | None = None
    approval_date: str | None = None
    cases: tuple[ProvenanceFixtureCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_review(self) -> "ProvenanceBenchmark":
        case_ids = [case.case_id for case in self.cases]
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("fixture case IDs must be unique")
        if self.status == "reviewed":
            if not all((self.annotated_by, self.approved_by, self.approval_date)):
                raise ValueError("reviewed benchmark requires annotation and approval metadata")
            if self.annotated_by.casefold() == self.approved_by.casefold():
                raise ValueError("annotator and approver must be distinct")
        return self


class ProvenanceThresholds(DomainModel):
    """Predeclared Phase 5 release thresholds."""

    canonical_precision: float = Field(ge=0, le=1)
    exact_duplicate_precision: float = Field(ge=0, le=1)
    exact_duplicate_recall: float = Field(ge=0, le=1)
    derivative_precision: float = Field(ge=0, le=1)
    derivative_recall: float = Field(ge=0, le=1)
    family_accuracy: float = Field(ge=0, le=1)
    maximum_false_independent_rate: float = Field(ge=0, le=1)
    maximum_verdict_regressions: int = Field(ge=0)
    minimum_citation_full_rate: float = Field(ge=0, le=1)
    maximum_added_latency_ratio: float = Field(ge=0)
    maximum_added_model_cost_usd: float = Field(ge=0)


class Phase5ExperimentManifest(DomainModel):
    """Content-addressed Stage 5.0 experiment definition."""

    manifest_id: str = Field(pattern=r"^[a-z0-9_-]+$")
    schema_version: int = Field(ge=1)
    provenance_dataset_id: str
    provenance_dataset_version: int = Field(ge=1)
    fixture_case_ids: tuple[str, ...] = Field(min_length=10)
    artifacts: tuple[BaselineArtifact, ...]
    thresholds: ProvenanceThresholds
    paid_model_calls_authorized: bool = False
    pdf_downloads_authorized: bool = False

    @model_validator(mode="after")
    def validate_fixture_selection(self) -> "Phase5ExperimentManifest":
        if len(self.fixture_case_ids) < 10:
            raise ValueError("at least ten provenance fixture cases are required")
        if len(set(self.fixture_case_ids)) != len(self.fixture_case_ids):
            raise ValueError("provenance fixture case IDs must be unique")
        if len({item.artifact_id for item in self.artifacts}) != len(self.artifacts):
            raise ValueError("artifact IDs must be unique")
        return self


class Phase5ManifestVerification(DomainModel):
    """Offline Stage 5.0 verification result."""

    manifest_id: str
    valid: bool
    benchmark_reviewed: bool
    checked_artifact_count: int = Field(ge=0)
    errors: tuple[str, ...]


def load_provenance_benchmark(path: str | Path) -> ProvenanceBenchmark:
    return ProvenanceBenchmark.model_validate_json(Path(path).read_text(encoding="utf-8"))


def load_phase5_manifest(path: str | Path) -> Phase5ExperimentManifest:
    return Phase5ExperimentManifest.model_validate_json(Path(path).read_text(encoding="utf-8"))


def verify_phase5_manifest(
    manifest: Phase5ExperimentManifest, project_root: str | Path
) -> Phase5ManifestVerification:
    """Verify frozen files and identities without network or model access."""
    root = Path(project_root).resolve()
    errors: list[str] = []
    checked = 0
    benchmark: ProvenanceBenchmark | None = None
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
        if artifact.artifact_id == "provenance_benchmark":
            try:
                benchmark = load_provenance_benchmark(candidate)
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
                errors.append(f"provenance_benchmark: cannot validate ({exc})")
    if benchmark is None:
        errors.append("provenance_benchmark: artifact is required")
    else:
        if benchmark.dataset_id != manifest.provenance_dataset_id:
            errors.append("provenance_benchmark: dataset_id mismatch")
        if benchmark.version != manifest.provenance_dataset_version:
            errors.append("provenance_benchmark: version mismatch")
        if tuple(case.case_id for case in benchmark.cases) != manifest.fixture_case_ids:
            errors.append("provenance_benchmark: locked case IDs or order changed")
        if benchmark.status != "reviewed":
            errors.append("provenance_benchmark: human review is pending")
    return Phase5ManifestVerification(
        manifest_id=manifest.manifest_id,
        valid=not errors,
        benchmark_reviewed=benchmark is not None and benchmark.status == "reviewed",
        checked_artifact_count=checked,
        errors=tuple(errors),
    )
