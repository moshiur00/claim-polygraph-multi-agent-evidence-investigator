"""Evidence-family and source-independence artifacts."""

from uuid import UUID

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel


class EvidenceFamily(DomainModel):
    """Sources grouped because they may not be independent confirmations."""

    family_id: UUID
    source_ids: tuple[UUID, ...]
    evidence_ids: tuple[UUID, ...]
    hostnames: tuple[str, ...]
    publishers: tuple[str, ...] = ()
    grouping_reasons: tuple[str, ...]

    @model_validator(mode="after")
    def family_must_have_members(self) -> "EvidenceFamily":
        if not self.source_ids or not self.evidence_ids:
            raise ValueError("evidence families require sources and evidence")
        return self


class IndependenceAnalysis(DomainModel):
    """Auditable deterministic evidence-family analysis."""

    claim_id: UUID
    required_independent_families: int = Field(ge=1, le=10)
    families: tuple[EvidenceFamily, ...]
    limitations: tuple[str, ...] = ()

    @property
    def independent_family_count(self) -> int:
        return len(self.families)

    @property
    def requirement_met(self) -> bool:
        return self.independent_family_count >= self.required_independent_families
