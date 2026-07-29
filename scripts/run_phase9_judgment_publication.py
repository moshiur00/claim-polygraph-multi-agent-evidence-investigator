"""Run and hash the zero-cost Stage 9.8 release gate."""

import subprocess
import sys
from pathlib import Path

from claim_polygraph_ng.evaluation.phase9_judgment_publication import (
    Phase9JudgmentPublicationGate,
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
            "tests/integration/test_authoritative_judgment_publication.py",
            "tests/unit/test_full_report_assurance.py",
            "tests/integration/test_authoritative_langgraph.py",
            "-q",
        ],
        cwd=root,
        check=False,
    )
    if test.returncode:
        raise SystemExit(test.returncode)
    gate = Phase9JudgmentPublicationGate(
        proposed_enforced_verdict_separated=True,
        judgment_policy_checkpointed=True,
        sentence_assurance_checkpointed=True,
        bounded_revision_maximum=2,
        readiness_checkpointed=True,
        publication_decision_persisted=True,
        unsupported_critical_assertion_blocked=True,
        public_renderer_fail_closed=True,
        direct_rollback_gated=True,
    )
    export_gate(
        gate,
        root
        / "artifacts/evaluations/"
        "phase9-stage9.8-judgment-publication-v1.json",
    )
    manifest = build_release_manifest(root)
    verification = verify_release_manifest(manifest, root)
    print(
        f"Evaluation: {gate.evaluation_id}\n"
        f"Verdict boundary: "
        f"{'passed' if gate.proposed_enforced_verdict_separated else 'failed'}\n"
        f"Citation revision bound: {gate.bounded_revision_maximum}\n"
        f"Critical assertion blocking: "
        f"{'passed' if gate.unsupported_critical_assertion_blocked else 'failed'}\n"
        f"Direct rollback gate: "
        f"{'passed' if gate.direct_rollback_gated else 'failed'}\n"
        f"Artifacts checked: {verification.checked_artifact_count}\n"
        f"Valid: {'yes' if verification.valid else 'no'}"
    )
    if not verification.valid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
