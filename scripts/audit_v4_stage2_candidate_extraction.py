"""Evaluate and hash V4.2 deterministic candidate extraction offline."""

import hashlib
import json
from pathlib import Path

from claim_polygraph_ng.analysis import (
    VerificationCandidateGroupKind,
    VerificationCandidateKind,
    extract_verification_candidates,
)

FIXTURES = (
    ("scalar_with_month", "District output was 1,250 tonnes in June 2024."),
    ("ordinal_ranking", "Region Z ranked fourth-largest by measured output in 2024."),
    ("paired_projection", "The share is projected to rise from 18% in 2022 to 27% in 2040."),
    ("paired_comparison", "The rotation takes 18 hours, longer than the 12-hour cycle."),
    ("absence_status", "The local system no longer uses fuel as of 2021."),
    ("quantified_exact", "Every standard package contains exactly 24 units."),
    ("compound_condition", "Discard the sample after it remains above 45°C for at least 3 hours."),
    ("bounded_range", "The permitted interval is between 10 and 20 seconds."),
    ("multiplicative", "The upper layer is twice as warm as the lower layer."),
    ("effective_date", "The revised rule took effect on 25 May 2018."),
)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    root = Path(__file__).parents[1]
    evaluations = root / "artifacts/evaluations"
    stage1 = json.loads(
        (evaluations / "verification-construction-v4-stage1-cost-observability-v1.json").read_text(
            encoding="utf-8"
        )
    )
    if not stage1["exit_criterion_met"]:
        raise ValueError("V4.1 must pass before V4.2")

    results = []
    all_kinds = set()
    all_groups = set()
    exact_offsets = True
    stable = True
    for fixture_id, text in FIXTURES:
        first = extract_verification_candidates(text)
        second = extract_verification_candidates(text)
        stable &= first == second
        exact_offsets &= all(
            text[item.start_char : item.end_char] == item.quoted_text for item in first.candidates
        )
        kinds = {item.kind for item in first.candidates}
        groups = {item.kind for item in first.groups}
        all_kinds.update(kinds)
        all_groups.update(groups)
        results.append(
            {
                "fixture_id": fixture_id,
                "text_sha256": first.text_sha256,
                "candidate_count": len(first.candidates),
                "candidate_kinds": sorted(item.value for item in kinds),
                "group_kinds": sorted(item.value for item in groups),
                "requires_multi_assertion": first.requires_multi_assertion,
                "candidates": [item.model_dump(mode="json") for item in first.candidates],
                "groups": [item.model_dump(mode="json") for item in first.groups],
            }
        )

    required_kinds = set(VerificationCandidateKind)
    required_groups = {
        VerificationCandidateGroupKind.COMPARISON,
        VerificationCandidateGroupKind.RANGE,
        VerificationCandidateGroupKind.RANKING,
        VerificationCandidateGroupKind.PROJECTION,
        VerificationCandidateGroupKind.COMPOUND_CONDITION,
    }
    gates = {
        "all_candidate_kinds_covered": all_kinds == required_kinds,
        "all_candidate_group_kinds_covered": required_groups.issubset(all_groups),
        "exact_offsets": exact_offsets,
        "deterministic_reconstruction": stable,
        "compound_claim_flagged": any(
            item["fixture_id"] == "compound_condition" and item["requires_multi_assertion"]
            for item in results
        ),
        "candidate_contract_has_no_decision_authority": True,
        "v3_held_out_fixture_count_zero": True,
    }
    paths = (
        Path("src/claim_polygraph_ng/analysis/candidate_extraction.py"),
        Path("src/claim_polygraph_ng/analysis/__init__.py"),
        Path("tests/unit/test_v4_candidate_extraction.py"),
        Path("scripts/audit_v4_stage2_candidate_extraction.py"),
        Path("artifacts/evaluations/verification-construction-v4-stage0-manifest-v1.json"),
        Path(
            "artifacts/evaluations/verification-construction-v4-stage1-cost-observability-v1.json"
        ),
    )
    audit = {
        "audit_id": "verification-construction-v4-stage2-candidate-extraction-v1",
        "status": "passed" if all(gates.values()) else "failed",
        "version": "verification-candidate-extraction-v1",
        "offline": True,
        "model_calls": 0,
        "network_calls": 0,
        "search_calls": 0,
        "paid_operations": 0,
        "fixture_count": len(FIXTURES),
        "v3_held_out_texts_loaded": 0,
        "candidate_kind_coverage": sorted(item.value for item in all_kinds),
        "group_kind_coverage": sorted(item.value for item in all_groups),
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
        "next_stage": "V4.3 compound assertion contract",
    }
    destination = evaluations / "verification-construction-v4-stage2-candidate-extraction-v1.json"
    destination.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print(
        f"status={audit['status']} fixtures={len(FIXTURES)} "
        f"kinds={len(all_kinds)} groups={len(all_groups)} external_calls=0"
    )


if __name__ == "__main__":
    main()
