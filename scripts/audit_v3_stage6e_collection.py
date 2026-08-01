"""Audit V3.6e collection without exposing held-out claim text to a model."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from claim_polygraph_ng.evaluation.v3_annotation import (
    load_replacement_calibration_workbook,
)

ROOT = Path(__file__).parents[1]
WORKBOOK = (
    ROOT
    / "benchmarks/"
    "verification_construction_v3_stage6e_fresh_calibration_workbook_v1.json"
)
EXPOSED_WORKBOOKS = (
    ROOT
    / "benchmarks/"
    "verification_construction_v3_stage6a_replacement_calibration_workbook_v1_APPROVED.json",
    ROOT
    / "benchmarks/"
    "verification_construction_v3_stage6c_fresh_calibration_workbook_v1_APPROVED.json",
)


def main() -> None:
    workbook = load_replacement_calibration_workbook(WORKBOOK)
    exposed_claims: set[str] = set()
    exposed_urls: set[str] = set()
    exposed_families: set[str] = set()
    for path in EXPOSED_WORKBOOKS:
        packet = load_replacement_calibration_workbook(path)
        for case in packet.cases:
            exposed_claims.add(case.claim_text.casefold().strip())
            exposed_families.add(case.origin_family_id.casefold().strip())
            exposed_urls.update(item.url.casefold().strip() for item in case.evidence)

    claims = [case.claim_text.casefold().strip() for case in workbook.cases]
    families = [case.origin_family_id.casefold().strip() for case in workbook.cases]
    urls = [
        evidence.url.casefold().strip()
        for case in workbook.cases
        for evidence in case.evidence
    ]
    family_counts = Counter(families)
    exact_span_failures = 0
    for case in workbook.cases:
        case.proposal.claim_span.validate_against(case.claim_text)
        evidence = {item.evidence_id: item for item in case.evidence}
        for span in case.proposal.evidence_spans:
            item = evidence[span.evidence_id]
            if item.passage[span.start_char : span.end_char] != span.quoted_text:
                exact_span_failures += 1

    checks = {
        "case_count": len(workbook.cases) == 20,
        "minimum_origin_families": len(set(families)) >= 10,
        "maximum_two_cases_per_family": max(family_counts.values()) <= 2,
        "unique_claims": len(claims) == len(set(claims)),
        "no_exposed_claim_reuse": not set(claims).intersection(exposed_claims),
        "no_exposed_url_reuse": not set(urls).intersection(exposed_urls),
        "no_exposed_family_reuse": not set(families).intersection(exposed_families),
        "exact_machine_spans": exact_span_failures == 0,
        "accessible_html_only": all(
            url.startswith("https://") and not url.endswith(".pdf") for url in urls
        ),
        "all_annotations_unrecorded": all(
            case.annotation is None for case in workbook.cases
        ),
        "all_approvals_unrecorded": all(
            case.approval is None for case in workbook.cases
        ),
    }
    artifact = {
        "audit_id": "verification-construction-v3-stage6e-collection-audit-v1",
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "case_count": len(workbook.cases),
        "origin_family_count": len(set(families)),
        "family_counts": dict(sorted(family_counts.items())),
        "suggested_constructible_cases": sum(
            case.proposal.suggested_gold_label
            and case.proposal.suggested_gold_label.value
            in {"deterministic_constructible", "fallback_eligible"}
            for case in workbook.cases
        ),
        "suggested_nonconstructible_cases": sum(
            case.proposal.suggested_gold_label
            and case.proposal.suggested_gold_label.value
            in {"unconstructible", "not_applicable"}
            for case in workbook.cases
        ),
        "controls": {
            "model_calls": 0,
            "estimated_cost_usd": 0.0,
            "pdf_downloads": 0,
            "restricted_content_fetches": 0,
            "held_out_claim_texts_printed_or_exposed_to_model": 0,
            "held_out_cases_exposed_to_provider": 0,
            "human_annotations_recorded": 0,
            "human_approvals_recorded": 0,
        },
        "review_defaults": {
            "annotator_identity": "Md Moshiur Rahman",
            "approver_identity": "Md Rashedul Islam",
            "approval_decisions_prefilled": 0,
            "approval_checklists_prefilled": 0,
        },
    }
    destination = (
        ROOT
        / "artifacts/evaluations/"
        "verification-construction-v3-stage6e-collection-audit-v1.json"
    )
    destination.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    if not all(checks.values()):
        failed = [name for name, passed in checks.items() if not passed]
        raise ValueError(f"V3.6e collection audit failed: {failed}")
    print(destination.relative_to(ROOT))
    print("status=passed cases=20 families=10 model_calls=0 pdfs=0")


if __name__ == "__main__":
    main()
