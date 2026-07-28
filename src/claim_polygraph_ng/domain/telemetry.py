"""Privacy-safe OpenTelemetry-compatible operational contracts."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, JsonValue, model_validator

from claim_polygraph_ng.domain.base import DomainModel


def telemetry_utc_now() -> datetime:
    return datetime.now(UTC)


class SpanKind(StrEnum):
    API = "api"
    JOB = "job"
    LANGGRAPH = "langgraph"
    AGENT = "agent"
    PROVIDER = "provider"
    REVIEW = "review"
    INTERNAL = "internal"


class SpanStatus(StrEnum):
    OK = "ok"
    ERROR = "error"
    CANCELLED = "cancelled"


class MetricName(StrEnum):
    API_LATENCY_MS = "api.latency_ms"
    JOB_QUEUE_DEPTH = "job.queue_depth"
    JOB_WAIT_MS = "job.wait_ms"
    JOB_FAILURE = "job.failure"
    PROVIDER_LATENCY_MS = "provider.latency_ms"
    PROVIDER_FAILURE = "provider.failure"
    MODEL_TOKENS = "model.tokens"
    MODEL_COST_USD = "model.cost_usd"
    EVIDENCE_YIELD = "evidence.yield"
    CITATION_FAILURE = "citation.failure"
    REVIEW_BACKLOG = "review.backlog"
    LANGGRAPH_NODE_LATENCY_MS = "langgraph.node_latency_ms"
    BUDGET_EXHAUSTION = "budget.exhaustion"
    CHECKPOINT_FAILURE = "checkpoint.failure"


class TraceContext(DomainModel):
    trace_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    span_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    trace_flags: str = Field(default="01", pattern=r"^[0-9a-f]{2}$")

    @property
    def traceparent(self) -> str:
        return f"00-{self.trace_id}-{self.span_id}-{self.trace_flags}"


class TelemetrySpan(DomainModel):
    span_record_id: UUID = Field(default_factory=uuid4)
    trace_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    span_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    parent_span_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{16}$")
    name: str = Field(min_length=2, max_length=200)
    kind: SpanKind
    status: SpanStatus
    started_at: datetime
    ended_at: datetime
    duration_ms: float = Field(ge=0)
    attributes: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_interval(self) -> "TelemetrySpan":
        if self.ended_at < self.started_at:
            raise ValueError("span end cannot precede start")
        return self


class MetricPoint(DomainModel):
    metric_id: UUID = Field(default_factory=uuid4)
    name: MetricName
    value: float
    unit: str = Field(min_length=1, max_length=30)
    occurred_at: datetime = Field(default_factory=telemetry_utc_now)
    trace_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    attributes: dict[str, JsonValue] = Field(default_factory=dict)


class MetricAggregate(DomainModel):
    name: MetricName
    count: int = Field(ge=0)
    total: float
    mean: float
    p95: float
    maximum: float


class AlertSeverity(StrEnum):
    WARNING = "warning"
    CRITICAL = "critical"


class AlertRule(DomainModel):
    rule_id: str = Field(min_length=3, max_length=100)
    metric: MetricName
    threshold: float
    comparison: str = Field(pattern=r"^(gt|gte)$")
    minimum_samples: int = Field(default=1, ge=1)
    severity: AlertSeverity
    message: str = Field(min_length=3, max_length=500)


class OperationalAlert(DomainModel):
    alert_id: UUID = Field(default_factory=uuid4)
    rule_id: str
    metric: MetricName
    severity: AlertSeverity
    observed_value: float
    threshold: float
    message: str
    triggered_at: datetime = Field(default_factory=telemetry_utc_now)


class TelemetrySnapshot(DomainModel):
    generated_at: datetime = Field(default_factory=telemetry_utc_now)
    spans: int = Field(ge=0)
    traces: int = Field(ge=0)
    metrics: tuple[MetricAggregate, ...]
    alerts: tuple[OperationalAlert, ...]
