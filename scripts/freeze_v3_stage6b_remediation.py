"""Freeze the V3.6b development/synthetic remediation boundary."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from claim_polygraph_ng.analysis.assisted_verification_construction import (
    ASSISTED_CONSTRUCTION_PROMPT_VERSION,
)


def _digest(root: Path, relative: str) -> dict[str, str]:
    return {
        "path": relative,
        "sha256": hashlib.sha256((root / relative).read_bytes()).hexdigest(),
    }


def main() -> None:
    root = Path(__file__).parents[1]
    failed_baseline = (
        "artifacts/evaluations/"
        "verification-construction-v3-stage6a-replacement-calibration-freeze-v1.json",
        "artifacts/evaluations/"
        "verification-construction-v3-stage6a-replacement-calibration-v1.json",
        "artifacts/evaluations/"
        "verification-construction-v3-stage6a-replacement-calibration-audit-v1.json",
    )
    implementation = (
        "src/claim_polygraph_ng/domain/verification.py",
        "src/claim_polygraph_ng/analysis/assisted_verification_construction.py",
        "src/claim_polygraph_ng/analysis/bounded_assisted_construction.py",
        "src/claim_polygraph_ng/providers/openai.py",
        "src/claim_polygraph_ng/providers/ollama.py",
        "tests/unit/test_v3_assisted_boundary.py",
        "benchmarks/verification_construction_v3_stage6b_synthetic_fixtures_v1.json",
        "artifacts/evaluations/"
        "verification-construction-v3-stage6b-synthetic-audit-v1.json",
        "artifacts/evaluations/"
        "verification-construction-v3-stage6b-fresh-calibration-protocol-v1.json",
    )
    manifest = {
        "manifest_id": "verification-construction-v3-stage6b-remediation-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "status": "remediation_frozen_awaiting_fresh_calibration_collection",
        "prompt_version": ASSISTED_CONSTRUCTION_PROMPT_VERSION,
        "failed_v36a_disposition": "preserved_immutable_diagnostic_baseline",
        "failed_v36a_artifacts": [
            _digest(root, path) for path in failed_baseline
        ],
        "remediation_scope": [
            "numeric normalization",
            "deterministic evidence-span reconstruction",
            "safe temporal binding defaults",
            "bounded scalar-subject canonicalization",
            "expanded eligibility and units",
            "bounded 1200-token structured response",
        ],
        "development_and_synthetic_only": True,
        "replacement_calibration_used_for_tests": False,
        "original_held_out_sealed": True,
        "implementation_artifacts": [
            _digest(root, path) for path in implementation
        ],
        "controls": {
            "remediation_model_calls": 0,
            "remediation_estimated_cost_usd": 0.0,
            "original_calibration_cases_loaded_for_tuning": 0,
            "replacement_calibration_cases_loaded_for_tuning": 0,
            "original_held_out_cases_loaded": 0,
        },
        "next_gate": (
            "Collect twenty new cases from at least ten independent origin "
            "families, obtain human annotation and distinct approval, then "
            "freeze and execute one new calibration."
        ),
    }
    destination = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage6b-remediation-manifest-v1.json"
    )
    destination.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print("status=frozen model_calls=0 held_out=0")


if __name__ == "__main__":
    main()
