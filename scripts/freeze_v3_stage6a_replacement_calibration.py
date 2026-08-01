"""Freeze the approved V3.6a replacement calibration before its one allowed run."""

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
from claim_polygraph_ng.evaluation.v3_annotation import (
    V3ReviewDecision,
    load_replacement_calibration_workbook,
)
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
    workbook_path = (
        root
        / "benchmarks/"
        "verification_construction_v3_stage6a_replacement_calibration_workbook_v1_APPROVED.json"
    )
    workbook = load_replacement_calibration_workbook(workbook_path)
    if any(
        case.annotation is None
        or case.approval is None
        or case.approval.decision is not V3ReviewDecision.APPROVE
        for case in workbook.cases
    ):
        raise ValueError("replacement calibration lacks complete distinct approval")
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
        workbook_path.relative_to(root),
    )
    budget = AssistedConstructionBudget()
    manifest = {
        "manifest_id": (
            "verification-construction-v3-stage6a-replacement-calibration-freeze-v1"
        ),
        "status": "frozen",
        "execution_limit": 1,
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
            "search_calls": 0,
            "automatic_retries": 0,
        },
        "promotion_thresholds": {
            "minimum_evidence_span_validity": 1.0,
            "maximum_unsafe_accepted_constructions": 0,
            "minimum_construction_precision": 0.98,
            "minimum_incremental_recall_gain": 0.15,
            "minimum_overall_construction_recall": 0.75,
            "minimum_human_review_routing_recall": 1.0,
            "maximum_publication_safety_regressions": 0,
            "maximum_duplicate_paid_operations": 0,
            "maximum_cost_per_recovered_assertion_usd": 0.05,
        },
        "replacement_workbook_sha256": _hash(workbook_path),
        "case_count": len(workbook.cases),
        "case_ids": [case.case_id for case in workbook.cases],
        "origin_family_count": len(
            {case.origin_family_id for case in workbook.cases}
        ),
        "annotators": sorted(
            {
                case.annotation.annotator_identity
                for case in workbook.cases
                if case.annotation
            }
        ),
        "distinct_approvers": sorted(
            {
                case.approval.approver_identity
                for case in workbook.cases
                if case.approval
            }
        ),
        "original_calibration_known": True,
        "original_held_out_sealed": True,
        "held_out_cases_loaded": 0,
        "artifacts": [
            {"path": path.as_posix(), "sha256": _hash(root / path)}
            for path in files
        ],
    }
    destination = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage6a-replacement-calibration-freeze-v1.json"
    )
    if destination.exists():
        raise FileExistsError("V3.6a replacement freeze already exists")
    destination.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print("status=frozen cases=20 held_out=0 model_calls=0")


if __name__ == "__main__":
    main()
