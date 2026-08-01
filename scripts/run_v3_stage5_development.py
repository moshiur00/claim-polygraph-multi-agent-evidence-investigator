"""Run the frozen V3.5 prompt only on schema-compatible development cases."""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from claim_polygraph_ng.analysis.assisted_verification_construction import (
    ASSISTED_CONSTRUCTION_PROMPT_VERSION,
    AssistedConstructionRequest,
)
from claim_polygraph_ng.analysis.bounded_assisted_construction import (
    BoundedAssistedConstructionService,
)
from claim_polygraph_ng.domain import Evidence, EvidenceStance
from claim_polygraph_ng.evaluation.v3_development import select_v3_development_cases
from claim_polygraph_ng.persistence.paid_operations import SQLitePaidOperationLedger
from claim_polygraph_ng.providers.idempotent import IdempotentStructuredModelProvider
from claim_polygraph_ng.providers.openai import OpenAIStructuredModelProvider
from claim_polygraph_ng.telemetry import TelemetryCollector

MODEL = "gpt-5.6-luna"
EXPERIMENT_ID = uuid5(NAMESPACE_URL, "claim-polygraph/v3.5/development/v1")


def _load_api_key(root: Path) -> str:
    value = os.getenv("OPENAI_API_KEY", "").strip()
    if value:
        return value
    for line in (root / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("OPENAI_API_KEY="):
            return line.partition("=")[2].strip().strip("\"'")
    raise ValueError("OPENAI_API_KEY is unavailable")


def _schema_eligible(claim: str) -> bool:
    """Require two explicit unit-bearing numeric operands before a paid call."""
    unit_values = re.findall(
        r"(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?\s*(?:%|percent(?:age)?\b)",
        claim,
        re.IGNORECASE,
    )
    return len(unit_values) >= 2


async def main() -> None:
    root = Path(__file__).parents[1]
    cases, selection = select_v3_development_cases(
        root / "benchmarks/verification_construction_v3_approved_frozen_v2.json"
    )
    paid_path = root / "data/v3-stage5-paid-operations.db"
    telemetry_path = root / "data/v3-stage5-telemetry.db"
    ledger = SQLitePaidOperationLedger(paid_path)
    telemetry = TelemetryCollector(telemetry_path)
    telemetry.initialize()
    provider = OpenAIStructuredModelProvider(
        api_key=_load_api_key(root),
        model=MODEL,
        timeout_seconds=60,
    )

    assisted_ids = set(selection.assisted_case_ids)
    results: list[dict] = []
    for case in cases:
        if case.case_id not in assisted_ids:
            continue
        if not _schema_eligible(case.claim_text):
            results.append(
                {
                    "case_id": case.case_id,
                    "disposition": "human_review_schema_ineligible",
                    "paid_call": False,
                }
            )
            continue
        claim_id = uuid5(NAMESPACE_URL, f"claim-polygraph/v3.5/{case.case_id}")
        failed_id = uuid5(NAMESPACE_URL, f"{claim_id}/failed-construction")
        evidence = tuple(
            Evidence(
                evidence_id=uuid5(
                    NAMESPACE_URL,
                    f"claim-polygraph/v3.5/{case.case_id}/{item.evidence_id}",
                ),
                claim_id=claim_id,
                source_id=uuid5(NAMESPACE_URL, item.url),
                passage=item.passage,
                stance=EvidenceStance.CONTEXT,
                relevance_score=1,
            )
            for item in case.evidence
        )
        request = AssistedConstructionRequest(
            claim_id=claim_id,
            claim_text=case.claim_text,
            failed_construction_id=failed_id,
            approved_evidence_ids=tuple(item.evidence_id for item in evidence),
        )
        wrapped = IdempotentStructuredModelProvider(
            provider=provider,
            ledger=ledger,
            investigation_id=EXPERIMENT_ID,
            node_id=f"verification-construction:{case.case_id}",
            worker_id="v3.5-development",
        )
        service = BoundedAssistedConstructionService(
            provider=wrapped,
            ledger=ledger,
            investigation_id=EXPERIMENT_ID,
            telemetry=telemetry,
        )
        try:
            proposal = await service.propose(request=request, evidence=evidence)
            results.append(
                {
                    "case_id": case.case_id,
                    "disposition": "validated_proposal",
                    "paid_call": True,
                    "proposal": proposal.model_dump(mode="json"),
                }
            )
        except Exception as error:
            results.append(
                {
                    "case_id": case.case_id,
                    "disposition": "human_review_validation_or_provider_failure",
                    "paid_call": True,
                    "error_type": type(error).__name__,
                    "error": str(error)[:500],
                }
            )

    cost = ledger.cost_ledger(EXPERIMENT_ID)
    receipts = ledger.list_receipts(EXPERIMENT_ID)
    snapshot = telemetry.snapshot()
    artifact = {
        "artifact_id": "verification-construction-v3-stage5-development-run-v1",
        "status": "completed",
        "prompt_version": ASSISTED_CONSTRUCTION_PROMPT_VERSION,
        "model": MODEL,
        "split": "development",
        "development_cases": 20,
        "fallback_eligible_cases": len(selection.assisted_case_ids),
        "paid_calls": cost.model_operation_count,
        "provider_attempts": sum(item.attempt_number for item in receipts),
        "failed_provider_attempts": sum(
            item.attempt_number
            for item in receipts
            if item.status.value.startswith("failed")
        ),
        "receipt_failures": [
            {
                "node_id": item.spec.node_id,
                "status": item.status.value,
                "attempt_number": item.attempt_number,
                "error_class": item.error_class,
                "safe_error": item.safe_error,
            }
            for item in receipts
            if item.status.value.startswith("failed")
        ],
        "estimated_cost_usd": cost.estimated_cost_usd,
        "calibration_cases_exposed_to_model": 0,
        "held_out_cases_exposed_to_model": 0,
        "telemetry": {
            "spans": snapshot.spans,
            "traces": snapshot.traces,
            "metric_series": len(snapshot.metrics),
        },
        "results": results,
    }
    destination = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage5-development-run-v1.json"
    )
    destination.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print(
        f"paid_calls={cost.model_operation_count} "
        f"cost_usd={cost.estimated_cost_usd:.6f}"
    )


if __name__ == "__main__":
    asyncio.run(main())
