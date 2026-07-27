"""Deterministic evidence analysis."""

from claim_polygraph_ng.analysis.aggregation import (
    aggregate_component_label,
    constrain_parent_verdict,
)
from claim_polygraph_ng.analysis.context import verify_claim_context
from claim_polygraph_ng.analysis.independence import analyze_source_independence

__all__ = [
    "aggregate_component_label",
    "analyze_source_independence",
    "constrain_parent_verdict",
    "verify_claim_context",
]
