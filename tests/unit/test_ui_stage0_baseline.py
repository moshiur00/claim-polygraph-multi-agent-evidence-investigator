import json
from pathlib import Path

ROOT = Path(__file__).parents[2]
ARTIFACT = ROOT / "artifacts/evaluations/ui-stabilization-stage0-baseline-v1.json"


def test_ui_stage0_baseline_is_complete_and_offline() -> None:
    baseline = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert baseline["status"] == "frozen_visual_capture_deferred"
    assert baseline["next_stage_authorized"]
    assert baseline["missing_inputs"] == []
    assert baseline["external_effects"] == {
        "provider_calls": 0,
        "model_calls": 0,
        "search_calls": 0,
        "benchmark_cases_loaded": 0,
    }
    assert len(baseline["authority_map"]) == 12
    assert len(baseline["known_defects"]) == 12
    assert baseline["supported_viewports_px"] == [1440, 1280, 1024, 768, 390]


def test_ui_stage0_records_content_addressed_inputs() -> None:
    baseline = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert baseline["inputs"]
    for item in baseline["inputs"]:
        assert item["path"]
        assert len(item["sha256"]) == 64
        int(item["sha256"], 16)
        assert item["bytes"] > 0


def test_ui_stage0_does_not_claim_a_visual_capture() -> None:
    baseline = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert not baseline["visual_baseline"]["captured"]
    assert not baseline["visual_baseline"]["fabricated_or_stale_screenshot_used"]
    assert baseline["visual_baseline"]["required_before_stage"] == "UI.9"
