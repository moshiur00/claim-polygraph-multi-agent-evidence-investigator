"""Freeze the unchanged V3.6e configuration for one held-out execution."""

import hashlib
import json
from pathlib import Path

from claim_polygraph_ng.analysis.assisted_verification_construction import (
    ASSISTED_CONSTRUCTION_PROMPT_VERSION,
    AssistedNumericalProviderProposal,
    AssistedScalarProviderProposal,
    AssistedTemporalProviderProposal,
)
from claim_polygraph_ng.analysis.bounded_assisted_construction import (
    AssistedConstructionBudget,
)
from claim_polygraph_ng.domain import ModelTask
from claim_polygraph_ng.evaluation.v3_annotation import V3AnnotationCase
from claim_polygraph_ng.evaluation.v3_manifest import V3DatasetSplit
from claim_polygraph_ng.providers.ollama import _TASK_INSTRUCTIONS


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _schema_hash(model: type) -> str:
    payload = json.dumps(
        model.model_json_schema(), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def main() -> None:
    root = Path(__file__).parents[1]
    calibration_audit_path = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage6e-fresh-calibration-audit-v1.json"
    )
    calibration_audit = json.loads(
        calibration_audit_path.read_text(encoding="utf-8")
    )
    if not calibration_audit["eligible_for_original_held_out"]:
        raise ValueError("V3.6e did not authorize opening the original held-out split")

    dataset_path = (
        root / "benchmarks/verification_construction_v3_approved_frozen_v2.json"
    )
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    cases = tuple(
        V3AnnotationCase.model_validate(case)
        for case in payload["cases"]
        if case["split"] == V3DatasetSplit.HELD_OUT
    )
    if len(cases) != 20:
        raise ValueError("V3.7 requires exactly 20 held-out cases")
    if any(case.annotation is None or case.approval is None for case in cases):
        raise ValueError("held-out cases require completed annotation and approval")

    instruction = _TASK_INSTRUCTIONS[ModelTask.ASSIST_VERIFICATION_CONSTRUCTION]
    if ASSISTED_CONSTRUCTION_PROMPT_VERSION not in instruction:
        raise ValueError("implemented prompt differs from declared prompt version")
    files = (
        Path("src/claim_polygraph_ng/domain/verification.py"),
        Path("src/claim_polygraph_ng/analysis/assisted_verification_construction.py"),
        Path("src/claim_polygraph_ng/analysis/bounded_assisted_construction.py"),
        Path("src/claim_polygraph_ng/providers/idempotent.py"),
        Path("src/claim_polygraph_ng/providers/openai.py"),
        Path("src/claim_polygraph_ng/providers/ollama.py"),
        dataset_path.relative_to(root),
        calibration_audit_path.relative_to(root),
    )
    budget = AssistedConstructionBudget()
    thresholds = {
        "minimum_evidence_span_validity": 1.0,
        "maximum_unsafe_accepted_constructions": 0,
        "minimum_construction_precision": 0.98,
        "minimum_incremental_recall_gain": 0.15,
        "minimum_overall_construction_recall": 0.75,
        "minimum_human_review_routing_recall": 1.0,
        "maximum_publication_safety_regressions": 0,
        "maximum_duplicate_paid_operations": 0,
        "maximum_cost_per_recovered_assertion_usd": 0.05,
    }
    manifest = {
        "manifest_id": "verification-construction-v3-stage7-held-out-freeze-v1",
        "status": "frozen",
        "execution_limit": 1,
        "configuration_source": (
            "verification-construction-v3-stage6e-fresh-calibration-freeze-v1"
        ),
        "configuration_changed_after_calibration": False,
        "prompt_version": ASSISTED_CONSTRUCTION_PROMPT_VERSION,
        "prompt_sha256": hashlib.sha256(instruction.encode()).hexdigest(),
        "schemas": {
            "comparison_sha256": _schema_hash(AssistedNumericalProviderProposal),
            "scalar_sha256": _schema_hash(AssistedScalarProviderProposal),
            "temporal_sha256": _schema_hash(AssistedTemporalProviderProposal),
        },
        "provider": {
            "name": "openai",
            "model": "gpt-5.6-luna",
            "reasoning_effort": "low",
            "store": False,
        },
        "budget": {
            **budget.model_dump(mode="json"),
            "maximum_calls": 20,
            "maximum_total_cost_usd": 0.75,
            "search_calls": 0,
            "automatic_retries": 0,
        },
        "promotion_thresholds": thresholds,
        "dataset_sha256": _hash(dataset_path),
        "case_count": len(cases),
        "case_ids": [case.case_id for case in cases],
        "positive_gold_cases": sum(
            case.annotation.gold_label.value
            in {"deterministic_constructible", "fallback_eligible"}
            for case in cases
            if case.annotation
        ),
        "held_out_opened_after_passing_calibration": True,
        "held_out_provider_calls_before_execution": 0,
        "artifacts": [
            {"path": path.as_posix(), "sha256": _hash(root / path)}
            for path in files
        ],
    }
    destination = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage7-held-out-freeze-v1.json"
    )
    if destination.exists():
        raise FileExistsError("V3.7 held-out freeze already exists")
    destination.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print("status=frozen cases=20 executions=0 provider_calls=0")


if __name__ == "__main__":
    main()
