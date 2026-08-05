"""Readable and machine-readable report generation."""

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from claim_polygraph_ng.analysis import build_argument_ledger, reassess_full_report_assurance
from claim_polygraph_ng.domain import (
    ArgumentLedger,
    ArtifactType,
    AtomicClaim,
    AuthoritativePublicationDecision,
    ClaimCoverage,
    ClaimDecomposition,
    ComplexInvestigationReport,
    ComplexWorkflowCheckpoint,
    ContextVerification,
    DistributionMedium,
    Evidence,
    EvidenceDispositionRecord,
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
    SocialEvidencePolicyResult,
    Source,
    TraceEvent,
    TraceEventType,
    Verdict,
    VerificationPacketV2,
    assess_evidence_packet,
)
from claim_polygraph_ng.domain.evidence_disposition import apply_evidence_dispositions
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
    *,
    require_completed: bool = True,
) -> InvestigationReport:
    """Reconstruct a report; optionally permit a complete provisional packet."""
    investigation = repository.get_investigation(investigation_id)
    if investigation is None:
        raise InvestigationNotFoundError(f"investigation not found: {investigation_id}")
    if require_completed and investigation.status is not InvestigationStatus.COMPLETED:
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
    publication_decisions = repository.list_artifacts(
        investigation_id,
        ArtifactType.PUBLICATION_DECISION,
        AuthoritativePublicationDecision,
    )
    social_evidence_policies = repository.list_artifacts(
        investigation_id,
        ArtifactType.SOCIAL_EVIDENCE_POLICY,
        SocialEvidencePolicyResult,
    )
    evidence_dispositions = repository.list_artifacts(
        investigation_id,
        ArtifactType.EVIDENCE_DISPOSITION,
        EvidenceDispositionRecord,
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

    original_ledger = argument_ledgers[-1] if argument_ledgers else None
    effective_evidence = apply_evidence_dispositions(evidence, evidence_dispositions)
    evidence_integrity = assess_evidence_packet(
        evidence,
        claim_text=claims[0].text,
        decisive_evidence_ids=verdicts[-1].decisive_evidence_ids,
        dispositions=evidence_dispositions,
    )
    current_citation_ids = tuple(
        item.evidence_id for item in evidence_integrity if item.citation_eligible
    )
    effective_assurance = (
        reassess_full_report_assurance(
            historical=full_report_assurance[-1],
            evidence=effective_evidence,
            approved_evidence_ids=current_citation_ids,
        )
        if full_report_assurance
        else None
    )
    effective_ledger = (
        build_argument_ledger(
            claim=claims[0],
            evidence=effective_evidence,
            verification=verification_packets[-1] if verification_packets else None,
            provenance=provenance[-1] if provenance else None,
            propositions=original_ledger.propositions if original_ledger else None,
        )
        if evidence or original_ledger
        else None
    )

    return InvestigationReport(
        investigation=investigation,
        claim=claims[0],
        plan=plans[-1],
        sources=sources,
        evidence=evidence,
        evidence_dispositions=evidence_dispositions,
        evidence_integrity=evidence_integrity,
        independence_analysis=independence[-1] if independence else None,
        provenance=provenance[-1] if provenance else None,
        verification_packet=verification_packets[-1] if verification_packets else None,
        argument_ledger=original_ledger,
        effective_argument_ledger=effective_ledger,
        judgment_policy=judgment_policies[-1] if judgment_policies else None,
        readiness=readiness_artifacts[-1] if readiness_artifacts else None,
        context_verification=(context_verification[-1] if context_verification else None),
        verdict=verdicts[-1],
        audits=audits,
        full_report_assurance=(full_report_assurance[-1] if full_report_assurance else None),
        effective_full_report_assurance=effective_assurance,
        publication_decision=(
            publication_decisions[-1] if publication_decisions else None
        ),
        social_evidence_policy=(
            social_evidence_policies[-1] if social_evidence_policies else None
        ),
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
        component_assurance = (
            component.effective_full_report_assurance
            or component.full_report_assurance
        )
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
    assurance = report.effective_full_report_assurance or report.full_report_assurance
    decision = report.publication_decision
    integrity_blockers = tuple(
        assessment
        for assessment in report.evidence_integrity
        if assessment.publication_blocking
    )
    if integrity_blockers:
        raise PublicationBlockedError(
            "publication blocked: one or more decisive evidence passages are ineligible"
        )
    if decision is not None and not decision.publication_allowed:
        reasons = decision.blocking_reasons or (
            "Authoritative human approval is required before publication.",
        )
        raise PublicationBlockedError("publication blocked: " + " ".join(reasons))
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
    if report.evidence_dispositions:
        lines.extend(
            [
                "## Evidence decision history",
                "",
                "These append-only decisions change effective use without rewriting "
                "the retained evidence.",
                "",
            ]
        )
        for disposition in report.evidence_dispositions:
            approved_use = (
                f" / {disposition.approved_use.value}"
                if disposition.approved_use is not None
                else ""
            )
            lines.append(
                f"- **{disposition.kind.value}{approved_use}** for "
                f"`{disposition.evidence_id}`: {_inline(disposition.reason)} "
                f"_(reviewed by {_inline(disposition.reviewer_identity)}; approved by "
                f"{_inline(disposition.approver_identity)})_"
            )
        lines.append("")

    for heading, stance in (
        ("Supporting evidence", EvidenceStance.SUPPORTS),
        ("Contradictory evidence", EvidenceStance.CONTRADICTS),
        ("Qualifying evidence", EvidenceStance.QUALIFIES),
        ("Context", EvidenceStance.CONTEXT),
    ):
        items = tuple(item for item in report.evidence if item.stance is stance)
        lines.extend(_evidence_section(heading, items, evidence_labels, source_by_id))

    social_items = tuple(
        item
        for item in report.evidence
        if (
            source_by_id.get(item.source_id) is not None
            and source_by_id[item.source_id].distribution_medium
            is DistributionMedium.SOCIAL_PLATFORM
        )
    )
    if social_items:
        lines.extend(
            [
                "## Social-evidence trace",
                "",
                "Authenticity records attribution; it does not establish that a "
                "statement is true. Relevance is not authority or independence.",
                "",
            ]
        )
        for item in social_items:
            source = source_by_id[item.source_id]
            context = source.social_context
            eligibility = source.social_eligibility
            assert context is not None
            assert eligibility is not None
            original = context.original_source
            underlying = (
                source_by_id.get(original.source_id)
                if original is not None and original.source_id is not None
                else None
            )
            family = next(
                (
                    candidate
                    for candidate in (report.provenance.families if report.provenance else ())
                    if source.source_id in candidate.source_ids
                ),
                None,
            )
            account = context.account
            account_label = (
                f"@{account.handle}"
                if account.handle
                else account.display_name or "unresolved account"
            )
            origin_label = (
                underlying.title
                if underlying is not None
                else str(original.url)
                if original is not None and original.url is not None
                else "original social post"
            )
            lines.extend(
                [
                    f"### {evidence_labels[item.evidence_id]} — "
                    f"{_inline(source.title)}",
                    "",
                    f"- **Platform/account:** {_inline(account.platform)} / "
                    f"{_inline(account_label)}",
                    f"- **Identity resolved:** "
                    f"{'yes' if account.identity_resolved else 'no'}",
                    f"- **Account type:** {account.account_type.value}",
                    f"- **Authenticity:** {account.authenticity_status.value}",
                    f"- **Authority scope:** "
                    f"{_inline(account.authority_scope or 'not established')}",
                    f"- **Post/capture:** {context.post_type.value} / "
                    f"{context.capture_method.value}",
                    f"- **Content origin:** {context.content_origin_status.value}",
                    f"- **Original source:** {_inline(origin_label)}",
                    f"- **Original-source status:** "
                    f"{'resolved' if original and original.resolved else 'not resolved'}",
                    f"- **Eligibility:** {eligibility.decision.value}",
                    f"- **Assigned use:** {item.evidentiary_use.value}",
                    f"- **Allowed uses:** "
                    f"{_joined(value.value for value in eligibility.allowed_uses)}",
                    f"- **Corroboration required:** "
                    f"{'yes' if eligibility.requires_corroboration else 'no'}",
                    f"- **Independent proof allowed:** "
                    f"{'yes' if eligibility.independent_proof_allowed else 'no'}",
                    f"- **Evidence family:** "
                    f"{family.family_id if family is not None else 'unassigned'}",
                    f"- **Eligibility reasons:** "
                    f"{_joined(eligibility.reason_codes)}",
                    "",
                ]
            )

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
                f"- **Comparative construction attempts:** "
                f"{len(packet.comparative_constructions)}",
                f"- **Temporal construction attempts:** "
                f"{len(packet.temporal_constructions)}",
                f"- **Version:** {packet.verification_version}",
                "",
            ]
        )
        for construction in packet.comparative_constructions:
            lines.extend(
                [
                    f"### Comparative construction `{construction.construction_id}`",
                    "",
                    f"- **State:** {construction.state.value}",
                    f"- **Claim span:** {construction.claim_text_span}",
                    f"- **Typed comparison:** {construction.left_subject} "
                    f"{construction.comparator.value} {construction.right_subject}",
                    f"- **Property and dimension:** {construction.compared_property}; "
                    f"{construction.dimension.value}",
                    f"- **Evidence bindings:** "
                    f"{_joined(tuple(str(value) for value in construction.evidence_ids))}",
                    f"- **Failure code:** {construction.failure_code or 'none'}",
                    f"- **Explanation:** {construction.explanation}",
                    f"- **Constructor version:** {construction.construction_version}",
                    "",
                ]
            )
        for construction in packet.temporal_constructions:
            lines.extend(
                [
                    f"### Temporal construction `{construction.construction_id}`",
                    "",
                    f"- **State:** {construction.state.value}",
                    f"- **Claim span:** {construction.claim_text_span}",
                    f"- **Typed relation:** {construction.left_subject} "
                    f"{construction.relation.value} {construction.right_subject}",
                    f"- **Evidence bindings:** "
                    f"{_joined(tuple(str(value) for value in construction.evidence_ids))}",
                    f"- **Failure code:** {construction.failure_code or 'none'}",
                    f"- **Explanation:** {construction.explanation}",
                    f"- **Constructor version:** {construction.construction_version}",
                    "",
                ]
            )
        for assertion in packet.numerical_assertions:
            expected = ", ".join(
                f"{value.value} {value.unit or ''}".strip()
                for value in assertion.expected_values
            )
            result = (
                f"{assertion.normalized_result.value} "
                f"{assertion.normalized_result.unit or ''}".strip()
                if assertion.normalized_result is not None
                else "not established"
            )
            lines.extend(
                [
                    f"### Numerical assertion `{assertion.assertion_id}`",
                    "",
                    f"- **State:** {assertion.state.value}",
                    f"- **Comparator:** {assertion.comparator.value}",
                    f"- **Expected/reference value:** {expected}",
                    f"- **Evidence-grounded result:** {result}",
                    f"- **Expression:** {assertion.expression or 'direct comparison'}",
                    "",
                ]
            )

    ledger = report.effective_argument_ledger or report.argument_ledger
    if ledger is not None:
        lines.extend(
            [
                "## Effective argument ledger",
                "",
                f"- **Material propositions:** "
                f"{sum(item.material for item in ledger.propositions)}",
                f"- **Challenger findings:** {len(ledger.challenge_findings)}",
                "",
            ]
        )
        if (
            report.effective_argument_ledger is not None
            and report.argument_ledger is not None
            and report.effective_argument_ledger != report.argument_ledger
        ):
            lines.extend(
                [
                    "The effective ledger was reconstructed from the current evidence "
                    "packet and recorded evidence dispositions. The original persisted "
                    "ledger remains available in the immutable audit record.",
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
    effective_assurance = (
        report.effective_full_report_assurance or report.full_report_assurance
    )
    if effective_assurance is not None:
        assurance = effective_assurance
        lines.extend(
            [
                "",
                "## Effective full-report citation assurance",
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
    if (
        report.effective_full_report_assurance is not None
        and report.full_report_assurance is not None
        and report.effective_full_report_assurance != report.full_report_assurance
    ):
        historical = report.full_report_assurance
        lines.extend(
            [
                "## Historical citation assurance",
                "",
                "> Retained for audit history; this is not the current publication authority.",
                "",
                f"- **Historical status:** {historical.publication_status.value}",
                f"- **Historical full-support rate:** "
                f"{historical.final_audit.full_support_rate:.2%}",
                "",
            ]
        )

    if report.social_evidence_policy is not None:
        social_policy = report.social_evidence_policy
        lines.extend(
            [
                "## Social-evidence constraints",
                "",
                f"- **Social evidence referenced:** "
                f"{len(social_policy.social_evidence_ids)}",
                f"- **Non-social evidence referenced:** "
                f"{len(social_policy.non_social_evidence_ids)}",
                f"- **Human review required:** "
                f"{'yes' if social_policy.requires_human_review else 'no'}",
                f"- **Publication blocked:** "
                f"{'yes' if social_policy.publication_blocked else 'no'}",
                "",
            ]
        )
        for finding in social_policy.findings:
            lines.append(
                f"- **{finding.severity.value} / {finding.code.value}:** "
                f"{finding.reason}"
            )
        lines.append("")
    if report.publication_decision is not None:
        decision = report.publication_decision
        lines.extend(
            [
                "",
                "## Authoritative publication decision",
                "",
                f"- **Status:** {decision.status.value}",
                f"- **Publication allowed:** "
                f"{'yes' if decision.publication_allowed else 'no'}",
                f"- **Proposed label:** {decision.proposed_label.value}",
                f"- **Enforced label:** {decision.enforced_label.value}",
                f"- **Readiness:** {decision.readiness_state.value}",
                f"- **Reason codes:** {', '.join(decision.reason_codes)}",
                "",
            ]
        )
        if decision.blocking_reasons:
            lines.extend(["### Publication blockers", ""])
            lines.extend(_bullet_items(decision.blocking_reasons))

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
