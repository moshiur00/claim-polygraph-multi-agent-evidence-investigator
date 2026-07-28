"""Deterministic Stage 8.12 trace, privacy, metric and alert gate."""

from pathlib import Path

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.telemetry import MetricName, SpanKind
from claim_polygraph_ng.telemetry import DEFAULT_ALERT_RULES, TelemetryCollector


class TelemetryGateResult(DomainModel):
    trace_id: str
    boundary_kinds: tuple[SpanKind, ...]
    span_count: int
    parent_chain_valid: bool
    restart_trace_count: int
    sensitive_values_absent: bool
    metric_names: tuple[MetricName, ...]
    alert_rule_ids: tuple[str, ...]
    passed: bool
    failed_checks: tuple[str, ...] = ()


def run_telemetry_gate(directory: str | Path) -> TelemetryGateResult:
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    database = root / "telemetry.sqlite3"
    collector = TelemetryCollector(database)
    collector.initialize()
    with collector.span(
        "api.investigation",
        SpanKind.API,
        attributes={"claim_text": "Sensitive benchmark claim"},
    ) as root_context:
        with (
            collector.span("job.execute", SpanKind.JOB),
            collector.span("langgraph.research", SpanKind.LANGGRAPH),
            collector.span(
                "agent.academic",
                SpanKind.AGENT,
                attributes={"agent.role": "academic"},
            ),
            collector.span(
                "provider.search",
                SpanKind.PROVIDER,
                attributes={"provider.id": "fixture", "prompt": "private prompt"},
            ),
        ):
            collector.metric(MetricName.PROVIDER_LATENCY_MS, 120, "ms")
        with collector.span(
            "review.decision",
            SpanKind.REVIEW,
            attributes={"reviewer_identity": "Private Reviewer"},
        ):
            collector.metric(MetricName.REVIEW_BACKLOG, 3, "reviews")

    collector.metric(MetricName.JOB_QUEUE_DEPTH, 28, "jobs")
    for _ in range(3):
        collector.metric(MetricName.PROVIDER_FAILURE, 1, "failure")
    collector.metric(MetricName.CITATION_FAILURE, 1, "failure")

    spans = collector.trace(root_context.trace_id)
    by_id = {span.span_id: span for span in spans}
    parent_chain_valid = all(
        span.parent_span_id is None or span.parent_span_id in by_id for span in spans
    )
    serialized = " ".join(span.model_dump_json() for span in spans)
    sensitive_absent = all(
        value not in serialized
        for value in ("Sensitive benchmark claim", "private prompt", "Private Reviewer")
    )
    restarted = TelemetryCollector(database)
    restarted.initialize()
    restart_trace_count = len(restarted.trace(root_context.trace_id))
    snapshot = restarted.snapshot(DEFAULT_ALERT_RULES)
    kinds = tuple(span.kind for span in spans)
    expected_kinds = {
        SpanKind.API,
        SpanKind.JOB,
        SpanKind.LANGGRAPH,
        SpanKind.AGENT,
        SpanKind.PROVIDER,
        SpanKind.REVIEW,
    }
    failed: list[str] = []
    checks = {
        "cross-boundary trace is incomplete": set(kinds) == expected_kinds,
        "parent span chain is invalid": parent_chain_valid,
        "restart lost spans": restart_trace_count == len(spans),
        "sensitive telemetry was retained": sensitive_absent,
        "metric aggregation is empty": bool(snapshot.metrics),
        "expected alerts did not trigger": {
            alert.rule_id for alert in snapshot.alerts
        }
        == {"queue-depth", "provider-failures", "citation-failures"},
    }
    failed.extend(message for message, passed in checks.items() if not passed)
    return TelemetryGateResult(
        trace_id=root_context.trace_id,
        boundary_kinds=kinds,
        span_count=len(spans),
        parent_chain_valid=parent_chain_valid,
        restart_trace_count=restart_trace_count,
        sensitive_values_absent=sensitive_absent,
        metric_names=tuple(metric.name for metric in snapshot.metrics),
        alert_rule_ids=tuple(alert.rule_id for alert in snapshot.alerts),
        passed=not failed,
        failed_checks=tuple(failed),
    )
