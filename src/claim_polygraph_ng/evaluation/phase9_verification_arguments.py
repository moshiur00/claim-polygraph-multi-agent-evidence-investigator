"""Stage 9.7 verification/argument release records and hashing."""

import hashlib
from pathlib import Path

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.evaluation.phase9_baseline import (
    Phase9ArtifactHash,
    Phase9BaselineVerification,
)


class Phase9VerificationArgumentGate(DomainModel):
    evaluation_id: str = "phase9-stage9.7-verification-arguments-v1"
    verification_branch_count: int
    verification_concurrent: bool
    sequential_equivalence: bool
    approved_packet_isolated: bool
    defender_challenger_concurrent: bool
    defender_challenger_independent: bool
    deterministic_reconciliation: bool
    replay_without_role_execution: bool
    direct_fallback_retained: bool
    external_model_calls: int = 0
    live_search_calls: int = 0
    network_fetches: int = 0
    pdf_downloads: int = 0


class Phase9VerificationArgumentManifest(DomainModel):
    manifest_id: str = "phase9-stage9.7-release-manifest-v1"
    artifacts: tuple[Phase9ArtifactHash, ...]
    external_model_calls: int = 0
    live_search_calls: int = 0
    network_fetches: int = 0
    pdf_downloads: int = 0


_ARTIFACTS = (
    (
        "analysis_contracts",
        "src/claim_polygraph_ng/domain/authoritative_analysis.py",
    ),
    (
        "verification_subgraph",
        "src/claim_polygraph_ng/application/langgraph_verification.py",
    ),
    (
        "argument_subgraph",
        "src/claim_polygraph_ng/application/langgraph_argument.py",
    ),
    (
        "authoritative_graph",
        "src/claim_polygraph_ng/application/langgraph_authoritative.py",
    ),
    ("service_authority", "src/claim_polygraph_ng/application/investigation_service.py"),
    (
        "integration_tests",
        "tests/integration/test_authoritative_verification_arguments.py",
    ),
    (
        "stage9_6_manifest",
        "artifacts/evaluations/phase9-stage9.6-release-manifest-v1.json",
    ),
    (
        "stage9_7_gate",
        "artifacts/evaluations/phase9-stage9.7-verification-arguments-v1.json",
    ),
    ("stage9_7_report", "docs/PHASE_9_STAGE_9.7_COMPLETION_REPORT.md"),
)


def export_gate(gate: Phase9VerificationArgumentGate, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(gate.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return target


def build_release_manifest(root: str | Path) -> Phase9VerificationArgumentManifest:
    project = Path(root).resolve()
    manifest = Phase9VerificationArgumentManifest(
        artifacts=tuple(
            Phase9ArtifactHash(
                artifact_id=artifact_id,
                path=path,
                sha256=_sha256(project / path),
            )
            for artifact_id, path in _ARTIFACTS
        )
    )
    target = project / "artifacts/evaluations/phase9-stage9.7-release-manifest-v1.json"
    target.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_release_manifest(
    manifest: Phase9VerificationArgumentManifest,
    root: str | Path,
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
        checked_contract_count=1,
        errors=tuple(errors),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
