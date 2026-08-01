"""Typed linked-assertion contracts for compound verification claims."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel


class LinkedAssertionComponentKind(StrEnum):
    VALUE_CONDITION = "value_condition"
    DATE_CONTEXT = "date_context"
    RANK_CONTEXT = "rank_context"
    STATUS_CONTEXT = "status_context"
    CONSEQUENCE = "consequence"


class LinkedAssertionRelation(StrEnum):
    AND = "and"
    COMPARES_TO = "compares_to"
    RANGE_BOUNDS = "range_bounds"
    PROJECTS_TO = "projects_to"
    QUALIFIES = "qualifies"
    IMPLIES = "implies"


class LinkedAssertionConstructionState(StrEnum):
    CONSTRUCTED = "constructed"
    UNCONSTRUCTED = "unconstructed"


class LinkedAssertionComponent(DomainModel):
    component_id: str = Field(pattern=r"^component-[0-9]{3}$")
    kind: LinkedAssertionComponentKind
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    quoted_text: str = Field(min_length=1, max_length=2_000)
    candidate_ids: tuple[str, ...] = ()
    decimal_value: Decimal | None = None
    decimal_scale: Decimal | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, min_length=1, max_length=100)
    comparator: str | None = Field(default=None, min_length=1, max_length=100)
    date_value: date | None = None
    date_precision: str | None = Field(default=None, pattern=r"^(year|month|day)$")
    ordinal_rank: int | None = Field(default=None, ge=1)
    status: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_component(self) -> LinkedAssertionComponent:
        if self.end_char <= self.start_char:
            raise ValueError("component end must follow its start")
        if len(self.candidate_ids) != len(set(self.candidate_ids)):
            raise ValueError("component candidate IDs must be unique")
        if self.kind is LinkedAssertionComponentKind.VALUE_CONDITION and (
            self.decimal_value is None or self.decimal_scale is None
        ):
            raise ValueError("value conditions require a decimal value and scale")
        if self.kind is LinkedAssertionComponentKind.DATE_CONTEXT and (
            self.date_value is None or self.date_precision is None
        ):
            raise ValueError("date context requires a value and precision")
        if self.kind is LinkedAssertionComponentKind.RANK_CONTEXT and self.ordinal_rank is None:
            raise ValueError("rank context requires an ordinal")
        if self.kind is LinkedAssertionComponentKind.STATUS_CONTEXT and self.status is None:
            raise ValueError("status context requires a status")
        if self.kind is not LinkedAssertionComponentKind.CONSEQUENCE and not self.candidate_ids:
            raise ValueError("typed components require candidate provenance")
        return self


class LinkedAssertionEdge(DomainModel):
    source_component_id: str = Field(pattern=r"^component-[0-9]{3}$")
    target_component_id: str = Field(pattern=r"^component-[0-9]{3}$")
    relation: LinkedAssertionRelation

    @model_validator(mode="after")
    def reject_self_edge(self) -> LinkedAssertionEdge:
        if self.source_component_id == self.target_component_id:
            raise ValueError("linked assertion edges cannot be self-referential")
        return self


class LinkedAssertionConstruction(DomainModel):
    construction_id: UUID
    group_id: str = Field(pattern=r"^group-[0-9]{3}$")
    group_kind: str = Field(min_length=3, max_length=100)
    claim_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    state: LinkedAssertionConstructionState
    required_candidate_ids: tuple[str, ...]
    components: tuple[LinkedAssertionComponent, ...] = ()
    edges: tuple[LinkedAssertionEdge, ...] = ()
    failure_code: str | None = Field(
        default=None, pattern=r"^[a-z0-9_]+$", min_length=3, max_length=100
    )
    explanation: str = Field(min_length=3, max_length=2_000)
    construction_version: str = "linked-assertion-construction-v1"

    @model_validator(mode="after")
    def validate_construction(self) -> LinkedAssertionConstruction:
        if len(self.required_candidate_ids) != len(set(self.required_candidate_ids)):
            raise ValueError("required candidate IDs must be unique")
        if self.state is LinkedAssertionConstructionState.CONSTRUCTED:
            if len(self.components) < 2 or not self.edges:
                raise ValueError("constructed groups require components and links")
            if self.failure_code is not None:
                raise ValueError("constructed groups cannot retain a failure code")
            component_ids = {item.component_id for item in self.components}
            if len(component_ids) != len(self.components):
                raise ValueError("component IDs must be unique")
            covered = {
                candidate_id
                for component in self.components
                for candidate_id in component.candidate_ids
            }
            assigned = [
                candidate_id
                for component in self.components
                for candidate_id in component.candidate_ids
            ]
            if covered != set(self.required_candidate_ids):
                raise ValueError("constructed group must cover every material candidate")
            if len(assigned) != len(set(assigned)):
                raise ValueError("each material candidate must be assigned exactly once")
            if any(
                edge.source_component_id not in component_ids
                or edge.target_component_id not in component_ids
                for edge in self.edges
            ):
                raise ValueError("edge references an unknown component")
        else:
            if self.failure_code is None:
                raise ValueError("unconstructed groups require a failure code")
            if self.components or self.edges:
                raise ValueError("failed construction cannot expose partial assertions")
        return self


class LinkedAssertionPacket(DomainModel):
    claim_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_extraction_version: str = Field(min_length=3, max_length=100)
    constructions: tuple[LinkedAssertionConstruction, ...]
    constructed_count: int = Field(ge=0)
    unconstructed_count: int = Field(ge=0)
    material_candidate_count: int = Field(ge=0)
    covered_material_candidate_count: int = Field(ge=0)
    material_coverage: float = Field(ge=0, le=1)
    requires_human_review: bool

    @model_validator(mode="after")
    def validate_counts(self) -> LinkedAssertionPacket:
        constructed = sum(
            item.state is LinkedAssertionConstructionState.CONSTRUCTED
            for item in self.constructions
        )
        if constructed != self.constructed_count:
            raise ValueError("constructed count differs from packet contents")
        if len(self.constructions) - constructed != self.unconstructed_count:
            raise ValueError("unconstructed count differs from packet contents")
        if self.covered_material_candidate_count > self.material_candidate_count:
            raise ValueError("covered material candidates exceed the total")
        return self
