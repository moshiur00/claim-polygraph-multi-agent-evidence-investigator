"""Offline V3.1 inventory assembly from reviewed repository evidence packets."""

import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field

from claim_polygraph_ng.domain.base import DomainModel


class V3InventoryCandidate(DomainModel):
    candidate_id: str = Field(pattern=r"^V3-CAND-[0-9]{3}$")
    source_case_id: str = Field(pattern=r"^CPNG-[0-9]{3}$")
    claim_text: str = Field(min_length=3, max_length=10_000)
    origin_family_id: str = Field(pattern=r"^initial_claims:CPNG-[0-9]{3}$")
    evidence_item_count: int = Field(ge=1)
    source_classes: tuple[str, ...] = Field(min_length=1)
    annotation_status: str
    annotated_by: str = Field(min_length=3)
    approved_by: str = Field(min_length=3)
    eligible: bool
    exclusion_reasons: tuple[str, ...] = ()


class V3InventoryAudit(DomainModel):
    inventory_id: str
    target_case_count: int = Field(ge=50, le=100)
    required_family_count: int = Field(ge=1)
    candidate_count: int = Field(ge=0)
    eligible_unique_claim_count: int = Field(ge=0)
    eligible_family_count: int = Field(ge=0)
    case_shortfall: int = Field(ge=0)
    family_shortfall: int = Field(ge=0)
    exact_target_met: bool
    split_assignment_performed: bool
    model_calls: int = Field(ge=0)
    network_calls: int = Field(ge=0)
    search_calls: int = Field(ge=0)
    candidates: tuple[V3InventoryCandidate, ...]


class V3PublicHtmlCandidate(DomainModel):
    collection_case_id: str = Field(pattern=r"^V3-WEB-[0-9]{3}$")
    claim_text: str = Field(min_length=3, max_length=10_000)
    dimension: str
    origin_family_id: str = Field(pattern=r"^public_html:[a-z0-9_]+$")
    source_class: str
    source_title: str = Field(min_length=3)
    source_url: str
    source_excerpt: str = Field(min_length=3, max_length=500)
    retrieved_at: str


class V3PoolCandidate(DomainModel):
    candidate_id: str
    claim_text: str
    origin_family_id: str
    source_classes: tuple[str, ...]
    dimension: str | None = None
    split: str
    provenance_status: str


class V3CollectionGateAudit(DomainModel):
    audit_id: str
    target_case_count: int
    required_family_count: int
    total_case_count: int
    total_family_count: int
    added_case_count: int
    added_family_count: int
    split_counts: dict[str, int]
    source_class_counts: dict[str, int]
    provisional_dimension_counts: dict[str, int]
    collection_gate_passed: bool
    split_assignment_performed: bool
    annotation_complete: bool
    dataset_frozen: bool
    controls: dict[str, int | float | bool]
    candidates: tuple[V3PoolCandidate, ...]


def assemble_repository_inventory(
    benchmark_path: str | Path,
    *,
    target_case_count: int = 60,
    required_family_count: int = 40,
) -> V3InventoryAudit:
    """Extract eligible atomic candidates without network or model assistance."""
    payload = json.loads(Path(benchmark_path).read_text(encoding="utf-8"))
    candidates: list[V3InventoryCandidate] = []
    sequence = 0
    for case in payload.get("cases", []):
        components = case.get("expected_components") or [case.get("claim")]
        evidence = case.get("candidate_evidence") or []
        source_classes = tuple(
            sorted(
                {
                    str(item.get("source_type") or "unknown")
                    for item in evidence
                }
            )
        )
        annotated_by = str(case.get("annotated_by") or "")
        approved_by = str(case.get("approved_by") or "")
        reasons = []
        if case.get("annotation_status") != "reviewed":
            reasons.append("annotation_not_reviewed")
        if not evidence:
            reasons.append("evidence_packet_missing")
        if not annotated_by or not approved_by:
            reasons.append("review_identity_missing")
        elif annotated_by.casefold() == approved_by.casefold():
            reasons.append("distinct_approval_missing")
        for component in components:
            if not component:
                continue
            sequence += 1
            candidates.append(
                V3InventoryCandidate(
                    candidate_id=f"V3-CAND-{sequence:03d}",
                    source_case_id=case["case_id"],
                    claim_text=component,
                    origin_family_id=f"initial_claims:{case['case_id']}",
                    evidence_item_count=len(evidence),
                    source_classes=source_classes or ("unknown",),
                    annotation_status=str(case.get("annotation_status") or "unknown"),
                    annotated_by=annotated_by or "missing",
                    approved_by=approved_by or "missing",
                    eligible=not reasons,
                    exclusion_reasons=tuple(reasons),
                )
            )
    eligible = [item for item in candidates if item.eligible]
    unique_claims = {normalize_claim(item.claim_text) for item in eligible}
    families = {item.origin_family_id for item in eligible}
    target_met = (
        len(unique_claims) >= target_case_count
        and len(families) >= required_family_count
    )
    return V3InventoryAudit(
        inventory_id="verification-construction-v3-repository-inventory-v1",
        target_case_count=target_case_count,
        required_family_count=required_family_count,
        candidate_count=len(candidates),
        eligible_unique_claim_count=len(unique_claims),
        eligible_family_count=len(families),
        case_shortfall=max(0, target_case_count - len(unique_claims)),
        family_shortfall=max(0, required_family_count - len(families)),
        exact_target_met=target_met,
        split_assignment_performed=target_met,
        model_calls=0,
        network_calls=0,
        search_calls=0,
        candidates=tuple(candidates),
    )


def normalize_claim(value: str) -> str:
    return " ".join(value.casefold().split()).rstrip(".!?")


def assemble_public_html_collection_gate(
    benchmark_path: str | Path,
    collection_path: str | Path,
    *,
    target_case_count: int = 60,
    required_family_count: int = 40,
    random_seed: int = 20260730,
) -> V3CollectionGateAudit:
    """Combine the reviewed local inventory with provenance-safe HTML candidates.

    This gate proves collection size, family diversity, and family-isolated split
    assignment. It intentionally does not claim that V3.2 human annotation or
    the final quota-constrained dataset freeze has occurred.
    """
    local = assemble_repository_inventory(
        benchmark_path,
        target_case_count=target_case_count,
        required_family_count=required_family_count,
    )
    payload = json.loads(Path(collection_path).read_text(encoding="utf-8"))
    if payload.get("rights_policy", {}).get("allowed_content_type") != "text/html":
        raise ValueError("public collection must be restricted to text/html")
    if payload.get("rights_policy", {}).get("pdf_downloads_allowed") is not False:
        raise ValueError("public collection must explicitly prohibit PDF downloads")

    web_candidates = tuple(
        V3PublicHtmlCandidate.model_validate(item)
        for item in payload.get("cases", [])
    )
    normalized_claims = {
        normalize_claim(item.claim_text)
        for item in local.candidates
        if item.eligible
    }
    seen_web_ids: set[str] = set()
    web_families: Counter[str] = Counter()
    for item in web_candidates:
        parsed = urlparse(item.source_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError(f"{item.collection_case_id} requires a public HTTPS URL")
        if item.collection_case_id in seen_web_ids:
            raise ValueError(f"duplicate collection id: {item.collection_case_id}")
        seen_web_ids.add(item.collection_case_id)
        normalized = normalize_claim(item.claim_text)
        if normalized in normalized_claims:
            raise ValueError(f"duplicate claim: {item.collection_case_id}")
        normalized_claims.add(normalized)
        web_families[item.origin_family_id] += 1
    if any(count > 2 for count in web_families.values()):
        raise ValueError("public collection exceeds the two-case origin-family cap")

    unsplit: list[dict[str, object]] = []
    for item in local.candidates:
        if not item.eligible:
            continue
        unsplit.append(
            {
                "candidate_id": item.candidate_id,
                "claim_text": item.claim_text,
                "origin_family_id": item.origin_family_id,
                "source_classes": item.source_classes,
                "dimension": None,
                "provenance_status": "reviewed_repository_packet",
            }
        )
    for item in web_candidates:
        unsplit.append(
            {
                "candidate_id": item.collection_case_id,
                "claim_text": item.claim_text,
                "origin_family_id": item.origin_family_id,
                "source_classes": (item.source_class,),
                "dimension": item.dimension,
                "provenance_status": "public_html_pending_v3_2_annotation",
            }
        )

    if len(unsplit) != target_case_count:
        raise ValueError(
            f"collection must produce exactly {target_case_count} cases; got {len(unsplit)}"
        )
    assignments = _assign_family_isolated_splits(
        unsplit,
        quotas={"development": 20, "calibration": 20, "held_out": 20},
        random_seed=random_seed,
    )
    candidates = tuple(
        V3PoolCandidate.model_validate({**item, "split": assignments[str(item["candidate_id"])]})
        for item in unsplit
    )
    families = {item.origin_family_id for item in candidates}
    source_counts = Counter(
        source_class
        for item in candidates
        for source_class in item.source_classes
    )
    dimension_counts = Counter(
        item.dimension for item in candidates if item.dimension is not None
    )
    split_counts = Counter(item.split for item in candidates)
    passed = (
        len(candidates) == target_case_count
        and len(families) >= required_family_count
        and split_counts == Counter(
            {"development": 20, "calibration": 20, "held_out": 20}
        )
    )
    return V3CollectionGateAudit(
        audit_id="verification-construction-v3-stage1a-public-html-collection-gate-v1",
        target_case_count=target_case_count,
        required_family_count=required_family_count,
        total_case_count=len(candidates),
        total_family_count=len(families),
        added_case_count=len(web_candidates),
        added_family_count=len(web_families),
        split_counts=dict(sorted(split_counts.items())),
        source_class_counts=dict(sorted(source_counts.items())),
        provisional_dimension_counts=dict(sorted(dimension_counts.items())),
        collection_gate_passed=passed,
        split_assignment_performed=True,
        annotation_complete=False,
        dataset_frozen=False,
        controls={
            "restricted_documents_downloaded": 0,
            "pdf_downloads": 0,
            "public_web_search_calls": 10,
            "public_html_candidates_selected": len(web_candidates),
            "model_calls": 0,
            "estimated_cost_usd": 0.0,
            "held_out_labels_exposed": False,
        },
        candidates=candidates,
    )


def _assign_family_isolated_splits(
    candidates: list[dict[str, object]],
    *,
    quotas: dict[str, int],
    random_seed: int,
) -> dict[str, str]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in candidates:
        grouped[str(item["origin_family_id"])].append(item)
    groups = list(grouped.items())
    random.Random(random_seed).shuffle(groups)
    groups.sort(key=lambda pair: len(pair[1]), reverse=True)
    remaining = dict(quotas)
    assignments: dict[str, str] = {}
    for _, group in groups:
        eligible = [
            split for split, capacity in remaining.items() if capacity >= len(group)
        ]
        if not eligible:
            raise ValueError("family-isolated split quotas cannot be satisfied")
        split = max(eligible, key=lambda name: (remaining[name], name))
        for item in group:
            assignments[str(item["candidate_id"])] = split
        remaining[split] -= len(group)
    if any(remaining.values()):
        raise ValueError(f"unfilled split quotas: {remaining}")
    return assignments
