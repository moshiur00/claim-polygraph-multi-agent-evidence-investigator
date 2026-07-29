"""Stage 9.3 graph-state schema and release manifest."""

import hashlib
import json
from pathlib import Path

from pydantic import Field

from claim_polygraph_ng.domain.authoritative_graph import (
    AuthoritativeInvestigationGraphState,
)
from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.evaluation.phase9_baseline import (
    Phase9ArtifactHash,
    Phase9BaselineVerification,
)


class Phase9GraphStateManifest(DomainModel):
    manifest_id: str = "phase9-stage9.3-authoritative-graph-state-v1"
    schema_version: int = 1
    graph_version: str = "authoritative-investigation-graph-v1"
    state_schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    invariant_count: int
    migration_sources: tuple[str, ...]
    external_model_calls: int = 0
    live_search_calls: int = 0
    network_fetches: int = 0
    pdf_downloads: int = 0
    artifacts: tuple[Phase9ArtifactHash, ...]


INVARIANTS = (
    "graph identity and version are immutable",
    "checkpoint sequence increases exactly once",
    "completed operations cannot disappear",
    "artifact references cannot disappear",
    "approved evidence cannot disappear",
    "paid receipts cannot disappear",
    "review records are append-only",
    "failure records are append-only",
    "resource consumption cannot decrease",
    "final report reference is immutable",
    "terminal state cannot transition",
    "all artifact references resolve during reconstruction",
)

_ARTIFACTS = (
    ("graph_state", "src/claim_polygraph_ng/domain/authoritative_graph.py"),
    ("state_policy", "src/claim_polygraph_ng/application/authoritative_graph_state.py"),
    ("checkpoint_repository", "src/claim_polygraph_ng/persistence/authoritative_graph.py"),
    ("persistence_exports", "src/claim_polygraph_ng/persistence/__init__.py"),
    ("state_tests", "tests/unit/test_authoritative_graph_state.py"),
    ("stage9_2_manifest", "artifacts/evaluations/phase9-stage9.2-release-manifest-v1.json"),
    ("stage9_3_report", "docs/PHASE_9_STAGE_9.3_COMPLETION_REPORT.md"),
)


def build_phase9_graph_state_manifest(
    project_root: str | Path,
) -> Phase9GraphStateManifest:
    root = Path(project_root).resolve()
    schema = AuthoritativeInvestigationGraphState.model_json_schema()
    manifest = Phase9GraphStateManifest(
        state_schema_sha256=hashlib.sha256(
            json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        invariant_count=len(INVARIANTS),
        migration_sources=("DurableMultiAgentGraphState",),
        artifacts=tuple(
            Phase9ArtifactHash(
                artifact_id=artifact_id,
                path=path,
                sha256=_sha256(root / path),
            )
            for artifact_id, path in _ARTIFACTS
        ),
    )
    target = root / "artifacts/evaluations/phase9-stage9.3-graph-state-v1.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_phase9_graph_state_manifest(
    manifest: Phase9GraphStateManifest,
    project_root: str | Path,
) -> Phase9BaselineVerification:
    root = Path(project_root).resolve()
    schema = AuthoritativeInvestigationGraphState.model_json_schema()
    expected_schema = hashlib.sha256(
        json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    errors: list[str] = []
    if manifest.state_schema_sha256 != expected_schema:
        errors.append("authoritative graph state schema mismatch")
    checked = 0
    for artifact in manifest.artifacts:
        candidate = (root / artifact.path).resolve()
        if not candidate.is_file():
            errors.append(f"{artifact.artifact_id}: file missing")
            continue
        checked += 1
        if _sha256(candidate) != artifact.sha256:
            errors.append(f"{artifact.artifact_id}: SHA-256 mismatch")
    return Phase9BaselineVerification(
        valid=not errors,
        checked_artifact_count=checked,
        checked_contract_count=1,
        errors=tuple(errors),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
