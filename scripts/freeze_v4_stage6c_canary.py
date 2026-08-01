"""Freeze the final authorized V4 temporal canary."""

import hashlib
import json
import os
from pathlib import Path

from claim_polygraph_ng.analysis.assisted_verification_construction import (
    ASSISTED_CANONICALIZATION_VERSION,
    ASSISTED_CONSTRUCTION_PROMPT_VERSION,
)
from claim_polygraph_ng.evaluation.v4_budget_amendment import (
    V4CanaryBudgetAmendment,
)

FIXTURE = {
    "canary_id": "v4.6c-final-synthetic-temporal-canary-v1",
    "kind": "temporal_status",
    "claim_text": "License S took effect on 6 April 2020.",
    "evidence_text": (
        "The fictional licensing register states that License S took effect on 6 April 2020."
    ),
}


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _env_value(root: Path, name: str, default: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    for line in (root / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{name}="):
            return line.partition("=")[2].strip().strip("\"'")
    return default


def main() -> None:
    root = Path(__file__).parents[1]
    evaluations = root / "artifacts/evaluations"
    amendment_path = evaluations / "verification-construction-v4-canary-budget-amendment-v1.json"
    amendment = V4CanaryBudgetAmendment.model_validate_json(
        amendment_path.read_text(encoding="utf-8")
    )
    if not amendment.final_canary_authorized or amendment.synthetic_calls_remaining != 1:
        raise ValueError("the V4.6c final canary is not authorized")
    remediation_path = evaluations / "verification-construction-v4-stage6b-temporal-wire-v1.json"
    remediation = json.loads(remediation_path.read_text(encoding="utf-8"))
    if not remediation["exit_criterion_met"]:
        raise ValueError("V4.6b must pass before the final canary")
    fixture = {
        **FIXTURE,
        "fixture_sha256": hashlib.sha256(
            f"{FIXTURE['claim_text']}\n{FIXTURE['evidence_text']}".encode()
        ).hexdigest(),
    }
    manifest = {
        "manifest_id": "verification-construction-v4-stage6c-canary-manifest-v1",
        "status": "frozen",
        "final_authorized_canary": True,
        "provider": "openai",
        "model": _env_value(root, "OPENAI_FAST_MODEL", "gpt-4o-mini"),
        "prompt_version": ASSISTED_CONSTRUCTION_PROMPT_VERSION,
        "canonicalization_version": ASSISTED_CANONICALIZATION_VERSION,
        "maximum_provider_attempts": 1,
        "maximum_calls_per_fixture": 1,
        "maximum_input_tokens": 6000,
        "maximum_output_tokens": 900,
        "automatic_retries": 0,
        "maximum_total_cost_usd": 0.25,
        "fixture": fixture,
        "fresh_receipt_identity": True,
        "dataset_exposure": {
            "benchmark": 0,
            "development": 0,
            "calibration": 0,
            "held_out": 0,
        },
        "budget_amendment": {
            "path": amendment_path.relative_to(root).as_posix(),
            "sha256": _hash(amendment_path),
        },
        "offline_remediation": {
            "path": remediation_path.relative_to(root).as_posix(),
            "sha256": _hash(remediation_path),
        },
        "model_calls_before_execution": 0,
        "network_calls_before_execution": 0,
        "paid_operations_before_execution": 0,
    }
    destination = evaluations / "verification-construction-v4-stage6c-canary-manifest-v1.json"
    destination.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print(
        f"status=frozen model={manifest['model']} attempts=1 "
        f"canonicalization={ASSISTED_CANONICALIZATION_VERSION}"
    )


if __name__ == "__main__":
    main()
