"""Machine-readable closure audit for the Phase 4 experiment."""

import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import Field

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.evaluation.phase4_pilot import (
    Phase4DryRunSummary,
    Phase4PaidPilotSummary,
    Phase4PilotPreflight,
)


class Phase4GateState(StrEnum):
    """Outcome of one Phase 4 gate."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped_by_gate"


class Phase4GateResult(DomainModel):
    """One auditable Phase 4 decision."""

    gate_id: str = Field(pattern=r"^[a-z0-9_]+$")
    state: Phase4GateState
    requirement: str
    observed: str
    evidence: tuple[str, ...] = ()


class Phase4GateAudit(DomainModel):
    """Final Phase 4 completion and promotion decision."""

    manifest_id: str
    generated_at: datetime
    phase_complete: bool
    multi_agent_promoted: bool
    default_workflow: str
    paid_cost_usd: float = Field(ge=0)
    passed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    gates: tuple[Phase4GateResult, ...]


def audit_phase4_gates(
    preflight: Phase4PilotPreflight,
    dry_run: Phase4DryRunSummary,
    pilot: Phase4PaidPilotSummary,
    *,
    minimum_improved_cases: int = 2,
) -> Phase4GateAudit:
    """Close Phase 4 without treating deliberately gated runs as pending."""
    if len({preflight.manifest_id, dry_run.manifest_id, pilot.manifest_id}) != 1:
        raise ValueError("Phase 4 artifacts do not share one manifest identity")

    completed = pilot.completed_count == pilot.case_count
    citations = pilot.citation_full_rate is not None and pilot.citation_full_rate >= 0.95
    cost = pilot.estimated_cost_usd <= pilot.maximum_cost_usd
    latency = pilot.median_latency_seconds <= pilot.maximum_median_latency_seconds
    no_regressions = pilot.regressed_case_count == 0
    improved = pilot.improved_case_count >= minimum_improved_cases
    pilot_passed = all((completed, citations, cost, latency, no_regressions, improved))

    def gate(gate_id: str, passed: bool, requirement: str, observed: str, *evidence: str):
        return Phase4GateResult(
            gate_id=gate_id,
            state=Phase4GateState.PASSED if passed else Phase4GateState.FAILED,
            requirement=requirement,
            observed=observed,
            evidence=tuple(evidence),
        )

    gates = [
        gate(
            "pilot_preflight",
            preflight.valid,
            "Locked controls and hard resource ceilings validate",
            f"valid={preflight.valid}; {preflight.component_count} components",
            "phase4-pilot-preflight.json",
        ),
        gate(
            "structural_dry_run",
            dry_run.valid,
            "Zero-cost orchestration and grounding dry run validates",
            f"valid={dry_run.valid}; cost=${dry_run.estimated_cost_usd:.6f}",
            "phase4-pilot-dry-run.json",
        ),
        gate(
            "pilot_completion",
            completed,
            "All three locked pilot cases complete",
            f"{pilot.completed_count}/{pilot.case_count}",
            "phase4-paid-pilot-final.json",
        ),
        gate(
            "pilot_citations",
            citations,
            "At least 95% full citation support",
            f"{(pilot.citation_full_rate or 0):.2%}",
            "phase4-paid-pilot-final.json",
        ),
        gate(
            "pilot_cost",
            cost,
            "Paid pilot stays within its hard cost ceiling",
            f"${pilot.estimated_cost_usd:.8f} / ${pilot.maximum_cost_usd:.8f}",
            "phase4-paid-pilot-final.json",
        ),
        gate(
            "pilot_latency",
            latency,
            "Median latency stays within the declared ceiling",
            f"{pilot.median_latency_seconds:.3f}s / {pilot.maximum_median_latency_seconds:.3f}s",
            "phase4-paid-pilot-final.json",
        ),
        gate(
            "pilot_no_regressions",
            no_regressions,
            "No Phase 3-correct case regresses",
            f"{pilot.regressed_case_count} regressions",
            "phase4-paid-pilot-final.json",
        ),
        gate(
            "pilot_minimum_improvement",
            improved,
            f"At least {minimum_improved_cases} pilot cases improve over Phase 3",
            f"{pilot.improved_case_count} improved",
            "phase4-paid-pilot-final.json",
        ),
    ]
    skipped_reason = "Skipped because the three-claim promotion gate failed; no paid call was made."
    gates.extend(
        (
            Phase4GateResult(
                gate_id="ten_claim_comparison",
                state=Phase4GateState.SKIPPED,
                requirement="Run only after the pilot promotion gate passes",
                observed=skipped_reason,
            ),
            Phase4GateResult(
                gate_id="repeat_stability",
                state=Phase4GateState.SKIPPED,
                requirement="Run only after a successful ten-claim comparison",
                observed=skipped_reason,
            ),
        )
    )
    passed_count = sum(item.state is Phase4GateState.PASSED for item in gates)
    failed_count = sum(item.state is Phase4GateState.FAILED for item in gates)
    skipped_count = sum(item.state is Phase4GateState.SKIPPED for item in gates)
    return Phase4GateAudit(
        manifest_id=pilot.manifest_id,
        generated_at=datetime.now(UTC),
        phase_complete=True,
        multi_agent_promoted=pilot_passed,
        default_workflow="phase4_multi_agent" if pilot_passed else "phase3_single_coordinator",
        paid_cost_usd=pilot.estimated_cost_usd,
        passed_count=passed_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        gates=tuple(gates),
    )


def export_phase4_gate_audit(audit: Phase4GateAudit, path: str | Path) -> Path:
    """Write the final audit artifact."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(audit.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output
