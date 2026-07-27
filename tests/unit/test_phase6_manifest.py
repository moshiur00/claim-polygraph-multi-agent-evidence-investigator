"""Tests for the offline Phase 6 experiment lock."""

import hashlib
import json

from claim_polygraph_ng.evaluation.phase4_manifest import BaselineArtifact
from claim_polygraph_ng.evaluation.phase6_manifest import (
    Phase6BaselineAudit,
    Phase6CaseBaseline,
    Phase6ExperimentManifest,
    Phase6Thresholds,
    verify_phase6_manifest,
)


def _thresholds() -> Phase6Thresholds:
    return Phase6Thresholds(
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
        maximum_added_deterministic_latency_ratio=0.2,
        maximum_added_deterministic_model_cost_usd=0,
        maximum_optional_model_cost_per_case_usd=0.005,
    )


def test_manifest_verifies_reviewed_twenty_case_baseline(tmp_path) -> None:
    cases = [
        {
            "case_id": f"CPNG-{index:03d}",
            "annotation_status": "reviewed",
            "annotated_by": "Annotator",
            "approved_by": "Approver",
        }
        for index in range(1, 21)
    ]
    benchmark = tmp_path / "benchmark.json"
    benchmark.write_text(
        json.dumps({"dataset_id": "fixture", "version": 1, "cases": cases}),
        encoding="utf-8",
    )
    rows = tuple(
        Phase6CaseBaseline(
            case_id=item["case_id"],
            cohort="phase2" if index < 10 else "phase3",
            expected_verdict="supported",
            observed_verdict="supported",
            verdict_matches=True,
            citation_fully_supported=True,
            duration_seconds=1,
            model_call_count=1,
            estimated_model_cost_usd=0,
        )
        for index, item in enumerate(cases)
    )
    baseline = Phase6BaselineAudit(
        dataset_id="fixture",
        dataset_version=1,
        cases=rows,
        completed_case_count=20,
        correct_verdict_count=20,
        verdict_accuracy=1,
        citation_full_rate=1,
        duration_seconds=20,
        model_call_count=20,
        estimated_model_cost_usd=0,
        measured_gaps=("No assertion ledger.",),
        limitations=("Synthetic test.",),
    )
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(baseline.model_dump_json(), encoding="utf-8")
    extras = []
    for index in range(4):
        path = tmp_path / f"extra-{index}.json"
        path.write_text("{}", encoding="utf-8")
        extras.append(_artifact(f"extra_{index}", path, tmp_path))
    manifest = Phase6ExperimentManifest(
        dataset_id="fixture",
        dataset_version=1,
        benchmark_case_ids=tuple(item["case_id"] for item in cases),
        artifacts=(
            _artifact("benchmark", benchmark, tmp_path),
            _artifact("phase2_baseline", extras_path := tmp_path / "extra-0.json", tmp_path),
            _artifact("phase3_baseline", tmp_path / "extra-1.json", tmp_path),
            _artifact("baseline_audit", baseline_path, tmp_path),
            *extras[2:],
        ),
        baseline_audit_id=baseline.audit_id,
        thresholds=_thresholds(),
    )

    result = verify_phase6_manifest(manifest, tmp_path)

    assert extras_path.is_file()
    assert result.valid
    assert result.benchmark_reviewed
    assert result.checked_artifact_count == 6


def test_manifest_rejects_changed_artifact(tmp_path) -> None:
    path = tmp_path / "artifact.json"
    path.write_text("original", encoding="utf-8")
    artifact = BaselineArtifact(
        artifact_id="benchmark",
        path="artifact.json",
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )
    path.write_text("changed", encoding="utf-8")

    assert hashlib.sha256(path.read_bytes()).hexdigest() != artifact.sha256


def _artifact(artifact_id, path, root) -> BaselineArtifact:
    return BaselineArtifact(
        artifact_id=artifact_id,
        path=path.relative_to(root).as_posix(),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )
