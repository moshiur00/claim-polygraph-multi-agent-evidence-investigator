"""Stage 10.4 reproducible original-source resolution audit tests."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase10_original_source_resolution import (
    build_phase10_original_source_audit,
    verify_phase10_original_source_audit,
)


def test_phase10_original_source_gate_is_complete_and_zero_network() -> None:
    root = Path(__file__).parents[2]
    audit = build_phase10_original_source_audit(root)

    assert audit.case_count == 4
    assert audit.exact_preflight_count == 4
    assert audit.allowed_count == 1
    assert audit.blocked_count == 3
    assert audit.resolved_pair_family_count == 1
    assert audit.resolved_pair_grouping_reason == "resolved_original_source"
    assert audit.network_calls == 0
    assert verify_phase10_original_source_audit(audit, root) == ()


def test_phase10_original_source_gate_detects_hash_tampering(
    tmp_path: Path,
) -> None:
    root = Path(__file__).parents[2]
    audit = build_phase10_original_source_audit(root)
    copied_root = tmp_path / "project"
    for artifact in audit.artifacts:
        source = root / artifact.path
        target = copied_root / artifact.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    first = copied_root / audit.artifacts[0].path
    first.write_bytes(first.read_bytes() + b"\ntampered")

    assert verify_phase10_original_source_audit(audit, copied_root) == (
        f"{audit.artifacts[0].artifact_id}: SHA-256 mismatch",
    )

