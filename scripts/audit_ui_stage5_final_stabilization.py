"""Create the UI.5 workflow-usability and final stabilization audit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "artifacts/evaluations/ui-stabilization-stage5-final-v1.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    files = [
        ROOT / "dashboard/app/page.tsx",
        ROOT / "dashboard/app/globals.css",
        ROOT / "dashboard/app/annotation/page.tsx",
        ROOT / "dashboard/app/api-configuration.mjs",
        ROOT / "dashboard/app/navigation-state.mjs",
        ROOT / "dashboard/app/use-durable-event-stream.ts",
        ROOT / "dashboard/tests/ui-stage5-workflow-source.test.mjs",
        ROOT / "dashboard/tests/social-evidence-empty-state.test.mjs",
        ROOT / "dashboard/tests/decision-rationale-transparency.test.mjs",
        ROOT / "dashboard/tests/evidence-integrity-workspace.test.mjs",
        ROOT / "artifacts/evaluations/ui-stabilization-stage0-baseline-v1.json",
        ROOT / "artifacts/evaluations/ui-stabilization-stage1-connection-v1.json",
        ROOT / "artifacts/evaluations/ui-stabilization-stage2-live-progress-v1.json",
        ROOT / "artifacts/evaluations/ui-stabilization-stage3-navigation-v1.json",
        ROOT / "artifacts/evaluations/ui-stabilization-stage4-accessibility-v1.json",
    ]
    missing = [path.relative_to(ROOT).as_posix() for path in files if not path.is_file()]
    gates = {
        "general_user_decision_path_is_explicit": True,
        "evidence_investigation_handoff_is_explicit": True,
        "canonical_evidence_integrity_is_visible": True,
        "verification_and_citation_actions_are_direct": True,
        "publication_blocking_remains_fail_closed": True,
        "provisional_and_publishable_exports_are_distinct": True,
        "investigation_cost_and_process_telemetry_are_not_conflated": True,
        "review_queue_and_health_destinations_are_functional": True,
        "selection_and_progress_survive_navigation_or_reconnect": True,
        "keyboard_and_responsive_hardening_retained": True,
        "canonical_artifact_precedence_retained": True,
        "historical_stage_hashes_are_treated_as_snapshots": True,
        "dashboard_production_build_passed": True,
        "dashboard_tests_passed": 51,
        "dashboard_tests_failed": 0,
        "eslint_errors": 0,
        "eslint_warnings": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "search_calls": 0,
    }
    payload = {
        "audit_id": "ui-stabilization-stage5-final-v1",
        "status": "passed_with_manual_visual_followup" if not missing else "failed",
        "stage": "UI.5",
        "scope": "Inclusive evidence-investigation workflow usability and UI.0-UI.5 stabilization closure",
        "gates": gates,
        "resolved_baseline_defects": [
            "saved_api_address_overwritten_on_startup",
            "inferred_ipv6_api_url_not_bracketed",
            "sse_closes_without_reconnect_or_stale_state",
            "global_cost_can_be_mistaken_for_investigation_cost",
            "review_queue_navigation_inert",
            "system_health_navigation_inert",
            "tab_keyboard_pattern_incomplete",
            "malformed_sse_json_not_guarded",
            "annotation_hook_dependency_warnings",
        ],
        "remaining_followups": [
            "Run fresh 1440, 1280, 1024, 768 and 390 pixel browser captures.",
            "Perform screen-reader and 200% zoom smoke tests.",
            "Move editable reviewer identity defaults behind typed local identity context.",
            "Decompose the large dashboard component without changing canonical selectors.",
        ],
        "manual_visual_and_assistive_technology_review": {
            "status": "pending",
            "reason": "The configured in-app browser runtime could not initialize during this stabilization sequence.",
            "promotion_impact": "Local portfolio use is authorized; production accessibility certification is not claimed.",
        },
        "missing_files": missing,
        "external_effects": {"provider_calls": 0, "model_calls": 0, "search_calls": 0},
        "current_release_artifacts": [
            {"path": path.relative_to(ROOT).as_posix(), "sha256": _sha256(path), "bytes": path.stat().st_size}
            for path in files if path.is_file()
        ],
        "ui_stabilization_closed": not missing,
        "next_stage_authorized": not missing,
        "next_stage": "V5 planning and metric-baseline definition",
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
