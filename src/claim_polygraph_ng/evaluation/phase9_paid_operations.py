"""Stage 9.5 offline paid-operation safety gate and release manifest."""

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.investigation import ModelCallUsage, ModelTask
from claim_polygraph_ng.domain.paid_operations import (
    PaidOperationKind,
    PaidOperationSpec,
    PaidReceiptDecision,
)
from claim_polygraph_ng.evaluation.phase9_baseline import (
    Phase9ArtifactHash,
    Phase9BaselineVerification,
)
from claim_polygraph_ng.persistence.paid_operations import SQLitePaidOperationLedger


class Phase9PaidOperationGate(DomainModel):
    evaluation_id: str = "phase9-stage9.5-paid-operation-safety-v1"
    completed_replay_without_execution: bool
    active_concurrency_blocked: bool
    stale_pre_call_reclaimable: bool
    stale_in_flight_ambiguous: bool
    unique_cost_entry_count: int
    estimated_cost_usd: float
    external_model_calls: int = 0
    live_search_calls: int = 0
    network_fetches: int = 0
    pdf_downloads: int = 0


class Phase9PaidOperationReleaseManifest(DomainModel):
    manifest_id: str = "phase9-stage9.5-release-manifest-v1"
    artifacts: tuple[Phase9ArtifactHash, ...]
    external_model_calls: int = 0
    live_search_calls: int = 0
    network_fetches: int = 0
    pdf_downloads: int = 0


_ARTIFACTS = (
    ("receipt_contracts", "src/claim_polygraph_ng/domain/paid_operations.py"),
    ("receipt_repository", "src/claim_polygraph_ng/persistence/paid_operations.py"),
    ("provider_decorators", "src/claim_polygraph_ng/providers/idempotent.py"),
    ("receipt_tests", "tests/unit/test_paid_operation_receipts.py"),
    ("stage9_4_manifest", "artifacts/evaluations/phase9-stage9.4-release-manifest-v1.json"),
    ("stage9_5_gate", "artifacts/evaluations/phase9-stage9.5-paid-operation-safety-v1.json"),
    ("stage9_5_report", "docs/PHASE_9_STAGE_9.5_COMPLETION_REPORT.md"),
)


def evaluate_phase9_paid_operation_gate(
    database_path: str | Path,
) -> Phase9PaidOperationGate:
    ledger = SQLitePaidOperationLedger(database_path)
    investigation_id = uuid4()
    now = datetime.now(UTC)
    completed_spec = _spec(investigation_id, "completed")
    first = ledger.reserve(completed_spec, worker_id="worker-one", now=now)
    ledger.mark_provider_started(
        completed_spec.operation_key,
        worker_id="worker-one",
        now=now,
    )
    ledger.complete(
        completed_spec.operation_key,
        worker_id="worker-one",
        result_payload='{"result":"stored"}',
        usage=ModelCallUsage(
            provider_id="fixture-provider",
            model="fixture-model",
            task=ModelTask.NORMALIZE_CLAIM,
            duration_seconds=0.1,
            input_tokens=10,
            output_tokens=5,
            estimated_cost_usd=0.001,
            output_valid=True,
        ),
        now=now,
    )
    cached = ledger.reserve(completed_spec, worker_id="worker-two", now=now)

    reserved_spec = _spec(investigation_id, "reserved")
    ledger.reserve(
        reserved_spec,
        worker_id="worker-one",
        lease_seconds=1,
        now=now,
    )
    active = ledger.reserve(reserved_spec, worker_id="worker-two", now=now)
    reclaimed = ledger.reserve(
        reserved_spec,
        worker_id="worker-two",
        now=now + timedelta(seconds=2),
    )

    ambiguous_spec = _spec(investigation_id, "ambiguous")
    ledger.reserve(
        ambiguous_spec,
        worker_id="worker-one",
        lease_seconds=1,
        now=now,
    )
    ledger.mark_provider_started(
        ambiguous_spec.operation_key,
        worker_id="worker-one",
        now=now,
    )
    ambiguous = ledger.reserve(
        ambiguous_spec,
        worker_id="worker-two",
        now=now + timedelta(seconds=2),
    )
    costs = ledger.cost_ledger(investigation_id)
    return Phase9PaidOperationGate(
        completed_replay_without_execution=(
            first.decision is PaidReceiptDecision.EXECUTE
            and cached.decision is PaidReceiptDecision.RETURN_CACHED
        ),
        active_concurrency_blocked=active.decision is PaidReceiptDecision.ACTIVE,
        stale_pre_call_reclaimable=reclaimed.decision is PaidReceiptDecision.EXECUTE,
        stale_in_flight_ambiguous=ambiguous.decision is PaidReceiptDecision.AMBIGUOUS,
        unique_cost_entry_count=costs.completed_operation_count,
        estimated_cost_usd=costs.estimated_cost_usd,
    )


def export_phase9_paid_operation_gate(
    gate: Phase9PaidOperationGate,
    path: str | Path,
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(gate.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return target


def build_phase9_paid_operation_release_manifest(
    root: str | Path,
) -> Phase9PaidOperationReleaseManifest:
    project = Path(root).resolve()
    manifest = Phase9PaidOperationReleaseManifest(
        artifacts=tuple(
            Phase9ArtifactHash(
                artifact_id=artifact_id,
                path=path,
                sha256=_sha256(project / path),
            )
            for artifact_id, path in _ARTIFACTS
        )
    )
    target = project / "artifacts/evaluations/phase9-stage9.5-release-manifest-v1.json"
    target.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_phase9_paid_operation_release_manifest(
    manifest: Phase9PaidOperationReleaseManifest,
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
        checked_contract_count=1,
        errors=tuple(errors),
    )


def _spec(investigation_id, suffix):
    digest = hashlib.sha256(suffix.encode()).hexdigest()
    return PaidOperationSpec(
        operation_key=f"paid:{digest}",
        investigation_id=investigation_id,
        node_id=f"node-{suffix}",
        kind=PaidOperationKind.MODEL,
        provider="fixture-provider",
        model_or_engine="fixture-model",
        task="fixture-task",
        canonical_input_sha256=digest,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
