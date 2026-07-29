"""Deterministic argument and publication constraints for social evidence."""

from enum import StrEnum
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.argument import (
    ArgumentLedger,
    PropositionResolution,
)
from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.enums import (
    DistributionMedium,
    EvidenceEligibilityDecision,
    EvidentiaryUse,
)
from claim_polygraph_ng.domain.models import Evidence, Source
from claim_polygraph_ng.domain.provenance import (
    InvestigationProvenance,
    SocialRiskSeverity,
)


class SocialConstraintCode(StrEnum):
    APPROVED_RECORD_MISSING = "approved_record_missing"
    INELIGIBLE_EVIDENCE_REFERENCED = "ineligible_evidence_referenced"
    EVIDENTIARY_USE_UNSPECIFIED = "evidentiary_use_unspecified"
    EVIDENTIARY_USE_NOT_ALLOWED = "evidentiary_use_not_allowed"
    DECISIVE_USE_NOT_ALLOWED = "decisive_use_not_allowed"
    NON_SOCIAL_CORROBORATION_MISSING = "non_social_corroboration_missing"
    UNRESOLVED_SOCIAL_RISK = "unresolved_social_risk"


class SocialConstraintFinding(DomainModel):
    finding_id: str = Field(pattern=r"^social-constraint-[0-9a-f]{16}$")
    code: SocialConstraintCode
    severity: SocialRiskSeverity
    reason: str = Field(min_length=10, max_length=2_000)
    proposition_id: UUID | None = None
    source_id: UUID | None = None
    evidence_ids: tuple[UUID, ...] = ()


class SocialEvidencePolicyResult(DomainModel):
    """Auditable fail-closed decision over argument uses of social material."""

    claim_id: UUID
    policy_version: str = Field(
        default="social-argument-publication-policy-v1",
        pattern=r"^social-argument-publication-policy-v1$",
    )
    findings: tuple[SocialConstraintFinding, ...] = ()
    social_evidence_ids: tuple[UUID, ...] = ()
    non_social_evidence_ids: tuple[UUID, ...] = ()
    requires_human_review: bool
    publication_blocked: bool
    blocking_reasons: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_policy_result(self) -> "SocialEvidencePolicyResult":
        if self.publication_blocked != bool(self.blocking_reasons):
            raise ValueError("publication blocking requires explicit reasons")
        if self.publication_blocked and not self.requires_human_review:
            raise ValueError("blocked social evidence requires human review")
        return self


def evaluate_social_evidence_constraints(
    *,
    ledger: ArgumentLedger,
    sources: tuple[Source, ...],
    evidence: tuple[Evidence, ...],
    provenance: InvestigationProvenance | None = None,
) -> SocialEvidencePolicyResult:
    """Restrict social items to approved uses and require ordinary corroboration."""
    source_by_id = {item.source_id: item for item in sources}
    evidence_by_id = {item.evidence_id: item for item in evidence}
    findings: list[SocialConstraintFinding] = []

    def add(
        code: SocialConstraintCode,
        severity: SocialRiskSeverity,
        reason: str,
        *,
        proposition_id: UUID | None = None,
        source_id: UUID | None = None,
        evidence_ids: tuple[UUID, ...] = (),
    ) -> None:
        identity = "|".join(
            (
                code.value,
                str(proposition_id or ""),
                str(source_id or ""),
                *(str(item) for item in evidence_ids),
            )
        )
        findings.append(
            SocialConstraintFinding(
                finding_id=(f"social-constraint-{uuid5(NAMESPACE_URL, identity).hex[:16]}"),
                code=code,
                severity=severity,
                reason=reason,
                proposition_id=proposition_id,
                source_id=source_id,
                evidence_ids=evidence_ids,
            )
        )

    referenced = {
        evidence_id
        for argument in ledger.arguments
        for evidence_id in (
            *argument.supporting_evidence_ids,
            *argument.contradictory_evidence_ids,
            *argument.qualifying_evidence_ids,
            *argument.contextual_evidence_ids,
        )
    }
    social_ids: set[UUID] = set()
    non_social_ids: set[UUID] = set()
    for evidence_id in sorted(referenced, key=str):
        item = evidence_by_id.get(evidence_id)
        if item is None:
            add(
                SocialConstraintCode.APPROVED_RECORD_MISSING,
                SocialRiskSeverity.BLOCKING,
                "The argument references an approved evidence record that is unavailable.",
                evidence_ids=(evidence_id,),
            )
            continue
        source = source_by_id.get(item.source_id)
        if source is None:
            add(
                SocialConstraintCode.APPROVED_RECORD_MISSING,
                SocialRiskSeverity.BLOCKING,
                "The argument references evidence whose source record is unavailable.",
                source_id=item.source_id,
                evidence_ids=(evidence_id,),
            )
            continue
        if source.distribution_medium is not DistributionMedium.SOCIAL_PLATFORM:
            non_social_ids.add(evidence_id)
            continue
        social_ids.add(evidence_id)
        eligibility = source.social_eligibility
        if eligibility is None or eligibility.decision is EvidenceEligibilityDecision.INELIGIBLE:
            add(
                SocialConstraintCode.INELIGIBLE_EVIDENCE_REFERENCED,
                SocialRiskSeverity.BLOCKING,
                "The argument references social material that is not eligible as evidence.",
                source_id=source.source_id,
                evidence_ids=(evidence_id,),
            )
            continue
        if item.evidentiary_use is EvidentiaryUse.UNSPECIFIED:
            add(
                SocialConstraintCode.EVIDENTIARY_USE_UNSPECIFIED,
                SocialRiskSeverity.BLOCKING,
                "Social evidence used in an argument requires an explicit "
                "approved evidentiary use.",
                source_id=source.source_id,
                evidence_ids=(evidence_id,),
            )
        elif item.evidentiary_use not in eligibility.allowed_uses:
            add(
                SocialConstraintCode.EVIDENTIARY_USE_NOT_ALLOWED,
                SocialRiskSeverity.BLOCKING,
                "The assigned use of this social item is outside its deterministic eligibility.",
                source_id=source.source_id,
                evidence_ids=(evidence_id,),
            )

    material_ids = {item.proposition_id for item in ledger.propositions if item.material}
    for argument in ledger.arguments:
        if argument.proposition_id not in material_ids:
            continue
        decisive_ids: tuple[UUID, ...] = ()
        if argument.resolution is PropositionResolution.SUPPORTED:
            decisive_ids = argument.supporting_evidence_ids
        elif argument.resolution is PropositionResolution.CONTRADICTED:
            decisive_ids = argument.contradictory_evidence_ids
        if not decisive_ids:
            continue
        social_decisive = tuple(item for item in decisive_ids if item in social_ids)
        if not social_decisive:
            continue
        for evidence_id in social_decisive:
            source = source_by_id[evidence_by_id[evidence_id].source_id]
            if not source.social_eligibility.decisive_use_allowed:
                add(
                    SocialConstraintCode.DECISIVE_USE_NOT_ALLOWED,
                    SocialRiskSeverity.CAUTION,
                    "Social material may inform the proposition but cannot "
                    "independently decide it.",
                    proposition_id=argument.proposition_id,
                    source_id=source.source_id,
                    evidence_ids=(evidence_id,),
                )
        if not any(item in non_social_ids for item in decisive_ids):
            add(
                SocialConstraintCode.NON_SOCIAL_CORROBORATION_MISSING,
                SocialRiskSeverity.BLOCKING,
                "A decisive factual proposition supported by social material "
                "lacks non-social corroboration.",
                proposition_id=argument.proposition_id,
                evidence_ids=social_decisive,
            )

    if provenance and any(
        item.severity in {SocialRiskSeverity.CAUTION, SocialRiskSeverity.BLOCKING}
        for item in provenance.social_risk_findings
    ):
        add(
            SocialConstraintCode.UNRESOLVED_SOCIAL_RISK,
            SocialRiskSeverity.CAUTION,
            "One or more persisted social-source risks remain unresolved and require review.",
        )

    unique = {item.finding_id: item for item in findings}
    ordered = tuple(unique[key] for key in sorted(unique))
    blocking_reasons = tuple(
        item.reason for item in ordered if item.severity is SocialRiskSeverity.BLOCKING
    )
    return SocialEvidencePolicyResult(
        claim_id=ledger.claim_id,
        findings=ordered,
        social_evidence_ids=tuple(sorted(social_ids, key=str)),
        non_social_evidence_ids=tuple(sorted(non_social_ids, key=str)),
        requires_human_review=bool(ordered),
        publication_blocked=bool(blocking_reasons),
        blocking_reasons=blocking_reasons,
    )
