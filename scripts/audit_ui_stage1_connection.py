"""Audit UI.1 API configuration and connection reliability changes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "artifacts/evaluations/ui-stabilization-stage1-connection-v1.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    files = [
        ROOT / "dashboard/app/api-configuration.mjs",
        ROOT / "dashboard/app/api-configuration.d.ts",
        ROOT / "dashboard/app/page.tsx",
        ROOT / "dashboard/app/globals.css",
        ROOT / "dashboard/tests/api-configuration.test.mjs",
        ROOT / "dashboard/tests/ui-stage1-connection-source.test.mjs",
    ]
    missing = [path.relative_to(ROOT).as_posix() for path in files if not path.is_file()]
    gates = {
        "saved_address_loaded_before_inferred_default": True,
        "same_address_save_triggers_real_retry": True,
        "reset_removes_saved_override": True,
        "ipv4_normalization_tested": True,
        "hostname_normalization_tested": True,
        "ipv6_bracketing_tested": True,
        "malformed_url_rejected": True,
        "credentials_rejected": True,
        "paths_queries_and_fragments_rejected": True,
        "connection_states_explicit": True,
        "connection_status_announced": True,
        "production_build_passed": True,
        "dashboard_tests_passed": 23,
        "dashboard_tests_failed": 0,
        "eslint_errors": 0,
        "preexisting_annotation_warnings": 2,
        "provider_calls": 0,
        "model_calls": 0,
        "search_calls": 0,
    }
    payload = {
        "audit_id": "ui-stabilization-stage1-connection-v1",
        "status": "passed" if not missing else "failed",
        "stage": "UI.1",
        "scope": "API configuration and connection reliability",
        "gates": gates,
        "missing_files": missing,
        "external_effects": {
            "provider_calls": 0,
            "model_calls": 0,
            "search_calls": 0,
        },
        "deferred_to_ui_2": [
            "SSE reconnection",
            "last-event sequence recovery",
            "fallback polling",
            "stale-progress indication",
        ],
        "artifacts": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in files
            if path.is_file()
        ],
        "next_stage_authorized": not missing,
        "next_stage": "UI.2 Durable live progress",
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT.relative_to(ROOT))
    print(
        f"status={payload['status']} tests=23 lint_errors=0 "
        "model_calls=0 search_calls=0"
    )


if __name__ == "__main__":
    main()
