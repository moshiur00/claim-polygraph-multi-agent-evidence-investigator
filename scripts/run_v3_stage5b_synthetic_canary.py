"""Run one non-benchmark temporal canary through the real provider boundary."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from run_v3_stage5_development import _load_api_key

from claim_polygraph_ng.analysis.assisted_verification_construction import (
    ASSISTED_CONSTRUCTION_PROMPT_VERSION,
    AssistedConstructionKind,
    AssistedConstructionRequest,
)
from claim_polygraph_ng.analysis.bounded_assisted_construction import (
    BoundedAssistedConstructionService,
)
from claim_polygraph_ng.domain import Evidence, EvidenceStance
from claim_polygraph_ng.persistence.paid_operations import SQLitePaidOperationLedger
from claim_polygraph_ng.providers.idempotent import IdempotentStructuredModelProvider
from claim_polygraph_ng.providers.openai import OpenAIStructuredModelProvider
from claim_polygraph_ng.telemetry import TelemetryCollector

MODEL = "gpt-5.6-luna"
CANARY_ID = "v3.5b-synthetic-temporal-canary-v1"
EXPERIMENT_ID = uuid5(NAMESPACE_URL, f"claim-polygraph/{CANARY_ID}")
CLAIM_TEXT = "Regulation X began applying on 25 May 2018."
EVIDENCE_TEXT = "The official register states Regulation X began applying on 25 May 2018."


async def main() -> None:
    root = Path(__file__).parents[1]
    claim_id = uuid5(NAMESPACE_URL, f"{CANARY_ID}/claim")
    evidence = Evidence(
        evidence_id=uuid5(NAMESPACE_URL, f"{CANARY_ID}/evidence"),
        claim_id=claim_id,
        source_id=uuid5(NAMESPACE_URL, f"{CANARY_ID}/source"),
        passage=EVIDENCE_TEXT,
        stance=EvidenceStance.CONTEXT,
        relevance_score=1,
    )
    request = AssistedConstructionRequest(
        claim_id=claim_id,
        claim_text=CLAIM_TEXT,
        failed_construction_id=uuid5(NAMESPACE_URL, f"{CANARY_ID}/failure"),
        approved_evidence_ids=(evidence.evidence_id,),
        construction_kind=AssistedConstructionKind.TEMPORAL_STATUS,
    )
    ledger = SQLitePaidOperationLedger(root / "data/v3-stage5b-paid-operations.db")
    telemetry = TelemetryCollector(root / "data/v3-stage5b-telemetry.db")
    telemetry.initialize()
    provider = OpenAIStructuredModelProvider(
        api_key=_load_api_key(root),
        model=MODEL,
        timeout_seconds=60,
    )
    wrapped = IdempotentStructuredModelProvider(
        provider=provider,
        ledger=ledger,
        investigation_id=EXPERIMENT_ID,
        node_id=f"verification-construction:{CANARY_ID}",
        worker_id="v3.5b-canary",
    )
    service = BoundedAssistedConstructionService(
        provider=wrapped,
        ledger=ledger,
        investigation_id=EXPERIMENT_ID,
        telemetry=telemetry,
    )

    result: dict
    try:
        proposal = await service.propose(request=request, evidence=(evidence,))
        result = {
            "disposition": "validated_proposal",
            "proposal": proposal.model_dump(mode="json"),
        }
    except Exception as error:
        result = {
            "disposition": "safe_failure",
            "error_type": type(error).__name__,
            "error": str(error)[:1_000],
        }

    receipts = ledger.list_receipts(EXPERIMENT_ID)
    cost = ledger.cost_ledger(EXPERIMENT_ID)
    snapshot = telemetry.snapshot()
    artifact = {
        "artifact_id": "verification-construction-v3-stage5b-synthetic-canary-v1",
        "status": (
            "passed"
            if result["disposition"] == "validated_proposal"
            else "failed_safe"
        ),
        "synthetic_fixture": True,
        "fixture_sha256": hashlib.sha256(
            f"{CLAIM_TEXT}\n{EVIDENCE_TEXT}".encode()
        ).hexdigest(),
        "prompt_version": ASSISTED_CONSTRUCTION_PROMPT_VERSION,
        "model": MODEL,
        "provider_attempts": sum(item.attempt_number for item in receipts),
        "completed_paid_operations": cost.model_operation_count,
        "input_tokens": cost.input_tokens,
        "output_tokens": cost.output_tokens,
        "estimated_cost_usd": cost.estimated_cost_usd,
        "benchmark_cases_loaded": 0,
        "development_cases_exposed_to_model": 0,
        "calibration_cases_exposed_to_model": 0,
        "held_out_cases_exposed_to_model": 0,
        "telemetry": {
            "spans": snapshot.spans,
            "traces": snapshot.traces,
            "metric_series": len(snapshot.metrics),
        },
        "receipt_statuses": [item.status.value for item in receipts],
        "result": result,
    }
    destination = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage5b-synthetic-canary-v1.json"
    )
    destination.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print(
        f"status={artifact['status']} attempts={artifact['provider_attempts']} "
        f"completed={cost.model_operation_count} cost_usd={cost.estimated_cost_usd:.6f}"
    )


if __name__ == "__main__":
    asyncio.run(main())
