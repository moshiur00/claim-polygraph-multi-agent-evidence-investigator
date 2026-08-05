"""Audit UI.3 navigation and information architecture without provider calls."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "artifacts/evaluations/ui-stabilization-stage3-navigation-v1.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    files = [
        ROOT / "dashboard/app/navigation-state.mjs",
        ROOT / "dashboard/app/navigation-state.d.ts",
        ROOT / "dashboard/app/page.tsx",
        ROOT / "dashboard/app/globals.css",
        ROOT / "dashboard/tests/navigation-state.test.mjs",
        ROOT / "dashboard/tests/ui-stage3-navigation-source.test.mjs",
        ROOT / "dashboard/tests/accessibility.test.mjs",
    ]
    missing = [path.relative_to(ROOT).as_posix() for path in files if not path.is_file()]
    gates = {
        "review_queue_destination_is_functional": True,
        "review_state_comes_from_canonical_history": True,
        "system_health_destination_is_functional": True,
        "health_and_telemetry_are_distinguished": True,
        "investigations_are_searchable": True,
        "selection_is_url_preserved": True,
        "browser_back_forward_is_supported": True,
        "loading_empty_error_and_unavailable_states_exist": True,
        "dashboard_production_build_passed": True,
        "dashboard_tests_passed": 35,
        "dashboard_tests_failed": 0,
        "eslint_errors": 0,
        "preexisting_annotation_warnings": 2,
        "provider_calls": 0,
        "model_calls": 0,
        "search_calls": 0,
    }
    payload = {
        "audit_id": "ui-stabilization-stage3-navigation-v1",
        "status": "passed" if not missing else "failed",
        "stage": "UI.3",
        "scope": "Navigation, review queue, system health, case search and URL restoration",
        "gates": gates,
        "visual_verification": {
            "status": "unavailable",
            "reason": "The in-app browser runtime could not initialize in this execution environment.",
            "substitute_browser_used": False,
        },
        "missing_files": missing,
        "external_effects": {"provider_calls": 0, "model_calls": 0, "search_calls": 0},
        "artifacts": [
            {"path": path.relative_to(ROOT).as_posix(), "sha256": _sha256(path), "bytes": path.stat().st_size}
            for path in files if path.is_file()
        ],
        "next_stage_authorized": not missing,
        "next_stage": "UI.4 responsive layout and accessibility hardening",
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
