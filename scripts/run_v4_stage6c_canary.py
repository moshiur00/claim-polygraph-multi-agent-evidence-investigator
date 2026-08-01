"""Run the final one-call V4.6c temporal canary."""

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

EXPERIMENT_ID = uuid5(NAMESPACE_URL, "claim-polygraph/v4.6c/final-synthetic-canary/v1")


def _secret(root: Path, name: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    for line in (root / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{name}="):
            return line.partition("=")[2].strip().strip("\"'")
    raise ValueError(f"{name} is unavailable")


async def main() -> None:
    root = Path(__file__).parents[1]
    manifest_path = (
        root / "artifacts/evaluations/verification-construction-v4-stage6c-canary-manifest-v1.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    fixture = manifest["fixture"]
    claim_id = uuid5(NAMESPACE_URL, f"{fixture['canary_id']}/claim")
    evidence = Evidence(
        evidence_id=uuid5(NAMESPACE_URL, f"{fixture['canary_id']}/evidence"),
        claim_id=claim_id,
        source_id=uuid5(NAMESPACE_URL, f"{fixture['canary_id']}/source"),
        passage=fixture["evidence_text"],
        stance=EvidenceStance.CONTEXT,
        relevance_score=1,
    )
    request = AssistedConstructionRequest(
        claim_id=claim_id,
        claim_text=fixture["claim_text"],
        failed_construction_id=uuid5(NAMESPACE_URL, f"{fixture['canary_id']}/construction"),
        approved_evidence_ids=(evidence.evidence_id,),
        construction_kind=AssistedConstructionKind.TEMPORAL_STATUS,
    )
    ledger = SQLitePaidOperationLedger(root / "data/v4-stage6c-paid-operations.db")
    if ledger.list_receipts(EXPERIMENT_ID):
        raise ValueError("V4.6c requires a fresh empty receipt identity")
    telemetry = TelemetryCollector(root / "data/v4-stage6c-telemetry.db")
    telemetry.initialize()
    provider = OpenAIStructuredModelProvider(
        api_key=_secret(root, "OPENAI_API_KEY"),
        model=manifest["model"],
        timeout_seconds=60,
    )
    wrapped = IdempotentStructuredModelProvider(
        provider=provider,
        ledger=ledger,
        investigation_id=EXPERIMENT_ID,
        node_id=f"verification-construction:{fixture['canary_id']}",
        worker_id="v4.6c-canary",
    )
    service = BoundedAssistedConstructionService(
        provider=wrapped,
        ledger=ledger,
        investigation_id=EXPERIMENT_ID,
        budget=AssistedConstructionBudget(
            maximum_total_calls=1,
            maximum_input_tokens=6000,
            maximum_output_tokens=900,
            maximum_total_cost_usd=0.25,
        ),
        telemetry=telemetry,
    )
    try:
        proposal = await service.propose(request=request, evidence=(evidence,))
        replay = await service.propose(request=request, evidence=(evidence,))
        result = {
            "disposition": "validated_proposal",
            "proposal": proposal.model_dump(mode="json"),
            "cached_replay_equal": replay == proposal,
        }
    except Exception as error:
        result = {
            "disposition": "safe_failure",
            "error_type": type(error).__name__,
            "error": str(error)[:1000],
            "cached_replay_equal": False,
        }
    receipts = ledger.list_receipts(EXPERIMENT_ID)
    cost = ledger.cost_ledger(EXPERIMENT_ID)
    snapshot = telemetry.snapshot()
    artifact = {
        "artifact_id": "verification-construction-v4-stage6c-canary-result-v1",
        "status": (
            "passed"
            if result["disposition"] == "validated_proposal" and result["cached_replay_equal"]
            else "failed_safe"
        ),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "model": manifest["model"],
        "provider_attempts": cost.attempted_operation_count,
        "completed_paid_operations": cost.completed_operation_count,
        "failed_paid_operations": cost.failed_operation_count,
        "input_tokens": cost.input_tokens,
        "output_tokens": cost.output_tokens,
        "estimated_cost_usd": cost.estimated_cost_usd,
        "estimated_cost_upper_bound_usd": (cost.estimated_cost_upper_bound_usd),
        "receipt_statuses": [item.status.value for item in receipts],
        "usage_dispositions": [item.usage_disposition.value for item in receipts],
        "telemetry": {
            "spans": snapshot.spans,
            "traces": snapshot.traces,
            "metric_series": len(snapshot.metrics),
        },
        "dataset_exposure": manifest["dataset_exposure"],
        "result": result,
    }
    destination = (
        root / "artifacts/evaluations/verification-construction-v4-stage6c-canary-result-v1.json"
    )
    destination.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print(
        f"status={artifact['status']} "
        f"attempts={artifact['provider_attempts']} "
        f"cost_usd={artifact['estimated_cost_usd']:.8f}"
    )


if __name__ == "__main__":
    asyncio.run(main())
