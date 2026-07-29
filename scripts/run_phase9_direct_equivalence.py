"""Run the zero-cost 20-case Stage 9.2 direct-composition evaluation."""

from pathlib import Path
from tempfile import TemporaryDirectory

from claim_polygraph_ng.evaluation.phase9_direct import (
    build_phase9_direct_release_manifest,
    evaluate_phase9_direct_composition,
    export_phase9_direct_evaluation,
    verify_phase9_direct_release_manifest,
)


def main() -> None:
    root = Path(__file__).parents[1]
    with TemporaryDirectory(prefix="claim-polygraph-phase9-2-") as temporary:
        evaluation = evaluate_phase9_direct_composition(
            project_root=root,
            database_path=Path(temporary) / "investigations.db",
        )
    export_phase9_direct_evaluation(
        evaluation,
        root / "artifacts/evaluations/phase9-stage9.2-direct-composition-v1.json",
    )
    manifest = build_phase9_direct_release_manifest(root)
    verification = verify_phase9_direct_release_manifest(manifest, root)
    print(
        f"Evaluation: {evaluation.evaluation_id}\n"
        f"Cases: {evaluation.case_count}\n"
        f"Completed: {evaluation.completed_count}\n"
        f"Structurally consistent: {'yes' if evaluation.structurally_consistent else 'no'}\n"
        f"Release artifacts checked: {verification.checked_artifact_count}\n"
        f"Release valid: {'yes' if verification.valid else 'no'}"
    )
    if (
        evaluation.completed_count != evaluation.case_count
        or not evaluation.structurally_consistent
        or not verification.valid
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
