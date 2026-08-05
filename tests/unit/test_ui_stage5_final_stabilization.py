import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[2]
ARTIFACT = ROOT / "artifacts/evaluations/ui-stabilization-stage5-final-v1.json"


def test_ui_stage5_closes_automated_stabilization_gates() -> None:
    audit = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert audit["status"] == "passed_with_manual_visual_followup"
    assert audit["ui_stabilization_closed"]
    assert audit["next_stage_authorized"]
    assert not audit["missing_files"]
    assert audit["gates"]["dashboard_tests_passed"] == 51
    assert audit["gates"]["general_user_decision_path_is_explicit"]
    assert audit["gates"]["canonical_evidence_integrity_is_visible"]
    assert audit["gates"]["eslint_errors"] == 0
    assert audit["gates"]["eslint_warnings"] == 0
    assert audit["external_effects"] == {"provider_calls": 0, "model_calls": 0, "search_calls": 0}


def test_ui_stage5_current_release_hashes_match() -> None:
    audit = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    for item in audit["current_release_artifacts"]:
        path = ROOT / item["path"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
