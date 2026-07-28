"""Demonstrate Stage 7.2 interrupt, restart, and idempotent resume."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import NAMESPACE_URL, uuid5

from claim_polygraph_ng.application import DurableFixtureLangGraphWorkflow
from claim_polygraph_ng.domain import (
    FixtureGraphRequest,
    ReviewDecision,
    ReviewDecisionKind,
    VerdictLabel,
)

ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "artifacts/evaluations/phase7-stage7.2-durable-resume-v1.json"


def main() -> int:
    request = FixtureGraphRequest(
        graph_run_id=uuid5(NAMESPACE_URL, "claim-polygraph/phase7/stage7.2"),
        claim_text="The Great Wall is visible from the Moon with the unaided eye.",
        approved_evidence_ids=tuple(
            uuid5(NAMESPACE_URL, f"claim-polygraph/CPNG-005/evidence/{index}")
            for index in range(1, 4)
        ),
        authoritative_verdict=VerdictLabel.CONTRADICTED,
        review_required=True,
        review_reason="The absolute statement requires explicit human confirmation.",
    )
    decision = ReviewDecision(
        decision_id=uuid5(NAMESPACE_URL, "claim-polygraph/phase7/stage7.2/decision"),
        kind=ReviewDecisionKind.APPROVE,
        reviewer_identity="Stage 7.2 deterministic fixture reviewer",
        rationale="Approved solely to test durable checkpoint and resume behavior.",
    )
    with TemporaryDirectory(prefix="claim-polygraph-phase7-") as temporary:
        database = Path(temporary) / "checkpoint.db"
        with DurableFixtureLangGraphWorkflow(database, enabled=True) as first:
            paused = first.start(request)
        with DurableFixtureLangGraphWorkflow(database, enabled=True) as restarted:
            reconstructed = restarted.snapshot(str(request.graph_run_id))
            completed = restarted.resume(str(request.graph_run_id), decision)
            replayed = restarted.resume(str(request.graph_run_id), decision)
        pre_counts_reused = all(
            completed.operation_counts[node] == count == 1
            for node, count in paused.operation_counts.items()
        )
        artifact = {
            "evaluation_id": "phase7-stage7.2-durable-resume-v1",
            "checkpoint_reconstructed": reconstructed == paused,
            "pre_interrupt_operations_reused": pre_counts_reused,
            "idempotent_decision_replay": replayed == completed,
            "provider_usage": {
                "model_calls": 0,
                "search_calls": 0,
                "network_calls": 0,
                "estimated_cost_usd": 0.0,
            },
            "paused": paused.model_dump(mode="json"),
            "completed": completed.model_dump(mode="json"),
        }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(f"Interrupted: {paused.status.value}")
    print(f"Checkpoint reconstructed: {artifact['checkpoint_reconstructed']}")
    print(f"Pre-interrupt operations reused: {pre_counts_reused}")
    print(f"Idempotent decision replay: {artifact['idempotent_decision_replay']}")
    print(f"Completed: {completed.status.value}")
    print(f"Final verdict: {completed.final_verdict.value}")
    print("Provider usage: models=0, searches=0, network=0, cost=$0.0000")
    print(f"Artifact: {OUTPUT.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
