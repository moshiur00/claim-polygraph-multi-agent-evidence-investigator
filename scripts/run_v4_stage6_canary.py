"""Run two receipt-protected V4.6 synthetic provider canaries."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from claim_polygraph_ng.analysis.assisted_verification_construction import (
    AssistedConstructionKind,
    AssistedConstructionRequest,
)
from claim_polygraph_ng.analysis.bounded_assisted_construction import (
    AssistedConstructionBudget,
    BoundedAssistedConstructionService,
)
from claim_polygraph_ng.domain import Evidence, EvidenceStance
from claim_polygraph_ng.persistence.paid_operations import (
    SQLitePaidOperationLedger,
)
from claim_polygraph_ng.providers.idempotent import (
    IdempotentStructuredModelProvider,
)
from claim_polygraph_ng.providers.openai import (
    OpenAIStructuredModelProvider,
)
from claim_polygraph_ng.telemetry import TelemetryCollector

EXPERIMENT_ID = uuid5(NAMESPACE_URL, "claim-polygraph/v4.6/synthetic-canary/v1")


def _secret(root: Path, name: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    for line in (root / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{name}="):
            return line.partition("=")[2].strip().strip("\"'")
    raise ValueError(f"{name} is unavailable")


async def _execute_fixture(
    *,
    fixture: dict,
    provider: OpenAIStructuredModelProvider,
    ledger: SQLitePaidOperationLedger,
    telemetry: TelemetryCollector,
) -> dict:
    canary_id = fixture["canary_id"]
    claim_id = uuid5(NAMESPACE_URL, f"{canary_id}/claim")
    evidence = Evidence(
        evidence_id=uuid5(NAMESPACE_URL, f"{canary_id}/evidence"),
        claim_id=claim_id,
        source_id=uuid5(NAMESPACE_URL, f"{canary_id}/source"),
        passage=fixture["evidence_text"],
        stance=EvidenceStance.CONTEXT,
        relevance_score=1,
    )
    request = AssistedConstructionRequest(
        claim_id=claim_id,
        claim_text=fixture["claim_text"],
        failed_construction_id=uuid5(NAMESPACE_URL, f"{canary_id}/construction"),
        approved_evidence_ids=(evidence.evidence_id,),
        construction_kind=AssistedConstructionKind(fixture["kind"]),
    )
    wrapped = IdempotentStructuredModelProvider(
        provider=provider,
        ledger=ledger,
        investigation_id=EXPERIMENT_ID,
        node_id=f"verification-construction:{canary_id}",
        worker_id="v4.6-canary",
    )
    service = BoundedAssistedConstructionService(
        provider=wrapped,
        ledger=ledger,
        investigation_id=EXPERIMENT_ID,
        budget=AssistedConstructionBudget(
            maximum_total_calls=2,
            maximum_input_tokens=6000,
            maximum_output_tokens=900,
            maximum_total_cost_usd=0.75,
        ),
        telemetry=telemetry,
    )
    try:
        proposal = await service.propose(request=request, evidence=(evidence,))
        replay = await service.propose(request=request, evidence=(evidence,))
        return {
            "canary_id": canary_id,
            "disposition": "validated_proposal",
            "proposal": proposal.model_dump(mode="json"),
            "cached_replay_equal": replay == proposal,
        }
    except Exception as error:
        return {
            "canary_id": canary_id,
            "disposition": "safe_failure",
            "error_type": type(error).__name__,
            "error": str(error)[:1000],
            "cached_replay_equal": False,
        }


async def main() -> None:
    root = Path(__file__).parents[1]
    manifest_path = (
        root / "artifacts/evaluations/verification-construction-v4-stage6-canary-manifest-v1.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["status"] != "frozen":
        raise ValueError("V4.6 manifest is not frozen")
    database = root / "data/v4-stage6-paid-operations.db"
    telemetry_database = root / "data/v4-stage6-telemetry.db"
    ledger = SQLitePaidOperationLedger(database)
    telemetry = TelemetryCollector(telemetry_database)
    telemetry.initialize()
    provider = OpenAIStructuredModelProvider(
        api_key=_secret(root, "OPENAI_API_KEY"),
        model=manifest["model"],
        timeout_seconds=60,
    )

    before = ledger.list_receipts(EXPERIMENT_ID)
    if before:
        raise ValueError("V4.6 fresh execution requires an empty experiment ledger")
    results = []
    for fixture in manifest["fixtures"]:
        results.append(
            await _execute_fixture(
                fixture=fixture,
                provider=provider,
                ledger=ledger,
                telemetry=telemetry,
            )
        )

    receipts_before_cancel = ledger.list_receipts(EXPERIMENT_ID)
    cancellation_receipt_count_before = len(receipts_before_cancel)
    cancel_fixture = manifest["fixtures"][0]
    cancel_claim_id = uuid5(NAMESPACE_URL, "v4.6/cancel/claim")
    cancel_evidence = Evidence(
        evidence_id=uuid5(NAMESPACE_URL, "v4.6/cancel/evidence"),
        claim_id=cancel_claim_id,
        source_id=uuid5(NAMESPACE_URL, "v4.6/cancel/source"),
        passage=cancel_fixture["evidence_text"],
        stance=EvidenceStance.CONTEXT,
        relevance_score=1,
    )
    cancel_request = AssistedConstructionRequest(
        claim_id=cancel_claim_id,
        claim_text=cancel_fixture["claim_text"],
        failed_construction_id=uuid5(NAMESPACE_URL, "v4.6/cancel/construction"),
        approved_evidence_ids=(cancel_evidence.evidence_id,),
        construction_kind=AssistedConstructionKind.NUMERICAL_SCALAR,
    )
    cancel_provider = IdempotentStructuredModelProvider(
        provider=provider,
        ledger=ledger,
        investigation_id=EXPERIMENT_ID,
        node_id="verification-construction:v4.6-cancel",
        worker_id="v4.6-canary",
    )
    cancel_service = BoundedAssistedConstructionService(
        provider=cancel_provider,
        ledger=ledger,
        investigation_id=EXPERIMENT_ID,
        cancellation_requested=lambda: True,
    )
    cancellation_error = None
    try:
        await cancel_service.propose(request=cancel_request, evidence=(cancel_evidence,))
    except Exception as error:
        cancellation_error = type(error).__name__

    receipts = ledger.list_receipts(EXPERIMENT_ID)
    cost = ledger.cost_ledger(EXPERIMENT_ID)
    snapshot = telemetry.snapshot()
    artifact = {
        "artifact_id": "verification-construction-v4-stage6-canary-result-v1",
        "status": (
            "passed"
            if all(
                item["disposition"] == "validated_proposal" and item["cached_replay_equal"]
                for item in results
            )
            else "failed_safe"
        ),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "model": manifest["model"],
        "provider_attempts": cost.attempted_operation_count,
        "completed_paid_operations": cost.completed_operation_count,
        "failed_paid_operations": cost.failed_operation_count,
        "input_tokens": cost.input_tokens,
        "cached_input_tokens": cost.cached_input_tokens,
        "output_tokens": cost.output_tokens,
        "estimated_cost_usd": cost.estimated_cost_usd,
        "estimated_cost_upper_bound_usd": (cost.estimated_cost_upper_bound_usd),
        "cost_is_lower_bound": cost.cost_is_lower_bound,
        "unpriced_operation_count": cost.unpriced_operation_count,
        "receipt_statuses": [item.status.value for item in receipts],
        "usage_dispositions": [item.usage_disposition.value for item in receipts],
        "cancellation": {
            "error_type": cancellation_error,
            "receipt_count_before": cancellation_receipt_count_before,
            "receipt_count_after": len(receipts),
            "created_receipt": (len(receipts) != cancellation_receipt_count_before),
        },
        "telemetry": {
            "spans": snapshot.spans,
            "traces": snapshot.traces,
            "metric_series": len(snapshot.metrics),
        },
        "dataset_exposure": manifest["dataset_exposure"],
        "results": results,
    }
    destination = (
        root / "artifacts/evaluations/verification-construction-v4-stage6-canary-result-v1.json"
    )
    destination.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print(
        f"status={artifact['status']} "
        f"attempts={artifact['provider_attempts']} "
        f"completed={artifact['completed_paid_operations']} "
        f"cost_usd={artifact['estimated_cost_usd']:.6f}"
    )


if __name__ == "__main__":
    asyncio.run(main())
