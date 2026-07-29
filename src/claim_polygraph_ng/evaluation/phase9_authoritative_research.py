"""Stage 9.6 release records for authoritative multi-agent research."""

import hashlib
from pathlib import Path

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.evaluation.phase9_baseline import (
    Phase9ArtifactHash,
    Phase9BaselineVerification,
)


class Phase9AuthoritativeResearchGate(DomainModel):
    evaluation_id: str = "phase9-stage9.6-authoritative-multi-agent-research-v1"
    authoritative_graph_integration: bool
    minimum_role_count: int
    concurrent_role_fan_out: bool
    shared_cache_deduplication: bool
    durable_assignments_and_results: bool
    sufficiency_and_budget_routing: bool
    receipt_guard_enforced: bool
    authoritative_packet_preserved: bool
    direct_research_fallback_retained: bool
    external_model_calls: int = 0
    live_search_calls: int = 0
    network_fetches: int = 0
    pdf_downloads: int = 0


class Phase9AuthoritativeResearchReleaseManifest(DomainModel):
    manifest_id: str = "phase9-stage9.6-release-manifest-v1"
    artifacts: tuple[Phase9ArtifactHash, ...]
    external_model_calls: int = 0
    live_search_calls: int = 0
    network_fetches: int = 0
    pdf_downloads: int = 0


_ARTIFACTS = (
    ("authority_bridge", "src/claim_polygraph_ng/application/authoritative_research.py"),
    ("authoritative_graph", "src/claim_polygraph_ng/application/langgraph_authoritative.py"),
    ("service_authority", "src/claim_polygraph_ng/application/investigation_service.py"),
    ("research_subgraph", "src/claim_polygraph_ng/application/langgraph_research.py"),
    ("durable_state", "src/claim_polygraph_ng/domain/authoritative_graph.py"),
    ("receipt_repository", "src/claim_polygraph_ng/persistence/paid_operations.py"),
    (
        "integration_tests",
        "tests/integration/test_authoritative_multi_agent_research.py",
    ),
    (
        "stage9_5_manifest",
        "artifacts/evaluations/phase9-stage9.5-release-manifest-v1.json",
    ),
    (
        "stage9_6_gate",
        "artifacts/evaluations/phase9-stage9.6-authoritative-multi-agent-research-v1.json",
    ),
    ("stage9_6_report", "docs/PHASE_9_STAGE_9.6_COMPLETION_REPORT.md"),
)


def export_gate(gate: Phase9AuthoritativeResearchGate, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(gate.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return target


def build_release_manifest(root: str | Path) -> Phase9AuthoritativeResearchReleaseManifest:
    project = Path(root).resolve()
    manifest = Phase9AuthoritativeResearchReleaseManifest(
        artifacts=tuple(
            Phase9ArtifactHash(
                artifact_id=artifact_id,
                path=path,
                sha256=_sha256(project / path),
            )
            for artifact_id, path in _ARTIFACTS
        )
    )
    target = project / "artifacts/evaluations/phase9-stage9.6-release-manifest-v1.json"
    target.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_release_manifest(
    manifest: Phase9AuthoritativeResearchReleaseManifest,
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
