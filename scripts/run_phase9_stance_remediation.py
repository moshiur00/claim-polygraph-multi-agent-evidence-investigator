"""Validate and hash the scoped Stage 9.12a stance remediation."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

root = Path(__file__).resolve().parents[1]
comparison_path = (
    root / "artifacts/evaluations/phase9-stage9.12-frozen-comparison-v1.json"
)
comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
unified = comparison["unified"]
without_challenger = comparison["minus_challenger"]

checks = {
    "twenty_frozen_cases_replayed": comparison["case_count"] == 20,
    "verdict_equivalence_is_100_percent": (
        unified["direct_verdict_equivalence"] == 1
    ),
    "challenger_material_gain_preserved": (
        comparison["challenger_material_gain_cases"] > 0
    ),
    "challenger_evidence_coverage_gain_preserved": (
        unified["mean_evidence_coverage_ratio"]
        > without_challenger["mean_evidence_coverage_ratio"]
    ),
    "challenger_family_coverage_gain_preserved": (
        unified["mean_family_coverage_ratio"]
        > without_challenger["mean_family_coverage_ratio"]
    ),
    "challenger_stance_coverage_gain_preserved": (
        unified["challenge_coverage_rate"]
        > without_challenger["challenge_coverage_rate"]
    ),
    "no_duplicate_paid_operations": unified["duplicate_paid_operations"] == 0,
}
result = {
    "evaluation_id": "phase9-stage9.12a-stance-remediation-v1",
    "generated_at": datetime.now(UTC).isoformat(),
    "source_evaluation": comparison["evaluation_id"],
    "case_count": comparison["case_count"],
    "checks": checks,
    "valid": all(checks.values()),
    "metrics": {
        "unified_direct_verdict_equivalence": unified[
            "direct_verdict_equivalence"
        ],
        "unified_mean_evidence_coverage_ratio": unified[
            "mean_evidence_coverage_ratio"
        ],
        "without_challenger_mean_evidence_coverage_ratio": without_challenger[
            "mean_evidence_coverage_ratio"
        ],
        "unified_mean_family_coverage_ratio": unified[
            "mean_family_coverage_ratio"
        ],
        "without_challenger_mean_family_coverage_ratio": without_challenger[
            "mean_family_coverage_ratio"
        ],
        "unified_challenge_coverage_rate": unified["challenge_coverage_rate"],
        "without_challenger_challenge_coverage_rate": without_challenger[
            "challenge_coverage_rate"
        ],
        "challenger_material_gain_cases": comparison[
            "challenger_material_gain_cases"
        ],
    },
    "remaining_non_stance_gate_failures": comparison["failed_gates"],
    "external_model_calls": comparison["external_model_calls"],
    "live_search_calls": comparison["live_search_calls"],
    "network_fetches": comparison["network_fetches"],
    "pdf_downloads": comparison["pdf_downloads"],
}
result_path = (
    root / "artifacts/evaluations/phase9-stage9.12a-stance-remediation-v1.json"
)
result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

artifact_paths = (
    "src/claim_polygraph_ng/analysis/stance.py",
    "src/claim_polygraph_ng/providers/mock.py",
    "src/claim_polygraph_ng/evaluation/phase9_comparison.py",
    "tests/unit/test_evidence_stance_contract.py",
    "tests/integration/test_phase9_comparison.py",
    "docs/PHASE_9_STAGE_9.12A_COMPLETION_REPORT.md",
    "artifacts/evaluations/phase9-stage9.12-frozen-comparison-v1.json",
    "artifacts/evaluations/phase9-stage9.12a-stance-remediation-v1.json",
)
manifest = {
    "manifest_id": "phase9-stage9.12a-release-manifest-v1",
    "generated_at": datetime.now(UTC).isoformat(),
    "artifacts": [
        {
            "path": path,
            "sha256": hashlib.sha256((root / path).read_bytes()).hexdigest(),
        }
        for path in artifact_paths
    ],
}
manifest_path = (
    root / "artifacts/evaluations/phase9-stage9.12a-release-manifest-v1.json"
)
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

print(f"Evaluation: {result['evaluation_id']}")
print(f"Cases: {result['case_count']}")
print(
    "Direct equivalence: "
    f"{result['metrics']['unified_direct_verdict_equivalence']:.1%}"
)
print(
    "Challenger gain cases: "
    f"{result['metrics']['challenger_material_gain_cases']}"
)
print(f"Scoped remediation valid: {'yes' if result['valid'] else 'no'}")
print(
    "Remaining broader gates: "
    + (", ".join(result["remaining_non_stance_gate_failures"]) or "none")
)
raise SystemExit(0 if result["valid"] else 1)
