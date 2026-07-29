"""Run and hash the zero-cost Stage 9.5 paid-operation safety gate."""

from pathlib import Path
from tempfile import TemporaryDirectory

from claim_polygraph_ng.evaluation.phase9_paid_operations import (
    build_phase9_paid_operation_release_manifest,
    evaluate_phase9_paid_operation_gate,
    export_phase9_paid_operation_gate,
    verify_phase9_paid_operation_release_manifest,
)


def main() -> None:
    root = Path(__file__).parents[1]
    with TemporaryDirectory(prefix="claim-polygraph-phase9-5-") as temporary:
        gate = evaluate_phase9_paid_operation_gate(Path(temporary) / "receipts.db")
    export_phase9_paid_operation_gate(
        gate,
        root / "artifacts/evaluations/phase9-stage9.5-paid-operation-safety-v1.json",
    )
    manifest = build_phase9_paid_operation_release_manifest(root)
    verification = verify_phase9_paid_operation_release_manifest(manifest, root)
    passed = all(
        (
            gate.completed_replay_without_execution,
            gate.active_concurrency_blocked,
            gate.stale_pre_call_reclaimable,
            gate.stale_in_flight_ambiguous,
            gate.unique_cost_entry_count == 1,
            verification.valid,
        )
    )
    print(
        f"Evaluation: {gate.evaluation_id}\n"
        f"Completed replay: {'passed' if gate.completed_replay_without_execution else 'failed'}\n"
        f"Concurrent claim: {'passed' if gate.active_concurrency_blocked else 'failed'}\n"
        f"Pre-call recovery: {'passed' if gate.stale_pre_call_reclaimable else 'failed'}\n"
        f"Ambiguous-call protection: {'passed' if gate.stale_in_flight_ambiguous else 'failed'}\n"
        f"Unique cost entries: {gate.unique_cost_entry_count}\n"
        f"Artifacts checked: {verification.checked_artifact_count}\n"
        f"Valid: {'yes' if passed else 'no'}"
    )
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
