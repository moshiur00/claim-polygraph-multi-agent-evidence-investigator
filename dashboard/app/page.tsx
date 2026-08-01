"use client";
/* eslint-disable react-hooks/set-state-in-effect */

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

type Investigation = { investigation_id: string; input_claim: string; status: string; stage: string };
type Evidence = {
  evidence_id: string; source_id: string; passage: string; stance: string;
  relevance_score: number; evidence_family_id: string | null; evidentiary_use: string;
};
type SocialEligibility = {
  decision: string; allowed_uses: string[]; decisive_use_allowed: boolean;
  independent_proof_allowed: boolean; requires_corroboration: boolean;
  requires_human_review: boolean; reason_codes: string[];
};
type SocialContext = {
  account: {
    platform: string; handle: string | null; display_name: string | null;
    profile_url: string | null; account_type: string; identity_resolved: boolean;
    authority_scope: string | null; authenticity_status: string;
    authenticity_basis: string | null;
    authenticity_evidence: Array<{
      evidence_type: string; reference_url: string | null; observed_at: string;
      description: string;
    }>;
  };
  post_type: string; platform_post_id: string | null; posted_at: string | null;
  original_source: {
    relationship: string; source_id: string | null; url: string | null; resolved: boolean;
  } | null;
  capture_method: string; content_origin_status: string; attribution_scope: string;
  attributed_text: string | null; eyewitness_claim: boolean; unavailable_or_deleted: boolean;
  archive_reference: {
    archive_url: string; archive_provider: string; reliability_verified: boolean;
    verification_basis: string | null;
  } | null;
};
type Source = {
  source_id: string; title: string; publisher: string | null; source_type: string;
  url: string; canonical_url: string; distribution_medium: string;
  social_context: SocialContext | null; social_eligibility: SocialEligibility | null;
};
type StructuredReportAssertion = {
  assertion_id: string; claim_id: string; sentence: string; cited_evidence_ids: string[];
  asserted_stance: string; required_phrases: string[]; material: boolean; critical: boolean;
  section: string; ordinal: number;
};
type CitationEvidenceLink = {
  evidence_id: string; passage: string; stance: string; matched_phrases: string[];
};
type CitationFinding = {
  assertion_id: string; sentence: string; material: boolean; critical: boolean;
  status: string; links: CitationEvidenceLink[]; missing_phrases: string[];
  issue_codes: string[]; explanation: string;
};
type CitationAssurancePacket = {
  claim_id: string; approved_evidence_ids: string[]; findings: CitationFinding[];
  supported_count: number; partial_count: number; unsupported_count: number;
  contradictory_count: number; out_of_packet_count: number; full_support_rate: number;
};
type CitationRevision = {
  assertion_id: string; attempt_number: number; original_sentence: string;
  revised_sentence: string; cited_evidence_ids: string[]; rationale: string;
  verdict_label_changed: boolean;
};
type FullReportAssurance = {
  publication_status: string; material_sentence_count: number;
  audited_material_sentence_count: number; critical_failure_count: number;
  original_assertions: StructuredReportAssertion[]; final_assertions: StructuredReportAssertion[];
  initial_audit: CitationAssurancePacket; final_audit: CitationAssurancePacket;
  revisions: CitationRevision[]; blocking_reasons: string[]; maximum_revision_attempts: number;
};
type VerificationFinding = {
  code: string; severity: string; message: string; recommended_action: string;
  readiness_impact: string; evidence_ids: string[];
};
type ContextValueObservation = {
  raw_text: string; normalized_text: string; origin: string;
  evidence_id: string | null; source_id: string | null;
  start_char: number | null; end_char: number | null; unit_hint: string | null;
};
type NormalizedNumericValue = {
  value: string | number; unit: string | null; dimension: string;
  scale: string | number; tolerance: string | number | null;
};
type TemporalInstant = { value: string; precision: string };
type TemporalInterval = {
  start: TemporalInstant | null; end: TemporalInstant | null;
  start_inclusive: boolean; end_inclusive: boolean;
};
type VerificationPacket = {
  claim_id: string; verification_version: string; approved_evidence_ids: string[];
  numerical_assertions: Array<{
    assertion_id: string; claim_id: string; claim_text_span: string; comparator: string;
    operation: string; expected_values: NormalizedNumericValue[]; evidence_ids: string[];
    state: string; normalized_result: NormalizedNumericValue | null; expression: string | null;
    rounding_rule: string | null; issues: string[]; limitations: string[];
    findings: VerificationFinding[];
  }>;
  temporal_assertions: Array<{
    assertion_id: string; claim_id: string; claim_text_span: string; relation: string;
    reference_date: TemporalInstant | null; claimed_interval: TemporalInterval | null;
    requires_reference_date: boolean;
    observations: Array<{
      evidence_id: string; publication_date: TemporalInstant | null;
      effective_interval: TemporalInterval | null; observed_status: string | null;
      retrospective: boolean;
    }>;
    state: string; issues: string[]; limitations: string[]; findings: VerificationFinding[];
  }>;
  comparative_constructions: Array<{
    construction_id: string; claim_id: string; claim_text_span: string;
    left_subject: string; right_subject: string; compared_property: string;
    comparator: string; dimension: string; state: string; assertion_id: string | null;
    evidence_ids: string[]; failure_code: string | null; explanation: string;
    construction_version: string;
  }>;
  temporal_constructions: Array<{
    construction_id: string; claim_id: string; claim_text_span: string;
    left_subject: string; right_subject: string; relation: string;
    state: string; assertion_id: string | null; evidence_ids: string[];
    failure_code: string | null; explanation: string; construction_version: string;
  }>;
  limitations: string[]; findings: VerificationFinding[];
};
type Report = {
  investigation: Investigation;
  claim: {
    claim_id: string; text: string; claim_type: string; checkworthiness: number;
    entities: string[]; quantities: string[]; reference_date: string | null;
    geography: string | null; ambiguities: string[]; retained_context: string[];
  };
  plan: {
    required_research_paths: string[]; required_source_types: string[];
    minimum_independent_families: number; maximum_search_calls: number;
    maximum_pages_fetched: number; requires_numerical_check: boolean;
    requires_temporal_check: boolean;
  };
  sources: Source[];
  evidence: Evidence[];
  verdict: {
    verdict_id: string; label: string; confidence: number | null;
    concise_explanation: string; detailed_reasoning: string;
    decisive_evidence_ids: string[]; contradictory_evidence_ids: string[];
    unresolved_questions: string[]; conditions_that_could_change_verdict: string[];
    human_review_required: boolean; review_reason: string | null;
  };
  audits: Array<{
    sentence_id: string; sentence: string; support_level: string; cited_evidence_ids: string[];
    issue_type: string | null; explanation: string | null; suggested_revision: string | null;
  }>;
  independence_analysis: { independent_family_count: number; required_independent_families: number; limitations: string[] } | null;
  provenance: {
    confirmed_independent_lower_bound: number; possible_independent_upper_bound: number;
    unresolved_dependency_count: number; requirement_state: string; limitations: string[];
    families: Array<{ family_id: string; source_ids: string[]; grouping_reasons: string[] }>;
    source_quality: Array<{
      source_id: string;
      dimensions: Array<{ dimension: string; finding: string; reason: string; signals: string[] }>;
      limitations: string[]; ignored_signals: string[];
    }>;
    social_risk_findings: Array<{
      code: string; severity: string; reason: string; source_id: string | null;
      evidence_ids: string[];
    }>;
  } | null;
  readiness: {
    state: string; material_coverage: number; verification_completeness: number;
    citation_audit_complete: boolean; reason_codes: string[]; limitations: string[];
    source_quality_unknown_count: number; blocking_challenge_count: number;
    nonblocking_challenge_count: number; unresolved_question_count: number;
    confirmed_independent_lower_bound: number; possible_independent_upper_bound: number;
    social_risk_finding_count: number; blocking_social_risk_count: number;
    social_policy_finding_count: number; blocking_social_policy_finding_count: number;
  } | null;
  context_verification: {
    numerical: {
      required: boolean; status: string; claim_values: string[]; evidence_values: string[];
      claim_units: string[]; evidence_units: string[]; exactness_terms: string[]; issues: string[];
      claim_observations: ContextValueObservation[]; evidence_observations: ContextValueObservation[];
      findings: VerificationFinding[];
    };
    temporal: {
      required: boolean; status: string; reference_date: string | null;
      source_publication_dates: string[]; issues: string[]; findings: VerificationFinding[];
    };
    limitations: string[];
  } | null;
  verification_packet: VerificationPacket | null;
  argument_ledger: {
    propositions: Array<{ proposition_id: string; text: string; material: boolean }>;
    arguments: Array<{ proposition_id: string; resolution: string; supporting_evidence_ids: string[]; contradictory_evidence_ids: string[]; qualifying_evidence_ids: string[]; unresolved_reasons: string[] }>;
    challenge_findings: Array<{ finding_id: string; kind: string; severity: string; rationale: string; evidence_ids: string[] }>;
    limitations: string[];
  } | null;
  judgment_policy: {
    proposed_label: string; enforced_label: string; allowed_labels: string[];
    changed: boolean; applied: boolean; human_review_required: boolean;
    reason_codes: string[]; rationale: string;
  } | null;
  full_report_assurance: FullReportAssurance | null;
  social_evidence_policy: {
    policy_version: string;
    findings: Array<{
      finding_id: string; code: string; severity: string; reason: string;
      proposition_id: string | null; source_id: string | null; evidence_ids: string[];
    }>;
    social_evidence_ids: string[]; non_social_evidence_ids: string[];
    requires_human_review: boolean; publication_blocked: boolean;
    blocking_reasons: string[];
  } | null;
  publication_decision: {
    status: string; publication_allowed: boolean; human_review_required: boolean;
    reason_codes: string[]; blocking_reasons: string[];
  } | null;
};
type GraphSnapshot = {
  thread_id: string; status: string; authoritative_verdict: string;
  final_verdict: string | null; completed_nodes: string[];
  applied_decision_id: string | null; reviewer_identity: string | null;
};
type ReviewRequest = {
  request_id: string; investigation_id: string; graph_thread_id: string;
  reason: string; created_at: string;
};
type ReviewHistory = {
  request: ReviewRequest;
  findings: Array<{ finding_id: string; summary: string; kind: string }>;
  decisions: Array<{
    decision_id: string; kind: string; reviewer_identity: string; rationale: string;
    proposed_verdict: string | null; created_at: string;
    verification_construction_id?: string | null;
    verification_disposition?: string | null;
    corrected_claim_text_span?: string | null; corrected_value?: string | null;
    corrected_unit?: string | null; corrected_evidence_ids?: string[];
  }>;
  approvals: Array<{ approval_id: string; approver_identity: string; decision: string }>;
  revisions: Array<{ revision_id: string; revised_verdict: string }>;
  events: Array<{ sequence: number; action: string; actor_identity: string }>;
  chain_valid: boolean;
};
type ApiStatus = {
  status: string;
  api_version: string;
  orchestrator: "langgraph" | "direct" | "multi_agent_experimental";
  authoritative_service: string;
  retrieval_provider?: string;
  live_research?: boolean;
  model_provider?: string;
};
type TelemetrySnapshot = {
  spans: number;
  traces: number;
  metrics: Array<{ name: string; count: number; total: number; unit?: string }>;
};
type ClaimCandidate = {
  candidate_id: string;
  text: string;
  checkworthiness: number;
  rank: number;
  context_before: string;
  context_after: string;
};
type ClaimExtractionPacket = {
  input_kind: string;
  candidates: ClaimCandidate[];
  automatic_investigation_started: boolean;
};
type InvestigationJob = {
  job: {
    job_id: string; status: string; attempts: number;
    last_error: string | null; result_reference: string | null;
  };
  investigation_id: string | null;
  events: Array<{ sequence: number; action: string; detail: string; occurred_at: string }>;
};
type AuthoritativeJob = InvestigationJob & {
  thread_id: string;
  graph: {
    phase: string; checkpoint_sequence: number; completed_operations: string[];
    components: Array<{ component_id: string; claim_summary: string }>;
    requirements: Array<{ requirement_id: string; kind: string; rationale_summary: string }>;
    assignments: Array<{ assignment_id: string; role: string; round_number: number; requirement_ids: string[] }>;
    research_results: Array<{
      result_id: string; assignment_id: string; source_ids: string[]; evidence_ids: string[];
      unresolved_requirement_ids: string[]; failure_summary: string | null;
    }>;
    artifacts: Array<{ artifact_type: string; artifact_id: string; schema_version: number }>;
    evidence_families: unknown[]; approved_evidence_ids: string[];
    verification_construction_ids: string[];
    verification_construction_states: Record<string, string>;
    unresolved_questions: Array<{ question_id: string; requirement_ids: string[]; question_summary: string }>;
    budget: {
      maximum_rounds: number; maximum_concurrent_roles: number; maximum_search_calls: number;
      maximum_pages_per_component: number; maximum_model_calls: number;
      maximum_duration_seconds: number; maximum_cost_usd: number;
    };
    publication_blocked: boolean; publication_blocking_reasons: string[];
    consumption: {
      completed_rounds: number; role_activations: number; search_calls: number; fetched_pages: number;
      model_calls: number; total_tokens: number; duration_seconds: number; estimated_cost_usd: number;
    };
  } | null;
  interruption: {
    question: string; claim_text: string; route_reason: string; allowed_decisions: string[];
    provisional_verdict: string; approved_evidence_ids: string[];
  } | null;
  review: ReviewHistory | null;
  publication_status: string;
  verdict: string | null;
  report_available: boolean;
};

const graphOrder = ["created", "claim_analysis", "planning", "research", "verification", "arguments", "judgment", "citation_assurance", "readiness", "review", "finalization", "complete"] as const;
const graphLabels: Record<string, string> = {
  created: "Create", claim_analysis: "Analyze", planning: "Plan",
  research: "Multi-agent research", verification: "Verify",
  arguments: "Defender / challenger", judgment: "Judgment",
  citation_assurance: "Citation assurance", readiness: "Readiness",
  review: "Human review", finalization: "Publish", complete: "Complete",
};
const defaultApi = "http://127.0.0.1:8000";
const titleCase = (value: string) => value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
const shortId = (value: string) => value.slice(0, 8).toUpperCase();
const canonicalStance = (value: string) => ({
  supports: "supporting", supporting: "supporting",
  contradicts: "contradictory", contradictory: "contradictory",
  qualifies: "qualifying", qualifying: "qualifying",
  context: "context",
}[value] ?? value);

const canonicalVerdictLabel = (report: Report, graph: GraphSnapshot | null) =>
  graph?.final_verdict ?? report.judgment_policy?.enforced_label ?? report.verdict.label;

const canonicalCitationSummary = (report: Report) => {
  if (report.full_report_assurance) {
    const audit = report.full_report_assurance.final_audit;
    return {
      rate: Math.round(audit.full_support_rate * 100),
      supported: audit.supported_count,
      total: audit.findings.length,
      status: report.full_report_assurance.publication_status,
      authority: "Full-report citation assurance",
    };
  }
  const supported = report.audits.filter((audit) => audit.support_level === "full").length;
  return {
    rate: report.audits.length ? Math.round(supported / report.audits.length * 100) : 0,
    supported,
    total: report.audits.length,
    status: "legacy_fallback",
    authority: "Legacy sentence-audit fallback",
  };
};

const canonicalVerificationSummary = (report: Report) => {
  const packet = report.verification_packet;
  const numerical = packet?.numerical_assertions ?? [];
  const temporal = packet?.temporal_assertions ?? [];
  const assertions = [...numerical, ...temporal];
  const requiredNumerical = report.context_verification?.numerical.required
    ?? report.plan.requires_numerical_check;
  const requiredTemporal = report.context_verification?.temporal.required
    ?? report.plan.requires_temporal_check;
  const missingRequired =
    (requiredNumerical && numerical.length === 0 ? 1 : 0)
    + (requiredTemporal && temporal.length === 0 ? 1 : 0);
  const unresolved = assertions.filter((assertion) =>
    ["insufficient", "error"].includes(assertion.state)).length + missingRequired;
  const completed = assertions.filter((assertion) =>
    ["verified", "contradicted", "qualified", "not_applicable"].includes(assertion.state)).length;
  const required = requiredNumerical || requiredTemporal;
  const completeness = assertions.length
    ? Math.round(completed / assertions.length * 100)
    : required ? 0 : 100;
  const findings = [
    ...(packet?.findings ?? []),
    ...numerical.flatMap((assertion) => assertion.findings ?? []),
    ...temporal.flatMap((assertion) => assertion.findings ?? []),
  ];
  return {
    completeness,
    unresolved,
    requiredNumerical,
    requiredTemporal,
    findings,
    authority: packet ? "Assertion-level verification packet" : "Legacy compatibility fallback",
  };
};

const auditFilterOptions = [
  ["all", "All assertions"],
  ["problems", "Problems only"],
  ["critical", "Critical only"],
  ["supported", "Supported"],
  ["partial", "Partial"],
  ["unsupported", "Unsupported"],
  ["revised", "Revised"],
] as const;

function CitationAuditView({
  report,
  sources,
  evidence,
  openEvidence,
}: {
  report: Report;
  sources: Map<string, Source>;
  evidence: Evidence[];
  openEvidence: (evidenceId: string) => void;
}) {
  const [filter, setFilter] = useState<(typeof auditFilterOptions)[number][0]>("all");
  const assurance = report.full_report_assurance;
  const fallbackFindings: CitationFinding[] = report.audits.map((audit) => ({
    assertion_id: audit.sentence_id,
    sentence: audit.sentence,
    material: true,
    critical: false,
    status: audit.support_level === "full" ? "supported" : audit.support_level === "none" ? "unsupported" : audit.support_level,
    links: audit.cited_evidence_ids.map((id) => {
      const record = evidence.find((item) => item.evidence_id === id);
      return {
        evidence_id: id,
        passage: record?.passage ?? "The cited evidence record is not available in this report.",
        stance: record?.stance ?? "unknown",
        matched_phrases: [],
      };
    }),
    missing_phrases: [],
    issue_codes: audit.issue_type ? [audit.issue_type] : [],
    explanation: audit.explanation ?? (
      audit.support_level === "full"
        ? "The cited evidence supports this material sentence."
        : "The legacy audit did not provide a detailed explanation."
    ),
  }));
  const findings = assurance?.final_audit.findings ?? fallbackFindings;
  const initialByAssertion = new Map(
    assurance?.initial_audit.findings.map((finding) => [finding.assertion_id, finding]) ?? [],
  );
  const assertionById = new Map(
    assurance?.final_assertions.map((assertion) => [assertion.assertion_id, assertion]) ?? [],
  );
  const revisionsByAssertion = new Map<string, CitationRevision[]>();
  for (const revision of assurance?.revisions ?? []) {
    revisionsByAssertion.set(
      revision.assertion_id,
      [...(revisionsByAssertion.get(revision.assertion_id) ?? []), revision],
    );
  }
  const visibleFindings = findings.filter((finding) => {
    if (filter === "all") return true;
    if (filter === "problems") return finding.status !== "supported";
    if (filter === "critical") return finding.critical;
    if (filter === "revised") return revisionsByAssertion.has(finding.assertion_id);
    return finding.status === filter;
  });
  const supportedCount = assurance?.final_audit.supported_count
    ?? findings.filter((finding) => finding.status === "supported").length;
  const partialCount = assurance?.final_audit.partial_count
    ?? findings.filter((finding) => finding.status === "partial").length;
  const unsupportedCount = (assurance?.final_audit.unsupported_count ?? 0)
    + (assurance?.final_audit.contradictory_count ?? 0)
    + (assurance?.final_audit.out_of_packet_count ?? 0)
    || findings.filter((finding) => !["supported", "partial"].includes(finding.status)).length;
  const supportRate = Math.round(
    (assurance?.final_audit.full_support_rate
      ?? (findings.length ? supportedCount / findings.length : 0)) * 100,
  );
  const publicationStatus = assurance?.publication_status ?? (
    findings.every((finding) => finding.status === "supported") ? "ready" : "blocked"
  );

  return <div className="citation-audit-dashboard">
    <section className={`citation-gate ${publicationStatus === "ready" ? "ready" : "blocked"}`}>
      <div>
        <span>FULL-REPORT CITATION ASSURANCE</span>
        <h2>{publicationStatus === "ready" ? "Citation gate passed" : "Publication blocked by citation assurance"}</h2>
        <p>{publicationStatus === "ready"
          ? "Every critical assertion passed and the material-sentence support rate meets the publication threshold."
          : assurance?.blocking_reasons[0] ?? "One or more material assertions still lack complete support."}</p>
      </div>
      <dl>
        <div><dt>Full support</dt><dd>{supportRate}%</dd></div>
        <div><dt>Material coverage</dt><dd>{assurance ? `${assurance.audited_material_sentence_count}/${assurance.material_sentence_count}` : `${findings.length}/${findings.length}`}</dd></div>
        <div><dt>Critical failures</dt><dd>{assurance?.critical_failure_count ?? findings.filter((finding) => finding.critical && finding.status !== "supported").length}</dd></div>
        <div><dt>Revision attempts</dt><dd>{assurance?.revisions.length ?? report.audits.filter((audit) => audit.suggested_revision).length}</dd></div>
      </dl>
    </section>

    <section className="citation-metrics" aria-label="Citation audit status summary">
      <article><span>SUPPORTED</span><strong>{supportedCount}</strong><small>Complete approved-passage match</small></article>
      <article><span>PARTIAL</span><strong>{partialCount}</strong><small>Only part of the assertion is supported</small></article>
      <article><span>OTHER FAILURES</span><strong>{unsupportedCount}</strong><small>Unsupported, contradictory, or outside packet</small></article>
      <article><span>PUBLICATION THRESHOLD</span><strong>95%</strong><small>With zero critical failures</small></article>
    </section>

    {(assurance?.blocking_reasons.length ?? 0) > 0 && <section className="citation-blockers">
      <span>WHY PUBLICATION IS BLOCKED</span>
      {assurance?.blocking_reasons.map((reason, index) => <p key={reason}><b>{index + 1}</b>{reason}</p>)}
    </section>}

    <section className="citation-controls" aria-label="Filter citation findings">
      <div><span>ASSERTION INVENTORY</span><b>{visibleFindings.length} of {findings.length} shown</b></div>
      <div>{auditFilterOptions.map(([value, label]) => <button
        className={filter === value ? "active" : ""}
        key={value}
        onClick={() => setFilter(value)}
      >{label}</button>)}</div>
    </section>

    <div className="citation-findings">
      {visibleFindings.map((finding) => {
        const assertion = assertionById.get(finding.assertion_id);
        const initial = initialByAssertion.get(finding.assertion_id);
        const revisions = revisionsByAssertion.get(finding.assertion_id) ?? [];
        const lastRevision = revisions.at(-1);
        const assertionNumber = findings.findIndex((item) => item.assertion_id === finding.assertion_id) + 1;
        const citationIds = assertion?.cited_evidence_ids.length
          ? assertion.cited_evidence_ids
          : finding.links.map((link) => link.evidence_id);
        const linkByEvidence = new Map(finding.links.map((link) => [link.evidence_id, link]));
        return <article className={`citation-finding audit-${finding.status}`} key={finding.assertion_id}>
          <header>
            <div>
              <b>Sentence {assertionNumber}</b>
              <span>{titleCase(assertion?.section ?? "report assertion")}</span>
              {(assertion?.critical ?? finding.critical) && <em className="critical">Critical</em>}
              {(assertion?.material ?? finding.material) && <em>Material</em>}
            </div>
            <div>
              {initial && initial.status !== finding.status && <small>{titleCase(initial.status)} →</small>}
              <strong className={`audit-status-${finding.status}`}>{titleCase(finding.status)}</strong>
            </div>
          </header>

          <blockquote>{finding.sentence}</blockquote>

          <div className="citation-diagnosis">
            <section>
              <span>WHY THIS STATUS</span>
              <p>{finding.explanation}</p>
            </section>
            <dl>
              <div><dt>Expected stance</dt><dd>{titleCase(canonicalStance(assertion?.asserted_stance ?? "not recorded"))}</dd></div>
              <div><dt>Approved citations</dt><dd>{citationIds.length}</dd></div>
              <div><dt>Audit phase</dt><dd>{initial ? "Final re-audit" : "Legacy sentence audit"}</dd></div>
            </dl>
          </div>

          {finding.issue_codes.length > 0 && <div className="audit-issues">
            <span>ISSUES</span>
            {finding.issue_codes.map((issue) => <b key={issue}>{titleCase(issue)}</b>)}
          </div>}

          {(finding.missing_phrases.length > 0 || (assertion?.required_phrases.length ?? 0) > 0) && <div className="phrase-audit">
            <section><span>REQUIRED SUPPORT</span>{assertion?.required_phrases.map((phrase) => <mark key={phrase}>{phrase}</mark>)}</section>
            <section><span>STILL MISSING</span>{finding.missing_phrases.length
              ? finding.missing_phrases.map((phrase) => <mark className="missing" key={phrase}>{phrase}</mark>)
              : <b>None</b>}</section>
          </div>}

          <div className="citation-mappings">
            <div className="citation-subhead"><span>CITATION-TO-PASSAGE MAPPING</span><b>{citationIds.length} reference{citationIds.length === 1 ? "" : "s"}</b></div>
            {citationIds.map((evidenceId) => {
              const record = evidence.find((item) => item.evidence_id === evidenceId);
              const source = record ? sources.get(record.source_id) : null;
              const link = linkByEvidence.get(evidenceId);
              return <details key={evidenceId}>
                <summary>
                  <span>{shortId(evidenceId)}</span>
                  <b>{source?.publisher ?? source?.title ?? "Evidence record unavailable"}</b>
                  <em>{titleCase(canonicalStance(link?.stance ?? record?.stance ?? "unknown"))}</em>
                </summary>
                <div>
                  {link?.matched_phrases.length ? <section className="matched-phrases"><span>MATCHED PHRASES</span>{link.matched_phrases.map((phrase) => <mark key={phrase}>{phrase}</mark>)}</section> : <p className="no-match">No required phrase match was recorded for this citation.</p>}
                  <blockquote>“{link?.passage ?? record?.passage ?? "The cited passage is not available in this report."}”</blockquote>
                  <dl>
                    <div><dt>Source type</dt><dd>{titleCase(source?.source_type ?? "unknown")}</dd></div>
                    <div><dt>Evidence family</dt><dd>{record?.evidence_family_id ? shortId(record.evidence_family_id) : "Unassigned"}</dd></div>
                    <div><dt>Approved use</dt><dd>{titleCase(record?.evidentiary_use ?? "not recorded")}</dd></div>
                    <div><dt>Packet status</dt><dd>{assurance?.final_audit.approved_evidence_ids.includes(evidenceId) === false ? "Outside approved packet" : "Approved"}</dd></div>
                  </dl>
                  <div className="citation-actions">
                    {record && <button onClick={() => openEvidence(evidenceId)}>Open full evidence record →</button>}
                    {source?.url && <a href={source.url} target="_blank" rel="noreferrer">Open original source ↗</a>}
                  </div>
                </div>
              </details>;
            })}
            {!citationIds.length && <p className="citation-empty">No evidence citation is attached to this assertion.</p>}
          </div>

          {lastRevision && <details className="revision-comparison">
            <summary>Bounded revision · attempt {lastRevision.attempt_number}</summary>
            <div>
              <section><span>ORIGINAL</span><p>{lastRevision.original_sentence}</p></section>
              <section><span>REVISED AND RE-AUDITED</span><p>{lastRevision.revised_sentence}</p></section>
              <footer><b>Rationale</b><p>{lastRevision.rationale}</p><small>Verdict label changed: {lastRevision.verdict_label_changed ? "Yes" : "No"}</small></footer>
            </div>
          </details>}
        </article>;
      })}
      {!visibleFindings.length && <p className="citation-empty">No assertions match this filter.</p>}
    </div>

    <details className="citation-method">
      <summary>How to interpret citation assurance</summary>
      <div>
        <section><b>What it checks</b><p>Material report assertions must link to approved passages with the required wording and expected evidence stance. Critical failures and support below 95% block publication.</p></section>
        <section><b>What it does not prove</b><p>A citation match does not establish that a source is correct, authoritative, independent, or contextually complete. Those safeguards are evaluated in Evidence, Verification, Provenance, and Social evidence.</p></section>
        <section><b>Revision boundary</b><p>Bounded revision may narrow unsupported wording to an approved passage. It cannot add assertions, introduce unapproved evidence, or change the verdict label.</p></section>
      </div>
    </details>
  </div>;
}

const verificationFilterOptions = [
  ["all", "All assertions"],
  ["problems", "Problems only"],
  ["numerical", "Numerical"],
  ["temporal", "Temporal"],
  ["verified", "Verified"],
] as const;

const formatNumericValue = (value: NormalizedNumericValue) => {
  const scaled = String(value.scale) === "1" ? "" : ` × ${value.scale}`;
  const tolerance = value.tolerance == null ? "" : ` ± ${value.tolerance}`;
  return `${value.value}${scaled}${value.unit ? ` ${value.unit}` : ""}${tolerance}`;
};

const formatInstant = (value: TemporalInstant | null) => (
  value ? `${value.value} (${titleCase(value.precision)} precision)` : "Not supplied"
);

const formatInterval = (value: TemporalInterval | null) => {
  if (!value) return "Not supplied";
  const start = value.start ? formatInstant(value.start) : "Open";
  const end = value.end ? formatInstant(value.end) : "Open";
  return `${value.start_inclusive ? "[" : "("}${start} → ${end}${value.end_inclusive ? "]" : ")"}`;
};

const observationCategory = (observation: ContextValueObservation) => {
  if (observation.unit_hint === "percent" || observation.raw_text.includes("%")) return "Percentages";
  if (observation.unit_hint && observation.unit_hint !== "unknown") return "Measurements";
  const numeric = Number(observation.normalized_text.replace("%", ""));
  if (/^\d{4}$/.test(observation.raw_text) && numeric >= 1500 && numeric <= 2200) return "Dates and years";
  if (Number.isFinite(numeric) && Number.isInteger(numeric)) return "Counts and identifiers";
  return "Unclassified values";
};

const observationExcerpt = (observation: ContextValueObservation, evidence: Evidence[]) => {
  const record = evidence.find((item) => item.evidence_id === observation.evidence_id);
  if (!record || observation.start_char == null || observation.end_char == null) return null;
  const start = Math.max(0, observation.start_char - 55);
  const end = Math.min(record.passage.length, observation.end_char + 55);
  return `${start ? "…" : ""}${record.passage.slice(start, end).trim()}${end < record.passage.length ? "…" : ""}`;
};

function VerificationEvidenceTrace({
  evidenceId,
  evidence,
  sources,
  approved,
  openEvidence,
}: {
  evidenceId: string;
  evidence: Evidence[];
  sources: Map<string, Source>;
  approved: string[];
  openEvidence: (evidenceId: string) => void;
}) {
  const record = evidence.find((item) => item.evidence_id === evidenceId);
  const source = record ? sources.get(record.source_id) : null;
  return <details className="verification-evidence">
    <summary>
      <span>{shortId(evidenceId)}</span>
      <b>{source?.publisher ?? source?.title ?? "Evidence record unavailable"}</b>
      <em>{approved.includes(evidenceId) ? "Approved" : "Outside packet"}</em>
    </summary>
    <div>
      <blockquote>“{record?.passage ?? "The cited passage is not available in this report."}”</blockquote>
      <dl>
        <div><dt>Stance</dt><dd>{titleCase(canonicalStance(record?.stance ?? "unknown"))}</dd></div>
        <div><dt>Source type</dt><dd>{titleCase(source?.source_type ?? "unknown")}</dd></div>
        <div><dt>Evidence family</dt><dd>{record?.evidence_family_id ? shortId(record.evidence_family_id) : "Unassigned"}</dd></div>
        <div><dt>Approved use</dt><dd>{titleCase(record?.evidentiary_use ?? "not recorded")}</dd></div>
      </dl>
      <div className="verification-actions">
        {record && <button onClick={() => openEvidence(evidenceId)}>Open full evidence record →</button>}
        {source?.url && <a href={source.url} target="_blank" rel="noreferrer">Open original source ↗</a>}
      </div>
    </div>
  </details>;
}

function VerificationDashboard({
  report,
  sources,
  evidence,
  openEvidence,
  prepareClaimEdit,
  openReviewBrief,
}: {
  report: Report;
  sources: Map<string, Source>;
  evidence: Evidence[];
  openEvidence: (evidenceId: string) => void;
  prepareClaimEdit: () => void;
  openReviewBrief: () => void;
}) {
  const [filter, setFilter] = useState<(typeof verificationFilterOptions)[number][0]>("all");
  const packet = report.verification_packet;
  const context = report.context_verification;
  const numerical = packet?.numerical_assertions ?? [];
  const temporal = packet?.temporal_assertions ?? [];
  const numericalConstruction = packet?.comparative_constructions?.[0] ?? null;
  const temporalConstruction = packet?.temporal_constructions?.[0] ?? null;
  const assertions = [
    ...numerical.map((item) => ({ id: item.assertion_id, kind: "numerical" as const, state: item.state, item })),
    ...temporal.map((item) => ({ id: item.assertion_id, kind: "temporal" as const, state: item.state, item })),
  ];
  const resolvedStates = new Set(["verified", "contradicted", "qualified", "not_applicable"]);
  const problemStates = new Set(["insufficient", "error"]);
  const completed = assertions.filter((item) => resolvedStates.has(item.state)).length;
  const verified = assertions.filter((item) => item.state === "verified").length;
  const contradicted = assertions.filter((item) => item.state === "contradicted").length;
  const qualified = assertions.filter((item) => item.state === "qualified").length;
  const numericalRequired = context?.numerical.required ?? report.plan.requires_numerical_check;
  const temporalRequired = context?.temporal.required ?? report.plan.requires_temporal_check;
  const requirementCount = Number(numericalRequired) + Number(temporalRequired);
  const missingRequiredAssertions =
    (numericalRequired && numerical.length === 0 ? 1 : 0)
    + (temporalRequired && temporal.length === 0 ? 1 : 0);
  const unresolvedAssertions = assertions.filter((item) => problemStates.has(item.state)).length;
  const unresolved = unresolvedAssertions + missingRequiredAssertions;
  const verificationRequired = Boolean(
    numericalRequired || temporalRequired,
  );
  const verificationState = unresolved
    ? "human_review_required"
    : assertions.length
      ? completed === assertions.length ? "complete" : "incomplete"
      : verificationRequired ? "not_evaluated" : "not_required";
  const visible = assertions.filter((assertion) => {
    if (filter === "all") return true;
    if (filter === "problems") return problemStates.has(assertion.state);
    if (filter === "verified") return assertion.state === "verified";
    return assertion.kind === filter;
  });
  const allFindings = [
    ...(packet?.findings ?? []),
    ...numerical.flatMap((item) => item.findings ?? []),
    ...temporal.flatMap((item) => item.findings ?? []),
    ...(report.context_verification?.numerical.findings ?? []),
    ...(report.context_verification?.temporal.findings ?? []),
  ].filter((finding, index, values) => (
    values.findIndex((item) => item.code === finding.code && item.message === finding.message) === index
  ));
  const blockingFindings = allFindings.filter((finding) => finding.severity === "blocking");
  const readinessImpact = blockingFindings.some((finding) => finding.readiness_impact === "publication_block")
    ? "Publication blocked"
    : allFindings.some((finding) => finding.readiness_impact === "human_review")
      ? "Human review required"
      : allFindings.some((finding) => finding.readiness_impact === "readiness_signal")
        ? "Readiness qualified"
        : "No verification restriction";
  const evidenceObservations = context?.numerical.evidence_observations ?? [];
  const groupedObservations = Object.entries(
    evidenceObservations.reduce<Record<string, ContextValueObservation[]>>((groups, observation) => {
      const category = observationCategory(observation);
      groups[category] = [...(groups[category] ?? []), observation];
      return groups;
    }, {}),
  );

  return <div className="verification-workspace">
    <section className={`verification-gate state-${verificationState}`}>
      <div>
        <span>ASSERTION-LEVEL VERIFICATION</span>
        <h2>{verificationState === "complete"
          ? "Verification complete"
          : verificationState === "not_required"
            ? "No numerical or temporal check required"
            : verificationState === "not_evaluated"
              ? "Required verification was not performed"
              : "Verification requires attention"}</h2>
        <p>{unresolved
          ? missingRequiredAssertions
            ? `${missingRequiredAssertions} required check${missingRequiredAssertions === 1 ? "" : "s"} could not be constructed as a typed assertion. ${unresolvedAssertions ? `${unresolvedAssertions} constructed assertion${unresolvedAssertions === 1 ? "" : "s"} also remain unresolved.` : ""}`
            : `${unresolvedAssertions} constructed assertion${unresolvedAssertions === 1 ? "" : "s"} remain insufficient or failed. The unresolved state is preserved instead of being converted into a pass.`
          : assertions.length
            ? "Every detected numerical and temporal assertion reached a typed terminal state."
            : verificationRequired
              ? "The legacy check requested verification, but no typed assertion could be constructed."
              : "The investigation plan did not identify a material numerical or time-sensitive assertion."}</p>
      </div>
      <dl>
        <div><dt>Readiness impact</dt><dd>{readinessImpact}</dd></div>
        <div><dt>Packet version</dt><dd>{packet?.verification_version ?? "Legacy only"}</dd></div>
        <div><dt>Approved evidence available</dt><dd>{packet?.approved_evidence_ids.length ?? evidence.length}</dd></div>
        <div><dt>Completeness</dt><dd>{assertions.length ? `${Math.round(completed / assertions.length * 100)}%` : verificationRequired ? "0%" : "N/A"}</dd></div>
      </dl>
    </section>

    <section className="verification-metrics" aria-label="Verification result summary">
      <article><span>REQUIREMENTS</span><strong>{requirementCount}</strong><small>{Number(numericalRequired)} numerical · {Number(temporalRequired)} temporal</small></article>
      <article><span>ASSERTIONS CONSTRUCTED</span><strong>{assertions.length}</strong><small>Safe typed verification inputs</small></article>
      <article><span>ASSERTIONS VERIFIED</span><strong>{verified}</strong><small>{contradicted} contradicted · {qualified} qualified</small></article>
      <article><span>CONSTRUCTION FAILURES</span><strong>{missingRequiredAssertions}</strong><small>{unresolvedAssertions} additional constructed assertion issue(s)</small></article>
    </section>

    {verificationRequired && <section className="verification-requirements">
      <header><div><span>WHY VERIFICATION WAS REQUESTED</span><h2>Requirement and construction status</h2></div><p>The requirement is distinct from the assertion. A plan may require a check even when the system cannot safely identify its operands.</p></header>
      <div>
        {numericalRequired && <article className={numerical.length ? "constructed" : "failed"}>
          <div><em>NUMERICAL</em><strong>{numerical.length ? "Typed assertion constructed" : "Construction failed"}</strong></div>
          <blockquote>{report.claim.text}</blockquote>
          <dl>
            <div><dt>Requirement source</dt><dd>{report.plan.requires_numerical_check ? "Persisted investigation plan" : "Deterministic claim-context detection"}</dd></div>
            <div><dt>Comparison</dt><dd>{numericalConstruction ? `${numericalConstruction.left_subject} ${titleCase(numericalConstruction.comparator)} ${numericalConstruction.right_subject}` : "No typed comparison constructed"}</dd></div>
            <div><dt>Compared property</dt><dd>{numericalConstruction ? `${titleCase(numericalConstruction.compared_property)} · ${titleCase(numericalConstruction.dimension)}` : "Not resolved"}</dd></div>
            <div><dt>Evidence bound to assertion</dt><dd>{numericalConstruction?.evidence_ids.length ?? 0}</dd></div>
            <div><dt>Outcome</dt><dd>{numerical.length ? `${numerical.length} assertion(s) available` : "Verification was not run"}</dd></div>
          </dl>
        </article>}
        {temporalRequired && <article className={temporal.length ? "constructed" : "failed"}>
          <div><em>TEMPORAL</em><strong>{temporal.length ? "Typed assertion constructed" : "Construction failed"}</strong></div>
          <blockquote>{report.claim.text}</blockquote>
          <dl>
            <div><dt>Requirement source</dt><dd>{report.plan.requires_temporal_check ? "Persisted investigation plan" : "Deterministic time-sensitive wording detection"}</dd></div>
            <div><dt>Reference date</dt><dd>{context?.temporal.reference_date ?? report.claim.reference_date ?? "Not supplied"}</dd></div>
            <div><dt>Temporal relation</dt><dd>{temporalConstruction ? `${temporalConstruction.left_subject} ${titleCase(temporalConstruction.relation)} ${temporalConstruction.right_subject}` : "No typed relation constructed"}</dd></div>
            <div><dt>Evidence bound to assertion</dt><dd>{temporalConstruction?.evidence_ids.length ?? temporal.flatMap((item) => item.observations).length}</dd></div>
            <div><dt>Expected structure</dt><dd>Relation, reference date, effective interval and approved evidence binding</dd></div>
            <div><dt>Outcome</dt><dd>{temporal.length ? `${temporal.length} assertion(s) available` : "Verification was not run"}</dd></div>
          </dl>
        </article>}
      </div>
    </section>}

    {verificationRequired && <section className="verification-trace">
      <div><span>VERIFICATION TRACE</span><h2>What happened in this investigation</h2></div>
      <ol>
        <li className="complete"><i>1</i><div><b>Requirement recorded</b><small>{requirementCount} numerical or temporal requirement(s)</small></div></li>
        <li className={missingRequiredAssertions ? "failed" : "complete"}><i>2</i><div><b>Typed assertion construction</b><small>{missingRequiredAssertions ? `${missingRequiredAssertions} required structure(s) could not be built safely` : `${assertions.length} assertion(s) constructed`}</small></div></li>
        <li className={assertions.length ? "complete" : "skipped"}><i>3</i><div><b>Evidence binding</b><small>{assertions.length ? "Approved evidence references recorded" : "Skipped because no typed assertion existed"}</small></div></li>
        <li className={assertions.length ? unresolvedAssertions ? "failed" : "complete" : "skipped"}><i>4</i><div><b>Deterministic verification</b><small>{assertions.length ? `${completed} of ${assertions.length} reached a terminal state` : "Not run; no calculation or temporal relation was guessed"}</small></div></li>
        <li className={unresolved ? "failed" : "complete"}><i>5</i><div><b>Readiness routing</b><small>{unresolved ? "Human review required" : "No verification escalation recorded"}</small></div></li>
      </ol>
    </section>}

    {unresolved > 0 && <section className="verification-recovery">
      <div><span>AVAILABLE NEXT ACTIONS</span><h2>Resolve the verification gap</h2><p>These actions navigate or prepare existing workflows. They do not silently rerun research or create a paid model call.</p></div>
      <div>
        <button onClick={prepareClaimEdit}>Prepare a clarified claim</button>
        <button onClick={() => evidence[0] && openEvidence(evidence[0].evidence_id)} disabled={!evidence.length}>Inspect retained evidence</button>
        <button onClick={openReviewBrief}>Open human-review brief</button>
      </div>
      <small>Marking a requirement “not applicable” needs a persisted reviewer decision and is intentionally not offered as an informal dashboard toggle.</small>
    </section>}

    {allFindings.length > 0 && <section className="verification-findings">
      <div><span>ACTIONABLE VERIFICATION FINDINGS</span><b>{blockingFindings.length} blocking</b></div>
      {allFindings.map((finding) => <article className={`severity-${finding.severity}`} key={`${finding.code}:${finding.message}`}>
        <em>{titleCase(finding.severity)}</em>
        <div><b>{titleCase(finding.code)}</b><p>{finding.message}</p><small><strong>How to resolve:</strong> {finding.recommended_action}</small></div>
        <span>{titleCase(finding.readiness_impact)}</span>
      </article>)}
    </section>}

    {assertions.length > 0 && <section className="verification-controls">
      <div><span>VERIFICATION ASSERTIONS</span><b>{visible.length} of {assertions.length} shown</b></div>
      <div>{verificationFilterOptions.map(([value, label]) => <button
        className={filter === value ? "active" : ""}
        key={value}
        onClick={() => setFilter(value)}
      >{label}</button>)}</div>
    </section>}

    {assertions.length > 0 && <div className="verification-assertions">
      {visible.map((assertion, index) => assertion.kind === "numerical" ? (() => {
        const item = assertion.item;
        return <article className={`verification-assertion state-${item.state}`} key={item.assertion_id}>
          <header><div><b>Numerical assertion {index + 1}</b><span>{titleCase(item.operation)} · {titleCase(item.comparator)}</span></div><strong>{titleCase(item.state)}</strong></header>
          <blockquote>{item.claim_text_span}</blockquote>
          <section className="numeric-comparison">
            <div><span>EXPECTED</span>{item.expected_values.map((value, valueIndex) => <b key={valueIndex}>{formatNumericValue(value)}</b>)}</div>
            <i>→</i>
            <div><span>EVIDENCE-GROUNDED RESULT</span><b>{item.normalized_result ? formatNumericValue(item.normalized_result) : "Not established"}</b></div>
          </section>
          {(item.expression || item.rounding_rule) && <dl className="verification-calculation">
            {item.expression && <div><dt>Calculation</dt><dd>{item.expression}</dd></div>}
            {item.rounding_rule && <div><dt>Rounding rule</dt><dd>{item.rounding_rule}</dd></div>}
          </dl>}
          {[...(item.findings ?? [])].map((finding) => <div className={`assertion-finding severity-${finding.severity}`} key={finding.code}><b>{finding.message}</b><p>{finding.recommended_action}</p></div>)}
          {item.evidence_ids.length > 0 && <section className="verification-evidence-list"><span>APPROVED EVIDENCE USED</span>{item.evidence_ids.map((id) => <VerificationEvidenceTrace key={id} evidenceId={id} evidence={evidence} sources={sources} approved={packet?.approved_evidence_ids ?? []} openEvidence={openEvidence} />)}</section>}
          {item.limitations.length > 0 && <details className="assertion-limitations"><summary>Assertion limitations</summary>{item.limitations.map((limitation) => <p key={limitation}>{limitation}</p>)}</details>}
        </article>;
      })() : (() => {
        const item = assertion.item;
        return <article className={`verification-assertion state-${item.state}`} key={item.assertion_id}>
          <header><div><b>Temporal assertion {index + 1}</b><span>{titleCase(item.relation)}</span></div><strong>{titleCase(item.state)}</strong></header>
          <blockquote>{item.claim_text_span}</blockquote>
          <section className="temporal-specification">
            <dl>
              <div><dt>Reference date required</dt><dd>{item.requires_reference_date ? "Yes" : "No"}</dd></div>
              <div><dt>Reference date</dt><dd>{formatInstant(item.reference_date)}</dd></div>
              <div><dt>Claimed interval</dt><dd>{formatInterval(item.claimed_interval)}</dd></div>
            </dl>
          </section>
          {[...(item.findings ?? [])].map((finding) => <div className={`assertion-finding severity-${finding.severity}`} key={finding.code}><b>{finding.message}</b><p>{finding.recommended_action}</p></div>)}
          <section className="temporal-observations">
            <div><span>TEMPORAL EVIDENCE TIMELINE</span><b>{item.observations.length} observation{item.observations.length === 1 ? "" : "s"}</b></div>
            {item.observations.map((observation) => <article key={observation.evidence_id}>
              <i />
              <div>
                <b>{shortId(observation.evidence_id)}</b>
                <dl>
                  <div><dt>Publication date</dt><dd>{formatInstant(observation.publication_date)}</dd></div>
                  <div><dt>Effective interval</dt><dd>{formatInterval(observation.effective_interval)}</dd></div>
                  <div><dt>Observed status</dt><dd>{observation.observed_status ?? "Not supplied"}</dd></div>
                  <div><dt>Retrospective</dt><dd>{observation.retrospective ? "Yes" : "No"}</dd></div>
                </dl>
                <VerificationEvidenceTrace evidenceId={observation.evidence_id} evidence={evidence} sources={sources} approved={packet?.approved_evidence_ids ?? []} openEvidence={openEvidence} />
              </div>
            </article>)}
            {!item.observations.length && <p>No typed effective-date or status observation was available.</p>}
          </section>
          {item.limitations.length > 0 && <details className="assertion-limitations"><summary>Assertion limitations</summary>{item.limitations.map((limitation) => <p key={limitation}>{limitation}</p>)}</details>}
        </article>;
      })())}
      {!visible.length && <p className="verification-empty">No assertions match this filter.</p>}
    </div>}

    {context && <details className="legacy-context">
      <summary>Compatibility diagnostic · raw context extraction</summary>
      <div>
        <section>
          <span>NUMERICAL EXTRACTION</span>
          <dl>
            <div><dt>Legacy status</dt><dd>{titleCase(context.numerical.status)}</dd></div>
            <div><dt>Claim operands</dt><dd>{context.numerical.claim_observations.length}</dd></div>
            <div><dt>Evidence tokens</dt><dd>{context.numerical.evidence_observations.length}</dd></div>
            <div><dt>Exactness terms</dt><dd>{context.numerical.exactness_terms.join(", ") || "None"}</dd></div>
          </dl>
          <div className="value-observations">{context.numerical.claim_observations.map((observation, index) => <article key={`claim:${index}`}><b>{observation.raw_text}</b><span>Claim · {observation.unit_hint ?? "unit unknown"}</span><small>{observation.start_char == null ? "Offset unavailable" : `Characters ${observation.start_char}–${observation.end_char}`}</small></article>)}</div>
          {!context.numerical.claim_observations.length && <p>No explicit claim operand was extracted. A required check cannot pass on evidence numbers alone.</p>}
        </section>
        <section>
          <span>EVIDENCE VALUE PROVENANCE</span>
          <p className="diagnostic-warning">These are unclassified tokens found in retained passages. They are not operands, corroboration, or proof until a typed assertion binds them to the claim.</p>
          <div className="observation-groups">{groupedObservations.map(([category, observations]) => <details key={category}>
            <summary><b>{category}</b><span>{observations.length} token{observations.length === 1 ? "" : "s"}</span></summary>
            <div className="value-observations">{observations.slice(0, 6).map((observation, index) => <article key={`${observation.evidence_id}:${observation.start_char}:${index}`}><b>{observation.raw_text}</b><span>{observation.evidence_id ? shortId(observation.evidence_id) : "Unknown evidence"} · {observation.unit_hint ?? "unit unknown"}</span><small>{observationExcerpt(observation, evidence) ?? (observation.start_char == null ? "Offset unavailable" : `Passage characters ${observation.start_char}–${observation.end_char}`)}</small>{observation.evidence_id && <button onClick={() => openEvidence(observation.evidence_id!)}>Inspect passage →</button>}</article>)}</div>
            {observations.length > 6 && <p>{observations.length - 6} additional token(s) hidden in this category.</p>}
          </details>)}</div>
          {!evidenceObservations.length && <p>No numerical evidence token was extracted.</p>}
        </section>
      </div>
    </details>}

    <details className="verification-method">
      <summary>How to interpret verification</summary>
      <div>
        <section><b>Verified is narrow</b><p>It means the typed comparator, values or dates, approved evidence, and bounded calculation agree. It is not a general truth score.</p></section>
        <section><b>Publication date is not effective date</b><p>A later article may describe an earlier event. Temporal verification keeps publication, effective interval, reference date, and retrospective use separate.</p></section>
        <section><b>Fail-closed compatibility</b><p>Raw strings can aid diagnosis but cannot become proof until values, units, dates, and evidence links are typed.</p></section>
      </div>
    </details>
  </div>;
}

const authoritativeGraphSnapshot = (value: AuthoritativeJob): GraphSnapshot | null => {
  if (!value.graph) return null;
  const phaseIndex = graphOrder.indexOf(value.graph.phase as typeof graphOrder[number]);
  const completed = phaseIndex < 0
    ? []
    : graphOrder.slice(0, phaseIndex + (value.job.status === "interrupted" ? 0 : 1));
  return {
    thread_id: value.thread_id,
    status: value.job.status === "interrupted" ? "review_required" : value.graph.phase,
    authoritative_verdict: value.verdict ?? value.interruption?.provisional_verdict ?? "unverifiable",
    final_verdict: value.graph.phase === "complete" ? value.verdict : null,
    completed_nodes: [...completed],
    applied_decision_id: value.review?.decisions.at(-1)?.decision_id ?? null,
    reviewer_identity: value.review?.decisions.at(-1)?.reviewer_identity ?? null,
  };
};

export default function Home() {
  const [apiBase, setApiBase] = useState(defaultApi);
  const [apiDraft, setApiDraft] = useState(defaultApi);
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [graph, setGraph] = useState<GraphSnapshot | null>(null);
  const [review, setReview] = useState<ReviewHistory | null>(null);
  const [section, setSection] = useState("Review brief");
  const [selectedEvidence, setSelectedEvidence] = useState(0);
  const [claim, setClaim] = useState("");
  const [inputMode, setInputMode] = useState<"manual_claim" | "article_text" | "public_url">("manual_claim");
  const [claimCandidates, setClaimCandidates] = useState<ClaimCandidate[]>([]);
  const [decisionKind, setDecisionKind] = useState("approve");
  const [verificationDisposition, setVerificationDisposition] = useState("none");
  const [correctedValue, setCorrectedValue] = useState("");
  const [correctedUnit, setCorrectedUnit] = useState("");
  const [revisedVerdict, setRevisedVerdict] = useState("mixed");
  const [rationale, setRationale] = useState("The cited evidence supports this review decision.");
  const [reviewer, setReviewer] = useState("Md Moshiur Rahman");
  const [approver, setApprover] = useState("Md Rashedul Islam");
  const [busy, setBusy] = useState(false);
  const [activity, setActivity] = useState<"investigation" | "extraction" | "review" | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [job, setJob] = useState<AuthoritativeJob | null>(null);
  const [liveStage, setLiveStage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [apiStatus, setApiStatus] = useState<ApiStatus | null>(null);
  const [telemetry, setTelemetry] = useState<TelemetrySnapshot | null>(null);

  const request = useCallback(async <T,>(path: string, init?: RequestInit): Promise<T> => {
    const response = await fetch(`${apiBase}${path}`, {
      ...init, headers: { "Content-Type": "application/json", ...init?.headers },
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.detail ?? `Request failed (${response.status})`);
    }
    return response.json() as Promise<T>;
  }, [apiBase]);

  const loadInvestigations = useCallback(async () => {
    try {
      const [items, status] = await Promise.all([
        request<Investigation[]>("/api/investigations"),
        request<ApiStatus>("/health"),
      ]);
      setApiStatus(status);
      request<TelemetrySnapshot>("/api/operations/telemetry")
        .then(setTelemetry)
        .catch(() => setTelemetry(null));
      setInvestigations(items); setConnected(true); setError(null);
      if (!selectedId && items.length) setSelectedId(items.at(-1)!.investigation_id);
    } catch {
      setConnected(false);
      setError(`The evidence API could not be reached at ${apiBase}.`);
    }
  }, [apiBase, request, selectedId]);

  useEffect(() => {
    const inferred = `${window.location.protocol}//${window.location.hostname}:8000`;
    window.localStorage.setItem("claim-polygraph-api", inferred);
    setApiBase(inferred);
    setApiDraft(inferred);
  }, []);
  useEffect(() => { void loadInvestigations(); }, [loadInvestigations]);
  useEffect(() => {
    if (!selectedId) { setReport(null); return; }
    void request<Report>(`/api/investigations/${selectedId}/report`)
      .then((value) => { setReport(value); setSelectedEvidence(0); setError(null); })
      .catch((reason: Error) => setError(reason.message));
  }, [request, selectedId]);
  useEffect(() => {
    if (!graph?.thread_id) return;
    const stream = new EventSource(`${apiBase}/api/graph-runs/${graph.thread_id}/events?after=0&follow=true`);
    stream.addEventListener("graph_state", (event) => {
      const snapshot = JSON.parse((event as MessageEvent).data) as GraphSnapshot;
      setGraph(snapshot);
      if (snapshot.status !== "review_required") stream.close();
    });
    stream.onerror = () => stream.close();
    return () => stream.close();
  }, [apiBase, graph?.thread_id]);
  const jobActive = job != null && !["completed", "interrupted", "cancelled", "failed", "dead_letter"].includes(job.job.status);
  const working = busy || jobActive;
  useEffect(() => {
    if (!working) { setElapsedSeconds(0); return; }
    const started = Date.now();
    const timer = window.setInterval(() => setElapsedSeconds(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, [working]);
  useEffect(() => {
    const storedJob = window.localStorage.getItem("claim-polygraph-active-job");
    if (!storedJob) return;
    void request<AuthoritativeJob>(`/api/authoritative-jobs/${storedJob}`)
      .then((restored) => {
        if (["cancelled", "failed", "dead_letter"].includes(restored.job.status)) {
          window.localStorage.removeItem("claim-polygraph-active-job");
        }
        setJob(restored);
        setGraph(authoritativeGraphSnapshot(restored));
        setReview(restored.review);
        if (restored.report_available && restored.investigation_id) setSelectedId(restored.investigation_id);
      })
      .catch(() => window.localStorage.removeItem("claim-polygraph-active-job"));
  }, [request]);
  useEffect(() => {
    if (!job?.job.job_id || !jobActive) return;
    const stream = new EventSource(`${apiBase}/api/authoritative-jobs/${job.job.job_id}/events?after=0&follow=true`);
    stream.addEventListener("authoritative_state", (event) => {
      const state = JSON.parse((event as MessageEvent).data) as AuthoritativeJob;
      setJob(state);
      setGraph(authoritativeGraphSnapshot(state));
      setReview(state.review);
      setLiveStage(state.graph?.phase ?? null);
      if (state.report_available && state.investigation_id) setSelectedId(state.investigation_id);
      if (["completed", "interrupted", "cancelled", "failed", "dead_letter"].includes(state.job.status)) {
        stream.close();
        if (state.job.status !== "interrupted") window.localStorage.removeItem("claim-polygraph-active-job");
        if (state.job.status === "completed" && state.investigation_id) {
          void request<Report>(`/api/investigations/${state.investigation_id}/report`).then(async (completed) => {
            setReport(completed);
            setInvestigations(await request<Investigation[]>("/api/investigations"));
            setTelemetry(await request<TelemetrySnapshot>("/api/operations/telemetry"));
            setActivity(null);
          });
        } else if (state.job.status === "interrupted" && state.investigation_id) {
          void request<Report>(`/api/investigations/${state.investigation_id}/report`)
            .then(setReport)
            .catch(() => null);
          setActivity(null);
        } else if (state.job.last_error) {
          setError(state.job.last_error);
          setActivity(null);
        }
      }
    });
    stream.onerror = () => stream.close();
    return () => stream.close();
  }, [apiBase, job?.job.job_id, jobActive, request]);
  useEffect(() => {
    if (!jobActive || !job?.investigation_id) return;
    const stream = new EventSource(`${apiBase}/api/investigations/${job.investigation_id}/events?after=0&follow=true`);
    const updateStage = (event: Event) => {
      const trace = JSON.parse((event as MessageEvent).data) as { stage?: string };
      if (trace.stage) setLiveStage(trace.stage);
    };
    ["investigation_created", "status_changed", "artifact_created", "provider_called", "provider_failed", "investigation_completed", "investigation_failed"].forEach((name) => stream.addEventListener(name, updateStage));
    stream.onerror = () => stream.close();
    return () => stream.close();
  }, [apiBase, job?.investigation_id, jobActive]);

  const sources = useMemo(() => new Map(report?.sources.map((source) => [source.source_id, source]) ?? []), [report]);
  const evidence = report?.evidence ?? [];
  const selected = evidence[selectedEvidence] ?? null;
  const socialEvidence = evidence.filter(
    (item) => sources.get(item.source_id)?.distribution_medium === "social_platform",
  );
  const socialSourceCount = new Set(socialEvidence.map((item) => item.source_id)).size;
  const socialRiskCount = report?.provenance?.social_risk_findings.length ?? 0;
  const blockingSocialCount = report?.social_evidence_policy?.findings.filter(
    (finding) => finding.severity === "blocking",
  ).length ?? 0;
  const citationSummary = report ? canonicalCitationSummary(report) : null;
  const verificationSummary = report ? canonicalVerificationSummary(report) : null;
  const resolvedVerdict = report ? canonicalVerdictLabel(report, graph) : null;
  const reviewPending = graph?.status === "review_required" && (review?.decisions.length ?? 0) === 0;
  const liveNodeIndex = liveStage ? Math.max(0, graphOrder.indexOf(liveStage as typeof graphOrder[number])) : 0;
  const completedGraphNodes = graph?.completed_nodes.filter((node) => graphOrder.includes(node as typeof graphOrder[number])).length ?? 0;
  const graphProgress = graph ? Math.round(completedGraphNodes / graphOrder.length * 100) : 0;
  const reviewDecisionOptions = [
    ["approve", "Approve provisional verdict"],
    ["revise", "Revise verdict"],
    ["request_evidence", "Request more evidence"],
    ["reject", "Reject packet"],
  ] as const;
  const allowedReviewDecisions = job?.interruption?.allowed_decisions ?? reviewDecisionOptions.map(([value]) => value);
  const effectiveDecisionKind = allowedReviewDecisions.includes(decisionKind)
    ? decisionKind
    : allowedReviewDecisions[0] ?? "reject";
  const reviewConstructions = [
    ...(report?.verification_packet?.comparative_constructions ?? []),
    ...(report?.verification_packet?.temporal_constructions ?? []),
  ];
  const reviewConstruction = reviewConstructions.find(
    (construction) => construction.state !== "constructed",
  ) ?? reviewConstructions[0] ?? null;
  const verificationDispositionOptions = effectiveDecisionKind === "approve"
    ? [["none", "No construction decision"], ["accept", "Accept construction"], ["not_applicable", "Mark requirement not applicable"]]
    : effectiveDecisionKind === "revise"
      ? [["none", "No construction decision"], ["correct", "Correct construction"]]
      : effectiveDecisionKind === "request_evidence"
        ? [["none", "No construction decision"], ["request_evidence", "Request evidence for construction"]]
        : [["none", "No construction decision"]];
  const effectiveVerificationDisposition = verificationDispositionOptions.some(
    ([value]) => value === verificationDisposition,
  ) ? verificationDisposition : "none";
  const researchResultsByAssignment = useMemo(
    () => new Map(job?.graph?.research_results.map((result) => [result.assignment_id, result]) ?? []),
    [job],
  );
  const successfulResearchRoles = job?.graph?.assignments.filter((assignment) => {
    const result = researchResultsByAssignment.get(assignment.assignment_id);
    return result && !result.failure_summary && result.evidence_ids.length > 0;
  }).length ?? 0;
  const failedResearchRoles = job?.graph?.research_results.filter((result) => result.failure_summary).length ?? 0;
  const contaminatedEvidence = evidence.filter((item) => {
    const normalized = item.passage.toLocaleLowerCase();
    const signals = ["get shortened url", "switch to legacy parser", "print/export", "move to sidebar", "wikidata item"];
    return signals.filter((signal) => normalized.includes(signal)).length >= 2 || normalized.includes("Ã");
  });
  const citationReady = report?.full_report_assurance?.publication_status === "ready";
  const overallPublicationReady = Boolean(
    report
    && report.publication_decision
    && report.publication_decision.publication_allowed,
  );
  const reviewerRecommendation = overallPublicationReady
    ? "Publish"
    : report?.social_evidence_policy?.publication_blocked
      ? "Do not publish"
      : "Request more evidence";

  async function submitClaim(event: FormEvent) {
    event.preventDefault(); if (!claim.trim()) return; setBusy(true);
    setActivity(inputMode === "manual_claim" ? "investigation" : "extraction");
    try {
      if (inputMode !== "manual_claim") {
        const extracted = await request<ClaimExtractionPacket>("/api/claim-inputs/extract", {
          method: "POST",
          body: JSON.stringify(inputMode === "public_url"
            ? { kind: "public_url", url: claim }
            : { kind: "article_text", text: claim }),
        });
        setClaimCandidates(extracted.candidates);
        setError(null);
        return;
      }
      await investigateCandidate(claim);
    } catch (reason) { setError((reason as Error).message); } finally { setBusy(false); setActivity(null); }
  }

  async function investigateCandidate(selectedClaim: string) {
      const created = await request<AuthoritativeJob>("/api/authoritative-jobs", {
        method: "POST",
        body: JSON.stringify({ claim: selectedClaim, idempotency_key: `dashboard:${crypto.randomUUID()}` }),
      });
      window.localStorage.setItem("claim-polygraph-active-job", created.job.job_id);
      setJob(created); setLiveStage("created"); setReport(null); setGraph(null); setReview(null);
      setClaim(""); setClaimCandidates([]); setError(null);
  }

  async function cancelJob() {
    if (!jobActive || !job) return;
      const cancelled = await request<AuthoritativeJob>(`/api/authoritative-jobs/${job.job.job_id}/cancel`, {
      method: "POST", headers: { "X-Reviewer-Identity": reviewer },
    });
    setJob(cancelled);
  }

  async function saveDecision() {
    if (!review || !job) return; setBusy(true); setActivity("review");
    try {
      const decision: Record<string, unknown> = { kind: effectiveDecisionKind, reviewer_identity: reviewer, rationale };
      if (effectiveDecisionKind === "revise") decision.revised_verdict = revisedVerdict;
      if (reviewConstruction && effectiveVerificationDisposition !== "none") {
        decision.verification_construction_id = reviewConstruction.construction_id;
        decision.verification_disposition = effectiveVerificationDisposition;
      }
      if (effectiveVerificationDisposition === "correct") {
        decision.corrected_claim_text_span = reviewConstruction?.claim_text_span;
        if (correctedValue.trim()) decision.corrected_value = correctedValue.trim();
        if (correctedUnit.trim()) decision.corrected_unit = correctedUnit.trim();
        if (selected) decision.corrected_evidence_ids = [selected.evidence_id];
      }
      const result = await request<AuthoritativeJob>(
        `/api/authoritative-jobs/${job.job.job_id}/review`,
        {
          method: "POST", headers: { "X-Reviewer-Identity": reviewer },
          body: JSON.stringify({ decision, approver_identity: ["approve", "revise"].includes(effectiveDecisionKind) ? approver : null }),
        },
      );
      setJob(result); setGraph(authoritativeGraphSnapshot(result)); setReview(result.review); setError(null);
      if (result.report_available && result.investigation_id) {
        setSelectedId(result.investigation_id);
        setReport(await request<Report>(`/api/investigations/${result.investigation_id}/report`));
      }
      window.localStorage.removeItem("claim-polygraph-active-job");
    } catch (reason) { setError((reason as Error).message); } finally { setBusy(false); setActivity(null); }
  }

  function saveApiAddress(event: FormEvent) {
    event.preventDefault();
    const normalized = apiDraft.trim().replace(/\/$/, "");
    window.localStorage.setItem("claim-polygraph-api", normalized);
    setApiBase(normalized); setError(null);
  }

  const modelCost = telemetry?.metrics.find((metric) => metric.name === "model.cost_usd")?.total ?? 0;
  const modelTokens = telemetry?.metrics.find((metric) => metric.name === "model.tokens")?.total ?? 0;
  const externalSearchPricing = apiStatus?.retrieval_provider?.startsWith("serpapi") ?? false;

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark">CP</div><div><strong>Claim Polygraph</strong><span>Evidence console</span></div></div>
        <nav aria-label="Investigations">
          <button className="nav-item selected"><span>◎</span>Investigations</button>
          <button className="nav-item"><span>◇</span>Review queue<b>{reviewPending ? 1 : 0}</b></button>
          <a className="nav-item" href="/annotation"><span>✓</span>V3 annotation</a>
          <button className="nav-item"><span>◌</span>System health</button>
        </nav>
        <div className="investigation-list">
          <span>RECENT CASES</span>
          {investigations.slice(-5).reverse().map((item) => (
            <button key={item.investigation_id} className={selectedId === item.investigation_id ? "case active" : "case"} onClick={() => { setSelectedId(item.investigation_id); setGraph(null); setReview(null); setSection("Review brief"); }}>
              <b>{shortId(item.investigation_id)}</b><small>{item.input_claim}</small>
            </button>
          ))}
        </div>
        <div className="phase-card"><span>{apiStatus?.orchestrator === "langgraph" ? "PROMOTED LOCAL DEFAULT" : "ROLLBACK / DIAGNOSTIC MODE"}</span><strong>{titleCase(apiStatus?.orchestrator ?? "connecting")} orchestrator</strong><div className="meter"><i /></div><small>{apiStatus?.live_research ? "Live web research enabled" : "Recorded fixture research"}</small><small>Authority · InvestigationService</small><small>Rollback · Direct composition retained</small></div>
        <div className="profile"><div className="avatar">MR</div><div><strong>Md Moshiur Rahman</strong><span>Reviewer</span></div><span className={connected ? "connection online" : "connection"}>{connected ? "LIVE" : "OFFLINE"}</span></div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div><p>{report ? `INVESTIGATION · ${shortId(report.investigation.investigation_id)}` : "NEW INVESTIGATION"}</p><h1>{report?.claim.text ?? "Investigate a factual claim"}</h1></div>
          <div className="top-actions">
            <div className="cost-chip" aria-label="Temporary usage and cost estimate">
              <span>LOCAL COST TOTAL</span>
              <strong>${modelCost.toFixed(6)}</strong>
              <small>{Math.round(modelTokens).toLocaleString()} model tokens · {externalSearchPricing ? "search billed by SerpAPI plan" : "search $0 API fee"}</small>
            </div>
            <span className={graph?.status === "complete" ? "status complete" : "status"}><i /> {graph ? titleCase(graph.status) : report ? titleCase(report.investigation.status) : "Ready"}</span>
            {report && <a className="ghost" href={`${apiBase}/api/investigations/${report.investigation.investigation_id}/report?format=${overallPublicationReady ? "markdown" : "provisional_markdown"}`} target="_blank">{overallPublicationReady ? "Export report" : "Download draft"}</a>}
          </div>
        </header>
        {!report && <section className="desk-intro">
          <div><span>CLAIM DESK</span><h2>Build a source-grounded fact check</h2><p>Enter one checkable claim or extract candidates from reporting material. The desk will search multiple evidence paths, challenge the initial interpretation, verify context, and prepare a provisional report for your review.</p></div>
          <ol><li><b>1</b><span>Investigate<small>Search and retrieve</small></span></li><li><b>2</b><span>Verify<small>Context and independence</small></span></li><li><b>3</b><span>Review<small>You make the decision</small></span></li></ol>
        </section>}

        <form className="claim-bar" onSubmit={submitClaim}>
          <label htmlFor="input-mode">INPUT TYPE</label>
          <select id="input-mode" value={inputMode} onChange={(event) => { setInputMode(event.target.value as typeof inputMode); setClaimCandidates([]); }}>
            <option value="manual_claim">Manual claim</option>
            <option value="article_text">Article text</option>
            <option value="public_url">Public URL</option>
          </select>
          <label htmlFor="claim-input">{inputMode === "manual_claim" ? "CLAIM TO INVESTIGATE" : inputMode === "article_text" ? "ARTICLE TEXT" : "PUBLIC ARTICLE URL"}</label>
          <div>{inputMode === "article_text"
            ? <textarea id="claim-input" value={claim} onChange={(event) => setClaim(event.target.value)} placeholder="Paste article text. Extraction will not start an investigation." />
            : <input id="claim-input" value={claim} onChange={(event) => setClaim(event.target.value)} placeholder={inputMode === "public_url" ? "https://example.org/article" : "Enter a checkable factual claim…"} />}
            <button className="primary" disabled={busy || !connected || claim.trim().length < 3}>{inputMode === "manual_claim" ? "Investigate" : "Extract claims"}</button></div>
        </form>
        <details className="system-context">
          <summary>Research system and safeguards</summary>
          <div><p><b>{apiStatus?.orchestrator === "langgraph" ? "Unified LangGraph active." : `${titleCase(apiStatus?.orchestrator ?? "Connecting")} path active.`}</b> Research, verification, defender/challenger arguments, judgment, review, and publication are checkpointed in one durable thread.</p><span>InvestigationService authority</span><span>Direct rollback retained</span><span>{apiStatus?.live_research ? "Live research" : "Fixture research"}</span></div>
        </details>
        {working && <section className="activity-card" role="status" aria-live="polite">
          <div className="activity-pulse"><i /><i /><i /></div>
          <div className="activity-copy">
            <span>{jobActive || activity === "investigation" ? "INVESTIGATION IN PROGRESS" : activity === "extraction" ? "EXTRACTING CLAIMS" : "UPDATING REVIEW"}</span>
            <strong>{jobActive || activity === "investigation" ? `${titleCase(liveStage ?? job?.job.status ?? "queued")} · Researchers are gathering, challenging and verifying evidence` : activity === "extraction" ? "Finding checkable statements in the submitted material" : "Saving the decision and resuming the durable graph"}</strong>
            <small>{elapsedSeconds}s elapsed · This is live activity, not an estimated completion percentage.</small>
          </div>
          {jobActive && <button className="cancel-job" onClick={cancelJob}>Cancel safely</button>}
          <div className="activity-track"><i /></div>
        </section>}
        {jobActive && <section className="working-graph" aria-label="Investigation graph is running">
          <div className="working-graph-head"><div><span>AUTHORITATIVE INVESTIGATION PROGRESS</span><strong>{titleCase(liveStage ?? job.job.status)}</strong></div><small>{job.investigation_id ? "Persisted evidence-production trace connected" : "Durable job queued · waiting for investigation ID"}</small></div>
          <div className="graph-progress" role="progressbar" aria-valuenow={Math.round((liveNodeIndex + 1) / graphOrder.length * 100)} aria-valuemin={0} aria-valuemax={100}><i style={{width: `${Math.round((liveNodeIndex + 1) / graphOrder.length * 100)}%`}} /></div>
          <div className="graph investigation-graph graph-running">
            {graphOrder.map((node, index) => <div className={`node ${index < liveNodeIndex ? "done" : index === liveNodeIndex ? "active" : "waiting"}`} key={node}><div>{index < liveNodeIndex ? "✓" : index === liveNodeIndex ? "↻" : index + 1}</div><span>{graphLabels[node]}</span>{index < graphOrder.length - 1 && <i />}</div>)}
          </div>
          <p>One durable LangGraph thread is coordinating authoritative research, verification, arguments, judgment, review routing and publication. InvestigationService remains the domain and persistence authority inside each node.</p>
        </section>}
        {claimCandidates.length > 0 && <section className="record-list" aria-label="Extracted claim candidates">
          {claimCandidates.map((candidate) => <article key={candidate.candidate_id}>
            <b>{candidate.rank}. {candidate.text}</b>
            <span>Check-worthiness {Math.round(candidate.checkworthiness * 100)}%</span>
            <button className="ghost" disabled={busy} onClick={() => { setBusy(true); setActivity("investigation"); void investigateCandidate(candidate.text).catch((reason: Error) => setError(reason.message)).finally(() => { setBusy(false); setActivity(null); }); }}>Investigate this claim</button>
          </article>)}
        </section>}
        {error && <div className="error-banner" role="alert">{error}</div>}

        {!report && reviewPending && job?.interruption ? (
          <div className="pre-report-workspace" aria-label="Investigation result requiring review">
            <section className="pre-report-hero">
              <div><span>PROVISIONAL INVESTIGATION RESULT</span><h2>{job.interruption.claim_text}</h2><p>{job.interruption.route_reason}</p></div>
              <div className="provisional-seal"><small>PROVISIONAL VERDICT</small><strong>{titleCase(job.interruption.provisional_verdict)}</strong><em>Publication blocked</em></div>
            </section>

            <section className="interrupted-summary">
              <div><span>WORKFLOW</span><strong>{titleCase(job.graph?.phase ?? "review")}</strong><small>Checkpoint {job.graph?.checkpoint_sequence ?? "—"}</small></div>
              <div><span>RESEARCH ROLES</span><strong>{job.graph?.assignments.length ?? 0}</strong><small>{successfulResearchRoles} returned evidence · {failedResearchRoles} failed</small></div>
              <div><span>APPROVED EVIDENCE</span><strong>{job.graph?.approved_evidence_ids.length ?? 0}</strong><small>{job.graph?.evidence_families.length ?? 0} independent families</small></div>
              <div><span>UNRESOLVED</span><strong>{job.graph?.unresolved_questions.length ?? 0}</strong><small>Research questions</small></div>
              <div><span>COST SO FAR</span><strong>${(job.graph?.consumption.estimated_cost_usd ?? 0).toFixed(4)}</strong><small>{job.graph?.consumption.model_calls ?? 0} model calls · {job.graph?.consumption.total_tokens ?? 0} tokens</small></div>
              <div><span>DURATION</span><strong>{(job.graph?.consumption.duration_seconds ?? 0).toFixed(1)}s</strong><small>{job.graph?.consumption.completed_rounds ?? 0} research round</small></div>
            </section>

            <section className="graph-card interrupted-graph">
              <div className="card-heading"><div><span>AUTHORITATIVE LANGGRAPH TRACE</span><h2>Paused safely at human review</h2><small className="authority-note">All completed operations are checkpointed. Requesting more evidence resumes this thread without replaying paid work.</small></div><div className="graph-progress-label"><strong>{graphProgress}%</strong><small>{completedGraphNodes} of {graphOrder.length} phases checkpointed</small></div></div>
              <div className="graph-progress" role="progressbar" aria-valuenow={graphProgress} aria-valuemin={0} aria-valuemax={100}><i style={{width: `${graphProgress}%`}} /></div>
              <div className="graph">{graphOrder.map((node, index) => { const done = graph?.completed_nodes.includes(node); const active = node === "review"; return <div className={`node ${done ? "done" : active ? "active" : "waiting"}`} key={node}><div>{done ? "✓" : active ? "!" : index + 1}</div><span>{graphLabels[node]}</span>{index < graphOrder.length - 1 && <i />}</div>; })}</div>
            </section>

            <div className="pre-report-columns">
              <main>
                <section className="detail-card">
                  <div className="detail-heading"><div><span>MULTI-AGENT RESEARCH</span><h2>What each specialist returned</h2></div><small>{job.graph?.consumption.role_activations ?? 0} role activations</small></div>
                  <div className="agent-results">{job.graph?.assignments.map((assignment) => { const result = researchResultsByAssignment.get(assignment.assignment_id); const failed = Boolean(result?.failure_summary); return <article className={failed ? "agent-failed" : "agent-success"} key={assignment.assignment_id}><div><b>{titleCase(assignment.role)}</b><em>{failed ? "Retrieval failed" : result?.evidence_ids.length ? "Evidence returned" : "No retained evidence"}</em></div><p>{failed ? result?.failure_summary : `${result?.source_ids.length ?? 0} sources · ${result?.evidence_ids.length ?? 0} evidence passages`}</p><small>Round {assignment.round_number} · Assignment {shortId(assignment.assignment_id)}</small></article>; })}</div>
                </section>

                <section className="detail-card">
                  <div className="detail-heading"><div><span>RESEARCH REQUIREMENTS</span><h2>Coverage requested by the plan</h2></div><small>{job.graph?.requirements.length ?? 0} requirements</small></div>
                  <div className="requirement-list">{job.graph?.requirements.map((requirement) => <article key={requirement.requirement_id}><b>{titleCase(requirement.kind)}</b><p>{requirement.rationale_summary}</p><small>{shortId(requirement.requirement_id)}</small></article>)}</div>
                </section>

                <section className="detail-grid">
                  <article className="detail-card blocker-card"><span>PUBLICATION SAFEGUARDS</span><h2>Why no final report was released</h2>{job.graph?.publication_blocking_reasons.map((reason, index) => <p key={index}><b>{index + 1}</b>{reason}</p>)}</article>
                  <article className="detail-card"><span>UNRESOLVED QUESTIONS</span><h2>What additional research must answer</h2>{job.graph?.unresolved_questions.map((question) => <p className="unresolved-item" key={question.question_id}>{question.question_summary}</p>)}</article>
                </section>

                <section className="detail-grid">
                  <article className="detail-card"><span>BUDGET & CONSUMPTION</span><h2>Resource controls</h2><dl className="compact-dl"><div><dt>Rounds</dt><dd>{job.graph?.consumption.completed_rounds ?? 0} / {job.graph?.budget.maximum_rounds ?? "—"}</dd></div><div><dt>Role activations</dt><dd>{job.graph?.consumption.role_activations ?? 0}</dd></div><div><dt>Search calls</dt><dd>{job.graph?.consumption.search_calls ?? 0} / {job.graph?.budget.maximum_search_calls ?? "—"}</dd></div><div><dt>Fetched pages</dt><dd>{job.graph?.consumption.fetched_pages ?? 0}</dd></div><div><dt>Model calls</dt><dd>{job.graph?.consumption.model_calls ?? 0} / {job.graph?.budget.maximum_model_calls ?? "—"}</dd></div><div><dt>Cost ceiling</dt><dd>${(job.graph?.budget.maximum_cost_usd ?? 0).toFixed(2)}</dd></div></dl></article>
                  <article className="detail-card"><span>DURABILITY & AUDIT</span><h2>Persisted trace</h2><dl className="compact-dl"><div><dt>Job</dt><dd>{shortId(job.job.job_id)}</dd></div><div><dt>Thread</dt><dd>{shortId(job.thread_id)}</dd></div><div><dt>Investigation</dt><dd>{job.investigation_id ? shortId(job.investigation_id) : "—"}</dd></div><div><dt>Attempts</dt><dd>{job.job.attempts}</dd></div><div><dt>Artifacts</dt><dd>{job.graph?.artifacts.length ?? 0}</dd></div><div><dt>Audit chain</dt><dd>{review?.chain_valid ? "Verified" : "Pending"}</dd></div></dl></article>
                </section>

                <section className="detail-card">
                  <div className="detail-heading"><div><span>JOB EVENT TIMELINE</span><h2>What happened</h2></div><small>{job.events.length} durable events</small></div>
                  <div className="event-timeline">{job.events.map((event) => <article key={event.sequence}><i>{event.sequence}</i><div><b>{titleCase(event.action)}</b><p>{event.detail}</p><small>{new Date(event.occurred_at).toLocaleString()}</small></div></article>)}</div>
                </section>
              </main>

              <aside className="review-panel sticky-review">
                <div className="review-kicker">REQUIRED NEXT ACTION</div>
                <h2>{job.interruption.allowed_decisions.includes("approve") ? "Confirm provisional verdict" : "Evidence retrieval needs attention"}</h2>
                <p className="reason">{job.interruption.route_reason}</p>
                <label>Decision<select value={effectiveDecisionKind} onChange={(event) => setDecisionKind(event.target.value)}>{reviewDecisionOptions.filter(([value]) => allowedReviewDecisions.includes(value)).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
                {reviewConstruction && <label>Verification construction decision<select value={effectiveVerificationDisposition} onChange={(event) => setVerificationDisposition(event.target.value)}>{verificationDispositionOptions.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select><small>Applies to construction {shortId(reviewConstruction.construction_id)} and is persisted in the immutable review record.</small></label>}
                {effectiveVerificationDisposition === "correct" && <div className="review-correction-grid"><label>Correct value<input value={correctedValue} onChange={(event) => setCorrectedValue(event.target.value)} placeholder="Exact reviewed value" /></label><label>Correct unit<input value={correctedUnit} onChange={(event) => setCorrectedUnit(event.target.value)} placeholder="Normalized unit" /></label><small>The currently selected approved evidence passage will be attached to this correction.</small></div>}
                {effectiveDecisionKind === "revise" && <label>Revised verdict<select value={revisedVerdict} onChange={(event) => setRevisedVerdict(event.target.value)}>{["supported", "contradicted", "mixed", "misleading", "unsupported", "unverifiable"].map((label) => <option value={label} key={label}>{titleCase(label)}</option>)}</select></label>}
                <label>Review rationale<textarea value={rationale} onChange={(event) => setRationale(event.target.value)} /></label>
                <label>Reviewer identity<input value={reviewer} onChange={(event) => setReviewer(event.target.value)} /></label>
                {["approve", "revise"].includes(effectiveDecisionKind) && <label>Distinct approver identity<input value={approver} onChange={(event) => setApprover(event.target.value)} /></label>}
                <button className="primary" onClick={saveDecision} disabled={busy || rationale.trim().length < 3 || reviewer.trim().length < 3 || (["approve", "revise"].includes(effectiveDecisionKind) && (approver.trim().length < 3 || approver.trim().toLocaleLowerCase() === reviewer.trim().toLocaleLowerCase()))}>{busy ? "Saving…" : "Save decision & resume graph"}</button>
                <small className="immutable">Only permitted decisions are offered. The result is appended to the immutable review history.</small>
              </aside>
            </div>
          </div>
        ) : !report ? (
          <section className="empty-state">
            <span>CONNECTED EVIDENCE WORKSPACE</span><h2>{connected ? "Submit your first claim" : "Connect the evidence API"}</h2>
            <p>{connected ? "The investigation service will produce a typed evidence packet and citation-grounded verdict." : "Start the local API, then retry. You can also change its address below."}</p>
            <form onSubmit={saveApiAddress}><input aria-label="API address" value={apiDraft} onChange={(event) => setApiDraft(event.target.value)} /><button className="ghost">Save & retry</button></form>
          </section>
        ) : (
          <>
            <section className={`report-lifecycle ${overallPublicationReady ? "ready" : "provisional"}`}>
              <div><span>{overallPublicationReady ? "PUBLICATION-READY REPORT" : "PROVISIONAL REPORT · HUMAN DECISION PENDING"}</span><h2>The automated investigation is complete</h2><p>{overallPublicationReady ? "The recorded safeguards permit publication. A journalist should still inspect decisive evidence before use." : "The complete evidence-assisted report is available below. Publication remains blocked until a human reviews the evidence, limitations, and automated recommendation."}</p></div>
              <div><small>WORKFLOW POSITION</small><strong>{reviewPending ? "Human review" : overallPublicationReady ? "Ready to publish" : titleCase(graph?.status ?? report.investigation.status)}</strong><em>{evidence.length} evidence passage{evidence.length === 1 ? "" : "s"} · {citationSummary?.total ?? 0} canonical citation finding{citationSummary?.total === 1 ? "" : "s"}</em></div>
            </section>
            <div className="summary-row">
              <div><span>{graph?.final_verdict ? "FINAL VERDICT" : "PROVISIONAL VERDICT"}</span><strong>{titleCase(resolvedVerdict ?? report.verdict.label)}</strong><small>{graph?.final_verdict ? "Review-resumed graph decision" : report.judgment_policy ? "Judgment-policy enforced label" : "Persisted verdict fallback"}</small></div>
              <div><span>CONFIDENCE <button className="info-dot" aria-label="Explain confidence" title="A calibrated probability of verdict correctness. A dash means the system has not been empirically calibrated and will not invent a probability.">?</button></span><strong>{report.verdict.confidence == null ? "—" : `${Math.round(report.verdict.confidence * 100)}%`}</strong><small>{report.verdict.confidence == null ? "Not calibrated" : "Calibrated probability"}</small></div>
              <div><span>CITATION SUPPORT <button className="info-dot" aria-label="Explain citation support" title="Material report assertions marked fully supported in the final full-report citation-assurance audit.">?</button></span><strong>{citationSummary?.rate ?? 0}%</strong><small>{citationSummary?.supported ?? 0}/{citationSummary?.total ?? 0} · {citationSummary?.authority}</small></div>
              <div><span>INDEPENDENT FAMILIES <button className="info-dot" aria-label="Explain evidence families" title="Groups of sources that appear to originate independently. Multiple pages repeating one original report count as one family.">?</button></span><strong>{report.independence_analysis?.independent_family_count ?? "—"}</strong><small>Target {report.plan.minimum_independent_families}</small></div>
              <div><span>EVIDENCE ITEMS</span><strong>{evidence.length}</strong></div>
            </div>
            <div className="graph-card">
              <div className="card-heading"><div><span>UNIFIED AUTHORITATIVE LANGGRAPH</span><h2>{graph ? titleCase(graph.status) : "Awaiting investigation"}</h2><small className="authority-note">Each node calls a typed InvestigationService operation; the graph coordinates but does not bypass domain authority.</small></div>{graph ? <div className="graph-progress-label"><strong>{graphProgress}%</strong><small>{completedGraphNodes} of {graphOrder.length} phases checkpointed</small></div> : null}</div>
              {graph && <div className="graph-progress" role="progressbar" aria-valuenow={graphProgress} aria-valuemin={0} aria-valuemax={100} aria-label="Checkpointed graph progress"><i style={{width: `${graphProgress}%`}} /></div>}
              <div className="graph">
                {graphOrder.map((node, index) => {
                  const done = graph?.completed_nodes.includes(node);
                  const active = graph?.status === "review_required" && node === "review";
                  return <div className={`node ${done ? "done" : active ? "active" : "waiting"}`} key={node}><div>{done ? "✓" : active ? "!" : index + 1}</div><span>{graphLabels[node]}</span>{index < graphOrder.length - 1 && <i />}</div>;
                })}
              </div>
            </div>
            <div className="tabs" role="tablist">
              {["Review brief", "Overview", "Evidence", "Social evidence", "Decision rationale", "Verification", "Citation audit", "Review history", "System architecture"].map((item) => <button key={item} role="tab" aria-selected={section === item} className={section === item ? "active" : ""} onClick={() => setSection(item)}>{item}</button>)}
            </div>
            {section === "Review brief" && <div className="review-brief-dashboard">
              <section className={`review-recommendation ${overallPublicationReady ? "publishable" : "hold"}`}>
                <div><span>REVIEW RECOMMENDATION</span><h2>{reviewerRecommendation}</h2><p>{overallPublicationReady ? "The persisted authoritative publication decision permits publication. A journalist should still inspect decisive evidence." : report.publication_decision ? "The authoritative publication decision records one or more blocking safeguards." : "No authoritative publication decision is available, so the dashboard fails closed and treats this report as provisional."}</p></div>
                <div className="review-verdict"><small>PROVISIONAL FACTUAL VERDICT</small><strong>{titleCase(resolvedVerdict ?? report.verdict.label)}</strong><em>{report.verdict.confidence == null ? "Confidence not calibrated" : `${Math.round(report.verdict.confidence * 100)}% calibrated confidence`}</em></div>
              </section>
              <section className="review-gates">
                <article><span>JUDGMENT READINESS</span><strong>{titleCase(report.readiness?.state ?? "not reported")}</strong><p>{report.readiness?.state === "human_review_required" ? "Blocking safeguards remain; the verdict is provisional." : "The deterministic readiness gate does not require escalation."}</p></article>
                <article><span>CITATION ASSURANCE</span><strong>{titleCase(report.full_report_assurance?.publication_status ?? "not reported")}</strong><p>{citationReady ? "The report sentences passed citation matching. This does not establish source authority or independence." : "The report has citation-assurance failures."}</p></article>
                <article><span>INDEPENDENCE</span><strong>{titleCase(report.provenance?.requirement_state ?? "not reported")}</strong><p>{report.provenance ? `${report.provenance.confirmed_independent_lower_bound} confirmed; up to ${report.provenance.possible_independent_upper_bound} possible; ${report.provenance.unresolved_dependency_count} unresolved relationship(s).` : "No provenance assessment was recorded."}</p></article>
                <article><span>VERIFICATION</span><strong>{verificationSummary?.completeness ?? 0}% complete</strong><p>{verificationSummary?.unresolved ? `${verificationSummary.unresolved} required assertion-level check(s) remain unresolved.` : "No unresolved assertion-level verification check was recorded."}</p><small>{verificationSummary?.authority}</small></article>
                <article><span>SOURCE QUALITY</span><strong>{report.readiness?.source_quality_unknown_count ?? 0} unknown signal(s)</strong><p>Unknown quality is not evidence that a source is poor, but it prevents the system from claiming verified authority.</p></article>
                <article><span>PASSAGE HYGIENE</span><strong>{contaminatedEvidence.length ? `${contaminatedEvidence.length} warning(s)` : "Clean"}</strong><p>{contaminatedEvidence.length ? "Retained passages appear to include navigation text, export controls, encoding damage, or other page boilerplate." : "No common navigation or encoding contamination was detected."}</p></article>
                <article className={blockingSocialCount ? "gate-blocked" : ""}><span>SOCIAL EVIDENCE</span><strong>{socialEvidence.length ? `${socialEvidence.length} item(s)` : "None retained"}</strong><p>{blockingSocialCount ? `${blockingSocialCount} blocking social-evidence finding(s) prevent publication.` : socialRiskCount ? `${socialRiskCount} social-source risk signal(s) require inspection.` : "No unresolved social-evidence risk was recorded."}</p></article>
              </section>
              <div className="review-brief-columns">
                <section className="detail-card">
                  <span>CLAIM FRAMING</span><h2>{report.claim.text}</h2>
                  <dl className="compact-dl"><div><dt>Type</dt><dd>{titleCase(report.claim.claim_type)}</dd></div><div><dt>Checkworthiness</dt><dd>{Math.round(report.claim.checkworthiness * 100)}%</dd></div><div><dt>Geography/context</dt><dd>{report.claim.geography ?? "Not specified"}</dd></div><div><dt>Recorded ambiguities</dt><dd>{report.claim.ambiguities.length}</dd></div></dl>
                  {!report.claim.ambiguities.length && <p className="review-warning">A zero ambiguity count means the automated normalizer recorded none; it is not proof that broad terms such as “people” or a historical period are sufficiently scoped.</p>}
                </section>
                <section className="detail-card">
                  <span>WHY REVIEW WAS ROUTED</span><h2>{report.readiness?.reason_codes.length ?? 0} safeguard signals</h2>
                  <div className="reason-chips">{report.readiness?.reason_codes.map((reason) => <b key={reason}>{titleCase(reason)}</b>)}</div>
                  <dl className="compact-dl"><div><dt>Blocking challenges</dt><dd>{report.readiness?.blocking_challenge_count ?? 0}</dd></div><div><dt>Nonblocking challenges</dt><dd>{report.readiness?.nonblocking_challenge_count ?? 0}</dd></div><div><dt>Unresolved questions</dt><dd>{report.readiness?.unresolved_question_count ?? report.verdict.unresolved_questions.length}</dd></div><div><dt>Material coverage</dt><dd>{Math.round((report.readiness?.material_coverage ?? 0) * 100)}%</dd></div></dl>
                </section>
              </div>
              <section className="review-actions-card">
                <div><span>RECOMMENDED REVIEW ACTION</span><h2>{reviewerRecommendation}</h2><p>{overallPublicationReady ? "Confirm the cited sources and approve through the authoritative review thread." : "Obtain at least one directly relevant academic or primary historical source, replace contaminated passages, resolve provenance, and rerun verification and citation assurance."}</p></div>
                <div><button onClick={() => setSection("Evidence")}>Inspect exact evidence</button>{(socialEvidence.length > 0 || socialRiskCount > 0) && <button onClick={() => setSection("Social evidence")}>Trace social evidence</button>}<button onClick={() => setSection("Verification")}>Inspect unresolved checks</button><button onClick={() => setSection("Citation audit")}>Inspect citation mapping</button></div>
              </section>
              {reviewPending && job?.interruption && <section className="journalist-decision">
                <div className="decision-intro"><span>YOUR JUDGMENT</span><h2>Record the editorial decision</h2><p>The automated verdict is advisory. Review the report first, then approve, revise, request stronger evidence, or reject the packet. Only actions permitted by the authoritative workflow are shown.</p><dl><div><dt>Automated recommendation</dt><dd>{reviewerRecommendation}</dd></div><div><dt>Provisional verdict</dt><dd>{titleCase(job.interruption.provisional_verdict)}</dd></div><div><dt>Audit history</dt><dd>{review?.chain_valid ? "Verified" : "Pending"}</dd></div></dl></div>
                <div className="decision-form">
                  <label>Editorial decision<select value={effectiveDecisionKind} onChange={(event) => setDecisionKind(event.target.value)}>{reviewDecisionOptions.filter(([value]) => allowedReviewDecisions.includes(value)).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
                  {reviewConstruction && <label>Verification construction decision<select value={effectiveVerificationDisposition} onChange={(event) => setVerificationDisposition(event.target.value)}>{verificationDispositionOptions.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select><small>Applies to construction {shortId(reviewConstruction.construction_id)} and is written to the durable review history.</small></label>}
                  {effectiveVerificationDisposition === "correct" && <div className="review-correction-grid"><label>Correct value<input value={correctedValue} onChange={(event) => setCorrectedValue(event.target.value)} placeholder="Exact reviewed value" /></label><label>Correct unit<input value={correctedUnit} onChange={(event) => setCorrectedUnit(event.target.value)} placeholder="Normalized unit" /></label><small>Correction is bound to the selected approved evidence passage.</small></div>}
                  {effectiveDecisionKind === "revise" && <label>Revised verdict<select value={revisedVerdict} onChange={(event) => setRevisedVerdict(event.target.value)}>{["supported", "contradicted", "mixed", "misleading", "unsupported", "unverifiable"].map((label) => <option value={label} key={label}>{titleCase(label)}</option>)}</select></label>}
                  <label>Decision rationale<textarea value={rationale} onChange={(event) => setRationale(event.target.value)} placeholder="Explain what you verified and why this action is justified." /></label>
                  <div className="identity-row"><label>Reviewer<input value={reviewer} onChange={(event) => setReviewer(event.target.value)} /></label>{["approve", "revise"].includes(effectiveDecisionKind) && <label>Distinct approver<input value={approver} onChange={(event) => setApprover(event.target.value)} /></label>}</div>
                  <button className="primary" onClick={saveDecision} disabled={busy || rationale.trim().length < 3 || reviewer.trim().length < 3 || (["approve", "revise"].includes(effectiveDecisionKind) && (approver.trim().length < 3 || approver.trim().toLocaleLowerCase() === reviewer.trim().toLocaleLowerCase()))}>{busy ? "Recording decision…" : "Record decision and resume"}</button>
                  <small>The decision is appended to the immutable review history. Completed paid research operations are not repeated.</small>
                </div>
              </section>}
              <p className="transparency-note"><b>Review boundary:</b> this brief organizes persisted safeguards and deterministic hygiene warnings. It supports a human decision; it does not impersonate or replace the named reviewer.</p>
            </div>}
            {section === "Overview" && <div className="report-dashboard">
              <section className="report-card verdict-card">
                <span>DECISION</span><h2>{titleCase(resolvedVerdict ?? report.verdict.label)}</h2>
                <p>{report.readiness?.state === "human_review_required" ? "The evidence points to this verdict, but one or more safeguards require human review." : "The evidence packet has passed the current deterministic readiness checks."}</p>
                <dl><div><dt>Readiness</dt><dd>{titleCase(report.readiness?.state ?? "not reported")}</dd></div><div><dt>Publication</dt><dd>{titleCase(report.full_report_assurance?.publication_status ?? "not reported")}</dd></div><div><dt>Critical citation failures</dt><dd>{report.full_report_assurance?.critical_failure_count ?? "—"}</dd></div></dl>
              </section>
              <section className="report-card">
                <span>RESEARCH COVERAGE</span><h2>{evidence.length} retained passages</h2>
                <div className="stance-bars">{["supporting", "contradictory", "qualifying", "context"].map((stance) => { const count = evidence.filter((item) => canonicalStance(item.stance) === stance).length; return <div key={stance}><label>{titleCase(stance)} <b>{count}</b></label><i><b style={{width: `${evidence.length && count ? Math.max(4, count / evidence.length * 100) : 0}%`}} /></i></div>; })}</div>
                <small>Paths: {report.plan.required_research_paths.map(titleCase).join(" · ")}</small>
              </section>
              <section className="report-card">
                <span>INDEPENDENCE & PROVENANCE</span><h2>{titleCase(report.provenance?.requirement_state ?? "not reported")}</h2>
                <dl><div><dt>Confirmed independent lower bound</dt><dd>{report.provenance?.confirmed_independent_lower_bound ?? "—"}</dd></div><div><dt>Possible upper bound</dt><dd>{report.provenance?.possible_independent_upper_bound ?? "—"}</dd></div><div><dt>Unresolved relationships</dt><dd>{report.provenance?.unresolved_dependency_count ?? "—"}</dd></div></dl>
              </section>
              <section className="report-card">
                <span>VERIFICATION</span><h2>{verificationSummary?.completeness ?? 0}% complete</h2>
                <dl><div><dt>Unresolved typed checks</dt><dd>{verificationSummary?.unresolved ?? "—"}</dd></div><div><dt>Numerical check required</dt><dd>{verificationSummary?.requiredNumerical ? "Yes" : "No"}</dd></div><div><dt>Temporal check required</dt><dd>{verificationSummary?.requiredTemporal ? "Yes" : "No"}</dd></div><div><dt>Authority</dt><dd>{verificationSummary?.authority ?? "Not reported"}</dd></div></dl>
              </section>
              <section className={`report-card social-overview-card ${blockingSocialCount ? "blocked" : ""}`}>
                <span>SOCIAL-EVIDENCE GOVERNANCE</span><h2>{blockingSocialCount ? "Publication blocked" : socialEvidence.length ? "Review trace available" : "No social evidence retained"}</h2>
                <dl><div><dt>Social passages</dt><dd>{socialEvidence.length}</dd></div><div><dt>Distinct social sources</dt><dd>{socialSourceCount}</dd></div><div><dt>Policy findings</dt><dd>{report.social_evidence_policy?.findings.length ?? 0}</dd></div></dl>
                <button className="inline-link" onClick={() => setSection("Social evidence")}>Open social-source trace →</button>
              </section>
              <details className="score-guide">
                <summary>How to read scores and safeguards</summary>
                <div><b>Relevance</b><p>A model-assigned claim-to-passage match from 0–100%. It measures topical usefulness, not source truth, quality, or verdict confidence.</p></div>
                <div><b>Citation support</b><p>The share of audited material sentences fully supported by their cited passages.</p></div>
                <div><b>Readiness</b><p>A deterministic completeness gate. It is deliberately separate from probability or confidence.</p></div>
                <div><b>Independent families</b><p>Source-origin groups. Repetition across dependent sources does not increase the confirmed independent count.</p></div>
              </details>
            </div>}
            {section === "Social evidence" && <div className="social-transparency-dashboard">
              <section className={`social-policy-hero ${report.social_evidence_policy?.publication_blocked ? "blocked" : ""}`}>
                <div>
                  <span>SOCIAL-EVIDENCE POLICY</span>
                  <h2>{report.social_evidence_policy?.publication_blocked ? "Critical social dependency blocks publication" : socialEvidence.length ? "Every social item has a traceable, limited role" : "No social-media passage was retained as evidence"}</h2>
                  <p>Social reach, engagement, and platform badges are not truth signals. Each item is evaluated by identity, authenticity, attribution, original-source linkage, approved use, corroboration, and shared origin.</p>
                </div>
                <dl>
                  <div><dt>Social passages</dt><dd>{socialEvidence.length}</dd></div>
                  <div><dt>Policy findings</dt><dd>{report.social_evidence_policy?.findings.length ?? 0}</dd></div>
                  <div><dt>Blocking findings</dt><dd>{blockingSocialCount}</dd></div>
                  <div><dt>Publication</dt><dd>{titleCase(report.publication_decision?.status ?? (report.social_evidence_policy?.publication_blocked ? "blocked" : "not blocked"))}</dd></div>
                </dl>
              </section>

              {report.social_evidence_policy?.findings.length ? <section className="social-findings" aria-label="Social evidence policy findings">
                <div className="section-heading"><div><span>POLICY FINDINGS</span><h2>What requires attention</h2></div><small>Deterministic · persisted · reviewable</small></div>
                <div>{report.social_evidence_policy.findings.map((finding) => <article className={`social-finding ${finding.severity}`} key={finding.finding_id}><em>{titleCase(finding.severity)}</em><div><b>{titleCase(finding.code)}</b><p>{finding.reason}</p>{finding.evidence_ids.length > 0 && <small>Evidence {finding.evidence_ids.map(shortId).join(" · ")}</small>}</div></article>)}</div>
              </section> : null}

              {socialEvidence.length ? <div className="social-item-list">
                {socialEvidence.map((item, itemIndex) => {
                  const source = sources.get(item.source_id)!;
                  const context = source.social_context;
                  const eligibility = source.social_eligibility;
                  const original = context?.original_source;
                  const underlying = original?.source_id ? sources.get(original.source_id) : null;
                  const family = report.provenance?.families.find((candidate) => candidate.source_ids.includes(source.source_id));
                  const quality = report.provenance?.source_quality.find((candidate) => candidate.source_id === source.source_id);
                  const risks = report.provenance?.social_risk_findings.filter((finding) => finding.source_id === source.source_id || finding.evidence_ids.includes(item.evidence_id)) ?? [];
                  const policyFindings = report.social_evidence_policy?.findings.filter((finding) => finding.source_id === source.source_id || finding.evidence_ids.includes(item.evidence_id)) ?? [];
                  const useLabel = eligibility?.decision === "ineligible"
                    ? "Excluded from evidence"
                    : item.evidentiary_use === "discovery_lead"
                      ? "Discovery lead"
                      : item.evidentiary_use === "context"
                        ? "Context only"
                        : "Approved, constrained evidence";
                  return <article className="social-trace-card" key={item.evidence_id}>
                    <header>
                      <div><span>{titleCase(context?.account.platform ?? "social platform")} · {shortId(item.evidence_id)}</span><h2>{context?.account.display_name ?? (context?.account.handle ? `@${context.account.handle}` : source.title)}</h2><p>{source.title}</p></div>
                      <div className={`use-badge ${eligibility?.decision ?? "unknown"}`}><small>EVIDENTIARY ROLE</small><strong>{useLabel}</strong></div>
                    </header>
                    <div className="social-trace">
                      <section>
                        <b>1</b><span>Discovery</span>
                        <strong>{titleCase(context?.post_type ?? "unknown post")}</strong>
                        <p>{titleCase(context?.capture_method ?? "unknown capture")} · {context?.posted_at ? new Date(context.posted_at).toLocaleString() : "Post time not recorded"}</p>
                      </section>
                      <section>
                        <b>2</b><span>Identity & authenticity</span>
                        <strong>{titleCase(context?.account.authenticity_status ?? "unknown")}</strong>
                        <p>{context?.account.identity_resolved ? `${titleCase(context.account.account_type)} identity recorded.` : "Account identity unresolved."} {context?.account.authenticity_basis ?? ""}</p>
                      </section>
                      <section>
                        <b>3</b><span>Original source</span>
                        <strong>{original?.resolved ? "Resolved" : original ? "Unresolved" : "Original post"}</strong>
                        <p>{underlying?.title ?? original?.url ?? (original ? "Linked record unavailable" : "No derivative source claimed")}</p>
                      </section>
                      <section>
                        <b>4</b><span>Approved use</span>
                        <strong>{titleCase(item.evidentiary_use)}</strong>
                        <p>{eligibility?.allowed_uses.length ? `Allowed: ${eligibility.allowed_uses.map(titleCase).join(", ")}.` : "No evidentiary use is approved."} {eligibility?.requires_corroboration ? "Non-social corroboration required." : ""}</p>
                      </section>
                      <section>
                        <b>5</b><span>Verdict effect</span>
                        <strong>{policyFindings.some((finding) => finding.severity === "blocking") ? "Publication blocker" : item.evidentiary_use === "context" ? "Contextual only" : "Bounded contribution"}</strong>
                        <p>{policyFindings[0]?.reason ?? "No item-specific blocking policy finding was recorded."}</p>
                      </section>
                    </div>
                    <div className="social-detail-grid">
                      <section>
                        <span>ACCOUNT AND ATTRIBUTION</span>
                        <dl>
                          <div><dt>Account</dt><dd>{context?.account.handle ? `@${context.account.handle}` : "Not recorded"}</dd></div>
                          <div><dt>Authority scope</dt><dd>{context?.account.authority_scope ?? "Not established"}</dd></div>
                          <div><dt>Attribution</dt><dd>{titleCase(context?.attribution_scope ?? "unspecified")}</dd></div>
                          <div><dt>Content origin</dt><dd>{titleCase(context?.content_origin_status ?? "unknown")}</dd></div>
                          <div><dt>Eyewitness claim</dt><dd>{context?.eyewitness_claim ? "Yes — corroboration required" : "No"}</dd></div>
                          <div><dt>Unavailable/deleted</dt><dd>{context?.unavailable_or_deleted ? "Yes" : "No"}</dd></div>
                        </dl>
                      </section>
                      <section>
                        <span>PROVENANCE AND INDEPENDENCE</span>
                        <dl>
                          <div><dt>Evidence family</dt><dd>{family?.family_id ? shortId(family.family_id) : item.evidence_family_id ? shortId(item.evidence_family_id) : "Unassigned"}</dd></div>
                          <div><dt>Family members</dt><dd>{family?.source_ids.length ?? 1}</dd></div>
                          <div><dt>Grouping reason</dt><dd>{family?.grouping_reasons.map(titleCase).join(", ") || "No shared origin recorded"}</dd></div>
                          <div><dt>Independent proof allowed</dt><dd>{eligibility?.independent_proof_allowed ? "Yes, within scope" : "No"}</dd></div>
                        </dl>
                        <p className="independence-warning">Reposts, screenshots, and publications derived from one underlying record remain one evidence family, even across platforms.</p>
                      </section>
                      <section>
                        <span>QUALITY AND LIMITATIONS</span>
                        <div className="quality-signals">{quality?.dimensions.map((dimension) => <div key={dimension.dimension}><b>{titleCase(dimension.dimension)}</b><em>{titleCase(dimension.finding)}</em><p>{dimension.reason}</p></div>) ?? <p>No source-quality dimensions were recorded.</p>}</div>
                        {quality?.ignored_signals.length ? <p className="ignored-signals"><b>Ignored as authority signals:</b> {quality.ignored_signals.map(titleCase).join(", ")}</p> : null}
                      </section>
                    </div>
                    {(risks.length > 0 || eligibility?.reason_codes.length) && <details className="social-limitations">
                      <summary>Why this classification was assigned</summary>
                      {eligibility?.reason_codes.map((reason) => <p key={reason}><b>Eligibility:</b> {titleCase(reason)}</p>)}
                      {risks.map((risk, index) => <p key={`${risk.code}-${index}`}><b>{titleCase(risk.severity)} risk · {titleCase(risk.code)}:</b> {risk.reason}</p>)}
                    </details>}
                    <footer>
                      <a href={source.url} target="_blank" rel="noreferrer">Open accessible social source ↗</a>
                      {underlying?.url ? <a href={underlying.url} target="_blank" rel="noreferrer">Open underlying record ↗</a> : original?.url ? <a href={original.url} target="_blank" rel="noreferrer">Open linked origin ↗</a> : null}
                      <button onClick={() => { setSelectedEvidence(evidence.findIndex((candidate) => candidate.evidence_id === item.evidence_id)); setSection("Evidence"); }}>Inspect retained passage {itemIndex + 1} →</button>
                    </footer>
                  </article>;
                })}
              </div> : <section className="social-empty-state">
                <span>NO RETAINED SOCIAL EVIDENCE</span>
                <h2>This investigation did not rely on a social-media passage.</h2>
                <p>Social links may still have served as discovery leads, but no social item appears in the approved argument packet. The ordinary evidence and provenance views remain authoritative.</p>
                <button onClick={() => setSection("Evidence")}>Return to evidence packet</button>
              </section>}

              <p className="transparency-note"><b>Interpretation boundary:</b> authenticity means the account or capture was attributed with recorded evidence. It does not make every statement true. Relevance means topical match. It does not measure correctness, authority, independence, or probability.</p>
            </div>}
            {section === "Decision rationale" && <div className="decision-dashboard">
              <section className="decision-hero">
                <span>VERDICT EXPLANATION</span><h2>{report.verdict.concise_explanation}</h2>
                <p>{report.verdict.detailed_reasoning}</p>
                <div className="decision-badge">{titleCase(report.verdict.label)}</div>
              </section>
              <div className="decision-columns">
                <section className="report-card">
                  <span>ARGUMENT LEDGER</span><h2>{titleCase(report.argument_ledger?.arguments[0]?.resolution ?? "not reported")}</h2>
                  <p>The ledger resolves each material proposition using only evidence retained in the approved packet.</p>
                  <dl><div><dt>Supporting items</dt><dd>{report.argument_ledger?.arguments[0]?.supporting_evidence_ids.length ?? 0}</dd></div><div><dt>Contradictory items</dt><dd>{report.argument_ledger?.arguments[0]?.contradictory_evidence_ids.length ?? 0}</dd></div><div><dt>Qualifying items</dt><dd>{report.argument_ledger?.arguments[0]?.qualifying_evidence_ids.length ?? 0}</dd></div></dl>
                </section>
                <section className="report-card">
                  <span>POLICY CONSTRAINT</span><h2>{titleCase(report.judgment_policy?.enforced_label ?? report.verdict.label)}</h2>
                  <p>{report.judgment_policy?.rationale ?? "No separate judgment-policy explanation was recorded."}</p>
                  <dl><div><dt>Proposed label</dt><dd>{titleCase(report.judgment_policy?.proposed_label ?? report.verdict.label)}</dd></div><div><dt>Policy changed it</dt><dd>{report.judgment_policy?.changed ? "Yes" : "No"}</dd></div><div><dt>Allowed labels</dt><dd>{report.judgment_policy?.allowed_labels.map(titleCase).join(", ") ?? "—"}</dd></div></dl>
                </section>
              </div>
              <section className="challenge-card">
                <div><span>CHALLENGER FINDINGS</span><h2>What could weaken this decision</h2></div>
                {report.argument_ledger?.challenge_findings.map((finding) => <article key={finding.finding_id}><b>{titleCase(finding.kind)}</b><em>{titleCase(finding.severity)}</em><p>{finding.rationale}</p></article>)}
                {!report.argument_ledger?.challenge_findings.length && <p>No deterministic challenger findings were recorded.</p>}
              </section>
              <section className="decisive-list">
                <span>DECISIVE EVIDENCE</span>
                {report.verdict.decisive_evidence_ids.map((id) => { const item = evidence.find((candidate) => candidate.evidence_id === id); const source = item ? sources.get(item.source_id) : null; return <button key={id} onClick={() => { const index = evidence.findIndex((candidate) => candidate.evidence_id === id); setSelectedEvidence(Math.max(0, index)); setSection("Evidence"); }}><b>{shortId(id)}</b><strong>{source?.title ?? "Retained evidence"}</strong><small>Open exact passage →</small></button>; })}
              </section>
              <p className="transparency-note"><b>Transparency boundary:</b> this view exposes the persisted explanation, evidence links, deterministic challenges, and policy decisions. It does not expose or reconstruct private model chain-of-thought.</p>
            </div>}
            {section === "Verification" && <VerificationDashboard
              report={report}
              sources={sources}
              evidence={evidence}
              openEvidence={(id) => {
                const evidenceIndex = evidence.findIndex((item) => item.evidence_id === id);
                if (evidenceIndex >= 0) {
                  setSelectedEvidence(evidenceIndex);
                  setSection("Evidence");
                }
              }}
              prepareClaimEdit={() => {
                setClaim(report.claim.text);
                window.scrollTo({ top: 0, behavior: "smooth" });
              }}
              openReviewBrief={() => setSection("Review brief")}
            />}
            {section === "System architecture" && <div className="architecture-dashboard">
              <section className="architecture-hero">
                <span>ACCEPTED ARCHITECTURE · ADR 0021</span>
                <h2>One graph coordinates the lifecycle. Domain authority stays explicit.</h2>
                <p>The unified LangGraph is the approved bounded local and observational default. It checkpoints every material transition and resumes the same investigation after review or restart.</p>
              </section>
              <div className="architecture-grid">
                <article><span>DEFAULT PATH</span><h3>Unified LangGraph</h3><p>Coordinates claim analysis, genuine multi-agent research, verification, arguments, judgment, citation assurance, review and publication.</p><b>{apiStatus?.orchestrator === "langgraph" ? "Active now" : "Not currently active"}</b></article>
                <article><span>DOMAIN AUTHORITY</span><h3>InvestigationService</h3><p>Owns typed domain operations, persisted evidence, verification artifacts, policy enforcement and final report construction.</p><b>Cannot be bypassed by agents</b></article>
                <article><span>ROLLBACK</span><h3>Direct composition</h3><p>Runs the same authoritative operations sequentially when the graph must be disabled or rolled back.</p><b>Retained and tested</b></article>
                <article><span>RESEARCH ROLES</span><h3>Bounded specialists</h3><p>Primary-source, general, academic, fact-check and challenger roles receive typed assignments and return evidence through the shared approval boundary.</p><b>Budgeted · deduplicated · checkpointed</b></article>
              </div>
              <section className="trust-boundary">
                <div><span>WHAT THE PROMOTION PROVES</span><p>Workflow equivalence, durable recovery, citation enforcement, review continuity and challenger coverage within the measured local envelope.</p></div>
                <div><span>WHAT IT DOES NOT CLAIM</span><p>Calibrated autonomous factual accuracy, unbounded distributed scale, or permission to publish unsupported critical assertions.</p></div>
              </section>
            </div>}
            {["Evidence", "Citation audit", "Review history"].includes(section) && <div className="content-grid">
              <section className="evidence-panel">
                <div className="panel-title"><div><span>{section.toUpperCase()}</span><h2>{section === "Evidence" ? "Evidence packet" : section}</h2></div><span className="filter">{section === "Evidence" ? `${evidence.length} passages` : `${section === "Citation audit" ? report.full_report_assurance?.final_audit.findings.length ?? report.audits.length : review?.events.length ?? 0} records`}</span></div>
                {section === "Evidence" && <div className="evidence-layout">
                  <div className="evidence-list">
                    {evidence.map((item, index) => {
                      const source = sources.get(item.source_id);
                      return <button className={selectedEvidence === index ? "evidence-item active" : "evidence-item"} onClick={() => setSelectedEvidence(index)} key={item.evidence_id}><div><span>{shortId(item.evidence_id)}</span><b>{titleCase(item.stance)}</b></div><strong>{source?.publisher ?? source?.title ?? "Stored source"}</strong>{source?.distribution_medium === "social_platform" && <em className="social-source-label">Social · {titleCase(item.evidentiary_use)}</em>}<p>{item.passage}</p></button>;
                    })}
                    {!evidence.length && <p className="empty-copy">No retained evidence passages.</p>}
                  </div>
                  <article className="passage">
                    {selected ? <><div className="passage-meta"><span>EXACT PASSAGE</span><b>{shortId(selected.evidence_id)}</b></div><blockquote>“{selected.passage}”</blockquote><dl><div><dt>Source</dt><dd>{sources.get(selected.source_id)?.url ? <a href={sources.get(selected.source_id)?.url} target="_blank" rel="noreferrer">{sources.get(selected.source_id)?.title ?? "Open source"} ↗</a> : sources.get(selected.source_id)?.title ?? "Stored source"}</dd></div><div><dt>Publisher</dt><dd>{sources.get(selected.source_id)?.publisher ?? "Not recorded"}</dd></div><div><dt>Source type</dt><dd>{titleCase(sources.get(selected.source_id)?.source_type ?? "unknown")}</dd></div><div><dt>Distribution</dt><dd>{titleCase(sources.get(selected.source_id)?.distribution_medium ?? "unknown")}</dd></div><div><dt>Approved use</dt><dd>{titleCase(selected.evidentiary_use)}</dd></div><div><dt>Stance</dt><dd>{titleCase(canonicalStance(selected.stance))}</dd></div><div><dt>Relevance <button className="info-dot" title="Claim-to-passage topical match. It is not a truth, quality, or confidence score." aria-label="Explain relevance score">?</button></dt><dd>{Math.round(selected.relevance_score * 100)}%</dd></div><div><dt>Evidence family</dt><dd>{selected.evidence_family_id ? shortId(selected.evidence_family_id) : "Unassigned"}</dd></div></dl><div className="score-explanation"><b>What {Math.round(selected.relevance_score * 100)}% means</b><p>The passage was rated as highly related to this claim. This score does not establish that the passage is correct or independent; those are evaluated separately.</p></div>{sources.get(selected.source_id)?.distribution_medium === "social_platform" && <div className="social-evidence-callout"><b>Social-source constraints apply</b><p>This item can only be used as {titleCase(selected.evidentiary_use)}. Inspect identity, authenticity, original-source linkage, corroboration, and policy findings before relying on it.</p><button onClick={() => setSection("Social evidence")}>Open full social trace →</button></div>}<div className="support-note">Citation data loaded from the authoritative report.</div></> : <p className="empty-copy">Select an evidence passage.</p>}
                  </article>
                </div>}
                {section === "Citation audit" && <CitationAuditView
                  report={report}
                  sources={sources}
                  evidence={evidence}
                  openEvidence={(id) => {
                    const evidenceIndex = evidence.findIndex((item) => item.evidence_id === id);
                    if (evidenceIndex >= 0) {
                      setSelectedEvidence(evidenceIndex);
                      setSection("Evidence");
                    }
                  }}
                />}
                {section === "Review history" && <div className="record-list">{review?.events.map((event) => <article key={event.sequence}><b>{event.sequence}. {titleCase(event.action)}</b><span>{event.actor_identity}</span></article>)}{review?.decisions.filter((decision) => decision.verification_disposition).map((decision) => <article key={`construction-${decision.decision_id}`}><b>Verification construction: {titleCase(decision.verification_disposition!)}</b><span>{decision.verification_construction_id ? shortId(decision.verification_construction_id) : "Unknown construction"} · persisted with decision {shortId(decision.decision_id)}{decision.corrected_value ? ` · ${decision.corrected_value} ${decision.corrected_unit ?? ""}` : ""}{decision.corrected_evidence_ids?.length ? ` · ${decision.corrected_evidence_ids.length} approved evidence binding(s)` : ""}</span></article>)}{!review && <p className="empty-copy">Start a review workflow to create an immutable history.</p>}</div>}
              </section>
              <aside className="review-panel">
                <div className="review-kicker">HUMAN REVIEW</div>
                {!graph ? <div className="approved-state"><div className="approval-mark">{report.verdict.human_review_required ? "!" : "✓"}</div><h2>{report.verdict.human_review_required ? "Human review required" : "No human review required"}</h2><p>{report.verdict.human_review_required ? report.verdict.review_reason ?? "The persisted report requires review, but its live graph thread is not loaded in this browser." : "This completed report was publication-ready under the recorded deterministic safeguards."}</p><dl><div><dt>Verdict</dt><dd>{titleCase(report.verdict.label)}</dd></div><div><dt>Publication</dt><dd>{titleCase(report.full_report_assurance?.publication_status ?? "recorded")}</dd></div><div><dt>Review record</dt><dd>{review ? `${review.events.length} event(s)` : "None required"}</dd></div></dl></div>
                  : reviewPending ? <><h2>{job?.interruption?.allowed_decisions.includes("approve") ? "Confirm final verdict" : "Evidence retrieval needs attention"}</h2><p className="reason">{review?.request.reason}</p><label>Decision<select value={effectiveDecisionKind} onChange={(event) => setDecisionKind(event.target.value)}>{reviewDecisionOptions.filter(([value]) => allowedReviewDecisions.includes(value)).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>{reviewConstruction && <label>Verification construction decision<select value={effectiveVerificationDisposition} onChange={(event) => setVerificationDisposition(event.target.value)}>{verificationDispositionOptions.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>}{effectiveDecisionKind === "revise" && <label>Revised verdict<select value={revisedVerdict} onChange={(event) => setRevisedVerdict(event.target.value)}>{["supported", "contradicted", "mixed", "misleading", "unsupported", "unverifiable"].map((label) => <option value={label} key={label}>{titleCase(label)}</option>)}</select></label>}<label>Review rationale<textarea value={rationale} onChange={(event) => setRationale(event.target.value)} /></label><label>Reviewer identity<input value={reviewer} onChange={(event) => setReviewer(event.target.value)} /></label>{["approve", "revise"].includes(effectiveDecisionKind) && <label>Distinct approver identity<input value={approver} onChange={(event) => setApprover(event.target.value)} /></label>}<button className="primary" onClick={saveDecision} disabled={busy || rationale.trim().length < 3 || reviewer.trim().length < 3 || (["approve", "revise"].includes(effectiveDecisionKind) && (approver.trim().length < 3 || approver.trim().toLocaleLowerCase() === reviewer.trim().toLocaleLowerCase()))}>{busy ? "Saving…" : "Save decision & resume graph"}</button><small className="immutable">The decision is appended to the immutable audit history.</small></>
                  : <div className="approved-state"><div className="approval-mark">{graph.status === "complete" ? "✓" : "!"}</div><h2>{titleCase(graph.status)}</h2><p>The graph resumed from its SQLite checkpoint without repeating completed research nodes.</p><dl><div><dt>Final verdict</dt><dd>{graph.final_verdict ? titleCase(graph.final_verdict) : "Not issued"}</dd></div><div><dt>Reviewer</dt><dd>{graph.reviewer_identity ?? "—"}</dd></div><div><dt>Audit chain</dt><dd>{review?.chain_valid ? "Verified" : "Pending"}</dd></div></dl></div>}
              </aside>
            </div>
            }
          </>
        )}
      </section>
    </main>
  );
}

