"""Stage 10.0 social-evidence baseline and policy tests."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase10_social_baseline import (
    build_phase10_social_baseline,
    load_phase10_social_baseline,
    verify_phase10_social_baseline,
)


def test_repository_phase10_social_baseline_is_complete_and_valid() -> None:
    root = Path(__file__).parents[2]
    manifest = build_phase10_social_baseline(root)
    verification = verify_phase10_social_baseline(manifest, root)

    assert manifest.default_orchestrator == "langgraph"
    assert manifest.authoritative_domain_service == "InvestigationService"
    assert manifest.rollback_path == "direct"
    assert manifest.adr_status == "proposed"
    assert all(value == 0 for value in manifest.resource_policy.model_dump().values())
    assert len(manifest.observations) == 7
    assert len(manifest.policy_matrix) == 8
    assert len(manifest.non_negotiable_safeguards) == 7
    assert verification.valid
    assert verification.checked_artifact_count == 12


def test_policy_prevents_social_repetition_from_becoming_proof() -> None:
    root = Path(__file__).parents[2]
    manifest = build_phase10_social_baseline(root)
    rules = {item.material_type: item for item in manifest.policy_matrix}

    assert not rules["unknown_individual_post"].independent_proof
    assert not rules["repost_quote_or_screenshot"].independent_proof
    assert not rules["post_linking_report"].independent_proof
    assert "share_evidence_family" in rules["post_linking_report"].required_controls
    assert any(
        "Cross-platform repetition" in safeguard
        for safeguard in manifest.non_negotiable_safeguards
    )


def test_manifest_round_trip_and_hash_tamper_detection(tmp_path: Path) -> None:
    root = Path(__file__).parents[2]
    manifest = build_phase10_social_baseline(root)
    loaded = load_phase10_social_baseline(
        root
        / "artifacts/evaluations/phase10-stage10.0-social-evidence-baseline-v1.json"
    )
    assert loaded == manifest

    copied_root = tmp_path / "project"
    for artifact in manifest.artifacts:
        source = root / artifact.path
        target = copied_root / artifact.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    assert verify_phase10_social_baseline(manifest, copied_root).valid

    first = copied_root / manifest.artifacts[0].path
    first.write_bytes(first.read_bytes() + b"\ntampered")
    result = verify_phase10_social_baseline(manifest, copied_root)
    assert not result.valid
    assert result.errors == (f"{manifest.artifacts[0].artifact_id}: SHA-256 mismatch",)

