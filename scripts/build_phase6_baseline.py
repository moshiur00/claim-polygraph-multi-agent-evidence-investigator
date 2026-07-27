"""Build the frozen Stage 6.0 baseline and manifest without external calls."""

import hashlib
import json
from pathlib import Path

from claim_polygraph_ng.evaluation.phase4_manifest import BaselineArtifact
from claim_polygraph_ng.evaluation.phase6_manifest import (
    Phase6BaselineAudit,
    Phase6CaseBaseline,
    Phase6ExperimentManifest,
    Phase6Thresholds,
)

ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "artifacts/evaluations"
BENCHMARK = ROOT / "benchmarks/initial_claims_v1.json"
PHASE2 = OUTPUT / "phase2-ten-live-e2e-v4-independent-declared-1.json"
PHASE3 = OUTPUT / "phase3-v5-final-validated-a.json"
BASELINE = OUTPUT / "phase6-stage6.0-baseline-v1.json"
MANIFEST = OUTPUT / "phase6-experiment-manifest-v1.json"

SUPPORTING_ARTIFACTS = {
    "benchmark": BENCHMARK,
    "phase2_baseline": PHASE2,
    "phase3_baseline": PHASE3,
    "phase3_gate_audit": OUTPUT / "phase3-v5-final-gate-audit.json",
    "phase4_closure_audit": OUTPUT / "phase4-final-gate-audit.json",
    "phase5_manifest": OUTPUT / "phase5-source-intelligence-manifest-v1.json",
}


def main() -> int:
    benchmark = _json(BENCHMARK)
    phase2 = _json(PHASE2)
    phase3 = _json(PHASE3)
    expected = {case["case_id"]: case["expected_verdict"] for case in benchmark["cases"]}
    rows = []
    for cohort, payload in (("phase2", phase2), ("phase3", phase3)):
        for result in payload["results"]:
            case_id = result["case_id"]
            observed = result["verdict_label"]
            matches = observed == expected[case_id]
            full_count = result.get("full_audit_count", result.get("parent_full_audit_count", 0))
            audit_count = result.get("audit_count", result.get("parent_audit_count", 0))
            rows.append(
                Phase6CaseBaseline(
                    case_id=case_id,
                    cohort=cohort,
                    expected_verdict=expected[case_id],
                    observed_verdict=observed,
                    verdict_matches=matches,
                    citation_fully_supported=audit_count > 0 and full_count == audit_count,
                    duration_seconds=result["duration_seconds"],
                    model_call_count=result["metered_model_call_count"],
                    estimated_model_cost_usd=result["estimated_model_cost_usd"],
                    failure_class=None if matches else "verdict_taxonomy_or_evidence_gap",
                )
            )
    rows.sort(key=lambda item: item.case_id)
    correct = sum(row.verdict_matches for row in rows)
    baseline = Phase6BaselineAudit(
        dataset_id=benchmark["dataset_id"],
        dataset_version=benchmark["version"],
        cases=tuple(rows),
        completed_case_count=len(rows),
        correct_verdict_count=correct,
        verdict_accuracy=correct / len(rows),
        citation_full_rate=sum(row.citation_fully_supported for row in rows) / len(rows),
        duration_seconds=sum(row.duration_seconds for row in rows),
        model_call_count=sum(row.model_call_count for row in rows),
        estimated_model_cost_usd=sum(row.estimated_model_cost_usd for row in rows),
        measured_gaps=(
            "CPNG-006 baseline label is unsupported; reviewed label is supported.",
            "CPNG-019 baseline label is misleading; reviewed label is contradicted.",
            "Stored aggregate runs do not expose assertion-level numerical verification metrics.",
            "Stored aggregate runs do not expose assertion-level temporal verification metrics.",
            "No typed claim-to-evidence argument ledger exists in the baseline.",
            "Verdict confidence remains intentionally uncalibrated.",
        ),
        limitations=(
            "The baseline combines the authoritative Phase 2 CPNG-001-010 run and "
            "Phase 3 CPNG-011-020 run.",
            "Durations and costs came from different declared runs and are summed only "
            "as a reference, not as a concurrency-normalized performance measure.",
            "No search, page fetch, PDF download, or model call was made to build this audit.",
        ),
    )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text(baseline.model_dump_json(indent=2) + "\n", encoding="utf-8")

    artifacts = [
        _artifact(artifact_id, path)
        for artifact_id, path in SUPPORTING_ARTIFACTS.items()
    ]
    artifacts.append(_artifact("baseline_audit", BASELINE))
    manifest = Phase6ExperimentManifest(
        dataset_id=benchmark["dataset_id"],
        dataset_version=benchmark["version"],
        benchmark_case_ids=tuple(case["case_id"] for case in benchmark["cases"]),
        artifacts=tuple(artifacts),
        baseline_audit_id=baseline.audit_id,
        thresholds=Phase6Thresholds(
            maximum_verdict_regressions=0,
            minimum_required_check_trigger_recall=1,
            maximum_false_passed_incomplete_checks=0,
            minimum_numerical_operation_accuracy=0.95,
            minimum_temporal_relation_accuracy=0.95,
            maximum_out_of_packet_argument_references=0,
            maximum_unsupported_resolved_propositions=0,
            maximum_post_enforcement_constraint_violations=0,
            minimum_required_review_escalation_recall=1,
            minimum_citation_full_rate=0.95,
            maximum_added_deterministic_latency_ratio=0.20,
            maximum_added_deterministic_model_cost_usd=0,
            maximum_optional_model_cost_per_case_usd=0.005,
        ),
    )
    MANIFEST.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"Baseline: {BASELINE.relative_to(ROOT)}")
    print(f"Manifest: {MANIFEST.relative_to(ROOT)}")
    print(f"Cases: {len(rows)}")
    print(f"Verdict accuracy: {baseline.verdict_accuracy:.2%}")
    print(f"Citation full rate: {baseline.citation_full_rate:.2%}")
    return 0


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact(artifact_id: str, path: Path) -> BaselineArtifact:
    return BaselineArtifact(
        artifact_id=artifact_id,
        path=path.relative_to(ROOT).as_posix(),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )


if __name__ == "__main__":
    raise SystemExit(main())
