import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from claim_polygraph_ng.evaluation.v3_annotation import (
    V3ReplacementCalibrationWorkbook,
)

ROOT = Path(__file__).resolve().parents[2]
WORKBOOK = (
    ROOT
    / "benchmarks/"
    "verification_construction_v3_stage6a_replacement_calibration_workbook_v1.json"
)


def test_replacement_calibration_has_twenty_fresh_cases_and_ten_families() -> None:
    workbook = V3ReplacementCalibrationWorkbook.model_validate_json(
        WORKBOOK.read_text(encoding="utf-8")
    )
    assert len(workbook.cases) == 20
    assert len({case.origin_family_id for case in workbook.cases}) >= 10
    assert all(case.annotation is None and case.approval is None for case in workbook.cases)
    assert sum(case.proposal.model_calls for case in workbook.cases) == 0


def test_replacement_contract_does_not_weaken_original_workbook_cardinality() -> None:
    payload = json.loads(WORKBOOK.read_text(encoding="utf-8"))
    payload["cases"] = payload["cases"][:-1]
    with pytest.raises(ValidationError):
        V3ReplacementCalibrationWorkbook.model_validate(payload)
