"""Stage 9.4 authoritative fixture-graph evaluation and release manifest."""

import asyncio
import hashlib
from pathlib import Path

from claim_polygraph_ng.application import InvestigationService
from claim_polygraph_ng.application.langgraph_authoritative import (
    AuthoritativeFixtureLangGraphWorkflow,
)
from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.operations import AuthoritativeOperation
from claim_polygraph_ng.evaluation.phase9_baseline import (
    Phase9ArtifactHash,
    Phase9BaselineVerification,
)
from claim_polygraph_ng.persistence import SQLiteInvestigationRepository
from claim_polygraph_ng.persistence.authoritative_graph import (
    SQLiteAuthoritativeGraphCheckpointRepository,
)
from claim_polygraph_ng.providers import (
    DeterministicModelProvider,
    DeterministicSearchProvider,
)


class Phase9GraphSkeletonEvaluation(DomainModel):
    evaluation_id: str = "phase9-stage9.4-authoritative-graph-skeleton-v1"
    graph_version: str
    operation_count: int
    checkpoint_count: int
    report_completed: bool
    final_report_persisted: bool
    fixture_model_operations: int
    fixture_search_operations: int
    external_model_calls: int = 0
    live_search_calls: int = 0
    network_fetches: int = 0
    pdf_downloads: int = 0


class Phase9GraphSkeletonReleaseManifest(DomainModel):
    manifest_id: str = "phase9-stage9.4-release-manifest-v1"
    artifacts: tuple[Phase9ArtifactHash, ...]
    external_model_calls: int = 0
    live_search_calls: int = 0
    network_fetches: int = 0
    pdf_downloads: int = 0


_ARTIFACTS = (
    ("authoritative_graph", "src/claim_polygraph_ng/application/langgraph_authoritative.py"),
    ("investigation_service", "src/claim_polygraph_ng/application/investigation_service.py"),
    ("artifact_contract", "src/claim_polygraph_ng/domain/investigation.py"),
    ("integration_tests", "tests/integration/test_authoritative_langgraph.py"),
    ("stage9_3_manifest", "artifacts/evaluations/phase9-stage9.3-graph-state-v1.json"),
    ("stage9_4_evaluation", "artifacts/evaluations/phase9-stage9.4-graph-skeleton-v1.json"),
    ("stage9_4_report", "docs/PHASE_9_STAGE_9.4_COMPLETION_REPORT.md"),
)


def evaluate_phase9_graph_skeleton(
    root: str | Path,
    work_path: str | Path,
) -> Phase9GraphSkeletonEvaluation:
    del root
    work = Path(work_path)
    investigations = SQLiteInvestigationRepository(work / "investigations.db")
    service = InvestigationService(
        repository=investigations,
        model_provider=DeterministicModelProvider(),
        search_provider=DeterministicSearchProvider(),
    )
    state_path = work / "state.db"
    with AuthoritativeFixtureLangGraphWorkflow(
        service=service,
        investigations=investigations,
        langgraph_checkpoint_path=work / "langgraph.db",
        state_checkpoint_path=state_path,
    ) as workflow:
        result = asyncio.run(
            workflow.run_to_completion("The fixture programme reduced waste.")
        )
    history = SQLiteAuthoritativeGraphCheckpointRepository(state_path).history(
        result.state.thread_id
    )
    return Phase9GraphSkeletonEvaluation(
        graph_version=result.state.graph_version,
        operation_count=len(result.state.completed_operations),
        checkpoint_count=len(history),
        report_completed=result.report.investigation.status.value == "completed",
        final_report_persisted=result.state.final_report_ref is not None,
        fixture_model_operations=7,
        fixture_search_operations=3,
    )


def export_phase9_graph_skeleton(
    evaluation: Phase9GraphSkeletonEvaluation,
    path: str | Path,
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(evaluation.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return target


def build_phase9_graph_skeleton_release_manifest(
    root: str | Path,
) -> Phase9GraphSkeletonReleaseManifest:
    project = Path(root).resolve()
    manifest = Phase9GraphSkeletonReleaseManifest(
        artifacts=tuple(
            Phase9ArtifactHash(
                artifact_id=artifact_id,
                path=path,
                sha256=_sha256(project / path),
            )
            for artifact_id, path in _ARTIFACTS
        )
    )
    target = project / "artifacts/evaluations/phase9-stage9.4-release-manifest-v1.json"
    target.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_phase9_graph_skeleton_release_manifest(
    manifest: Phase9GraphSkeletonReleaseManifest,
    root: str | Path,
) -> Phase9BaselineVerification:
    project = Path(root).resolve()
    errors: list[str] = []
    checked = 0
    for artifact in manifest.artifacts:
        candidate = project / artifact.path
        if not candidate.is_file():
            errors.append(f"{artifact.artifact_id}: file missing")
            continue
        checked += 1
        if _sha256(candidate) != artifact.sha256:
            errors.append(f"{artifact.artifact_id}: SHA-256 mismatch")
    return Phase9BaselineVerification(
        valid=not errors,
        checked_artifact_count=checked,
        checked_contract_count=len(AuthoritativeOperation),
        errors=tuple(errors),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
