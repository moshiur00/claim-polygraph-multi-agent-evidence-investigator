"""Zero-cost Stage 9.2 direct-composition structural evaluation."""

import asyncio
import hashlib
from collections import Counter
from pathlib import Path

from claim_polygraph_ng.application import InvestigationService
from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.investigation import ArtifactType, TraceEventType
from claim_polygraph_ng.evaluation.phase9_baseline import (
    Phase9ArtifactHash,
    Phase9BaselineVerification,
)
from claim_polygraph_ng.evaluation.runner import load_benchmark
from claim_polygraph_ng.persistence import SQLiteInvestigationRepository
from claim_polygraph_ng.providers import (
    DeterministicModelProvider,
    DeterministicSearchProvider,
)


class Phase9DirectCaseResult(DomainModel):
    case_id: str
    completed: bool
    verdict_label: str
    source_count: int
    evidence_count: int
    artifact_counts: dict[str, int]
    event_types: tuple[str, ...]
    model_calls: int
    search_calls: int
    pages_fetched: int


class Phase9DirectEvaluation(DomainModel):
    evaluation_id: str = "phase9-stage9.2-direct-composition-v1"
    case_count: int
    completed_count: int
    structurally_consistent: bool
    model_provider: str = "deterministic-model"
    search_provider: str = "deterministic-search"
    paid_model_calls: int = 0
    live_search_calls: int = 0
    network_fetches: int = 0
    pdf_downloads: int = 0
    cases: tuple[Phase9DirectCaseResult, ...]


class Phase9DirectReleaseManifest(DomainModel):
    manifest_id: str = "phase9-stage9.2-release-manifest-v1"
    artifacts: tuple[Phase9ArtifactHash, ...]
    external_model_calls: int = 0
    live_search_calls: int = 0
    network_fetches: int = 0
    pdf_downloads: int = 0


_REQUIRED_SINGLETONS = {
    ArtifactType.CLAIM,
    ArtifactType.PLAN,
    ArtifactType.INDEPENDENCE,
    ArtifactType.PROVENANCE,
    ArtifactType.CONTEXT_VERIFICATION,
    ArtifactType.VERIFICATION_PACKET,
    ArtifactType.ARGUMENT_LEDGER,
    ArtifactType.JUDGMENT_POLICY,
    ArtifactType.VERDICT,
    ArtifactType.AUDIT,
    ArtifactType.FULL_REPORT_ASSURANCE,
    ArtifactType.READINESS,
}

_RELEASE_ARTIFACTS = (
    ("investigation_service", "src/claim_polygraph_ng/application/investigation_service.py"),
    ("direct_evaluator", "src/claim_polygraph_ng/evaluation/phase9_direct.py"),
    ("direct_runner", "scripts/run_phase9_direct_equivalence.py"),
    ("direct_tests", "tests/unit/test_phase9_direct_composition.py"),
    ("direct_evaluation", "artifacts/evaluations/phase9-stage9.2-direct-composition-v1.json"),
    ("stage9_1_contracts", "artifacts/evaluations/phase9-stage9.1-operation-contracts-v1.json"),
    ("stage9_2_report", "docs/PHASE_9_STAGE_9.2_COMPLETION_REPORT.md"),
)


def evaluate_phase9_direct_composition(
    *,
    project_root: str | Path,
    database_path: str | Path,
) -> Phase9DirectEvaluation:
    root = Path(project_root).resolve()
    dataset = load_benchmark(root / "benchmarks/initial_claims_v1.json")
    repository = SQLiteInvestigationRepository(database_path)
    results: list[Phase9DirectCaseResult] = []
    for case in dataset.cases:
        service = InvestigationService(
            repository=repository,
            model_provider=DeterministicModelProvider(),
            search_provider=DeterministicSearchProvider(),
        )
        report = asyncio.run(service.investigate(case.claim))
        investigation_id = report.investigation.investigation_id
        events = repository.list_events(investigation_id)
        counts = {
            artifact_type.value: len(
                repository.list_artifacts(
                    investigation_id,
                    artifact_type,
                    _artifact_model(artifact_type),
                )
            )
            for artifact_type in _REQUIRED_SINGLETONS
        }
        completed = (
            report.investigation.status.value == "completed"
            and all(count == 1 for count in counts.values())
            and events[0].event_type is TraceEventType.INVESTIGATION_CREATED
            and events[-1].event_type is TraceEventType.INVESTIGATION_COMPLETED
        )
        terminal = events[-1].details
        results.append(
            Phase9DirectCaseResult(
                case_id=case.case_id,
                completed=completed,
                verdict_label=report.verdict.label.value,
                source_count=len(report.sources),
                evidence_count=len(report.evidence),
                artifact_counts=counts,
                event_types=tuple(item.event_type.value for item in events),
                model_calls=int(terminal.get("llm_calls", 0)),
                search_calls=int(terminal.get("search_calls", 0)),
                pages_fetched=int(terminal.get("pages_fetched", 0)),
            )
        )
    signatures = Counter(
        (
            item.verdict_label,
            item.source_count,
            item.evidence_count,
            tuple(sorted(item.artifact_counts.items())),
            item.event_types,
            item.model_calls,
            item.search_calls,
            item.pages_fetched,
        )
        for item in results
    )
    return Phase9DirectEvaluation(
        case_count=len(results),
        completed_count=sum(item.completed for item in results),
        structurally_consistent=len(signatures) == 1,
        cases=tuple(results),
    )


def export_phase9_direct_evaluation(
    evaluation: Phase9DirectEvaluation,
    path: str | Path,
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(evaluation.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return target


def build_phase9_direct_release_manifest(
    project_root: str | Path,
) -> Phase9DirectReleaseManifest:
    root = Path(project_root).resolve()
    manifest = Phase9DirectReleaseManifest(
        artifacts=tuple(
            Phase9ArtifactHash(
                artifact_id=artifact_id,
                path=path,
                sha256=sha256(root / path),
            )
            for artifact_id, path in _RELEASE_ARTIFACTS
        )
    )
    target = root / "artifacts/evaluations/phase9-stage9.2-release-manifest-v1.json"
    target.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_phase9_direct_release_manifest(
    manifest: Phase9DirectReleaseManifest,
    project_root: str | Path,
) -> Phase9BaselineVerification:
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
        if sha256(candidate) != artifact.sha256:
            errors.append(f"{artifact.artifact_id}: SHA-256 mismatch")
    return Phase9BaselineVerification(
        valid=not errors,
        checked_artifact_count=checked,
        checked_contract_count=0,
        errors=tuple(errors),
    )


def _artifact_model(artifact_type: ArtifactType):
    from claim_polygraph_ng.domain import (
        ArgumentLedger,
        AtomicClaim,
        ContextVerification,
        FullReportCitationAssurance,
        IndependenceAnalysis,
        InvestigationPlan,
        InvestigationProvenance,
        JudgmentPolicyTrace,
        JudgmentReadiness,
        SentenceAudit,
        Verdict,
        VerificationPacketV2,
    )

    return {
        ArtifactType.CLAIM: AtomicClaim,
        ArtifactType.PLAN: InvestigationPlan,
        ArtifactType.INDEPENDENCE: IndependenceAnalysis,
        ArtifactType.PROVENANCE: InvestigationProvenance,
        ArtifactType.CONTEXT_VERIFICATION: ContextVerification,
        ArtifactType.VERIFICATION_PACKET: VerificationPacketV2,
        ArtifactType.ARGUMENT_LEDGER: ArgumentLedger,
        ArtifactType.JUDGMENT_POLICY: JudgmentPolicyTrace,
        ArtifactType.VERDICT: Verdict,
        ArtifactType.AUDIT: SentenceAudit,
        ArtifactType.FULL_REPORT_ASSURANCE: FullReportCitationAssurance,
        ArtifactType.READINESS: JudgmentReadiness,
    }[artifact_type]


def sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
