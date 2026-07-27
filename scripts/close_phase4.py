"""Produce the final Phase 4 gate audit from immutable experiment artifacts."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase4_gates import (
    audit_phase4_gates,
    export_phase4_gate_audit,
)
from claim_polygraph_ng.evaluation.phase4_pilot import (
    Phase4DryRunSummary,
    Phase4PaidPilotSummary,
    Phase4PilotPreflight,
)

ROOT = Path(__file__).parents[1]
ARTIFACTS = ROOT / "artifacts/evaluations"


def _load(model, name: str):
    return model.model_validate_json((ARTIFACTS / name).read_text(encoding="utf-8"))


def main() -> int:
    audit = audit_phase4_gates(
        _load(Phase4PilotPreflight, "phase4-pilot-preflight.json"),
        _load(Phase4DryRunSummary, "phase4-pilot-dry-run.json"),
        _load(Phase4PaidPilotSummary, "phase4-paid-pilot-final.json"),
    )
    output = export_phase4_gate_audit(audit, ARTIFACTS / "phase4-final-gate-audit.json")
    print(f"Phase complete: {audit.phase_complete}")
    print(f"Multi-agent promoted: {audit.multi_agent_promoted}")
    print(f"Default workflow: {audit.default_workflow}")
    print(f"Artifact: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
