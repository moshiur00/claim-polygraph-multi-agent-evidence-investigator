"""Run, export and hash the Stage 9.12 frozen comparison."""

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from claim_polygraph_ng.evaluation.phase9_comparison import (
    build_release_manifest,
    evaluate_phase9_comparison,
    export_evaluation,
    verify_release_manifest,
)

root = Path(__file__).resolve().parents[1]
with TemporaryDirectory(prefix="claim-polygraph-phase9.12-") as directory:
    evaluation = asyncio.run(evaluate_phase9_comparison(root, directory))
export_evaluation(
    evaluation,
    root / "artifacts/evaluations/phase9-stage9.12-frozen-comparison-v1.json",
)
manifest = build_release_manifest(root)
verification = verify_release_manifest(manifest, root)
print(f"Evaluation: {evaluation.evaluation_id}")
print(f"Cases: {evaluation.case_count}")
print(f"Direct equivalence: {evaluation.unified.direct_verdict_equivalence:.1%}")
print(f"Unified evidence coverage: {evaluation.unified.mean_evidence_coverage_ratio:.1%}")
print(f"Challenger material-gain cases: {evaluation.challenger_material_gain_cases}")
print(f"Duplicate paid operations: {evaluation.unified.duplicate_paid_operations}")
print(f"Disposition: {evaluation.recommended_disposition}")
print(f"Artifacts checked: {verification.checked_artifact_count}")
print(f"Valid: {'yes' if verification.valid else 'no'}")
raise SystemExit(0 if verification.valid else 1)
