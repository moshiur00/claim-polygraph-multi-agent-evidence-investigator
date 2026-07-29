"""Stage 9.0 baseline and compatibility-contract tests."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase9_baseline import (
    build_phase9_baseline,
    load_phase9_baseline,
    verify_phase9_baseline,
)


def test_repository_phase9_baseline_is_complete_and_valid() -> None:
    root = Path(__file__).parents[2]
    manifest = build_phase9_baseline(root)
    verification = verify_phase9_baseline(manifest, root)

    assert manifest.case_count == 20
    assert {case.case_id for case in manifest.cases} == {
        f"CPNG-{number:03d}" for number in range(1, 21)
    }
    assert all(case.annotation_status == "reviewed" for case in manifest.cases)
    assert manifest.authoritative_domain_service == "InvestigationService"
    assert manifest.default_orchestrator == "langgraph"
    assert manifest.rollback_path == "direct"
    assert manifest.resource_policy.model_calls == 0
    assert len(manifest.responsibilities) == 11
    assert len(manifest.compatibility_contracts) == 6
    assert verification.valid
    assert verification.checked_artifact_count == 15


def test_manifest_round_trip_and_hash_tamper_detection(tmp_path) -> None:
    root = Path(__file__).parents[2]
    manifest = build_phase9_baseline(root)
    loaded = load_phase9_baseline(
        root / "artifacts/evaluations/phase9-stage9.0-baseline-v1.json"
    )
    assert loaded == manifest

    copied_root = tmp_path / "project"
    for artifact in manifest.artifacts:
        source = root / artifact.path
        target = copied_root / artifact.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    assert verify_phase9_baseline(manifest, copied_root).valid

    first = copied_root / manifest.artifacts[0].path
    first.write_bytes(first.read_bytes() + b"\ntampered")
    result = verify_phase9_baseline(manifest, copied_root)
    assert not result.valid
    assert result.errors == (f"{manifest.artifacts[0].artifact_id}: SHA-256 mismatch",)
