"""Run and hash the zero-cost Stage 9.4 authoritative graph skeleton."""

from pathlib import Path
from tempfile import TemporaryDirectory

from claim_polygraph_ng.evaluation.phase9_graph_skeleton import (
    build_phase9_graph_skeleton_release_manifest,
    evaluate_phase9_graph_skeleton,
    export_phase9_graph_skeleton,
    verify_phase9_graph_skeleton_release_manifest,
)


def main() -> None:
    root = Path(__file__).parents[1]
    with TemporaryDirectory(prefix="claim-polygraph-phase9-4-") as temporary:
        evaluation = evaluate_phase9_graph_skeleton(root, temporary)
    export_phase9_graph_skeleton(
        evaluation,
        root / "artifacts/evaluations/phase9-stage9.4-graph-skeleton-v1.json",
    )
    manifest = build_phase9_graph_skeleton_release_manifest(root)
    verification = verify_phase9_graph_skeleton_release_manifest(manifest, root)
    print(
        f"Evaluation: {evaluation.evaluation_id}\n"
        f"Operations completed: {evaluation.operation_count}\n"
        f"Authoritative checkpoints: {evaluation.checkpoint_count}\n"
        f"Report completed: {'yes' if evaluation.report_completed else 'no'}\n"
        f"Artifacts checked: {verification.checked_artifact_count}\n"
        f"Valid: {'yes' if verification.valid else 'no'}"
    )
    if (
        evaluation.operation_count != 18
        or evaluation.checkpoint_count != 18
        or not evaluation.report_completed
        or not verification.valid
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
