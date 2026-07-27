from pathlib import Path

import pytest
from pydantic import ValidationError

from claim_polygraph_ng.evaluation.phase5_quality_calibration import (
    SourceQualityCalibrationSet,
    evaluate_source_quality_calibration,
    load_source_quality_calibration,
)


def test_repository_calibration_agrees_and_is_human_reviewed():
    root = Path(__file__).parents[2]
    calibration = load_source_quality_calibration(
        root / "benchmarks/phase5_source_quality_calibration_v1.json"
    )

    result = evaluate_source_quality_calibration(calibration)

    assert result.case_count == 8
    assert result.dimension_count == 64
    assert result.agreement == 1
    assert result.agreement_gate_passed
    assert result.human_review_gate_passed
    assert result.valid
    assert result.mismatches == ()


def test_review_requires_distinct_people():
    root = Path(__file__).parents[2]
    draft = load_source_quality_calibration(
        root / "benchmarks/phase5_source_quality_calibration_v1.json"
    )
    payload = draft.model_dump(mode="json")
    payload.update(
        {
            "status": "reviewed",
            "annotated_by": "Same Person",
            "approved_by": "same person",
            "approval_date": "2026-07-28",
        }
    )

    with pytest.raises(ValidationError, match="distinct"):
        SourceQualityCalibrationSet.model_validate(payload)


def test_changed_label_is_reported():
    root = Path(__file__).parents[2]
    draft = load_source_quality_calibration(
        root / "benchmarks/phase5_source_quality_calibration_v1.json"
    )
    payload = draft.model_dump(mode="json")
    payload["cases"][0]["expected_findings"]["authority"] = "favorable"
    changed = SourceQualityCalibrationSet.model_validate(payload)

    result = evaluate_source_quality_calibration(changed)

    assert result.agreement == 63 / 64
    assert result.mismatches == ("QUAL-001:authority: expected favorable, observed unknown",)
