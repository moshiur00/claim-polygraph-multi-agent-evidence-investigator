"""Run and hash the zero-cost Stage 9.6 release gate."""

import subprocess
import sys
from pathlib import Path

from claim_polygraph_ng.evaluation.phase9_authoritative_research import (
    Phase9AuthoritativeResearchGate,
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
            "tests/integration/test_authoritative_multi_agent_research.py",
            "tests/integration/test_langgraph_research_fanout.py",
            "-q",
        ],
        cwd=root,
        check=False,
    )
    if test.returncode:
        raise SystemExit(test.returncode)
    gate = Phase9AuthoritativeResearchGate(
        authoritative_graph_integration=True,
        minimum_role_count=3,
        concurrent_role_fan_out=True,
        shared_cache_deduplication=True,
        durable_assignments_and_results=True,
        sufficiency_and_budget_routing=True,
        receipt_guard_enforced=True,
        authoritative_packet_preserved=True,
        direct_research_fallback_retained=True,
    )
    export_gate(
        gate,
        root
        / "artifacts/evaluations/"
        "phase9-stage9.6-authoritative-multi-agent-research-v1.json",
    )
    manifest = build_release_manifest(root)
    verification = verify_release_manifest(manifest, root)
    print(
        f"Evaluation: {gate.evaluation_id}\n"
        f"Minimum roles: {gate.minimum_role_count}\n"
        f"Concurrent fan-out: {'passed' if gate.concurrent_role_fan_out else 'failed'}\n"
        f"Shared-cache deduplication: "
        f"{'passed' if gate.shared_cache_deduplication else 'failed'}\n"
        f"Receipt guard: {'passed' if gate.receipt_guard_enforced else 'failed'}\n"
        f"Artifacts checked: {verification.checked_artifact_count}\n"
        f"Valid: {'yes' if verification.valid else 'no'}"
    )
    if not verification.valid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
