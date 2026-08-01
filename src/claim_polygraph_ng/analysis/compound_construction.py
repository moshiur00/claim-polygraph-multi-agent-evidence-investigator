"""Fail-closed construction of linked assertions from V4 candidate groups."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from itertools import pairwise
from uuid import NAMESPACE_URL, uuid5

from claim_polygraph_ng.analysis.candidate_extraction import (
    VerificationCandidate,
    VerificationCandidateExtraction,
    VerificationCandidateGroup,
    VerificationCandidateGroupKind,
    VerificationCandidateKind,
)
from claim_polygraph_ng.domain.compound_assertions import (
    LinkedAssertionComponent,
    LinkedAssertionComponentKind,
    LinkedAssertionConstruction,
    LinkedAssertionConstructionState,
    LinkedAssertionEdge,
    LinkedAssertionPacket,
    LinkedAssertionRelation,
)

LINKED_ASSERTION_CONSTRUCTION_VERSION = "linked-assertion-construction-v1"

_ACTION = re.compile(
    r"\b(?:must|should|required|require|discard|remove|prohibit|allow|eligible)\b",
    re.IGNORECASE,
)
_CONDITION_MARKER = re.compile(r"\b(?:after|before|during|when|if|for)\b", re.IGNORECASE)


def construct_linked_assertions(
    text: str,
    extraction: VerificationCandidateExtraction,
) -> LinkedAssertionPacket:
    """Construct every candidate group without dropping material operands."""
    if hashlib.sha256(text.encode()).hexdigest() != extraction.text_sha256:
        raise ValueError("candidate packet belongs to different claim text")
    by_id = {item.candidate_id: item for item in extraction.candidates}
    constructions = tuple(
        _construct_group(text, extraction, group, by_id) for group in extraction.groups
    )
    required = {
        candidate_id
        for construction in constructions
        for candidate_id in construction.required_candidate_ids
    }
    covered = {
        candidate_id
        for construction in constructions
        if construction.state is LinkedAssertionConstructionState.CONSTRUCTED
        for component in construction.components
        for candidate_id in component.candidate_ids
    }
    constructed_count = sum(
        item.state is LinkedAssertionConstructionState.CONSTRUCTED for item in constructions
    )
    material_coverage = len(covered) / len(required) if required else 1.0
    return LinkedAssertionPacket(
        claim_text_sha256=extraction.text_sha256,
        candidate_extraction_version=extraction.version,
        constructions=constructions,
        constructed_count=constructed_count,
        unconstructed_count=len(constructions) - constructed_count,
        material_candidate_count=len(required),
        covered_material_candidate_count=len(covered),
        material_coverage=material_coverage,
        requires_human_review=any(
            item.state is LinkedAssertionConstructionState.UNCONSTRUCTED for item in constructions
        ),
    )


def _construct_group(
    text: str,
    extraction: VerificationCandidateExtraction,
    group: VerificationCandidateGroup,
    by_id: dict[str, VerificationCandidate],
) -> LinkedAssertionConstruction:
    candidates = tuple(by_id[item] for item in group.candidate_ids)
    required = tuple(item.candidate_id for item in candidates if item.material)
    failure = _group_failure(group.kind, candidates)
    construction_id = uuid5(
        NAMESPACE_URL,
        f"{extraction.text_sha256}/{group.group_id}/{group.kind.value}/v1",
    )
    if failure is not None:
        return LinkedAssertionConstruction(
            construction_id=construction_id,
            group_id=group.group_id,
            group_kind=group.kind.value,
            claim_text_sha256=extraction.text_sha256,
            state=LinkedAssertionConstructionState.UNCONSTRUCTED,
            required_candidate_ids=required,
            failure_code=failure,
            explanation="Candidate group is incomplete and was routed to review.",
        )

    anchors = _anchors(group.kind, candidates)
    assigned: dict[str, list[VerificationCandidate]] = defaultdict(list)
    for candidate in candidates:
        anchor = min(
            anchors,
            key=lambda item: (
                _distance(candidate, item),
                item.start_char,
                item.candidate_id,
            ),
        )
        assigned[anchor.candidate_id].append(candidate)
    components = [
        _component(index, text, anchor, assigned[anchor.candidate_id])
        for index, anchor in enumerate(anchors, 1)
    ]
    consequence = _consequence_component(text, len(components) + 1)
    if group.kind is VerificationCandidateGroupKind.COMPOUND_CONDITION:
        if _ACTION.search(text) and consequence is None:
            return LinkedAssertionConstruction(
                construction_id=construction_id,
                group_id=group.group_id,
                group_kind=group.kind.value,
                claim_text_sha256=extraction.text_sha256,
                state=LinkedAssertionConstructionState.UNCONSTRUCTED,
                required_candidate_ids=required,
                failure_code="missing_material_consequence",
                explanation=("An explicit consequence could not be preserved safely."),
            )
        if consequence is not None:
            components.append(consequence)
    edges = _edges(group.kind, components)
    try:
        return LinkedAssertionConstruction(
            construction_id=construction_id,
            group_id=group.group_id,
            group_kind=group.kind.value,
            claim_text_sha256=extraction.text_sha256,
            state=LinkedAssertionConstructionState.CONSTRUCTED,
            required_candidate_ids=required,
            components=tuple(components),
            edges=edges,
            explanation=("Every material candidate is represented in linked typed components."),
        )
    except ValueError:
        return LinkedAssertionConstruction(
            construction_id=construction_id,
            group_id=group.group_id,
            group_kind=group.kind.value,
            claim_text_sha256=extraction.text_sha256,
            state=LinkedAssertionConstructionState.UNCONSTRUCTED,
            required_candidate_ids=required,
            failure_code="material_operand_coverage_failed",
            explanation=(
                "A complete linked construction could not preserve every material operand."
            ),
        )


def _group_failure(
    kind: VerificationCandidateGroupKind,
    candidates: tuple[VerificationCandidate, ...],
) -> str | None:
    value_count = sum(
        item.kind is VerificationCandidateKind.VALUE and item.material for item in candidates
    )
    if (
        kind
        in {
            VerificationCandidateGroupKind.COMPARISON,
            VerificationCandidateGroupKind.RANGE,
            VerificationCandidateGroupKind.PROJECTION,
            VerificationCandidateGroupKind.COMPOUND_CONDITION,
        }
        and value_count < 2
    ):
        return "missing_material_value"
    if kind is VerificationCandidateGroupKind.RANKING and not any(
        item.kind is VerificationCandidateKind.RANK for item in candidates
    ):
        return "missing_rank"
    if kind is VerificationCandidateGroupKind.PROJECTION and not any(
        item.kind is VerificationCandidateKind.PROJECTION for item in candidates
    ):
        return "missing_projection_relation"
    return None


def _anchors(
    kind: VerificationCandidateGroupKind,
    candidates: tuple[VerificationCandidate, ...],
) -> tuple[VerificationCandidate, ...]:
    preferred = (
        VerificationCandidateKind.RANK
        if kind is VerificationCandidateGroupKind.RANKING
        else VerificationCandidateKind.VALUE
    )
    anchors = tuple(item for item in candidates if item.kind is preferred and item.material)
    if kind is VerificationCandidateGroupKind.RANKING:
        contexts = tuple(
            item
            for item in candidates
            if item.kind in {VerificationCandidateKind.DATE, VerificationCandidateKind.VALUE}
            and item.material
        )
        anchors = (*anchors, *contexts[:1])
    return tuple({item.candidate_id: item for item in anchors}.values())


def _component(
    index: int,
    text: str,
    anchor: VerificationCandidate,
    assigned: list[VerificationCandidate],
) -> LinkedAssertionComponent:
    ordered = sorted(assigned, key=lambda item: (item.start_char, item.end_char))
    start = min(item.start_char for item in ordered)
    end = max(item.end_char for item in ordered)
    comparator = next(
        (item.relation for item in ordered if item.kind is VerificationCandidateKind.COMPARATOR),
        None,
    )
    unit = next(
        (item.unit for item in ordered if item.kind is VerificationCandidateKind.UNIT),
        None,
    )
    date_candidate = next(
        (item for item in ordered if item.kind is VerificationCandidateKind.DATE),
        None,
    )
    common = {
        "component_id": f"component-{index:03d}",
        "start_char": start,
        "end_char": end,
        "quoted_text": text[start:end],
        "candidate_ids": tuple(item.candidate_id for item in ordered),
    }
    if anchor.kind is VerificationCandidateKind.VALUE:
        return LinkedAssertionComponent(
            **common,
            kind=LinkedAssertionComponentKind.VALUE_CONDITION,
            decimal_value=anchor.decimal_value,
            decimal_scale=anchor.decimal_scale,
            unit=unit,
            comparator=comparator,
            date_value=date_candidate.date_value if date_candidate else None,
            date_precision=(
                date_candidate.date_precision.value
                if date_candidate and date_candidate.date_precision
                else None
            ),
        )
    if anchor.kind is VerificationCandidateKind.RANK:
        return LinkedAssertionComponent(
            **common,
            kind=LinkedAssertionComponentKind.RANK_CONTEXT,
            ordinal_rank=anchor.ordinal_rank,
        )
    if anchor.kind is VerificationCandidateKind.DATE:
        return LinkedAssertionComponent(
            **common,
            kind=LinkedAssertionComponentKind.DATE_CONTEXT,
            date_value=anchor.date_value,
            date_precision=anchor.date_precision.value if anchor.date_precision else None,
        )
    return LinkedAssertionComponent(
        **common,
        kind=LinkedAssertionComponentKind.STATUS_CONTEXT,
        status=anchor.relation or anchor.normalized_text,
    )


def _consequence_component(text: str, index: int) -> LinkedAssertionComponent | None:
    if not _ACTION.search(text):
        return None
    marker = _CONDITION_MARKER.search(text)
    if marker is None:
        return None
    if marker.group(0).casefold() == "if":
        comma = text.find(",", marker.end())
        if comma < 0:
            return None
        start, end = comma + 1, len(text)
    else:
        start, end = 0, marker.start()
    while start < end and text[start].isspace():
        start += 1
    while end > start and (text[end - 1].isspace() or text[end - 1] in ",;."):
        end -= 1
    if start >= end or not _ACTION.search(text[start:end]):
        return None
    return LinkedAssertionComponent(
        component_id=f"component-{index:03d}",
        kind=LinkedAssertionComponentKind.CONSEQUENCE,
        start_char=start,
        end_char=end,
        quoted_text=text[start:end],
    )


def _edges(
    kind: VerificationCandidateGroupKind,
    components: list[LinkedAssertionComponent],
) -> tuple[LinkedAssertionEdge, ...]:
    typed = [
        item for item in components if item.kind is not LinkedAssertionComponentKind.CONSEQUENCE
    ]
    if len(typed) < 2:
        return ()
    relation = {
        VerificationCandidateGroupKind.COMPARISON: LinkedAssertionRelation.COMPARES_TO,
        VerificationCandidateGroupKind.RANGE: LinkedAssertionRelation.RANGE_BOUNDS,
        VerificationCandidateGroupKind.RANKING: LinkedAssertionRelation.QUALIFIES,
        VerificationCandidateGroupKind.PROJECTION: LinkedAssertionRelation.PROJECTS_TO,
        VerificationCandidateGroupKind.COMPOUND_CONDITION: LinkedAssertionRelation.AND,
    }[kind]
    edges = [
        LinkedAssertionEdge(
            source_component_id=left.component_id,
            target_component_id=right.component_id,
            relation=relation,
        )
        for left, right in pairwise(typed)
    ]
    consequence = next(
        (item for item in components if item.kind is LinkedAssertionComponentKind.CONSEQUENCE),
        None,
    )
    if consequence is not None:
        edges.extend(
            LinkedAssertionEdge(
                source_component_id=item.component_id,
                target_component_id=consequence.component_id,
                relation=LinkedAssertionRelation.IMPLIES,
            )
            for item in typed
        )
    return tuple(edges)


def _distance(left: VerificationCandidate, right: VerificationCandidate) -> float:
    left_center = (left.start_char + left.end_char) / 2
    right_center = (right.start_char + right.end_char) / 2
    return abs(left_center - right_center)
