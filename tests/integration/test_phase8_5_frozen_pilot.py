"""Three-case zero-cost pilot for the promoted LangGraph research fan-out."""

import asyncio

import httpx

from claim_polygraph_ng.api_server import build_development_app

CLAIMS = (
    "The programme reduced emissions by 12 percent in 2024.",
    "The agency reported 42 cases in 2025.",
    "The policy applied to every participant.",
)


async def _run_pilot(app):
    rows = []
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://pilot",
    ) as client:
        for claim in CLAIMS:
            created = await client.post("/api/investigations", json={"claim": claim})
            assert created.status_code == 201
            report = created.json()
            investigation_id = report["investigation"]["investigation_id"]
            graph = await client.get(f"/api/graph-runs/{investigation_id}")
            assert graph.status_code == 200
            rows.append((report, graph.json()))
    return rows


def test_three_case_frozen_pilot_preserves_authority_and_zero_cost(tmp_path) -> None:
    rows = asyncio.run(_run_pilot(build_development_app(tmp_path)))

    assert len(rows) == 3
    for report, graph in rows:
        state = graph["research_state"]
        assert len(state["assignments"]) == len(state["results"]) == 3
        assert state["consumption"]["role_activations"] == 3
        assert state["consumption"]["model_calls"] == 0
        assert state["consumption"]["estimated_cost_usd"] == 0
        assert len(state["argument_role_result_ids"]) == 2
        assert state["reconciled_argument_ledger"] == report["argument_ledger"]
        assurance = report["full_report_assurance"]
        assert report["verdict"]["confidence"] is None
        assert report["readiness"]["confidence_score"] is None
        assert assurance["publication_status"] == "ready"
        assert assurance["final_audit"]["full_support_rate"] >= 0.95
        assert assurance["critical_failure_count"] == 0
        assert assurance["material_sentence_count"] == assurance["audited_material_sentence_count"]
        approved = set(state["approved_evidence_ids"])
        authoritative = {item["evidence_id"] for item in report["evidence"]}
        candidate_only = set(state["stored_evidence_ids"]) - approved
        assert approved == authoritative
        assert candidate_only
