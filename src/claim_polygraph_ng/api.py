"""FastAPI surface for persisted investigations and durable fixture graphs."""

import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from uuid import UUID, uuid4

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse

from claim_polygraph_ng.application.langgraph_authoritative import (
    AuthoritativeFixtureLangGraphWorkflow,
)
from claim_polygraph_ng.application.langgraph_durable import (
    DuplicateReviewDecisionError,
    DurableFixtureLangGraphWorkflow,
    ExistingGraphThreadError,
    GraphResumeError,
)
from claim_polygraph_ng.application.orchestrator import OrchestratorMode
from claim_polygraph_ng.domain.api import (
    ApiStatus,
    AuthoritativeJobResponse,
    AuthoritativeReviewRequest,
    CreateInvestigationRequest,
    InvestigationJobResponse,
    StartGraphRunRequest,
    StartGraphRunResponse,
    SubmitApprovalRequest,
    SubmitDecisionRequest,
    SubmitDecisionResponse,
    SubmitRevisionRequest,
)
from claim_polygraph_ng.domain.graph import DurableGraphSnapshot
from claim_polygraph_ng.domain.input import ClaimExtractionPacket, InvestigationInput
from claim_polygraph_ng.domain.investigation import (
    ArtifactType,
    Investigation,
    InvestigationReport,
    InvestigationStatus,
)
from claim_polygraph_ng.domain.jobs import (
    TERMINAL_JOB_STATUSES,
    JobFailureClass,
    JobSpec,
    JobStatus,
)
from claim_polygraph_ng.domain.models import AtomicClaim, Evidence, Verdict
from claim_polygraph_ng.domain.review import (
    ReviewAuditTrail,
    ReviewerDecisionRecord,
    ReviewRequest,
)
from claim_polygraph_ng.domain.telemetry import (
    AlertRule,
    MetricName,
    SpanKind,
    TelemetrySnapshot,
    TelemetrySpan,
)
from claim_polygraph_ng.persistence.authoritative_graph import (
    AuthoritativeCheckpointCorruptionError,
)
from claim_polygraph_ng.persistence.base import InvestigationRepository
from claim_polygraph_ng.persistence.jobs import JobBackpressureError, SQLiteJobQueue
from claim_polygraph_ng.persistence.review import (
    ReviewConcurrencyError,
    ReviewLedgerError,
    ReviewPolicyError,
    SQLiteReviewLedger,
)
from claim_polygraph_ng.providers import ModelUnavailableError, SearchProviderError
from claim_polygraph_ng.reporting import (
    IncompleteInvestigationError,
    InvestigationNotFoundError,
    PublicationBlockedError,
    load_report,
    render_markdown,
    render_publishable_markdown,
)
from claim_polygraph_ng.telemetry import (
    DEFAULT_ALERT_RULES,
    TelemetryCollector,
    parse_traceparent,
)


@dataclass(frozen=True)
class ApiDependencies:
    """Explicit resources used by the API; production and tests can wire separately."""

    investigations: InvestigationRepository
    reviews: SQLiteReviewLedger
    graph_checkpoint_path: Path
    graph_enabled: bool = True
    investigate: Callable[[str], Awaitable[InvestigationReport]] | None = None
    orchestrator_mode: OrchestratorMode = OrchestratorMode.DIRECT
    extract_claims: Callable[[InvestigationInput], Awaitable[ClaimExtractionPacket]] | None = None
    telemetry: TelemetryCollector | None = None
    telemetry_rules: tuple[AlertRule, ...] = DEFAULT_ALERT_RULES
    retrieval_provider: str = "deterministic"
    live_research: bool = False
    model_provider: str = "deterministic"
    job_queue: SQLiteJobQueue | None = None
    authoritative_workflow: AuthoritativeFixtureLangGraphWorkflow | None = None


def create_app(dependencies: ApiDependencies) -> FastAPI:
    """Build the Stage 7.5 API without global mutable service state."""
    dependencies.investigations.initialize()
    dependencies.reviews.initialize()
    app = FastAPI(title="Claim Polygraph NG API", version="10.9")
    allowed_origins = tuple(
        origin.strip()
        for origin in os.getenv(
            "CLAIM_POLYGRAPH_DASHBOARD_ORIGINS",
            (
                "http://localhost:3000,http://127.0.0.1:3000,"
                "http://localhost:5173,http://127.0.0.1:5173,"
                "https://claim-polygraph-review.moshiur-mishuk00.chatgpt.site"
            ),
        ).split(",")
        if origin.strip()
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Reviewer-Identity"],
    )

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "name": "Claim Polygraph NG API",
            "status": "ok",
            "health": "/health",
            "documentation": "/docs",
            "dashboard": "http://localhost:3000",
        }

    if dependencies.telemetry is not None:
        dependencies.telemetry.initialize()

        @app.middleware("http")
        async def observe_request(request: Request, call_next):
            started = perf_counter()
            parent = parse_traceparent(request.headers.get("traceparent"))
            route_kind = (
                SpanKind.REVIEW
                if "/reviews" in request.url.path
                else SpanKind.LANGGRAPH
                if "/graph-runs" in request.url.path
                else SpanKind.API
            )
            with dependencies.telemetry.span(
                f"http.{request.method.casefold()}",
                SpanKind.API,
                parent=parent,
                attributes={
                    "http.method": request.method,
                    "http.route_group": route_kind.value,
                },
            ) as api_context:
                with dependencies.telemetry.span(
                    f"{route_kind.value}.request",
                    route_kind,
                    attributes={"http.method": request.method},
                ):
                    response = await call_next(request)
                response.headers["traceparent"] = api_context.traceparent
                dependencies.telemetry.metric(
                    MetricName.API_LATENCY_MS,
                    (perf_counter() - started) * 1_000,
                    "ms",
                    attributes={
                        "http.method": request.method,
                        "http.status_code": response.status_code,
                        "http.route_group": route_kind.value,
                    },
                )
                return response

    worker_wakeup = asyncio.Event()
    worker_task: asyncio.Task | None = None

    def resolve_job_investigation(job) -> UUID | None:
        if job.result_reference:
            return UUID(job.result_reference)
        claim = str(job.spec.payload.get("claim", ""))
        candidates = [
            item
            for item in dependencies.investigations.list_investigations()
            if item.input_claim == claim and item.created_at >= job.created_at
        ]
        return candidates[0].investigation_id if candidates else None

    async def execute_next_job() -> bool:
        if dependencies.job_queue is None or dependencies.investigate is None:
            return False
        job = dependencies.job_queue.claim("api-async-worker", lease_seconds=90)
        if job is None:
            return False
        renewal_stopped = asyncio.Event()

        async def renew_lease() -> None:
            while not renewal_stopped.is_set():
                try:
                    await asyncio.wait_for(renewal_stopped.wait(), timeout=30)
                except TimeoutError:
                    try:
                        dependencies.job_queue.renew_lease(
                            job.job_id, "api-async-worker", lease_seconds=90
                        )
                    except Exception:
                        return

        renewer = asyncio.create_task(renew_lease())
        try:
            if (
                job.spec.kind == "authoritative_langgraph_investigation"
                and dependencies.authoritative_workflow is not None
            ):
                thread_id = str(job.spec.payload["thread_id"])

                def authoritative_safe_boundary() -> None:
                    boundary = dependencies.job_queue.safe_boundary(
                        job.job_id, "api-async-worker"
                    )
                    if boundary.status is JobStatus.CANCELLED:
                        raise RuntimeError("authoritative job cancelled at node boundary")

                graph_result = await dependencies.authoritative_workflow.start(
                    str(job.spec.payload["claim"]),
                    thread_id=thread_id,
                    safe_boundary=authoritative_safe_boundary,
                )
                current = dependencies.job_queue.safe_boundary(
                    job.job_id, "api-async-worker"
                )
                if current.status is JobStatus.CANCELLED:
                    return True
                if graph_result.interrupt is not None:
                    dependencies.job_queue.interrupt(
                        job.job_id,
                        "api-async-worker",
                        reason=graph_result.interrupt.route_reason,
                    )
                else:
                    dependencies.job_queue.complete(
                        job.job_id,
                        "api-async-worker",
                        result_reference=thread_id,
                    )
                return True
            report = await dependencies.investigate(str(job.spec.payload["claim"]))
            current = dependencies.job_queue.safe_boundary(job.job_id, "api-async-worker")
            if current.status is not JobStatus.CANCELLED:
                dependencies.job_queue.complete(
                    job.job_id,
                    "api-async-worker",
                    result_reference=str(report.investigation.investigation_id),
                )
        except Exception as error:
            current = dependencies.job_queue.load(job.job_id)
            if current.status in {JobStatus.RUNNING, JobStatus.CANCELLING}:
                fallback_id = resolve_job_investigation(job)
                fallback = (
                    dependencies.investigations.get_investigation(fallback_id)
                    if fallback_id is not None
                    else None
                )
                if fallback is not None and fallback.status is InvestigationStatus.COMPLETED:
                    dependencies.job_queue.complete(
                        job.job_id,
                        "api-async-worker",
                        result_reference=str(fallback.investigation_id),
                    )
                else:
                    dependencies.job_queue.fail(
                        job.job_id,
                        "api-async-worker",
                        classification=(
                            JobFailureClass.TRANSIENT
                            if isinstance(
                                error, (SearchProviderError, ModelUnavailableError)
                            )
                            else JobFailureClass.PERMANENT
                        ),
                        error=f"{type(error).__name__}: {error}",
                    )
        finally:
            renewal_stopped.set()
            await renewer
        return True

    async def worker_loop() -> None:
        if dependencies.job_queue is None:
            return
        dependencies.job_queue.recover_expired_leases()
        while True:
            if await execute_next_job():
                continue
            worker_wakeup.clear()
            with suppress(TimeoutError):
                await asyncio.wait_for(worker_wakeup.wait(), timeout=1)

    @app.on_event("startup")
    async def start_job_worker() -> None:
        nonlocal worker_task
        if dependencies.job_queue is not None:
            dependencies.job_queue.initialize()
            worker_task = asyncio.create_task(worker_loop())

    @app.on_event("shutdown")
    async def stop_job_worker() -> None:
        if worker_task is not None:
            worker_task.cancel()
            with suppress(asyncio.CancelledError):
                await worker_task

    @app.get("/health", response_model=ApiStatus)
    def health() -> ApiStatus:
        return ApiStatus(
            status="ok",
            orchestrator=dependencies.orchestrator_mode.value,
            retrieval_provider=dependencies.retrieval_provider,
            live_research=dependencies.live_research,
            model_provider=dependencies.model_provider,
        )

    def authoritative_response(job) -> AuthoritativeJobResponse:
        workflow = dependencies.authoritative_workflow
        if workflow is None:
            raise HTTPException(
                status_code=503, detail="authoritative LangGraph is not configured"
            )
        thread_id = str(job.spec.payload.get("thread_id") or job.result_reference or "")
        if not thread_id:
            raise HTTPException(status_code=409, detail="job has no authoritative thread")
        try:
            state = workflow.latest_state(thread_id)
        except AuthoritativeCheckpointCorruptionError as error:
            raise HTTPException(
                status_code=503,
                detail="authoritative checkpoint integrity validation failed",
            ) from error
        trail = workflow.review_trail(thread_id)
        stored_report = None
        if state is not None and (
            state.final_report_ref is not None
            or (
                state.readiness_ref is not None
                and state.publication_decision_ref is not None
            )
        ):
            try:
                stored_report = load_report(
                    dependencies.investigations,
                    state.investigation_id,
                    require_completed=state.final_report_ref is not None,
                )
            except (InvestigationNotFoundError, IncompleteInvestigationError):
                stored_report = None
        interruption = None
        if job.status is JobStatus.INTERRUPTED and trail is not None:
            # The immutable request is the durable public representation of the
            # LangGraph interrupt; no synthetic node progress is emitted.
            from claim_polygraph_ng.domain.graph import (
                ReviewDecisionKind,
                ReviewInterruptPayload,
            )

            claims = (
                dependencies.investigations.list_artifacts(
                    state.investigation_id,
                    ArtifactType.CLAIM,
                    AtomicClaim,
                )
                if state is not None
                else ()
            )
            verdicts = (
                dependencies.investigations.list_artifacts(
                    state.investigation_id,
                    ArtifactType.ENFORCED_VERDICT,
                    Verdict,
                )
                or dependencies.investigations.list_artifacts(
                    state.investigation_id,
                    ArtifactType.PROPOSED_VERDICT,
                    Verdict,
                )
                if state is not None
                else ()
            )
            claim = (
                stored_report.claim
                if stored_report is not None
                else claims[0]
                if claims
                else None
            )
            verdict = (
                stored_report.verdict
                if stored_report is not None
                else verdicts[0]
                if verdicts
                else None
            )
            if claim is not None and verdict is not None:
                allowed_decisions = (
                    (
                        ReviewDecisionKind.REQUEST_EVIDENCE,
                        ReviewDecisionKind.REJECT,
                    )
                    if state is not None and not state.approved_evidence_ids
                    else (
                        ReviewDecisionKind.APPROVE,
                        ReviewDecisionKind.REVISE,
                        ReviewDecisionKind.REQUEST_EVIDENCE,
                        ReviewDecisionKind.REJECT,
                    )
                )
                interruption = ReviewInterruptPayload(
                    thread_id=thread_id,
                    question="Should this investigation be approved for publication?",
                    claim_text=claim.text,
                    provisional_verdict=verdict.label,
                    approved_evidence_ids=state.approved_evidence_ids,
                    route_reason=trail.request.reason,
                    allowed_decisions=allowed_decisions,
                )
        decision_kind = (
            trail.decisions[-1].kind.value
            if trail is not None and trail.decisions
            else None
        )
        publication_status = (
            "more_evidence_required"
            if decision_kind == "request_evidence"
            else "rejected"
            if decision_kind == "reject"
            else
            "published"
            if state is not None
            and state.phase.value == "complete"
            and not state.publication_blocked
            else "blocked"
            if state is not None and state.publication_blocked
            else "review_required"
            if job.status is JobStatus.INTERRUPTED
            else "processing"
            if job.status in {JobStatus.QUEUED, JobStatus.RUNNING}
            else job.status.value
        )
        return AuthoritativeJobResponse(
            job=job,
            thread_id=thread_id,
            investigation_id=state.investigation_id if state is not None else None,
            graph=state,
            interruption=interruption,
            review=trail,
            publication_status=publication_status,
            verdict=stored_report.verdict.label.value if stored_report is not None else None,
            report_available=stored_report is not None,
            events=dependencies.job_queue.audit_events(job.job_id)
            if dependencies.job_queue is not None
            else (),
        )

    @app.post(
        "/api/authoritative-jobs",
        response_model=AuthoritativeJobResponse,
        status_code=202,
    )
    async def create_authoritative_job(
        payload: CreateInvestigationRequest,
        response: Response,
    ) -> AuthoritativeJobResponse:
        if dependencies.job_queue is None or dependencies.authoritative_workflow is None:
            raise HTTPException(
                status_code=503, detail="authoritative LangGraph jobs are not configured"
            )
        thread_id = str(uuid4())
        key = payload.idempotency_key or f"authoritative:{thread_id}"
        try:
            admitted = dependencies.job_queue.enqueue(
                JobSpec(
                    idempotency_key=key,
                    kind="authoritative_langgraph_investigation",
                    payload={"claim": payload.claim, "thread_id": thread_id},
                    provider=dependencies.retrieval_provider,
                    maximum_attempts=2,
                )
            )
        except JobBackpressureError as error:
            raise HTTPException(status_code=429, detail=str(error)) from error
        worker_wakeup.set()
        response.headers["Location"] = f"/api/authoritative-jobs/{admitted.job.job_id}"
        return authoritative_response(admitted.job)

    @app.get(
        "/api/authoritative-jobs/{job_id}",
        response_model=AuthoritativeJobResponse,
    )
    def get_authoritative_job(job_id: UUID) -> AuthoritativeJobResponse:
        if dependencies.job_queue is None:
            raise HTTPException(status_code=503, detail="durable jobs are not configured")
        try:
            job = dependencies.job_queue.load(job_id)
        except Exception as error:
            raise HTTPException(status_code=404, detail="job not found") from error
        if job.spec.kind != "authoritative_langgraph_investigation":
            raise HTTPException(status_code=404, detail="authoritative job not found")
        return authoritative_response(job)

    @app.post(
        "/api/authoritative-jobs/{job_id}/review",
        response_model=AuthoritativeJobResponse,
    )
    async def review_authoritative_job(
        job_id: UUID,
        payload: AuthoritativeReviewRequest,
        x_reviewer_identity: str | None = Header(default=None),
    ) -> AuthoritativeJobResponse:
        if dependencies.job_queue is None or dependencies.authoritative_workflow is None:
            raise HTTPException(status_code=503, detail="authoritative jobs are not configured")
        _require_identity(x_reviewer_identity, payload.decision.reviewer_identity)
        try:
            job = dependencies.job_queue.load(job_id)
            if job.spec.kind != "authoritative_langgraph_investigation":
                raise HTTPException(status_code=404, detail="authoritative job not found")
            thread_id = str(job.spec.payload["thread_id"])
            result = await dependencies.authoritative_workflow.resume(
                thread_id,
                payload.decision,
                approver_identity=payload.approver_identity,
            )
            if result.interrupt is None:
                job = dependencies.job_queue.complete_interrupted(
                    job_id,
                    actor=payload.decision.reviewer_identity,
                    result_reference=thread_id,
                )
            return authoritative_response(job)
        except HTTPException:
            raise
        except (DuplicateReviewDecisionError, GraphResumeError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post(
        "/api/authoritative-jobs/{job_id}/cancel",
        response_model=AuthoritativeJobResponse,
    )
    def cancel_authoritative_job(
        job_id: UUID,
        x_reviewer_identity: str = Header(default="dashboard-user"),
    ) -> AuthoritativeJobResponse:
        if dependencies.job_queue is None:
            raise HTTPException(status_code=503, detail="durable jobs are not configured")
        try:
            job = dependencies.job_queue.load(job_id)
            if job.spec.kind != "authoritative_langgraph_investigation":
                raise HTTPException(status_code=404, detail="authoritative job not found")
            job = dependencies.job_queue.request_cancellation(
                job_id, actor=x_reviewer_identity
            )
            return authoritative_response(job)
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/api/authoritative-jobs/{job_id}/events")
    async def stream_authoritative_job_events(
        job_id: UUID,
        after: int = Query(default=0, ge=0),
        follow: bool = Query(default=True),
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    ) -> StreamingResponse:
        if dependencies.job_queue is None or dependencies.authoritative_workflow is None:
            raise HTTPException(status_code=503, detail="authoritative jobs are not configured")
        try:
            job = dependencies.job_queue.load(job_id)
        except Exception as error:
            raise HTTPException(status_code=404, detail="job not found") from error
        if job.spec.kind != "authoritative_langgraph_investigation":
            raise HTTPException(status_code=404, detail="authoritative job not found")
        try:
            dependencies.authoritative_workflow.state_history(
                str(job.spec.payload["thread_id"])
            )
        except AuthoritativeCheckpointCorruptionError as error:
            raise HTTPException(
                status_code=503,
                detail="authoritative checkpoint integrity validation failed",
            ) from error

        if last_event_id is not None:
            try:
                reconnect_cursor = int(last_event_id)
            except ValueError as error:
                raise HTTPException(
                    status_code=422, detail="Last-Event-ID must be a non-negative integer"
                ) from error
            if reconnect_cursor < 0:
                raise HTTPException(
                    status_code=422, detail="Last-Event-ID must be a non-negative integer"
                )
        else:
            reconnect_cursor = 0

        async def generate_authoritative_events():
            cursor = max(after, reconnect_cursor)
            last_job_sequence = 0
            while True:
                current = dependencies.job_queue.load(job_id)
                thread_id = str(current.spec.payload["thread_id"])
                history = dependencies.authoritative_workflow.state_history(thread_id)
                for state in history:
                    event_sequence = state.checkpoint_sequence + 1
                    if event_sequence <= cursor:
                        continue
                    yield (
                        f"id: {event_sequence}\nevent: authoritative_checkpoint\ndata: "
                        f"{state.model_dump_json()}\n\n"
                    )
                    cursor = event_sequence
                events = dependencies.job_queue.audit_events(job_id)
                for event in events:
                    if event.sequence <= last_job_sequence:
                        continue
                    yield f"event: job_event\ndata: {event.model_dump_json()}\n\n"
                    last_job_sequence = event.sequence
                payload = authoritative_response(current)
                yield f"event: authoritative_state\ndata: {payload.model_dump_json()}\n\n"
                if not follow or current.status in TERMINAL_JOB_STATUSES or (
                    current.status is JobStatus.INTERRUPTED
                ):
                    break
                yield ": keep-alive\n\n"
                await asyncio.sleep(0.25)

        return StreamingResponse(
            generate_authoritative_events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/investigations", response_model=list[Investigation])
    def list_investigations() -> list[Investigation]:
        return list(dependencies.investigations.list_investigations())

    @app.get("/api/operations/telemetry", response_model=TelemetrySnapshot)
    def get_telemetry() -> TelemetrySnapshot:
        if dependencies.telemetry is None:
            raise HTTPException(status_code=503, detail="telemetry is not configured")
        return dependencies.telemetry.snapshot(dependencies.telemetry_rules)

    @app.get("/api/operations/traces/{trace_id}", response_model=list[TelemetrySpan])
    def get_trace(trace_id: str) -> list[TelemetrySpan]:
        if dependencies.telemetry is None:
            raise HTTPException(status_code=503, detail="telemetry is not configured")
        invalid_hex = any(
            character not in "0123456789abcdef" for character in trace_id
        )
        if len(trace_id) != 32 or invalid_hex:
            raise HTTPException(status_code=422, detail="trace ID must be 32 lowercase hex digits")
        return list(dependencies.telemetry.trace(trace_id))

    @app.post(
        "/api/claim-inputs/extract",
        response_model=ClaimExtractionPacket,
        status_code=200,
    )
    async def extract_claims(payload: InvestigationInput) -> ClaimExtractionPacket:
        if dependencies.extract_claims is None:
            raise HTTPException(status_code=503, detail="claim extraction is not configured")
        try:
            return await dependencies.extract_claims(payload)
        except Exception as error:
            raise HTTPException(
                status_code=422,
                detail=f"claim extraction failed: {type(error).__name__}",
            ) from error

    @app.post(
        "/api/investigations",
        response_model=InvestigationReport,
        status_code=201,
    )
    async def create_investigation(
        payload: CreateInvestigationRequest,
        response: Response,
    ) -> InvestigationReport:
        if dependencies.investigate is None:
            raise HTTPException(status_code=503, detail="investigation runner is not configured")
        try:
            report = await dependencies.investigate(payload.claim)
            response.headers["X-Claim-Polygraph-Orchestrator"] = (
                dependencies.orchestrator_mode.value
            )
            response.headers["X-Claim-Polygraph-Authority"] = "InvestigationService"
            return report
        except Exception as error:
            raise HTTPException(
                status_code=502,
                detail=f"investigation provider failed: {type(error).__name__}",
            ) from error

    @app.post(
        "/api/investigation-jobs",
        response_model=InvestigationJobResponse,
        status_code=202,
    )
    async def create_investigation_job(
        payload: CreateInvestigationRequest,
        response: Response,
    ) -> InvestigationJobResponse:
        if dependencies.job_queue is None or dependencies.investigate is None:
            raise HTTPException(
                status_code=503,
                detail="durable investigation jobs are not configured",
            )
        key = payload.idempotency_key or f"investigation:{uuid4()}"
        try:
            admitted = dependencies.job_queue.enqueue(
                JobSpec(
                    idempotency_key=key,
                    kind="authoritative_investigation",
                    payload={"claim": payload.claim},
                    provider=dependencies.retrieval_provider,
                    maximum_attempts=1,
                )
            )
        except JobBackpressureError as error:
            raise HTTPException(status_code=429, detail=str(error)) from error
        worker_wakeup.set()
        response.headers["Location"] = f"/api/investigation-jobs/{admitted.job.job_id}"
        return InvestigationJobResponse(
            job=admitted.job,
            events=dependencies.job_queue.audit_events(admitted.job.job_id),
        )

    @app.get(
        "/api/investigation-jobs/{job_id}",
        response_model=InvestigationJobResponse,
    )
    def get_investigation_job(job_id: UUID) -> InvestigationJobResponse:
        if dependencies.job_queue is None:
            raise HTTPException(
                status_code=503,
                detail="durable investigation jobs are not configured",
            )
        try:
            job = dependencies.job_queue.load(job_id)
            investigation_id = resolve_job_investigation(job)
            return InvestigationJobResponse(
                job=job,
                investigation_id=investigation_id,
                events=dependencies.job_queue.audit_events(job_id),
            )
        except Exception as error:
            raise HTTPException(status_code=404, detail=f"job not found: {job_id}") from error

    @app.post(
        "/api/investigation-jobs/{job_id}/cancel",
        response_model=InvestigationJobResponse,
    )
    def cancel_investigation_job(
        job_id: UUID,
        x_reviewer_identity: str = Header(default="dashboard-user"),
    ) -> InvestigationJobResponse:
        if dependencies.job_queue is None:
            raise HTTPException(
                status_code=503,
                detail="durable investigation jobs are not configured",
            )
        try:
            job = dependencies.job_queue.request_cancellation(job_id, actor=x_reviewer_identity)
            return InvestigationJobResponse(
                job=job, events=dependencies.job_queue.audit_events(job_id)
            )
        except Exception as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/api/investigation-jobs/{job_id}/events")
    async def stream_investigation_job_events(
        job_id: UUID,
        after: int = Query(default=0, ge=0),
        follow: bool = Query(default=True),
    ) -> StreamingResponse:
        if dependencies.job_queue is None:
            raise HTTPException(
                status_code=503,
                detail="durable investigation jobs are not configured",
            )
        try:
            dependencies.job_queue.load(job_id)
        except Exception as error:
            raise HTTPException(status_code=404, detail=f"job not found: {job_id}") from error

        async def generate_job_events():
            cursor = after
            while True:
                job = dependencies.job_queue.load(job_id)
                events = dependencies.job_queue.audit_events(job_id)
                for event in events:
                    if event.sequence <= cursor:
                        continue
                    yield (
                        f"id: {event.sequence}\nevent: job_event\ndata: "
                        f"{event.model_dump_json()}\n\n"
                    )
                    cursor = event.sequence
                payload = InvestigationJobResponse(
                    job=job,
                    investigation_id=resolve_job_investigation(job),
                    events=events,
                )
                yield f"event: job_state\ndata: {payload.model_dump_json()}\n\n"
                if not follow or job.status in TERMINAL_JOB_STATUSES:
                    break
                yield ": keep-alive\n\n"
                await asyncio.sleep(0.5)

        return StreamingResponse(generate_job_events(), media_type="text/event-stream")

    @app.get("/api/investigations/{investigation_id}", response_model=Investigation)
    def get_investigation(investigation_id: UUID) -> Investigation:
        investigation = dependencies.investigations.get_investigation(investigation_id)
        if investigation is None:
            raise HTTPException(status_code=404, detail="investigation not found")
        return investigation

    @app.get(
        "/api/investigations/{investigation_id}/evidence",
        response_model=list[Evidence],
    )
    def get_evidence(investigation_id: UUID) -> list[Evidence]:
        _require_investigation(dependencies.investigations, investigation_id)
        return list(
            dependencies.investigations.list_artifacts(
                investigation_id, ArtifactType.EVIDENCE, Evidence
            )
        )

    @app.get("/api/investigations/{investigation_id}/report")
    def get_report(investigation_id: UUID, format: str = Query(default="json")):
        try:
            report = load_report(
                dependencies.investigations,
                investigation_id,
                require_completed=False,
            )
        except InvestigationNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except IncompleteInvestigationError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if format in {"markdown", "provisional_markdown"}:
            events = dependencies.investigations.list_events(investigation_id)
            if format == "provisional_markdown":
                return PlainTextResponse(
                    "> **PROVISIONAL — HUMAN REVIEW REQUIRED BEFORE PUBLICATION**\n\n"
                    + render_markdown(report, events)
                )
            try:
                return PlainTextResponse(render_publishable_markdown(report, events))
            except PublicationBlockedError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
        if format != "json":
            raise HTTPException(
                status_code=422,
                detail="format must be json, markdown, or provisional_markdown",
            )
        return report

    @app.post("/api/graph-runs", response_model=StartGraphRunResponse, status_code=201)
    def start_graph(payload: StartGraphRunRequest) -> StartGraphRunResponse:
        _require_investigation(dependencies.investigations, payload.investigation_id)
        with _workflow(dependencies) as workflow:
            try:
                snapshot = workflow.start(payload.graph)
            except ExistingGraphThreadError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
        review = None
        if snapshot.interrupt is not None:
            review = ReviewRequest(
                investigation_id=payload.investigation_id,
                graph_thread_id=snapshot.thread_id,
                claim_id=payload.claim_id,
                reason=snapshot.interrupt.route_reason,
                created_by=payload.review_created_by,
            )
            dependencies.reviews.create_request(review)
        return StartGraphRunResponse(graph=snapshot, review=review)

    @app.get("/api/graph-runs/{thread_id}", response_model=DurableGraphSnapshot)
    def get_graph(thread_id: str) -> DurableGraphSnapshot:
        with _workflow(dependencies) as workflow:
            try:
                return workflow.snapshot(thread_id)
            except GraphResumeError as error:
                raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/api/graph-runs/{thread_id}/events")
    async def stream_graph_events(
        thread_id: str,
        after: int = Query(default=0, ge=0),
        follow: bool = Query(default=True),
    ) -> StreamingResponse:
        with _workflow(dependencies) as workflow:
            try:
                workflow.snapshot(thread_id)
            except GraphResumeError as error:
                raise HTTPException(status_code=404, detail=str(error)) from error

        async def generate():
            cursor = after
            while True:
                with _workflow(dependencies) as workflow:
                    snapshot = workflow.snapshot(thread_id)
                for sequence, node in enumerate(snapshot.completed_nodes, 1):
                    if sequence <= cursor:
                        continue
                    data = json.dumps(
                        {"thread_id": thread_id, "node": node.value},
                        separators=(",", ":"),
                    )
                    yield f"id: {sequence}\nevent: graph_node\ndata: {data}\n\n"
                    cursor = sequence
                data = json.dumps(snapshot.model_dump(mode="json"), separators=(",", ":"))
                yield f"event: graph_state\ndata: {data}\n\n"
                if not follow or snapshot.status.value != "review_required":
                    break
                yield ": keep-alive\n\n"
                await asyncio.sleep(0.25)

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/reviews", response_model=list[ReviewRequest])
    def list_reviews() -> list[ReviewRequest]:
        return list(dependencies.reviews.list_requests())

    @app.get("/api/reviews/{request_id}", response_model=ReviewAuditTrail)
    def get_review(request_id: UUID) -> ReviewAuditTrail:
        return _load_review(dependencies.reviews, request_id)

    @app.post(
        "/api/reviews/{request_id}/decisions",
        response_model=SubmitDecisionResponse,
    )
    def submit_decision(
        request_id: UUID,
        payload: SubmitDecisionRequest,
        x_reviewer_identity: str | None = Header(default=None),
    ) -> SubmitDecisionResponse:
        history = _load_review(dependencies.reviews, request_id)
        _require_identity(x_reviewer_identity, payload.decision.reviewer_identity)
        if not history.decisions and len(history.events) != payload.expected_sequence:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"stale review version: expected {payload.expected_sequence}, "
                    f"current {len(history.events)}"
                ),
            )
        if history.request.graph_thread_id == "":
            raise HTTPException(status_code=409, detail="review has no graph thread")
        with _workflow(dependencies) as workflow:
            try:
                snapshot = workflow.resume(history.request.graph_thread_id, payload.decision)
            except DuplicateReviewDecisionError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            except GraphResumeError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
        record = ReviewerDecisionRecord(
            decision_id=payload.decision.decision_id,
            request_id=request_id,
            kind=payload.decision.kind,
            reviewer_identity=payload.decision.reviewer_identity,
            rationale=payload.decision.rationale,
            proposed_verdict=payload.decision.revised_verdict,
        )
        try:
            dependencies.reviews.record_decision(
                record, expected_sequence=payload.expected_sequence
            )
        except (ReviewConcurrencyError, ReviewPolicyError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return SubmitDecisionResponse(graph=snapshot, review=dependencies.reviews.load(request_id))

    @app.post(
        "/api/reviews/{request_id}/approvals",
        response_model=ReviewAuditTrail,
    )
    def submit_approval(
        request_id: UUID,
        payload: SubmitApprovalRequest,
        x_reviewer_identity: str | None = Header(default=None),
    ) -> ReviewAuditTrail:
        if payload.approval.request_id != request_id:
            raise HTTPException(status_code=422, detail="request ID mismatch")
        _require_identity(x_reviewer_identity, payload.approval.approver_identity)
        try:
            dependencies.reviews.record_approval(
                payload.approval, expected_sequence=payload.expected_sequence
            )
        except (ReviewConcurrencyError, ReviewPolicyError, ReviewLedgerError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return dependencies.reviews.load(request_id)

    @app.post(
        "/api/reviews/{request_id}/revisions",
        response_model=ReviewAuditTrail,
    )
    def submit_revision(
        request_id: UUID,
        payload: SubmitRevisionRequest,
        x_reviewer_identity: str | None = Header(default=None),
    ) -> ReviewAuditTrail:
        if payload.revision.request_id != request_id:
            raise HTTPException(status_code=422, detail="request ID mismatch")
        history = _load_review(dependencies.reviews, request_id)
        approval = next(
            (
                item
                for item in history.approvals
                if item.approval_id == payload.revision.approval_id
            ),
            None,
        )
        if approval is None:
            raise HTTPException(status_code=409, detail="approval not found")
        _require_identity(x_reviewer_identity, approval.approver_identity)
        try:
            dependencies.reviews.record_revision(
                payload.revision, expected_sequence=payload.expected_sequence
            )
        except (ReviewConcurrencyError, ReviewPolicyError, ReviewLedgerError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return dependencies.reviews.load(request_id)

    @app.get("/api/investigations/{investigation_id}/events")
    async def stream_events(
        investigation_id: UUID,
        after: int = Query(default=0, ge=0),
        follow: bool = Query(default=True),
    ) -> StreamingResponse:
        _require_investigation(dependencies.investigations, investigation_id)

        async def generate():
            cursor = after
            while True:
                investigation = _require_investigation(
                    dependencies.investigations, investigation_id
                )
                events = dependencies.investigations.list_events(investigation_id)
                for sequence, event in enumerate(events, 1):
                    if sequence <= cursor:
                        continue
                    data = json.dumps(event.model_dump(mode="json"), separators=(",", ":"))
                    yield f"id: {sequence}\nevent: {event.event_type.value}\ndata: {data}\n\n"
                    cursor = sequence
                terminal = investigation.status in {
                    InvestigationStatus.COMPLETED,
                    InvestigationStatus.FAILED,
                    InvestigationStatus.CANCELLED,
                }
                if not follow or terminal:
                    break
                yield ": keep-alive\n\n"
                await asyncio.sleep(0.25)

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


def _workflow(dependencies: ApiDependencies) -> DurableFixtureLangGraphWorkflow:
    return DurableFixtureLangGraphWorkflow(
        dependencies.graph_checkpoint_path,
        enabled=dependencies.graph_enabled,
        telemetry=dependencies.telemetry,
    )


def _require_investigation(
    repository: InvestigationRepository, investigation_id: UUID
) -> Investigation:
    investigation = repository.get_investigation(investigation_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail="investigation not found")
    return investigation


def _load_review(ledger: SQLiteReviewLedger, request_id: UUID) -> ReviewAuditTrail:
    try:
        return ledger.load(request_id)
    except ReviewLedgerError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


def _require_identity(header: str | None, body_identity: str) -> None:
    """Stage 7.5 authorization placeholder: bind actor header to signed body later."""
    if header is None or header.casefold() != body_identity.casefold():
        raise HTTPException(status_code=403, detail="reviewer identity header mismatch")
