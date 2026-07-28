"""Stage 8.12 frozen operational observability gate."""

from claim_polygraph_ng.domain.telemetry import SpanKind
from claim_polygraph_ng.evaluation.telemetry_gate import run_telemetry_gate


def test_telemetry_gate_covers_every_boundary_and_privacy_rule(tmp_path) -> None:
    result = run_telemetry_gate(tmp_path)
    assert result.passed, result.failed_checks
    assert set(result.boundary_kinds) == set(SpanKind) - {SpanKind.INTERNAL}
    assert result.span_count == result.restart_trace_count == 6
    assert result.sensitive_values_absent
