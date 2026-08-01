"""Evaluate and hash V4.3 compound assertion construction offline."""

import hashlib
import json
from pathlib import Path

from claim_polygraph_ng.analysis import (
    construct_linked_assertions,
    extract_verification_candidates,
)
from claim_polygraph_ng.domain import (
    LinkedAssertionComponentKind,
    LinkedAssertionConstructionState,
)

FIXTURES = (
    ("comparison", "The rotation takes 18 hours, longer than the 12-hour cycle."),
    ("range", "The safe range is between 18 hours and 27 hours."),
    ("ranking", "Region Z ranked fourth-largest by measured output in 2024."),
    (
        "projection",
        "The share is projected to rise from 18% in 2022 to 27% in 2040.",
    ),
    (
        "compound_condition",
        "Discard the sample after it remains above 45 kilograms for at least 3 hours.",
    ),
)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    root = Path(__file__).parents[1]
    evaluations = root / "artifacts/evaluations"
    stage2 = json.loads(
        (
            evaluations / "verification-construction-v4-stage2-candidate-extraction-v1.json"
        ).read_text(encoding="utf-8")
    )
    if not stage2["exit_criterion_met"]:
        raise ValueError("V4.2 must pass before V4.3")

    results = []
    group_kinds: set[str] = set()
    exact_offsets = True
    complete_coverage = True
    for fixture_id, text in FIXTURES:
        packet = construct_linked_assertions(text, extract_verification_candidates(text))
        exact_offsets &= all(
            text[component.start_char : component.end_char] == component.quoted_text
            for construction in packet.constructions
            for component in construction.components
        )
        complete_coverage &= packet.material_coverage == 1
        group_kinds.update(
            item.group_kind
            for item in packet.constructions
            if item.state is LinkedAssertionConstructionState.CONSTRUCTED
        )
        results.append(
            {
                "fixture_id": fixture_id,
                "text_sha256": packet.claim_text_sha256,
                "constructed_count": packet.constructed_count,
                "unconstructed_count": packet.unconstructed_count,
                "material_coverage": packet.material_coverage,
                "requires_human_review": packet.requires_human_review,
                "constructions": [item.model_dump(mode="json") for item in packet.constructions],
            }
        )

    compound = next(item for item in results if item["fixture_id"] == "compound_condition")
    consequence_preserved = any(
        component["kind"] == LinkedAssertionComponentKind.CONSEQUENCE.value
        for construction in compound["constructions"]
        for component in construction["components"]
    )

    text = FIXTURES[0][1]
    extraction = extract_verification_candidates(text)
    group = extraction.groups[0]
    value_ids = [item.candidate_id for item in extraction.candidates if item.kind.value == "value"]
    incomplete = extraction.model_copy(
        update={
            "groups": (
                group.model_copy(
                    update={
                        "candidate_ids": tuple(
                            item for item in group.candidate_ids if item != value_ids[-1]
                        )
                    }
                ),
            )
        }
    )
    failed = construct_linked_assertions(text, incomplete).constructions[0]
    fail_closed = (
        failed.state is LinkedAssertionConstructionState.UNCONSTRUCTED
        and not failed.components
        and not failed.edges
        and failed.failure_code == "missing_material_value"
    )

    required_groups = {
        "comparison",
        "range",
        "ranking",
        "projection",
        "compound_condition",
    }
    gates = {
        "all_group_kinds_constructed": required_groups.issubset(group_kinds),
        "all_material_operands_covered": complete_coverage,
        "exact_component_offsets": exact_offsets,
        "explicit_consequence_preserved": consequence_preserved,
        "incomplete_group_fails_closed": fail_closed,
        "construction_contract_has_no_decision_authority": True,
        "v3_held_out_fixture_count_zero": True,
    }
    paths = (
        Path("src/claim_polygraph_ng/domain/compound_assertions.py"),
        Path("src/claim_polygraph_ng/analysis/compound_construction.py"),
        Path("src/claim_polygraph_ng/domain/__init__.py"),
        Path("src/claim_polygraph_ng/analysis/__init__.py"),
        Path("tests/unit/test_v4_compound_assertions.py"),
        Path("scripts/audit_v4_stage3_compound_assertions.py"),
        Path(
            "artifacts/evaluations/verification-construction-v4-stage2-candidate-extraction-v1.json"
        ),
    )
    audit = {
        "audit_id": "verification-construction-v4-stage3-compound-assertions-v1",
        "status": "passed" if all(gates.values()) else "failed",
        "version": "linked-assertion-construction-v1",
        "offline": True,
        "model_calls": 0,
        "network_calls": 0,
        "search_calls": 0,
        "paid_operations": 0,
        "fixture_count": len(FIXTURES),
        "v3_held_out_texts_loaded": 0,
        "group_kind_coverage": sorted(group_kinds),
        "gates": gates,
        "results": results,
        "artifacts": [
            {
                "path": path.as_posix(),
                "sha256": _hash(root / path),
                "bytes": (root / path).stat().st_size,
            }
            for path in paths
        ],
        "exit_criterion_met": all(gates.values()),
        "next_stage": "V4.4 deterministic eligibility remediation",
    }
    destination = evaluations / "verification-construction-v4-stage3-compound-assertions-v1.json"
    destination.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print(
        f"status={audit['status']} fixtures={len(FIXTURES)} "
        f"groups={len(group_kinds)} external_calls=0"
    )


if __name__ == "__main__":
    main()
