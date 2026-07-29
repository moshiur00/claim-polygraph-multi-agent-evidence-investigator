"""Stage 10.2 reproducible normalization-gate tests."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase10_social_normalization import (
    build_phase10_social_normalization_audit,
    verify_phase10_social_normalization_audit,
)


def test_phase10_social_normalization_gate_is_complete_and_zero_network() -> None:
    root = Path(__file__).parents[2]
    audit = build_phase10_social_normalization_audit(root)

    assert audit.case_count == 15
    assert audit.exact_match_count == 15
    assert audit.social_case_count == 13
    assert audit.non_social_case_count == 2
    assert audit.platform_count == 10
    assert audit.unknown_social_path_count == 1
    assert audit.social_page_fetches == 0
    assert verify_phase10_social_normalization_audit(audit, root) == ()


def test_phase10_social_normalization_gate_detects_hash_tampering(
    tmp_path: Path,
) -> None:
    root = Path(__file__).parents[2]
    audit = build_phase10_social_normalization_audit(root)
    copied_root = tmp_path / "project"
    for artifact in audit.artifacts:
        source = root / artifact.path
        target = copied_root / artifact.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    first = copied_root / audit.artifacts[0].path
    first.write_bytes(first.read_bytes() + b"\ntampered")

    assert verify_phase10_social_normalization_audit(audit, copied_root) == (
        f"{audit.artifacts[0].artifact_id}: SHA-256 mismatch",
    )

