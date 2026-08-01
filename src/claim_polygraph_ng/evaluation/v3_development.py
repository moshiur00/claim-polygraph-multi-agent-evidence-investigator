"""Sealed development-split access for V3 assisted-construction debugging."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import Field

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.evaluation.v3_annotation import V3AnnotationCase
from claim_polygraph_ng.evaluation.v3_manifest import (
    V3ConstructionGoldLabel,
    V3DatasetSplit,
)


class V3DevelopmentSelection(DomainModel):
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    split: V3DatasetSplit
    case_count: int = Field(ge=1)
    assisted_case_ids: tuple[str, ...]
    control_case_ids: tuple[str, ...]


def select_v3_development_cases(
    dataset_path: str | Path,
) -> tuple[tuple[V3AnnotationCase, ...], V3DevelopmentSelection]:
    """Return a development-only workbook and prove no other split escaped."""
    path = Path(dataset_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = tuple(
        case for case in payload["cases"] if case["split"] == V3DatasetSplit.DEVELOPMENT
    )
    if len(cases) != 20:
        raise ValueError("V3.5 requires exactly 20 development cases")
    development_cases = tuple(V3AnnotationCase.model_validate(case) for case in cases)
    if any(case.split is not V3DatasetSplit.DEVELOPMENT for case in development_cases):
        raise ValueError("calibration or held-out case crossed the V3.5 split gate")
    assisted = tuple(
        case.case_id
        for case in development_cases
        if case.annotation
        and case.annotation.gold_label is V3ConstructionGoldLabel.FALLBACK_ELIGIBLE
    )
    controls = tuple(case.case_id for case in development_cases if case.case_id not in assisted)
    return development_cases, V3DevelopmentSelection(
        dataset_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        split=V3DatasetSplit.DEVELOPMENT,
        case_count=len(development_cases),
        assisted_case_ids=assisted,
        control_case_ids=controls,
    )
