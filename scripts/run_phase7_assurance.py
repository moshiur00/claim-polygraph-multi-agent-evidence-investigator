"""Run the frozen Stage 7.3 assurance and routing evaluation."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase7_assurance import (
    evaluate_phase7_assurance,
    export_phase7_assurance,
)

ROOT = Path(__file__).parents[1]
BENCHMARK = ROOT / "benchmarks/phase7_citation_routing_v1.json"
OUTPUT = ROOT / "artifacts/evaluations/phase7-stage7.3-assurance-routing-v1.json"


def main() -> int:
    result = evaluate_phase7_assurance(BENCHMARK)
    export_phase7_assurance(result, OUTPUT)
    print(f"Cases: {result.case_count}")
    print(f"Citation accuracy: {result.citation_accuracy:.2%}")
    print(f"Critical-route recall: {result.critical_route_recall:.2%}")
    print(f"Route accuracy: {result.route_accuracy:.2%}")
    print(
        "Unsupported marked supported: "
        f"{result.unsupported_marked_supported_count}"
    )
    print(f"Promotion gate passed: {result.promotion_gate_passed}")
    print(f"Artifact: {OUTPUT.relative_to(ROOT).as_posix()}")
    return 0 if result.promotion_gate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
