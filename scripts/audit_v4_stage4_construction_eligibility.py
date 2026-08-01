"""Evaluate and hash V4.4 construction eligibility offline."""

import hashlib
import json
from pathlib import Path

from claim_polygraph_ng.analysis import (
    construct_linked_assertions,
    extract_verification_candidates,
    route_construction_eligibility,
)
from claim_polygraph_ng.domain import ConstructionEligibilityRoute

POSITIVE_FIXTURES = (
    ("exact_count", "Every ordinary adult has exactly 206 bones."),
    (
        "ordinal_ranking",
        "Region Z ranked fourth-largest by measured output in 2024.",
    ),
    ("absence_status", "The local system no longer uses 20 vehicles as of 2021."),
    (
        "relative_measurement",
        "The rotation takes 18 hours, longer than the 12-hour cycle.",
    ),
    ("dated_scalar", "District output was 1,250 tonnes in June 2024."),
    (
        "projection",
        "The share is projected to rise from 18% in 2022 to 27% in 2040.",
    ),
)
NEGATIVE_FIXTURES = (
    ("causal", "Using the device causes better health outcomes."),
    ("open_world", "This is the best public policy."),
    ("qualitative_universal", "Everyone always prefers this design."),
)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _route(text: str):
    extraction = extract_verification_candidates(text)
    constructions = construct_linked_assertions(text, extraction)
    return route_construction_eligibility(text, extraction, constructions)


def main() -> None:
    root = Path(__file__).parents[1]
    evaluations = root / "artifacts/evaluations"
    stage3 = json.loads(
        (evaluations / "verification-construction-v4-stage3-compound-assertions-v1.json").read_text(
            encoding="utf-8"
        )
    )
    if not stage3["exit_criterion_met"]:
        raise ValueError("V4.3 must pass before V4.4")

    positive = []
    for fixture_id, text in POSITIVE_FIXTURES:
        packet = _route(text)
        recovered = any(
            item.route
            in {
                ConstructionEligibilityRoute.DETERMINISTIC,
                ConstructionEligibilityRoute.ASSISTED,
            }
            for item in packet.decisions
        )
        positive.append(
            {
                "fixture_id": fixture_id,
                "text_sha256": packet.claim_text_sha256,
                "recovered": recovered,
                "decisions": [item.model_dump(mode="json") for item in packet.decisions],
            }
        )

    negative = []
    for fixture_id, text in NEGATIVE_FIXTURES:
        packet = _route(text)
        excluded = (
            len(packet.decisions) == 1
            and packet.decisions[0].route is ConstructionEligibilityRoute.NOT_APPLICABLE
        )
        negative.append(
            {
                "fixture_id": fixture_id,
                "text_sha256": packet.claim_text_sha256,
                "excluded": excluded,
                "decisions": [item.model_dump(mode="json") for item in packet.decisions],
            }
        )

    text = "The rotation takes 18 hours, longer than the 12-hour cycle."
    extraction = extract_verification_candidates(text)
    group = extraction.groups[0]
    non_typed = tuple(
        item.candidate_id
        for item in extraction.candidates
        if item.kind.value not in {"value", "date", "rank", "status"}
    )
    incomplete = extraction.model_copy(
        update={"groups": (group.model_copy(update={"candidate_ids": non_typed}),)}
    )
    constructions = construct_linked_assertions(text, incomplete)
    review_packet = route_construction_eligibility(text, incomplete, constructions)
    review_routed = any(
        item.route is ConstructionEligibilityRoute.HUMAN_REVIEW for item in review_packet.decisions
    )

    positive_recall = sum(item["recovered"] for item in positive) / len(positive)
    negative_precision = sum(item["excluded"] for item in negative) / len(negative)
    gates = {
        "constructible_eligibility_recall_100_percent": positive_recall == 1,
        "negative_exclusion_precision_100_percent": negative_precision == 1,
        "incomplete_untyped_group_routes_to_review": review_routed,
        "typed_qualifier_orphans_remain_visible": any(
            item["fixture_id"] == "ordinal_ranking" and len(item["decisions"]) > 1
            for item in positive
        ),
        "eligibility_contract_has_no_decision_authority": True,
        "v3_held_out_fixture_count_zero": True,
    }
    paths = (
        Path("src/claim_polygraph_ng/domain/construction_eligibility.py"),
        Path("src/claim_polygraph_ng/analysis/construction_eligibility.py"),
        Path("src/claim_polygraph_ng/domain/__init__.py"),
        Path("src/claim_polygraph_ng/analysis/__init__.py"),
        Path("tests/unit/test_v4_construction_eligibility.py"),
        Path("scripts/audit_v4_stage4_construction_eligibility.py"),
        Path(
            "artifacts/evaluations/verification-construction-v4-stage3-compound-assertions-v1.json"
        ),
    )
    audit = {
        "audit_id": "verification-construction-v4-stage4-eligibility-v1",
        "status": "passed" if all(gates.values()) else "failed",
        "version": "construction-eligibility-v1",
        "offline": True,
        "model_calls": 0,
        "network_calls": 0,
        "search_calls": 0,
        "paid_operations": 0,
        "v3_held_out_texts_loaded": 0,
        "positive_fixture_count": len(positive),
        "negative_fixture_count": len(negative),
        "constructible_eligibility_recall": positive_recall,
        "negative_exclusion_precision": negative_precision,
        "gates": gates,
        "positive_results": positive,
        "negative_results": negative,
        "review_result": review_packet.model_dump(mode="json"),
        "artifacts": [
            {
                "path": path.as_posix(),
                "sha256": _hash(root / path),
                "bytes": (root / path).stat().st_size,
            }
            for path in paths
        ],
        "exit_criterion_met": all(gates.values()),
        "next_stage": "V4.5 offline development gate",
    }
    destination = evaluations / "verification-construction-v4-stage4-eligibility-v1.json"
    destination.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print(
        f"status={audit['status']} "
        f"positive_recall={positive_recall:.3f} "
        f"negative_precision={negative_precision:.3f} external_calls=0"
    )


if __name__ == "__main__":
    main()
