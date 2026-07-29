"""Typed results for authoritative verification and argument fan-out."""

from uuid import UUID

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.provenance import InvestigationProvenance
from claim_polygraph_ng.domain.verification import (
    ContextVerification,
    VerificationPacketV2,
)


class EvidenceCoverageCheck(DomainModel):
    claim_id: UUID
    approved_evidence_ids: tuple[UUID, ...]
    relevant_evidence_ids: tuple[UUID, ...]
    supporting_evidence_ids: tuple[UUID, ...]
    challenging_evidence_ids: tuple[UUID, ...]
    covered: bool
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_packet_scope(self) -> "EvidenceCoverageCheck":
        approved = set(self.approved_evidence_ids)
        for references in (
            self.relevant_evidence_ids,
            self.supporting_evidence_ids,
            self.challenging_evidence_ids,
        ):
            if not set(references) <= approved:
                raise ValueError("coverage references must remain in the approved packet")
        if self.covered != bool(self.relevant_evidence_ids):
            raise ValueError("coverage status must reflect relevant approved evidence")
        return self


class AuthoritativeVerificationReport(DomainModel):
    investigation_id: UUID
    claim_id: UUID
    approved_evidence_ids: tuple[UUID, ...]
    approved_packet_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    completed_branches: tuple[str, ...]
    context: ContextVerification
    verification: VerificationPacketV2
    provenance: InvestigationProvenance
    coverage: EvidenceCoverageCheck

    @model_validator(mode="after")
    def validate_shared_packet(self) -> "AuthoritativeVerificationReport":
        if set(self.verification.approved_evidence_ids) != set(
            self.approved_evidence_ids
        ):
            raise ValueError("verification must use exactly the approved packet")
        if self.coverage.approved_evidence_ids != self.approved_evidence_ids:
            raise ValueError("coverage must use exactly the approved packet")
        if (
            self.context.claim_id != self.claim_id
            or self.verification.claim_id != self.claim_id
            or self.provenance.claim_id != self.claim_id
            or self.coverage.claim_id != self.claim_id
        ):
            raise ValueError("every verification branch must reference the same claim")
        if set(self.completed_branches) != {
            "numerical",
            "temporal",
            "provenance",
            "coverage",
        }:
            raise ValueError("all four verification branches must complete")
        return self
