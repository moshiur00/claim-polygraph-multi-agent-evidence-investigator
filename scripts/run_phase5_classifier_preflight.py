"""Run the zero-cost Stage 5.7 schema and selection preflight."""

import json
from pathlib import Path

from claim_polygraph_ng.evaluation.phase5_ambiguous_classifier import (
    build_classifier_preflight,
    export_ambiguous_classifier_artifact,
)
from claim_polygraph_ng.evaluation.phase5_evidence_families import (
    EvidenceFamilyEvaluation,
)

ROOT = Path(__file__).parents[1]


def main() -> int:
    baseline = EvidenceFamilyEvaluation.model_validate(
        json.loads(
            (ROOT / "artifacts/evaluations/phase5-stage5.6-evidence-families.json").read_text(
                encoding="utf-8"
            )
        )
    )
    result = build_classifier_preflight(baseline)
    output = export_ambiguous_classifier_artifact(
        result, ROOT / "artifacts/evaluations/phase5-stage5.7-preflight.json"
    )
    print(f"Eligible: {result.eligible_case_ids}")
    print(f"Maximum calls: {result.maximum_model_calls}")
    print(f"Maximum cost: ${result.maximum_cost_usd:.4f}")
    print(f"Valid: {result.valid}")
    print(f"Artifact: {output}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
