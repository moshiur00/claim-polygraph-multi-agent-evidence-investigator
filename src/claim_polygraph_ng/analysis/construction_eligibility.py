"""Candidate-driven verification-construction eligibility routing."""

from __future__ import annotations

import hashlib
import re

from claim_polygraph_ng.analysis.candidate_extraction import (
    VerificationCandidate,
    VerificationCandidateExtraction,
    VerificationCandidateKind,
)
from claim_polygraph_ng.domain.compound_assertions import (
    LinkedAssertionConstructionState,
    LinkedAssertionPacket,
)
from claim_polygraph_ng.domain.construction_eligibility import (
    ConstructionEligibilityDecision,
    ConstructionEligibilityPacket,
    ConstructionEligibilityReason,
    ConstructionEligibilityRoute,
)

CONSTRUCTION_ELIGIBILITY_VERSION = "construction-eligibility-v1"

_CAUSAL = re.compile(
    r"\b(?:causes?|caused|because|leads?\s+to|results?\s+in|"
    r"responsible\s+for)\b",
    re.IGNORECASE,
)
_OPEN_WORLD = re.compile(
    r"\b(?:best|worst|most|least|greatest|safest|healthiest|"
    r"most\s+(?:important|effective|popular|successful))\b",
    re.IGNORECASE,
)
_GENERALIZATION = re.compile(r"\b(?:everyone|everything|nobody|always|never)\b", re.IGNORECASE)
_UNBOUNDED_REQUIREMENT = re.compile(r"\b(?:do|does|did)\s+not\s+need\b", re.IGNORECASE)


def route_construction_eligibility(
    text: str,
    extraction: VerificationCandidateExtraction,
    constructions: LinkedAssertionPacket,
) -> ConstructionEligibilityPacket:
    """Route typed construction work without inferring truth or evidence fit."""
    digest = hashlib.sha256(text.encode()).hexdigest()
    if digest != extraction.text_sha256:
        raise ValueError("candidate packet belongs to different claim text")
    if digest != constructions.claim_text_sha256:
        raise ValueError("linked-construction packet belongs to different claim text")
    if constructions.candidate_extraction_version != extraction.version:
        raise ValueError("candidate and construction versions are inconsistent")

    by_id = {item.candidate_id: item for item in extraction.candidates}
    decisions = [_route_group(text, item, by_id) for item in constructions.constructions]
    grouped_ids = {
        candidate_id
        for item in constructions.constructions
        for candidate_id in item.required_candidate_ids
    }
    ungrouped = tuple(
        item
        for item in extraction.candidates
        if item.material and item.candidate_id not in grouped_ids
    )
    if ungrouped or not decisions:
        decisions.append(_route_ungrouped(text, ungrouped, orphaned=bool(decisions)))

    counts = {
        route: sum(item.route is route for item in decisions)
        for route in ConstructionEligibilityRoute
    }
    return ConstructionEligibilityPacket(
        claim_text_sha256=digest,
        candidate_extraction_version=extraction.version,
        linked_construction_version=(
            constructions.constructions[0].construction_version
            if constructions.constructions
            else "linked-assertion-construction-v1"
        ),
        decisions=tuple(decisions),
        deterministic_count=counts[ConstructionEligibilityRoute.DETERMINISTIC],
        assisted_count=counts[ConstructionEligibilityRoute.ASSISTED],
        human_review_count=counts[ConstructionEligibilityRoute.HUMAN_REVIEW],
        not_applicable_count=counts[ConstructionEligibilityRoute.NOT_APPLICABLE],
        requires_human_review=bool(counts[ConstructionEligibilityRoute.HUMAN_REVIEW]),
    )


def _route_group(
    text: str,
    construction,
    by_id: dict[str, VerificationCandidate],
) -> ConstructionEligibilityDecision:
    candidates = tuple(by_id[item] for item in construction.required_candidate_ids)
    exclusion = _qualitative_exclusion(text, candidates)
    if exclusion is not None:
        return _decision(
            target_id=f"eligibility-{construction.group_id}",
            group_id=construction.group_id,
            route=ConstructionEligibilityRoute.NOT_APPLICABLE,
            reasons=(exclusion,),
            candidates=candidates,
            explanation=("Typed candidates do not bound the claim's qualitative scope."),
        )
    if construction.state is LinkedAssertionConstructionState.CONSTRUCTED:
        return _decision(
            target_id=f"eligibility-{construction.group_id}",
            group_id=construction.group_id,
            route=ConstructionEligibilityRoute.DETERMINISTIC,
            reasons=(ConstructionEligibilityReason.COMPLETE_LINKED_GROUP,),
            candidates=candidates,
            linked_construction_id=str(construction.construction_id),
            explanation=("The linked construction preserves every material operand."),
        )
    typed_basis = _has_typed_basis(candidates)
    return _decision(
        target_id=f"eligibility-{construction.group_id}",
        group_id=construction.group_id,
        route=(
            ConstructionEligibilityRoute.ASSISTED
            if typed_basis
            else ConstructionEligibilityRoute.HUMAN_REVIEW
        ),
        reasons=(
            ConstructionEligibilityReason.BOUNDED_CONSTRUCTION_AMBIGUITY
            if typed_basis
            else ConstructionEligibilityReason.INCOMPLETE_MATERIAL_OPERANDS,
        ),
        candidates=candidates,
        explanation=(
            "Typed operands exist but deterministic construction was incomplete."
            if typed_basis
            else "No safe complete construction can be recovered from the candidates."
        ),
    )


def _route_ungrouped(
    text: str,
    candidates: tuple[VerificationCandidate, ...],
    *,
    orphaned: bool,
) -> ConstructionEligibilityDecision:
    exclusion = _qualitative_exclusion(text, candidates)
    if exclusion is not None:
        return _decision(
            target_id="eligibility-ungrouped",
            route=ConstructionEligibilityRoute.NOT_APPLICABLE,
            reasons=(exclusion,),
            candidates=candidates,
            explanation=(
                "This numerical/temporal verifier cannot safely represent the "
                "claim's open qualitative scope."
            ),
        )
    kinds = {item.kind for item in candidates}
    if VerificationCandidateKind.STATUS in kinds:
        reason = ConstructionEligibilityReason.STATUS_OR_ABSENCE
    elif VerificationCandidateKind.DATE in kinds:
        reason = ConstructionEligibilityReason.ORDINARY_TEMPORAL_LANGUAGE
    elif kinds.intersection(
        {
            VerificationCandidateKind.VALUE,
            VerificationCandidateKind.RANK,
        }
    ):
        reason = ConstructionEligibilityReason.ORDINARY_NUMERICAL_LANGUAGE
    elif candidates and orphaned:
        reason = ConstructionEligibilityReason.BOUNDED_CONSTRUCTION_AMBIGUITY
    else:
        return _decision(
            target_id="eligibility-ungrouped",
            route=ConstructionEligibilityRoute.NOT_APPLICABLE,
            reasons=(ConstructionEligibilityReason.NO_TYPED_VERIFICATION_BASIS,),
            candidates=candidates,
            explanation=(
                "No numerical, temporal, ranking, or status construction basis was detected."
            ),
        )
    return _decision(
        target_id="eligibility-ungrouped",
        route=ConstructionEligibilityRoute.ASSISTED,
        reasons=(reason,),
        candidates=candidates,
        explanation=(
            "Ordinary typed language is eligible for bounded assisted "
            "construction because no complete linked group exists."
        ),
    )


def _qualitative_exclusion(
    text: str,
    candidates: tuple[VerificationCandidate, ...],
) -> ConstructionEligibilityReason | None:
    if _CAUSAL.search(text):
        return ConstructionEligibilityReason.CAUSAL_CLAIM
    if _UNBOUNDED_REQUIREMENT.search(text):
        return ConstructionEligibilityReason.QUALITATIVE_GENERALIZATION
    has_rank = any(item.kind is VerificationCandidateKind.RANK for item in candidates)
    if _OPEN_WORLD.search(text) and not has_rank:
        return ConstructionEligibilityReason.OPEN_WORLD_SUPERLATIVE
    has_typed_basis = _has_typed_basis(candidates)
    if _GENERALIZATION.search(text) and not has_typed_basis:
        return ConstructionEligibilityReason.QUALITATIVE_GENERALIZATION
    return None


def _has_typed_basis(
    candidates: tuple[VerificationCandidate, ...],
) -> bool:
    return any(
        item.kind
        in {
            VerificationCandidateKind.VALUE,
            VerificationCandidateKind.DATE,
            VerificationCandidateKind.RANK,
            VerificationCandidateKind.STATUS,
        }
        for item in candidates
    )


def _decision(
    *,
    target_id: str,
    route: ConstructionEligibilityRoute,
    reasons: tuple[ConstructionEligibilityReason, ...],
    candidates: tuple[VerificationCandidate, ...],
    explanation: str,
    group_id: str | None = None,
    linked_construction_id: str | None = None,
) -> ConstructionEligibilityDecision:
    return ConstructionEligibilityDecision(
        target_id=target_id,
        group_id=group_id,
        route=route,
        reasons=reasons,
        candidate_ids=tuple(item.candidate_id for item in candidates),
        linked_construction_id=linked_construction_id,
        requires_human_review=(route is ConstructionEligibilityRoute.HUMAN_REVIEW),
        explanation=explanation,
    )
