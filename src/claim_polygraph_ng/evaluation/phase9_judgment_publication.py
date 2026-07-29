"""Stage 9.8 judgment/publication release records and hashing."""

import hashlib
from pathlib import Path

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.evaluation.phase9_baseline import (
    Phase9ArtifactHash,
    Phase9BaselineVerification,
)


class Phase9JudgmentPublicationGate(DomainModel):
    evaluation_id: str = "phase9-stage9.8-judgment-publication-v1"
    proposed_enforced_verdict_separated: bool
    judgment_policy_checkpointed: bool
    sentence_assurance_checkpointed: bool
    bounded_revision_maximum: int
    readiness_checkpointed: bool
    publication_decision_persisted: bool
    unsupported_critical_assertion_blocked: bool
    public_renderer_fail_closed: bool
    direct_rollback_gated: bool
    external_model_calls: int = 0
    live_search_calls: int = 0
    network_fetches: int = 0
    pdf_downloads: int = 0


class Phase9JudgmentPublicationManifest(DomainModel):
    manifest_id: str = "phase9-stage9.8-release-manifest-v1"
    artifacts: tuple[Phase9ArtifactHash, ...]
    external_model_calls: int = 0
    live_search_calls: int = 0
    network_fetches: int = 0
    pdf_downloads: int = 0


_ARTIFACTS = (
    ("publication_contract", "src/claim_polygraph_ng/domain/publication.py"),
    ("report_contract", "src/claim_polygraph_ng/domain/investigation.py"),
    ("durable_state", "src/claim_polygraph_ng/domain/authoritative_graph.py"),
    ("operation_contracts", "src/claim_polygraph_ng/application/operation_contracts.py"),
    ("service_authority", "src/claim_polygraph_ng/application/investigation_service.py"),
    ("authoritative_graph", "src/claim_polygraph_ng/application/langgraph_authoritative.py"),
    ("publication_renderer", "src/claim_polygraph_ng/reporting/reports.py"),
    (
        "integration_tests",
        "tests/integration/test_authoritative_judgment_publication.py",
    ),
    (
        "stage9_7_manifest",
        "artifacts/evaluations/phase9-stage9.7-release-manifest-v1.json",
    ),
    (
        "stage9_8_gate",
        "artifacts/evaluations/phase9-stage9.8-judgment-publication-v1.json",
    ),
    ("stage9_8_report", "docs/PHASE_9_STAGE_9.8_COMPLETION_REPORT.md"),
)


def export_gate(gate: Phase9JudgmentPublicationGate, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(gate.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return target


def build_release_manifest(root: str | Path) -> Phase9JudgmentPublicationManifest:
    project = Path(root).resolve()
    manifest = Phase9JudgmentPublicationManifest(
        artifacts=tuple(
            Phase9ArtifactHash(
                artifact_id=artifact_id,
                path=path,
                sha256=_sha256(project / path),
            )
            for artifact_id, path in _ARTIFACTS
        )
    )
    target = project / "artifacts/evaluations/phase9-stage9.8-release-manifest-v1.json"
    target.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_release_manifest(
    manifest: Phase9JudgmentPublicationManifest,
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
