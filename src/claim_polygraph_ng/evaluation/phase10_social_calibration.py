"""Stage 10.8 adversarial social-evidence replay and human-calibration gate."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field

from claim_polygraph_ng.analysis import (
    analyze_source_independence,
    build_argument_ledger,
)
from claim_polygraph_ng.analysis.investigation_provenance import (
    build_investigation_provenance,
)
from claim_polygraph_ng.domain import (
    AtomicClaim,
    DistributionMedium,
    Evidence,
    EvidenceEligibilityDecision,
    EvidenceStance,
    EvidentiaryUse,
    ExtractionStatus,
    InvestigationPlan,
    ResearchPath,
    SocialAccountIdentity,
    SocialAccountType,
    SocialArchiveReference,
    SocialAuthenticityEvidence,
    SocialAuthenticityEvidenceType,
    SocialAuthenticityStatus,
    SocialCaptureMethod,
    SocialContentOriginStatus,
    SocialOriginalSourceLink,
    SocialPostType,
    SocialSourceContext,
    SocialSourceRelationship,
    Source,
    SourceType,
    evaluate_social_evidence_constraints,
    evaluate_social_evidence_eligibility,
)
from claim_polygraph_ng.domain.base import DomainModel


class Phase10CalibrationArtifact(DomainModel):
    artifact_id: str
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Phase10AdversarialCaseResult(DomainModel):
    case_id: str
    category: str
    expected_eligibility: EvidenceEligibilityDecision
    actual_eligibility: EvidenceEligibilityDecision
    expected_usable: bool
    actual_usable: bool
    mandatory_review: bool
    actual_review_routed: bool
    unsafe_if_published: bool
    publication_blocked: bool
    expected_family_count: int = Field(ge=1)
    actual_family_count: int = Field(ge=1)
    origin_resolution_applicable: bool
    origin_expected_resolved: bool
    origin_actual_resolved: bool
    verdict_stability_case: bool
    baseline_resolution: str
    expanded_resolution: str
    stable: bool
    policy_finding_codes: tuple[str, ...]


class Phase10SocialCalibrationAudit(DomainModel):
    audit_id: str = "phase10-stage10.8-social-calibration-audit-v1"
    fixture_id: str
    case_count: int
    category_count: int
    exact_eligibility_count: int
    eligibility_precision: float = Field(ge=0, le=1)
    unsafe_case_count: int
    unsafe_publication_count: int
    unsafe_publication_rate: float = Field(ge=0, le=1)
    origin_applicable_count: int
    origin_resolution_accuracy: float = Field(ge=0, le=1)
    expected_resolved_origin_count: int
    resolved_origin_count: int
    origin_resolution_rate: float = Field(ge=0, le=1)
    independence_inflation_case_count: int
    maximum_family_inflation: int
    mandatory_review_case_count: int
    routed_mandatory_review_count: int
    review_routing_recall: float = Field(ge=0, le=1)
    review_routing_precision: float = Field(ge=0, le=1)
    verdict_stability_case_count: int
    stable_verdict_count: int
    verdict_stability_rate: float = Field(ge=0, le=1)
    machine_gate_passed: bool
    human_calibration_status: str
    stage_exit_ready: bool
    model_calls: int = 0
    search_calls: int = 0
    network_calls: int = 0
    errors: tuple[str, ...]
    cases: tuple[Phase10AdversarialCaseResult, ...]
    artifacts: tuple[Phase10CalibrationArtifact, ...]


_FIXTURE = "benchmarks/phase10_social_adversarial_benchmark_v1.json"
_REVIEW_PACKET = (
    "artifacts/reviews/phase10-stage10.8-human-calibration-packet-v1.json"
)
_AUDIT = "artifacts/evaluations/phase10-stage10.8-social-calibration-audit-v1.json"
_STATIC_ARTIFACTS = (
    ("fixture", _FIXTURE),
    (
        "completion_report",
        "docs/PHASE_10_STAGE_10.8_BENCHMARK_AND_HUMAN_CALIBRATION.md",
    ),
    (
        "human_review_guide",
        "docs/PHASE_10_STAGE_10.8_HUMAN_REVIEW_GUIDE.md",
    ),
    ("social_contracts", "src/claim_polygraph_ng/domain/social.py"),
    ("social_policy", "src/claim_polygraph_ng/domain/social_constraints.py"),
    ("provenance", "src/claim_polygraph_ng/analysis/investigation_provenance.py"),
    ("independence", "src/claim_polygraph_ng/analysis/independence.py"),
    ("argument_ledger", "src/claim_polygraph_ng/analysis/argument_ledger.py"),
    (
        "tests",
        "tests/unit/test_phase10_social_calibration.py",
    ),
)


def build_phase10_social_calibration_audit(
    project_root: str | Path,
) -> Phase10SocialCalibrationAudit:
    root = Path(project_root).resolve()
    fixture = json.loads((root / _FIXTURE).read_text("utf-8"))
    results = tuple(_replay_case(case) for case in fixture["cases"])
    review_path = root / _REVIEW_PACKET
    if not review_path.exists():
        _write_review_packet(review_path, fixture, results)
    review = json.loads(review_path.read_text("utf-8"))
    human_status = str(review.get("status", "pending"))

    exact = sum(
        item.actual_eligibility is item.expected_eligibility for item in results
    )
    true_positive = sum(item.actual_usable and item.expected_usable for item in results)
    false_positive = sum(
        item.actual_usable and not item.expected_usable for item in results
    )
    eligibility_precision = _ratio(true_positive, true_positive + false_positive)
    unsafe = tuple(item for item in results if item.unsafe_if_published)
    unsafe_publications = sum(not item.publication_blocked for item in unsafe)
    origins = tuple(item for item in results if item.origin_resolution_applicable)
    origin_exact = sum(
        item.origin_actual_resolved == item.origin_expected_resolved
        for item in origins
    )
    expected_resolved = tuple(item for item in origins if item.origin_expected_resolved)
    resolved = sum(item.origin_actual_resolved for item in expected_resolved)
    inflation = tuple(
        item.actual_family_count - item.expected_family_count for item in results
    )
    mandatory = tuple(item for item in results if item.mandatory_review)
    routed_mandatory = sum(item.actual_review_routed for item in mandatory)
    routed = tuple(item for item in results if item.actual_review_routed)
    correctly_routed = sum(item.mandatory_review for item in routed)
    stability = tuple(item for item in results if item.verdict_stability_case)
    stable = sum(item.stable for item in stability)
    errors: list[str] = []
    if exact != len(results):
        errors.append("one or more eligibility decisions differ from the frozen labels")
    if eligibility_precision != 1:
        errors.append("eligibility precision is below 100%")
    if unsafe_publications:
        errors.append("an unsafe adversarial case remained publishable")
    if origins and origin_exact != len(origins):
        errors.append("original-source resolution differs from the frozen expectation")
    if any(value > 0 for value in inflation):
        errors.append("shared-origin sources inflated independent family counts")
    if mandatory and routed_mandatory != len(mandatory):
        errors.append("mandatory-review routing recall is below 100%")
    if stability and stable != len(stability):
        errors.append("duplicate distribution changed deterministic resolution")

    machine_gate = not errors
    human_approved = _human_packet_approved(review, results)
    if human_status == "approved" and not human_approved:
        errors.append("human calibration packet is marked approved but incomplete")
    artifacts = tuple(
        Phase10CalibrationArtifact(
            artifact_id=artifact_id,
            path=path,
            sha256=_sha256(root / path),
        )
        for artifact_id, path in (*_STATIC_ARTIFACTS, ("human_review", _REVIEW_PACKET))
    )
    return Phase10SocialCalibrationAudit(
        fixture_id=fixture["fixture_id"],
        case_count=len(results),
        category_count=len({item.category for item in results}),
        exact_eligibility_count=exact,
        eligibility_precision=eligibility_precision,
        unsafe_case_count=len(unsafe),
        unsafe_publication_count=unsafe_publications,
        unsafe_publication_rate=_ratio(unsafe_publications, len(unsafe)),
        origin_applicable_count=len(origins),
        origin_resolution_accuracy=_ratio(origin_exact, len(origins)),
        expected_resolved_origin_count=len(expected_resolved),
        resolved_origin_count=resolved,
        origin_resolution_rate=_ratio(resolved, len(expected_resolved)),
        independence_inflation_case_count=sum(value > 0 for value in inflation),
        maximum_family_inflation=max((0, *inflation)),
        mandatory_review_case_count=len(mandatory),
        routed_mandatory_review_count=routed_mandatory,
        review_routing_recall=_ratio(routed_mandatory, len(mandatory)),
        review_routing_precision=_ratio(correctly_routed, len(routed)),
        verdict_stability_case_count=len(stability),
        stable_verdict_count=stable,
        verdict_stability_rate=_ratio(stable, len(stability)),
        machine_gate_passed=machine_gate,
        human_calibration_status=human_status,
        stage_exit_ready=machine_gate and human_approved,
        errors=tuple(errors),
        cases=results,
        artifacts=artifacts,
    )


def export_phase10_social_calibration_audit(
    project_root: str | Path,
) -> Phase10SocialCalibrationAudit:
    root = Path(project_root).resolve()
    audit = build_phase10_social_calibration_audit(root)
    target = root / _AUDIT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(audit.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return audit


def verify_phase10_social_calibration_audit(
    audit: Phase10SocialCalibrationAudit,
    project_root: str | Path,
) -> tuple[str, ...]:
    root = Path(project_root).resolve()
    errors = list(audit.errors)
    if not audit.machine_gate_passed:
        errors.append("Stage 10.8 deterministic benchmark gate did not pass")
    if audit.unsafe_publication_rate != 0:
        errors.append("unsafe-publication rate must be zero")
    if audit.review_routing_recall != 1:
        errors.append("mandatory-review recall must be 100%")
    if audit.independence_inflation_case_count:
        errors.append("independence inflation must be zero")
    if audit.model_calls or audit.search_calls or audit.network_calls:
        errors.append("Stage 10.8 replay must be zero-provider")
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


def _replay_case(case: dict[str, Any]) -> Phase10AdversarialCaseResult:
    case_id = str(case["case_id"])
    claim_id = uuid5(NAMESPACE_URL, f"{case_id}:claim")
    underlying_id = uuid5(NAMESPACE_URL, f"{case_id}:underlying")
    sources = tuple(
        _social_source(case, index, underlying_id)
        for index in range(int(case["social_source_count"]))
    )
    if case["include_non_social_corroboration"]:
        sources = (*sources, _underlying_source(case_id, underlying_id))
    evidence = tuple(
        _social_evidence(case, claim_id, source, index)
        for index, source in enumerate(sources[: int(case["social_source_count"])])
    )
    if case["include_non_social_corroboration"]:
        evidence = (
            *evidence,
            Evidence(
                evidence_id=uuid5(NAMESPACE_URL, f"{case_id}:underlying-evidence"),
                claim_id=claim_id,
                source_id=underlying_id,
                passage="The independent underlying record supplies the factual proposition.",
                stance=EvidenceStance.SUPPORTS,
                relevance_score=0.95,
                evidentiary_use=EvidentiaryUse.DECISIVE,
            ),
        )
    plan = InvestigationPlan(
        claim_id=claim_id,
        required_research_paths=(
            ResearchPath.PRIMARY,
            ResearchPath.CONTRADICTION,
        ),
        minimum_independent_families=1,
    )
    provenance = build_investigation_provenance(
        plan=plan,
        sources=sources,
        evidence=evidence,
    )
    claim = AtomicClaim(
        claim_id=claim_id,
        text=f"{case_id} material factual proposition.",
        checkworthiness=0.9,
    )
    ledger = build_argument_ledger(
        claim=claim,
        evidence=evidence,
        provenance=provenance,
    )
    social_policy = evaluate_social_evidence_constraints(
        ledger=ledger,
        sources=sources,
        evidence=evidence,
        provenance=provenance,
    )
    _, independence = analyze_source_independence(
        claim_id=claim_id,
        sources=sources,
        evidence=evidence,
        required_families=1,
    )
    first_eligibility = sources[0].social_eligibility
    assert first_eligibility is not None
    baseline_count = 1
    baseline_sources = sources[:baseline_count]
    baseline_evidence = evidence[:baseline_count]
    if case["include_non_social_corroboration"]:
        baseline_sources = (*baseline_sources, sources[-1])
        baseline_evidence = (*baseline_evidence, evidence[-1])
    baseline_provenance = build_investigation_provenance(
        plan=plan,
        sources=baseline_sources,
        evidence=baseline_evidence,
    )
    baseline_ledger = build_argument_ledger(
        claim=claim,
        evidence=baseline_evidence,
        provenance=baseline_provenance,
    )
    baseline_resolution = baseline_ledger.arguments[0].resolution.value
    expanded_resolution = ledger.arguments[0].resolution.value
    origin = sources[0].social_context.original_source
    actual_origin_resolved = bool(origin and origin.resolved)
    return Phase10AdversarialCaseResult(
        case_id=case_id,
        category=str(case["category"]),
        expected_eligibility=EvidenceEligibilityDecision(case["expected_eligibility"]),
        actual_eligibility=first_eligibility.decision,
        expected_usable=bool(case["expected_usable"]),
        actual_usable=(
            first_eligibility.decision is not EvidenceEligibilityDecision.INELIGIBLE
        ),
        mandatory_review=bool(case["mandatory_review"]),
        actual_review_routed=social_policy.requires_human_review,
        unsafe_if_published=bool(case["unsafe_if_published"]),
        publication_blocked=social_policy.publication_blocked,
        expected_family_count=int(case["expected_family_count"]),
        actual_family_count=independence.independent_family_count,
        origin_resolution_applicable=bool(case["origin_resolution_applicable"]),
        origin_expected_resolved=bool(case["origin_expected_resolved"]),
        origin_actual_resolved=actual_origin_resolved,
        verdict_stability_case=bool(case["verdict_stability_case"]),
        baseline_resolution=baseline_resolution,
        expanded_resolution=expanded_resolution,
        stable=baseline_resolution == expanded_resolution,
        policy_finding_codes=tuple(
            sorted({item.code.value for item in social_policy.findings})
        ),
    )


def _social_source(
    case: dict[str, Any],
    index: int,
    underlying_id: UUID,
) -> Source:
    case_id = str(case["case_id"])
    account = _account(str(case["account_variant"]), case_id, index)
    variant = str(case["post_variant"])
    original = None
    archive = None
    capture = SocialCaptureMethod.DIRECT_PUBLIC_PAGE
    origin_status = SocialContentOriginStatus.ORIGINAL_ACCESSIBLE
    post_type = SocialPostType.ORIGINAL
    unavailable = False
    eyewitness = variant == "eyewitness"
    if variant == "screenshot":
        post_type = SocialPostType.SCREENSHOT
        capture = SocialCaptureMethod.SCREENSHOT
        origin_status = SocialContentOriginStatus.SCREENSHOT_ONLY
        original = SocialOriginalSourceLink(
            relationship=SocialSourceRelationship.SCREENSHOT_OF,
            url=f"https://social.example/original/{case_id}",
        )
    elif variant == "repost":
        post_type = SocialPostType.REPOST
        original = SocialOriginalSourceLink(
            relationship=SocialSourceRelationship.REPOST_OF,
            url=f"https://social.example/shared/{case_id}",
        )
    elif variant == "deleted_unverified":
        capture = SocialCaptureMethod.COPIED_TEXT
        origin_status = SocialContentOriginStatus.COPIED_TEXT_ONLY
        unavailable = True
    elif variant == "deleted_verified_archive":
        capture = SocialCaptureMethod.RELIABLE_ARCHIVE
        origin_status = SocialContentOriginStatus.ARCHIVED_COPY
        unavailable = True
        archive = SocialArchiveReference(
            archive_url=f"https://archive.example/{case_id}",
            archive_provider="Recorded reliable archive fixture",
            captured_at=datetime.now(UTC),
            reliability_verified=True,
            verification_basis="Archive capture hash and provider record were verified.",
        )
    elif variant in {"resolved_link", "unresolved_link"}:
        resolved = variant == "resolved_link"
        post_type = SocialPostType.LINK_SHARE
        original = SocialOriginalSourceLink(
            relationship=SocialSourceRelationship.LINKS_TO,
            source_id=underlying_id if resolved else None,
            url=f"https://records.example/{case_id}",
            resolved=resolved,
        )
    context = SocialSourceContext(
        account=account,
        post_type=post_type,
        platform_post_id=f"{case_id}-{index}",
        posted_at=datetime(2026, 7, 1, 12, index, tzinfo=UTC),
        original_source=original,
        capture_method=capture,
        content_origin_status=origin_status,
        archive_reference=archive,
        eyewitness_claim=eyewitness,
        unavailable_or_deleted=unavailable,
    )
    source_id = uuid5(NAMESPACE_URL, f"{case_id}:social:{index}")
    return Source(
        source_id=source_id,
        url=f"https://platform-{index}.example/account/post/{case_id}",
        canonical_url=f"https://platform-{index}.example/account/post/{case_id}",
        title=f"{case_id} social item {index + 1}",
        source_type=SourceType.OTHER,
        publisher=f"Platform {index + 1}",
        retrieved_at=datetime.now(UTC),
        extraction_status=ExtractionStatus.EXTRACTED,
        distribution_medium=DistributionMedium.SOCIAL_PLATFORM,
        social_context=context,
        social_eligibility=evaluate_social_evidence_eligibility(context),
    )


def _account(variant: str, case_id: str, index: int) -> SocialAccountIdentity:
    if variant == "unresolved":
        return SocialAccountIdentity(
            platform=f"platform-{index}",
            identity_resolved=False,
        )
    authenticated = variant.startswith("authenticated")
    government = variant == "authenticated_government"
    return SocialAccountIdentity(
        platform=f"platform-{index}",
        handle=f"account-{case_id.lower()}-{index}",
        account_type=(
            SocialAccountType.GOVERNMENT
            if government
            else SocialAccountType.INDIVIDUAL
        ),
        authority_scope=(
            "Statements about the institution's own actions." if government else None
        ),
        authenticity_status=(
            SocialAuthenticityStatus.AUTHENTICATED
            if authenticated
            else SocialAuthenticityStatus.UNKNOWN
        ),
        authenticity_evidence=(
            (
                SocialAuthenticityEvidence(
                    evidence_type=(
                        SocialAuthenticityEvidenceType.OFFICIAL_WEBSITE_LINK
                    ),
                    reference_url=f"https://authority.example/{case_id}/social",
                    observed_at=datetime.now(UTC),
                    description="The official website links to this account.",
                ),
            )
            if authenticated
            else ()
        ),
    )


def _underlying_source(case_id: str, source_id: UUID) -> Source:
    return Source(
        source_id=source_id,
        url=f"https://records.example/{case_id}",
        canonical_url=f"https://records.example/{case_id}",
        title=f"{case_id} underlying record",
        source_type=SourceType.PRIMARY_DOCUMENT,
        publisher="Independent records authority",
        retrieved_at=datetime.now(UTC),
        extraction_status=ExtractionStatus.EXTRACTED,
        distribution_medium=DistributionMedium.DOCUMENT,
    )


def _social_evidence(
    case: dict[str, Any],
    claim_id: UUID,
    source: Source,
    index: int,
) -> Evidence:
    case_id = str(case["case_id"])
    return Evidence(
        evidence_id=uuid5(NAMESPACE_URL, f"{case_id}:social-evidence:{index}"),
        claim_id=claim_id,
        source_id=source.source_id,
        passage=f"{case_id} retained social passage {index + 1}.",
        stance=EvidenceStance(case["social_stance"]),
        relevance_score=0.85,
        evidentiary_use=EvidentiaryUse(case["evidentiary_use"]),
    )


def _write_review_packet(
    target: Path,
    fixture: dict[str, Any],
    results: tuple[Phase10AdversarialCaseResult, ...],
) -> None:
    result_by_id = {item.case_id: item for item in results}
    selected = [
        case
        for case in fixture["cases"]
        if case["mandatory_review"]
        or result_by_id[case["case_id"]].actual_review_routed
        != case["mandatory_review"]
        or result_by_id[case["case_id"]].actual_eligibility.value
        != case["expected_eligibility"]
        or (
            case["unsafe_if_published"]
            and not result_by_id[case["case_id"]].publication_blocked
        )
        or case["category"]
        in {"official_announcement", "primary_document_link"}
    ]
    packet = {
        "packet_id": "phase10-stage10.8-human-calibration-packet-v1",
        "status": "pending",
        "annotator_identity": None,
        "distinct_approver_identity": None,
        "reviewed_at": None,
        "instructions": [
            "Review the policy label, mandatory-review expectation, and "
            "publication safety outcome.",
            "Do not infer truth from engagement, badges, or repetition.",
            "Record approve, revise, or reject for every selected case.",
            "A distinct approver is required before Stage 10.8 can close."
        ],
        "cases": [
            {
                "case_id": case["case_id"],
                "category": case["category"],
                "summary": case["summary"],
                "expected_eligibility": case["expected_eligibility"],
                "machine_eligibility": result_by_id[case["case_id"]].actual_eligibility.value,
                "mandatory_review": case["mandatory_review"],
                "machine_review_routed": result_by_id[
                    case["case_id"]
                ].actual_review_routed,
                "unsafe_if_published": case["unsafe_if_published"],
                "machine_publication_blocked": result_by_id[
                    case["case_id"]
                ].publication_blocked,
                "policy_findings": list(
                    result_by_id[case["case_id"]].policy_finding_codes
                ),
                "review_decision": None,
                "revised_eligibility": None,
                "revised_mandatory_review": None,
                "revised_unsafe_if_published": None,
                "review_notes": None
            }
            for case in selected
        ],
        "approval": {
            "decision": None,
            "notes": None
        }
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")


def _human_packet_approved(
    packet: dict[str, Any],
    results: tuple[Phase10AdversarialCaseResult, ...],
) -> bool:
    del results
    if packet.get("status") != "approved":
        return False
    if not packet.get("annotator_identity") or not packet.get(
        "distinct_approver_identity"
    ):
        return False
    if (
        str(packet["annotator_identity"]).strip().casefold()
        == str(packet["distinct_approver_identity"]).strip().casefold()
    ):
        return False
    cases = packet.get("cases", [])
    return bool(cases) and all(
        item.get("review_decision") in {"approve", "revise", "reject"}
        and item.get("review_notes")
        for item in cases
    ) and packet.get("approval", {}).get("decision") in {
        "approve",
        "approve_with_revisions",
    }


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 1.0


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
