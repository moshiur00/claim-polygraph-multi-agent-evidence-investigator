"""Typed deterministic judgment-policy artifacts."""

from enum import StrEnum
from uuid import UUID

from pydantic import Field

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.enums import VerdictLabel


class JudgmentReasonCode(StrEnum):
    LABEL_ALLOWED = "label_allowed"
    LABEL_INCOMPATIBLE_WITH_SUPPORTED = "label_incompatible_with_supported"
    LABEL_INCOMPATIBLE_WITH_CONTRADICTED = "label_incompatible_with_contradicted"
    LABEL_INCOMPATIBLE_WITH_QUALIFIED = "label_incompatible_with_qualified"
    LABEL_INCOMPATIBLE_WITH_UNRESOLVED = "label_incompatible_with_unresolved"
    BLOCKING_CHALLENGE = "blocking_challenge"
    MIXED_MATERIAL_RESOLUTIONS = "mixed_material_resolutions"


class JudgmentPolicyTrace(DomainModel):
    """Auditable distinction between model proposal and enforced result."""

    claim_id: UUID
    verdict_id: UUID
    policy_version: str = Field(default="judgment-policy-v1", pattern=r"^judgment-policy-v1$")
    proposed_label: VerdictLabel
    enforced_label: VerdictLabel
    allowed_labels: tuple[VerdictLabel, ...] = Field(min_length=1)
    changed: bool
    applied: bool = True
    human_review_required: bool
    reason_codes: tuple[JudgmentReasonCode, ...] = Field(min_length=1)
    rationale: str = Field(min_length=10, max_length=3_000)
