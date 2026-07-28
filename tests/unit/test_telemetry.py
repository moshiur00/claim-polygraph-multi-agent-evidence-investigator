"""Stage 8.12 trace, metric, privacy and alert contracts."""

import pytest

from claim_polygraph_ng.domain.telemetry import (
    AlertRule,
    AlertSeverity,
    MetricName,
    SpanKind,
)
from claim_polygraph_ng.telemetry import (
    TelemetryCollector,
    parse_traceparent,
    redact_attributes,
)


def test_nested_boundaries_share_one_trace_and_valid_parent_chain(tmp_path) -> None:
    collector = TelemetryCollector(tmp_path / "telemetry.sqlite3")
    collector.initialize()
    with collector.span("api.post", SpanKind.API) as root:
        with (
            collector.span("job.execute", SpanKind.JOB),
            collector.span("langgraph.research", SpanKind.LANGGRAPH),
            collector.span("agent.academic", SpanKind.AGENT),
            collector.span("provider.search", SpanKind.PROVIDER),
        ):
            pass
        with collector.span("review.decision", SpanKind.REVIEW):
            pass

    spans = collector.trace(root.trace_id)
    assert len(spans) == 6
    assert {span.kind for span in spans} == {
        SpanKind.API,
        SpanKind.JOB,
        SpanKind.LANGGRAPH,
        SpanKind.AGENT,
        SpanKind.PROVIDER,
        SpanKind.REVIEW,
    }
    by_id = {span.span_id: span for span in spans}
    assert sum(span.parent_span_id is None for span in spans) == 1
    assert all(
        span.parent_span_id is None or span.parent_span_id in by_id for span in spans
    )


def test_traceparent_round_trip_and_invalid_input() -> None:
    value = "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01"
    assert parse_traceparent(value).traceparent == value
    assert parse_traceparent("malformed") is None
    assert parse_traceparent("00-" + "0" * 32 + "-" + "1" * 16 + "-01") is None


def test_sensitive_attributes_are_hashed_and_raw_values_absent() -> None:
    redacted = redact_attributes(
        {
            "claim_text": "Private medical claim",
            "reviewer_identity": "Person Name",
            "provider.id": "fixture",
        }
    )
    rendered = str(redacted)
    assert "Private medical claim" not in rendered
    assert "Person Name" not in rendered
    assert redacted["provider.id"] == "fixture"
    assert len(redacted["claim_text.sha256"]) == 16


def test_metric_aggregation_and_deterministic_alerts(tmp_path) -> None:
    collector = TelemetryCollector(tmp_path / "telemetry.sqlite3")
    collector.initialize()
    for value in (100, 200, 3_000, 4_000, 5_000):
        collector.metric(MetricName.API_LATENCY_MS, value, "ms")
    rule = AlertRule(
        rule_id="latency",
        metric=MetricName.API_LATENCY_MS,
        threshold=2_000,
        comparison="gt",
        minimum_samples=5,
        severity=AlertSeverity.WARNING,
        message="API latency is elevated.",
    )
    snapshot = collector.snapshot((rule,))
    assert snapshot.metrics[0].count == 5
    assert snapshot.metrics[0].p95 == pytest.approx(4_800)
    assert snapshot.alerts[0].rule_id == "latency"
