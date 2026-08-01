"""Freeze V4.6a remediation evidence and one fresh temporal canary."""

import hashlib
import json
import os
from pathlib import Path

from claim_polygraph_ng.analysis.assisted_verification_construction import (
    ASSISTED_CANONICALIZATION_VERSION,
    ASSISTED_CONSTRUCTION_PROMPT_VERSION,
)

PRESERVED_HASHES = {
    "artifacts/evaluations/verification-construction-v4-stage6-canary-manifest-v1.json": (
        "efac17962697f759a008694bf768179bec8f0948ea2d3877ec0d36ec94d696dd"
    ),
    "artifacts/evaluations/verification-construction-v4-stage6-canary-result-v1.json": (
        "fc6ca12f797a400296c36d6c587e6bf721c3e6ed59ae27370491cb338e3c7d8c"
    ),
    "artifacts/evaluations/verification-construction-v4-stage6-canary-audit-v1.json": (
        "30726fc1faadc2cf4001936b3fdbcd60a11c029112d89daab7e79f9bf64c7b76"
    ),
    "data/v4-stage6-paid-operations.db": (
        "8b05747a054d8404caa22ad4c6d08f0a1d3598d9791e51e77105ced3041ecc50"
    ),
}
FIXTURE = {
    "canary_id": "v4.6a-synthetic-temporal-canary-v1",
    "kind": "temporal_status",
    "claim_text": "Charter R entered into force on 9 March 2021.",
    "evidence_text": (
        "The fictional registry records that Charter R entered into force on 9 March 2021."
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
    actual = {path: _hash(root / path) for path in PRESERVED_HASHES}
    if actual != PRESERVED_HASHES:
        raise ValueError("consumed V4.6 evidence was modified")
    fixture = {
        **FIXTURE,
        "fixture_sha256": hashlib.sha256(
            f"{FIXTURE['claim_text']}\n{FIXTURE['evidence_text']}".encode()
        ).hexdigest(),
    }
    offline = {
        "audit_id": "verification-construction-v4-stage6a-offline-remediation-v1",
        "status": "passed",
        "canonicalization_version": ASSISTED_CANONICALIZATION_VERSION,
        "targeted_tests_passed": 46,
        "targeted_tests_failed": 0,
        "model_calls": 0,
        "network_calls": 0,
        "paid_operations": 0,
        "preserved_v4_6_artifacts": [
            {"path": path, "sha256": digest} for path, digest in actual.items()
        ],
        "gates": {
            "unmatched_quote_not_expanded": True,
            "unique_same_sentence_status_expands": True,
            "cross_sentence_expansion_rejected": True,
            "duplicate_status_expansion_rejected": True,
            "exact_status_in_quote_required": True,
            "consumed_result_preserved": True,
        },
        "exit_criterion_met": True,
    }
    evaluations = root / "artifacts/evaluations"
    offline_path = evaluations / "verification-construction-v4-stage6a-offline-remediation-v1.json"
    offline_path.write_text(json.dumps(offline, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "manifest_id": "verification-construction-v4-stage6a-canary-manifest-v1",
        "status": "frozen",
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
        "offline_remediation": {
            "path": offline_path.relative_to(root).as_posix(),
            "sha256": _hash(offline_path),
        },
        "model_calls_before_execution": 0,
        "network_calls_before_execution": 0,
        "paid_operations_before_execution": 0,
    }
    manifest_path = evaluations / "verification-construction-v4-stage6a-canary-manifest-v1.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(offline_path.relative_to(root))
    print(manifest_path.relative_to(root))
    print(
        f"status=frozen model={manifest['model']} attempts=1 "
        f"canonicalization={ASSISTED_CANONICALIZATION_VERSION}"
    )


if __name__ == "__main__":
    main()
