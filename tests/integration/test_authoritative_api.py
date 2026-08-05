"""Stage 9.10 single-job authoritative API and SSE integration."""

from time import sleep

from fastapi.testclient import TestClient

from claim_polygraph_ng.api import ApiDependencies, create_app
from claim_polygraph_ng.application.investigation_service import InvestigationService
from claim_polygraph_ng.application.langgraph_authoritative import (
    AuthoritativeFixtureLangGraphWorkflow,
)
from claim_polygraph_ng.domain.jobs import JobAdmissionPolicy
from claim_polygraph_ng.persistence import (
    SQLiteInvestigationRepository,
    SQLiteReviewLedger,
)
from claim_polygraph_ng.persistence.jobs import SQLiteJobQueue
from claim_polygraph_ng.providers import (
    DeterministicModelProvider,
    DeterministicSearchProvider,
)


def test_authoritative_job_exposes_checkpoint_sse_and_same_thread_review(tmp_path):
    investigations = SQLiteInvestigationRepository(tmp_path / "investigations.db")
    reviews = SQLiteReviewLedger(tmp_path / "reviews.db")
    service = InvestigationService(
        repository=investigations,
        model_provider=DeterministicModelProvider(),
        search_provider=DeterministicSearchProvider(),
    )
    workflow = AuthoritativeFixtureLangGraphWorkflow(
        service=service,
        investigations=investigations,
        langgraph_checkpoint_path=tmp_path / "langgraph.db",
        state_checkpoint_path=tmp_path / "state.db",
        review_ledger=reviews,
    )
    queue = SQLiteJobQueue(tmp_path / "jobs.db", JobAdmissionPolicy())
    app = create_app(
        ApiDependencies(
            investigations=investigations,
            reviews=reviews,
            graph_checkpoint_path=tmp_path / "legacy-graph.db",
            investigate=service.investigate,
            job_queue=queue,
            authoritative_workflow=workflow,
        )
    )

    with TestClient(app) as client:
        created = client.post(
            "/api/authoritative-jobs",
            json={"claim": "The fixture claim is true.", "idempotency_key": "stage9.10"},
        )
        assert created.status_code == 202
        job_id = created.json()["job"]["job_id"]
        thread_id = created.json()["thread_id"]

        current = created.json()
        for _ in range(200):
            current = client.get(f"/api/authoritative-jobs/{job_id}").json()
            if current["job"]["status"] in {"interrupted", "completed", "failed"}:
                break
            sleep(0.02)

        assert current["thread_id"] == thread_id
        assert current["graph"]["checkpoint_sequence"] > 0
        assert current["investigation_id"]
        assert current["publication_status"] in {
            "review_required",
            "published",
            "blocked",
        }
        reconstructed = client.get(
            f"/api/investigations/{current['investigation_id']}/authoritative-job"
        )
        assert reconstructed.status_code == 200
        assert reconstructed.json()["job"]["job_id"] == job_id
        assert reconstructed.json()["thread_id"] == thread_id
        assert reconstructed.json()["graph"]["checkpoint_sequence"] == current["graph"][
            "checkpoint_sequence"
        ]
        if current["job"]["status"] == "interrupted":
            assert current["report_available"] is True
            investigation_id = current["investigation_id"]
            provisional = client.get(f"/api/investigations/{investigation_id}/report")
            assert provisional.status_code == 200
            assert provisional.json()["verdict"]["human_review_required"] is True
            draft = client.get(
                f"/api/investigations/{investigation_id}/report",
                params={"format": "provisional_markdown"},
            )
            assert draft.status_code == 200
            assert "PROVISIONAL — HUMAN REVIEW REQUIRED" in draft.text

        with client.stream(
            "GET",
            f"/api/authoritative-jobs/{job_id}/events?follow=false",
        ) as response:
            body = "".join(response.iter_text())
        assert response.status_code == 200
        assert "event: authoritative_checkpoint" in body
        assert "event: authoritative_state" in body

        checkpoint = current["graph"]["checkpoint_sequence"] + 1
        with client.stream(
            "GET",
            f"/api/authoritative-jobs/{job_id}/events?follow=false",
            headers={"Last-Event-ID": str(checkpoint)},
        ) as response:
            resumed_body = "".join(response.iter_text())
        assert response.status_code == 200
        assert "event: authoritative_state" in resumed_body
        assert "event: authoritative_checkpoint" not in resumed_body

        if current["job"]["status"] == "interrupted":
            resumed = client.post(
                f"/api/authoritative-jobs/{job_id}/review",
                headers={"X-Reviewer-Identity": "Stage Reviewer"},
                json={
                    "decision": {
                        "kind": "approve",
                        "reviewer_identity": "Stage Reviewer",
                        "rationale": "The evidence packet and safeguards were reviewed.",
                    },
                    "approver_identity": "Distinct Stage Approver",
                },
            )
            assert resumed.status_code == 200
            payload = resumed.json()
            assert payload["job"]["status"] == "completed"
            assert payload["thread_id"] == thread_id
            assert payload["graph"]["phase"] == "complete"
            assert payload["review"]["chain_valid"] is True
            investigation = client.get(
                f"/api/investigations/{payload['investigation_id']}"
            ).json()
            assert investigation["status"] == "completed"
            assert investigation["stage"] == "complete"


def test_legacy_read_routes_remain_available_with_authoritative_api(tmp_path):
    investigations = SQLiteInvestigationRepository(tmp_path / "investigations.db")
    reviews = SQLiteReviewLedger(tmp_path / "reviews.db")
    app = create_app(
        ApiDependencies(
            investigations=investigations,
            reviews=reviews,
            graph_checkpoint_path=tmp_path / "legacy-graph.db",
        )
    )
    with TestClient(app) as client:
        assert client.get("/api/investigations").status_code == 200
        assert client.get("/api/reviews").status_code == 200
        assert client.post("/api/investigations", json={"claim": "A claim"}).status_code == 503
