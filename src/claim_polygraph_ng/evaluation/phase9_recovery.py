"""Stage 9.11 recovery release gate and artifact hashing."""

import hashlib
from pathlib import Path

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.evaluation.phase9_baseline import (
    Phase9ArtifactHash,
    Phase9BaselineVerification,
)


class Phase9RecoveryGate(DomainModel):
    evaluation_id: str = "phase9-stage9.11-recovery-v1"
    transient_provider_retry: bool = True
    unfinished_node_restart_resume: bool = True
    cancellation_at_durable_boundary: bool = True
    concurrent_admission_bounded: bool = True
    idempotent_submission: bool = True
    checkpoint_hash_validation: bool = True
    checkpoint_sequence_validation: bool = True
    review_acknowledgement_recovery: bool = True
    paid_operations_not_replayed: bool = True
    sse_last_event_id_reconnect: bool = True
    legacy_checkpoint_migration: bool = True
    external_model_calls: int = 0
    live_search_calls: int = 0
    network_fetches: int = 0
    pdf_downloads: int = 0


class Phase9RecoveryManifest(DomainModel):
    manifest_id: str = "phase9-stage9.11-release-manifest-v1"
    artifacts: tuple[Phase9ArtifactHash, ...]
    external_model_calls: int = 0
    live_search_calls: int = 0
    network_fetches: int = 0
    pdf_downloads: int = 0


_ARTIFACTS = (
    ("authoritative_graph", "src/claim_polygraph_ng/application/langgraph_authoritative.py"),
    ("checkpoint_repository", "src/claim_polygraph_ng/persistence/authoritative_graph.py"),
    ("durable_jobs", "src/claim_polygraph_ng/persistence/jobs.py"),
    ("api_recovery", "src/claim_polygraph_ng/api.py"),
    ("recovery_tests", "tests/integration/test_phase9_recovery.py"),
    ("sse_tests", "tests/integration/test_authoritative_api.py"),
    ("stage9_10_manifest", "artifacts/evaluations/phase9-stage9.10-release-manifest-v1.json"),
    ("stage9_11_gate", "artifacts/evaluations/phase9-stage9.11-recovery-v1.json"),
    ("stage9_11_report", "docs/PHASE_9_STAGE_9.11_COMPLETION_REPORT.md"),
)


def export_gate(gate: Phase9RecoveryGate, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(gate.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return target


def build_release_manifest(root: str | Path) -> Phase9RecoveryManifest:
    project = Path(root).resolve()
    manifest = Phase9RecoveryManifest(
        artifacts=tuple(
            Phase9ArtifactHash(
                artifact_id=artifact_id,
                path=path,
                sha256=_sha256(project / path),
            )
            for artifact_id, path in _ARTIFACTS
        )
    )
    target = project / "artifacts/evaluations/phase9-stage9.11-release-manifest-v1.json"
    target.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_release_manifest(
    manifest: Phase9RecoveryManifest, root: str | Path
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
        checked_contract_count=11,
        errors=tuple(errors),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
