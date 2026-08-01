"""Freeze the zero-call V3.6d remediation and its next calibration boundary."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from claim_polygraph_ng.analysis.assisted_verification_construction import (
    ASSISTED_CONSTRUCTION_PROMPT_VERSION,
)


def _artifact(root: Path, relative: str) -> dict[str, str]:
    return {
        "path": relative,
        "sha256": hashlib.sha256((root / relative).read_bytes()).hexdigest(),
    }


def main() -> None:
    root = Path(__file__).parents[1]
    previous = (
        "artifacts/evaluations/"
        "verification-construction-v3-stage6c-fresh-calibration-freeze-v1.json",
        "artifacts/evaluations/"
        "verification-construction-v3-stage6c-fresh-calibration-v1.json",
        "artifacts/evaluations/"
        "verification-construction-v3-stage6c-fresh-calibration-audit-v1.json",
    )
    implementation = (
        "src/claim_polygraph_ng/analysis/assisted_verification_construction.py",
        "src/claim_polygraph_ng/providers/ollama.py",
        "tests/unit/test_v3_assisted_boundary.py",
        "scripts/audit_v3_stage6d_remediation.py",
        "artifacts/evaluations/"
        "verification-construction-v3-stage6d-remediation-audit-v1.json",
    )
    manifest = {
        "manifest_id": "verification-construction-v3-stage6d-remediation-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "status": "remediation_frozen_awaiting_fresh_calibration",
        "prompt_version": ASSISTED_CONSTRUCTION_PROMPT_VERSION,
        "v36c_disposition": "preserved_failed_calibration_diagnostic",
        "v36c_artifacts": [_artifact(root, path) for path in previous],
        "remediation_scope": [
            "bounded common-count and hyphenated-unit eligibility",
            "explicit temporal creation and historical-range routing",
            "pre-1900 explicit date support",
            "month-first provider date normalization",
        ],
        "implementation_artifacts": [
            _artifact(root, path) for path in implementation
        ],
        "controls": {
            "development_synthetic_and_exposed_v36c_only": True,
            "model_calls": 0,
            "estimated_cost_usd": 0.0,
            "original_held_out_cases_loaded": 0,
            "original_held_out_cases_exposed_to_model": 0,
        },
        "next_calibration": {
            "fresh_cases_required": 20,
            "minimum_origin_families": 10,
            "ai_prefill_allowed": True,
            "required_annotator": "Md Moshiur Rahman",
            "required_distinct_approver": "Md Rashedul Islam",
            "human_review_required": True,
            "execution_limit_after_freeze": 1,
            "original_held_out_may_open_only_if_every_frozen_gate_passes": True,
        },
    }
    destination = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage6d-remediation-manifest-v1.json"
    )
    if destination.exists():
        raise FileExistsError("V3.6d remediation manifest already exists")
    destination.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print("status=frozen model_calls=0 held_out=0")


if __name__ == "__main__":
    main()
