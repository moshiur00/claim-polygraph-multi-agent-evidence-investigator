"""Stage 9.9 human-review release records and hashing."""

import hashlib
from pathlib import Path

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.evaluation.phase9_baseline import (
    Phase9ArtifactHash,
    Phase9BaselineVerification,
)


class Phase9HumanReviewGate(DomainModel):
    evaluation_id: str = "phase9-stage9.9-authoritative-human-review-v1"
    same_thread_resume: bool
    approval_path: bool
    revision_path: bool
    more_evidence_path: bool
    rejection_path: bool
    append_only_audit_chain: bool
    distinct_revision_approval: bool
    accepted_decision_idempotent: bool
    conflicting_decision_rejected: bool
    completed_operations_not_replayed: bool
    paid_operations_not_replayed: bool
    external_model_calls: int = 0
    live_search_calls: int = 0
    network_fetches: int = 0
    pdf_downloads: int = 0


class Phase9HumanReviewManifest(DomainModel):
    manifest_id: str = "phase9-stage9.9-release-manifest-v1"
    artifacts: tuple[Phase9ArtifactHash, ...]
    external_model_calls: int = 0
    live_search_calls: int = 0
    network_fetches: int = 0
    pdf_downloads: int = 0


_ARTIFACTS = (
    ("authoritative_graph", "src/claim_polygraph_ng/application/langgraph_authoritative.py"),
    ("graph_transition_policy", "src/claim_polygraph_ng/application/authoritative_graph_state.py"),
    ("review_contracts", "src/claim_polygraph_ng/domain/review.py"),
    ("review_repository", "src/claim_polygraph_ng/persistence/review.py"),
    (
        "integration_tests",
        "tests/integration/test_authoritative_human_review.py",
    ),
    (
        "stage9_8_manifest",
        "artifacts/evaluations/phase9-stage9.8-release-manifest-v1.json",
    ),
    (
        "stage9_9_gate",
        "artifacts/evaluations/phase9-stage9.9-authoritative-human-review-v1.json",
    ),
    ("stage9_9_report", "docs/PHASE_9_STAGE_9.9_COMPLETION_REPORT.md"),
)


def export_gate(gate: Phase9HumanReviewGate, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(gate.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return target


def build_release_manifest(root: str | Path) -> Phase9HumanReviewManifest:
    project = Path(root).resolve()
    manifest = Phase9HumanReviewManifest(
        artifacts=tuple(
            Phase9ArtifactHash(
                artifact_id=artifact_id,
                path=path,
                sha256=_sha256(project / path),
            )
            for artifact_id, path in _ARTIFACTS
        )
    )
    target = project / "artifacts/evaluations/phase9-stage9.9-release-manifest-v1.json"
    target.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_release_manifest(
    manifest: Phase9HumanReviewManifest,
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
