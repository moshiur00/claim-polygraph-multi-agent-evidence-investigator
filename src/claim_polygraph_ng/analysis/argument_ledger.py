"""Deterministic argument ledger and bounded challenger construction."""

import hashlib
import re
from uuid import NAMESPACE_URL, uuid5

from claim_polygraph_ng.domain import (
    ArgumentLedger,
    AssertionVerificationState,
    AtomicClaim,
    ChallengeFinding,
    ChallengeKind,
    ChallengeSeverity,
    Evidence,
    EvidenceStance,
    InvestigationProvenance,
    MaterialProposition,
    PropositionArgument,
    PropositionResolution,
    VerificationPacketV2,
)

_ABSOLUTE = re.compile(r"\b(all|always|every|exactly|never|only|no longer)\b", re.I)
_CAUSAL = re.compile(r"\b(cause[sd]?|caused by|leads? to|results? in|because)\b", re.I)
_INDIVIDUAL = re.compile(r"\b(every person|any person|everyone|all people)\b", re.I)


def build_argument_ledger(
    *,
    claim: AtomicClaim,
    evidence: tuple[Evidence, ...],
    verification: VerificationPacketV2 | None = None,
    provenance: InvestigationProvenance | None = None,
    propositions: tuple[MaterialProposition, ...] | None = None,
) -> ArgumentLedger:
    """Map approved artifacts to material propositions without generating facts."""
    if any(item.claim_id != claim.claim_id for item in evidence):
        raise ValueError("all evidence must reference the ledger claim")
    if verification is not None and verification.claim_id != claim.claim_id:
        raise ValueError("verification packet must reference the ledger claim")
    if provenance is not None and provenance.claim_id != claim.claim_id:
        raise ValueError("provenance packet must reference the ledger claim")
    propositions = propositions or (
        MaterialProposition(
            proposition_id=uuid5(NAMESPACE_URL, f"{claim.claim_id}/{claim.text}"),
            claim_id=claim.claim_id,
            text=claim.text,
        ),
    )
    approved = tuple(dict.fromkeys(item.evidence_id for item in evidence))
    usable = tuple(item for item in evidence if item.relevance_score >= 0.5)
    stance_ids = {
        stance: tuple(item.evidence_id for item in usable if item.stance is stance)
        for stance in EvidenceStance
    }
    numerical_ids = (
        tuple(item.assertion_id for item in verification.numerical_assertions)
        if verification
        else ()
    )
    temporal_ids = (
        tuple(item.assertion_id for item in verification.temporal_assertions)
        if verification
        else ()
    )
    verification_states = (
        tuple(item.state for item in verification.numerical_assertions)
        + tuple(item.state for item in verification.temporal_assertions)
        if verification
        else ()
    )
    arguments = tuple(
        PropositionArgument(
            proposition_id=proposition.proposition_id,
            resolution=_resolution(stance_ids, verification_states),
            supporting_evidence_ids=stance_ids[EvidenceStance.SUPPORTS],
            contradictory_evidence_ids=stance_ids[EvidenceStance.CONTRADICTS],
            qualifying_evidence_ids=stance_ids[EvidenceStance.QUALIFIES],
            contextual_evidence_ids=stance_ids[EvidenceStance.CONTEXT],
            numerical_assertion_ids=numerical_ids,
            temporal_assertion_ids=temporal_ids,
            unresolved_reasons=_unresolved_reasons(stance_ids, verification_states),
        )
        for proposition in propositions
    )
    findings = tuple(
        finding
        for proposition, argument in zip(propositions, arguments, strict=True)
        for finding in _challenge(proposition, argument, verification, provenance)
    )
    return ArgumentLedger(
        claim_id=claim.claim_id,
        approved_evidence_ids=approved,
        propositions=propositions,
        arguments=arguments,
        challenge_findings=findings,
        provenance_requirement_state=(provenance.requirement_state.value if provenance else None),
        provenance_lower_bound=(
            provenance.confirmed_independent_lower_bound if provenance else None
        ),
        provenance_upper_bound=(
            provenance.possible_independent_upper_bound if provenance else None
        ),
        limitations=(
            "The ledger reorganizes approved artifacts and does not create evidence or facts.",
            "Challenger rules identify review conditions, not verdict labels.",
        ),
    )


def _resolution(stance_ids, states) -> PropositionResolution:
    if AssertionVerificationState.CONTRADICTED in states:
        return PropositionResolution.CONTRADICTED
    if any(
        state in {AssertionVerificationState.QUALIFIED, AssertionVerificationState.ERROR}
        for state in states
    ):
        return PropositionResolution.QUALIFIED
    supports = bool(stance_ids[EvidenceStance.SUPPORTS])
    contradicts = bool(stance_ids[EvidenceStance.CONTRADICTS])
    qualifies = bool(stance_ids[EvidenceStance.QUALIFIES])
    if contradicts and not supports:
        return PropositionResolution.CONTRADICTED
    if qualifies or (supports and contradicts):
        return PropositionResolution.QUALIFIED
    if supports:
        return PropositionResolution.SUPPORTED
    return PropositionResolution.UNRESOLVED


def _unresolved_reasons(stance_ids, states) -> tuple[str, ...]:
    reasons = []
    if not any(
        stance_ids[stance] for stance in EvidenceStance if stance is not EvidenceStance.IRRELEVANT
    ):
        reasons.append("No relevant approved evidence resolves the proposition.")
    if any(
        state in {AssertionVerificationState.INSUFFICIENT, AssertionVerificationState.ERROR}
        for state in states
    ):
        reasons.append("A numerical or temporal verification remains unresolved.")
    return tuple(reasons)


def _challenge(proposition, argument, verification, provenance):
    findings = []
    if _ABSOLUTE.search(proposition.text) and argument.qualifying_evidence_ids:
        findings.append(
            _finding(
                proposition,
                ChallengeKind.ABSOLUTE_WORDING,
                ChallengeSeverity.MATERIAL,
                "Absolute wording is challenged by approved qualifying evidence.",
                argument.qualifying_evidence_ids,
            )
        )
    if _CAUSAL.search(proposition.text):
        findings.append(
            _finding(
                proposition,
                ChallengeKind.CAUSAL_OVERREACH,
                ChallengeSeverity.CAUTION,
                "Causal wording requires evidence that establishes causation, not association.",
                (*argument.supporting_evidence_ids, *argument.qualifying_evidence_ids),
            )
        )
    if _INDIVIDUAL.search(proposition.text):
        findings.append(
            _finding(
                proposition,
                ChallengeKind.POPULATION_TO_INDIVIDUAL,
                ChallengeSeverity.CAUTION,
                "Universal individual wording may exceed population-level evidence.",
                (*argument.supporting_evidence_ids, *argument.qualifying_evidence_ids),
            )
        )
    if not argument.contradictory_evidence_ids and not argument.qualifying_evidence_ids:
        findings.append(
            _finding(
                proposition,
                ChallengeKind.MISSING_COUNTEREVIDENCE,
                ChallengeSeverity.CAUTION,
                "The approved packet contains no contradictory or qualifying passage.",
                (),
            )
        )
    if verification and any(
        item.state in {AssertionVerificationState.INSUFFICIENT, AssertionVerificationState.ERROR}
        for item in verification.numerical_assertions
    ):
        findings.append(
            _finding(
                proposition,
                ChallengeKind.INCOMPLETE_NUMERICAL_CONTEXT,
                ChallengeSeverity.BLOCKING,
                "A required numerical assertion remains insufficient or errored.",
                (),
            )
        )
    if verification and any(
        item.state
        in {
            AssertionVerificationState.CONTRADICTED,
            AssertionVerificationState.INSUFFICIENT,
            AssertionVerificationState.ERROR,
        }
        for item in verification.temporal_assertions
    ):
        findings.append(
            _finding(
                proposition,
                ChallengeKind.TEMPORAL_MISMATCH,
                ChallengeSeverity.BLOCKING,
                "Temporal verification contradicts the assertion or remains unresolved.",
                (),
            )
        )
    if provenance and provenance.confirmed_independent_lower_bound < (
        provenance.required_independent_families
    ):
        findings.append(
            _finding(
                proposition,
                ChallengeKind.DEPENDENT_SOURCE_DIVERSITY,
                ChallengeSeverity.MATERIAL,
                "Confirmed independent evidence is below the required family count.",
                (),
            )
        )
    return findings


def _finding(proposition, kind, severity, rationale, evidence_ids):
    digest = hashlib.sha256(f"{proposition.proposition_id}/{kind.value}".encode()).hexdigest()
    return ChallengeFinding(
        finding_id=f"challenge-{digest[:16]}",
        proposition_id=proposition.proposition_id,
        kind=kind,
        severity=severity,
        rationale=rationale,
        evidence_ids=tuple(dict.fromkeys(evidence_ids)),
    )
