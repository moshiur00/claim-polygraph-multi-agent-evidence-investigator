"""Stage 7.9 closure manifest tests."""

from claim_polygraph_ng.evaluation.phase7_closure import (
    Phase7ReleaseManifest,
    build_phase7_closure,
    verify_phase7_manifest,
)


def test_approved_human_gate_closes_phase_and_manifest_is_valid(tmp_path) -> None:
    files = (
        "benchmarks/initial_claims_v1.json",
        "benchmarks/phase7_citation_routing_v1.json",
        "artifacts/evaluations/phase7-stage7.1-fixture-graph-v1.json",
        "artifacts/evaluations/phase7-stage7.2-durable-resume-v1.json",
        "artifacts/evaluations/phase7-stage7.3-assurance-routing-v1.json",
        "artifacts/evaluations/phase7-stage7.7-recovery-v1.json",
        "artifacts/evaluations/phase7-stage7.8-frozen-comparison-v1.json",
        "docs/PHASE_7_EXECUTION_PLAN.md",
        "docs/adr/0014-promote-langgraph-as-default-orchestrator.md",
        "docs/PHASE_7_COMPLETION_REPORT.md",
        "src/claim_polygraph_ng/api.py",
        "dashboard/app/page.tsx",
        "tests/security/test_api_security.py",
        "dashboard/tests/accessibility.test.mjs",
    )
    for relative in files:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative, encoding="utf-8")

    calibration, manifest, audit = build_phase7_closure(tmp_path)
    verification = verify_phase7_manifest(manifest, tmp_path)

    assert calibration.targeted_case_ids == ()
    assert calibration.promotion_approval_status == "approved"
    assert calibration.approver_identity == "Md Moshiur Rahman"
    assert calibration.approval_date == "2026-07-28"
    assert verification.valid
    assert verification.checked_artifact_count == 15
    assert audit.engineering_complete
    assert audit.phase_complete
    assert audit.langgraph_default_promoted
    assert audit.pending_count == 0


def test_manifest_detects_tampering(tmp_path) -> None:
    candidate = tmp_path / "artifact.txt"
    candidate.write_text("original", encoding="utf-8")
    manifest = Phase7ReleaseManifest.model_validate(
        {
            "artifacts": [
                {
                    "artifact_id": "artifact",
                    "path": "artifact.txt",
                    "sha256": ("0682c5f2076f099c34a0e268c15c5a3f0367adbec4f6c74a596d7a6c7d5f5f6b"),
                }
            ]
        }
    )
    candidate.write_text("tampered", encoding="utf-8")

    result = verify_phase7_manifest(manifest, tmp_path)
    assert not result.valid
    assert result.errors == ("artifact: SHA-256 mismatch",)
