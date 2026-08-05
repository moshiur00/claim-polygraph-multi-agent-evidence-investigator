"""Typed claim-to-evidence argument and challenger artifacts."""

from enum import StrEnum
from uuid import UUID

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel


class PropositionResolution(StrEnum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    QUALIFIED = "qualified"
    UNRESOLVED = "unresolved"


class ChallengeKind(StrEnum):
    ABSOLUTE_WORDING = "absolute_wording"
    CAUSAL_OVERREACH = "causal_overreach"
    POPULATION_TO_INDIVIDUAL = "population_to_individual"
    INSUFFICIENT_ELIGIBLE_EVIDENCE = "insufficient_eligible_evidence"
    MISSING_COUNTEREVIDENCE = "missing_counterevidence"
    INCOMPLETE_NUMERICAL_CONTEXT = "incomplete_numerical_context"
    TEMPORAL_MISMATCH = "temporal_mismatch"
    DEPENDENT_SOURCE_DIVERSITY = "dependent_source_diversity"


class ChallengeSeverity(StrEnum):
    CAUTION = "caution"
    MATERIAL = "material"
    BLOCKING = "blocking"


class MaterialProposition(DomainModel):
    proposition_id: UUID
    claim_id: UUID
    text: str = Field(min_length=3, max_length=5_000)
    material: bool = True


class PropositionArgument(DomainModel):
    proposition_id: UUID
    resolution: PropositionResolution
    supporting_evidence_ids: tuple[UUID, ...] = ()
    contradictory_evidence_ids: tuple[UUID, ...] = ()
    qualifying_evidence_ids: tuple[UUID, ...] = ()
    contextual_evidence_ids: tuple[UUID, ...] = ()
    numerical_assertion_ids: tuple[UUID, ...] = ()
    temporal_assertion_ids: tuple[UUID, ...] = ()
    unresolved_reasons: tuple[str, ...] = ()


class ChallengeFinding(DomainModel):
    finding_id: str = Field(pattern=r"^challenge-[0-9a-f]{16}$")
    proposition_id: UUID
    kind: ChallengeKind
    severity: ChallengeSeverity
    rationale: str = Field(min_length=10, max_length=2_000)
    evidence_ids: tuple[UUID, ...] = ()


class ArgumentLedger(DomainModel):
    claim_id: UUID
    ledger_version: str = Field(default="argument-ledger-v1", pattern=r"^argument-ledger-v1$")
    approved_evidence_ids: tuple[UUID, ...]
    propositions: tuple[MaterialProposition, ...] = Field(min_length=1)
    arguments: tuple[PropositionArgument, ...] = Field(min_length=1)
    challenge_findings: tuple[ChallengeFinding, ...] = ()
    provenance_requirement_state: str | None = None
    provenance_lower_bound: int | None = Field(default=None, ge=0)
    provenance_upper_bound: int | None = Field(default=None, ge=0)
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_references(self) -> "ArgumentLedger":
        proposition_ids = {item.proposition_id for item in self.propositions}
        if len(proposition_ids) != len(self.propositions):
            raise ValueError("proposition IDs must be unique")
        if any(item.claim_id != self.claim_id for item in self.propositions):
            raise ValueError("all propositions must reference the ledger claim")
        argument_ids = [item.proposition_id for item in self.arguments]
        if set(argument_ids) != proposition_ids or len(argument_ids) != len(set(argument_ids)):
            raise ValueError("every proposition requires exactly one argument")
        if any(item.proposition_id not in proposition_ids for item in self.challenge_findings):
            raise ValueError("challenge findings must reference a ledger proposition")
        approved = set(self.approved_evidence_ids)
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
        if not referenced.issubset(approved):
            raise ValueError("ledger records may reference only approved evidence IDs")
        return self
