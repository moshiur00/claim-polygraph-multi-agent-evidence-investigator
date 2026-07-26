"""Readable and machine-readable report generation."""

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from claim_polygraph_ng.domain import (
    ArtifactType,
    AtomicClaim,
    Evidence,
    EvidenceStance,
    InvestigationReport,
    InvestigationStatus,
    SentenceAudit,
    Source,
    TraceEvent,
    TraceEventType,
    Verdict,
)
from claim_polygraph_ng.domain.models import InvestigationPlan
from claim_polygraph_ng.persistence import InvestigationRepository


class InvestigationNotFoundError(LookupError):
    """Raised when an investigation identifier does not exist."""


class IncompleteInvestigationError(LookupError):
    """Raised when a complete report cannot be reconstructed."""


@dataclass(frozen=True)
class ExportedReportPaths:
    """Filesystem paths created for one investigation."""

    directory: Path
    report_json: Path
    report_markdown: Path
    trace_json: Path


def load_report(
    repository: InvestigationRepository,
    investigation_id: UUID,
) -> InvestigationReport:
    """Reconstruct and validate a completed report from stored artifacts."""
    investigation = repository.get_investigation(investigation_id)
    if investigation is None:
        raise InvestigationNotFoundError(f"investigation not found: {investigation_id}")
    if investigation.status is not InvestigationStatus.COMPLETED:
        raise IncompleteInvestigationError(
            f"investigation is {investigation.status.value}, not completed"
        )

    claims = repository.list_artifacts(investigation_id, ArtifactType.CLAIM, AtomicClaim)
    plans = repository.list_artifacts(investigation_id, ArtifactType.PLAN, InvestigationPlan)
    sources = repository.list_artifacts(investigation_id, ArtifactType.SOURCE, Source)
    evidence = repository.list_artifacts(investigation_id, ArtifactType.EVIDENCE, Evidence)
    verdicts = repository.list_artifacts(investigation_id, ArtifactType.VERDICT, Verdict)
    audits = repository.list_artifacts(investigation_id, ArtifactType.AUDIT, SentenceAudit)

    missing = [
        name
        for name, artifacts in (
            ("claim", claims),
            ("plan", plans),
            ("verdict", verdicts),
            ("audit", audits),
        )
        if not artifacts
    ]
    if missing:
        raise IncompleteInvestigationError(
            f"investigation is missing artifacts: {', '.join(missing)}"
        )

    return InvestigationReport(
        investigation=investigation,
        claim=claims[0],
        plan=plans[-1],
        sources=sources,
        evidence=evidence,
        verdict=verdicts[-1],
        audits=audits,
    )


def export_report(
    report: InvestigationReport,
    events: tuple[TraceEvent, ...],
    output_root: str | Path,
) -> ExportedReportPaths:
    """Write JSON, Markdown, and trace artifacts atomically enough for local use."""
    directory = Path(output_root) / str(report.investigation.investigation_id)
    directory.mkdir(parents=True, exist_ok=True)

    report_json = directory / "report.json"
    report_markdown = directory / "report.md"
    trace_json = directory / "trace.json"

    report_json.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    report_markdown.write_text(
        render_markdown(report, events),
        encoding="utf-8",
    )
    trace_json.write_text(
        json.dumps(
            [event.model_dump(mode="json") for event in events],
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    return ExportedReportPaths(
        directory=directory,
        report_json=report_json,
        report_markdown=report_markdown,
        trace_json=trace_json,
    )


def render_markdown(
    report: InvestigationReport,
    events: tuple[TraceEvent, ...],
) -> str:
    """Render a concise investigation report with inspectable evidence."""
    evidence_labels = {
        item.evidence_id: f"E{index}" for index, item in enumerate(report.evidence, start=1)
    }
    source_by_id = {source.source_id: source for source in report.sources}

    lines = [
        "# Claim Polygraph NG Investigation",
        "",
        "> Development notice: this report may use deterministic synthetic providers. "
        "Provider identifiers are shown in the execution summary.",
        "",
        "## Investigation",
        "",
        f"- **ID:** `{report.investigation.investigation_id}`",
        f"- **Status:** {report.investigation.status.value}",
        f"- **Created:** {report.investigation.created_at.isoformat()}",
        f"- **Updated:** {report.investigation.updated_at.isoformat()}",
        "",
        "## Claim",
        "",
        f"**Original:** {_inline(report.investigation.input_claim)}",
        "",
        f"**Normalized:** {_inline(report.claim.text)}",
        "",
        f"- **Type:** {report.claim.claim_type.value}",
        f"- **Checkworthiness:** {report.claim.checkworthiness:.2f}",
        f"- **Ambiguities:** {_joined(report.claim.ambiguities)}",
        "",
        "## Investigation plan",
        "",
        "- **Research paths:** "
        f"{_joined(path.value for path in report.plan.required_research_paths)}",
        f"- **Required source types:** "
        f"{_joined(source.value for source in report.plan.required_source_types)}",
        f"- **Minimum independent families:** {report.plan.minimum_independent_families}",
        f"- **Maximum search calls:** {report.plan.maximum_search_calls}",
        f"- **Maximum pages:** {report.plan.maximum_pages_fetched}",
        "",
    ]

    for heading, stance in (
        ("Supporting evidence", EvidenceStance.SUPPORTS),
        ("Contradictory evidence", EvidenceStance.CONTRADICTS),
        ("Qualifying evidence", EvidenceStance.QUALIFIES),
        ("Context", EvidenceStance.CONTEXT),
    ):
        items = tuple(item for item in report.evidence if item.stance is stance)
        lines.extend(_evidence_section(heading, items, evidence_labels, source_by_id))

    decisive = _evidence_references(report.verdict.decisive_evidence_ids, evidence_labels)
    contradictory = _evidence_references(report.verdict.contradictory_evidence_ids, evidence_labels)
    lines.extend(
        [
            "## Provisional verdict",
            "",
            f"**{report.verdict.label.value.replace('_', ' ').title()}**",
            "",
            _inline(report.verdict.concise_explanation),
            "",
            _inline(report.verdict.detailed_reasoning),
            "",
            f"- **Decisive evidence:** {decisive}",
            f"- **Contradictory evidence:** {contradictory}",
            f"- **Displayed confidence:** {_confidence(report.verdict.confidence)}",
            f"- **Human review required:** "
            f"{'yes' if report.verdict.human_review_required else 'no'}",
            "",
            "### Unresolved questions",
            "",
        ]
    )
    lines.extend(_bullet_items(report.verdict.unresolved_questions))
    lines.extend(
        [
            "",
            "### Conditions that could change the verdict",
            "",
        ]
    )
    lines.extend(_bullet_items(report.verdict.conditions_that_could_change_verdict))

    lines.extend(
        [
            "",
            "## Citation audit",
            "",
            "| Sentence | Support | Evidence | Issue |",
            "|---|---|---|---|",
        ]
    )
    for audit in report.audits:
        lines.append(
            "| "
            + " | ".join(
                (
                    _table(audit.sentence),
                    audit.support_level.value,
                    _evidence_references(audit.cited_evidence_ids, evidence_labels),
                    audit.issue_type.value if audit.issue_type else "none",
                )
            )
            + " |"
        )

    provider_events = tuple(
        event for event in events if event.event_type is TraceEventType.PROVIDER_CALLED
    )
    providers = sorted(
        {
            str(event.details["provider_id"])
            for event in provider_events
            if "provider_id" in event.details
        }
    )
    model_calls = sum("task" in event.details for event in provider_events)
    search_calls = sum("research_path" in event.details for event in provider_events)
    lines.extend(
        [
            "",
            "## Execution summary",
            "",
            f"- **Providers:** {_joined(providers)}",
            f"- **Structured model calls:** {model_calls}",
            f"- **Search calls:** {search_calls}",
            f"- **Trace events:** {len(events)}",
            "",
            "## Sources",
            "",
        ]
    )
    for source in report.sources:
        publisher = f" — {_inline(source.publisher)}" if source.publisher else ""
        lines.append(
            f"- **{_inline(source.title)}**{publisher}: <{source.canonical_url}> "
            f"_(extraction: {source.extraction_status.value})_"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "This is an evidence-assisted provisional assessment. Review the cited "
            "sources and limitations before relying on it.",
            "",
        ]
    )
    return "\n".join(lines)


def _evidence_section(
    heading: str,
    evidence_items: tuple[Evidence, ...],
    labels: dict[UUID, str],
    source_by_id: dict[UUID, Source],
) -> list[str]:
    lines = [f"## {heading}", ""]
    if not evidence_items:
        return [*lines, "_No evidence in this category._", ""]

    for item in evidence_items:
        source = source_by_id[item.source_id]
        label = labels[item.evidence_id]
        lines.extend(
            [
                f"### [{label}] {_inline(source.title)}",
                "",
                f"> {_blockquote(item.passage)}",
                "",
                f"- **Publisher:** {_inline(source.publisher or 'Unknown')}",
                f"- **Source type:** {source.source_type.value}",
                f"- **Relevance:** {item.relevance_score:.2f}",
                f"- **Entailment:** {_confidence(item.entailment_score)}",
                f"- **URL:** <{source.canonical_url}>",
                "",
            ]
        )
    return lines


def _evidence_references(
    identifiers: tuple[UUID, ...],
    labels: dict[UUID, str],
) -> str:
    references = [f"[{labels[value]}]" for value in identifiers if value in labels]
    return ", ".join(references) if references else "none"


def _bullet_items(items: tuple[str, ...]) -> list[str]:
    return [f"- {_inline(item)}" for item in items] or ["- None recorded."]


def _joined(values) -> str:
    prepared = [str(value) for value in values]
    return ", ".join(prepared) if prepared else "none"


def _confidence(value: float | None) -> str:
    return "not calibrated" if value is None else f"{value:.2f}"


def _inline(value: object) -> str:
    return str(value).replace("\r", " ").replace("\n", " ").strip()


def _table(value: object) -> str:
    return _inline(value).replace("|", "\\|")


def _blockquote(value: object) -> str:
    return _inline(value).replace(">", "\\>")
