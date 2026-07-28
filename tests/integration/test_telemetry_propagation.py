"""Trace propagation through real API middleware and durable job worker."""

from uuid import uuid4

from fastapi.testclient import TestClient

from claim_polygraph_ng.api import ApiDependencies, create_app
from claim_polygraph_ng.application.job_worker import DurableJobWorker
from claim_polygraph_ng.application.langgraph_durable import (
    DurableFixtureLangGraphWorkflow,
)
from claim_polygraph_ng.application.orchestrator import OrchestratorMode
from claim_polygraph_ng.domain.graph import FixtureGraphRequest
from claim_polygraph_ng.domain.jobs import JobAdmissionPolicy, JobSpec
from claim_polygraph_ng.domain.models import VerdictLabel
from claim_polygraph_ng.domain.telemetry import SpanKind
from claim_polygraph_ng.persistence.jobs import SQLiteJobQueue
from claim_polygraph_ng.persistence.review import SQLiteReviewLedger
from claim_polygraph_ng.persistence.sqlite import SQLiteInvestigationRepository
from claim_polygraph_ng.telemetry import TelemetryCollector


def test_api_accepts_w3c_parent_and_returns_continuation(tmp_path) -> None:
    telemetry = TelemetryCollector(tmp_path / "telemetry.sqlite3")
    app = create_app(
        ApiDependencies(
            investigations=SQLiteInvestigationRepository(tmp_path / "investigations.sqlite3"),
            reviews=SQLiteReviewLedger(tmp_path / "reviews.sqlite3"),
            graph_checkpoint_path=tmp_path / "graph.sqlite3",
            orchestrator_mode=OrchestratorMode.LANGGRAPH,
            telemetry=telemetry,
        )
    )
    parent = "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01"
    response = TestClient(app).get("/health", headers={"traceparent": parent})

    assert response.status_code == 200
    assert response.headers["traceparent"].startswith(
        "00-0123456789abcdef0123456789abcdef-"
    )
    spans = telemetry.trace("0123456789abcdef0123456789abcdef")
    assert [span.kind for span in spans] == [SpanKind.API, SpanKind.API]
    assert spans[0].parent_span_id == "0123456789abcdef"
    assert spans[1].parent_span_id == spans[0].span_id

    operational = TestClient(app).get("/api/operations/telemetry")
    assert operational.status_code == 200
    assert operational.json()["spans"] >= 2
    trace_response = TestClient(app).get(
        "/api/operations/traces/0123456789abcdef0123456789abcdef"
    )
    assert trace_response.status_code == 200
    assert len(trace_response.json()) >= 2


def test_job_continues_api_trace_and_child_provider_span(tmp_path) -> None:
    telemetry = TelemetryCollector(tmp_path / "telemetry.sqlite3")
    telemetry.initialize()
    queue = SQLiteJobQueue(tmp_path / "jobs.sqlite3", JobAdmissionPolicy())
    queue.initialize()
    with telemetry.span("api.submit", SpanKind.API) as api_context:
        job = queue.enqueue(
            JobSpec(
                idempotency_key="trace-job",
                kind="investigation",
                payload={"claim": "private"},
                traceparent=api_context.traceparent,
            )
        ).job

    def execute(_job, _context):
        with telemetry.span("provider.fixture", SpanKind.PROVIDER):
            return "artifacts/report.md"

    completed = DurableJobWorker(queue, "worker", telemetry).run_once(execute)
    assert completed is not None and completed.job_id == job.job_id
    spans = telemetry.trace(api_context.trace_id)
    kinds = [span.kind for span in spans]
    assert kinds == [SpanKind.API, SpanKind.JOB, SpanKind.PROVIDER]
    job_span = next(span for span in spans if span.kind is SpanKind.JOB)
    provider_span = next(span for span in spans if span.kind is SpanKind.PROVIDER)
    assert job_span.parent_span_id == api_context.span_id
    assert provider_span.parent_span_id == job_span.span_id


def test_langgraph_nodes_inherit_active_trace_and_emit_latency(tmp_path) -> None:
    telemetry = TelemetryCollector(tmp_path / "telemetry.sqlite3")
    telemetry.initialize()
    request = FixtureGraphRequest(
        claim_text="A deterministic telemetry fixture claim.",
        approved_evidence_ids=(uuid4(),),
        authoritative_verdict=VerdictLabel.SUPPORTED,
    )
    with telemetry.span("api.graph", SpanKind.API) as root, DurableFixtureLangGraphWorkflow(
        tmp_path / "graph.sqlite3",
        enabled=True,
        telemetry=telemetry,
    ) as workflow:
        workflow.start(request)

    spans = telemetry.trace(root.trace_id)
    node_spans = [span for span in spans if span.kind is SpanKind.LANGGRAPH]
    assert len(node_spans) == 10
    assert all(span.parent_span_id == root.span_id for span in node_spans)
    snapshot = telemetry.snapshot()
    latency = next(
        metric
        for metric in snapshot.metrics
        if metric.name.value == "langgraph.node_latency_ms"
    )
    assert latency.count == 10
