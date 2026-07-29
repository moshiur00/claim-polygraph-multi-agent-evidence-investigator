"""Backward-compatible contracts and deterministic policy for social material."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AnyHttpUrl, Field, JsonValue, model_validator

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.enums import (
    EvidenceEligibilityDecision,
    EvidentiaryUse,
    SocialAccountType,
    SocialAttributionScope,
    SocialAuthenticityEvidenceType,
    SocialAuthenticityStatus,
    SocialCaptureMethod,
    SocialContentOriginStatus,
    SocialPlatform,
    SocialPostType,
    SocialSourceRelationship,
    SocialUrlKind,
)


class ProviderResultMetadata(DomainModel):
    """Bounded provider attributes retained without changing their JSON values."""

    provider_id: str = Field(min_length=1, max_length=200)
    rank: int | None = Field(default=None, ge=1)
    result_id: str | None = Field(default=None, max_length=500)
    attributes: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def bound_untrusted_metadata(self) -> ProviderResultMetadata:
        if len(self.attributes) > 25:
            raise ValueError("provider metadata may contain at most 25 attributes")
        forbidden = {"api_key", "apikey", "password", "secret", "token"}
        if forbidden.intersection(key.casefold() for key in self.attributes):
            raise ValueError("provider metadata contains a forbidden credential field")
        encoded = json.dumps(self.attributes, ensure_ascii=False, separators=(",", ":"))
        if len(encoded) > 20_000:
            raise ValueError("provider metadata exceeds the 20,000 character limit")
        return self


class SocialUrlCandidate(DomainModel):
    """Fetch-free classification of a recognized public social URL."""

    platform: SocialPlatform
    url_kind: SocialUrlKind
    canonical_url: AnyHttpUrl
    account_handle: str | None = Field(default=None, max_length=300)
    platform_post_id: str | None = Field(default=None, max_length=500)
    normalization_version: Literal["social-url-v1"] = "social-url-v1"
    content_fetch_attempted: Literal[False] = False


class SocialAccountIdentity(DomainModel):
    """Recorded account identity without treating a badge as factual authority."""

    platform: str = Field(min_length=1, max_length=100)
    identity_resolved: bool = True
    handle: str | None = Field(default=None, max_length=200)
    platform_account_id: str | None = Field(default=None, max_length=300)
    display_name: str | None = Field(default=None, max_length=500)
    account_type: SocialAccountType = SocialAccountType.UNKNOWN
    authority_scope: str | None = Field(default=None, max_length=1_000)
    profile_url: AnyHttpUrl | None = None
    authenticity_status: SocialAuthenticityStatus = SocialAuthenticityStatus.UNKNOWN
    authenticity_basis: str | None = Field(default=None, max_length=2_000)
    authenticity_evidence: tuple[SocialAuthenticityEvidence, ...] = ()

    @model_validator(mode="after")
    def validate_identity(self) -> SocialAccountIdentity:
        if (
            self.identity_resolved
            and not self.handle
            and not self.platform_account_id
            and not self.profile_url
        ):
            raise ValueError("social account identity requires a handle, ID or profile URL")
        if not self.identity_resolved and (
            self.handle or self.platform_account_id or self.profile_url
        ):
            raise ValueError("unresolved social identity cannot contain resolved identifiers")
        if (
            not self.identity_resolved
            and self.authenticity_status is not SocialAuthenticityStatus.UNKNOWN
        ):
            raise ValueError("unresolved social identity must have unknown authenticity")
        documented_statuses = {
            SocialAuthenticityStatus.AUTHENTICATED,
            SocialAuthenticityStatus.DISPUTED,
        }
        if (
            self.authenticity_status in documented_statuses
            and not self.authenticity_basis
            and not self.authenticity_evidence
        ):
            raise ValueError(
                "authenticated or disputed social accounts require authenticity evidence"
            )
        if (
            self.authenticity_status is SocialAuthenticityStatus.UNKNOWN
            and (self.authenticity_basis or self.authenticity_evidence)
        ):
            raise ValueError("unknown authenticity cannot have authenticity evidence")
        institutional_types = {
            SocialAccountType.INSTITUTION,
            SocialAccountType.GOVERNMENT,
            SocialAccountType.ACADEMIC_INSTITUTION,
            SocialAccountType.NEWS_ORGANIZATION,
        }
        if self.authority_scope and (
            self.account_type not in institutional_types or not self.identity_resolved
        ):
            raise ValueError("authority_scope is only valid for institutional accounts")
        return self


class SocialAuthenticityEvidence(DomainModel):
    """One auditable, non-secret authenticity observation."""

    evidence_type: SocialAuthenticityEvidenceType
    reference_url: AnyHttpUrl | None = None
    observed_at: datetime
    description: str = Field(min_length=5, max_length=2_000)
    verified_by: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def reference_required_for_external_evidence(self) -> SocialAuthenticityEvidence:
        if (
            self.evidence_type
            in {
                SocialAuthenticityEvidenceType.OFFICIAL_WEBSITE_LINK,
                SocialAuthenticityEvidenceType.RELIABLE_ARCHIVE,
            }
            and self.reference_url is None
        ):
            raise ValueError("external authenticity evidence requires reference_url")
        return self


class SocialArchiveReference(DomainModel):
    """Metadata for an archive; never proof merely because a URL exists."""

    archive_url: AnyHttpUrl
    archive_provider: str = Field(min_length=1, max_length=300)
    captured_at: datetime | None = None
    content_hash: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    reliability_verified: bool = False
    verification_basis: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def verified_archive_requires_basis(self) -> SocialArchiveReference:
        if self.reliability_verified and not self.verification_basis:
            raise ValueError("verified archive reliability requires verification_basis")
        return self


class SocialOriginalSourceLink(DomainModel):
    """Typed derivation link used to recover origins and prevent double counting."""

    relationship: SocialSourceRelationship
    source_id: UUID | None = None
    url: AnyHttpUrl | None = None
    resolved: bool = False

    @model_validator(mode="after")
    def require_target(self) -> SocialOriginalSourceLink:
        if self.source_id is None and self.url is None:
            raise ValueError("original-source linkage requires a source_id or URL")
        if self.resolved and self.source_id is None:
            raise ValueError("resolved original-source linkage requires source_id")
        return self


class SocialSourceContext(DomainModel):
    """Social-media facts retained separately from source authority."""

    account: SocialAccountIdentity
    post_type: SocialPostType = SocialPostType.UNKNOWN
    platform_post_id: str | None = Field(default=None, max_length=500)
    posted_at: datetime | None = None
    original_source: SocialOriginalSourceLink | None = None
    capture_method: SocialCaptureMethod = SocialCaptureMethod.UNKNOWN
    content_origin_status: SocialContentOriginStatus = SocialContentOriginStatus.UNKNOWN
    attribution_scope: SocialAttributionScope = SocialAttributionScope.UNSPECIFIED
    attributed_text: str | None = Field(default=None, max_length=5_000)
    archive_reference: SocialArchiveReference | None = None
    eyewitness_claim: bool = False
    unavailable_or_deleted: bool = False

    @model_validator(mode="after")
    def derivation_types_require_origin(self) -> SocialSourceContext:
        derived_types = {
            SocialPostType.REPOST,
            SocialPostType.QUOTE,
            SocialPostType.SCREENSHOT,
            SocialPostType.LINK_SHARE,
        }
        if self.post_type in derived_types and self.original_source is None:
            raise ValueError("derived social material requires original_source linkage")
        copied_methods = {
            SocialCaptureMethod.SCREENSHOT: SocialContentOriginStatus.SCREENSHOT_ONLY,
            SocialCaptureMethod.COPIED_TEXT: SocialContentOriginStatus.COPIED_TEXT_ONLY,
        }
        expected_origin = copied_methods.get(self.capture_method)
        if expected_origin and self.content_origin_status is not expected_origin:
            raise ValueError(
                "screenshot or copied-text capture requires matching origin status"
            )
        if (
            self.content_origin_status is SocialContentOriginStatus.ARCHIVED_COPY
            and self.archive_reference is None
        ):
            raise ValueError("archived social content requires archive_reference")
        if (
            self.capture_method is SocialCaptureMethod.RELIABLE_ARCHIVE
            and (
                self.archive_reference is None
                or not self.archive_reference.reliability_verified
            )
        ):
            raise ValueError(
                "reliable-archive capture requires a verified archive reference"
            )
        if self.unavailable_or_deleted and self.content_origin_status not in {
            SocialContentOriginStatus.ORIGINAL_UNAVAILABLE,
            SocialContentOriginStatus.ARCHIVED_COPY,
            SocialContentOriginStatus.SCREENSHOT_ONLY,
            SocialContentOriginStatus.COPIED_TEXT_ONLY,
        }:
            raise ValueError(
                "unavailable social material requires a non-accessible origin status"
            )
        if self.attributed_text and self.attribution_scope is SocialAttributionScope.UNSPECIFIED:
            raise ValueError("attributed_text requires an explicit attribution_scope")
        return self


class SocialEvidenceEligibility(DomainModel):
    """Deterministic permitted uses for one classified social source."""

    decision: EvidenceEligibilityDecision
    allowed_uses: tuple[EvidentiaryUse, ...] = ()
    decisive_use_allowed: bool = False
    independent_proof_allowed: bool = False
    requires_corroboration: bool = True
    requires_human_review: bool = False
    reason_codes: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def keep_decision_and_uses_consistent(self) -> SocialEvidenceEligibility:
        if len(self.allowed_uses) != len(set(self.allowed_uses)):
            raise ValueError("allowed evidentiary uses must be unique")
        if self.decision is EvidenceEligibilityDecision.INELIGIBLE:
            if self.allowed_uses != (EvidentiaryUse.DISCOVERY_LEAD,):
                raise ValueError("ineligible social material may only remain a lead")
            if self.decisive_use_allowed or self.independent_proof_allowed:
                raise ValueError("ineligible social material cannot be decisive or independent")
        if self.decisive_use_allowed and EvidentiaryUse.DECISIVE not in self.allowed_uses:
            raise ValueError("decisive permission requires decisive in allowed_uses")
        return self


def evaluate_social_evidence_eligibility(
    context: SocialSourceContext,
) -> SocialEvidenceEligibility:
    """Apply the Stage 10.1 conservative, model-independent eligibility policy."""

    account = context.account
    if context.capture_method in {
        SocialCaptureMethod.SCREENSHOT,
        SocialCaptureMethod.COPIED_TEXT,
    }:
        return _lead_only("unverified_copy_requires_original", review=True)

    if context.unavailable_or_deleted:
        archive_verified = bool(
            context.archive_reference
            and context.archive_reference.reliability_verified
            and context.capture_method is SocialCaptureMethod.RELIABLE_ARCHIVE
        )
        if not archive_verified:
            return _lead_only("unavailable_original_without_verified_archive", review=True)
        return SocialEvidenceEligibility(
            decision=EvidenceEligibilityDecision.CONDITIONAL,
            allowed_uses=(
                EvidentiaryUse.ATTRIBUTED_STATEMENT,
                EvidentiaryUse.CONTEXT,
            ),
            requires_corroboration=True,
            requires_human_review=True,
            reason_codes=("verified_archive_still_requires_attribution_review",),
        )

    if context.capture_method is SocialCaptureMethod.SEARCH_RESULT_SNIPPET:
        return SocialEvidenceEligibility(
            decision=EvidenceEligibilityDecision.CONDITIONAL,
            allowed_uses=(
                EvidentiaryUse.DISCOVERY_LEAD,
                EvidentiaryUse.CONTEXT,
            ),
            requires_corroboration=True,
            requires_human_review=False,
            reason_codes=("search_snippet_not_authenticity_evidence",),
        )

    if account.authenticity_status is SocialAuthenticityStatus.DISPUTED:
        return _lead_only("authenticity_disputed", review=True)

    if context.post_type in {
        SocialPostType.REPOST,
        SocialPostType.QUOTE,
        SocialPostType.SCREENSHOT,
    }:
        reason = (
            "unresolved_shared_origin"
            if not context.original_source or not context.original_source.resolved
            else "derived_material_not_independent"
        )
        return _lead_only(reason, review=context.eyewitness_claim)

    if account.authenticity_status is not SocialAuthenticityStatus.AUTHENTICATED:
        return SocialEvidenceEligibility(
            decision=EvidenceEligibilityDecision.CONDITIONAL,
            allowed_uses=(
                EvidentiaryUse.DISCOVERY_LEAD,
                EvidentiaryUse.CONTEXT,
            ),
            requires_corroboration=True,
            requires_human_review=context.eyewitness_claim,
            reason_codes=("account_not_authenticated",),
        )

    if context.post_type is SocialPostType.LINK_SHARE:
        resolved = bool(context.original_source and context.original_source.resolved)
        return SocialEvidenceEligibility(
            decision=EvidenceEligibilityDecision.CONDITIONAL,
            allowed_uses=(
                EvidentiaryUse.DISCOVERY_LEAD,
                EvidentiaryUse.CONTEXT,
            ),
            requires_corroboration=True,
            requires_human_review=not resolved,
            reason_codes=(
                "cite_underlying_source" if resolved else "underlying_source_unresolved",
            ),
        )

    if context.eyewitness_claim:
        return SocialEvidenceEligibility(
            decision=EvidenceEligibilityDecision.CONDITIONAL,
            allowed_uses=(
                EvidentiaryUse.QUALIFIED_OBSERVATION,
                EvidentiaryUse.CONTEXT,
            ),
            requires_corroboration=True,
            requires_human_review=True,
            reason_codes=("eyewitness_requires_corroboration",),
        )

    if account.account_type in {
        SocialAccountType.INSTITUTION,
        SocialAccountType.GOVERNMENT,
    }:
        if not account.authority_scope:
            return SocialEvidenceEligibility(
                decision=EvidenceEligibilityDecision.CONDITIONAL,
                allowed_uses=(
                    EvidentiaryUse.ATTRIBUTED_STATEMENT,
                    EvidentiaryUse.CONTEXT,
                ),
                requires_corroboration=True,
                requires_human_review=True,
                reason_codes=("institutional_authority_scope_not_recorded",),
            )
        return SocialEvidenceEligibility(
            decision=EvidenceEligibilityDecision.ELIGIBLE,
            allowed_uses=(
                EvidentiaryUse.ATTRIBUTED_STATEMENT,
                EvidentiaryUse.CONTEXT,
            ),
            independent_proof_allowed=True,
            requires_corroboration=False,
            reason_codes=("first_party_statement_within_scope_only",),
        )

    if account.account_type is SocialAccountType.ACADEMIC_INSTITUTION:
        return SocialEvidenceEligibility(
            decision=EvidenceEligibilityDecision.CONDITIONAL,
            allowed_uses=(
                EvidentiaryUse.ATTRIBUTED_STATEMENT,
                EvidentiaryUse.DISCOVERY_LEAD,
                EvidentiaryUse.CONTEXT,
            ),
            requires_corroboration=True,
            reason_codes=("research_claim_requires_underlying_paper_or_data",),
        )

    return SocialEvidenceEligibility(
        decision=EvidenceEligibilityDecision.CONDITIONAL,
        allowed_uses=(
            EvidentiaryUse.ATTRIBUTED_STATEMENT,
            EvidentiaryUse.CONTEXT,
        ),
        requires_corroboration=True,
        reason_codes=("statement_only_not_underlying_fact",),
    )


def _lead_only(reason: str, *, review: bool) -> SocialEvidenceEligibility:
    return SocialEvidenceEligibility(
        decision=EvidenceEligibilityDecision.INELIGIBLE,
        allowed_uses=(EvidentiaryUse.DISCOVERY_LEAD,),
        requires_corroboration=True,
        requires_human_review=review,
        reason_codes=(reason,),
    )
