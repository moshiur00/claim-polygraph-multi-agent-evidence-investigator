"""Local reference collector with W3C propagation and privacy-safe storage."""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from pathlib import Path
from statistics import quantiles
from time import perf_counter
from typing import Any

from claim_polygraph_ng.domain.telemetry import (
    AlertRule,
    AlertSeverity,
    MetricAggregate,
    MetricName,
    MetricPoint,
    OperationalAlert,
    SpanKind,
    SpanStatus,
    TelemetrySnapshot,
    TelemetrySpan,
    TraceContext,
)
from claim_polygraph_ng.persistence.sqlite_runtime import connect_sqlite, enable_wal

_TRACEPARENT = re.compile(
    r"^00-(?P<trace>[0-9a-f]{32})-(?P<span>[0-9a-f]{16})-(?P<flags>[0-9a-f]{2})$"
)
_current_context: ContextVar[TraceContext | None] = ContextVar(
    "claim_polygraph_trace_context", default=None
)
_SENSITIVE_KEYS = frozenset(
    {
        "claim",
        "claim_text",
        "content",
        "document",
        "email",
        "input",
        "name",
        "payload",
        "prompt",
        "reviewer_identity",
        "secret",
        "snippet",
        "text",
        "token",
        "url",
    }
)

DEFAULT_ALERT_RULES = (
    AlertRule(
        rule_id="api-p95-latency",
        metric=MetricName.API_LATENCY_MS,
        threshold=2_000,
        comparison="gt",
        minimum_samples=5,
        severity=AlertSeverity.WARNING,
        message="API P95 latency exceeds two seconds.",
    ),
    AlertRule(
        rule_id="queue-depth",
        metric=MetricName.JOB_QUEUE_DEPTH,
        threshold=25,
        comparison="gte",
        severity=AlertSeverity.WARNING,
        message="Durable job queue is approaching its bounded capacity.",
    ),
    AlertRule(
        rule_id="provider-failures",
        metric=MetricName.PROVIDER_FAILURE,
        threshold=1,
        comparison="gte",
        minimum_samples=3,
        severity=AlertSeverity.CRITICAL,
        message="Repeated provider failures require investigation.",
    ),
    AlertRule(
        rule_id="citation-failures",
        metric=MetricName.CITATION_FAILURE,
        threshold=1,
        comparison="gte",
        severity=AlertSeverity.CRITICAL,
        message="A publication-critical citation assurance check failed.",
    ),
    AlertRule(
        rule_id="checkpoint-failures",
        metric=MetricName.CHECKPOINT_FAILURE,
        threshold=1,
        comparison="gte",
        severity=AlertSeverity.CRITICAL,
        message="A durable checkpoint operation failed.",
    ),
)


class TelemetryCollector:
    """Persist spans and metrics without retaining claims, secrets or raw PII."""

    def __init__(self, database_path: str | Path) -> None:
        self._path = str(database_path)

    def initialize(self) -> None:
        with self._connect() as connection:
            enable_wal(connection)
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS telemetry_spans (
                    span_record_id TEXT PRIMARY KEY, trace_id TEXT NOT NULL,
                    span_id TEXT NOT NULL UNIQUE, started_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS telemetry_spans_trace
                    ON telemetry_spans(trace_id, started_at);
                CREATE TABLE IF NOT EXISTS telemetry_metrics (
                    metric_id TEXT PRIMARY KEY, name TEXT NOT NULL,
                    occurred_at TEXT NOT NULL, payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS telemetry_metrics_name
                    ON telemetry_metrics(name, occurred_at);
                """
            )

    @contextmanager
    def span(
        self,
        name: str,
        kind: SpanKind,
        *,
        parent: TraceContext | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> Iterator[TraceContext]:
        inherited = parent or _current_context.get()
        context = TraceContext(
            trace_id=inherited.trace_id if inherited else secrets.token_hex(16),
            span_id=secrets.token_hex(8),
            trace_flags=inherited.trace_flags if inherited else "01",
        )
        parent_span_id = inherited.span_id if inherited else None
        token: Token = _current_context.set(context)
        started_at = datetime.now(UTC)
        started = perf_counter()
        status = SpanStatus.OK
        final_attributes = dict(attributes or {})
        try:
            yield context
        except Exception as error:
            status = SpanStatus.ERROR
            final_attributes["error.type"] = type(error).__name__
            raise
        finally:
            ended_at = datetime.now(UTC)
            _current_context.reset(token)
            self.record_span(
                TelemetrySpan(
                    trace_id=context.trace_id,
                    span_id=context.span_id,
                    parent_span_id=parent_span_id,
                    name=name,
                    kind=kind,
                    status=status,
                    started_at=started_at,
                    ended_at=ended_at,
                    duration_ms=(perf_counter() - started) * 1_000,
                    attributes=redact_attributes(final_attributes),
                )
            )

    def record_span(self, span: TelemetrySpan) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO telemetry_spans VALUES (?, ?, ?, ?, ?)",
                (
                    str(span.span_record_id),
                    span.trace_id,
                    span.span_id,
                    span.started_at.isoformat(),
                    span.model_dump_json(),
                ),
            )

    def metric(
        self,
        name: MetricName,
        value: float,
        unit: str,
        *,
        attributes: Mapping[str, Any] | None = None,
        context: TraceContext | None = None,
    ) -> MetricPoint:
        active = context or _current_context.get()
        point = MetricPoint(
            name=name,
            value=value,
            unit=unit,
            trace_id=active.trace_id if active else None,
            attributes=redact_attributes(attributes or {}),
        )
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO telemetry_metrics VALUES (?, ?, ?, ?)",
                (
                    str(point.metric_id),
                    point.name.value,
                    point.occurred_at.isoformat(),
                    point.model_dump_json(),
                ),
            )
        return point

    def trace(self, trace_id: str) -> tuple[TelemetrySpan, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM telemetry_spans WHERE trace_id = ? ORDER BY started_at",
                (trace_id,),
            ).fetchall()
        return tuple(TelemetrySpan.model_validate_json(row[0]) for row in rows)

    def snapshot(self, rules: tuple[AlertRule, ...] = ()) -> TelemetrySnapshot:
        with self._connect() as connection:
            span_count, trace_count = connection.execute(
                "SELECT COUNT(*), COUNT(DISTINCT trace_id) FROM telemetry_spans"
            ).fetchone()
            rows = connection.execute(
                "SELECT payload FROM telemetry_metrics ORDER BY occurred_at"
            ).fetchall()
        points = tuple(MetricPoint.model_validate_json(row[0]) for row in rows)
        aggregates: list[MetricAggregate] = []
        for name in MetricName:
            values = [point.value for point in points if point.name is name]
            if not values:
                continue
            p95 = (
                quantiles(values, n=20, method="inclusive")[18]
                if len(values) > 1
                else values[0]
            )
            aggregates.append(
                MetricAggregate(
                    name=name,
                    count=len(values),
                    total=sum(values),
                    mean=sum(values) / len(values),
                    p95=p95,
                    maximum=max(values),
                )
            )
        alerts = evaluate_alerts(tuple(aggregates), rules)
        return TelemetrySnapshot(
            spans=span_count,
            traces=trace_count,
            metrics=tuple(aggregates),
            alerts=alerts,
        )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = connect_sqlite(self._path)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def parse_traceparent(value: str | None) -> TraceContext | None:
    if value is None:
        return None
    match = _TRACEPARENT.fullmatch(value.casefold())
    if match is None or set(match.group("trace")) == {"0"} or set(match.group("span")) == {"0"}:
        return None
    return TraceContext(
        trace_id=match.group("trace"),
        span_id=match.group("span"),
        trace_flags=match.group("flags"),
    )


def current_trace_context() -> TraceContext | None:
    return _current_context.get()


def redact_attributes(attributes: Mapping[str, Any]) -> dict[str, Any]:
    """Allow low-cardinality operational metadata; hash sensitive values."""
    redacted: dict[str, Any] = {}
    for raw_key, raw_value in attributes.items():
        key = str(raw_key)[:100]
        lowered = key.casefold()
        if any(part in lowered for part in _SENSITIVE_KEYS):
            digest = hashlib.sha256(str(raw_value).encode()).hexdigest()[:16]
            redacted[f"{key}.sha256"] = digest
            continue
        if isinstance(raw_value, (bool, int, float)) or raw_value is None:
            redacted[key] = raw_value
        elif isinstance(raw_value, str):
            redacted[key] = raw_value[:200]
        else:
            redacted[key] = json.dumps(raw_value, sort_keys=True, default=str)[:200]
    return redacted


def evaluate_alerts(
    aggregates: tuple[MetricAggregate, ...], rules: tuple[AlertRule, ...]
) -> tuple[OperationalAlert, ...]:
    by_name = {aggregate.name: aggregate for aggregate in aggregates}
    alerts: list[OperationalAlert] = []
    for rule in rules:
        aggregate = by_name.get(rule.metric)
        if aggregate is None or aggregate.count < rule.minimum_samples:
            continue
        observed = aggregate.p95
        triggered = (
            observed > rule.threshold
            if rule.comparison == "gt"
            else observed >= rule.threshold
        )
        if triggered:
            alerts.append(
                OperationalAlert(
                    rule_id=rule.rule_id,
                    metric=rule.metric,
                    severity=rule.severity,
                    observed_value=observed,
                    threshold=rule.threshold,
                    message=rule.message,
                )
            )
    return tuple(alerts)
