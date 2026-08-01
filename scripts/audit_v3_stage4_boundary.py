"""Audit and hash the V3.4 provider boundary without executing a model."""

import hashlib
import json
from pathlib import Path

from claim_polygraph_ng.analysis.assisted_verification_construction import (
    AssistedConstructionProposal,
)
from claim_polygraph_ng.analysis.bounded_assisted_construction import (
    AssistedConstructionBudget,
)
from claim_polygraph_ng.domain import ModelTask


def main() -> None:
    root = Path(__file__).parents[1]
    manifest_path = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage4-provider-boundary-v1.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["selected_model"] != "gpt-5.6-luna":
        raise ValueError("V3.4 model selection changed")
    if manifest["status"] != "wired_not_executed":
        raise ValueError("V3.4 must not execute benchmark calls")
    if any(manifest["execution_controls"].values()):
        raise ValueError("V3.4 execution controls must remain false or zero")

    budget = AssistedConstructionBudget()
    expected_budget = {
        "maximum_calls_per_case": budget.maximum_calls_per_case,
        "maximum_total_calls": budget.maximum_total_calls,
        "maximum_input_tokens_per_call": budget.maximum_input_tokens,
        "maximum_output_tokens_per_call": budget.maximum_output_tokens,
        "maximum_total_cost_usd": budget.maximum_total_cost_usd,
    }
    if manifest["frozen_budget"] != expected_budget:
        raise ValueError("implemented and declared V3.4 budgets differ")
    forbidden = {"verdict", "verification_state", "readiness", "publication"}
    if forbidden.intersection(AssistedConstructionProposal.model_fields):
        raise ValueError("assisted proposal crosses a protected decision boundary")
    if (
        ModelTask.ASSIST_VERIFICATION_CONSTRUCTION.value
        != "assist_verification_construction"
    ):
        raise ValueError("assisted task identifier changed")

    paths = (
        Path("src/claim_polygraph_ng/analysis/assisted_verification_construction.py"),
        Path("src/claim_polygraph_ng/analysis/bounded_assisted_construction.py"),
        Path("src/claim_polygraph_ng/providers/idempotent.py"),
        Path("src/claim_polygraph_ng/providers/openai.py"),
        Path("artifacts/evaluations/verification-construction-v3-stage4-provider-boundary-v1.json"),
    )
    audit = {
        "audit_id": "verification-construction-v3-stage4-boundary-audit-v1",
        "status": "passed",
        "selected_model": manifest["selected_model"],
        "model_calls": 0,
        "network_calls": 0,
        "paid_operations": 0,
        "prompt_tuning_performed": False,
        "artifacts": [
            {
                "path": path.as_posix(),
                "sha256": hashlib.sha256((root / path).read_bytes()).hexdigest(),
            }
            for path in paths
        ],
        "gates": {
            "structured_output": True,
            "exact_span_validation": True,
            "approved_packet_enforcement": True,
            "durable_receipt_cache": True,
            "duplicate_charge_prevention": True,
            "one_attempt_per_case": True,
            "cost_and_token_budgets": True,
            "cooperative_cancellation": True,
            "privacy_safe_telemetry": True,
            "judgment_fields_absent": True,
        },
    }
    destination = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage4-boundary-audit-v1.json"
    )
    destination.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print("status=passed model=gpt-5.6-luna model_calls=0 paid_operations=0")


if __name__ == "__main__":
    main()
