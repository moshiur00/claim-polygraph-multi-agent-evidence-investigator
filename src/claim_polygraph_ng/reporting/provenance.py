"""Standalone machine-readable and Markdown provenance inspection reports."""

import json
from pathlib import Path

from pydantic import AnyHttpUrl, Field

from claim_polygraph_ng.analysis.evidence_families import (
    EvidenceFamilyInference,
    FamilySourceRecord,
    infer_evidence_families,
)
from claim_polygraph_ng.analysis.independence_features import (
    IndependenceFeatures,
    calculate_independence_features,
)
from claim_polygraph_ng.analysis.source_quality import SourceQualityAssessment
from claim_polygraph_ng.domain.base import DomainModel

PROVENANCE_REPORT_VERSION = "provenance-report-v1"


class ProvenanceSourceSummary(DomainModel):
    """Source metadata displayed without reproducing full documents."""

    source_id: str
    title: str
    publisher: str | None
    canonical_url: AnyHttpUrl


class SourceQualityReportEntry(DomainModel):
    """Links an assessment to the report's source identifier."""

    source_id: str
    assessment: SourceQualityAssessment


class ComponentProvenanceReport(DomainModel):
    """Inspection packet for one material claim component."""

    component_id: str
    component_claim: str
    sources: tuple[ProvenanceSourceSummary, ...]
    family_inference: EvidenceFamilyInference
    independence: IndependenceFeatures
    quality_assessments: tuple[SourceQualityReportEntry, ...] = ()


class ProvenanceInspectionReport(DomainModel):
    """Portable provenance report that can later embed in investigation output."""

    report_version: str = PROVENANCE_REPORT_VERSION
    dataset_id: str
    dataset_version: int = Field(ge=1)
    components: tuple[ComponentProvenanceReport, ...]
    limitations: tuple[str, ...]


class ExportedProvenancePaths(DomainModel):
    """Paths created by a provenance report export."""

    report_json: Path
    report_markdown: Path


def build_component_provenance_report(
    *,
    component_id: str,
    component_claim: str,
    source_records: tuple[FamilySourceRecord, ...],
    source_summaries: tuple[ProvenanceSourceSummary, ...],
    required_independent_families: int,
    quality_assessments: tuple[SourceQualityReportEntry, ...] = (),
) -> ComponentProvenanceReport:
    if {item.source_id for item in source_records} != {item.source_id for item in source_summaries}:
        raise ValueError("source records and summaries must contain the same source IDs")
    inference = infer_evidence_families(component_id, source_records)
    independence = calculate_independence_features(
        inference,
        raw_source_count=len(source_records),
        required_independent_families=required_independent_families,
    )
    return ComponentProvenanceReport(
        component_id=component_id,
        component_claim=component_claim,
        sources=tuple(sorted(source_summaries, key=lambda item: item.source_id)),
        family_inference=inference,
        independence=independence,
        quality_assessments=quality_assessments,
    )


def render_provenance_markdown(report: ProvenanceInspectionReport) -> str:
    """Render all relationships and uncertainty without hiding unknowns."""
    lines = [
        "# Claim Polygraph NG Provenance Inspection",
        "",
        f"- **Dataset:** {_inline(report.dataset_id)} v{report.dataset_version}",
        f"- **Report version:** `{report.report_version}`",
        "",
    ]
    for component in report.components:
        features = component.independence
        lines.extend(
            (
                f"## {_inline(component.component_id)}",
                "",
                f"**Claim:** {_inline(component.component_claim)}",
                "",
                "### Independence summary",
                "",
                f"- Raw sources: {features.raw_source_count}",
                f"- Grouped families: {features.grouped_family_count}",
                (
                    "- Confirmed/possible independent families: "
                    f"[{features.confirmed_independent_lower_bound}, "
                    f"{features.possible_independent_upper_bound}]"
                ),
                f"- Unresolved dependency pairs: {features.unresolved_dependency_count}",
                f"- Requirement: **{features.requirement_state.value}**",
                "",
                "### Evidence families",
                "",
            )
        )
        for family in component.family_inference.families:
            reasons = ", ".join(family.grouping_reasons) or "no dependency merge"
            lines.append(
                f"- `{family.family_id}`: {', '.join(family.source_ids)} — {_inline(reasons)}"
            )
        lines.extend(("", "### Dependency edges", ""))
        for edge in component.family_inference.dependency_edges:
            lines.append(
                f"- {edge.left_source_id} ↔ {edge.right_source_id}: "
                f"**{edge.status.value}** ({edge.confidence:.2f}) — "
                f"{_inline(', '.join(edge.reasons))}"
            )
        lines.extend(("", "### Sources", ""))
        for source in component.sources:
            publisher = f" — {_inline(source.publisher)}" if source.publisher else ""
            lines.append(
                f"- **{_inline(source.title)}** (`{source.source_id}`){publisher}: "
                f"<{source.canonical_url}>"
            )
        if component.quality_assessments:
            lines.extend(("", "### Source-quality dimensions", ""))
            for entry in component.quality_assessments:
                lines.append(f"- Source `{entry.source_id}`")
                for dimension in entry.assessment.dimensions:
                    lines.append(
                        f"  - {dimension.dimension.value}: **{dimension.finding.value}** "
                        f"— {_inline(dimension.reason)}"
                    )
        lines.append("")
    lines.extend(("## Limitations", ""))
    lines.extend(f"- {_inline(item)}" for item in report.limitations)
    return "\n".join(lines).rstrip() + "\n"


def export_provenance_report(
    report: ProvenanceInspectionReport, output_directory: str | Path
) -> ExportedProvenancePaths:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "provenance-report.json"
    markdown_path = output / "provenance-report.md"
    json_path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_provenance_markdown(report), encoding="utf-8")
    return ExportedProvenancePaths(
        report_json=json_path,
        report_markdown=markdown_path,
    )


def _inline(value: str) -> str:
    return " ".join(value.replace("`", "'").replace("\n", " ").split())
