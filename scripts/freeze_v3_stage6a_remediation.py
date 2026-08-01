"""Freeze the V3.6 failure baseline and declare the isolated V3.6a boundary."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT
    / "artifacts/evaluations/"
    "verification-construction-v3-stage6a-remediation-manifest-v1.json"
)
FAILED_BASELINE = (
    "artifacts/evaluations/"
    "verification-construction-v3-stage6-calibration-freeze-v1.json",
    "artifacts/evaluations/"
    "verification-construction-v3-stage6-calibration-v1.json",
    "artifacts/evaluations/"
    "verification-construction-v3-stage6-calibration-audit-v1.json",
)
REMEDIATION_CONTRACTS = (
    "src/claim_polygraph_ng/analysis/assisted_verification_construction.py",
    "src/claim_polygraph_ng/analysis/bounded_assisted_construction.py",
    "src/claim_polygraph_ng/providers/openai.py",
    "src/claim_polygraph_ng/providers/ollama.py",
)
REPLACEMENT_REVIEW_PACKET = (
    "benchmarks/"
    "verification_construction_v3_stage6a_replacement_calibration_workbook_v1.json"
)


def digest(relative_path: str) -> dict[str, str]:
    content = (ROOT / relative_path).read_bytes()
    return {
        "path": relative_path,
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def main() -> None:
    manifest = {
        "manifest_id": "verification-construction-v3-stage6a-remediation-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "failed_configuration_disposition": "preserved_immutable_diagnostic_baseline",
        "failed_baseline_artifacts": [digest(path) for path in FAILED_BASELINE],
        "remediation_configuration": {
            "prompt_version": "verification-construction-v3-remediation-v4",
            "development_and_synthetic_only": True,
            "original_calibration_treated_as_exposed": True,
            "fresh_replacement_calibration_required": True,
            "replacement_calibration_execution_limit": 1,
            "original_held_out_sealed": True,
            "held_out_open_condition": "replacement_calibration_passes_all_frozen_gates",
            "contracts": [digest(path) for path in REMEDIATION_CONTRACTS],
            "replacement_review_packet": digest(REPLACEMENT_REVIEW_PACKET),
        },
        "current_status": "awaiting_fresh_human_annotation_and_distinct_approval",
        "controls": {
            "model_calls": 0,
            "estimated_cost_usd": 0.0,
            "original_held_out_cases_loaded": 0,
            "original_held_out_cases_exposed": 0,
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
