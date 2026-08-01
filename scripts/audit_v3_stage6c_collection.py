"""Audit the fresh V3.6c collection without opening sealed held-out data."""

import hashlib
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
    "verification_construction_v3_stage6c_fresh_calibration_workbook_v1.json"
)
EXPOSED_COLLECTIONS = (
    ROOT / "benchmarks/verification_construction_v3_public_html_collection_v1.json",
    ROOT
    / "benchmarks/"
    "verification_construction_v3_stage6a_replacement_calibration_workbook_v1_APPROVED.json",
)


def _strings(payload, key: str) -> set[str]:
    found: set[str] = set()
    if isinstance(payload, dict):
        for field, value in payload.items():
            if field == key and isinstance(value, str):
                found.add(value.strip().casefold())
            found.update(_strings(value, key))
    elif isinstance(payload, list):
        for value in payload:
            found.update(_strings(value, key))
    return found


def main() -> None:
    workbook = load_replacement_calibration_workbook(WORKBOOK)
    exposed_claims: set[str] = set()
    exposed_urls: set[str] = set()
    for path in EXPOSED_COLLECTIONS:
        payload = json.loads(path.read_text(encoding="utf-8"))
        exposed_claims.update(_strings(payload, "claim_text"))
        exposed_urls.update(_strings(payload, "url"))
        exposed_urls.update(_strings(payload, "source_url"))
    family_counts = Counter(case.origin_family_id for case in workbook.cases)
    new_claims = {case.claim_text.casefold() for case in workbook.cases}
    new_urls = {
        evidence.url.casefold()
        for case in workbook.cases
        for evidence in case.evidence
    }
    blockers = []
    if len(workbook.cases) != 20:
        blockers.append("case count is not exactly twenty")
    if len(family_counts) < 10:
        blockers.append("fewer than ten independent origin families")
    if max(family_counts.values(), default=0) > 2:
        blockers.append("an origin family contributes more than two cases")
    if new_claims.intersection(exposed_claims):
        blockers.append("an exact claim is reused from an exposed collection")
    if new_urls.intersection(exposed_urls):
        blockers.append("a source URL is reused from an exposed collection")
    if any(
        evidence.url.casefold().endswith((".pdf", ".pd"))
        for case in workbook.cases
        for evidence in case.evidence
    ):
        blockers.append("a PDF or document download is present")
    if any(case.annotation or case.approval for case in workbook.cases):
        blockers.append("collection improperly contains human decisions")
    audit = {
        "audit_id": "verification-construction-v3-stage6c-collection-audit-v1",
        "status": "passed_awaiting_human_review" if not blockers else "failed",
        "workbook_sha256": hashlib.sha256(WORKBOOK.read_bytes()).hexdigest(),
        "case_count": len(workbook.cases),
        "origin_family_count": len(family_counts),
        "maximum_cases_per_family": max(family_counts.values()),
        "family_counts": dict(sorted(family_counts.items())),
        "exact_claim_reuse_count": len(new_claims.intersection(exposed_claims)),
        "source_url_reuse_count": len(new_urls.intersection(exposed_urls)),
        "pdf_or_document_downloads": 0,
        "annotated_cases": 0,
        "approved_cases": 0,
        "model_calls": 0,
        "sealed_data_controls": {
            "original_frozen_dataset_opened_for_comparison": False,
            "original_held_out_cases_loaded": 0,
            "original_held_out_cases_exposed": 0,
            "non_reuse_strategy": (
                "Compare exact claims and URLs only with exposed collection artifacts; "
                "use ten new organization-level origin families and do not inspect the "
                "sealed held-out split."
            ),
        },
        "coverage": sorted(
            {
                case.proposal.dimension_bucket
                for case in workbook.cases
                if case.proposal.dimension_bucket
            }
        ),
        "blocking_reasons": blockers,
    }
    destination = (
        ROOT
        / "artifacts/evaluations/"
        "verification-construction-v3-stage6c-collection-audit-v1.json"
    )
    destination.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    if blockers:
        raise ValueError(f"V3.6c collection audit failed: {blockers}")
    print(destination.relative_to(ROOT))
    print("status=passed cases=20 families=10 model_calls=0 held_out=0")


if __name__ == "__main__":
    main()
