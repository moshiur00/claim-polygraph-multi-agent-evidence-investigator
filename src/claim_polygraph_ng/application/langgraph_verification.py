"""Concurrent deterministic verification fan-out for Stage 9.7."""

import asyncio
import hashlib
import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from claim_polygraph_ng.analysis import (
    bridge_legacy_verification,
    verify_claim_context,
)
from claim_polygraph_ng.analysis.investigation_provenance import (
    build_investigation_provenance,
)
from claim_polygraph_ng.domain import (
    AtomicClaim,
    ContextVerification,
    Evidence,
    EvidenceStance,
    InvestigationPlan,
    Source,
)
from claim_polygraph_ng.domain.authoritative_analysis import (
    AuthoritativeVerificationReport,
    EvidenceCoverageCheck,
)


class _VerificationState(TypedDict, total=False):
    branches: list[str]
    results: Annotated[list[dict[str, Any]], operator.add]


class AuthoritativeVerificationFanOutWorkflow:
    """Run compatible checks concurrently and return one typed immutable packet."""

    def __init__(self) -> None:
        self._active_branches = 0
        self.maximum_active_branches = 0

    async def execute(
        self,
        *,
        investigation_id,
        claim: AtomicClaim,
        plan: InvestigationPlan,
        sources: tuple[Source, ...],
        evidence: tuple[Evidence, ...],
        approved_evidence_ids: tuple,
    ) -> AuthoritativeVerificationReport:
        if tuple(item.evidence_id for item in evidence) != approved_evidence_ids:
            raise ValueError("verification input must equal the approved evidence packet")
        self._active_branches = 0
        self.maximum_active_branches = 0
        graph = _build_graph(self, claim, plan, sources, evidence)
        output = await graph.ainvoke(
            {
                "branches": ["numerical", "temporal", "provenance", "coverage"],
                "results": [],
            }
        )
        by_branch = {item["branch"]: item["payload"] for item in output["results"]}
        numerical_context = ContextVerification.model_validate(by_branch["numerical"])
        temporal_context = ContextVerification.model_validate(by_branch["temporal"])
        numerical = numerical_context.numerical
        temporal = temporal_context.temporal
        context = ContextVerification(
            claim_id=claim.claim_id,
            numerical=numerical,
            temporal=temporal,
            scope_findings=numerical_context.scope_findings,
            limitations=numerical_context.limitations,
        )
        verification = bridge_legacy_verification(
            claim=claim,
            legacy=context,
            sources=sources,
            evidence=evidence,
        )
        packet_hash = hashlib.sha256(
            "|".join(map(str, approved_evidence_ids)).encode()
        ).hexdigest()
        return AuthoritativeVerificationReport(
            investigation_id=investigation_id,
            claim_id=claim.claim_id,
            approved_evidence_ids=approved_evidence_ids,
            approved_packet_sha256=packet_hash,
            completed_branches=tuple(by_branch),
            context=context,
            verification=verification,
            provenance=by_branch["provenance"],
            coverage=by_branch["coverage"],
        )


def _build_graph(workflow, claim, plan, sources, evidence):
    builder = StateGraph(_VerificationState)

    async def check(state: _VerificationState):
        workflow._active_branches += 1
        workflow.maximum_active_branches = max(
            workflow.maximum_active_branches, workflow._active_branches
        )
        try:
            await asyncio.sleep(0)
            branch = state["branches"][0]
            if branch in {"numerical", "temporal"}:
                payload = verify_claim_context(
                    claim=claim,
                    plan=plan,
                    sources=sources,
                    evidence=evidence,
                )
            elif branch == "provenance":
                payload = build_investigation_provenance(
                    plan=plan,
                    sources=sources,
                    evidence=evidence,
                )
            elif branch == "coverage":
                payload = _coverage(claim, evidence)
            else:
                raise ValueError(f"unknown verification branch: {branch}")
            return {
                "results": [
                    {"branch": branch, "payload": payload.model_dump(mode="json")}
                ]
            }
        finally:
            workflow._active_branches -= 1

    builder.add_node("dispatch_checks", lambda _state: {})
    builder.add_node("run_check", check)
    builder.add_node("join_checks", lambda _state: {})
    builder.add_edge(START, "dispatch_checks")
    builder.add_conditional_edges(
        "dispatch_checks",
        lambda state: [
            Send("run_check", {"branches": [branch], "results": []})
            for branch in state["branches"]
        ],
    )
    builder.add_edge("run_check", "join_checks")
    builder.add_edge("join_checks", END)
    return builder.compile()


def _coverage(claim: AtomicClaim, evidence: tuple[Evidence, ...]) -> EvidenceCoverageCheck:
    approved = tuple(item.evidence_id for item in evidence)
    relevant = tuple(
        item.evidence_id
        for item in evidence
        if item.relevance_score >= 0.5 and item.stance is not EvidenceStance.IRRELEVANT
    )
    supporting = tuple(
        item.evidence_id for item in evidence if item.stance is EvidenceStance.SUPPORTS
    )
    challenging = tuple(
        item.evidence_id
        for item in evidence
        if item.stance in {EvidenceStance.CONTRADICTS, EvidenceStance.QUALIFIES}
    )
    return EvidenceCoverageCheck(
        claim_id=claim.claim_id,
        approved_evidence_ids=approved,
        relevant_evidence_ids=relevant,
        supporting_evidence_ids=supporting,
        challenging_evidence_ids=challenging,
        covered=bool(relevant),
        limitations=(
            "Coverage records approved relevant passages; it is not a probability.",
        ),
    )
