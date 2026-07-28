"""Build the Stage 8.14 human-review packet from five frozen fixture cases."""

import argparse
import asyncio
import json
import tempfile
from pathlib import Path

import httpx

from claim_polygraph_ng.api_server import build_development_app
from claim_polygraph_ng.evaluation.phase8_promotion import FROZEN_PROMOTION_CLAIMS
from claim_polygraph_ng.persistence.research import SQLiteResearchRepository


async def build_packet() -> dict:
    cases = []
    with tempfile.TemporaryDirectory(prefix="cpng-stage8-14-review-") as directory:
        root = Path(directory)
        app = build_development_app(root, orchestrator="langgraph")
        repository = SQLiteResearchRepository(root / "research.db")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://review-packet",
        ) as client:
            for case_id, claim in FROZEN_PROMOTION_CLAIMS:
                response = await client.post(
                    "/api/investigations", json={"claim": claim}
                )
                response.raise_for_status()
                report = response.json()
                graph_response = await client.get(
                    f"/api/graph-runs/{report['investigation']['investigation_id']}"
                )
                graph_response.raise_for_status()
                state = graph_response.json()["research_state"]
                assignments = {
                    item["assignment_id"]: item["role"]
                    for item in state["assignments"]
                }
                approved_ids = set(state["approved_evidence_ids"])
                candidate_ids = tuple(
                    evidence_id
                    for evidence_id in state["stored_evidence_ids"]
                    if evidence_id not in approved_ids
                )
                evidence = {
                    str(item.evidence_id): item
                    for item in repository.get_evidence(candidate_ids)
                }
                source_ids = tuple(item.source_id for item in evidence.values())
                sources = {
                    str(item.source_id): item
                    for item in repository.get_sources(source_ids)
                }
                role_by_evidence = {}
                for result in state["results"]:
                    role = assignments[result["assignment_id"]]
                    for evidence_id in result["evidence_ids"]:
                        role_by_evidence[evidence_id] = role
                candidates = []
                for evidence_id in candidate_ids:
                    item = evidence[evidence_id]
                    source = sources[str(item.source_id)]
                    candidates.append(
                        {
                            "evidence_id": evidence_id,
                            "role": role_by_evidence[evidence_id],
                            "stance": item.stance.value,
                            "passage": item.passage,
                            "source_title": source.title,
                            "publisher": source.publisher,
                            "source_type": source.source_type.value,
                            "rights_status": source.rights_status.value,
                            "content_retention": source.content_retention.value,
                            "evidence_family_id": (
                                str(item.evidence_family_id)
                                if item.evidence_family_id
                                else None
                            ),
                        }
                    )
                cases.append(
                    {
                        "case_id": case_id,
                        "claim": claim,
                        "authoritative_verdict": report["verdict"]["label"],
                        "authoritative_evidence_count": len(report["evidence"]),
                        "candidate_evidence_count": len(candidates),
                        "candidates": candidates,
                    }
                )
    return {
        "packet_id": "phase8-stage8.14-targeted-human-review-v1",
        "status": "awaiting_human_review",
        "fixture_disclosure": (
            "All candidate passages in this packet come from deterministic synthetic "
            "providers. They test role separation and containment, not real-world factual "
            "quality. They must not be described as externally verified evidence."
        ),
        "promotion_question": (
            "Does the multi-agent packet materially improve research structure enough "
            "to promote it as the default research subgraph while InvestigationService "
            "remains authoritative?"
        ),
        "cases": cases,
        "reviewer_identity": None,
        "review_date": None,
        "review_decision": None,
        "approver_identity": None,
        "approval_date": None,
        "approval_decision": None,
    }


def render_markdown(packet: dict) -> str:
    lines = [
        "# Phase 8 Stage 8.14 targeted human-review packet",
        "",
        f"Status: **{packet['status']}**",
        "",
        "## Required disclosure",
        "",
        packet["fixture_disclosure"],
        "",
        "This review can approve the architecture and demonstrated role separation. "
        "It cannot claim that synthetic passages improve real-world factual accuracy.",
        "",
        "## Decision requested",
        "",
        packet["promotion_question"],
        "",
        "Promotion choices:",
        "",
        "- `promote_observational_default`: run multi-agent research by default, but "
        "keep its evidence observational and keep InvestigationService authoritative.",
        "- `hold`: retain the current observational opt-in/default arrangement pending "
        "a live reviewed evidence pilot.",
        "- `reject`: remove the multi-agent subgraph from the promoted journey.",
        "",
    ]
    for case in packet["cases"]:
        lines.extend(
            [
                f"## {case['case_id']}",
                "",
                f"**Claim:** {case['claim']}",
                "",
                f"**Authoritative verdict:** `{case['authoritative_verdict']}`",
                "",
                (
                    f"Authoritative evidence: {case['authoritative_evidence_count']}; "
                    f"candidate additions: {case['candidate_evidence_count']}."
                ),
                "",
            ]
        )
        for index, candidate in enumerate(case["candidates"], 1):
            lines.extend(
                [
                    f"### Candidate {index} — {candidate['role']}",
                    "",
                    f"- Stance: `{candidate['stance']}`",
                    f"- Source: {candidate['source_title']} ({candidate['source_type']})",
                    f"- Publisher: {candidate['publisher'] or 'not recorded'}",
                    f"- Rights: `{candidate['rights_status']}`; retention: "
                    f"`{candidate['content_retention']}`",
                    f"- Evidence family: `{candidate['evidence_family_id']}`",
                    "",
                    f"> {candidate['passage']}",
                    "",
                ]
            )
        lines.extend(
            [
                "Review checklist:",
                "",
                "- [ ] Candidate roles are meaningfully distinct rather than duplicated.",
                "- [ ] The challenger contributes a real contradiction or qualification.",
                "- [ ] Evidence-family separation is structurally credible.",
                "- [ ] No candidate escaped into the authoritative packet.",
                "- [ ] The synthetic-fixture limitation is acceptable for architecture "
                "promotion only.",
                "",
                "Case judgment: `improved / unchanged / worse`",
                "",
                "Notes:",
                "",
            ]
        )
    lines.extend(
        [
            "## Human decision record",
            "",
            "- Reviewer identity:",
            "- Review date:",
            "- Decision: `promote_observational_default / hold / reject`",
            "- Rationale:",
            "- Distinct approver identity:",
            "- Approval date:",
            "- Approval decision: `approve / reject`",
            "",
            "The final ADR must not be marked accepted until these fields and every "
            "case checklist are completed by humans.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    args = parser.parse_args()
    packet = asyncio.run(build_packet())
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(packet, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.markdown_output.write_text(render_markdown(packet), encoding="utf-8")
    print(f"Review cases: {len(packet['cases'])}")
    print(f"Status: {packet['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
