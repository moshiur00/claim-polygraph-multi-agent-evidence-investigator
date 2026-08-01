"""Build the zero-model-call V3.2 reviewer workbook and gate audit."""

import json
from pathlib import Path

from claim_polygraph_ng.evaluation.v3_annotation import (
    V3AnnotationCase,
    V3AnnotationWorkbook,
    V3EvidenceSpan,
    V3ExactTextSpan,
    V3MachinePreparedProposal,
    V3ReviewEvidence,
    audit_annotation_workbook,
    load_sampling_quotas,
)


def main() -> None:
    root = Path(__file__).parents[1]
    initial = _read(root / "benchmarks/initial_claims_v1.json")
    public = _read(
        root / "benchmarks/verification_construction_v3_public_html_collection_v1.json"
    )
    collection_gate = _read(
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage1a-public-html-collection-gate-v1.json"
    )
    split_by_candidate = {
        item["candidate_id"]: item["split"]
        for item in collection_gate["candidates"]
    }
    source_candidates = [
        *_local_candidates(initial),
        *_public_candidates(public),
    ]
    cases = []
    for sequence, candidate in enumerate(source_candidates, start=1):
        claim = candidate["claim_text"]
        evidence = tuple(candidate["evidence"])
        cases.append(
            V3AnnotationCase(
                case_id=f"V3-{sequence:03d}",
                source_candidate_id=candidate["candidate_id"],
                split=split_by_candidate[candidate["candidate_id"]],
                origin_family_id=candidate["origin_family_id"],
                claim_text=claim,
                evidence=evidence,
                proposal=V3MachinePreparedProposal(
                    dimension_bucket=candidate.get("dimension"),
                    comparator_or_relation=_relation_hint(claim),
                    claim_span=V3ExactTextSpan(
                        start_char=0,
                        end_char=len(claim),
                        quoted_text=claim,
                    ),
                    evidence_spans=tuple(
                        V3EvidenceSpan(
                            evidence_id=item.evidence_id,
                            start_char=0,
                            end_char=len(item.passage),
                            quoted_text=item.passage,
                        )
                        for item in evidence
                    ),
                    machine_notes=(
                        "Full-span candidates are navigation aids, not human gold.",
                        "Annotator must narrow spans to the material operands and relation.",
                        "No construction label or verification state was machine-assigned.",
                    ),
                    model_calls=0,
                ),
            )
        )
    workbook = V3AnnotationWorkbook(cases=tuple(cases))
    workbook_path = (
        root / "benchmarks/verification_construction_v3_annotation_workbook_v1.json"
    )
    workbook_path.write_text(
        workbook.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    label_quotas, dimension_quotas = load_sampling_quotas(
        root / "artifacts/evaluations/verification-construction-v3-sampling-policy-v1.json"
    )
    audit = audit_annotation_workbook(
        workbook,
        expected_label_quotas=label_quotas,
        expected_dimension_quotas=dimension_quotas,
    )
    audit_path = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage2-annotation-gate-v1.json"
    )
    audit_path.write_text(audit.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(workbook_path.relative_to(root))
    print(audit_path.relative_to(root))
    print(
        f"cases={audit.total_cases} annotated={audit.annotated_cases} "
        f"approved={audit.approved_cases} ready={audit.ready_to_freeze}"
    )


def _local_candidates(payload: dict) -> list[dict]:
    result = []
    sequence = 0
    for case in payload["cases"]:
        components = case.get("expected_components") or [case["claim"]]
        evidence = tuple(
            V3ReviewEvidence(
                evidence_id=f"{case['case_id']}:{item['annotation_id']}",
                title=item["source_title"],
                url=item["source_url"],
                source_class=item.get("source_type") or "unknown",
                passage=item["excerpt"],
            )
            for item in case["candidate_evidence"]
        )
        for component in components:
            sequence += 1
            result.append(
                {
                    "candidate_id": f"V3-CAND-{sequence:03d}",
                    "claim_text": component,
                    "origin_family_id": f"initial_claims:{case['case_id']}",
                    "dimension": _dimension_hint(
                        component,
                        case.get("categories", []),
                    ),
                    "evidence": evidence,
                }
            )
    return result


def _public_candidates(payload: dict) -> list[dict]:
    return [
        {
            "candidate_id": case["collection_case_id"],
            "claim_text": case["claim_text"],
            "origin_family_id": case["origin_family_id"],
            "dimension": case["dimension"],
            "evidence": (
                V3ReviewEvidence(
                    evidence_id=f"{case['collection_case_id']}:E1",
                    title=case["source_title"],
                    url=case["source_url"],
                    source_class=case["source_class"],
                    passage=case["source_excerpt"],
                ),
            ),
        }
        for case in payload["cases"]
    ]


def _dimension_hint(claim: str, categories: list[str]) -> str | None:
    text = claim.casefold()
    if any(word in text for word in ("percent", "rate", "%")):
        return "percentage_or_rate"
    if any(word in text for word in ("price", "cost", "dollar", "€", "£")):
        return "currency"
    if any(word in text for word in ("pressure", "kilopascal", "atmosphere")):
        return "pressure"
    if any(word in text for word in ("temperature", "celsius", "fahrenheit", "hotter", "boil")):
        return "temperature"
    if any(word in text for word in ("speed", "faster", "kilometres per hour", "miles per hour")):
        return "speed"
    if any(word in text for word in ("day", "year long", "duration", "hours")):
        return "duration"
    if any(word in text for word in ("population", "number", "count", "bones", "largest")):
        return "count"
    if "numerical" in categories:
        return "distance_or_mass"
    if any(word in text for word in ("currently", "as of", "before", "after", "founded")):
        return "temporal_interval_or_status"
    return None


def _relation_hint(claim: str) -> str | None:
    text = claim.casefold()
    pairs = (
        ("at least", "greater_than_or_equal"),
        ("at most", "less_than_or_equal"),
        ("higher than", "greater_than"),
        ("more than", "greater_than"),
        ("longer than", "greater_than"),
        ("hotter than", "greater_than"),
        ("faster than", "greater_than"),
        ("lower than", "less_than"),
        ("less than", "less_than"),
        ("before", "before"),
        ("after", "after"),
        (" on ", "on"),
        ("exactly", "equal"),
        (" is ", "equal_or_status"),
    )
    return next((relation for token, relation in pairs if token in text), None)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
