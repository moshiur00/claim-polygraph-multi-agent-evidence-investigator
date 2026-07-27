"""Deterministic parent-label constraints for material component verdicts."""

from collections.abc import Sequence

from claim_polygraph_ng.domain import Verdict, VerdictLabel

_POSITIVE = {VerdictLabel.SUPPORTED, VerdictLabel.MOSTLY_SUPPORTED}
_UNRESOLVED = {VerdictLabel.UNSUPPORTED, VerdictLabel.UNVERIFIABLE}


def aggregate_component_label(component_verdicts: Sequence[Verdict]) -> VerdictLabel:
    """Return a conservative parent label from material component verdicts."""
    if not component_verdicts:
        raise ValueError("at least one component verdict is required")
    labels = {verdict.label for verdict in component_verdicts}
    if labels == {VerdictLabel.SUPPORTED}:
        return VerdictLabel.SUPPORTED
    if labels <= _POSITIVE:
        return VerdictLabel.MOSTLY_SUPPORTED
    if VerdictLabel.MISLEADING in labels:
        if len(component_verdicts) >= 3 and VerdictLabel.CONTRADICTED in labels:
            return VerdictLabel.MIXED
        return VerdictLabel.MISLEADING
    if VerdictLabel.CONTRADICTED in labels and labels & _POSITIVE:
        return VerdictLabel.MIXED
    if labels == {VerdictLabel.CONTRADICTED}:
        return VerdictLabel.CONTRADICTED
    if labels <= _UNRESOLVED:
        return (
            VerdictLabel.UNVERIFIABLE
            if VerdictLabel.UNVERIFIABLE in labels
            else VerdictLabel.UNSUPPORTED
        )
    if VerdictLabel.OUTDATED in labels and labels <= {
        VerdictLabel.OUTDATED,
        VerdictLabel.SUPPORTED,
    }:
        return VerdictLabel.OUTDATED
    return VerdictLabel.MIXED


def constrain_parent_verdict(
    proposed: Verdict,
    component_verdicts: Sequence[Verdict],
) -> Verdict:
    """Replace an inconsistent parent label and retain an explicit review signal."""
    required_label = aggregate_component_label(component_verdicts)
    if proposed.label is required_label:
        return proposed
    reason = (
        f"Parent label constrained from {proposed.label.value} to "
        f"{required_label.value} by material component verdicts."
    )
    if proposed.review_reason:
        reason = f"{proposed.review_reason} {reason}"
    return Verdict.model_validate(
        {
            **proposed.model_dump(),
            "label": required_label,
            "human_review_required": True,
            "review_reason": reason,
        }
    )
