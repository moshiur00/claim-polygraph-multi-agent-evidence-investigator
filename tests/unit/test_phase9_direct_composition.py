"""Stage 9.2 operation extraction and direct-composition tests."""

import inspect
from pathlib import Path

from claim_polygraph_ng.application import InvestigationService
from claim_polygraph_ng.evaluation.phase9_direct import (
    build_phase9_direct_release_manifest,
    evaluate_phase9_direct_composition,
    verify_phase9_direct_release_manifest,
)


def test_investigate_is_a_thin_ordered_operation_composition() -> None:
    source = inspect.getsource(InvestigationService.investigate)
    operations = (
        "create_investigation(",
        "normalize_claim(",
        "plan_investigation(",
        "prepare_research_requirements(",
        "execute_research(",
        "consolidate_evidence(",
        "analyze_provenance(",
        "verify_context(",
        "build_argument_ledger(",
        "construct_defender_argument(",
        "construct_challenger_argument(",
        "reconcile_arguments(",
        "draft_verdict(",
        "apply_judgment_policy(",
        "audit_citations(",
        "assess_readiness(",
        "route_review(",
        "finalize_report(",
    )
    positions = [source.index(operation) for operation in operations]
    assert positions == sorted(positions)
    assert "_generate(" not in source
    assert "await self._research(" not in source


def test_three_case_direct_fixture_is_structurally_equivalent(tmp_path) -> None:
    root = Path(__file__).parents[2]
    evaluation = evaluate_phase9_direct_composition(
        project_root=root,
        database_path=tmp_path / "direct.db",
    )

    assert evaluation.case_count == 20
    assert evaluation.completed_count == 20
    assert evaluation.structurally_consistent
    assert evaluation.paid_model_calls == 0
    assert evaluation.live_search_calls == 0
    assert {item.model_calls for item in evaluation.cases} == {7}
    assert {item.search_calls for item in evaluation.cases} == {3}
    assert {item.evidence_count for item in evaluation.cases} == {3}


def test_stage9_2_release_manifest_verifies() -> None:
    root = Path(__file__).parents[2]
    manifest = build_phase9_direct_release_manifest(root)
    result = verify_phase9_direct_release_manifest(manifest, root)

    assert len(manifest.artifacts) == 7
    assert result.valid
