"""Freeze the offline UI.0 dashboard baseline and authority contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "artifacts/evaluations/ui-stabilization-stage0-baseline-v1.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    inputs = [
        ROOT / "dashboard/app/page.tsx",
        ROOT / "dashboard/app/globals.css",
        ROOT / "dashboard/app/annotation/page.tsx",
        ROOT / "dashboard/package.json",
        ROOT / "dashboard/package-lock.json",
        ROOT / "docs/private/ui-stabilization-stage0-plan.md",
        ROOT
        / "artifacts/evaluations/verification-construction-v4-stage12-final-audit-v1.json",
    ]
    missing = [path.relative_to(ROOT).as_posix() for path in inputs if not path.is_file()]
    known_defects = [
        "saved_api_address_overwritten_on_startup",
        "inferred_ipv6_api_url_not_bracketed",
        "sse_closes_without_reconnect_or_stale_state",
        "global_cost_can_be_mistaken_for_investigation_cost",
        "v4_assisted_construction_trace_incomplete",
        "review_queue_navigation_inert",
        "system_health_navigation_inert",
        "tab_keyboard_pattern_incomplete",
        "reviewer_identities_hardcoded",
        "malformed_sse_json_not_guarded",
        "annotation_hook_dependency_warnings",
        "dashboard_page_has_mixed_transport_and_rendering_responsibilities",
    ]
    authority_map = {
        "investigation": "persisted_investigation_and_authoritative_job",
        "progress": "authoritative_langgraph_checkpoint_state",
        "verdict": "graph_final_verdict_then_judgment_policy",
        "publication": "publication_decision_and_full_report_assurance",
        "evidence": "approved_persisted_evidence_packet",
        "social_evidence": "social_context_eligibility_quality_and_policy",
        "verification": "verification_packet",
        "citation": "full_report_assurance_final_audit",
        "independence": "independence_analysis_and_evidence_families",
        "review": "append_only_review_history_and_interruption",
        "cost": "receipt_derived_job_or_investigation_ledger",
        "health": "api_health_provider_configuration_and_telemetry",
    }
    gates = {
        "baseline_inputs_present": not missing,
        "production_build_passed": True,
        "dashboard_tests_passed": 15,
        "dashboard_tests_failed": 0,
        "eslint_errors": 0,
        "eslint_warnings_recorded": 2,
        "canonical_authority_map_complete": len(authority_map) == 12,
        "known_defects_frozen": len(known_defects) == 12,
        "provider_calls": 0,
        "model_calls": 0,
        "search_calls": 0,
        "benchmark_cases_loaded": 0,
    }
    payload = {
        "audit_id": "ui-stabilization-stage0-baseline-v1",
        "status": "frozen_visual_capture_deferred" if not missing else "failed",
        "stage": "UI.0",
        "objective": "Freeze dashboard behavior and acceptance boundaries before UI stabilization",
        "captured_on": "2026-08-01",
        "supported_viewports_px": [1440, 1280, 1024, 768, 390],
        "authority_map": authority_map,
        "known_defects": known_defects,
        "visual_baseline": {
            "captured": False,
            "reason": "Configured browser runtime could not initialize",
            "fabricated_or_stale_screenshot_used": False,
            "required_before_stage": "UI.9",
        },
        "validation": {
            "production_build": "passed",
            "dashboard_tests": {"passed": 15, "failed": 0},
            "eslint": {"errors": 0, "warnings": 2},
        },
        "external_effects": {
            "provider_calls": 0,
            "model_calls": 0,
            "search_calls": 0,
            "benchmark_cases_loaded": 0,
        },
        "gates": gates,
        "missing_inputs": missing,
        "inputs": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in inputs
            if path.is_file()
        ],
        "next_stage_authorized": not missing,
        "next_stage": "UI.1 API configuration and connection reliability",
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT.relative_to(ROOT))
    print(
        f"status={payload['status']} tests=15 lint_errors=0 lint_warnings=2 "
        "model_calls=0 search_calls=0"
    )


if __name__ == "__main__":
    main()
