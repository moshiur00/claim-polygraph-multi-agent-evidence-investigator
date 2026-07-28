"""Readable and machine-readable report generation."""

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from claim_polygraph_ng.domain import (
    ArgumentLedger,
    ArtifactType,
    AtomicClaim,
    ClaimCoverage,
    ClaimDecomposition,
    ComplexInvestigationReport,
    ComplexWorkflowCheckpoint,
    ContextVerification,
    Evidence,
    EvidenceStance,
    FullReportCitationAssurance,
    IndependenceAnalysis,
    InvestigationProvenance,
    InvestigationReport,
    InvestigationStatus,
    JudgmentPolicyTrace,
    JudgmentReadiness,
    MultiAgentInvestigationReport,
    PublicationGateStatus,
    ReportAssertionSection,
    SentenceAudit,
    Source,
    TraceEvent,
    TraceEventType,
    Verdict,
    VerificationPacketV2,
)
from claim_polygraph_ng.domain.models import InvestigationPlan
from claim_polygraph_ng.persistence import InvestigationRepository


class InvestigationNotFoundError(LookupError):
    """Raised when an investigation identifier does not exist."""


class IncompleteInvestigationError(LookupError):
    """Raised when a complete report cannot be reconstructed."""


class PublicationBlockedError(RuntimeError):
    """Raised when critical or excessive material citation failures remain."""


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
    independence = repository.list_artifacts(
        investigation_id,
        ArtifactType.INDEPENDENCE,
        IndependenceAnalysis,
    )
    provenance = repository.list_artifacts(
        investigation_id,
        ArtifactType.PROVENANCE,
        InvestigationProvenance,
    )
    verification_packets = repository.list_artifacts(
        investigation_id, ArtifactType.VERIFICATION_PACKET, VerificationPacketV2
    )
    argument_ledgers = repository.list_artifacts(
        investigation_id, ArtifactType.ARGUMENT_LEDGER, ArgumentLedger
    )
    judgment_policies = repository.list_artifacts(
        investigation_id, ArtifactType.JUDGMENT_POLICY, JudgmentPolicyTrace
    )
    readiness_artifacts = repository.list_artifacts(
        investigation_id, ArtifactType.READINESS, JudgmentReadiness
    )
    context_verification = repository.list_artifacts(
        investigation_id,
        ArtifactType.CONTEXT_VERIFICATION,
        ContextVerification,
    )
    verdicts = repository.list_artifacts(investigation_id, ArtifactType.VERDICT, Verdict)
    audits = repository.list_artifacts(investigation_id, ArtifactType.AUDIT, SentenceAudit)
    full_report_assurance = repository.list_artifacts(
        investigation_id,
        ArtifactType.FULL_REPORT_ASSURANCE,
        FullReportCitationAssurance,
    )

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
        independence_analysis=independence[-1] if independence else None,
        provenance=provenance[-1] if provenance else None,
        verification_packet=verification_packets[-1] if verification_packets else None,
        argument_ledger=argument_ledgers[-1] if argument_ledgers else None,
        judgment_policy=judgment_policies[-1] if judgment_policies else None,
        readiness=readiness_artifacts[-1] if readiness_artifacts else None,
        context_verification=(context_verification[-1] if context_verification else None),
        verdict=verdicts[-1],
        audits=audits,
        full_report_assurance=(full_report_assurance[-1] if full_report_assurance else None),
    )


def load_complex_report(
    repository: InvestigationRepository,
    investigation_id: UUID,
) -> ComplexInvestigationReport:
    """Reconstruct a completed parent report and its linked child reports."""
    investigation = repository.get_investigation(investigation_id)
    if investigation is None:
        raise InvestigationNotFoundError(f"investigation not found: {investigation_id}")
    if investigation.status is not InvestigationStatus.COMPLETED:
        raise IncompleteInvestigationError(
            f"investigation is {investigation.status.value}, not completed"
        )
    decompositions = repository.list_artifacts(
        investigation_id,
        ArtifactType.DECOMPOSITION,
        ClaimDecomposition,
    )
    checkpoints = repository.list_artifacts(
        investigation_id,
        ArtifactType.CHECKPOINT,
        ComplexWorkflowCheckpoint,
    )
    coverages = repository.list_artifacts(
        investigation_id,
        ArtifactType.COVERAGE,
        ClaimCoverage,
    )
    verdicts = repository.list_artifacts(investigation_id, ArtifactType.VERDICT, Verdict)
    audits = repository.list_artifacts(investigation_id, ArtifactType.AUDIT, SentenceAudit)
    assurance = repository.list_artifacts(
        investigation_id,
        ArtifactType.FULL_REPORT_ASSURANCE,
        FullReportCitationAssurance,
    )
    if not all((decompositions, checkpoints, coverages, verdicts, audits)):
        raise IncompleteInvestigationError(
            "completed complex investigation is missing required parent artifacts"
        )
    component_reports = tuple(
        load_report(repository, item.investigation_id)
        for item in checkpoints[-1].completed_components
    )
    return ComplexInvestigationReport(
        investigation=investigation,
        decomposition=decompositions[-1],
        component_reports=component_reports,
        coverage=coverages[-1],
        verdict=verdicts[-1],
        audits=audits,
        full_report_assurance=assurance[-1] if assurance else None,
    )


def export_report(
    report: InvestigationReport,
    events: tuple[TraceEvent, ...],
    output_root: str | Path,
) -> ExportedReportPaths:
    """Write JSON, Markdown, and trace artifacts atomically enough for local use."""
    publishable_markdown = render_publishable_markdown(report, events)
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
        publishable_markdown,
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


def export_complex_report(
    report: ComplexInvestigationReport,
    events: tuple[TraceEvent, ...],
    output_root: str | Path,
) -> ExportedReportPaths:
    """Write a complex parent report and trace without flattening components."""
    publishable_markdown = render_publishable_complex_markdown(report)
    directory = Path(output_root) / str(report.investigation.investigation_id)
    directory.mkdir(parents=True, exist_ok=True)
    report_json = directory / "report.json"
    report_markdown = directory / "report.md"
    trace_json = directory / "trace.json"
    report_json.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    report_markdown.write_text(publishable_markdown, encoding="utf-8")
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


def render_publishable_complex_markdown(report: ComplexInvestigationReport) -> str:
    """Require parent and every completed component to pass publication."""
    assurance = report.full_report_assurance
    if assurance is None or assurance.publication_status is PublicationGateStatus.BLOCKED:
        reasons = (
            assurance.blocking_reasons
            if assurance
            else ("parent full-report citation assurance is missing",)
        )
        raise PublicationBlockedError("complex publication blocked: " + " ".join(reasons))
    for component in report.component_reports:
        component_assurance = component.full_report_assurance
        if (
            component_assurance is None
            or component_assurance.publication_status is PublicationGateStatus.BLOCKED
        ):
            raise PublicationBlockedError(
                f"complex publication blocked by component {component.claim.claim_id}"
            )
    return render_complex_markdown(report)


def render_complex_markdown(report: ComplexInvestigationReport) -> str:
    """Render parent context, every component, coverage, verdict, and audit."""
    lines = [
        "# Claim Polygraph NG Complex Investigation",
        "",
        f"- **ID:** `{report.investigation.investigation_id}`",
        f"- **Status:** {report.investigation.status.value}",
        f"- **Original claim:** {_inline(report.investigation.input_claim)}",
        f"- **Decomposed:** {'yes' if report.decomposition.requires_decomposition else 'no'}",
        f"- **Material coverage:** {report.coverage.material_coverage_rate:.0%}",
        "",
        "## Material components",
        "",
    ]
    for index, component_report in enumerate(report.component_reports, start=1):
        lines.extend(
            [
                f"### C{index}: {_inline(component_report.claim.text)}",
                "",
                f"- **Verdict:** {component_report.verdict.label.value}",
                f"- **Evidence passages:** {len(component_report.evidence)}",
                f"- **Retained context:** {_joined(component_report.claim.retained_context)}",
                f"- **Child investigation:** `{component_report.investigation.investigation_id}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Parent verdict",
            "",
            f"**{report.verdict.label.value.replace('_', ' ').title()}**",
            "",
            _inline(report.verdict.concise_explanation),
            "",
            _inline(report.verdict.detailed_reasoning),
            "",
            "## Parent citation audit",
            "",
        ]
    )
    for audit in report.audits:
        lines.append(f"- **{audit.support_level.value}:** {_inline(audit.sentence)}")
    lines.append("")
    return "\n".join(lines)


def render_multi_agent_markdown(report: MultiAgentInvestigationReport) -> str:
    """Render role activation, shared evidence, sufficiency, and stopping state."""
    lines = [
        "# Claim Polygraph NG Multi-Agent Investigation",
        "",
        f"- **ID:** `{report.investigation_id}`",
        f"- **Claim:** {_inline(report.claim.text)}",
        f"- **Roles activated:** {_joined(item.role.value for item in report.assignments)}",
        f"- **Role results:** {len(report.results)}",
        f"- **Consolidated sources:** {len(report.consolidation.sources)}",
        f"- **Consolidated evidence:** {len(report.consolidation.evidence)}",
        f"- **Independent families:** {report.consolidation.independence.independent_family_count}",
        f"- **Sources removed as duplicates:** {report.consolidation.removed_source_count}",
        f"- **Evidence removed as duplicates:** {report.consolidation.removed_evidence_count}",
        f"- **Stopping decision:** {report.assessment.decision.value}",
        f"- **Verdict:** {report.verdict.label.value}",
        f"- **Citation support:** {report.audit.support_level.value}",
        "",
        "## Role trace",
        "",
    ]
    for result in report.results:
        lines.append(
            f"- **{result.role.value}:** searches {result.search_call_count}; "
            f"fetches {result.fetch_call_count}; evidence {len(result.evidence_ids)}; "
            f"cost ${result.estimated_cost_usd:.6f}; "
            f"status {'failed: ' + result.failure_reason if result.failure_reason else 'completed'}"
        )
    lines.extend(
        [
            "",
            "## Sufficiency",
            "",
            _inline(report.assessment.rationale),
            "",
            "## Grounding",
            "",
            f"- **Stored verdict evidence IDs:** {_joined(report.verdict.decisive_evidence_ids)}",
            f"- **Audited evidence IDs:** {_joined(report.audit.cited_evidence_ids)}",
            "",
        ]
    )
    return "\n".join(lines)


def render_publishable_markdown(
    report: InvestigationReport,
    events: tuple[TraceEvent, ...],
) -> str:
    """Render only after the complete material-sentence publication gate passes."""
    assurance = report.full_report_assurance
    if assurance is None:
        raise PublicationBlockedError(
            "full-report citation assurance is missing; publication is blocked"
        )
    if assurance.publication_status is PublicationGateStatus.BLOCKED:
        raise PublicationBlockedError(
            "publication blocked: " + " ".join(assurance.blocking_reasons)
        )
    return render_markdown(report, events)


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

    if report.independence_analysis is not None:
        analysis = report.independence_analysis
        lines.extend(
            [
                "## Evidence independence",
                "",
                f"- **Independent families:** {analysis.independent_family_count}",
                f"- **Required families:** {analysis.required_independent_families}",
                f"- **Requirement met:** {'yes' if analysis.requirement_met else 'no'}",
            ]
        )
        for index, family in enumerate(analysis.families, start=1):
            lines.append(
                f"- **Family {index}:** hosts {_joined(family.hostnames)}; "
                f"basis {_joined(family.grouping_reasons)}"
            )
        lines.append("")

    if report.provenance is not None:
        provenance = report.provenance
        lines.extend(
            [
                "## Provenance inspection",
                "",
                f"- **Confirmed independent lower bound:** "
                f"{provenance.confirmed_independent_lower_bound}",
                f"- **Possible independent upper bound:** "
                f"{provenance.possible_independent_upper_bound}",
                f"- **Required families:** {provenance.required_independent_families}",
                f"- **Requirement state:** {provenance.requirement_state.value}",
                f"- **Unresolved source relationships:** {provenance.unresolved_dependency_count}",
                f"- **Inferred families:** {len(provenance.families)}",
                "",
            ]
        )
        for family in provenance.families:
            reasons = _joined(family.grouping_reasons) if family.grouping_reasons else "none"
            lines.append(
                f"- **{family.family_id}:** {len(family.source_ids)} source(s); "
                f"grouping signals: {reasons}"
            )
        lines.extend(
            [
                "",
                "These bounds preserve unresolved dependency instead of treating it as "
                "confirmed independence. Source-quality observations are available in "
                "the JSON report and are not an aggregate trust score.",
                "",
            ]
        )

    if report.context_verification is not None:
        verification = report.context_verification
        lines.extend(
            [
                "## Context verification",
                "",
                f"- **Numerical check:** {verification.numerical.status.value}",
                f"- **Claim values:** {_joined(verification.numerical.claim_values)}",
                f"- **Numerical issues:** {_joined(verification.numerical.issues)}",
                f"- **Temporal check:** {verification.temporal.status.value}",
                f"- **Reference date:** {verification.temporal.reference_date or 'not specified'}",
                f"- **Temporal issues:** {_joined(verification.temporal.issues)}",
                "",
            ]
        )

    if report.verification_packet is not None:
        packet = report.verification_packet
        lines.extend(
            [
                "## Assertion-level verification",
                "",
                f"- **Numerical assertions:** {len(packet.numerical_assertions)}",
                f"- **Temporal assertions:** {len(packet.temporal_assertions)}",
                f"- **Version:** {packet.verification_version}",
                "",
            ]
        )

    if report.argument_ledger is not None:
        ledger = report.argument_ledger
        lines.extend(
            [
                "## Argument ledger",
                "",
                f"- **Material propositions:** "
                f"{sum(item.material for item in ledger.propositions)}",
                f"- **Challenger findings:** {len(ledger.challenge_findings)}",
                "",
            ]
        )
        for argument in ledger.arguments:
            lines.append(
                f"- **Proposition `{argument.proposition_id}`:** {argument.resolution.value}"
            )
        lines.append("")

    if report.judgment_policy is not None:
        policy = report.judgment_policy
        lines.extend(
            [
                "## Judgment policy",
                "",
                f"- **Proposed label:** {policy.proposed_label.value}",
                f"- **Policy candidate label:** {policy.enforced_label.value}",
                f"- **Changed:** {'yes' if policy.changed else 'no'}",
                f"- **Applied to verdict:** {'yes' if policy.applied else 'no'}",
                f"- **Reason codes:** {_joined(item.value for item in policy.reason_codes)}",
                "",
            ]
        )

    if report.readiness is not None:
        readiness = report.readiness
        lines.extend(
            [
                "## Judgment readiness",
                "",
                f"- **State:** {readiness.state.value}",
                f"- **Material coverage:** {readiness.material_coverage:.2%}",
                f"- **Verification completeness:** {readiness.verification_completeness:.2%}",
                f"- **Citation audit complete:** "
                f"{'yes' if readiness.citation_audit_complete else 'no'}",
                f"- **Reason codes:** {_joined(item.value for item in readiness.reason_codes)}",
                "",
            ]
        )

    decisive = _evidence_references(report.verdict.decisive_evidence_ids, evidence_labels)
    contradictory = _evidence_references(report.verdict.contradictory_evidence_ids, evidence_labels)
    summary = report.verdict.concise_explanation
    detailed = report.verdict.detailed_reasoning
    if report.full_report_assurance is not None:
        final_assertions = report.full_report_assurance.final_assertions
        summary = " ".join(
            _assured_sentence(item, evidence_labels)
            for item in final_assertions
            if item.section is ReportAssertionSection.VERDICT_SUMMARY
        )
        detailed = " ".join(
            _assured_sentence(item, evidence_labels)
            for item in final_assertions
            if item.section is ReportAssertionSection.DETAILED_REASONING
        )
    lines.extend(
        [
            "## Provisional verdict",
            "",
            f"**{report.verdict.label.value.replace('_', ' ').title()}**",
            "",
            _inline(summary),
            "",
            _inline(detailed),
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
    if report.full_report_assurance is not None:
        assurance = report.full_report_assurance
        lines.extend(
            [
                "",
                "## Full-report citation assurance",
                "",
                f"- **Publication status:** {assurance.publication_status.value}",
                f"- **Material sentences audited:** "
                f"{assurance.audited_material_sentence_count}/"
                f"{assurance.material_sentence_count}",
                f"- **Final full-support rate:** {assurance.final_audit.full_support_rate:.2%}",
                f"- **Critical failures:** {assurance.critical_failure_count}",
                f"- **Bounded revisions:** {len(assurance.revisions)}",
                "",
            ]
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
    usage_events = tuple(
        event for event in events if event.event_type is TraceEventType.MODEL_USAGE_RECORDED
    )
    input_tokens = int(_detail_total(usage_events, "input_tokens"))
    cached_input_tokens = int(_detail_total(usage_events, "cached_input_tokens"))
    output_tokens = int(_detail_total(usage_events, "output_tokens"))
    estimated_cost = _detail_total(usage_events, "estimated_cost_usd")
    model_latency = _detail_total(usage_events, "duration_seconds")
    unpriced_calls = sum(event.details.get("estimated_cost_usd") is None for event in usage_events)
    lines.extend(
        [
            "",
            "## Execution summary",
            "",
            f"- **Providers:** {_joined(providers)}",
            f"- **Structured model calls:** {model_calls}",
            f"- **Search calls:** {search_calls}",
            f"- **Metered input tokens:** {input_tokens}",
            f"- **Cached input tokens:** {cached_input_tokens}",
            f"- **Metered output tokens:** {output_tokens}",
            f"- **Estimated model cost:** ${estimated_cost:.6f}",
            f"- **Measured model latency:** {model_latency:.3f} seconds",
            f"- **Unpriced model calls:** {unpriced_calls}",
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
            f"_(extraction: {source.extraction_status.value}; "
            f"rights: {source.rights_status.value}; "
            f"retention: {source.content_retention.value})_"
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
                f"- **Rights status:** {source.rights_status.value}",
                f"- **Retention:** {source.content_retention.value}",
                f"- **Relevance:** {item.relevance_score:.2f}",
                f"- **Retrieval score:** {_confidence(item.retrieval_score)}",
                f"- **Entailment:** {_confidence(item.entailment_score)}",
                f"- **Source characters:** {_source_range(item)}",
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


def _assured_sentence(assertion, labels: dict[UUID, str]) -> str:
    references = _evidence_references(assertion.cited_evidence_ids, labels)
    return (
        f"{assertion.sentence} [Citations: {references}]"
        if references != "none"
        else assertion.sentence
    )


def _bullet_items(items: tuple[str, ...]) -> list[str]:
    return [f"- {_inline(item)}" for item in items] or ["- None recorded."]


def _joined(values) -> str:
    prepared = [str(value) for value in values]
    return ", ".join(prepared) if prepared else "none"


def _confidence(value: float | None) -> str:
    return "not calibrated" if value is None else f"{value:.2f}"


def _source_range(evidence: Evidence) -> str:
    if evidence.passage_start_char is None or evidence.passage_end_char is None:
        return "not recorded"
    return f"{evidence.passage_start_char}-{evidence.passage_end_char}"


def _inline(value: object) -> str:
    return str(value).replace("\r", " ").replace("\n", " ").strip()


def _table(value: object) -> str:
    return _inline(value).replace("|", "\\|")


def _blockquote(value: object) -> str:
    return _inline(value).replace(">", "\\>")


def _detail_total(events: tuple[TraceEvent, ...], key: str) -> float:
    values = (event.details.get(key) for event in events)
    return sum(
        float(value)
        for value in values
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    )
