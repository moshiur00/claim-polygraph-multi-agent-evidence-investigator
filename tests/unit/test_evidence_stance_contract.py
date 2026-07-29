"""Shared support, contradiction, qualification and context semantics."""

from uuid import uuid4

from claim_polygraph_ng.analysis.stance import (
    deterministic_stance_label,
    stance_profile,
)
from claim_polygraph_ng.domain import Evidence, EvidenceStance, VerdictLabel


def _evidence(stance: EvidenceStance) -> Evidence:
    return Evidence(
        claim_id=uuid4(),
        source_id=uuid4(),
        passage=f"A material {stance.value} passage.",
        stance=stance,
        relevance_score=0.9,
    )


def test_support_plus_contradiction_is_mixed() -> None:
    packet = (
        _evidence(EvidenceStance.SUPPORTS),
        _evidence(EvidenceStance.CONTRADICTS),
    )
    assert deterministic_stance_label(packet) is VerdictLabel.MIXED


def test_support_plus_material_qualification_is_mixed_not_supported() -> None:
    packet = (
        _evidence(EvidenceStance.SUPPORTS),
        _evidence(EvidenceStance.QUALIFIES),
    )
    profile = stance_profile(packet)
    assert profile.supports and profile.qualifies and not profile.contradicts
    assert deterministic_stance_label(packet) is VerdictLabel.MIXED


def test_context_does_not_become_support_or_contradiction() -> None:
    packet = (_evidence(EvidenceStance.CONTEXT),)
    profile = stance_profile(packet)
    assert profile.context_only
    assert deterministic_stance_label(packet) is VerdictLabel.UNVERIFIABLE


def test_challenger_role_does_not_imply_one_stance() -> None:
    """The stance contract accepts each counter-research relationship distinctly."""
    assert deterministic_stance_label(
        (_evidence(EvidenceStance.CONTRADICTS),)
    ) is VerdictLabel.CONTRADICTED
    assert deterministic_stance_label(
        (_evidence(EvidenceStance.QUALIFIES),)
    ) is VerdictLabel.MIXED
    assert deterministic_stance_label(
        (_evidence(EvidenceStance.CONTEXT),)
    ) is VerdictLabel.UNVERIFIABLE
