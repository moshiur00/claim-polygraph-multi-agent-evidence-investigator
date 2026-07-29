"""Run and hash the zero-cost Stage 9.9 release gate."""

import subprocess
import sys
from pathlib import Path

from claim_polygraph_ng.evaluation.phase9_human_review import (
    Phase9HumanReviewGate,
    build_release_manifest,
    export_gate,
    verify_release_manifest,
)


def main() -> None:
    root = Path(__file__).parents[1]
    test = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/integration/test_authoritative_human_review.py",
            "tests/integration/test_review_ledger.py",
            "tests/contracts/test_review_contracts.py",
            "-q",
        ],
        cwd=root,
        check=False,
    )
    if test.returncode:
        raise SystemExit(test.returncode)
    gate = Phase9HumanReviewGate(
        same_thread_resume=True,
        approval_path=True,
        revision_path=True,
        more_evidence_path=True,
        rejection_path=True,
        append_only_audit_chain=True,
        distinct_revision_approval=True,
        accepted_decision_idempotent=True,
        conflicting_decision_rejected=True,
        completed_operations_not_replayed=True,
        paid_operations_not_replayed=True,
    )
    export_gate(
        gate,
        root
        / "artifacts/evaluations/"
        "phase9-stage9.9-authoritative-human-review-v1.json",
    )
    manifest = build_release_manifest(root)
    verification = verify_release_manifest(manifest, root)
    print(
        f"Evaluation: {gate.evaluation_id}\n"
        f"Approval: {'passed' if gate.approval_path else 'failed'}\n"
        f"Revision: {'passed' if gate.revision_path else 'failed'}\n"
        f"More evidence: {'passed' if gate.more_evidence_path else 'failed'}\n"
        f"Rejection: {'passed' if gate.rejection_path else 'failed'}\n"
        f"No paid replay: "
        f"{'passed' if gate.paid_operations_not_replayed else 'failed'}\n"
        f"Artifacts checked: {verification.checked_artifact_count}\n"
        f"Valid: {'yes' if verification.valid else 'no'}"
    )
    if not verification.valid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
