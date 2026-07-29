"""Shared role-independent evidence-stance semantics."""

from dataclasses import dataclass

from claim_polygraph_ng.domain import Evidence, EvidenceStance, VerdictLabel


@dataclass(frozen=True)
class EvidenceStanceProfile:
    """Material stance presence used consistently by judgment boundaries."""

    supports: bool
    contradicts: bool
    qualifies: bool
    context_only: bool


def stance_profile(evidence: tuple[Evidence, ...]) -> EvidenceStanceProfile:
    """Summarize usable passages without treating research role as stance."""
    usable = tuple(
        item
        for item in evidence
        if item.relevance_score >= 0.5 and item.stance is not EvidenceStance.IRRELEVANT
    )
    stances = {item.stance for item in usable}
    substantive = stances & {
        EvidenceStance.SUPPORTS,
        EvidenceStance.CONTRADICTS,
        EvidenceStance.QUALIFIES,
    }
    return EvidenceStanceProfile(
        supports=EvidenceStance.SUPPORTS in stances,
        contradicts=EvidenceStance.CONTRADICTS in stances,
        qualifies=EvidenceStance.QUALIFIES in stances,
        context_only=bool(usable) and not substantive,
    )


def deterministic_stance_label(evidence: tuple[Evidence, ...]) -> VerdictLabel:
    """Return the fixture judgment implied by typed passage relationships.

    Qualification is neither support nor contradiction. A packet containing
    support plus material qualification is mixed; context never changes a
    verdict by itself.
    """
    profile = stance_profile(evidence)
    if profile.supports and (profile.contradicts or profile.qualifies):
        return VerdictLabel.MIXED
    if profile.contradicts and not profile.supports:
        return VerdictLabel.CONTRADICTED
    if profile.qualifies and not profile.supports:
        return VerdictLabel.MIXED
    if profile.supports:
        return VerdictLabel.SUPPORTED
    return VerdictLabel.UNVERIFIABLE
