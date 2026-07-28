"""Typed, tool-isolated defender/challenger argument contracts."""

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.argument import (
    ArgumentLedger,
    ChallengeFinding,
    MaterialProposition,
    PropositionArgument,
)
from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.models import AtomicClaim, Evidence
from claim_polygraph_ng.domain.provenance import InvestigationProvenance
from claim_polygraph_ng.domain.verification import VerificationPacketV2


class ArgumentRole(StrEnum):
    DEFENDER = "defender"
    CHALLENGER = "challenger"


class ArgumentPermission(StrEnum):
    READ_APPROVED_EVIDENCE = "read_approved_evidence"
    BUILD_POSITION = "build_position"


ARGUMENT_PERMISSIONS = frozenset(
    {
        ArgumentPermission.READ_APPROVED_EVIDENCE,
        ArgumentPermission.BUILD_POSITION,
    }
)


class ArgumentAssignment(DomainModel):
    """One immutable position-building task with no retrieval capability."""

    assignment_id: UUID = Field(default_factory=uuid4)
    investigation_id: UUID
    claim_id: UUID
    role: ArgumentRole
    proposition_ids: tuple[UUID, ...] = Field(min_length=1)
    approved_evidence_ids: tuple[UUID, ...] = Field(min_length=1)
    permissions: frozenset[ArgumentPermission] = ARGUMENT_PERMISSIONS

    @model_validator(mode="after")
    def enforce_isolated_permissions(self) -> "ArgumentAssignment":
        if self.permissions != ARGUMENT_PERMISSIONS:
            raise ValueError("argument roles may only read approved evidence and build a position")
        if len(set(self.proposition_ids)) != len(self.proposition_ids):
            raise ValueError("argument proposition IDs must be unique")
        if len(set(self.approved_evidence_ids)) != len(self.approved_evidence_ids):
            raise ValueError("approved argument evidence IDs must be unique")
        return self


class ArgumentRoleResult(DomainModel):
    """Independent role output referencing only its approved packet."""

    result_id: UUID = Field(default_factory=uuid4)
    assignment_id: UUID
    claim_id: UUID
    role: ArgumentRole
    arguments: tuple[PropositionArgument, ...] = Field(min_length=1)
    challenge_findings: tuple[ChallengeFinding, ...] = ()
    consumed_evidence_ids: tuple[UUID, ...] = ()
    search_calls: int = Field(default=0, ge=0, le=0)
    fetch_calls: int = Field(default=0, ge=0, le=0)
    model_calls: int = Field(default=0, ge=0)
    failure_reason: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def validate_consumed_references(self) -> "ArgumentRoleResult":
        consumed = set(self.consumed_evidence_ids)
        referenced = {
            evidence_id
            for argument in self.arguments
            for evidence_id in (
                *argument.supporting_evidence_ids,
                *argument.contradictory_evidence_ids,
                *argument.qualifying_evidence_ids,
                *argument.contextual_evidence_ids,
            )
        }
        referenced.update(
            evidence_id
            for finding in self.challenge_findings
            for evidence_id in finding.evidence_ids
        )
        if not referenced <= consumed:
            raise ValueError("argument references must be declared as consumed evidence")
        return self


class ArgumentWorkflowStage(StrEnum):
    PLANNED = "planned"
    ARGUED = "argued"
    RECONCILED = "reconciled"


class AdversarialArgumentCheckpoint(DomainModel):
    """Restart-safe state for the bounded argument fan-out and reconciliation."""

    investigation_id: UUID
    claim: AtomicClaim
    approved_evidence: tuple[Evidence, ...] = Field(min_length=1)
    propositions: tuple[MaterialProposition, ...] = Field(min_length=1)
    assignments: tuple[ArgumentAssignment, ...] = Field(min_length=2, max_length=2)
    stage: ArgumentWorkflowStage
    results: tuple[ArgumentRoleResult, ...] = ()
    verification: VerificationPacketV2 | None = None
    provenance: InvestigationProvenance | None = None
    reconciled_ledger: ArgumentLedger | None = None
    authoritative_ledger: ArgumentLedger | None = None

    @model_validator(mode="after")
    def validate_checkpoint_scope(self) -> "AdversarialArgumentCheckpoint":
        approved = {item.evidence_id for item in self.approved_evidence}
        if any(item.claim_id != self.claim.claim_id for item in self.approved_evidence):
            raise ValueError("argument evidence must reference the checkpoint claim")
        if {item.role for item in self.assignments} != {
            ArgumentRole.DEFENDER,
            ArgumentRole.CHALLENGER,
        }:
            raise ValueError("argument workflow requires one defender and one challenger")
        if any(
            item.investigation_id != self.investigation_id or item.claim_id != self.claim.claim_id
            for item in self.assignments
        ):
            raise ValueError("argument assignments must match the checkpoint identity")
        proposition_ids = {item.proposition_id for item in self.propositions}
        if any(set(item.proposition_ids) != proposition_ids for item in self.assignments):
            raise ValueError("both roles must receive every material proposition")
        if any(set(item.approved_evidence_ids) != approved for item in self.assignments):
            raise ValueError("both roles must receive exactly the approved evidence packet")
        assignment_ids = {item.assignment_id for item in self.assignments}
        if any(item.assignment_id not in assignment_ids for item in self.results):
            raise ValueError("argument results must reference a checkpoint assignment")
        if any(
            {item.proposition_id for item in result.arguments} != proposition_ids
            for result in self.results
        ):
            raise ValueError("argument results must cover every material proposition")
        if any(not set(item.consumed_evidence_ids) <= approved for item in self.results):
            raise ValueError("argument results may consume only approved evidence")
        return self


class AdversarialArgumentReport(DomainModel):
    """Authority-isolated output of independent argument construction."""

    investigation_id: UUID
    assignments: tuple[ArgumentAssignment, ...] = Field(min_length=2, max_length=2)
    results: tuple[ArgumentRoleResult, ...] = Field(min_length=2, max_length=2)
    reconciled_ledger: ArgumentLedger
    authoritative_ledger_equivalent: bool
    complete_role_coverage: bool
    human_review_required: bool
    human_review_reason: str | None = Field(default=None, max_length=2_000)
    authoritative_output_applied: bool = False

    @model_validator(mode="after")
    def validate_authority_and_escalation(self) -> "AdversarialArgumentReport":
        approved = set(self.reconciled_ledger.approved_evidence_ids)
        if any(not set(item.consumed_evidence_ids) <= approved for item in self.results):
            raise ValueError("argument report contains out-of-packet evidence")
        if self.authoritative_output_applied:
            raise ValueError("adversarial argument workflow cannot replace authority")
        if self.human_review_required != bool(self.human_review_reason):
            raise ValueError("argument review escalation requires exactly one reason")
        return self
