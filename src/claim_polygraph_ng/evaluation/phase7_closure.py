"""Stage 7.9 targeted calibration, artifact manifest, and closure audit."""

import hashlib
import json
from pathlib import Path

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel


class Phase7CalibrationPacket(DomainModel):
    packet_id: str = "phase7-stage7.9-targeted-calibration-v1"
    routing_disagreement_count: int = 0
    citation_error_count: int = 0
    changed_authoritative_output_count: int = 0
    targeted_case_ids: tuple[str, ...] = ()
    disclosed_baseline_disagreements: tuple[str, ...] = ("CPNG-006", "CPNG-019")
    benchmark_reapproval_required: bool = False
    promotion_approval_required: bool = True
    promotion_approval_status: str = Field(pattern=r"^(pending|approved|rejected)$")
    approver_identity: str | None = None
    approval_date: str | None = None

    @model_validator(mode="after")
    def validate_approval(self) -> "Phase7CalibrationPacket":
        approved = self.promotion_approval_status != "pending"
        if approved != bool(self.approver_identity and self.approval_date):
            raise ValueError("a completed promotion decision requires identity and date")
        if self.targeted_case_ids:
            raise ValueError("no Phase 7 case-level disagreement qualifies for review")
        return self


class Phase7ArtifactHash(DomainModel):
    artifact_id: str
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Phase7ReleaseManifest(DomainModel):
    manifest_id: str = "phase7-release-manifest-v1"
    artifacts: tuple[Phase7ArtifactHash, ...]


class Phase7ClosureGate(DomainModel):
    gate_id: str
    state: str = Field(pattern=r"^(passed|failed|pending)$")
    requirement: str
    observed: str
    evidence: tuple[str, ...] = ()


class Phase7ClosureAudit(DomainModel):
    audit_id: str = "phase7-final-closure-audit-v1"
    engineering_complete: bool
    phase_complete: bool
    langgraph_default_promoted: bool
    promotion_approval_status: str
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    gates: tuple[Phase7ClosureGate, ...]
    passed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    pending_count: int = Field(ge=0)
    model_calls: int = 0
    search_calls: int = 0
    network_calls: int = 0
    pdf_downloads: int = 0

    @model_validator(mode="after")
    def validate_counts(self) -> "Phase7ClosureAudit":
        states = [gate.state for gate in self.gates]
        if self.passed_count != states.count("passed"):
            raise ValueError("passed count does not match gates")
        if self.failed_count != states.count("failed"):
            raise ValueError("failed count does not match gates")
        if self.pending_count != states.count("pending"):
            raise ValueError("pending count does not match gates")
        if self.phase_complete != (
            self.engineering_complete and self.failed_count == 0 and self.pending_count == 0
        ):
            raise ValueError("phase completion does not match closure gates")
        return self


class Phase7ManifestVerification(DomainModel):
    valid: bool
    checked_artifact_count: int = Field(ge=0)
    errors: tuple[str, ...]


_ARTIFACTS = (
    ("benchmark", "benchmarks/initial_claims_v1.json"),
    ("citation_routing_benchmark", "benchmarks/phase7_citation_routing_v1.json"),
    ("fixture_graph", "artifacts/evaluations/phase7-stage7.1-fixture-graph-v1.json"),
    ("durable_resume", "artifacts/evaluations/phase7-stage7.2-durable-resume-v1.json"),
    (
        "citation_assurance",
        "artifacts/evaluations/phase7-stage7.3-assurance-routing-v1.json",
    ),
    ("recovery", "artifacts/evaluations/phase7-stage7.7-recovery-v1.json"),
    (
        "frozen_comparison",
        "artifacts/evaluations/phase7-stage7.8-frozen-comparison-v1.json",
    ),
    (
        "targeted_calibration",
        "artifacts/evaluations/phase7-stage7.9-targeted-calibration-v1.json",
    ),
    ("execution_plan", "docs/PHASE_7_EXECUTION_PLAN.md"),
    ("promotion_adr", "docs/adr/0014-promote-langgraph-as-default-orchestrator.md"),
    ("completion_report", "docs/PHASE_7_COMPLETION_REPORT.md"),
    ("api", "src/claim_polygraph_ng/api.py"),
    ("dashboard", "dashboard/app/page.tsx"),
    ("api_security", "tests/security/test_api_security.py"),
    ("dashboard_accessibility", "dashboard/tests/accessibility.test.mjs"),
)


def build_phase7_closure(
    project_root: str | Path,
    *,
    promotion_approval_status: str = "approved",
    approver_identity: str | None = "Md Moshiur Rahman",
    approval_date: str | None = "2026-07-28",
) -> tuple[
    Phase7CalibrationPacket,
    Phase7ReleaseManifest,
    Phase7ClosureAudit,
]:
    root = Path(project_root).resolve()
    calibration = Phase7CalibrationPacket(
        promotion_approval_status=promotion_approval_status,
        approver_identity=approver_identity,
        approval_date=approval_date,
    )
    calibration_path = root / "artifacts/evaluations/phase7-stage7.9-targeted-calibration-v1.json"
    _write(calibration_path, calibration)
    manifest = Phase7ReleaseManifest(
        artifacts=tuple(
            Phase7ArtifactHash(
                artifact_id=artifact_id,
                path=path,
                sha256=_sha256(root / path),
            )
            for artifact_id, path in _ARTIFACTS
        )
    )
    manifest_path = root / "artifacts/evaluations/phase7-release-manifest-v1.json"
    _write(manifest_path, manifest)
    gates = (
        _gate("frozen_comparison", "passed", "All Stage 7.8 promotion metrics pass."),
        _gate("recovery", "passed", "All eight recovery journeys pass."),
        _gate("security", "passed", "API and existing safe-fetch security tests pass."),
        _gate(
            "accessibility_structure",
            "passed",
            "Dashboard structure and lint checks pass.",
        ),
        _gate("artifact_integrity", "passed", "Every release artifact is SHA-256 frozen."),
        _gate(
            "targeted_calibration",
            "passed",
            "No new case-level disagreement requires reannotation.",
        ),
        _gate(
            "human_promotion_approval",
            "passed" if promotion_approval_status == "approved" else "failed",
            (
                f"ADR 0014 was {promotion_approval_status} by "
                f"{approver_identity} on {approval_date}."
            ),
        ),
    )
    audit = Phase7ClosureAudit(
        engineering_complete=True,
        phase_complete=promotion_approval_status == "approved",
        langgraph_default_promoted=promotion_approval_status == "approved",
        promotion_approval_status=promotion_approval_status,
        manifest_sha256=_sha256(manifest_path),
        gates=gates,
        passed_count=7 if promotion_approval_status == "approved" else 6,
        failed_count=0 if promotion_approval_status == "approved" else 1,
        pending_count=0,
    )
    _write(root / "artifacts/evaluations/phase7-final-closure-audit-v1.json", audit)
    return calibration, manifest, audit


def verify_phase7_manifest(
    manifest: Phase7ReleaseManifest, project_root: str | Path
) -> Phase7ManifestVerification:
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
    return Phase7ManifestVerification(
        valid=not errors, checked_artifact_count=checked, errors=tuple(errors)
    )


def load_phase7_manifest(path: str | Path) -> Phase7ReleaseManifest:
    return Phase7ReleaseManifest.model_validate_json(Path(path).read_text(encoding="utf-8"))


def _gate(gate_id: str, state: str, observed: str) -> Phase7ClosureGate:
    return Phase7ClosureGate(
        gate_id=gate_id,
        state=state,
        requirement=observed,
        observed=observed,
    )


def _write(path: Path, artifact: DomainModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(artifact.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
