"""Stage 10.5 social quality and shared-origin safety gate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import Field

from claim_polygraph_ng.analysis.evidence_families import (
    FamilySourceRecord,
    infer_evidence_families,
)
from claim_polygraph_ng.analysis.source_quality import (
    SourceQualityDimension,
    SourceQualityMetadata,
    assess_source_quality,
)
from claim_polygraph_ng.domain import DistributionMedium, SourceType
from claim_polygraph_ng.domain.base import DomainModel


class Phase10SocialQualityArtifact(DomainModel):
    artifact_id: str
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Phase10SocialQualityAudit(DomainModel):
    audit_id: str = "phase10-stage10.5-social-quality-gate-audit-v1"
    fixture_id: str
    quality_case_count: int
    exact_authority_count: int
    badge_authority_promotion_count: int
    engagement_authority_change_count: int
    shared_origin_source_count: int
    shared_origin_family_count: int
    shared_origin_reason_present: bool
    model_calls: int = 0
    search_calls: int = 0
    network_calls: int = 0
    valid: bool
    errors: tuple[str, ...]
    artifacts: tuple[Phase10SocialQualityArtifact, ...]


_ARTIFACTS = (
    ("fixtures", "benchmarks/phase10_social_quality_fixtures_v1.json"),
    ("source_quality", "src/claim_polygraph_ng/analysis/source_quality.py"),
    ("provenance", "src/claim_polygraph_ng/analysis/investigation_provenance.py"),
    ("independence", "src/claim_polygraph_ng/analysis/independence.py"),
    ("family_inference", "src/claim_polygraph_ng/analysis/evidence_families.py"),
    ("readiness", "src/claim_polygraph_ng/analysis/readiness.py"),
    ("readiness_contract", "src/claim_polygraph_ng/domain/readiness.py"),
    ("adversarial_tests", "tests/unit/test_social_quality_readiness.py"),
)


def build_phase10_social_quality_audit(
    project_root: str | Path,
) -> Phase10SocialQualityAudit:
    root = Path(project_root).resolve()
    fixture = json.loads(
        (root / "benchmarks/phase10_social_quality_fixtures_v1.json").read_text(
            "utf-8"
        )
    )
    errors: list[str] = []
    exact = badge_promotions = 0
    authority_by_case: dict[str, str] = {}
    for case in fixture["cases"]:
        assessment = assess_source_quality(
            SourceQualityMetadata(
                source_type=SourceType.OTHER,
                publisher_identified=True,
                author_identified=True,
                distribution_medium=DistributionMedium.SOCIAL_PLATFORM,
                social_identity_resolved=True,
                social_account_authenticated=case["authenticated"],
                social_account_institutional=True,
                social_authority_scope_recorded=case[
                    "authority_scope_recorded"
                ],
                institutional_authority_confirmed=case[
                    "institutional_authority_confirmed"
                ],
                prohibited_social_signals=tuple(case["prohibited_signals"]),
            )
        )
        authority = next(
            item
            for item in assessment.dimensions
            if item.dimension is SourceQualityDimension.AUTHORITY
        )
        authority_by_case[case["case_id"]] = authority.finding.value
        if authority.finding.value == case["expected_authority"]:
            exact += 1
        else:
            errors.append(f"{case['case_id']}: authority mismatch")
        if (
            "badge:verified" in case["prohibited_signals"]
            and authority.finding.value == "favorable"
        ):
            badge_promotions += 1

    engagement_changes = int(
        authority_by_case["SOCQUAL-002"] != authority_by_case["SOCQUAL-003"]
    )
    shared = fixture["shared_origin"]
    records = tuple(
        FamilySourceRecord(
            source_id=f"source-{index}",
            url=f"https://platform-{index}.example/post/{index}",
            text=f"Distinct passage {index} from a shared-origin distribution.",
            origin_urls=(shared["origin_url"],),
        )
        for index in range(shared["source_count"])
    )
    inference = infer_evidence_families(shared["component_id"], records)
    family_count = len(inference.families)
    reason_present = all(
        shared["expected_reason"] in family.grouping_reasons
        for family in inference.families
    )
    if family_count != shared["expected_family_count"] or not reason_present:
        errors.append("shared-origin family invariant failed")
    if badge_promotions:
        errors.append("platform badge promoted authority")
    if engagement_changes:
        errors.append("engagement metadata changed authority")

    return Phase10SocialQualityAudit(
        fixture_id=fixture["fixture_id"],
        quality_case_count=len(fixture["cases"]),
        exact_authority_count=exact,
        badge_authority_promotion_count=badge_promotions,
        engagement_authority_change_count=engagement_changes,
        shared_origin_source_count=shared["source_count"],
        shared_origin_family_count=family_count,
        shared_origin_reason_present=reason_present,
        valid=not errors and exact == len(fixture["cases"]),
        errors=tuple(errors),
        artifacts=tuple(
            Phase10SocialQualityArtifact(
                artifact_id=artifact_id,
                path=path,
                sha256=_sha256(root / path),
            )
            for artifact_id, path in _ARTIFACTS
        ),
    )


def export_phase10_social_quality_audit(
    project_root: str | Path,
) -> Phase10SocialQualityAudit:
    root = Path(project_root).resolve()
    audit = build_phase10_social_quality_audit(root)
    target = (
        root
        / "artifacts/evaluations/"
        "phase10-stage10.5-social-quality-gate-audit-v1.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(audit.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return audit


def verify_phase10_social_quality_audit(
    audit: Phase10SocialQualityAudit,
    project_root: str | Path,
) -> tuple[str, ...]:
    root = Path(project_root).resolve()
    errors = list(audit.errors)
    if not audit.valid or audit.exact_authority_count != audit.quality_case_count:
        errors.append("social authority fixture gate is incomplete")
    if (
        audit.badge_authority_promotion_count
        or audit.engagement_authority_change_count
        or audit.shared_origin_family_count != 1
    ):
        errors.append("social quality or origin invariant failed")
    if audit.model_calls or audit.search_calls or audit.network_calls:
        errors.append("Stage 10.5 audit must be zero-cost")
    for artifact in audit.artifacts:
        candidate = (root / artifact.path).resolve()
        if not candidate.is_file():
            errors.append(f"{artifact.artifact_id}: file missing")
        elif _sha256(candidate) != artifact.sha256:
            errors.append(f"{artifact.artifact_id}: SHA-256 mismatch")
    return tuple(dict.fromkeys(errors))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

