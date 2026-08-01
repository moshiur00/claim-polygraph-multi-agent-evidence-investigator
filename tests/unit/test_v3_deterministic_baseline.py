"""Stage V3.3 deterministic baseline tests."""

import hashlib
import json
from pathlib import Path

from claim_polygraph_ng.evaluation.v3_deterministic_baseline import (
    run_v3_deterministic_baseline,
)


def test_v3_baseline_is_offline_fail_closed_and_reproducible() -> None:
    root = Path(__file__).parents[2]
    result = run_v3_deterministic_baseline(
        root / "benchmarks/verification_construction_v3_approved_frozen_v2.json",
        project_root=root,
    )

    assert result.case_count == 60
    assert result.constructible_gold_count == 49
    assert result.constructions_succeeded == 0
    assert result.construction_recall == 0
    assert result.construction_precision is None
    assert result.exact_evidence_span_validity is None
    assert result.unsafe_accepted_constructions == 0
    assert result.human_review_routing_recall == 1
    assert result.publication_safety_regressions == 0
    assert result.controls == {
        "model_calls": 0,
        "network_calls": 0,
        "search_calls": 0,
        "paid_operations": 0,
        "benchmark_labels_used_as_constructor_inputs": 0,
    }


def test_persisted_v3_baseline_audit_hashes_match() -> None:
    root = Path(__file__).parents[2]
    audit = json.loads(
        (
            root
            / "artifacts/evaluations/"
            "verification-construction-v3-stage3-baseline-audit-v1.json"
        ).read_text(encoding="utf-8")
    )
    baseline = root / audit["baseline_path"]
    dataset = root / audit["dataset_path"]

    assert audit["status"] == "passed"
    assert hashlib.sha256(baseline.read_bytes()).hexdigest() == audit[
        "baseline_sha256"
    ]
    assert hashlib.sha256(dataset.read_bytes()).hexdigest() == audit["dataset_sha256"]
