"""Typed routing contracts for verification-construction eligibility."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel


class ConstructionEligibilityRoute(StrEnum):
    DETERMINISTIC = "deterministic"
    ASSISTED = "assisted"
    HUMAN_REVIEW = "human_review"
    NOT_APPLICABLE = "not_applicable"


class ConstructionEligibilityReason(StrEnum):
    COMPLETE_LINKED_GROUP = "complete_linked_group"
    ORDINARY_NUMERICAL_LANGUAGE = "ordinary_numerical_language"
    ORDINARY_TEMPORAL_LANGUAGE = "ordinary_temporal_language"
    STATUS_OR_ABSENCE = "status_or_absence"
    BOUNDED_CONSTRUCTION_AMBIGUITY = "bounded_construction_ambiguity"
    INCOMPLETE_MATERIAL_OPERANDS = "incomplete_material_operands"
    OPEN_WORLD_SUPERLATIVE = "open_world_superlative"
    CAUSAL_CLAIM = "causal_claim"
    QUALITATIVE_GENERALIZATION = "qualitative_generalization"
    NO_TYPED_VERIFICATION_BASIS = "no_typed_verification_basis"


class ConstructionEligibilityDecision(DomainModel):
    target_id: str = Field(min_length=3, max_length=100)
    group_id: str | None = Field(default=None, pattern=r"^group-[0-9]{3}$")
    route: ConstructionEligibilityRoute
    reasons: tuple[ConstructionEligibilityReason, ...] = Field(min_length=1)
    candidate_ids: tuple[str, ...] = ()
    linked_construction_id: str | None = None
    requires_human_review: bool
    explanation: str = Field(min_length=3, max_length=2_000)

    @model_validator(mode="after")
    def validate_route(self) -> ConstructionEligibilityDecision:
        if len(self.candidate_ids) != len(set(self.candidate_ids)):
            raise ValueError("eligibility candidate IDs must be unique")
        if self.route is ConstructionEligibilityRoute.HUMAN_REVIEW:
            if not self.requires_human_review:
                raise ValueError("human-review route must require human review")
        elif self.requires_human_review:
            raise ValueError("only the human-review route may require review at this boundary")
        if (
            self.route is ConstructionEligibilityRoute.DETERMINISTIC
            and self.linked_construction_id is None
        ):
            raise ValueError("deterministic routing requires a complete linked construction")
        return self


class ConstructionEligibilityPacket(DomainModel):
    claim_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_extraction_version: str = Field(min_length=3, max_length=100)
    linked_construction_version: str = Field(min_length=3, max_length=100)
    decisions: tuple[ConstructionEligibilityDecision, ...] = Field(min_length=1)
    deterministic_count: int = Field(ge=0)
    assisted_count: int = Field(ge=0)
    human_review_count: int = Field(ge=0)
    not_applicable_count: int = Field(ge=0)
    requires_human_review: bool
    version: str = "construction-eligibility-v1"

    @model_validator(mode="after")
    def validate_counts(self) -> ConstructionEligibilityPacket:
        counts = {
            route: sum(item.route is route for item in self.decisions)
            for route in ConstructionEligibilityRoute
        }
        expected = {
            ConstructionEligibilityRoute.DETERMINISTIC: self.deterministic_count,
            ConstructionEligibilityRoute.ASSISTED: self.assisted_count,
            ConstructionEligibilityRoute.HUMAN_REVIEW: self.human_review_count,
            ConstructionEligibilityRoute.NOT_APPLICABLE: self.not_applicable_count,
        }
        if counts != expected:
            raise ValueError("eligibility route counts differ from decisions")
        if self.requires_human_review != bool(self.human_review_count):
            raise ValueError("packet review flag differs from decisions")
        target_ids = [item.target_id for item in self.decisions]
        if len(target_ids) != len(set(target_ids)):
            raise ValueError("eligibility target IDs must be unique")
        return self
