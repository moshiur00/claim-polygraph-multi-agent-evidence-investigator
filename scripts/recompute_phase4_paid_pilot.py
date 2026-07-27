"""Recompute parent pilot labels after deterministic aggregation changes."""

from pathlib import Path
from uuid import uuid4

from claim_polygraph_ng.analysis import aggregate_component_label
from claim_polygraph_ng.domain import Verdict, VerdictLabel
from claim_polygraph_ng.evaluation import (
    Phase4PaidPilotSummary,
    export_phase4_pilot_artifact,
    load_phase4_manifest,
)

ROOT = Path(__file__).parents[1]
INPUT = ROOT / "artifacts/evaluations/phase4-paid-pilot.json"
OUTPUT = ROOT / "artifacts/evaluations/phase4-paid-pilot-final.json"


def _verdict(label: VerdictLabel) -> Verdict:
    return Verdict(
        claim_id=uuid4(),
        label=label,
        concise_explanation="Stored component result used for deterministic recomputation.",
        detailed_reasoning="No model or retrieval operation is repeated during recomputation.",
        decisive_evidence_ids=(uuid4(),),
    )


def main() -> int:
    summary = Phase4PaidPilotSummary.model_validate_json(INPUT.read_text(encoding="utf-8"))
    manifest = load_phase4_manifest(
        ROOT / "artifacts/evaluations/phase4-experiment-manifest-v1.json"
    )
    results = []
    for result in summary.results:
        if not result.completed:
            results.append(result)
            continue
        label = aggregate_component_label(
            tuple(_verdict(item.verdict_label) for item in result.component_results)
        )
        results.append(
            result.model_copy(
                update={
                    "verdict_label": label,
                    "verdict_matches": label is result.expected_verdict,
                }
            )
        )
    completed = tuple(item for item in results if item.completed)
    improved = sum(
        item.verdict_matches is True and item.phase3_verdict_matches is False for item in completed
    )
    regressed = sum(
        item.verdict_matches is False and item.phase3_verdict_matches is True for item in completed
    )
    accuracy = (
        sum(item.verdict_matches is True for item in completed) / len(completed)
        if completed
        else None
    )
    gate = (
        len(completed) == summary.case_count
        and improved >= manifest.pilot_gate.minimum_improved_cases
        and regressed <= manifest.pilot_gate.verdict_regressions_allowed
        and summary.citation_full_rate is not None
        and summary.citation_full_rate >= 0.95
        and summary.estimated_cost_usd <= summary.maximum_cost_usd
        and summary.median_latency_seconds <= summary.maximum_median_latency_seconds
    )
    final = summary.model_copy(
        update={
            "verdict_accuracy": accuracy,
            "improved_case_count": improved,
            "regressed_case_count": regressed,
            "pilot_gate_passed": gate,
            "results": tuple(results),
            "limitations": (
                *summary.limitations,
                "Parent labels were deterministically recomputed after correcting the generic "
                "misleading-plus-contradicted aggregation rule; no provider call was repeated.",
            ),
        }
    )
    export_phase4_pilot_artifact(final, OUTPUT)
    print(f"Final accuracy: {final.verdict_accuracy}")
    print(f"Improved/regressed: {final.improved_case_count}/{final.regressed_case_count}")
    print(f"Pilot gate passed: {final.pilot_gate_passed}")
    print(f"Artifact: {OUTPUT}")
    return 0 if final.pilot_gate_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
