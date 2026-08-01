"""Freeze the approved V4.9c calibration boundary before its one allowed run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from claim_polygraph_ng.analysis.assisted_verification_construction import (
    ASSISTED_CONSTRUCTION_PROMPT_VERSION,
    AssistedNumericalProviderProposal,
    AssistedScalarProviderProposal,
    AssistedTemporalProviderProposal,
)
from claim_polygraph_ng.domain import ModelTask
from claim_polygraph_ng.evaluation.v3_annotation import (
    V3ReviewDecision,
    load_replacement_calibration_workbook,
)
from claim_polygraph_ng.providers.ollama import _TASK_INSTRUCTIONS

ROOT = Path(__file__).parents[1]
EVALUATIONS = ROOT / "artifacts/evaluations"
WORKBOOK = (
    ROOT
    / "benchmarks/verification_construction_v4_stage9b_fresh_calibration_workbook_v1_APPROVED.json"
)
DESTINATION = (
    EVALUATIONS / "verification-construction-v4-stage9c-replacement-calibration-freeze-v1.json"
)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _schema_hash(model: type) -> str:
    encoded = json.dumps(model.model_json_schema(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def main() -> None:
    if DESTINATION.exists():
        raise FileExistsError("V4.9c calibration boundary is already frozen")
    workbook = load_replacement_calibration_workbook(WORKBOOK)
    if any(
        case.annotation is None
        or case.approval is None
        or case.approval.decision is not V3ReviewDecision.APPROVE
        for case in workbook.cases
    ):
        raise ValueError("V4.9c requires complete human annotation and distinct approval")
    review_gate = EVALUATIONS / "verification-construction-v4-stage9b-review-gate-v1.json"
    review = json.loads(review_gate.read_text(encoding="utf-8"))
    if not review["review_gate_passed"] or review["approved_workbook_sha256"] != _hash(WORKBOOK):
        raise ValueError("approved workbook differs from the passed V4.9b review gate")
    instruction = _TASK_INSTRUCTIONS[ModelTask.ASSIST_VERIFICATION_CONSTRUCTION]
    if ASSISTED_CONSTRUCTION_PROMPT_VERSION not in instruction:
        raise ValueError("implemented prompt differs from its declared version")

    frozen_files = (
        WORKBOOK,
        review_gate,
        EVALUATIONS / "verification-construction-v4-stage0-manifest-v1.json",
        EVALUATIONS / "verification-construction-v4-stage7b-remediation-audit-v1.json",
        EVALUATIONS / "verification-construction-v4-stage9a-remediation-audit-v1.json",
        ROOT / "src/claim_polygraph_ng/analysis/candidate_extraction.py",
        ROOT / "src/claim_polygraph_ng/analysis/compound_construction.py",
        ROOT / "src/claim_polygraph_ng/analysis/construction_eligibility.py",
        ROOT / "src/claim_polygraph_ng/analysis/assisted_verification_construction.py",
        ROOT / "src/claim_polygraph_ng/analysis/bounded_assisted_construction.py",
        ROOT / "src/claim_polygraph_ng/domain/verification.py",
        ROOT / "src/claim_polygraph_ng/providers/idempotent.py",
        ROOT / "src/claim_polygraph_ng/providers/openai.py",
        ROOT / "src/claim_polygraph_ng/persistence/paid_operations.py",
    )
    manifest = {
        "manifest_id": "verification-construction-v4-stage9c-replacement-calibration-freeze-v1",
        "status": "frozen",
        "execution_limit": 1,
        "dataset_split": "fresh_calibration",
        "workbook_sha256": _hash(WORKBOOK),
        "case_count": len(workbook.cases),
        "case_ids": [case.case_id for case in workbook.cases],
        "origin_family_count": len({case.origin_family_id for case in workbook.cases}),
        "prompt_version": ASSISTED_CONSTRUCTION_PROMPT_VERSION,
        "prompt_sha256": hashlib.sha256(instruction.encode()).hexdigest(),
        "schema_hashes": {
            "comparison": _schema_hash(AssistedNumericalProviderProposal),
            "scalar": _schema_hash(AssistedScalarProviderProposal),
            "temporal": _schema_hash(AssistedTemporalProviderProposal),
        },
        "provider": {
            "name": "openai",
            "model": "gpt-4o-mini",
            "reasoning_effort": None,
            "store": False,
            "timeout_seconds": 60,
        },
        "budget": {
            "maximum_calibration_calls": 20,
            "maximum_input_tokens_per_call": 6000,
            "maximum_output_tokens_per_call": 900,
            "maximum_calibration_cost_usd": 0.75,
            "automatic_retries_after_valid_receipt": 0,
            "search_calls": 0,
        },
        "promotion_thresholds": {
            "minimum_schema_validity": 1.0,
            "minimum_exact_span_validity": 1.0,
            "maximum_unsafe_accepted_constructions": 0,
            "minimum_construction_precision": 0.98,
            "minimum_overall_construction_recall": 0.75,
            "minimum_incremental_recall_gain_when_baseline_below_target": 0.15,
            "minimum_human_review_routing_recall": 1.0,
            "maximum_publication_safety_regressions": 0,
            "maximum_duplicate_paid_operations": 0,
            "maximum_cost_per_recovered_assertion_usd": 0.05,
        },
        "decision_rules": {
            "assisted_value_gate": "baseline_at_recall_target_or_incremental_gain_at_threshold",
            "zero_spend_cost_gate": "pass_when_no_paid_call_and_no_recovered_assertion",
            "failed_or_invalid_provider_output": "human_review",
        },
        "calibration_executions_before_freeze": 0,
        "held_out_cases_loaded": 0,
        "artifacts": [
            {"path": path.relative_to(ROOT).as_posix(), "sha256": _hash(path)}
            for path in frozen_files
        ],
    }
    DESTINATION.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(DESTINATION.relative_to(ROOT))
    print("status=frozen cases=20 execution_limit=1 model_calls=0")


if __name__ == "__main__":
    main()
