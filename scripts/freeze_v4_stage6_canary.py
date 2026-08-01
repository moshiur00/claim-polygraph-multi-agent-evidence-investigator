"""Freeze the two-call V4.6 synthetic canary before provider execution."""

import hashlib
import json
import os
from pathlib import Path

from claim_polygraph_ng.analysis.assisted_verification_construction import (
    ASSISTED_CONSTRUCTION_PROMPT_VERSION,
)

FIXTURES = (
    {
        "canary_id": "v4.6-synthetic-scalar-canary-v1",
        "kind": "numerical_scalar",
        "claim_text": "The sealed Vessel Q contains exactly 37 litres.",
        "evidence_text": (
            "The signed laboratory register states that the sealed Vessel Q "
            "contains exactly 37 litres."
        ),
    },
    {
        "canary_id": "v4.6-synthetic-temporal-canary-v1",
        "kind": "temporal_status",
        "claim_text": "Permit Z became effective on 17 February 2022.",
        "evidence_text": (
            "The fictional permit register states that Permit Z became "
            "effective on 17 February 2022."
        ),
    },
)


def _env_value(root: Path, name: str, default: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    env_path = root / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{name}="):
                return line.partition("=")[2].strip().strip("\"'")
    return default


def main() -> None:
    root = Path(__file__).parents[1]
    stage5_path = (
        root / "artifacts/evaluations/verification-construction-v4-stage5-offline-gate-v1.json"
    )
    stage5 = json.loads(stage5_path.read_text(encoding="utf-8"))
    if not stage5["exit_criterion_met"]:
        raise ValueError("V4.5 must pass before freezing V4.6")
    fixtures = [
        {
            **item,
            "fixture_sha256": hashlib.sha256(
                f"{item['claim_text']}\n{item['evidence_text']}".encode()
            ).hexdigest(),
        }
        for item in FIXTURES
    ]
    manifest = {
        "manifest_id": "verification-construction-v4-stage6-canary-manifest-v1",
        "status": "frozen",
        "synthetic_fixture_count": 2,
        "provider": "openai",
        "model": _env_value(root, "OPENAI_FAST_MODEL", "gpt-4o-mini"),
        "prompt_version": ASSISTED_CONSTRUCTION_PROMPT_VERSION,
        "maximum_provider_attempts": 2,
        "maximum_calls_per_fixture": 1,
        "maximum_input_tokens_per_call": 6000,
        "maximum_output_tokens_per_call": 900,
        "automatic_retries": 0,
        "maximum_total_cost_usd": 0.75,
        "fixtures": fixtures,
        "required_checks": [
            "branch_specific_structured_schema",
            "exact_claim_and_evidence_spans",
            "durable_usage_or_unknown_upper_bound",
            "cached_replay_without_provider_attempt",
            "cancellation_before_reservation",
            "duplicate_paid_operations_zero",
        ],
        "dataset_exposure": {
            "benchmark": 0,
            "development": 0,
            "calibration": 0,
            "held_out": 0,
        },
        "predecessor": {
            "path": stage5_path.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(stage5_path.read_bytes()).hexdigest(),
        },
        "model_calls_before_execution": 0,
        "network_calls_before_execution": 0,
        "paid_operations_before_execution": 0,
    }
    destination = (
        root / "artifacts/evaluations/verification-construction-v4-stage6-canary-manifest-v1.json"
    )
    destination.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print(f"status=frozen fixtures=2 model={manifest['model']} attempt_ceiling=2 calls=0")


if __name__ == "__main__":
    main()
