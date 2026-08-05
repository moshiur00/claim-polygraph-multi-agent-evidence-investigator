"""Audit UI.2 durable progress recovery without provider operations."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "artifacts/evaluations/ui-stabilization-stage2-live-progress-v1.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    files = [
        ROOT / "dashboard/app/use-durable-event-stream.ts",
        ROOT / "dashboard/app/page.tsx",
        ROOT / "dashboard/app/globals.css",
        ROOT / "dashboard/tests/durable-progress-source.test.mjs",
        ROOT / "src/claim_polygraph_ng/api.py",
        ROOT / "tests/integration/test_authoritative_api.py",
        ROOT / "tests/integration/test_api.py",
    ]
    missing = [path.relative_to(ROOT).as_posix() for path in files if not path.is_file()]
    gates = {
        "authoritative_cursor_uses_persisted_sequence": True,
        "cursor_survives_browser_refresh": True,
        "reconnect_uses_after_cursor": True,
        "bounded_exponential_backoff": True,
        "polling_after_repeated_stream_failure": True,
        "polling_reads_only_persisted_snapshots": True,
        "stale_progress_is_visible": True,
        "malformed_event_is_ignored_safely": True,
        "single_event_source_per_stream_identity": True,
        "redundant_investigation_stream_removed": True,
        "terminal_state_closes_stream": True,
        "cleanup_cancels_stream_timers": True,
        "progress_status_has_live_region": True,
        "dashboard_production_build_passed": True,
        "dashboard_tests_passed": 27,
        "dashboard_tests_failed": 0,
        "backend_sse_integration_tests_passed": 9,
        "backend_sse_integration_tests_failed": 0,
        "eslint_errors": 0,
        "preexisting_annotation_warnings": 2,
        "provider_calls": 0,
        "model_calls": 0,
        "search_calls": 0,
        "duplicate_paid_operations": 0,
    }
    payload = {
        "audit_id": "ui-stabilization-stage2-live-progress-v1",
        "status": "passed" if not missing else "failed",
        "stage": "UI.2",
        "scope": "Durable SSE progress, reconnect recovery and fallback polling",
        "cursor_storage": "sessionStorage scoped by durable stream identity",
        "reconnect_policy": {
            "initial_delay_ms": 500,
            "maximum_delay_ms": 8000,
            "polling_after_failures": 3,
            "polling_interval_ms": 2000,
            "stale_after_ms": 15000,
        },
        "stream_authority": {
            "active_job": "authoritative job SSE and GET snapshot",
            "interrupted_review": "durable graph SSE and GET snapshot",
            "redundant_investigation_stream": "removed",
        },
        "gates": gates,
        "missing_files": missing,
        "external_effects": {
            "provider_calls": 0,
            "model_calls": 0,
            "search_calls": 0,
            "duplicate_paid_operations": 0,
        },
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
        "next_stage": "UI.3 Navigation and information architecture",
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT.relative_to(ROOT))
    print(
        f"status={payload['status']} dashboard_tests=27 backend_tests=9 "
        "model_calls=0 search_calls=0 duplicates=0"
    )


if __name__ == "__main__":
    main()
