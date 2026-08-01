"""Run V3.5a on untouched, typed-compatible development cases only."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from run_v3_stage5_development import _load_api_key

from claim_polygraph_ng.analysis.assisted_verification_construction import (
    ASSISTED_CONSTRUCTION_PROMPT_VERSION,
    AssistedConstructionEligibility,
    AssistedConstructionKind,
    AssistedConstructionRequest,
    classify_assisted_eligibility,
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
EXPERIMENT_ID = uuid5(NAMESPACE_URL, "claim-polygraph/v3.5a/development/v2")
PREVIOUSLY_ATTEMPTED = frozenset({"V3-046"})


async def main() -> None:
    root = Path(__file__).parents[1]
    cases, selection = select_v3_development_cases(
        root / "benchmarks/verification_construction_v3_approved_frozen_v2.json"
    )
    ledger = SQLitePaidOperationLedger(root / "data/v3-stage5a-paid-operations.db")
    telemetry = TelemetryCollector(root / "data/v3-stage5a-telemetry.db")
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
        eligibility = classify_assisted_eligibility(case.claim_text)
        if case.case_id in PREVIOUSLY_ATTEMPTED:
            results.append(
                {
                    "case_id": case.case_id,
                    "eligibility": eligibility.value,
                    "disposition": "locked_previous_attempt",
                    "provider_attempt": False,
                }
            )
            continue
        if eligibility not in {
            AssistedConstructionEligibility.NUMERICAL,
            AssistedConstructionEligibility.TEMPORAL,
        }:
            results.append(
                {
                    "case_id": case.case_id,
                    "eligibility": eligibility.value,
                    "disposition": "human_review_ineligible",
                    "provider_attempt": False,
                }
            )
            continue

        claim_id = uuid5(NAMESPACE_URL, f"claim-polygraph/v3.5a/{case.case_id}")
        failed_id = uuid5(NAMESPACE_URL, f"{claim_id}/failed-construction")
        evidence = tuple(
            Evidence(
                evidence_id=uuid5(
                    NAMESPACE_URL,
                    f"claim-polygraph/v3.5a/{case.case_id}/{item.evidence_id}",
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
            construction_kind=(
                AssistedConstructionKind.NUMERICAL
                if eligibility is AssistedConstructionEligibility.NUMERICAL
                else AssistedConstructionKind.TEMPORAL_STATUS
            ),
        )
        wrapped = IdempotentStructuredModelProvider(
            provider=provider,
            ledger=ledger,
            investigation_id=EXPERIMENT_ID,
            node_id=f"verification-construction-v2:{case.case_id}",
            worker_id="v3.5a-development",
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
                    "eligibility": eligibility.value,
                    "disposition": "validated_proposal",
                    "provider_attempt": True,
                    "proposal": proposal.model_dump(mode="json"),
                }
            )
        except Exception as error:
            results.append(
                {
                    "case_id": case.case_id,
                    "eligibility": eligibility.value,
                    "disposition": "human_review_validation_or_provider_failure",
                    "provider_attempt": True,
                    "error_type": type(error).__name__,
                    "error": str(error)[:500],
                }
            )

    receipts = ledger.list_receipts(EXPERIMENT_ID)
    cost = ledger.cost_ledger(EXPERIMENT_ID)
    snapshot = telemetry.snapshot()
    artifact = {
        "artifact_id": "verification-construction-v3-stage5a-development-run-v1",
        "status": "completed",
        "prompt_version": ASSISTED_CONSTRUCTION_PROMPT_VERSION,
        "model": MODEL,
        "split": "development",
        "development_cases": 20,
        "fallback_eligible_cases": len(selection.assisted_case_ids),
        "provider_attempts": sum(item.attempt_number for item in receipts),
        "completed_paid_operations": cost.model_operation_count,
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
        "verification-construction-v3-stage5a-development-run-v1.json"
    )
    destination.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print(
        f"attempts={artifact['provider_attempts']} "
        f"completed={cost.model_operation_count} cost_usd={cost.estimated_cost_usd:.6f}"
    )


if __name__ == "__main__":
    asyncio.run(main())
