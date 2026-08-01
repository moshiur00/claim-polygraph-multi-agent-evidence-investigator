"""One-way access gate for the frozen V3 calibration split."""

import hashlib
import json
from pathlib import Path

from pydantic import Field

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.evaluation.v3_annotation import V3AnnotationCase
from claim_polygraph_ng.evaluation.v3_manifest import V3DatasetSplit


class V3CalibrationSelection(DomainModel):
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    case_count: int = Field(ge=1)
    case_ids: tuple[str, ...]


def select_v3_calibration_cases(
    dataset_path: str | Path,
) -> tuple[tuple[V3AnnotationCase, ...], V3CalibrationSelection]:
    path = Path(dataset_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = tuple(
        V3AnnotationCase.model_validate(case)
        for case in payload["cases"]
        if case["split"] == V3DatasetSplit.CALIBRATION
    )
    if len(cases) != 20:
        raise ValueError("V3.6 requires exactly 20 calibration cases")
    if any(case.split is not V3DatasetSplit.CALIBRATION for case in cases):
        raise ValueError("a non-calibration case crossed the V3.6 split gate")
    return cases, V3CalibrationSelection(
        dataset_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        case_count=len(cases),
        case_ids=tuple(case.case_id for case in cases),
    )
