"""Build and verify the offline Phase 6 closure artifacts."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase6_closure import (
    build_closure_audit,
    build_targeted_review,
    export_model,
    load_ablation,
    load_closure_audit,
    verify_closure_audit,
)

ROOT = Path(__file__).parents[1]
EVALUATIONS = ROOT / "artifacts/evaluations"
TARGETED_REVIEW = EVALUATIONS / "phase6-stage6.10-targeted-review-v1.json"
CLOSURE_AUDIT = EVALUATIONS / "phase6-final-release-audit.json"

FROZEN_ARTIFACTS = (
    "artifacts/evaluations/phase6-experiment-manifest-v1.json",
    "artifacts/evaluations/phase6-stage6.0-baseline-v1.json",
    "artifacts/evaluations/phase6-stage6.2-numerical-v1.json",
    "artifacts/evaluations/phase6-stage6.3-temporal-v1.json",
    "artifacts/evaluations/phase6-stage6.8-frozen-ablation-v1.json",
    "artifacts/evaluations/phase6-stage6.10-targeted-review-v1.json",
    "benchmarks/phase6_numerical_operations_v1.json",
    "benchmarks/phase6_temporal_relations_v1.json",
    "docs/adr/0013-phase6-policy-not-promoted.md",
    "docs/PHASE_6_COMPLETION_REPORT.md",
)


def main() -> int:
    ablation = load_ablation(
        EVALUATIONS / "phase6-stage6.8-frozen-ablation-v1.json"
    )
    review = build_targeted_review(ablation)
    export_model(review, TARGETED_REVIEW)
    audit = build_closure_audit(
        project_root=ROOT,
        artifact_paths=FROZEN_ARTIFACTS,
        ablation=ablation,
        targeted_review=review,
    )
    export_model(audit, CLOSURE_AUDIT)
    result = verify_closure_audit(load_closure_audit(CLOSURE_AUDIT), ROOT)
    print(f"Audit: {result.audit_id}")
    print(f"Artifacts checked: {result.checked_artifact_count}")
    print(f"Valid: {result.valid}")
    print(f"Phase complete: {audit.phase_complete}")
    print(f"Policy promoted: {audit.deterministic_policy_promoted}")
    for error in result.errors:
        print(f"Error: {error}")
    return 0 if result.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
