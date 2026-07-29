"""Stage 10.3 reproducible authenticity and attribution audit tests."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase10_social_attribution import (
    build_phase10_social_attribution_audit,
    verify_phase10_social_attribution_audit,
)


def test_phase10_social_attribution_gate_is_safe_and_complete() -> None:
    root = Path(__file__).parents[2]
    audit = build_phase10_social_attribution_audit(root)

    assert audit.case_count == 6
    assert audit.exact_match_count == 6
    assert audit.decision_counts == {
        "conditional": 2,
        "eligible": 1,
        "ineligible": 3,
    }
    assert audit.copied_material_case_count == 2
    assert audit.unavailable_case_count == 2
    assert audit.verified_archive_case_count == 1
    assert audit.decisive_permission_count == 0
    assert verify_phase10_social_attribution_audit(audit, root) == ()


def test_phase10_social_attribution_gate_detects_tampering(tmp_path: Path) -> None:
    root = Path(__file__).parents[2]
    audit = build_phase10_social_attribution_audit(root)
    copied_root = tmp_path / "project"
    for artifact in audit.artifacts:
        source = root / artifact.path
        target = copied_root / artifact.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    first = copied_root / audit.artifacts[0].path
    first.write_bytes(first.read_bytes() + b"\ntampered")

    assert verify_phase10_social_attribution_audit(audit, copied_root) == (
        f"{audit.artifacts[0].artifact_id}: SHA-256 mismatch",
    )

