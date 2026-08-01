"""Run and persist the offline V3.3 deterministic baseline."""

import hashlib
import json
from pathlib import Path

from claim_polygraph_ng.evaluation.v3_deterministic_baseline import (
    run_v3_deterministic_baseline,
)


def main() -> None:
    root = Path(__file__).parents[1]
    workbook = (
        root / "benchmarks/verification_construction_v3_approved_frozen_v2.json"
    )
    result = run_v3_deterministic_baseline(workbook, project_root=root)
    result_path = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage3-deterministic-baseline-v1.json"
    )
    result_path.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    audit = {
        "audit_id": "verification-construction-v3-stage3-baseline-audit-v1",
        "status": "passed",
        "baseline_path": result_path.relative_to(root).as_posix(),
        "baseline_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
        "dataset_path": result.dataset_path,
        "dataset_sha256": hashlib.sha256(workbook.read_bytes()).hexdigest(),
        "controls": result.controls,
        "baseline_is_promotion_candidate": False,
        "reason": (
            "V3.3 establishes the pre-assisted reference point. Promotion is decided "
            "only after development, calibration, held-out evaluation and adjudication."
        ),
    }
    audit_path = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage3-baseline-audit-v1.json"
    )
    audit_path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(result_path.relative_to(root))
    print(audit_path.relative_to(root))
    print(
        f"cases={result.case_count} recall={result.construction_recall:.1%} "
        f"unsafe={result.unsafe_accepted_constructions} "
        f"review_routing={result.human_review_routing_recall:.1%}"
    )


if __name__ == "__main__":
    main()
