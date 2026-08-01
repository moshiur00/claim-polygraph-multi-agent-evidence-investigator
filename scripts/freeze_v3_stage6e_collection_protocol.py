"""Freeze V3.6e collection and human-review controls before calibration."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


def _artifact(root: Path, relative: str) -> dict[str, str]:
    return {
        "path": relative,
        "sha256": hashlib.sha256((root / relative).read_bytes()).hexdigest(),
    }


def main() -> None:
    root = Path(__file__).parents[1]
    artifacts = (
        "benchmarks/"
        "verification_construction_v3_stage6e_fresh_calibration_workbook_v1.json",
        "artifacts/evaluations/"
        "verification-construction-v3-stage6e-collection-audit-v1.json",
        "scripts/build_v3_stage6e_fresh_calibration_workbook.py",
        "scripts/audit_v3_stage6e_collection.py",
        "dashboard/app/annotation/page.tsx",
        "dashboard/public/v3-stage6e-fresh-calibration.json",
    )
    manifest = {
        "manifest_id": "verification-construction-v3-stage6e-collection-protocol-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "status": "frozen_awaiting_human_annotation_and_distinct_approval",
        "case_count": 20,
        "minimum_origin_families": 10,
        "maximum_cases_per_origin_family": 2,
        "collection_rules": {
            "accessible_official_html_only": True,
            "pdf_downloads_allowed": False,
            "restricted_content_allowed": False,
            "previously_exposed_claim_url_or_family_reuse_allowed": False,
        },
        "review_rules": {
            "machine_suggestions_prefilled": True,
            "annotator_identity_default": "Md Moshiur Rahman",
            "approver_identity_default": "Md Rashedul Islam",
            "annotation_requires_explicit_human_record_action": True,
            "approval_requires_distinct_explicit_action": True,
            "approval_decision_defaults_to": "return_for_revision",
            "approval_checklist_defaults_checked": 0,
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
        "execution_controls": {
            "model_calls_before_approval_and_freeze": 0,
            "calibration_execution_limit_after_approval": 1,
            "held_out_may_open_only_if_every_gate_passes": True,
            "held_out_cases_exposed_to_model": 0,
        },
        "artifacts": [_artifact(root, path) for path in artifacts],
    }
    destination = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage6e-collection-protocol-v1.json"
    )
    destination.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print("status=frozen model_calls=0 held_out_provider_exposure=0")


if __name__ == "__main__":
    main()
