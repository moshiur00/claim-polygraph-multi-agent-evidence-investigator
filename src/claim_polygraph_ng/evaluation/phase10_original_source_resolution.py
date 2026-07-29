"""Stage 10.4 original-source resolution and family-integrity gate."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from pydantic import Field

from claim_polygraph_ng.analysis import analyze_source_independence
from claim_polygraph_ng.application import preflight_original_source_resolution
from claim_polygraph_ng.domain import (
    DistributionMedium,
    Evidence,
    EvidenceStance,
    ExtractionStatus,
    OriginalSourceResolutionPermission,
    OriginalSourceResolutionRequest,
    SocialAccountIdentity,
    SocialCaptureMethod,
    SocialContentOriginStatus,
    SocialOriginalSourceLink,
    SocialPostType,
    SocialSourceContext,
    SocialSourceRelationship,
    Source,
    SourceType,
    UnderlyingRecordKind,
    evaluate_social_evidence_eligibility,
)
from claim_polygraph_ng.domain.base import DomainModel


class Phase10OriginArtifact(DomainModel):
    artifact_id: str
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Phase10OriginResolutionAudit(DomainModel):
    audit_id: str = "phase10-stage10.4-original-source-gate-audit-v1"
    fixture_id: str
    case_count: int
    exact_preflight_count: int
    allowed_count: int
    blocked_count: int
    resolved_pair_family_count: int
    resolved_pair_grouping_reason: str
    model_calls: int = 0
    search_calls: int = 0
    network_calls: int = 0
    valid: bool
    errors: tuple[str, ...]
    artifacts: tuple[Phase10OriginArtifact, ...]


_ARTIFACTS = (
    ("fixtures", "benchmarks/phase10_original_source_resolution_fixtures_v1.json"),
    ("contracts", "src/claim_polygraph_ng/domain/original_source.py"),
    ("social_contracts", "src/claim_polygraph_ng/domain/social.py"),
    ("resolver", "src/claim_polygraph_ng/application/original_source_resolver.py"),
    ("persistence", "src/claim_polygraph_ng/persistence/research.py"),
    ("independence", "src/claim_polygraph_ng/analysis/independence.py"),
    ("family_inference", "src/claim_polygraph_ng/analysis/evidence_families.py"),
    ("provenance", "src/claim_polygraph_ng/analysis/investigation_provenance.py"),
)

_SOCIAL_ID = UUID("00000000-0000-0000-0000-000000000101")
_UNDERLYING_ID = UUID("00000000-0000-0000-0000-000000000102")
_CLAIM_ID = UUID("00000000-0000-0000-0000-000000000103")


def build_phase10_original_source_audit(
    project_root: str | Path,
) -> Phase10OriginResolutionAudit:
    root = Path(project_root).resolve()
    fixture = json.loads(
        (
            root / "benchmarks/phase10_original_source_resolution_fixtures_v1.json"
        ).read_text("utf-8")
    )
    errors: list[str] = []
    exact = allowed = blocked = 0
    for case in fixture["cases"]:
        source = _social_source(
            case["recorded_url"],
            resolved=case["link_resolved"],
        )
        request = _request(source, case["target_url"])
        reason = preflight_original_source_resolution(source, request)
        actual = "allowed" if reason is None else "blocked"
        allowed += actual == "allowed"
        blocked += actual == "blocked"
        if actual == case["expected_preflight"]:
            exact += 1
        else:
            errors.append(f"{case['case_id']}: preflight mismatch")

    social = _social_source(
        "https://authority.example/report",
        resolved=True,
    )
    underlying = Source(
        source_id=_UNDERLYING_ID,
        url="https://authority.example/report",
        canonical_url="https://authority.example/report",
        title="Underlying report",
        source_type=SourceType.OFFICIAL,
        retrieved_at=datetime.now(UTC),
        extraction_status=ExtractionStatus.EXTRACTED,
        distribution_medium=DistributionMedium.WEB_PAGE,
    )
    evidence = (
        Evidence(
            claim_id=_CLAIM_ID,
            source_id=social.source_id,
            passage="The social item links to the report.",
            stance=EvidenceStance.CONTEXT,
            relevance_score=0.7,
        ),
        Evidence(
            claim_id=_CLAIM_ID,
            source_id=underlying.source_id,
            passage="The underlying report contains the primary record.",
            stance=EvidenceStance.SUPPORTS,
            relevance_score=0.9,
        ),
    )
    _, independence = analyze_source_independence(
        claim_id=_CLAIM_ID,
        sources=(social, underlying),
        evidence=evidence,
        required_families=2,
    )
    reasons = independence.families[0].grouping_reasons
    if (
        independence.independent_family_count != 1
        or "resolved_original_source" not in reasons
    ):
        errors.append("resolved social/original pair was counted independently")

    return Phase10OriginResolutionAudit(
        fixture_id=fixture["fixture_id"],
        case_count=len(fixture["cases"]),
        exact_preflight_count=exact,
        allowed_count=allowed,
        blocked_count=blocked,
        resolved_pair_family_count=independence.independent_family_count,
        resolved_pair_grouping_reason="resolved_original_source",
        valid=not errors and exact == len(fixture["cases"]),
        errors=tuple(errors),
        artifacts=tuple(
            Phase10OriginArtifact(
                artifact_id=artifact_id,
                path=path,
                sha256=_sha256(root / path),
            )
            for artifact_id, path in _ARTIFACTS
        ),
    )


def export_phase10_original_source_audit(
    project_root: str | Path,
) -> Phase10OriginResolutionAudit:
    root = Path(project_root).resolve()
    audit = build_phase10_original_source_audit(root)
    target = (
        root
        / "artifacts/evaluations/"
        "phase10-stage10.4-original-source-gate-audit-v1.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(audit.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return audit


def verify_phase10_original_source_audit(
    audit: Phase10OriginResolutionAudit,
    project_root: str | Path,
) -> tuple[str, ...]:
    root = Path(project_root).resolve()
    errors = list(audit.errors)
    if not audit.valid or audit.exact_preflight_count != audit.case_count:
        errors.append("original-source preflight gate is incomplete")
    if (
        audit.resolved_pair_family_count != 1
        or audit.resolved_pair_grouping_reason != "resolved_original_source"
    ):
        errors.append("resolved-origin family invariant failed")
    if audit.model_calls or audit.search_calls or audit.network_calls:
        errors.append("Stage 10.4 audit must be zero-network")
    for artifact in audit.artifacts:
        candidate = (root / artifact.path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            errors.append(f"{artifact.artifact_id}: path escapes project root")
            continue
        if not candidate.is_file():
            errors.append(f"{artifact.artifact_id}: file missing")
        elif _sha256(candidate) != artifact.sha256:
            errors.append(f"{artifact.artifact_id}: SHA-256 mismatch")
    return tuple(dict.fromkeys(errors))


def _social_source(url: str, *, resolved: bool) -> Source:
    link = SocialOriginalSourceLink(
        relationship=SocialSourceRelationship.LINKS_TO,
        source_id=_UNDERLYING_ID if resolved else None,
        url=url,
        resolved=resolved,
    )
    context = SocialSourceContext(
        account=SocialAccountIdentity(platform="x", handle="authority"),
        post_type=SocialPostType.LINK_SHARE,
        original_source=link,
        capture_method=SocialCaptureMethod.SEARCH_RESULT_SNIPPET,
        content_origin_status=SocialContentOriginStatus.UNKNOWN,
    )
    return Source(
        source_id=_SOCIAL_ID,
        url="https://x.com/authority/status/123456",
        canonical_url="https://x.com/authority/status/123456",
        title="Social source",
        source_type=SourceType.OTHER,
        retrieved_at=datetime.now(UTC),
        extraction_status=ExtractionStatus.PARTIAL,
        distribution_medium=DistributionMedium.SOCIAL_PLATFORM,
        social_context=context,
        social_eligibility=evaluate_social_evidence_eligibility(context),
    )


def _request(source: Source, target_url: str) -> OriginalSourceResolutionRequest:
    return OriginalSourceResolutionRequest(
        social_source_id=source.source_id,
        target_url=target_url,
        relationship=SocialSourceRelationship.LINKS_TO,
        record_kind=UnderlyingRecordKind.REPORT,
        source_type=SourceType.OFFICIAL,
        title="Underlying report",
        permission=OriginalSourceResolutionPermission(
            authorized=True,
            authorized_by="fixture-policy",
            authorized_at=datetime.now(UTC),
            purpose="Evaluate the deterministic Stage 10.4 preflight.",
        ),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

