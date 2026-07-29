"""Run and hash the zero-cost Stage 9.7 release gate."""

import subprocess
import sys
from pathlib import Path

from claim_polygraph_ng.evaluation.phase9_verification_arguments import (
    Phase9VerificationArgumentGate,
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
            "tests/integration/test_authoritative_verification_arguments.py",
            "tests/integration/test_langgraph_adversarial_argument.py",
            "tests/integration/test_authoritative_langgraph.py",
            "-q",
        ],
        cwd=root,
        check=False,
    )
    if test.returncode:
        raise SystemExit(test.returncode)
    gate = Phase9VerificationArgumentGate(
        verification_branch_count=4,
        verification_concurrent=True,
        sequential_equivalence=True,
        approved_packet_isolated=True,
        defender_challenger_concurrent=True,
        defender_challenger_independent=True,
        deterministic_reconciliation=True,
        replay_without_role_execution=True,
        direct_fallback_retained=True,
    )
    export_gate(
        gate,
        root
        / "artifacts/evaluations/"
        "phase9-stage9.7-verification-arguments-v1.json",
    )
    manifest = build_release_manifest(root)
    verification = verify_release_manifest(manifest, root)
    print(
        f"Evaluation: {gate.evaluation_id}\n"
        f"Verification branches: {gate.verification_branch_count}\n"
        f"Concurrent verification: "
        f"{'passed' if gate.verification_concurrent else 'failed'}\n"
        f"Sequential equivalence: "
        f"{'passed' if gate.sequential_equivalence else 'failed'}\n"
        f"Argument isolation: "
        f"{'passed' if gate.defender_challenger_independent else 'failed'}\n"
        f"Artifacts checked: {verification.checked_artifact_count}\n"
        f"Valid: {'yes' if verification.valid else 'no'}"
    )
    if not verification.valid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
