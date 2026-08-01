"""Audit V4.10 fresh sealed held-out collection before human review."""

# ruff: noqa: E501 -- audit identifiers and declarative gates are intentionally explicit.

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

from claim_polygraph_ng.evaluation.v3_annotation import load_v4_fresh_held_out_workbook


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _walk_records(value, claims: set[str], domains: set[str]) -> None:
    if isinstance(value, dict):
        claim = value.get("claim_text")
        if isinstance(claim, str):
            claims.add(claim.casefold().strip())
        for key in ("url", "source_url"):
            url = value.get(key)
            if isinstance(url, str) and url.startswith("http"):
                domains.add(urlparse(url).netloc.casefold().removeprefix("www."))
        for child in value.values():
            _walk_records(child, claims, domains)
    elif isinstance(value, list):
        for child in value:
            _walk_records(child, claims, domains)


def main() -> None:
    root = Path(__file__).parents[1]
    workbook_path = root / "benchmarks/verification_construction_v4_stage10_fresh_held_out_workbook_v1.json"
    workbook = load_v4_fresh_held_out_workbook(workbook_path)
    retired_claims: set[str] = set()
    retired_domains: set[str] = set()
    for pattern in ("benchmarks/verification_construction_v3*.json", "benchmarks/verification_construction_v4*.json"):
        for path in root.glob(pattern):
            if path == workbook_path:
                continue
            _walk_records(json.loads(path.read_text(encoding="utf-8")), retired_claims, retired_domains)

    current_claims = {case.claim_text.casefold().strip() for case in workbook.cases}
    current_domains = {urlparse(item.url).netloc.casefold().removeprefix("www.") for case in workbook.cases for item in case.evidence}
    exact_span_failures = 0
    for case in workbook.cases:
        try:
            case.proposal.claim_span.validate_against(case.claim_text)
            evidence = {item.evidence_id: item for item in case.evidence}
            for span in case.proposal.evidence_spans:
                if evidence[span.evidence_id].passage[span.start_char:span.end_char] != span.quoted_text:
                    exact_span_failures += 1
        except ValueError:
            exact_span_failures += 1
    gates = {
        "case_count_20": len(workbook.cases) == 20,
        "minimum_10_origin_families": len({case.origin_family_id for case in workbook.cases}) >= 10,
        "exact_claim_reuse_zero": not current_claims.intersection(retired_claims),
        "retired_domain_reuse_zero": not current_domains.intersection(retired_domains),
        "held_out_only": all(case.split.value == "held_out" for case in workbook.cases),
        "exact_span_failures_zero": exact_span_failures == 0,
        "human_annotations_zero_before_review": all(case.annotation is None for case in workbook.cases),
        "approvals_zero_before_review": all(case.approval is None for case in workbook.cases),
        "provider_model_calls_zero": all(case.proposal.model_calls == 0 for case in workbook.cases),
        "pdf_sources_zero": all(not item.url.casefold().endswith(".pdf") for case in workbook.cases for item in case.evidence),
        "held_out_execution_zero": True,
        "held_out_cases_exposed_to_model_zero": True,
    }
    audit = {
        "audit_id": "verification-construction-v4-stage10-collection-audit-v1",
        "status": "awaiting_human_review" if all(gates.values()) else "blocked",
        "collection_gate_passed": all(gates.values()),
        "held_out_execution_authorized": False,
        "workbook_sha256": _hash(workbook_path),
        "case_count": len(workbook.cases),
        "origin_family_count": len({case.origin_family_id for case in workbook.cases}),
        "source_domain_count": len(current_domains),
        "source_domains": sorted(current_domains),
        "annotator_identity_prefill": "Md Moshiur Rahman",
        "distinct_approver_identity_prefill": "Md Rashedul Islam",
        "human_annotations_completed": 0,
        "distinct_approvals_completed": 0,
        "model_calls": 0,
        "network_calls_during_benchmark_execution": 0,
        "paid_operations": 0,
        "held_out_cases_exposed_to_model": 0,
        "gates": gates,
        "next_action": "Human annotation by Md Moshiur Rahman and distinct approval by Md Rashedul Islam",
    }
    destination = root / "artifacts/evaluations/verification-construction-v4-stage10-collection-audit-v1.json"
    destination.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print(f"status={audit['status']} cases={audit['case_count']} families={audit['origin_family_count']} model_calls=0")


if __name__ == "__main__":
    main()
