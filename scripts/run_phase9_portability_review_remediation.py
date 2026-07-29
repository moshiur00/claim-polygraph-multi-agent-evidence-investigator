"""Validate and hash the Stage 9.12b portability and review-routing repair."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from claim_polygraph_ng.evaluation.phase5_manifest import (
    load_phase5_manifest,
    verify_phase5_manifest,
)
from claim_polygraph_ng.evaluation.phase6_closure import (
    load_closure_audit,
    verify_closure_audit,
)

root = Path(__file__).resolve().parents[1]
phase5 = verify_phase5_manifest(
    load_phase5_manifest(
        root / "artifacts/evaluations/phase5-source-intelligence-manifest-v1.json"
    ),
    root,
)
phase6 = verify_closure_audit(
    load_closure_audit(
        root / "artifacts/evaluations/phase6-final-release-audit.json"
    ),
    root,
)
comparison = json.loads(
    (
        root / "artifacts/evaluations/phase9-stage9.12-frozen-comparison-v1.json"
    ).read_text(encoding="utf-8")
)
checks = {
    "phase5_historical_manifest_valid": phase5.valid,
    "phase6_historical_audit_valid": phase6.valid,
    "review_routing_recall_is_100_percent": (
        comparison["unified"]["review_routing_recall"] == 1
    ),
    "all_stage9_comparison_gates_pass": comparison["mandatory_gates_passed"],
    "verdict_equivalence_is_100_percent": (
        comparison["unified"]["direct_verdict_equivalence"] == 1
    ),
    "challenger_gain_is_preserved": (
        comparison["challenger_material_gain_cases"] > 0
    ),
}
result = {
    "evaluation_id": "phase9-stage9.12b-portability-review-remediation-v1",
    "generated_at": datetime.now(UTC).isoformat(),
    "checks": checks,
    "valid": all(checks.values()),
    "phase5_errors": phase5.errors,
    "phase6_errors": phase6.errors,
    "review_routing_recall": comparison["unified"]["review_routing_recall"],
    "recommended_disposition": comparison["recommended_disposition"],
    "external_model_calls": 0,
    "live_search_calls": 0,
    "network_fetches": 0,
    "pdf_downloads": 0,
}
result_path = (
    root
    / "artifacts/evaluations/phase9-stage9.12b-portability-review-remediation-v1.json"
)
result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

paths = (
    ".gitattributes",
    "src/claim_polygraph_ng/evaluation/artifact_hashing.py",
    "src/claim_polygraph_ng/evaluation/phase5_manifest.py",
    "src/claim_polygraph_ng/evaluation/phase6_closure.py",
    "src/claim_polygraph_ng/application/investigation_service.py",
    "src/claim_polygraph_ng/application/langgraph_authoritative.py",
    "src/claim_polygraph_ng/domain/investigation.py",
    "tests/unit/test_artifact_hashing.py",
    "tests/unit/test_review_routing.py",
    "tests/integration/test_authoritative_langgraph.py",
    "tests/integration/test_phase9_comparison.py",
    "scripts/run_phase9_portability_review_remediation.py",
    "docs/PHASE_9_STAGE_9.12B_COMPLETION_REPORT.md",
    "artifacts/evaluations/phase9-stage9.12-frozen-comparison-v1.json",
    "artifacts/evaluations/phase9-stage9.12b-portability-review-remediation-v1.json",
)
manifest = {
    "manifest_id": "phase9-stage9.12b-release-manifest-v1",
    "generated_at": datetime.now(UTC).isoformat(),
    "artifacts": [
        {
            "path": path,
            "sha256": hashlib.sha256((root / path).read_bytes()).hexdigest(),
        }
        for path in paths
    ],
}
(root / "artifacts/evaluations/phase9-stage9.12b-release-manifest-v1.json").write_text(
    json.dumps(manifest, indent=2) + "\n",
    encoding="utf-8",
)

print(f"Phase 5 valid: {'yes' if phase5.valid else 'no'}")
print(f"Phase 6 valid: {'yes' if phase6.valid else 'no'}")
print(
    "Review-routing recall: "
    f"{comparison['unified']['review_routing_recall']:.1%}"
)
print(f"Disposition: {comparison['recommended_disposition']}")
print(f"Valid: {'yes' if result['valid'] else 'no'}")
raise SystemExit(0 if result["valid"] else 1)
