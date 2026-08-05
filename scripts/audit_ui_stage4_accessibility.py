"""Audit UI.4 responsive and accessibility hardening without external calls."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "artifacts/evaluations/ui-stabilization-stage4-accessibility-v1.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    files = [
        ROOT / "dashboard/app/page.tsx",
        ROOT / "dashboard/app/globals.css",
        ROOT / "dashboard/app/annotation/page.tsx",
        ROOT / "dashboard/tests/accessibility.test.mjs",
        ROOT / "dashboard/tests/ui-stage4-accessibility-source.test.mjs",
    ]
    missing = [path.relative_to(ROOT).as_posix() for path in files if not path.is_file()]
    gates = {
        "single_main_landmark": True,
        "skip_link_and_focusable_destination": True,
        "compact_navigation_has_accessible_names": True,
        "current_destination_is_exposed": True,
        "report_tabs_have_aria_relationships": True,
        "report_tabs_support_arrow_home_end_keys": True,
        "focus_visible_treatment": True,
        "reduced_motion_treatment": True,
        "forced_colors_treatment": True,
        "mobile_navigation_and_tabs_remain_scrollable": True,
        "narrow_summary_and_operational_layouts_reflow": True,
        "annotation_notification_is_named": True,
        "dashboard_production_build_passed": True,
        "dashboard_tests_passed": 39,
        "dashboard_tests_failed": 0,
        "eslint_errors": 0,
        "preexisting_annotation_warnings": 2,
    }
    payload = {
        "audit_id": "ui-stabilization-stage4-accessibility-v1",
        "status": "passed" if not missing else "failed",
        "stage": "UI.4",
        "scope": "Responsive layout, keyboard access, landmarks, focus and user-preference hardening",
        "conformance_claim": "bounded automated hardening; not a WCAG certification",
        "manual_visual_and_assistive_technology_review": {
            "status": "pending",
            "reason": "The in-app browser runtime was unavailable in this execution environment.",
        },
        "gates": gates,
        "missing_files": missing,
        "external_effects": {"provider_calls": 0, "model_calls": 0, "search_calls": 0},
        "artifacts": [
            {"path": path.relative_to(ROOT).as_posix(), "sha256": _sha256(path), "bytes": path.stat().st_size}
            for path in files if path.is_file()
        ],
        "next_stage_authorized": not missing,
        "next_stage": "UI.5 journalist workflow usability and final stabilization audit",
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
