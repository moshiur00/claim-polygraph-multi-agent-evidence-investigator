"""Stage 8.0 locked baseline, routing controls, and offline verification."""

import hashlib
import json
from pathlib import Path

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.evaluation.phase7_assurance import (
    Phase7AssuranceEvaluation,
    evaluate_phase7_assurance,
)


class Phase8ArtifactHash(DomainModel):
    artifact_id: str = Field(pattern=r"^[a-z0-9_]+$")
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Phase8ResourceCeilings(DomainModel):
    fixture_model_calls: int = 0
    fixture_search_calls: int = 0
    fixture_network_calls: int = 0
    fixture_pdf_downloads: int = 0
    pilot_case_count: int = 5
    pilot_mean_cost_ratio: float = 2.0
    pilot_median_latency_ratio: float = 2.0
    verdict_regressions_allowed: int = 0
    duplicate_paid_operations_allowed: int = 0
    maximum_research_rounds: int = 2
    maximum_concurrent_roles: int = 4


class Phase8QualityGates(DomainModel):
    minimum_citation_support_rate: float = 0.95
    mandatory_review_recall: float = 1.0
    minimum_review_specificity: float = 0.8
    minimum_review_route_accuracy: float = 0.9
    minimum_improved_pilot_cases: int = 2
    material_sentence_audit_coverage: float = 1.0


class Phase8BaselineManifest(DomainModel):
    manifest_id: str = "phase8-stage8.0-baseline-v1"
    schema_version: int = 1
    dataset_id: str = "initial_claims"
    dataset_version: int = 5
    authoritative_case_count: int = 20
    authoritative_accuracy: float = 0.9
    known_disagreements: tuple[str, ...] = ("CPNG-006", "CPNG-019")
    default_orchestrator: str = "langgraph"
    authoritative_service: str = "InvestigationService"
    rollback_orchestrator: str = "direct"
    resource_ceilings: Phase8ResourceCeilings = Phase8ResourceCeilings()
    quality_gates: Phase8QualityGates = Phase8QualityGates()
    artifacts: tuple[Phase8ArtifactHash, ...]

    @model_validator(mode="after")
    def validate_artifacts(self) -> "Phase8BaselineManifest":
        if len({item.artifact_id for item in self.artifacts}) != len(self.artifacts):
            raise ValueError("artifact IDs must be unique")
        if len({item.path for item in self.artifacts}) != len(self.artifacts):
            raise ValueError("artifact paths must be unique")
        return self


class Phase8RoutingMetrics(DomainModel):
    case_count: int
    required_review_count: int
    automatic_count: int
    true_positive: int
    true_negative: int
    false_positive: int
    false_negative: int
    recall: float
    specificity: float
    precision: float
    route_accuracy: float
    gate_passed: bool
    assurance: Phase7AssuranceEvaluation


class Phase8ManifestVerification(DomainModel):
    valid: bool
    checked_artifact_count: int
    errors: tuple[str, ...]


_ARTIFACTS = (
    ("benchmark", "benchmarks/initial_claims_v1.json"),
    ("routing_controls", "benchmarks/phase8_review_routing_controls_v1.json"),
    ("phase7_closure", "artifacts/evaluations/phase7-final-closure-audit-v1.json"),
    ("phase7_frozen", "artifacts/evaluations/phase7-stage7.8-frozen-comparison-v1.json"),
    ("promotion_adr", "docs/adr/0014-promote-langgraph-as-default-orchestrator.md"),
    ("dashboard_adr", "docs/adr/0015-dashboard-root-monorepo.md"),
    ("dashboard_inventory", "docs/PHASE_8_STAGE_8.0_DASHBOARD_INVENTORY.md"),
    ("dashboard_history", "dashboard-history/dashboard-pre-monorepo-4651a05.bundle"),
    ("dashboard_package", "dashboard/package.json"),
    ("dashboard_lint", "dashboard/eslint.config.mjs"),
    ("dashboard_runner", "dashboard/scripts/run-vinext.mjs"),
    ("readme", "README.md"),
    ("benchmark_readme", "benchmarks/README.md"),
    ("phase8_plan", "docs/PHASE_8_TRUE_MULTI_AGENT_EXECUTION_PLAN.md"),
    ("stage8_0_report", "docs/PHASE_8_STAGE_8.0_COMPLETION_REPORT.md"),
)


def evaluate_phase8_routing_controls(path: str | Path) -> Phase8RoutingMetrics:
    assurance = evaluate_phase7_assurance(path)
    results = assurance.results
    true_positive = sum(item.expected_review and item.observed_review for item in results)
    true_negative = sum(not item.expected_review and not item.observed_review for item in results)
    false_positive = sum(not item.expected_review and item.observed_review for item in results)
    false_negative = sum(item.expected_review and not item.observed_review for item in results)
    required = true_positive + false_negative
    automatic = true_negative + false_positive
    predicted_review = true_positive + false_positive
    recall = true_positive / required if required else 1.0
    specificity = true_negative / automatic if automatic else 1.0
    precision = true_positive / predicted_review if predicted_review else 1.0
    accuracy = (true_positive + true_negative) / len(results)
    return Phase8RoutingMetrics(
        case_count=len(results),
        required_review_count=required,
        automatic_count=automatic,
        true_positive=true_positive,
        true_negative=true_negative,
        false_positive=false_positive,
        false_negative=false_negative,
        recall=recall,
        specificity=specificity,
        precision=precision,
        route_accuracy=accuracy,
        gate_passed=recall == 1 and specificity >= 0.8 and accuracy >= 0.9,
        assurance=assurance,
    )


def build_phase8_baseline(project_root: str | Path) -> Phase8BaselineManifest:
    root = Path(project_root).resolve()
    manifest = Phase8BaselineManifest(
        artifacts=tuple(
            Phase8ArtifactHash(
                artifact_id=artifact_id,
                path=path,
                sha256=_sha256(root / path),
            )
            for artifact_id, path in _ARTIFACTS
        )
    )
    target = root / "artifacts/evaluations/phase8-stage8.0-baseline-v1.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_phase8_baseline(
    manifest: Phase8BaselineManifest, project_root: str | Path
) -> Phase8ManifestVerification:
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
            errors.append(f"{artifact.artifact_id}: file missing")
            continue
        checked += 1
        if _sha256(candidate) != artifact.sha256:
            errors.append(f"{artifact.artifact_id}: SHA-256 mismatch")
    return Phase8ManifestVerification(
        valid=not errors,
        checked_artifact_count=checked,
        errors=tuple(errors),
    )


def load_phase8_baseline(path: str | Path) -> Phase8BaselineManifest:
    return Phase8BaselineManifest.model_validate_json(Path(path).read_text(encoding="utf-8"))


def export_phase8_routing(metrics: Phase8RoutingMetrics, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(metrics.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
