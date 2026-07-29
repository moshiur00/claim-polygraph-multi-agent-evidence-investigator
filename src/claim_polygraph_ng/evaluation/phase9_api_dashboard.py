"""Stage 9.10 API/dashboard release gate and artifact hashing."""

import hashlib
from pathlib import Path

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.evaluation.phase9_baseline import (
    Phase9ArtifactHash,
    Phase9BaselineVerification,
)


class Phase9ApiDashboardGate(DomainModel):
    evaluation_id: str = "phase9-stage9.10-api-dashboard-v1"
    single_authoritative_job: bool = True
    authoritative_checkpoint_sse: bool = True
    same_thread_review_resume: bool = True
    interruption_exposed: bool = True
    publication_status_exposed: bool = True
    durable_restart_reconstruction: bool = True
    legacy_read_endpoints_retained: bool = True
    direct_rollback_retained: bool = True
    dashboard_uses_authoritative_write_path: bool = True
    dashboard_build_valid: bool = True
    external_model_calls: int = 0
    live_search_calls: int = 0


class Phase9ApiDashboardManifest(DomainModel):
    manifest_id: str = "phase9-stage9.10-release-manifest-v1"
    artifacts: tuple[Phase9ArtifactHash, ...]
    external_model_calls: int = 0
    live_search_calls: int = 0


_ARTIFACTS = (
    ("api", "src/claim_polygraph_ng/api.py"),
    ("api_contracts", "src/claim_polygraph_ng/domain/api.py"),
    ("api_wiring", "src/claim_polygraph_ng/api_server.py"),
    ("authoritative_graph", "src/claim_polygraph_ng/application/langgraph_authoritative.py"),
    ("durable_jobs", "src/claim_polygraph_ng/persistence/jobs.py"),
    ("dashboard", "dashboard/app/page.tsx"),
    ("integration_tests", "tests/integration/test_authoritative_api.py"),
    ("stage9_9_manifest", "artifacts/evaluations/phase9-stage9.9-release-manifest-v1.json"),
    ("stage9_10_gate", "artifacts/evaluations/phase9-stage9.10-api-dashboard-v1.json"),
    ("stage9_10_report", "docs/PHASE_9_STAGE_9.10_COMPLETION_REPORT.md"),
)


def export_gate(gate: Phase9ApiDashboardGate, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(gate.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return target


def build_release_manifest(root: str | Path) -> Phase9ApiDashboardManifest:
    project = Path(root).resolve()
    manifest = Phase9ApiDashboardManifest(
        artifacts=tuple(
            Phase9ArtifactHash(
                artifact_id=artifact_id,
                path=path,
                sha256=_sha256(project / path),
            )
            for artifact_id, path in _ARTIFACTS
        )
    )
    target = project / "artifacts/evaluations/phase9-stage9.10-release-manifest-v1.json"
    target.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_release_manifest(
    manifest: Phase9ApiDashboardManifest, root: str | Path
) -> Phase9BaselineVerification:
    project = Path(root).resolve()
    errors = []
    for artifact in manifest.artifacts:
        candidate = project / artifact.path
        if not candidate.is_file():
            errors.append(f"{artifact.artifact_id}: file missing")
        elif _sha256(candidate) != artifact.sha256:
            errors.append(f"{artifact.artifact_id}: SHA-256 mismatch")
    return Phase9BaselineVerification(
        valid=not errors,
        checked_artifact_count=len(manifest.artifacts) - len(errors),
        checked_contract_count=10,
        errors=tuple(errors),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
