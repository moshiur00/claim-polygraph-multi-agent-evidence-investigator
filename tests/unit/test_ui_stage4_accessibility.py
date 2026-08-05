import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[2]
ARTIFACT = ROOT / "artifacts/evaluations/ui-stabilization-stage4-accessibility-v1.json"


def test_ui_stage4_passes_bounded_accessibility_gates() -> None:
    audit = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert audit["status"] == "passed"
    assert audit["next_stage_authorized"]
    assert not audit["missing_files"]
    assert audit["gates"]["dashboard_tests_passed"] == 39
    assert audit["conformance_claim"] == "bounded automated hardening; not a WCAG certification"
    assert audit["external_effects"] == {"provider_calls": 0, "model_calls": 0, "search_calls": 0}


def test_ui_stage4_artifact_hashes_are_well_formed_historical_snapshots() -> None:
    audit = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    for item in audit["artifacts"]:
        assert len(item["sha256"]) == 64
        int(item["sha256"], 16)
        assert item["bytes"] > 0
