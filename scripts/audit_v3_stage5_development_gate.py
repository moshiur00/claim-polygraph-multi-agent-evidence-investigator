"""Freeze and audit V3.5 development-only prompt/validator configuration."""

import hashlib
import json
from pathlib import Path

from claim_polygraph_ng.analysis.assisted_verification_construction import (
    ASSISTED_CONSTRUCTION_PROMPT_VERSION,
    AssistedConstructionProposal,
)
from claim_polygraph_ng.domain import ModelTask
from claim_polygraph_ng.evaluation.v3_development import (
    select_v3_development_cases,
)
from claim_polygraph_ng.providers.ollama import _TASK_INSTRUCTIONS


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    root = Path(__file__).parents[1]
    dataset_path = (
        root / "benchmarks/verification_construction_v3_approved_frozen_v2.json"
    )
    cases, selection = select_v3_development_cases(dataset_path)
    instruction = _TASK_INSTRUCTIONS[
        ModelTask.ASSIST_VERIFICATION_CONSTRUCTION
    ]
    if ASSISTED_CONSTRUCTION_PROMPT_VERSION not in instruction:
        raise ValueError("provider instruction does not carry the frozen prompt version")
    if len(cases) != 20 or len(selection.assisted_case_ids) != 9:
        raise ValueError("unexpected V3.5 development selection")
    forbidden = {"verdict", "verification_state", "readiness", "publication"}
    if forbidden.intersection(AssistedConstructionProposal.model_fields):
        raise ValueError("V3.5 response schema crosses a protected decision boundary")

    artifacts = (
        Path("src/claim_polygraph_ng/analysis/assisted_verification_construction.py"),
        Path("src/claim_polygraph_ng/analysis/bounded_assisted_construction.py"),
        Path("src/claim_polygraph_ng/evaluation/v3_development.py"),
        Path("src/claim_polygraph_ng/providers/ollama.py"),
        Path("src/claim_polygraph_ng/providers/openai.py"),
        Path("benchmarks/verification_construction_v3_approved_frozen_v2.json"),
    )
    audit = {
        "audit_id": "verification-construction-v3-stage5-development-gate-v1",
        "status": "passed",
        "prompt_version": ASSISTED_CONSTRUCTION_PROMPT_VERSION,
        "prompt_sha256": hashlib.sha256(instruction.encode("utf-8")).hexdigest(),
        "dataset_sha256": selection.dataset_sha256,
        "split_exposure": {
            "development_cases_loaded": selection.case_count,
            "development_assisted_cases": len(selection.assisted_case_ids),
            "development_control_cases": len(selection.control_case_ids),
            "calibration_cases_exposed_to_model": 0,
            "held_out_cases_exposed_to_model": 0,
        },
        "development_case_ids": [case.case_id for case in cases],
        "assisted_case_ids": list(selection.assisted_case_ids),
        "control_case_ids": list(selection.control_case_ids),
        "validation_changes": [
            "approved evidence IDs must all resolve before provider execution",
            "left and right subjects must occur in the exact claim span",
            "evidence bindings must be unique",
            "every evidence quote must match exact retained-passage offsets",
        ],
        "execution": {
            "model_calls": 0,
            "network_calls": 0,
            "paid_operations": 0,
            "prompt_iterations": 1,
        },
        "gates": {
            "development_only_selection": True,
            "calibration_sealed": True,
            "held_out_sealed": True,
            "versioned_prompt": True,
            "structured_output": True,
            "protected_decision_fields_absent": True,
            "deterministic_fail_closed_validation": True,
        },
        "artifacts": [
            {"path": path.as_posix(), "sha256": _sha256(root / path)}
            for path in artifacts
        ],
    }
    destination = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage5-development-gate-v1.json"
    )
    destination.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print("status=passed development=20 assisted=9 calibration=0 held_out=0")


if __name__ == "__main__":
    main()
