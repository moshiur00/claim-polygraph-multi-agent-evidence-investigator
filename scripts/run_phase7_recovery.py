"""Run the deterministic Stage 7.7 end-to-end recovery demonstration."""

import asyncio
from pathlib import Path

from claim_polygraph_ng.evaluation.phase7_recovery import (
    evaluate_phase7_recovery,
    export_phase7_recovery,
)

ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "artifacts/evaluations/phase7-stage7.7-recovery-v1.json"


def main() -> int:
    evaluation = asyncio.run(evaluate_phase7_recovery())
    export_phase7_recovery(evaluation, OUTPUT)
    for journey in evaluation.journeys:
        print(
            f"{journey.journey_id}: "
            f"{'passed' if journey.passed else 'failed'} "
            f"({journey.observed_outcome})"
        )
    print(f"Passed: {evaluation.passed_count}/{len(evaluation.journeys)}")
    print(f"Duplicate operations: {sum(item.duplicate_operations for item in evaluation.journeys)}")
    print("Provider usage: models=0, searches=0, network=0, PDFs=0, cost=$0.0000")
    print(f"Artifact: {OUTPUT.relative_to(ROOT).as_posix()}")
    return 0 if evaluation.all_paths_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
