"""Freeze V3.6 configuration before calibration execution."""

import hashlib
import json
from pathlib import Path

from claim_polygraph_ng.analysis.assisted_verification_construction import (
    ASSISTED_CONSTRUCTION_PROMPT_VERSION,
    AssistedNumericalProviderProposal,
    AssistedTemporalProviderProposal,
)
from claim_polygraph_ng.analysis.bounded_assisted_construction import (
    AssistedConstructionBudget,
)
from claim_polygraph_ng.domain import ModelTask
from claim_polygraph_ng.evaluation.v3_calibration import select_v3_calibration_cases
from claim_polygraph_ng.providers.ollama import _TASK_INSTRUCTIONS


def _canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> None:
    root = Path(__file__).parents[1]
    dataset = root / "benchmarks/verification_construction_v3_approved_frozen_v2.json"
    _, selection = select_v3_calibration_cases(dataset)
    instruction = _TASK_INSTRUCTIONS[ModelTask.ASSIST_VERIFICATION_CONSTRUCTION]
    if ASSISTED_CONSTRUCTION_PROMPT_VERSION not in instruction:
        raise ValueError("prompt implementation differs from declared version")
    budget = AssistedConstructionBudget()
    files = (
        Path("src/claim_polygraph_ng/analysis/assisted_verification_construction.py"),
        Path("src/claim_polygraph_ng/analysis/bounded_assisted_construction.py"),
        Path("src/claim_polygraph_ng/providers/idempotent.py"),
        Path("src/claim_polygraph_ng/providers/ollama.py"),
        Path("src/claim_polygraph_ng/providers/openai.py"),
        Path("src/claim_polygraph_ng/evaluation/v3_calibration.py"),
        Path("benchmarks/verification_construction_v3_approved_frozen_v2.json"),
    )
    manifest = {
        "manifest_id": "verification-construction-v3-stage6-calibration-freeze-v1",
        "status": "frozen",
        "frozen_before_calibration_execution": True,
        "prompt_version": ASSISTED_CONSTRUCTION_PROMPT_VERSION,
        "prompt_sha256": hashlib.sha256(instruction.encode("utf-8")).hexdigest(),
        "schemas": {
            "numerical_sha256": _canonical_hash(
                AssistedNumericalProviderProposal.model_json_schema()
            ),
            "temporal_sha256": _canonical_hash(
                AssistedTemporalProviderProposal.model_json_schema()
            ),
        },
        "provider": {
            "name": "openai",
            "model": "gpt-5.6-luna",
            "endpoint": "responses",
            "reasoning_effort": "low",
            "store": False,
        },
        "budget": {
            "maximum_calls_per_case": budget.maximum_calls_per_case,
            "maximum_total_calls": budget.maximum_total_calls,
            "maximum_input_tokens": budget.maximum_input_tokens,
            "maximum_output_tokens": budget.maximum_output_tokens,
            "maximum_total_cost_usd": budget.maximum_total_cost_usd,
            "search_calls": 0,
            "retries": 0,
        },
        "promotion_thresholds": {
            "minimum_evidence_span_validity": 1.0,
            "maximum_unsafe_accepted_constructions": 0,
            "minimum_construction_precision": 0.98,
            "minimum_fallback_recall_gain": 0.15,
            "minimum_overall_construction_recall": 0.75,
            "minimum_human_review_routing_recall": 1.0,
            "maximum_publication_safety_regressions": 0,
            "maximum_duplicate_paid_operations": 0,
            "maximum_cost_per_recovered_assertion_usd": 0.05,
        },
        "dataset_sha256": selection.dataset_sha256,
        "calibration_case_count": selection.case_count,
        "calibration_case_ids": list(selection.case_ids),
        "development_cases_exposed_during_freeze": 0,
        "held_out_cases_exposed_during_freeze": 0,
        "execution_at_freeze": {
            "calibration_model_calls": 0,
            "calibration_network_calls": 0,
            "calibration_paid_operations": 0,
        },
        "artifacts": [
            {
                "path": path.as_posix(),
                "sha256": hashlib.sha256((root / path).read_bytes()).hexdigest(),
            }
            for path in files
        ],
    }
    destination = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage6-calibration-freeze-v1.json"
    )
    destination.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print("status=frozen calibration=20 model_calls=0 held_out=0")


if __name__ == "__main__":
    main()
