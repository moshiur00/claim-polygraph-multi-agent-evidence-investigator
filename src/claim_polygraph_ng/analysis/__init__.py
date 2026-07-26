"""Deterministic evidence analysis."""

from claim_polygraph_ng.analysis.context import verify_claim_context
from claim_polygraph_ng.analysis.independence import analyze_source_independence

__all__ = ["analyze_source_independence", "verify_claim_context"]
