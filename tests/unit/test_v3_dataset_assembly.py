"""Offline V3.1 repository inventory and insufficiency tests."""

import json
from pathlib import Path

from claim_polygraph_ng.evaluation.v3_dataset_assembly import (
    assemble_public_html_collection_gate,
    assemble_repository_inventory,
)


def test_repository_inventory_reports_honest_frozen_policy_shortfall() -> None:
    root = Path(__file__).parents[2]
    audit = assemble_repository_inventory(root / "benchmarks/initial_claims_v1.json")

    assert audit.candidate_count == 31
    assert audit.eligible_unique_claim_count == 31
    assert audit.eligible_family_count == 20
    assert audit.case_shortfall == 29
    assert audit.family_shortfall == 20
    assert audit.exact_target_met is False
    assert audit.split_assignment_performed is False
    assert audit.model_calls == audit.network_calls == audit.search_calls == 0
    assert all(item.eligible for item in audit.candidates)
    assert all(
        item.annotated_by.casefold() != item.approved_by.casefold()
        for item in audit.candidates
    )


def test_inventory_is_deterministic_and_keeps_origin_families_grouped() -> None:
    root = Path(__file__).parents[2]
    first = assemble_repository_inventory(root / "benchmarks/initial_claims_v1.json")
    second = assemble_repository_inventory(root / "benchmarks/initial_claims_v1.json")

    assert first == second
    for source_case_id in {item.source_case_id for item in first.candidates}:
        family_ids = {
            item.origin_family_id
            for item in first.candidates
            if item.source_case_id == source_case_id
        }
        assert family_ids == {f"initial_claims:{source_case_id}"}


def test_persisted_inventory_gate_matches_computed_inventory() -> None:
    root = Path(__file__).parents[2]
    computed = assemble_repository_inventory(
        root / "benchmarks/initial_claims_v1.json"
    )
    persisted = json.loads(
        (
            root
            / "artifacts/evaluations/"
            "verification-construction-v3-stage1-inventory-gate-audit-v1.json"
        ).read_text(encoding="utf-8")
    )

    assert persisted["inventory"]["eligible_unique_claims"] == (
        computed.eligible_unique_claim_count
    )
    assert persisted["inventory"]["eligible_origin_families"] == (
        computed.eligible_family_count
    )
    assert persisted["inventory"]["case_shortfall"] == computed.case_shortfall
    assert persisted["inventory"]["family_shortfall"] == computed.family_shortfall
    assert persisted["quota_gate_passed"] is computed.exact_target_met
    assert persisted["controls"]["model_calls"] == 0
    assert persisted["controls"]["network_calls"] == 0
    assert persisted["controls"]["search_calls"] == 0


def test_public_html_collection_closes_size_family_and_split_gates() -> None:
    root = Path(__file__).parents[2]
    audit = assemble_public_html_collection_gate(
        root / "benchmarks/initial_claims_v1.json",
        root / "benchmarks/verification_construction_v3_public_html_collection_v1.json",
    )

    assert audit.total_case_count == 60
    assert audit.total_family_count == 40
    assert audit.added_case_count == 29
    assert audit.added_family_count == 20
    assert audit.split_counts == {
        "calibration": 20,
        "development": 20,
        "held_out": 20,
    }
    assert audit.collection_gate_passed is True
    assert audit.annotation_complete is False
    assert audit.dataset_frozen is False
    assert audit.controls["pdf_downloads"] == 0
    assert audit.controls["model_calls"] == 0

    family_splits: dict[str, set[str]] = {}
    for candidate in audit.candidates:
        family_splits.setdefault(candidate.origin_family_id, set()).add(candidate.split)
    assert all(len(splits) == 1 for splits in family_splits.values())


def test_persisted_public_html_gate_matches_computed_gate() -> None:
    root = Path(__file__).parents[2]
    computed = assemble_public_html_collection_gate(
        root / "benchmarks/initial_claims_v1.json",
        root / "benchmarks/verification_construction_v3_public_html_collection_v1.json",
    )
    persisted = json.loads(
        (
            root
            / "artifacts/evaluations/"
            "verification-construction-v3-stage1a-public-html-collection-gate-v1.json"
        ).read_text(encoding="utf-8")
    )

    assert persisted == computed.model_dump(mode="json")
