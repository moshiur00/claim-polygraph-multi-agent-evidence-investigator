"""Stage 7.5 typed API and persisted SSE integration tests."""

import asyncio
from uuid import uuid4

import httpx

from claim_polygraph_ng.api import ApiDependencies, create_app
from claim_polygraph_ng.application import ClaimExtractionService, InvestigationService
from claim_polygraph_ng.domain import (
    FixtureGraphRequest,
    ReviewDecision,
    ReviewDecisionKind,
    VerdictLabel,
)
from claim_polygraph_ng.domain.investigation import Investigation
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


def _client(tmp_path):
    repository = SQLiteInvestigationRepository(tmp_path / "investigations.db")
    service = InvestigationService(
        repository=repository,
        model_provider=DeterministicModelProvider(),
        search_provider=DeterministicSearchProvider(),
    )
    report = asyncio.run(service.investigate("The example policy reduced emissions."))
    ledger = SQLiteReviewLedger(tmp_path / "reviews.db")
    app = create_app(
        ApiDependencies(
            investigations=repository,
            reviews=ledger,
            graph_checkpoint_path=tmp_path / "graph.db",
            investigate=service.investigate,
            extract_claims=ClaimExtractionService().extract,
        )
    )
    return app, report


def test_article_extraction_returns_candidates_without_starting_investigation(tmp_path) -> None:
    app, existing = _client(tmp_path)
    before = asyncio.run(_request(app, "GET", "/api/investigations")).json()
    extracted = asyncio.run(
        _request(
            app,
            "POST",
            "/api/claim-inputs/extract",
            json={
                "kind": "article_text",
                "title": "Example report",
                "text": (
                    "Background information introduces the report. "
                    "The agency reported 42 cases in 2025."
                ),
            },
        )
    )
    after = asyncio.run(_request(app, "GET", "/api/investigations")).json()

    assert extracted.status_code == 200
    assert extracted.json()["candidates"][0]["text"] == (
        "The agency reported 42 cases in 2025."
    )
    assert not extracted.json()["automatic_investigation_started"]
    assert [item["investigation_id"] for item in before] == [
        item["investigation_id"] for item in after
    ] == [str(existing.investigation.investigation_id)]


async def _request(app, method: str, url: str, **kwargs):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.request(method, url, **kwargs)


def test_investigation_evidence_report_and_sse_are_exposed(tmp_path) -> None:
    app, report = _client(tmp_path)
    investigation_id = report.investigation.investigation_id

    listed = asyncio.run(_request(app, "GET", "/api/investigations"))
    health = asyncio.run(_request(app, "GET", "/health"))
    evidence = asyncio.run(_request(app, "GET", f"/api/investigations/{investigation_id}/evidence"))
    machine_report = asyncio.run(
        _request(app, "GET", f"/api/investigations/{investigation_id}/report")
    )
    markdown = asyncio.run(
        _request(
            app,
            "GET",
            f"/api/investigations/{investigation_id}/report?format=markdown",
        )
    )
    events = asyncio.run(
        _request(
            app,
            "GET",
            f"/api/investigations/{investigation_id}/events?follow=false",
        )
    )

    assert listed.status_code == evidence.status_code == machine_report.status_code == 200
    assert health.json()["orchestrator"] == "direct"
    assert health.json()["authoritative_service"] == "InvestigationService"
    assert listed.json()[0]["investigation_id"] == str(investigation_id)
    assert len(evidence.json()) == 3
    assert machine_report.json()["verdict"]["label"] == "mixed"
    assert markdown.headers["content-type"].startswith("text/plain")
    assert "# Claim Polygraph NG Investigation" in markdown.text
    assert events.headers["content-type"].startswith("text/event-stream")
    assert "event: investigation_completed" in events.text
    assert "data: {" in events.text


def test_async_investigation_job_is_idempotent_and_completes_once(tmp_path) -> None:
    repository = SQLiteInvestigationRepository(tmp_path / "investigations.db")
    service = InvestigationService(
        repository=repository,
        model_provider=DeterministicModelProvider(),
        search_provider=DeterministicSearchProvider(),
    )
    calls = 0

    async def investigate_once(claim: str):
        nonlocal calls
        calls += 1
        return await service.investigate(claim)

    app = create_app(
        ApiDependencies(
            investigations=repository,
            reviews=SQLiteReviewLedger(tmp_path / "reviews.db"),
            graph_checkpoint_path=tmp_path / "graph.db",
            investigate=investigate_once,
            job_queue=SQLiteJobQueue(
                tmp_path / "jobs.db",
                JobAdmissionPolicy(maximum_active_jobs=1, default_provider_limit=1),
            ),
        )
    )

    async def scenario():
        async with app.router.lifespan_context(app):
            first = await _request(
                app,
                "POST",
                "/api/investigation-jobs",
                json={
                    "claim": "The example policy reduced emissions.",
                    "idempotency_key": "same-request",
                },
            )
            replay = await _request(
                app,
                "POST",
                "/api/investigation-jobs",
                json={
                    "claim": "The example policy reduced emissions.",
                    "idempotency_key": "same-request",
                },
            )
            assert first.status_code == replay.status_code == 202
            assert first.json()["job"]["job_id"] == replay.json()["job"]["job_id"]
            job_id = first.json()["job"]["job_id"]
            for _ in range(100):
                state = await _request(app, "GET", f"/api/investigation-jobs/{job_id}")
                if state.json()["job"]["status"] == "completed":
                    break
                await asyncio.sleep(0.02)
            return state

    completed = asyncio.run(scenario())
    assert completed.json()["job"]["status"] == "completed"
    assert completed.json()["investigation_id"]
    assert calls == 1


def test_graph_review_resume_is_typed_durable_and_idempotent(tmp_path) -> None:
    app, report = _client(tmp_path)
    graph_id = uuid4()
    graph_request = FixtureGraphRequest(
        graph_run_id=graph_id,
        claim_text=report.claim.text,
        approved_evidence_ids=tuple(item.evidence_id for item in report.evidence),
        authoritative_verdict=report.verdict.label,
        review_required=True,
        review_reason="A reviewer must confirm this fixture verdict.",
    )
    started = asyncio.run(
        _request(
            app,
            "POST",
            "/api/graph-runs",
            json={
                "investigation_id": str(report.investigation.investigation_id),
                "claim_id": str(report.claim.claim_id),
                "graph": graph_request.model_dump(mode="json"),
            },
        )
    )
    assert started.status_code == 201
    request_id = started.json()["review"]["request_id"]
    assert started.json()["graph"]["status"] == "review_required"
    progress = asyncio.run(
        _request(
            app,
            "GET",
            f"/api/graph-runs/{graph_id}/events?follow=false",
            headers={"Origin": "http://localhost:3000"},
        )
    )
    assert progress.status_code == 200
    assert "event: graph_node" in progress.text
    assert "event: graph_state" in progress.text
    assert progress.headers["access-control-allow-origin"] == "http://localhost:3000"

    decision = ReviewDecision(
        kind=ReviewDecisionKind.APPROVE,
        reviewer_identity="Md Moshiur Rahman",
        rationale="The reviewed evidence supports the provisional verdict.",
    )
    decision_body = {
        "expected_sequence": 1,
        "decision": decision.model_dump(mode="json"),
    }
    completed = asyncio.run(
        _request(
            app,
            "POST",
            f"/api/reviews/{request_id}/decisions",
            json=decision_body,
            headers={"X-Reviewer-Identity": "Md Moshiur Rahman"},
        )
    )
    replayed = asyncio.run(
        _request(
            app,
            "POST",
            f"/api/reviews/{request_id}/decisions",
            json=decision_body,
            headers={"X-Reviewer-Identity": "Md Moshiur Rahman"},
        )
    )
    reconstructed = asyncio.run(_request(app, "GET", f"/api/graph-runs/{graph_id}"))

    assert completed.status_code == replayed.status_code == 200
    assert completed.json() == replayed.json()
    assert completed.json()["graph"]["status"] == "completed"
    assert len(completed.json()["review"]["decisions"]) == 1
    assert reconstructed.json()["applied_decision_id"] == str(decision.decision_id)


def test_stale_or_unattributed_decision_does_not_resume_graph(tmp_path) -> None:
    app, report = _client(tmp_path)
    graph_id = uuid4()
    request = FixtureGraphRequest(
        graph_run_id=graph_id,
        claim_text=report.claim.text,
        approved_evidence_ids=(report.evidence[0].evidence_id,),
        authoritative_verdict=VerdictLabel.MIXED,
        review_required=True,
        review_reason="Review is required for this fixture.",
    )
    started = asyncio.run(
        _request(
            app,
            "POST",
            "/api/graph-runs",
            json={
                "investigation_id": str(report.investigation.investigation_id),
                "claim_id": str(report.claim.claim_id),
                "graph": request.model_dump(mode="json"),
            },
        )
    ).json()
    decision = ReviewDecision(
        kind=ReviewDecisionKind.APPROVE,
        reviewer_identity="Md Moshiur Rahman",
        rationale="This should only apply with a current attributed request.",
    )
    endpoint = f"/api/reviews/{started['review']['request_id']}/decisions"
    forbidden = asyncio.run(
        _request(
            app,
            "POST",
            endpoint,
            json={"expected_sequence": 1, "decision": decision.model_dump(mode="json")},
        )
    )
    stale = asyncio.run(
        _request(
            app,
            "POST",
            endpoint,
            json={"expected_sequence": 99, "decision": decision.model_dump(mode="json")},
            headers={"X-Reviewer-Identity": "Md Moshiur Rahman"},
        )
    )
    graph = asyncio.run(_request(app, "GET", f"/api/graph-runs/{graph_id}"))

    assert forbidden.status_code == 403
    assert stale.status_code == 409
    assert graph.json()["status"] == "review_required"


def test_missing_and_incomplete_resources_have_stable_errors(tmp_path) -> None:
    app, _ = _client(tmp_path)
    missing = asyncio.run(_request(app, "GET", f"/api/investigations/{uuid4()}"))
    assert missing.status_code == 404

    repository = SQLiteInvestigationRepository(tmp_path / "incomplete.db")
    repository.initialize()
    investigation = Investigation(input_claim="An unfinished claim.")
    repository.save_investigation(investigation)
    incomplete_app = create_app(
        ApiDependencies(
            investigations=repository,
            reviews=SQLiteReviewLedger(tmp_path / "incomplete-reviews.db"),
            graph_checkpoint_path=tmp_path / "incomplete-graph.db",
        )
    )
    incomplete = asyncio.run(
        _request(
            incomplete_app,
            "GET",
            f"/api/investigations/{investigation.investigation_id}/report",
        )
    )
    assert incomplete.status_code == 409


def test_create_investigation_and_provider_failure_are_stable(tmp_path) -> None:
    app, _ = _client(tmp_path)
    created = asyncio.run(
        _request(
            app,
            "POST",
            "/api/investigations",
            json={"claim": "A newly submitted factual claim."},
        )
    )
    assert created.status_code == 201
    assert created.headers["x-claim-polygraph-orchestrator"] == "direct"
    assert created.headers["x-claim-polygraph-authority"] == "InvestigationService"
    assert created.json()["investigation"]["status"] == "completed"

    async def fail(_claim: str):
        raise RuntimeError("secret provider details")

    repository = SQLiteInvestigationRepository(tmp_path / "failed.db")
    failed_app = create_app(
        ApiDependencies(
            investigations=repository,
            reviews=SQLiteReviewLedger(tmp_path / "failed-reviews.db"),
            graph_checkpoint_path=tmp_path / "failed-graph.db",
            investigate=fail,
        )
    )
    failed = asyncio.run(
        _request(
            failed_app,
            "POST",
            "/api/investigations",
            json={"claim": "A provider failure fixture."},
        )
    )
    assert failed.status_code == 502
    assert failed.json()["detail"] == "investigation provider failed: RuntimeError"
