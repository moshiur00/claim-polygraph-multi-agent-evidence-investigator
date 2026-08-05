"use client";
/* eslint-disable react-hooks/set-state-in-effect */

import { FormEvent, ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import {
  ApiConfigurationError,
  FALLBACK_API_ADDRESS,
  loadApiConfiguration,
  resetApiConfiguration,
  saveApiConfiguration,
} from "./api-configuration.mjs";
import { useDurableEventStream } from "./use-durable-event-stream";
import { parseNavigationState, serializeNavigationState, type WorkspaceView } from "./navigation-state.mjs";

type Investigation = { investigation_id: string; input_claim: string; status: string; stage: string };
type Evidence = {
  evidence_id: string; source_id: string; passage: string; stance: string;
  relevance_score: number; evidence_family_id: string | null; evidentiary_use: string;
  chunk_id?: string | null; passage_start_char?: number | null; passage_end_char?: number | null;
  context?: string | null; extraction_status?: string; retrieval_score?: number | null;
  entailment_score?: number | null; temporal_compatibility?: number | null;
};
type EvidenceIntegrity = {
  evidence_id: string; status: "clean" | "caution" | "contaminated";
  reason_codes: string[]; matched_fragments: string[]; exact_quote: string;
  context_before: string | null; context_after: string | null; decisive: boolean;
  approved_use: string; requires_human_review: boolean; publication_blocking: boolean;
  excerpt_status?: "source_span_verified" | "bounded_diagnostic";
  excerpt_start_char?: number | null; excerpt_end_char?: number | null;
  argument_eligible?: boolean; citation_eligible?: boolean; decisive_use_eligible?: boolean;
  disposition_id?: string | null; disposition_kind?: string | null;
  disposition_reason?: string | null;
  remediation_actions?: string[];
};
type EvidenceDisposition = {
  disposition_id: string; investigation_id: string; evidence_id: string;
  kind: "exclude" | "approve_use" | "request_replacement" | "request_reextraction";
  approved_use: string | null; reason: string; reviewer_identity: string;
  approver_identity: string; created_at: string;
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
  author?: string | null; publication_date?: string | null; retrieved_at?: string;
  extraction_status?: string; rights_status?: string; content_retention?: string;
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
type ArgumentLedgerPacket = {
  approved_evidence_ids?: string[];
  propositions: Array<{ proposition_id: string; text: string; material: boolean }>;
  arguments: Array<{ proposition_id: string; resolution: string; supporting_evidence_ids: string[]; contradictory_evidence_ids: string[]; qualifying_evidence_ids: string[]; unresolved_reasons: string[] }>;
  challenge_findings: Array<{ finding_id: string; kind: string; severity: string; rationale: string; evidence_ids: string[] }>;
  limitations: string[];
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
  evidence_dispositions?: EvidenceDisposition[];
  evidence_integrity?: EvidenceIntegrity[];
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
    scope_findings?: VerificationFinding[];
    limitations: string[];
  } | null;
  verification_packet: VerificationPacket | null;
  argument_ledger: ArgumentLedgerPacket | null;
  effective_argument_ledger?: ArgumentLedgerPacket | null;
  judgment_policy: {
    proposed_label: string; enforced_label: string; allowed_labels: string[];
    changed: boolean; applied: boolean; human_review_required: boolean;
    reason_codes: string[]; rationale: string;
  } | null;
  full_report_assurance: FullReportAssurance | null;
  effective_full_report_assurance?: FullReportAssurance | null;
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
  claim_id: string; reason: string; created_by: string; created_at: string;
};
type ReviewHistory = {
  request: ReviewRequest;
  findings: Array<{
    finding_id: string; summary: string; kind: string; evidence_ids: string[];
    recorded_by: string; created_at: string;
  }>;
  decisions: Array<{
    record_id: string; decision_id: string; kind: string; reviewer_identity: string; rationale: string;
    proposed_verdict: string | null; created_at: string;
    verification_construction_id?: string | null;
    verification_disposition?: string | null;
    corrected_claim_text_span?: string | null; corrected_value?: string | null;
    corrected_unit?: string | null; corrected_evidence_ids?: string[];
  }>;
  approvals: Array<{
    approval_id: string; decision_record_id: string; approver_identity: string; decision: string;
    rationale: string; created_at: string;
  }>;
  revisions: Array<{
    revision_id: string; original_verdict: string; revised_verdict: string;
    change_kind: string; rationale: string; created_at: string;
  }>;
  events: Array<{
    sequence: number; action: string; actor_identity: string;
    entity_id: string; occurred_at: string; event_hash: string;
  }>;
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
  usage: {
    model_calls: number; input_tokens: number; cached_input_tokens: number;
    output_tokens: number; total_tokens: number; estimated_cost_usd: number;
    unpriced_model_calls: number;
  } | null;
};

const graphOrder = ["created", "claim_analysis", "planning", "research", "verification", "arguments", "judgment", "citation_assurance", "readiness", "review", "finalization", "complete"] as const;
const reportSections = ["Review brief", "Overview", "Evidence", "Social evidence", "Decision rationale", "Verification", "Citation audit", "Review history", "System architecture"] as const;
const graphLabels: Record<string, string> = {
  created: "Create", claim_analysis: "Analyze", planning: "Plan",
  research: "Multi-agent research", verification: "Verify",
  arguments: "Defender / challenger", judgment: "Judgment",
  citation_assurance: "Citation assurance", readiness: "Readiness",
  review: "Human review", finalization: "Publish", complete: "Complete",
};
type ConnectionState = "initializing" | "connecting" | "connected" | "unavailable" | "invalid";
const titleCase = (value: string) => value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
const shortId = (value: string) => value.slice(0, 8).toUpperCase();
const clientRequestId = () => {
  const generated = globalThis.crypto?.randomUUID?.();
  if (generated) return generated;
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
};
const reviewStateOf = (history: ReviewHistory) => {
  const latestDecision = history.decisions.at(-1);
  if (!latestDecision) return "review";
  const requiresDistinctApproval = ["approve", "revise"].includes(latestDecision.kind);
  const latestDecisionApproved = history.approvals.some((approval) => approval.decision_record_id === latestDecision.record_id);
  return requiresDistinctApproval && !latestDecisionApproved ? "approval" : "complete";
};
const reviewReasonCode = (reason: string) => reason.match(/(?:required|reason):\s*([a-z0-9_]+)/i)?.[1]?.toLocaleLowerCase() ?? reason.split(/[:.]/).map((part) => part.trim()).filter(Boolean).at(-1)?.toLocaleLowerCase().replaceAll(" ", "_") ?? "human_review";
const reviewReasonLabel = (reason: string) => {
  const code = reviewReasonCode(reason);
  return ({
    readiness_requires_review: "Safeguards require a human decision",
    policy_disagreement: "Evidence and policy assessments disagree",
    citation_audit_incomplete: "Citation support requires review",
    critical_verification_unresolved: "A critical verification check is unresolved",
    source_quality_unknown: "Source authority requires confirmation",
    blocking_challenge: "A material challenge remains unresolved",
    social_evidence_requires_review: "Social-evidence safeguards require review",
  } as Record<string, string>)[code] ?? titleCase(code);
};
const telemetryMetricView = (metric: TelemetrySnapshot["metrics"][number]) => {
  const average = metric.count > 0 ? metric.total / metric.count : 0;
  const views: Record<string, { label: string; value: string; detail: string }> = {
    "api.latency_ms": { label: "API response time", value: `${average.toLocaleString(undefined, { maximumFractionDigits: 1 })} ms avg`, detail: `${metric.count.toLocaleString()} timed requests` },
    "provider.latency_ms": { label: "Provider response time", value: `${average.toLocaleString(undefined, { maximumFractionDigits: 1 })} ms avg`, detail: `${metric.count.toLocaleString()} provider operations` },
    "model.tokens": { label: "Model tokens", value: Math.round(metric.total).toLocaleString(), detail: `${metric.count.toLocaleString()} model observations` },
    "model.cost_usd": { label: "Estimated model cost", value: `$${metric.total.toFixed(6)}`, detail: `${metric.count.toLocaleString()} cost observations` },
    "evidence.yield": { label: "Evidence yielded", value: Math.round(metric.total).toLocaleString(), detail: `${metric.count.toLocaleString()} measured research operations` },
    "langgraph.node_latency_ms": { label: "Workflow-step time", value: `${average.toLocaleString(undefined, { maximumFractionDigits: 1 })} ms avg`, detail: `${metric.count.toLocaleString()} timed workflow steps` },
  };
  return views[metric.name] ?? {
    label: titleCase(metric.name.replaceAll(".", " ")),
    value: `${metric.total.toLocaleString()}${metric.unit ? ` ${metric.unit}` : ""}`,
    detail: `${metric.count.toLocaleString()} observation${metric.count === 1 ? "" : "s"}`,
  };
};
const providerLabel = (value: string | undefined) => {
  if (!value) return "Not reported";
  const [provider, product] = value.split(":", 2);
  const providerName = ({ openai: "OpenAI", serpapi: "SerpAPI", langgraph: "Workflow engine" } as Record<string, string>)[provider.toLocaleLowerCase()] ?? titleCase(provider);
  const productName = product
    ? ({ google: "Google", "gpt-4o-mini": "GPT-4o mini" } as Record<string, string>)[product.toLocaleLowerCase()] ?? product
    : null;
  return productName ? `${providerName} · ${productName}` : providerName;
};

function MetricHelp({ id, label, children }: { id: string; label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return <span className="metric-help">
    <button
      type="button"
      className="info-dot"
      aria-label={label}
      aria-expanded={open}
      aria-controls={id}
      onClick={() => setOpen((value) => !value)}
    >?</button>
    {open && <span id={id} role="note" className="metric-help-popover">{children}</span>}
  </span>;
}
const canonicalStance = (value: string) => ({
  supports: "supporting", supporting: "supporting",
  contradicts: "contradictory", contradictory: "contradictory",
  qualifies: "qualifying", qualifying: "qualifying",
  context: "context",
}[value] ?? value);

const canonicalVerdictLabel = (report: Report, graph: GraphSnapshot | null) =>
  graph?.final_verdict ?? report.judgment_policy?.enforced_label ?? report.verdict.label;

const canonicalCitationSummary = (report: Report) => {
  const assurance = report.effective_full_report_assurance ?? report.full_report_assurance;
  if (assurance) {
    const audit = assurance.final_audit;
    return {
      rate: Math.round(audit.full_support_rate * 100),
      supported: audit.supported_count,
      total: audit.findings.length,
      status: assurance.publication_status,
      authority: report.effective_full_report_assurance
        ? "Effective full-report citation assurance"
        : "Historical full-report citation assurance",
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
  const historicalAssurance = report.full_report_assurance;
  const assurance = report.effective_full_report_assurance ?? historicalAssurance;
  const usingEffectiveAssurance = Boolean(report.effective_full_report_assurance);
  const historicalDiffers = Boolean(
    report.effective_full_report_assurance
    && historicalAssurance
    && (
      report.effective_full_report_assurance.publication_status !== historicalAssurance.publication_status
      || report.effective_full_report_assurance.final_audit.supported_count !== historicalAssurance.final_audit.supported_count
      || report.effective_full_report_assurance.final_audit.approved_evidence_ids.join() !== historicalAssurance.final_audit.approved_evidence_ids.join()
    ),
  );
  const integrityByEvidence = new Map(
    (report.evidence_integrity ?? []).map((item) => [item.evidence_id, item]),
  );
  const currentCitationEligibleCount = (report.evidence_integrity ?? []).filter(
    (item) => item.citation_eligible === true,
  ).length;
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
        <span>{usingEffectiveAssurance ? "EFFECTIVE FULL-REPORT CITATION ASSURANCE" : "HISTORICAL FULL-REPORT CITATION ASSURANCE"}</span>
        <h2>{publicationStatus === "ready" ? "Current citation gate passed" : "Current publication blocked by citation assurance"}</h2>
        <p>{publicationStatus === "ready"
          ? "Every current material clause has an eligible passage reference and meets the lexical support threshold."
          : assurance?.blocking_reasons[0] ?? "One or more material assertions still lack complete support."}</p>
      </div>
      <dl>
        <div><dt>Clause phrase coverage</dt><dd>{supportRate}%</dd></div>
        <div><dt>Material clauses audited</dt><dd>{assurance ? `${assurance.audited_material_sentence_count}/${assurance.material_sentence_count}` : `${findings.length}/${findings.length}`}</dd></div>
        <div><dt>Critical failures</dt><dd>{assurance?.critical_failure_count ?? findings.filter((finding) => finding.critical && finding.status !== "supported").length}</dd></div>
        <div><dt>Currently citation-eligible</dt><dd>{currentCitationEligibleCount}/{evidence.length}</dd></div>
      </dl>
    </section>

    {historicalDiffers && <section className="citation-history-notice">
      <div><span>HISTORICAL AUDIT PRESERVED</span><h3>The earlier packet passed, but it is not the current publication authority.</h3></div>
      <dl>
        <div><dt>Historical status</dt><dd>{titleCase(historicalAssurance?.publication_status ?? "not recorded")}</dd></div>
        <div><dt>Historical support</dt><dd>{Math.round((historicalAssurance?.final_audit.full_support_rate ?? 0) * 100)}%</dd></div>
        <div><dt>Current status</dt><dd>{titleCase(publicationStatus)}</dd></div>
      </dl>
    </section>}

    <section className="citation-metrics" aria-label="Citation audit status summary">
      <article><span>SUPPORTED CLAUSES</span><strong>{supportedCount}</strong><small>Eligible passage with required lexical match</small></article>
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
              <b>Material clause {assertionNumber}</b>
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
              <div><dt>Attached references</dt><dd>{citationIds.length}</dd></div>
              <div><dt>Eligible references</dt><dd>{citationIds.filter((id) => integrityByEvidence.get(id)?.citation_eligible === true).length}</dd></div>
              <div><dt>Audit authority</dt><dd>{usingEffectiveAssurance ? "Effective packet" : "Historical fallback"}</dd></div>
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
              : finding.status === "out_of_packet"
                ? <b>Not evaluated — citation eligibility failed first.</b>
                : <b>None</b>}</section>
          </div>}

          <div className="citation-mappings">
            <div className="citation-subhead"><span>CITATION-TO-PASSAGE MAPPING</span><b>{citationIds.length} reference{citationIds.length === 1 ? "" : "s"}</b></div>
            {citationIds.map((evidenceId) => {
              const record = evidence.find((item) => item.evidence_id === evidenceId);
              const source = record ? sources.get(record.source_id) : null;
              const link = linkByEvidence.get(evidenceId);
              const integrity = integrityByEvidence.get(evidenceId);
              return <details key={evidenceId}>
                <summary>
                  <span>{shortId(evidenceId)}</span>
                  <b>{source?.publisher ?? source?.title ?? "Evidence record unavailable"}</b>
                  <em>{integrity?.citation_eligible === true ? "Eligible" : "Ineligible"} · {titleCase(canonicalStance(link?.stance ?? record?.stance ?? "unknown"))}</em>
                </summary>
                <div>
                  {link?.matched_phrases.length ? <section className="matched-phrases"><span>MATCHED PHRASES</span>{link.matched_phrases.map((phrase) => <mark key={phrase}>{phrase}</mark>)}</section> : <p className="no-match">No required phrase match was recorded for this citation.</p>}
                  <blockquote>“{link?.passage ?? record?.passage ?? "The cited passage is not available in this report."}”</blockquote>
                  <dl>
                    <div><dt>Source type</dt><dd>{titleCase(source?.source_type ?? "unknown")}</dd></div>
                    <div><dt>Evidence family</dt><dd>{record?.evidence_family_id ? shortId(record.evidence_family_id) : "Unassigned"}</dd></div>
                    <div><dt>Approved use</dt><dd>{titleCase(record?.evidentiary_use ?? "not recorded")}</dd></div>
                    <div><dt>Current citation eligibility</dt><dd>{integrity?.citation_eligible === true ? "Eligible" : "Ineligible"}</dd></div>
                    <div><dt>Effective packet status</dt><dd>{assurance?.final_audit.approved_evidence_ids.includes(evidenceId) === false ? "Outside effective packet" : "Included"}</dd></div>
                  </dl>
                  {integrity?.citation_eligible === false && <p className="citation-integrity-warning">Current blocker: {integrity.reason_codes.map(titleCase).join(" · ") || "Evidence is not citation eligible."}</p>}
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
        <section><b>What it checks</b><p>Each material report clause must link to currently citation-eligible evidence with the required wording and expected evidence stance. Critical failures and phrase coverage below 95% block publication.</p></section>
        <section><b>What it does not prove</b><p>Clause phrase coverage is lexical. It does not establish semantic entailment, correctness, authority, independence, or contextual completeness. Those safeguards are evaluated separately.</p></section>
        <section><b>Revision boundary</b><p>Bounded revision may narrow unsupported wording to an approved passage. It cannot add assertions, introduce unapproved evidence, or change the verdict label.</p></section>
      </div>
    </details>
  </div>;
}

function ReviewHistoryView({ review }: { review: ReviewHistory | null }) {
  if (!review) return <p className="empty-copy">Start a review workflow to create an immutable history.</p>;
  const status = review.decisions.length ? "Decision recorded" : "Awaiting decision";
  const eventDetail = (event: ReviewHistory["events"][number]) => {
    const finding = review.findings.find((item) => item.finding_id === event.entity_id);
    const decision = review.decisions.find((item) => item.record_id === event.entity_id || item.decision_id === event.entity_id);
    const approval = review.approvals.find((item) => item.approval_id === event.entity_id);
    const revision = review.revisions.find((item) => item.revision_id === event.entity_id);
    if (finding) return finding.summary;
    if (decision) return `${titleCase(decision.kind)} · ${decision.rationale}`;
    if (approval) return `${titleCase(approval.decision)} · ${approval.rationale}`;
    if (revision) return `${titleCase(revision.original_verdict)} → ${titleCase(revision.revised_verdict)} · ${revision.rationale}`;
    return event.action === "request_created" ? review.request.reason : "Immutable review event recorded.";
  };
  return <div className="review-history-workspace">
    <section className="review-history-summary">
      <article><span>STATUS</span><strong>{status}</strong><small>{review.decisions.length ? `${review.decisions.length} reviewer decision(s)` : "No reviewer decision recorded"}</small></article>
      <article><span>FINDINGS</span><strong>{review.findings.length}</strong><small>Persisted review findings</small></article>
      <article><span>APPROVALS</span><strong>{review.approvals.length}</strong><small>Distinct approval records</small></article>
      <article className={review.chain_valid ? "chain-valid" : "chain-invalid"}><span>AUDIT CHAIN</span><strong>{review.chain_valid ? "Verified" : "Invalid"}</strong><small>Append-only hash continuity</small></article>
    </section>

    <section className="review-request-brief">
      <div><span>REVIEW REQUEST</span><h3>{review.request.reason}</h3></div>
      <dl>
        <div><dt>Requested by</dt><dd>{review.request.created_by}</dd></div>
        <div><dt>Created</dt><dd>{new Date(review.request.created_at).toLocaleString()}</dd></div>
        <div><dt>Request ID</dt><dd>{shortId(review.request.request_id)}</dd></div>
        <div><dt>Graph thread</dt><dd>{review.request.graph_thread_id}</dd></div>
      </dl>
    </section>

    <section className="review-event-section">
      <div className="review-history-heading"><span>IMMUTABLE EVENT TIMELINE</span><b>{review.events.length} event{review.events.length === 1 ? "" : "s"}</b></div>
      <div className="review-event-timeline">{review.events.map((event) => <article key={event.sequence}>
        <i>{event.sequence}</i>
        <div><header><b>{titleCase(event.action)}</b><time>{new Date(event.occurred_at).toLocaleString()}</time></header><p>{eventDetail(event)}</p><small>{event.actor_identity} · entity {shortId(event.entity_id)} · hash {event.event_hash.slice(0, 12)}…</small></div>
      </article>)}</div>
    </section>

    {review.findings.length > 0 && <section className="review-record-section"><div className="review-history-heading"><span>REVIEW FINDINGS</span><b>{review.findings.length}</b></div>{review.findings.map((finding) => <article key={finding.finding_id}><div><b>{titleCase(finding.kind)}</b><p>{finding.summary}</p></div><small>{finding.recorded_by} · {new Date(finding.created_at).toLocaleString()} · {finding.evidence_ids.length} evidence link(s)</small></article>)}</section>}
    {review.decisions.length > 0 && <section className="review-record-section"><div className="review-history-heading"><span>REVIEWER DECISIONS</span><b>{review.decisions.length}</b></div>{review.decisions.map((decision) => <article key={decision.record_id}><div><b>{titleCase(decision.kind)}{decision.proposed_verdict ? ` · ${titleCase(decision.proposed_verdict)}` : ""}</b><p>{decision.rationale}</p></div><small>{decision.reviewer_identity} · {new Date(decision.created_at).toLocaleString()} · decision {shortId(decision.decision_id)}</small></article>)}</section>}
    {review.approvals.length > 0 && <section className="review-record-section"><div className="review-history-heading"><span>DISTINCT APPROVALS</span><b>{review.approvals.length}</b></div>{review.approvals.map((approval) => <article key={approval.approval_id}><div><b>{titleCase(approval.decision)}</b><p>{approval.rationale}</p></div><small>{approval.approver_identity} · {new Date(approval.created_at).toLocaleString()}</small></article>)}</section>}
    {review.revisions.length > 0 && <section className="review-record-section"><div className="review-history-heading"><span>VERDICT REVISIONS</span><b>{review.revisions.length}</b></div>{review.revisions.map((revision) => <article key={revision.revision_id}><div><b>{titleCase(revision.original_verdict)} → {titleCase(revision.revised_verdict)}</b><p>{revision.rationale}</p></div><small>{titleCase(revision.change_kind)} · {new Date(revision.created_at).toLocaleString()}</small></article>)}</section>}
  </div>;
}

function SystemArchitectureView({
  apiStatus,
  job,
  graph,
  report,
  review,
  observedCost,
  observedTokens,
  costScope,
  externalSearchPricing,
}: {
  apiStatus: ApiStatus | null;
  job: AuthoritativeJob | null;
  graph: GraphSnapshot | null;
  report: Report;
  review: ReviewHistory | null;
  observedCost: number;
  observedTokens: number;
  costScope: string;
  externalSearchPricing: boolean;
}) {
  const runtime = job?.graph;
  const completed = new Set(graph?.completed_nodes ?? runtime?.completed_operations ?? []);
  const activePhase = runtime?.phase ?? null;
  const activeIndex = activePhase ? graphOrder.indexOf(activePhase as typeof graphOrder[number]) : -1;
  const roles = Array.from(new Set(runtime?.assignments.map((item) => titleCase(item.role)) ?? []));
  const integrityBlockers = (report.evidence_integrity ?? []).filter((item) => item.publication_blocking).length;
  const citationStatus = report.effective_full_report_assurance?.publication_status
    ?? report.full_report_assurance?.publication_status
    ?? "not recorded";
  const phaseState = (phase: typeof graphOrder[number], index: number) => (
    completed.has(phase) || activeIndex > index ? "done" : activePhase === phase ? "active" : "pending"
  );
  return <div className="architecture-dashboard">
    <section className="architecture-hero">
      <span>ACCEPTED ARCHITECTURE · ADR 0021</span>
      <h2>One durable graph coordinates the lifecycle. Domain authority stays explicit.</h2>
      <p>The durable workflow controls sequencing, interruption and recovery. InvestigationService owns evidence-changing domain operations. Specialist agents can propose research results, but cannot approve evidence, set policy, or publish a report.</p>
    </section>

    <section className="architecture-runtime" aria-label="Current runtime configuration">
      <article><span>ORCHESTRATOR</span><strong>{providerLabel(apiStatus?.orchestrator)}</strong><small>{apiStatus?.orchestrator === "langgraph" ? "Promoted path active" : "Rollback or alternate path active"}</small></article>
      <article><span>DOMAIN AUTHORITY</span><strong>{apiStatus?.authoritative_service ?? "Not reported"}</strong><small>Typed operations and persistence</small></article>
      <article><span>RETRIEVAL</span><strong>{providerLabel(apiStatus?.retrieval_provider)}</strong><small>{apiStatus?.live_research ? "Live research enabled" : "Fixture or offline mode"}</small></article>
      <article><span>MODEL</span><strong>{providerLabel(apiStatus?.model_provider)}</strong><small>Provider recorded by API</small></article>
      <article><span>CHECKPOINT</span><strong>{runtime ? `#${runtime.checkpoint_sequence}` : "Not loaded"}</strong><small>{activePhase ? titleCase(activePhase) : "No live thread in browser"}</small></article>
    </section>

    <section className="architecture-lifecycle">
      <div className="architecture-section-heading"><div><span>AUTHORITATIVE LIFECYCLE</span><h3>One checkpointed investigation thread</h3></div><p>Green nodes are persisted. The active node may interrupt for review without replaying completed or paid operations.</p></div>
      <ol>{graphOrder.map((phase, index) => {
        const state = phaseState(phase, index);
        return <li className={state} key={phase}><i>{state === "done" ? "✓" : index + 1}</i><b>{graphLabels[phase]}</b><small>{state === "done" ? "Persisted" : state === "active" ? "Active" : "Pending"}</small></li>;
      })}</ol>
    </section>

    <section className="architecture-flow" aria-label="Authority and data flow">
      <div className="architecture-section-heading"><div><span>AUTHORITY AND DATA FLOW</span><h3>What can change authoritative state</h3></div><p>Every arrow crosses a typed contract; only the domain-operation boundary can persist evidence or judgment artifacts.</p></div>
      <div className="architecture-flow-grid">
        <article><i>1</i><span>CONTROL PLANE</span><h4>Workflow coordinator</h4><p>Routes work, checkpoints state, enforces budgets, interrupts and resumes.</p><b>Cannot invent or approve evidence</b></article>
        <article><i>2</i><span>RESEARCH PLANE</span><h4>Bounded specialist agents</h4><p>{roles.length ? roles.join(" · ") : "Primary · general · academic · fact-check · challenger"}</p><b>{runtime?.assignments.length ?? 0} assignments · {runtime?.research_results.length ?? 0} results</b></article>
        <article><i>3</i><span>DOMAIN PLANE</span><h4>InvestigationService operations</h4><p>Normalizes, validates, deduplicates and persists approved domain artifacts.</p><b>{runtime?.artifacts.length ?? 0} graph artifact references</b></article>
        <article><i>4</i><span>ASSURANCE PLANE</span><h4>Verification, arguments and citation policy</h4><p>Deterministic gates reconcile evidence into a bounded judgment and publication decision.</p><b>{integrityBlockers} evidence blockers · citation {titleCase(citationStatus)}</b></article>
        <article><i>5</i><span>HUMAN AUTHORITY</span><h4>Append-only review ledger</h4><p>Reviewers request evidence, revise or reject; distinct approval is recorded when required.</p><b>{review?.events.length ?? 0} events · chain {review?.chain_valid ? "verified" : review ? "invalid" : "not loaded"}</b></article>
        <article><i>6</i><span>PUBLICATION PLANE</span><h4>Final report gate</h4><p>Publication is allowed only after evidence, verification, citation and review safeguards agree.</p><b>{titleCase(job?.publication_status ?? report.publication_decision?.status ?? "report state recorded")}</b></article>
      </div>
    </section>

    <section className="architecture-observability">
      <div><span>CURRENT INVESTIGATION ENVELOPE</span><dl>
        <div><dt>Components / requirements</dt><dd>{runtime?.components.length ?? 0} / {runtime?.requirements.length ?? 0}</dd></div>
        <div><dt>Evidence / families</dt><dd>{report.evidence.length} / {runtime?.evidence_families.length ?? new Set(report.evidence.map((item) => item.evidence_family_id).filter(Boolean)).size}</dd></div>
        <div><dt>Unresolved questions</dt><dd>{runtime?.unresolved_questions.length ?? 0}</dd></div>
        <div><dt>Publication blockers</dt><dd>{runtime?.publication_blocking_reasons.length ?? report.publication_decision?.blocking_reasons.length ?? 0}</dd></div>
      </dl></div>
      <div><span>GRAPH BUDGET COUNTERS</span><dl>
        <div><dt>Rounds</dt><dd>{runtime ? `${runtime.consumption.completed_rounds} / ${runtime.budget.maximum_rounds}` : "Not loaded"}</dd></div>
        <div><dt>Search calls</dt><dd>{runtime ? `${runtime.consumption.search_calls} / ${runtime.budget.maximum_search_calls}` : "Not loaded"}</dd></div>
        <div><dt>Model calls</dt><dd>{runtime ? `${runtime.consumption.model_calls} / ${runtime.budget.maximum_model_calls}` : "Not loaded"}</dd></div>
        <div><dt>Graph-attributed cost</dt><dd>{runtime ? `$${runtime.consumption.estimated_cost_usd.toFixed(6)}${runtime.budget.maximum_cost_usd > 0 ? ` / $${runtime.budget.maximum_cost_usd.toFixed(2)}` : " · no monetary cap recorded"}` : "Not loaded"}</dd></div>
      </dl></div>
      <div><span>OBSERVED COST ACCOUNTING</span><dl>
        <div><dt>Scope</dt><dd>{titleCase(costScope)}</dd></div>
        <div><dt>Observed model cost</dt><dd>${observedCost.toFixed(6)}</dd></div>
        <div><dt>Observed model tokens</dt><dd>{Math.round(observedTokens).toLocaleString()}</dd></div>
        <div><dt>Search pricing</dt><dd>{externalSearchPricing ? "External SerpAPI plan" : "$0 API fee recorded"}</dd></div>
      </dl><p className="architecture-accounting-note">Graph counters describe the loaded durable thread. Observed cost uses the same scope as the dashboard header and may cover the API process when job-specific receipts are not loaded.</p></div>
      <div><span>RECOVERY GUARANTEES</span><ul><li>SQLite-backed graph checkpoints</li><li>Receipt-protected paid operations</li><li>Idempotent resume after restart</li><li>Direct sequential rollback retained</li></ul></div>
    </section>

    <section className="architecture-authority-table">
      <div className="architecture-section-heading"><div><span>CAPABILITY BOUNDARIES</span><h3>Who is allowed to do what</h3></div></div>
      <div role="table" aria-label="Architecture capability boundaries">
        <div role="row" className="heading"><b role="columnheader">Component</b><b role="columnheader">May do</b><b role="columnheader">May not do</b><b role="columnheader">Durable output</b></div>
        <div role="row"><strong role="cell">Workflow coordinator</strong><span role="cell">Route, checkpoint, interrupt, resume</span><span role="cell">Change evidence or verdict semantics directly</span><span role="cell">Versioned workflow state</span></div>
        <div role="row"><strong role="cell">Research agents</strong><span role="cell">Search assigned requirements and return typed candidates</span><span role="cell">Approve evidence, bypass retrieval, or publish</span><span role="cell">Assignments and research results</span></div>
        <div role="row"><strong role="cell">InvestigationService</strong><span role="cell">Execute authoritative domain operations</span><span role="cell">Bypass validators, policy or persistence contracts</span><span role="cell">Evidence, ledgers, verdict and report artifacts</span></div>
        <div role="row"><strong role="cell">Human review</strong><span role="cell">Approve when eligible, revise, request evidence or reject</span><span role="cell">Silently rewrite prior events or approve blocked evidence</span><span role="cell">Hash-chained decisions and approvals</span></div>
      </div>
    </section>

    <section className="trust-boundary">
      <div><span>WHAT THE PROMOTION PROVES</span><p>Workflow equivalence, durable recovery, citation enforcement, review continuity and challenger coverage within the measured local envelope.</p></div>
      <div><span>WHAT IT DOES NOT CLAIM</span><p>Calibrated autonomous factual accuracy, unbounded distributed scale, or permission to publish unsupported critical assertions.</p></div>
    </section>
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
  packetReferenced,
  currentEligible,
  openEvidence,
}: {
  evidenceId: string;
  evidence: Evidence[];
  sources: Map<string, Source>;
  packetReferenced: string[];
  currentEligible: string[];
  openEvidence: (evidenceId: string) => void;
}) {
  const record = evidence.find((item) => item.evidence_id === evidenceId);
  const source = record ? sources.get(record.source_id) : null;
  return <details className="verification-evidence">
    <summary>
      <span>{shortId(evidenceId)}</span>
      <b>{source?.publisher ?? source?.title ?? "Evidence record unavailable"}</b>
      <em>{currentEligible.includes(evidenceId) ? "Currently eligible" : packetReferenced.includes(evidenceId) ? "Historical packet reference" : "Outside packet"}</em>
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
  const integrity = report.evidence_integrity ?? [];
  const eligibilityAssessed = integrity.length > 0;
  const currentEligibleEvidenceIds = integrity
    .filter((item) => item.argument_eligible === true)
    .map((item) => item.evidence_id);
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
  const scopeFindingCodes = new Set(["absolute_wording_requires_verification"]);
  const legacyNumericalFindings = report.context_verification?.numerical.findings ?? [];
  const scopeFindings = [
    ...(report.context_verification?.scope_findings ?? []),
    ...legacyNumericalFindings.filter((finding) => scopeFindingCodes.has(finding.code)),
  ].filter((finding, index, values) => (
    values.findIndex((item) => item.code === finding.code && item.message === finding.message) === index
  ));
  const allFindings = [
    ...(packet?.findings ?? []),
    ...numerical.flatMap((item) => item.findings ?? []),
    ...temporal.flatMap((item) => item.findings ?? []),
    ...legacyNumericalFindings.filter((finding) => !scopeFindingCodes.has(finding.code)),
    ...(report.context_verification?.temporal.findings ?? []),
  ].filter((finding, index, values) => (
    values.findIndex((item) => item.code === finding.code && item.message === finding.message) === index
  ));
  const blockingFindings = allFindings.filter((finding) => finding.severity === "blocking");
  const readinessImpact = !verificationRequired
    ? "Not applicable"
    : blockingFindings.some((finding) => finding.readiness_impact === "publication_block")
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
        <div><dt>Current evidence authority</dt><dd>{eligibilityAssessed ? `${currentEligibleEvidenceIds.length} eligible / ${evidence.length} retained` : `${evidence.length} retained · eligibility not assessed`}</dd></div>
        <div><dt>Completeness</dt><dd>{assertions.length ? `${Math.round(completed / assertions.length * 100)}%` : verificationRequired ? "0%" : "N/A"}</dd></div>
      </dl>
    </section>

    {scopeFindings.length > 0 && <section className="verification-findings scope-review-findings">
      <div><span>CLAIM-SCOPE REVIEW SIGNALS</span><b>{scopeFindings.length} semantic</b></div>
      {scopeFindings.map((finding) => <article className={`severity-${finding.severity}`} key={`${finding.code}:${finding.message}`}>
        <em>SCOPE</em>
        <div><b>Universal wording review recommended</b><p>{finding.message.replace("Absolute wording requires explicit verification", "Universal wording requires claim-scope review")}</p><small><strong>How to resolve:</strong> {finding.recommended_action}</small></div>
        <span>Not a numerical or temporal check</span>
      </article>)}
    </section>}

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
            <div><dt>Expected structure</dt><dd>Relation, reference date, effective interval and currently eligible evidence binding</dd></div>
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
        <li className={assertions.length ? "complete" : "skipped"}><i>3</i><div><b>Evidence binding</b><small>{assertions.length ? "Verification packet references recorded; current eligibility shown separately" : "Skipped because no typed assertion existed"}</small></div></li>
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
          {item.evidence_ids.length > 0 && <section className="verification-evidence-list"><span>VERIFICATION EVIDENCE REFERENCES</span>{item.evidence_ids.map((id) => <VerificationEvidenceTrace key={id} evidenceId={id} evidence={evidence} sources={sources} packetReferenced={packet?.approved_evidence_ids ?? []} currentEligible={currentEligibleEvidenceIds} openEvidence={openEvidence} />)}</section>}
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
                <VerificationEvidenceTrace evidenceId={observation.evidence_id} evidence={evidence} sources={sources} packetReferenced={packet?.approved_evidence_ids ?? []} currentEligible={currentEligibleEvidenceIds} openEvidence={openEvidence} />
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
            <div><dt>Claim numerical operands</dt><dd>{context.numerical.claim_observations.length}</dd></div>
            <div><dt>Evidence tokens</dt><dd>{context.numerical.evidence_observations.length}</dd></div>
            <div><dt>Scope qualifiers detected</dt><dd>{context.numerical.exactness_terms.join(", ") || "None"}</dd></div>
          </dl>
          <div className="value-observations">{context.numerical.claim_observations.map((observation, index) => <article key={`claim:${index}`}><b>{observation.raw_text}</b><span>Claim · {observation.unit_hint ?? "unit unknown"}</span><small>{observation.start_char == null ? "Offset unavailable" : `Characters ${observation.start_char}–${observation.end_char}`}</small></article>)}</div>
          {!context.numerical.claim_observations.length && <p>{numericalRequired ? "No explicit claim operand was extracted. A required numerical check cannot pass on evidence numbers alone." : "No numerical operand was expected because numerical verification was not required."}</p>}
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
        <section><b>Verified is narrow</b><p>It means the typed comparator, values or dates, currently eligible evidence, and bounded calculation agree. It is not a general truth score.</p></section>
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
    status: value.job.status === "interrupted"
      ? "review_required"
      : value.job.status === "completed" && value.publication_status !== "published"
        ? value.publication_status
        : value.graph.phase,
    authoritative_verdict: value.verdict ?? value.interruption?.provisional_verdict ?? "unverifiable",
    final_verdict: value.graph.phase === "complete" ? value.verdict : null,
    completed_nodes: [...completed],
    applied_decision_id: value.review?.decisions.at(-1)?.decision_id ?? null,
    reviewer_identity: value.review?.decisions.at(-1)?.reviewer_identity ?? null,
  };
};

function EvidenceWorkspace({ report, sources, selectedIndex, onSelect, openSocial, openReview, prepareFreshInvestigation, recordDisposition: persistDisposition, dispositionBusy, reviewerIdentity, approverIdentity, onReviewerIdentityChange, onApproverIdentityChange }: {
  report: Report; sources: Map<string, Source>; selectedIndex: number;
  onSelect: (index: number) => void; openSocial: () => void; openReview: () => void;
  prepareFreshInvestigation: () => void;
  recordDisposition: (kind: EvidenceDisposition["kind"], approvedUse: string | null, reason: string) => Promise<boolean>;
  dispositionBusy: boolean;
  reviewerIdentity: string; approverIdentity: string;
  onReviewerIdentityChange: (value: string) => void; onApproverIdentityChange: (value: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [stance, setStance] = useState("all");
  const [hygiene, setHygiene] = useState("all");
  const [decisiveOnly, setDecisiveOnly] = useState(false);
  const [approvedUse, setApprovedUse] = useState("context");
  const [dispositionReason, setDispositionReason] = useState("");
  const [pendingDisposition, setPendingDisposition] = useState<{ kind: EvidenceDisposition["kind"]; approvedUse: string | null; reason: string } | null>(null);
  const [dispositionValidation, setDispositionValidation] = useState<string | null>(null);
  const [dispositionNotice, setDispositionNotice] = useState<string | null>(null);
  const integrity = new Map((report.evidence_integrity ?? []).map((item) => [item.evidence_id, item]));
  const verdictSelectedIds = new Set(report.verdict.decisive_evidence_ids);
  const decisiveIds = new Set(report.verdict.decisive_evidence_ids.filter(
    (evidenceId) => integrity.get(evidenceId)?.decisive_use_eligible !== false,
  ));
  const assessments = report.evidence.map((item) => integrity.get(item.evidence_id));
  const blockingCount = assessments.filter((item) => item?.publication_blocking).length;
  const contaminatedCount = assessments.filter((item) => item?.status === "contaminated").length;
  const cautionCount = assessments.filter((item) => item?.status === "caution").length;
  const warningCount = assessments.filter((item) => item && item.status !== "clean").length;
  const unspecifiedCount = assessments.filter((item) => item?.approved_use === "unspecified").length;
  const ineligibleVerdictCount = [...verdictSelectedIds].filter((item) => !decisiveIds.has(item)).length;
  const eligibleCount = assessments.filter((item) => item?.argument_eligible !== false).length;
  const sourceCount = new Set(report.evidence.map((item) => item.source_id)).size;
  const visible = report.evidence.map((item, index) => ({ item, index })).filter(({ item }) => {
    const source = sources.get(item.source_id);
    const assessment = integrity.get(item.evidence_id);
    const haystack = `${source?.title ?? ""} ${source?.publisher ?? ""} ${item.passage}`.toLocaleLowerCase();
    return (!query || haystack.includes(query.toLocaleLowerCase()))
      && (stance === "all" || canonicalStance(item.stance) === stance)
      && (hygiene === "all" || assessment?.status === hygiene)
      && (!decisiveOnly || decisiveIds.has(item.evidence_id));
  });
  const selected = report.evidence[selectedIndex] ?? visible[0]?.item ?? null;
  const selectedAssessment = selected ? integrity.get(selected.evidence_id) : undefined;
  const selectedSource = selected ? sources.get(selected.source_id) : undefined;
  const effectiveUse = selectedAssessment?.approved_use ?? selected?.evidentiary_use ?? "unspecified";
  const selectedDispositions = (report.evidence_dispositions ?? [])
    .filter((item) => item.evidence_id === selected?.evidence_id)
    .sort((left, right) => right.created_at.localeCompare(left.created_at));
  const quality = report.provenance?.source_quality.find((item) => item.source_id === selected?.source_id);
  const knownQuality = quality?.dimensions.filter((item) => item.finding !== "unknown") ?? [];
  const unknownQuality = quality?.dimensions.filter((item) => item.finding === "unknown") ?? [];
  const assertionSections = new Map(
    (report.full_report_assurance?.final_assertions ?? []).map((item) => [item.assertion_id, item.section]),
  );
  const citationSuppressed = selectedAssessment?.citation_eligible === false;
  const citationUsage = citationSuppressed ? [] : (report.full_report_assurance?.final_audit.findings ?? []).filter(
    (finding) => assertionSections.get(finding.assertion_id) !== "evidence_finding"
      && finding.links.some((link) => link.evidence_id === selected?.evidence_id),
  );
  const grouped = visible.reduce((groups, entry) => {
    const items = groups.get(entry.item.source_id) ?? [];
    items.push(entry); groups.set(entry.item.source_id, items); return groups;
  }, new Map<string, Array<{ item: Evidence; index: number }>>());
  const overlapLabel = (items: Array<{ item: Evidence; index: number }>) => {
    if (items.length < 2) return null;
    const termSets = items.map(({ item }) => new Set(
      (integrity.get(item.evidence_id)?.exact_quote ?? item.passage)
        .toLocaleLowerCase().match(/[a-z0-9]{3,}/g) ?? [],
    ));
    for (let left = 0; left < termSets.length; left += 1) {
      for (let right = left + 1; right < termSets.length; right += 1) {
        const intersection = [...termSets[left]].filter((term) => termSets[right].has(term)).length;
        const union = new Set([...termSets[left], ...termSets[right]]).size || 1;
        if (intersection / union >= 0.72) return "POSSIBLE DUPLICATE";
      }
    }
    return "RELATED PASSAGES · SAME SOURCE";
  };

  const stageDisposition = (kind: EvidenceDisposition["kind"], boundedUse: string | null) => {
    if (dispositionReason.trim().length < 3) {
      setDispositionValidation("Enter a specific review rationale of at least three characters.");
      return;
    }
    setDispositionValidation(null);
    setDispositionNotice(null);
    setPendingDisposition({ kind, approvedUse: boundedUse, reason: dispositionReason.trim() });
  };
  const recordDisposition = async (kind: EvidenceDisposition["kind"], boundedUse: string | null, reason: string) => {
    if (reason.trim().length < 3) {
      setDispositionValidation("Enter a specific review rationale of at least three characters.");
      return;
    }
    stageDisposition(kind, boundedUse);
  };
  const confirmDisposition = async () => {
    if (!pendingDisposition) return;
    if (reviewerIdentity.trim().length < 3 || approverIdentity.trim().length < 3) {
      setDispositionValidation("Record both the reviewer and distinct approver identities.");
      return;
    }
    if (reviewerIdentity.trim().toLocaleLowerCase() === approverIdentity.trim().toLocaleLowerCase()) {
      setDispositionValidation("The reviewer and distinct approver must be different people.");
      return;
    }
    const recorded = await persistDisposition(pendingDisposition.kind, pendingDisposition.approvedUse, pendingDisposition.reason);
    if (!recorded) return;
    const requestOnly = ["request_replacement", "request_reextraction"].includes(pendingDisposition.kind);
    setDispositionNotice(requestOnly
      ? "The follow-up request was recorded. It did not start research or extraction."
      : "The append-only evidence decision was recorded and the authoritative investigation state was refreshed.");
    setPendingDisposition(null);
    setDispositionReason("");
  };

  return <div className="evidence-workspace">
    <section className={`evidence-safety ${blockingCount ? "blocked" : warningCount || unspecifiedCount ? "caution" : "clean"}`}>
      <div><span>EVIDENCE INTEGRITY</span><h2>{report.evidence.length > 0 && eligibleCount === 0 ? "No eligible evidence remains" : blockingCount ? "Publication-blocking evidence issue" : warningCount || unspecifiedCount ? "Evidence needs inspection" : "Retained passages passed hygiene checks"}</h2><p>Passage relevance, source authority, independence, and publication eligibility are separate safeguards. A high relevance score never proves truth.</p></div>
      <dl><div><dt>Sources</dt><dd>{sourceCount}</dd></div><div><dt>Passages</dt><dd>{report.evidence.length}</dd></div><div><dt>Eligible</dt><dd>{eligibleCount}</dd></div><div><dt>Contaminated</dt><dd>{contaminatedCount}</dd></div><div><dt>Caution</dt><dd>{cautionCount}</dd></div><div><dt>Use unresolved</dt><dd>{unspecifiedCount}</dd><small>{ineligibleVerdictCount} verdict-selected ineligible</small></div></dl>
    </section>
    {report.evidence.length > 0 && eligibleCount === 0 && <section className="zero-eligible-actions"><div><span>INVESTIGATION ACTION REQUIRED</span><h3>The current packet cannot support publication.</h3><p>Record a disposition for a selected passage, request clean replacement evidence, or prepare a fresh investigation. These actions do not silently reuse an ineligible passage.</p></div><button onClick={openReview}>Review blocked draft</button><button onClick={prepareFreshInvestigation}>Prepare fresh investigation</button></section>}
    <section className="evidence-toolbar" aria-label="Evidence filters">
      <label>SEARCH<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Source, publisher, or passage" /></label>
      <label>STANCE<select value={stance} onChange={(event) => setStance(event.target.value)}><option value="all">All stances</option><option value="supports">Supports</option><option value="contradicts">Contradicts</option><option value="qualifies">Qualifies</option><option value="context">Context</option></select></label>
      <label>PASSAGE HYGIENE<select value={hygiene} onChange={(event) => setHygiene(event.target.value)}><option value="all">All states</option><option value="clean">Clean</option><option value="caution">Caution</option><option value="contaminated">Contaminated</option></select></label>
      <label className="evidence-checkbox"><input type="checkbox" checked={decisiveOnly} onChange={(event) => setDecisiveOnly(event.target.checked)} />Eligible decisive only</label>
      {(query || stance !== "all" || hygiene !== "all" || decisiveOnly) && <button className="clear-evidence-filters" onClick={() => { setQuery(""); setStance("all"); setHygiene("all"); setDecisiveOnly(false); }}>Clear filters · {visible.length} result{visible.length === 1 ? "" : "s"}</button>}
    </section>
    {dispositionValidation && !pendingDisposition && <p className="field-error disposition-feedback" role="alert">{dispositionValidation}</p>}
    {dispositionNotice && <p className="disposition-notice disposition-feedback" role="status">{dispositionNotice}</p>}
    <section className="evidence-layout">
      <div className="evidence-list">
        {[...grouped.entries()].map(([sourceId, items]) => {
          const source = sources.get(sourceId);
          const overlap = overlapLabel(items);
          return <section className="evidence-source-group" key={sourceId}>
            <header><span>{items.length} PASSAGE{items.length === 1 ? "" : "S"}{overlap ? ` · ${overlap}` : ""}</span><strong>{source?.publisher ?? source?.title ?? "Stored source"}</strong><small>{titleCase(source?.source_type ?? "unknown")} · {source?.canonical_url ? new URL(source.canonical_url).hostname : "domain unavailable"} · one origin family {items[0].item.evidence_family_id ? shortId(items[0].item.evidence_family_id!) : "unassigned"}</small></header>
            {items.map(({ item, index }) => {
              const assessment = integrity.get(item.evidence_id);
              return <button aria-pressed={selectedIndex === index} className={selectedIndex === index ? "evidence-item active" : "evidence-item"} onClick={() => onSelect(index)} key={item.evidence_id}>
                <div><span>{shortId(item.evidence_id)}{decisiveIds.has(item.evidence_id) ? " · DECISIVE" : verdictSelectedIds.has(item.evidence_id) ? " · VERDICT-SELECTED · INELIGIBLE" : ""}</span><b>{titleCase(canonicalStance(item.stance))}</b></div>
                <p>{assessment?.exact_quote ?? item.passage.slice(0, 360)}</p>
                <footer><em className={`hygiene-badge ${assessment?.status ?? "unknown"}`}>{titleCase(assessment?.status ?? "not assessed")}</em><small>{titleCase(item.evidentiary_use)}</small></footer>
              </button>;
            })}
          </section>;
        })}
        {!visible.length && <p className="empty-copy">No evidence matches these filters.</p>}
      </div>
      <article className="passage">
        {selected ? <>
          <div className="passage-meta"><span>{selectedAssessment?.citation_eligible === false ? "DIAGNOSTIC EXCERPT · NOT EVIDENCE" : selectedAssessment?.excerpt_status === "source_span_verified" ? "SOURCE-SPAN VERIFIED QUOTE" : "BEST MATCHING EXCERPT · NOT SPAN VERIFIED"}</span><b>{shortId(selected.evidence_id)}</b></div>
          {selectedAssessment && (selectedAssessment.status !== "clean" || effectiveUse === "unspecified" || selectedAssessment.disposition_kind) && <div className={`integrity-alert consolidated ${selectedAssessment.publication_blocking ? "blocked" : "caution"}`}><b>{selectedAssessment.publication_blocking ? "Publication blocked by this evidence item" : "Evidence item needs inspection"}</b><p>{selectedAssessment.reason_codes.map(titleCase).join(" · ") || "A deterministic evidence warning was recorded."}</p>{selectedAssessment.matched_fragments.length > 0 && <small>Detected page chrome: {selectedAssessment.matched_fragments.join(", ")}</small>}{selectedAssessment.disposition_kind && <p className="persisted-disposition"><b>Latest persisted decision:</b> {titleCase(selectedAssessment.disposition_kind)} · {selectedAssessment.disposition_reason}</p>}<div className="disposition-editor"><label>APPROVED USE<select value={approvedUse} onChange={(event) => setApprovedUse(event.target.value)}><option value="decisive">Decisive</option><option value="qualified_observation">Qualified observation</option><option value="attributed_statement">Attributed statement</option><option value="context">Context only</option></select></label><label>REVIEW RATIONALE<input value={dispositionReason} onChange={(event) => setDispositionReason(event.target.value)} /></label><div className="remediation-actions"><button className="primary" disabled={dispositionBusy} onClick={() => void recordDisposition("approve_use", approvedUse, dispositionReason)}>Approve bounded use</button><button disabled={dispositionBusy} onClick={() => void recordDisposition("exclude", null, dispositionReason)}>Exclude passage</button><button disabled={dispositionBusy} onClick={() => void recordDisposition("request_replacement", null, dispositionReason)}>Request replacement</button><button disabled={dispositionBusy} onClick={() => void recordDisposition("request_reextraction", null, dispositionReason)}>Request re-extraction</button></div></div><div className="remediation-actions secondary-row">{selectedSource?.url && <a href={selectedSource.url} target="_blank" rel="noreferrer">Open original source ↗</a>}<button onClick={() => { const raw = document.querySelector<HTMLDetailsElement>("#raw-evidence-capture"); if (raw) { raw.open = true; raw.scrollIntoView({ behavior: "smooth", block: "center" }); } }}>Inspect stored capture</button><button onClick={openReview}>Open review brief</button></div><small>Each decision is append-only and requires a distinct approver. It does not rewrite the retained passage or replay research.</small></div>}
          <blockquote>“{selectedAssessment?.exact_quote ?? selected.passage}”</blockquote>
          {(selectedAssessment?.context_before || selectedAssessment?.context_after) && <details className="quote-context"><summary>Show bounded surrounding context</summary>{selectedAssessment.context_before && <p><b>Before:</b> {selectedAssessment.context_before}</p>}{selectedAssessment.context_after && <p><b>After:</b> {selectedAssessment.context_after}</p>}</details>}
          <dl><div><dt>Source</dt><dd>{selectedSource?.url ? <a href={selectedSource.url} target="_blank" rel="noreferrer">{selectedSource.title ?? "Open source"} ↗</a> : selectedSource?.title ?? "Stored source"}</dd></div><div><dt>Publisher / author</dt><dd>{selectedSource?.publisher ?? "Not recorded"}{selectedSource?.author ? ` · ${selectedSource.author}` : ""}</dd></div><div><dt>Source type</dt><dd>{titleCase(selectedSource?.source_type ?? "unknown")}{selectedSource?.source_type === "other" && selectedSource.canonical_url ? ` · ${new URL(selectedSource.canonical_url).hostname}` : ""}</dd></div><div><dt>Published / retrieved</dt><dd>{selectedSource?.publication_date ?? "Not recorded"} / {selectedSource?.retrieved_at ? new Date(selectedSource.retrieved_at).toLocaleDateString() : "Not recorded"}</dd></div><div><dt>Extraction</dt><dd>{titleCase(selectedSource?.extraction_status ?? selected.extraction_status ?? "unknown")}</dd></div><div><dt>Effective approved use</dt><dd>{titleCase(effectiveUse)}{selectedAssessment?.disposition_kind ? " · persisted reviewer decision" : ""}</dd></div><div><dt>Stance</dt><dd>{titleCase(canonicalStance(selected.stance))}</dd></div><div><dt>Relevance <small className="metric-boundary">Topical match only</small></dt><dd>{Math.round(selected.relevance_score * 100)}%</dd></div><div><dt>Evidence family</dt><dd>{selected.evidence_family_id ? shortId(selected.evidence_family_id) : "Unassigned"}</dd></div><div><dt>Excerpt authority</dt><dd>{titleCase(selectedAssessment?.excerpt_status ?? "not assessed")}</dd></div><div><dt>Stored span</dt><dd>{selectedAssessment?.excerpt_start_char != null && selectedAssessment?.excerpt_end_char != null ? `${selectedAssessment.excerpt_start_char}–${selectedAssessment.excerpt_end_char}` : "Legacy / unavailable"}</dd></div></dl>
          {selectedDispositions.length > 0 && <details className="disposition-history"><summary>Evidence decision history · {selectedDispositions.length} record{selectedDispositions.length === 1 ? "" : "s"}</summary>{selectedDispositions.map((item) => <article key={item.disposition_id}><b>{titleCase(item.kind)}{item.approved_use ? ` · ${titleCase(item.approved_use)}` : ""}</b><p>{item.reason}</p><small>{item.reviewer_identity} · approved by {item.approver_identity} · {new Date(item.created_at).toLocaleString()}</small></article>)}</details>}
          <section className={`citation-usage ${citationSuppressed ? "suppressed" : ""}`}><span>MATERIAL REPORT SENTENCES USING THIS PASSAGE</span>{citationSuppressed ? <p>This passage is not citation-eligible. Any historical mapping is displayed only in the audit record and cannot satisfy report support.</p> : citationUsage.length ? citationUsage.map((finding) => <article key={finding.assertion_id}><b>{titleCase(finding.status)}</b><p>{finding.sentence}</p><small>{finding.explanation}</small></article>) : <p>No material final-report assertion cites this passage.</p>}</section>
          {quality && <details className="source-quality" open={selectedAssessment?.argument_eligible !== false}><summary>Additional source-quality diagnostics</summary><span>SOURCE-QUALITY ASSESSMENT</span>{knownQuality.map((dimension) => <div key={dimension.dimension}><b>{titleCase(dimension.dimension)}</b><em>{titleCase(dimension.finding)}</em><p>{dimension.reason}</p></div>)}{unknownQuality.length > 0 && <details><summary>{unknownQuality.length} dimension{unknownQuality.length === 1 ? "" : "s"} not assessed · insufficient source metadata</summary>{unknownQuality.map((dimension) => <div key={dimension.dimension}><b>{titleCase(dimension.dimension)}</b><p>{dimension.reason}</p></div>)}</details>}{quality.limitations.length > 0 && <small>Limitations: {quality.limitations.join(" · ")}</small>}</details>}
          <div className="score-explanation"><b>Relevance: {Math.round(selected.relevance_score * 100)}% topical match</b><p>This is not a correctness, authority, independence, or confidence score.</p></div>
          <details className="raw-capture" id="raw-evidence-capture"><summary>Compatibility diagnostic · stored raw capture (may contain page chrome)</summary><p>This historical capture is diagnostic only. Use the bounded excerpt and original source for review.</p><p>{selected.passage}</p></details>
          {selectedSource?.distribution_medium === "social_platform" && <div className="social-evidence-callout"><b>Social-source constraints apply</b><p>This item can only be used as {titleCase(selected.evidentiary_use)}.</p><button onClick={openSocial}>Open full social trace →</button></div>}
        </> : <p className="empty-copy">Select an evidence passage.</p>}
      </article>
    </section>
    {pendingDisposition && selected && <div className="confirmation-backdrop" onMouseDown={() => !dispositionBusy && setPendingDisposition(null)}>
      <section className="confirmation-dialog" role="dialog" aria-modal="true" aria-labelledby="evidence-disposition-title" onMouseDown={(event) => event.stopPropagation()}>
        <span>APPEND-ONLY EVIDENCE DECISION</span>
        <h2 id="evidence-disposition-title">Confirm {titleCase(pendingDisposition.kind)}</h2>
        <p>This decision will be added to the immutable review history for evidence <b>{shortId(selected.evidence_id)}</b> from <b>{selectedSource?.publisher ?? selectedSource?.title ?? "the stored source"}</b>.</p>
        {["request_replacement", "request_reextraction"].includes(pendingDisposition.kind) && <p className="request-boundary">This records a durable follow-up request. It does not start research or extraction, and the passage remains ineligible while the request is pending.</p>}
        <dl><div><dt>Approved use</dt><dd>{pendingDisposition.approvedUse ? titleCase(pendingDisposition.approvedUse) : "Not applicable"}</dd></div><div><dt>Rationale</dt><dd>{pendingDisposition.reason}</dd></div></dl>
        <div className="confirmation-identities"><label>Reviewer identity<input value={reviewerIdentity} onChange={(event) => onReviewerIdentityChange(event.target.value)} /></label><label>Distinct approver identity<input value={approverIdentity} onChange={(event) => onApproverIdentityChange(event.target.value)} /></label></div>
        {dispositionValidation && <p className="field-error" role="alert">{dispositionValidation}</p>}
        <div className="confirmation-actions"><button disabled={dispositionBusy} onClick={() => setPendingDisposition(null)}>Cancel</button><button className="primary" disabled={dispositionBusy} onClick={() => void confirmDisposition()}>{dispositionBusy ? "Recording…" : "Confirm durable decision"}</button></div>
      </section>
    </div>}
  </div>;
}

export default function Home() {
  const [apiBase, setApiBase] = useState(FALLBACK_API_ADDRESS);
  const [apiDraft, setApiDraft] = useState(FALLBACK_API_ADDRESS);
  const [apiInitialized, setApiInitialized] = useState(false);
  const [connectionState, setConnectionState] = useState<ConnectionState>("initializing");
  const [connectionMessage, setConnectionMessage] = useState("Resolving the local evidence API address.");
  const [connectionRetry, setConnectionRetry] = useState(0);
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
  const [rationale, setRationale] = useState("");
  const [reviewer, setReviewer] = useState("Md Moshiur Rahman");
  const [approver, setApprover] = useState("Md Rashedul Islam");
  const [busy, setBusy] = useState(false);
  const [activity, setActivity] = useState<"investigation" | "extraction" | "review" | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [job, setJob] = useState<AuthoritativeJob | null>(null);
  const [liveStage, setLiveStage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [apiStatus, setApiStatus] = useState<ApiStatus | null>(null);
  const [telemetry, setTelemetry] = useState<TelemetrySnapshot | null>(null);
  const [workspaceView, setWorkspaceView] = useState<WorkspaceView>("investigations");
  const [caseQuery, setCaseQuery] = useState("");
  const [reviewQueue, setReviewQueue] = useState<ReviewHistory[]>([]);
  const [reviewQueueQuery, setReviewQueueQuery] = useState("");
  const [reviewQueueFilter, setReviewQueueFilter] = useState<"pending" | "review" | "approval" | "complete" | "all">("pending");
  const [navigationLoading, setNavigationLoading] = useState(true);
  const [reviewQueueError, setReviewQueueError] = useState<string | null>(null);

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
    setConnectionState("connecting");
    setConnectionMessage(`Connecting to ${apiBase}…`);
    try {
      const [items, status] = await Promise.all([
        request<Investigation[]>("/api/investigations"),
        request<ApiStatus>("/health"),
      ]);
      setApiStatus(status);
      request<TelemetrySnapshot>("/api/operations/telemetry")
        .then(setTelemetry)
        .catch(() => setTelemetry(null));
      setInvestigations(items); setConnectionState("connected");
      setConnectionMessage(`Connected to ${apiBase}.`); setError(null);
    } catch {
      setConnectionState("unavailable");
      setConnectionMessage(`The evidence API could not be reached at ${apiBase}.`);
      setError(`The evidence API could not be reached at ${apiBase}.`);
    } finally { setNavigationLoading(false); }
  }, [apiBase, request]);

  const loadReviewQueue = useCallback(async () => {
    setReviewQueueError(null);
    try {
      const requests = await request<ReviewRequest[]>("/api/reviews");
      const histories = await Promise.all(requests.map((item) => request<ReviewHistory>(`/api/reviews/${item.request_id}`)));
      setReviewQueue(histories.sort((left, right) => right.request.created_at.localeCompare(left.request.created_at)));
    } catch (reason) {
      setReviewQueueError((reason as Error).message);
    }
  }, [request]);

  useEffect(() => {
    const configured = loadApiConfiguration(window.localStorage, window.location);
    const navigation = parseNavigationState(window.location.search);
    setApiBase(configured.address);
    setApiDraft(configured.address);
    setConnectionState(configured.warning ? "invalid" : "connecting");
    setConnectionMessage(configured.warning ?? `Connecting to ${configured.address}…`);
    setWorkspaceView(navigation.view);
    setSelectedId(navigation.investigationId);
    setApiInitialized(true);
  }, []);
  useEffect(() => {
    if (apiInitialized) void loadInvestigations();
  }, [apiInitialized, connectionRetry, loadInvestigations]);
  useEffect(() => {
    if (apiInitialized && connectionState === "connected") void loadReviewQueue();
  }, [apiInitialized, connectionState, loadReviewQueue]);
  useEffect(() => {
    const restore = () => {
      const navigation = parseNavigationState(window.location.search);
      setWorkspaceView(navigation.view); setSelectedId(navigation.investigationId);
    };
    window.addEventListener("popstate", restore);
    return () => window.removeEventListener("popstate", restore);
  }, []);
  useEffect(() => {
    if (!selectedId) { setReport(null); return; }
    void request<Report>(`/api/investigations/${selectedId}/report`)
      .then((value) => { setReport(value); setSelectedEvidence(0); setError(null); })
      .catch((reason: Error) => setError(reason.message));
    void request<AuthoritativeJob>(`/api/investigations/${selectedId}/authoritative-job`)
      .then((value) => {
        setJob(value);
        setGraph(authoritativeGraphSnapshot(value));
        setReview(value.review);
        setLiveStage(value.graph?.phase ?? null);
      })
      .catch(() => {
        setJob(null);
        setGraph(null);
        setReview(null);
      });
  }, [request, selectedId]);
  const jobActive = job != null && !["completed", "interrupted", "cancelled", "failed", "dead_letter"].includes(job.job.status);
  const jobFailed = job != null && ["failed", "dead_letter"].includes(job.job.status);
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
        const terminalOrPaused = ["completed", "interrupted", "cancelled", "failed", "dead_letter"].includes(restored.job.status);
        if (terminalOrPaused) {
          window.localStorage.removeItem("claim-polygraph-active-job");
          if (["failed", "dead_letter"].includes(restored.job.status)) {
            setJob(restored);
            setGraph(authoritativeGraphSnapshot(restored));
            setError(null);
          }
          return;
        }
        setJob(restored);
        setGraph(authoritativeGraphSnapshot(restored));
        setReview(restored.review);
      })
      .catch(() => window.localStorage.removeItem("claim-polygraph-active-job"));
  }, [request]);
  const jobStream = useDurableEventStream<AuthoritativeJob>({
    active: Boolean(job?.job.job_id && jobActive),
    url: job?.job.job_id
      ? `${apiBase}/api/authoritative-jobs/${job.job.job_id}/events`
      : null,
    cursorKey: `authoritative-job:${job?.job.job_id ?? "none"}`,
    eventNames: ["authoritative_state"],
    sequenceOf: (_eventName, state) => state.graph
      ? state.graph.checkpoint_sequence + 1
      : null,
    poll: () => request<AuthoritativeJob>(`/api/authoritative-jobs/${job!.job.job_id}`),
    terminal: (state) => ["completed", "interrupted", "cancelled", "failed", "dead_letter"].includes(state.job.status),
    onEvent: (_eventName, state) => {
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
          setError(["failed", "dead_letter"].includes(state.job.status) ? null : state.job.last_error);
          setActivity(null);
        }
      }
    },
  });
  const graphStream = useDurableEventStream<GraphSnapshot>({
    active: Boolean(graph?.thread_id && !jobActive && graph.status === "review_required"),
    url: graph?.thread_id ? `${apiBase}/api/graph-runs/${graph.thread_id}/events` : null,
    cursorKey: `graph:${graph?.thread_id ?? "none"}`,
    eventNames: ["graph_state"],
    sequenceOf: (_eventName, snapshot) => snapshot.completed_nodes.length,
    poll: () => request<GraphSnapshot>(`/api/graph-runs/${graph!.thread_id}`),
    terminal: (snapshot) => snapshot.status !== "review_required",
    onEvent: (_eventName, snapshot) => setGraph(snapshot),
  });

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
    ["request_evidence", "Request more evidence"],
    ["revise", "Revise verdict"],
    ["reject", "Reject packet"],
  ] as const;
  const effectiveCitationStatus = report?.effective_full_report_assurance?.publication_status
    ?? report?.full_report_assurance?.publication_status;
  const approvalBlockedByEvidence = Boolean(
    report
    && (
      effectiveCitationStatus === "blocked"
      || (report.evidence_integrity ?? []).some((item) => item.publication_blocking)
    ),
  );
  const serverAllowedReviewDecisions = job?.interruption?.allowed_decisions
    ?? reviewDecisionOptions.map(([value]) => value);
  const allowedReviewDecisions = reviewDecisionOptions
    .map(([value]) => value)
    .filter((value) => (
      serverAllowedReviewDecisions.includes(value)
      && (value !== "approve" || !approvalBlockedByEvidence)
    ));
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
  const contaminatedEvidence = (report?.evidence_integrity ?? []).filter(
    (item) => item.status !== "clean",
  );
  const citationReady = effectiveCitationStatus === "ready";
  const evidenceIntegrityBlocked = (report?.evidence_integrity ?? []).some(
    (item) => item.publication_blocking,
  );
  const overallPublicationReady = Boolean(
    report
    && report.publication_decision
    && report.publication_decision.publication_allowed
    && !evidenceIntegrityBlocked
  );
  const reviewerRecommendation = overallPublicationReady
    ? "Publish"
    : report?.social_evidence_policy?.publication_blocked
      ? "Do not publish"
      : "Request more evidence";
  const persistedLedger = report?.argument_ledger ?? null;
  const effectiveLedger = report?.effective_argument_ledger ?? persistedLedger;
  const ledgerArguments = effectiveLedger?.arguments ?? [];
  const ledgerPropositions = effectiveLedger?.propositions ?? [];
  const persistedLedgerArguments = persistedLedger?.arguments ?? [];
  const effectiveApprovedIds = new Set(effectiveLedger?.approved_evidence_ids ?? []);
  const integrityByEvidence = new Map(
    (report?.evidence_integrity ?? []).map((item) => [item.evidence_id, item]),
  );
  const argumentEligibleCount = evidence.filter(
    (item) => effectiveApprovedIds.has(item.evidence_id),
  ).length;
  const decisiveEligibleIds = new Set(
    report?.verdict.decisive_evidence_ids.filter(
      (id) => effectiveApprovedIds.has(id) && integrityByEvidence.get(id)?.decisive_use_eligible !== false,
    ) ?? [],
  );
  const historicalVerdictEvidenceIds = new Set(
    report?.verdict.decisive_evidence_ids.filter((id) => !decisiveEligibleIds.has(id)) ?? [],
  );
  const effectiveLedgerChanged = Boolean(
    persistedLedger && effectiveLedger
    && JSON.stringify(persistedLedger.arguments) !== JSON.stringify(effectiveLedger.arguments),
  );
  const aggregateLedger = ledgerArguments.reduce((totals, argument) => ({
    supporting: totals.supporting + argument.supporting_evidence_ids.length,
    contradictory: totals.contradictory + argument.contradictory_evidence_ids.length,
    qualifying: totals.qualifying + argument.qualifying_evidence_ids.length,
  }), { supporting: 0, contradictory: 0, qualifying: 0 });
  const groupDecisionEvidence = (identifiers: string[], argumentsForRoles: ArgumentLedgerPacket["arguments"]) => Array.from(identifiers.reduce((groups, evidenceId) => {
    const item = evidence.find((candidate) => candidate.evidence_id === evidenceId);
    if (!item) return groups;
    const source = sources.get(item.source_id);
    const groupKey = `${item.source_id}:${item.evidence_family_id ?? "unassigned"}`;
    const roles = argumentsForRoles.flatMap((argument) => [
      ...(argument.supporting_evidence_ids.includes(evidenceId) ? ["Supports proposition"] : []),
      ...(argument.contradictory_evidence_ids.includes(evidenceId) ? ["Contradicts proposition"] : []),
      ...(argument.qualifying_evidence_ids.includes(evidenceId) ? ["Qualifies proposition"] : []),
    ]);
    const existing = groups.get(groupKey) ?? { source, familyId: item.evidence_family_id, items: [] as Array<{ item: Evidence; roles: string[] }> };
    existing.items.push({ item, roles: [...new Set(roles.length ? roles : [titleCase(item.stance)])] });
    groups.set(groupKey, existing);
    return groups;
  }, new Map<string, { source: Source | undefined; familyId: string | null; items: Array<{ item: Evidence; roles: string[] }> }>()).values());
  const decisiveEvidenceGroups = groupDecisionEvidence([...decisiveEligibleIds], ledgerArguments);
  const historicalEvidenceGroups = groupDecisionEvidence(
    [...historicalVerdictEvidenceIds],
    persistedLedgerArguments,
  );
  const materialQuantifiers = [...new Set(report?.claim.text.match(/\b(?:almost all|all|always|never|every|exactly|only)\b/gi)?.map((term) => term.toLocaleLowerCase()) ?? [])];
  const candidateClaimClauses = report?.claim.text
    .split(/\b(?:although|while|whereas|but)\b/i)
    .map((clause) => clause.trim().replace(/^[,;]|[,;.]$/g, "").trim())
    .filter((clause) => clause.length >= 10) ?? [];
  const compoundCoverageWarning = candidateClaimClauses.length > 1
    && ledgerPropositions.length < candidateClaimClauses.length;
  const explanationText = `${report?.verdict.concise_explanation ?? ""} ${report?.verdict.detailed_reasoning ?? ""}`.toLocaleLowerCase();
  const unreflectedQuantifiers = materialQuantifiers.filter((term) => !explanationText.includes(term));

  async function submitClaim(event: FormEvent) {
    event.preventDefault();
    const submittedClaim = claim.trim();
    if (submittedClaim.length < 3) {
      setError("Enter a factual claim of at least three characters before starting an investigation.");
      return;
    }
    setError(null); setBusy(true);
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
      await investigateCandidate(submittedClaim);
    } catch (reason) { setError((reason as Error).message); } finally { setBusy(false); setActivity(null); }
  }

  async function investigateCandidate(selectedClaim: string) {
      const created = await request<AuthoritativeJob>("/api/authoritative-jobs", {
        method: "POST",
        body: JSON.stringify({ claim: selectedClaim, idempotency_key: `dashboard:${clientRequestId()}` }),
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

  function prepareFailedJobRetry() {
    if (!jobFailed || !job) return;
    const failedClaim = typeof job.job.spec.payload.claim === "string" ? job.job.spec.payload.claim : "";
    setClaim(failedClaim); setJob(null); setGraph(null); setReview(null); setLiveStage(null); setError(null);
    window.localStorage.removeItem("claim-polygraph-active-job");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function saveDecision() {
    if (!review || !job) return; setBusy(true); setActivity("review");
    try {
      if (effectiveDecisionKind === "approve" && approvalBlockedByEvidence) {
        throw new Error("Approval is unavailable until the current evidence and citation blockers are resolved.");
      }
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
    try {
      const normalized = saveApiConfiguration(window.localStorage, apiDraft);
      setApiBase(normalized); setApiDraft(normalized); setError(null);
      setConnectionState("connecting");
      setConnectionMessage(`Connecting to ${normalized}…`);
      setConnectionRetry((value) => value + 1);
    } catch (reason) {
      const message = reason instanceof ApiConfigurationError
        ? reason.message
        : "The API address is invalid.";
      setConnectionState("invalid"); setConnectionMessage(message); setError(message);
    }
  }

  async function recordEvidenceDisposition(
    kind: EvidenceDisposition["kind"],
    approvedUse: string | null,
    reason: string,
  ): Promise<boolean> {
    if (!report || !selected) return false;
    if (reason.trim().length < 3) {
      setError("Record a review rationale of at least three characters.");
      return false;
    }
    setBusy(true); setActivity("review");
    try {
      const investigationId = report.investigation.investigation_id;
      await request(`/api/investigations/${report.investigation.investigation_id}/evidence-dispositions`, {
        method: "POST",
        headers: { "X-Reviewer-Identity": reviewer },
        body: JSON.stringify({
          reviewer_identity: reviewer,
          approver_identity: approver,
          disposition: {
            evidence_id: selected.evidence_id,
            kind,
            approved_use: approvedUse,
            reason: reason.trim(),
          },
        }),
      });
      const [freshReport, freshJob, freshInvestigations] = await Promise.all([
        request<Report>(`/api/investigations/${investigationId}/report`),
        request<AuthoritativeJob>(`/api/investigations/${investigationId}/authoritative-job`),
        request<Investigation[]>("/api/investigations"),
      ]);
      setReport(freshReport);
      setJob(freshJob);
      setGraph(authoritativeGraphSnapshot(freshJob));
      setReview(freshJob.review);
      setLiveStage(freshJob.graph?.phase ?? null);
      setInvestigations(freshInvestigations);
      await loadReviewQueue();
      setError(null);
      return true;
    } catch (reasonValue) {
      setError((reasonValue as Error).message);
      return false;
    } finally {
      setBusy(false); setActivity(null);
    }
  }

  function resetApiAddress() {
    const inferred = resetApiConfiguration(window.localStorage, window.location);
    setApiBase(inferred); setApiDraft(inferred); setError(null);
    setConnectionState("connecting");
    setConnectionMessage(`Reset to the inferred local API at ${inferred}.`);
    setConnectionRetry((value) => value + 1);
  }

  const telemetryModelCost = telemetry?.metrics.find((metric) => metric.name === "model.cost_usd")?.total ?? 0;
  const telemetryModelTokens = telemetry?.metrics.find((metric) => metric.name === "model.tokens")?.total ?? 0;
  const selectedJobMatches = Boolean(job?.investigation_id && job.investigation_id === selectedId);
  const activeJobOwnsUsage = Boolean(job && jobActive);
  const scopedJobOwnsUsage = activeJobOwnsUsage || selectedJobMatches;
  const scopedJobConsumption = scopedJobOwnsUsage ? job?.graph?.consumption : null;
  const scopedJobUsage = scopedJobOwnsUsage ? job?.usage : null;
  const displayedCost = scopedJobUsage?.estimated_cost_usd ?? scopedJobConsumption?.estimated_cost_usd ?? (scopedJobOwnsUsage ? 0 : telemetryModelCost);
  const displayedTokens = scopedJobUsage?.total_tokens ?? scopedJobConsumption?.total_tokens ?? (scopedJobOwnsUsage ? 0 : telemetryModelTokens);
  const displayedModelCalls = scopedJobUsage?.model_calls ?? scopedJobConsumption?.model_calls ?? (scopedJobOwnsUsage ? 0 : null);
  const costScope = activeJobOwnsUsage ? "CURRENT JOB USAGE" : selectedJobMatches ? "CURRENT INVESTIGATION COST" : "API PROCESS TELEMETRY";
  const externalSearchPricing = apiStatus?.retrieval_provider?.startsWith("serpapi") ?? false;
  const connected = connectionState === "connected";
  const progressStream = jobActive ? jobStream : graphStream;
  const progressStatusLabel = titleCase(progressStream.status);
  const filteredInvestigations = investigations.filter((item) => `${item.input_claim} ${item.investigation_id}`.toLocaleLowerCase().includes(caseQuery.trim().toLocaleLowerCase()));
  const pendingReviews = reviewQueue.filter((item) => reviewStateOf(item) !== "complete");
  const visibleReviewQueue = reviewQueue.filter((history) => {
    const state = reviewStateOf(history);
    const investigation = investigations.find((item) => item.investigation_id === history.request.investigation_id);
    const searchable = `${investigation?.input_claim ?? ""} ${history.request.investigation_id} ${history.request.request_id} ${history.request.reason} ${reviewReasonLabel(history.request.reason)}`.toLocaleLowerCase();
    const matchesQuery = searchable.includes(reviewQueueQuery.trim().toLocaleLowerCase());
    const matchesFilter = reviewQueueFilter === "all" || reviewQueueFilter === "pending" && state !== "complete" || reviewQueueFilter === state;
    return matchesQuery && matchesFilter;
  });
  const navigateWorkspace = (view: WorkspaceView, investigationId: string | null = null) => {
    setWorkspaceView(view);
    if (investigationId !== null) setSelectedId(investigationId);
    window.history.pushState({}, "", serializeNavigationState({ view, investigationId: investigationId ?? (view === "investigations" ? selectedId : null) }));
  };
  const selectInvestigation = (investigationId: string, targetSection: typeof reportSections[number] = "Review brief") => {
    setSelectedId(investigationId); setGraph(null); setReview(null); setSection(targetSection);
    navigateWorkspace("investigations", investigationId);
  };

  return (
    <main className="app-shell">
      <a className="skip-link" href="#workspace-content">Skip to investigation workspace</a>
      <aside className="sidebar" aria-label="Claim Polygraph workspace">
        <div className="brand"><div className="brand-mark">CP</div><div><strong>Claim Polygraph</strong><span>Evidence console</span></div></div>
        <nav aria-label="Workspace navigation">
          <button aria-label="Investigations" title="Investigations" aria-current={workspaceView === "investigations" ? "page" : undefined} className={`nav-item ${workspaceView === "investigations" ? "selected" : ""}`} onClick={() => navigateWorkspace("investigations")}><span aria-hidden="true">◎</span>Investigations</button>
          <button aria-label={`Review queue${pendingReviews.length ? `, ${pendingReviews.length} pending` : ""}`} title="Review queue" aria-current={workspaceView === "review_queue" ? "page" : undefined} className={`nav-item ${workspaceView === "review_queue" ? "selected" : ""}`} onClick={() => navigateWorkspace("review_queue")}><span aria-hidden="true">◇</span>Review queue{pendingReviews.length > 0 && <b>{pendingReviews.length}</b>}</button>
          <a className="nav-item" aria-label="Verification annotation studio" title="Verification annotation studio" href="/annotation"><span aria-hidden="true">✓</span>V3 annotation</a>
          <button aria-label="System health" title="System health" aria-current={workspaceView === "system_health" ? "page" : undefined} className={`nav-item ${workspaceView === "system_health" ? "selected" : ""}`} onClick={() => navigateWorkspace("system_health")}><span aria-hidden="true">◌</span>System health</button>
        </nav>
        <div className="investigation-list">
          <span>RECENT CASES</span>
          <input className="case-search" aria-label="Search investigations" value={caseQuery} onChange={(event) => setCaseQuery(event.target.value)} placeholder="Search claims or IDs" />
          {navigationLoading ? <small className="sidebar-state">Loading cases…</small> : filteredInvestigations.length === 0 ? <small className="sidebar-state">{caseQuery ? "No matching cases" : "No investigations yet"}</small> : filteredInvestigations.slice().reverse().slice(0, 20).map((item) => (
            <button key={item.investigation_id} className={selectedId === item.investigation_id ? "case active" : "case"} onClick={() => selectInvestigation(item.investigation_id)}>
              <b>{shortId(item.investigation_id)}</b><small>{item.input_claim}</small>
            </button>
          ))}
        </div>
        <div className="phase-card"><span>{apiStatus?.orchestrator === "langgraph" ? "PROMOTED LOCAL DEFAULT" : "ROLLBACK / DIAGNOSTIC MODE"}</span><strong>{apiStatus?.orchestrator === "langgraph" ? "Authoritative workflow" : `${providerLabel(apiStatus?.orchestrator)} orchestrator`}</strong><div className="meter"><i /></div><small>{apiStatus?.live_research ? "Live web research enabled" : "Recorded fixture research"}</small><small>Authority · InvestigationService</small><small>Rollback · Direct composition retained</small></div>
        <div className="profile"><div className="avatar">MR</div><div><strong>Md Moshiur Rahman</strong><span>Reviewer</span></div><span className={connected ? "connection online" : "connection"}>{connected ? "LIVE" : titleCase(connectionState)}</span></div>
      </aside>

      <section className="workspace" id="workspace-content" tabIndex={-1} aria-busy={working}>
        <header className="topbar">
          <div><p>{workspaceView === "review_queue" ? "HUMAN-IN-THE-LOOP" : workspaceView === "system_health" ? "OPERATIONS" : report ? `INVESTIGATION · ${shortId(report.investigation.investigation_id)}` : "NEW INVESTIGATION"}</p><h1>{workspaceView === "review_queue" ? "Review queue" : workspaceView === "system_health" ? "System health" : report?.claim.text ?? "Investigate a factual claim"}</h1></div>
          {workspaceView === "review_queue" ? <div className="top-actions queue-top-actions"><div className="queue-count-chip"><span>AWAITING ACTION</span><strong>{pendingReviews.length}</strong><small>{reviewQueue.length} total review records</small></div><span className="status"><i /> Review workspace</span></div>
            : workspaceView === "system_health" ? <div className="top-actions"><span className={connected ? "status complete" : "status"}><i /> {titleCase(connectionState)}</span></div>
            : !report && !jobActive && !jobFailed ? <div className="top-actions"><span className={connected ? "status complete" : "status"}><i /> {connected ? "Ready to investigate" : titleCase(connectionState)}</span></div>
            : jobFailed ? <div className="top-actions"><span className="status failed"><i /> Earlier attempt stopped</span></div>
            : <div className="top-actions">
              <div className="cost-chip" aria-label="Temporary usage and cost estimate">
                <span>{costScope}</span>
                <strong>${displayedCost.toFixed(6)}</strong>
                <small>{Math.round(displayedTokens).toLocaleString()} model tokens{displayedModelCalls == null ? "" : ` across ${displayedModelCalls} structured call${displayedModelCalls === 1 ? "" : "s"}`} · {activeJobOwnsUsage ? "this submitted job only" : selectedJobMatches ? "this investigation only" : "all activity observed by this API process"} · {externalSearchPricing ? "search billed separately by SerpAPI plan" : "search $0 API fee"}{scopedJobUsage?.unpriced_model_calls ? ` · ${scopedJobUsage.unpriced_model_calls} unpriced call(s)` : ""}</small>
              </div>
              <span className={graph?.status === "complete" ? "status complete" : "status"}><i /> {graph ? titleCase(graph.status) : report ? titleCase(report.investigation.status) : "Ready"}</span>
              {report && <a className="ghost" href={`${apiBase}/api/investigations/${report.investigation.investigation_id}/report?format=${overallPublicationReady ? "markdown" : "provisional_markdown"}`} target="_blank" rel="noreferrer" aria-label={overallPublicationReady ? "Open publication-ready report" : "Open provisional report draft; publication is blocked"}>{overallPublicationReady ? "Export report" : "Download provisional draft"}</a>}
            </div>}
        </header>
        {workspaceView === "investigations" && !report && <section className="desk-intro">
          <div><span>CLAIM DESK</span><h2>Build a source-grounded fact check</h2><p>Enter one checkable claim or extract candidates from reporting material. The desk will search multiple evidence paths, challenge the initial interpretation, verify context, and prepare a provisional report for your review.</p></div>
          <ol><li><b>1</b><span>Investigate<small>Search and retrieve</small></span></li><li><b>2</b><span>Verify<small>Context and independence</small></span></li><li><b>3</b><span>Review<small>You make the decision</small></span></li></ol>
        </section>}

        {workspaceView === "investigations" && <details className={`new-investigation-panel ${report ? "compact" : "initial"}`} open={report ? undefined : true}>
          <summary>{report ? "Start another investigation" : "New investigation"}</summary>
          <form className="claim-bar" onSubmit={submitClaim} noValidate>
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
              <button type="submit" className="primary" disabled={busy || !connected || claim.trim().length < 3}>{busy && activity === "investigation" ? "Starting…" : busy && activity === "extraction" ? "Extracting…" : inputMode === "manual_claim" ? "Investigate" : "Extract claims"}</button></div>
            {error && <p className="claim-submit-error" role="alert">{error}</p>}
          </form>
        </details>}
        {workspaceView === "investigations" && <div className="workspace-tools">
          <details className="system-context">
            <summary>Research safeguards</summary>
            <div><p><b>{apiStatus?.orchestrator === "langgraph" ? "Unified authoritative workflow active." : `${titleCase(apiStatus?.orchestrator ?? "Connecting")} path active.`}</b> Research, verification, defender/challenger arguments, judgment, review, and publication are checkpointed in one durable thread.</p><span>InvestigationService authority</span><span>Direct rollback retained</span><span>{apiStatus?.live_research ? "Live research" : "Fixture research"}</span></div>
          </details>
          <details className="api-configuration" open={!connected}>
            <summary>Evidence service · {titleCase(connectionState)}</summary>
            <form onSubmit={saveApiAddress}>
              <label htmlFor="api-address">API origin</label>
              <div><input id="api-address" aria-label="API address" value={apiDraft} onChange={(event) => setApiDraft(event.target.value)} aria-describedby="api-connection-message" /><button className="ghost">Save & retry</button><button type="button" className="ghost" onClick={resetApiAddress}>Reset to local default</button></div>
              <small id="api-connection-message" role="status" aria-live="polite">{connectionMessage}</small>
              <small>Only the API origin is stored locally. Credentials, paths, queries and fragments are rejected.</small>
            </form>
          </details>
        </div>}
        {workspaceView === "investigations" && working && <section className="activity-card" role="status" aria-live="polite">
          <div className="activity-pulse"><i /><i /><i /></div>
          <div className="activity-copy">
            <span>{jobActive || activity === "investigation" ? "INVESTIGATION IN PROGRESS" : activity === "extraction" ? "EXTRACTING CLAIMS" : "UPDATING REVIEW"}</span>
            <strong>{jobActive || activity === "investigation" ? `${titleCase(liveStage ?? job?.job.status ?? "queued")} · Researchers are gathering, challenging and verifying evidence` : activity === "extraction" ? "Finding checkable statements in the submitted material" : "Saving the decision and resuming the durable graph"}</strong>
            <small>{elapsedSeconds}s elapsed · Progress channel: {progressStatusLabel} · This is live activity, not an estimated completion percentage.</small>
          </div>
          {jobActive && <button className="cancel-job" onClick={cancelJob}>Cancel safely</button>}
          <div className="activity-track"><i /></div>
        </section>}
        {workspaceView === "investigations" && jobFailed && job && !report && <section className="job-failure-card" role="alert">
          <div><span>EARLIER ATTEMPT STOPPED</span><h2>No report was produced for that attempt</h2><p>{job.job.last_error ?? "The durable job ended before the investigation report could be created."}</p><small>Historical job {shortId(job.job.job_id)} · {job.job.attempts} attempt{job.job.attempts === 1 ? "" : "s"} recorded · The evidence service is currently {connected ? "connected" : "unavailable"}.</small></div>
          <button className="ghost" type="button" onClick={prepareFailedJobRetry}>Use claim in a new attempt</button>
        </section>}
        {workspaceView === "investigations" && jobActive && <section className="working-graph" aria-label="Investigation graph is running">
          <div className="working-graph-head"><div><span>AUTHORITATIVE INVESTIGATION PROGRESS</span><strong>{titleCase(liveStage ?? job.job.status)}</strong></div><div className={`stream-health ${progressStream.status}`} role="status" aria-live="polite"><b>{progressStatusLabel}</b><small>{progressStream.message}</small><small>Persisted sequence {progressStream.lastSequence}</small></div></div>
          <div className="graph-progress" role="progressbar" aria-valuenow={Math.round((liveNodeIndex + 1) / graphOrder.length * 100)} aria-valuemin={0} aria-valuemax={100}><i style={{width: `${Math.round((liveNodeIndex + 1) / graphOrder.length * 100)}%`}} /></div>
          <div className="graph investigation-graph graph-running">
            {graphOrder.map((node, index) => <div className={`node ${index < liveNodeIndex ? "done" : index === liveNodeIndex ? "active" : "waiting"}`} key={node}><div>{index < liveNodeIndex ? "✓" : index === liveNodeIndex ? "↻" : index + 1}</div><span>{graphLabels[node]}</span>{index < graphOrder.length - 1 && <i />}</div>)}
          </div>
          <p>One durable workflow thread is coordinating authoritative research, verification, arguments, judgment, review routing and publication. InvestigationService remains the domain and persistence authority inside each node.</p>
        </section>}
        {workspaceView === "investigations" && claimCandidates.length > 0 && <section className="record-list" aria-label="Extracted claim candidates">
          {claimCandidates.map((candidate) => <article key={candidate.candidate_id}>
            <b>{candidate.rank}. {candidate.text}</b>
            <span>Check-worthiness {Math.round(candidate.checkworthiness * 100)}%</span>
            <button className="ghost" disabled={busy} onClick={() => { setBusy(true); setActivity("investigation"); void investigateCandidate(candidate.text).catch((reason: Error) => setError(reason.message)).finally(() => { setBusy(false); setActivity(null); }); }}>Investigate this claim</button>
          </article>)}
        </section>}
        {error && workspaceView !== "investigations" && <div className="error-banner" role="alert">{error}</div>}

        {workspaceView === "review_queue" ? (
          <section className="navigation-view" aria-labelledby="review-queue-title">
            <div className="navigation-view-heading"><div><span>REVIEW OPERATIONS</span><h2 id="review-queue-title">Decisions requiring human judgment</h2><p>Prioritize unresolved cases, inspect the evidence packet, and record a decision without altering earlier audit history.</p></div><button className="ghost" onClick={() => void loadReviewQueue()}>Refresh queue</button></div>
            <div className="queue-toolbar" aria-label="Review queue controls"><label><span>SEARCH</span><input value={reviewQueueQuery} onChange={(event) => setReviewQueueQuery(event.target.value)} placeholder="Claim, case ID, or review reason" /></label><label><span>STATUS</span><select value={reviewQueueFilter} onChange={(event) => setReviewQueueFilter(event.target.value as typeof reviewQueueFilter)}><option value="pending">All awaiting action</option><option value="review">Awaiting reviewer</option><option value="approval">Awaiting distinct approval</option><option value="complete">Completed</option><option value="all">All records</option></select></label><div><span>VISIBLE</span><strong>{visibleReviewQueue.length}</strong><small>of {reviewQueue.length} records</small></div></div>
            {reviewQueueError ? <div className="view-state error-state" role="alert"><b>Review queue unavailable</b><p>{reviewQueueError}</p><button className="ghost" onClick={() => void loadReviewQueue()}>Try again</button></div>
              : connectionState === "connecting" || navigationLoading ? <div className="view-state" role="status">Loading durable review records…</div>
              : !connected ? <div className="view-state"><b>Connect the evidence API</b><p>The review queue cannot be read while the configured API is unavailable.</p></div>
              : reviewQueue.length === 0 ? <div className="view-state"><b>No review requests</b><p>Investigations routed to human judgment will appear here with their persisted reason and audit state.</p><button className="ghost" onClick={() => navigateWorkspace("investigations")}>Start an investigation</button></div>
              : visibleReviewQueue.length === 0 ? <div className="view-state"><b>No reviews match these filters</b><p>Change the search text or status filter to see other persisted review records.</p><button className="ghost" onClick={() => { setReviewQueueQuery(""); setReviewQueueFilter("pending"); }}>Clear filters</button></div>
              : <div className="queue-list">{visibleReviewQueue.map((history) => {
                const reviewState = reviewStateOf(history);
                const state = reviewState === "review" ? "Awaiting reviewer" : reviewState === "approval" ? "Awaiting distinct approval" : "Decision recorded";
                const pending = reviewState !== "complete";
                const investigation = investigations.find((item) => item.investigation_id === history.request.investigation_id);
                const reasonCode = reviewReasonCode(history.request.reason);
                return <article key={history.request.request_id} className={pending ? "queue-item pending" : "queue-item complete"}>
                  <div className="queue-case"><span>{pending ? "ACTION REQUIRED" : "AUDIT COMPLETE"}</span><h3>{investigation?.input_claim ?? `Investigation ${shortId(history.request.investigation_id)}`}</h3><p className="queue-reason">{reviewReasonLabel(history.request.reason)}</p><small>Case {shortId(history.request.investigation_id)} · Request {shortId(history.request.request_id)}</small></div>
                  <dl><div><dt>Next owner</dt><dd>{reviewState === "review" ? "Reviewer" : reviewState === "approval" ? "Distinct approver" : "None"}</dd></div><div><dt>Status</dt><dd>{state}</dd></div><div><dt>Reason code</dt><dd><code>{reasonCode}</code></dd></div><div><dt>Requested</dt><dd>{new Date(history.request.created_at).toLocaleString()}</dd></div><div><dt>Audit chain</dt><dd className={history.chain_valid ? "audit-valid" : "audit-warning"}>{history.chain_valid ? "Verified" : "Needs attention"}</dd></div></dl>
                  <button className="primary" onClick={() => selectInvestigation(history.request.investigation_id, pending ? "Review brief" : "Review history")}>{pending ? "Open review" : "Open history"}</button>
                </article>;
              })}</div>}
          </section>
        ) : workspaceView === "system_health" ? (
          <section className="navigation-view" aria-labelledby="system-health-title">
            <div className="navigation-view-heading"><div><span>LOCAL OPERATIONS</span><h2 id="system-health-title">Service and provider status</h2><p>Operational state, configured providers, cumulative usage, and recovery diagnostics from the evidence service.</p></div><button className="ghost" onClick={() => setConnectionRetry((value) => value + 1)}>Refresh status</button></div>
            {navigationLoading || connectionState === "connecting" ? <div className="view-state" role="status">Checking API and telemetry…</div> : <>
              <section className={`health-summary ${connected ? "healthy" : "unhealthy"}`} role="status" aria-live="polite"><div><span>{connected ? "CORE SERVICE AVAILABLE" : "CORE SERVICE UNAVAILABLE"}</span><h3>{connected ? "The evidence service is reachable" : "The dashboard cannot reach the evidence service"}</h3><p>{connected ? "Investigation records, review operations, and operational telemetry can be read from the configured service." : connectionMessage}</p></div><strong>{connected ? "Operational" : "Action required"}</strong></section>
              <div className="health-grid">
                <article><span>EVIDENCE SERVICE</span><strong className={connected ? "health-good" : "health-bad"}>{titleCase(connectionState)}</strong><p>{connected ? `API ${apiStatus?.api_version ?? "version not reported"} at the configured local origin.` : connectionMessage}</p></article>
                <article><span>RESEARCH PROVIDER</span><strong>{providerLabel(apiStatus?.retrieval_provider)}</strong><p>{apiStatus?.live_research ? "Live web research is enabled." : apiStatus ? "Recorded research fixtures are active." : "Provider state unavailable."}</p></article>
                <article><span>MODEL PROVIDER</span><strong>{providerLabel(apiStatus?.model_provider)}</strong><p>{Math.round(telemetryModelTokens).toLocaleString()} cumulative observed tokens · ${telemetryModelCost.toFixed(6)} estimated cumulative cost.</p></article>
                <article><span>DURABLE WORKFLOW</span><strong>{apiStatus ? "Active" : "Unavailable"}</strong><p>Domain operations: {apiStatus?.authoritative_service ?? "not reported"}. Sequential rollback remains available.</p></article>
              </div>
              <section className="telemetry-panel"><div className="telemetry-heading"><div><span>CUMULATIVE SERVICE ACTIVITY</span><h3>{telemetry ? "Operational telemetry" : "Telemetry unavailable"}</h3><p>Process/store-wide observations—not the selected investigation. Latency cards show averages, not accumulated duration.</p></div>{telemetry && <dl><div><dt>Traces</dt><dd>{telemetry.traces.toLocaleString()}</dd></div><div><dt>Spans</dt><dd>{telemetry.spans.toLocaleString()}</dd></div></dl>}</div>{telemetry ? telemetry.metrics.length === 0 ? <p className="empty-copy">No metrics have been recorded in this process.</p> : <div className="metric-list">{telemetry.metrics.map((metric) => { const view = telemetryMetricView(metric); return <article key={metric.name}><b>{view.label}</b><strong>{view.value}</strong><small>{view.detail}</small></article>; })}</div> : <div className="view-state"><p>The core API may be available while the optional telemetry endpoint is unavailable.</p></div>}</section>
              <details className="health-diagnostics"><summary>Configuration and diagnostics</summary><div className="health-diagnostic-grid"><form onSubmit={saveApiAddress}><label htmlFor="health-api-address">API origin</label><div><input id="health-api-address" value={apiDraft} onChange={(event) => setApiDraft(event.target.value)} /><button className="ghost">Save & retry</button><button type="button" className="ghost" onClick={resetApiAddress}>Reset</button></div><small>{connectionMessage}</small><small>Only the origin is stored locally; credentials, paths, queries, and fragments are rejected.</small></form><dl><div><dt>Configured origin</dt><dd>{apiBase}</dd></div><div><dt>API version</dt><dd>{apiStatus?.api_version ?? "Unavailable"}</dd></div><div><dt>Investigation records</dt><dd>{investigations.length}</dd></div><div><dt>Reviews awaiting action</dt><dd>{pendingReviews.length}</dd></div></dl></div></details>
            </>}
          </section>
        ) : !report && reviewPending && job?.interruption ? (
          <div className="pre-report-workspace" aria-label="Investigation result requiring review">
            <section className="pre-report-hero">
              <div><span>PROVISIONAL INVESTIGATION RESULT</span><h2>{job.interruption.claim_text}</h2><p>{job.interruption.route_reason}</p></div>
              <div className="provisional-seal"><small>PROVISIONAL VERDICT</small><strong>{titleCase(job.interruption.provisional_verdict)}</strong><em>Publication blocked</em></div>
            </section>

            <section className="interrupted-summary">
              <div><span>WORKFLOW</span><strong>{titleCase(job.graph?.phase ?? "review")}</strong><small>Checkpoint {job.graph?.checkpoint_sequence ?? ""}</small></div>
              <div><span>RESEARCH ROLES</span><strong>{job.graph?.assignments.length ?? 0}</strong><small>{successfulResearchRoles} returned evidence · {failedResearchRoles} failed</small></div>
              <div><span>APPROVED EVIDENCE</span><strong>{job.graph?.approved_evidence_ids.length ?? 0}</strong><small>{job.graph?.evidence_families.length ?? 0} independent families</small></div>
              <div><span>UNRESOLVED</span><strong>{job.graph?.unresolved_questions.length ?? 0}</strong><small>Research questions</small></div>
              <div><span>COST SO FAR</span><strong>${(job.graph?.consumption.estimated_cost_usd ?? 0).toFixed(4)}</strong><small>{job.graph?.consumption.model_calls ?? 0} model calls · {job.graph?.consumption.total_tokens ?? 0} tokens</small></div>
              <div><span>DURATION</span><strong>{(job.graph?.consumption.duration_seconds ?? 0).toFixed(1)}s</strong><small>{job.graph?.consumption.completed_rounds ?? 0} research round</small></div>
            </section>

            <section className="graph-card interrupted-graph">
              <div className="card-heading"><div><span>AUTHORITATIVE WORKFLOW TRACE</span><h2>Paused safely at human review</h2><small className="authority-note">All completed operations are checkpointed. Requesting more evidence resumes this thread without replaying paid work.</small></div><div className="graph-progress-label"><strong>{graphProgress}%</strong><small>{completedGraphNodes} of {graphOrder.length} phases checkpointed</small></div></div>
              <div className="graph-progress" role="progressbar" aria-valuenow={graphProgress} aria-valuemin={0} aria-valuemax={100}><i style={{width: `${graphProgress}%`}} /></div>
              <div className="stream-health inline-stream-health paused" role="status" aria-live="polite"><b>Review state · Awaiting decision</b><small>Safely paused at a persisted checkpoint · {completedGraphNodes} phases checkpointed · Live updates {graphStream.status === "live" ? "connected" : "recovering in background"}</small></div>
              <div className="graph">{graphOrder.map((node, index) => { const done = graph?.completed_nodes.includes(node); const active = node === "review"; return <div className={`node ${done ? "done" : active ? "active" : "waiting"}`} key={node}><div>{done ? "✓" : active ? "!" : index + 1}</div><span>{graphLabels[node]}</span>{index < graphOrder.length - 1 && <i />}</div>; })}</div>
            </section>

            <div className="pre-report-columns">
              <div className="pre-report-main">
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
              </div>

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
                <button className="primary" onClick={saveDecision} disabled={busy || rationale.trim().length < 3 || reviewer.trim().length < 3 || (["approve", "revise"].includes(effectiveDecisionKind) && (approver.trim().length < 3 || approver.trim().toLocaleLowerCase() === reviewer.trim().toLocaleLowerCase()))}>{busy ? "Saving…" : "Save decision & resume workflow"}</button>
                <small className="immutable">Only permitted decisions are offered. The result is appended to the immutable review history.</small>
              </aside>
            </div>
          </div>
        ) : !report ? (
          <section className="empty-state">
            <span>{connected ? "EVIDENCE WORKSPACE READY" : "CONNECTION REQUIRED"}</span><h2>{connected ? investigations.length > 0 ? "Start a new investigation" : "Submit your first claim" : "Connect the evidence service"}</h2>
            <p>{connected ? investigations.length > 0 ? "Enter a claim above, or open an existing investigation from Recent Cases." : "Enter a claim above to produce a typed evidence packet and citation-grounded provisional verdict." : "Start the local service, then retry. You can also change its address in the connection settings."}</p>
            {!connected && <button className="ghost" onClick={() => setConnectionRetry((value) => value + 1)}>Retry connection</button>}
          </section>
        ) : (
          <>
            <section className={`report-lifecycle ${overallPublicationReady ? "ready" : "provisional"}`}>
              <div><span>{overallPublicationReady ? "PUBLICATION-READY REPORT" : "CURRENT REPORT STATUS"}</span><h2>{overallPublicationReady ? "Ready for final source inspection" : approvalBlockedByEvidence ? "Evidence remediation required before a final decision" : "Report ready for human decision"}</h2><p>{overallPublicationReady ? "The recorded safeguards permit publication. Anyone relying on the result should still inspect decisive evidence before use." : approvalBlockedByEvidence ? "The provisional report is preserved for review, but its current evidence cannot support publication. Inspect the blockers and choose a permitted remediation action." : "The evidence-assisted report is ready for review. Publication remains blocked until a person evaluates the evidence, limitations, and recommendation."}</p></div>
              <div><small>NEXT REQUIRED STEP</small><strong>{overallPublicationReady ? "Final source check" : approvalBlockedByEvidence ? "Resolve evidence blockers" : "Record human decision"}</strong><em>{argumentEligibleCount}/{evidence.length} passages eligible · {report.effective_full_report_assurance?.critical_failure_count ?? 0} critical citation failures</em><button className="ghost" onClick={() => setSection(overallPublicationReady ? "Evidence" : "Review brief")}>{overallPublicationReady ? "Inspect decisive evidence" : "Open review brief"}</button></div>
            </section>
            <div className={`summary-row ${overallPublicationReady ? "ready" : "blocked"}`}>
              <div><span>{overallPublicationReady ? "CURRENT VERDICT" : "CURRENT EFFECTIVE DECISION"}</span><strong>{overallPublicationReady ? titleCase(resolvedVerdict ?? report.verdict.label) : "Unresolved"}</strong><small>{overallPublicationReady ? "Publication safeguards passed" : `Historical recommendation: ${titleCase(resolvedVerdict ?? report.verdict.label)}`}</small></div>
              <div><span>CONFIDENCE <MetricHelp id="confidence-help" label="Explain confidence">A calibrated probability of verdict correctness. A dash means the system has not been empirically calibrated and will not invent a probability.</MetricHelp></span><strong>{report.verdict.confidence == null ? "—" : `${Math.round(report.verdict.confidence * 100)}%`}</strong><small>{report.verdict.confidence == null ? "Not calibrated" : "Calibrated probability"}</small></div>
              <div><span>REPORT CITATION SUPPORT <MetricHelp id="citation-support-help" label="Explain report citation support">The share of material report assertions with accepted mappings to currently eligible evidence. It does not measure whether useful evidence was merely retained.</MetricHelp></span><strong>{citationSummary?.rate ?? 0}%</strong><small>{citationSummary?.supported ?? 0} of {citationSummary?.total ?? 0} material report assertions supported · {citationSummary?.authority}</small></div>
              <div><span>EFFECTIVE INDEPENDENCE <MetricHelp id="independence-help" label="Explain evidence families">Groups of currently eligible sources that appear to originate independently. Multiple pages repeating one original report count as one family.</MetricHelp></span><strong>{argumentEligibleCount ? report.provenance?.confirmed_independent_lower_bound ?? "—" : "—"}</strong><small>{argumentEligibleCount ? `Target ${report.plan.minimum_independent_families}` : `Retained packet recorded ${report.provenance?.confirmed_independent_lower_bound ?? 0}`}</small></div>
              <div><span>ELIGIBLE EVIDENCE <MetricHelp id="eligible-evidence-help" label="Explain eligible evidence">Retained passages that pass current integrity and approved-use checks. Eligibility does not mean the report has cited them correctly.</MetricHelp></span><strong>{argumentEligibleCount}/{evidence.length}</strong><small>Passages eligible for argument use · not a citation-support score</small></div>
            </div>
            <section className="workflow-compass" aria-label="Recommended review path">
              <article><span>1 · OUTCOME</span><strong>Understand the result</strong><p>{overallPublicationReady ? "Review the publishable conclusion and its recorded limitations." : `Start with the current blockers and the historical recommendation.`}</p><button onClick={() => setSection("Review brief")}>Review the outcome</button></article>
              <article><span>2 · EVIDENCE</span><strong>Inspect the sources</strong><p>{evidence.length} retained · {argumentEligibleCount} eligible · {report.provenance?.confirmed_independent_lower_bound ?? 0} retained source-origin families.</p><button onClick={() => setSection("Evidence")}>Inspect evidence</button></article>
              <article><span>3 · SAFEGUARDS</span><strong>Check the safeguards</strong><p>{verificationSummary && !verificationSummary.requiredNumerical && !verificationSummary.requiredTemporal ? "No typed numerical or temporal check was required." : `${verificationSummary?.unresolved ?? 0} typed verification checks unresolved.`} {report.effective_full_report_assurance?.critical_failure_count ?? 0} critical citation failures.</p><div><button onClick={() => setSection("Verification")}>Verification</button><button onClick={() => setSection("Citation audit")}>Citations</button></div></article>
              <article className={overallPublicationReady ? "ready" : "blocked"}><span>4 · DECISION</span><strong>{overallPublicationReady ? "Perform final check" : approvalBlockedByEvidence ? "Choose remediation" : "Record your decision"}</strong><p>{overallPublicationReady ? "The report can be exported after final source inspection." : approvalBlockedByEvidence ? "Request evidence, revise, or reject. Approval is unavailable while safeguards are blocked." : "Approve, revise, request evidence, or reject based on the reviewed packet."}</p><button onClick={() => setSection(reviewPending ? "Review brief" : overallPublicationReady ? "Evidence" : "Decision rationale")}>{overallPublicationReady ? "Final source check" : "Open decision"}</button></article>
            </section>
            <div className="graph-card report-workflow-trace">
              <div className="card-heading"><div><span>INVESTIGATION WORKFLOW</span><h2>{graph ? titleCase(graph.status) : "Awaiting investigation"}</h2><small className="authority-note">Completed stages are persisted. Resuming continues from the current checkpoint without repeating completed paid operations.</small></div>{graph ? <div className="graph-progress-label"><strong>{graphProgress}%</strong><small>{completedGraphNodes} of {graphOrder.length} phases checkpointed</small></div> : null}</div>
              {graph && <div className="graph-progress" role="progressbar" aria-valuenow={graphProgress} aria-valuemin={0} aria-valuemax={100} aria-label="Checkpointed workflow progress"><i style={{width: `${graphProgress}%`}} /></div>}
              {graph?.status === "review_required" && <div className="stream-health inline-stream-health paused" role="status" aria-live="polite"><b>Review state · Awaiting decision</b><small>Checkpoint {completedGraphNodes} of {graphOrder.length} is safely persisted. No processing is expected until a review decision is recorded.</small></div>}
              <div className="graph">
                {graphOrder.map((node, index) => {
                  const done = graph?.completed_nodes.includes(node);
                  const active = graph?.status === "review_required" && node === "review";
                  return <div className={`node ${done ? "done" : active ? "active" : "waiting"}`} key={node}><div>{done ? "✓" : active ? "!" : index + 1}</div><span>{graphLabels[node]}</span>{index < graphOrder.length - 1 && <i />}</div>;
                })}
              </div>
            </div>
            <div className="tabs" role="tablist" aria-label="Investigation report sections">
              {reportSections.map((item, index) => <button id={`report-tab-${index}`} aria-controls="report-section-panel" tabIndex={section === item ? 0 : -1} key={item} role="tab" aria-selected={section === item} className={section === item ? "active" : ""} onClick={() => setSection(item)} onKeyDown={(event) => {
                if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
                event.preventDefault();
                const next = event.key === "Home" ? 0 : event.key === "End" ? reportSections.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + reportSections.length) % reportSections.length;
                setSection(reportSections[next]);
                document.getElementById(`report-tab-${next}`)?.focus();
              }}>{item}</button>)}
            </div>
            <div id="report-section-panel" role="tabpanel" aria-labelledby={`report-tab-${Math.max(0, reportSections.indexOf(section as typeof reportSections[number]))}`} tabIndex={0}>
            {section === "Review brief" && <div className="review-brief-dashboard">
              <section className={`review-recommendation ${overallPublicationReady ? "publishable" : "hold"}`}>
                <div><span>REVIEW RECOMMENDATION</span><h2>{reviewerRecommendation}</h2><p>{overallPublicationReady ? "The persisted authoritative publication decision permits publication. Anyone relying on this result should still inspect decisive evidence." : report.publication_decision ? "The authoritative publication decision records one or more blocking safeguards." : "No authoritative publication decision is available, so the dashboard fails closed and treats this report as provisional."}</p></div>
                <div className="review-verdict"><small>{overallPublicationReady ? "CURRENT FACTUAL VERDICT" : "CURRENT EFFECTIVE DECISION"}</small><strong>{overallPublicationReady ? titleCase(resolvedVerdict ?? report.verdict.label) : "Unresolved"}</strong><em>{overallPublicationReady ? (report.verdict.confidence == null ? "Confidence not calibrated" : `${Math.round(report.verdict.confidence * 100)}% calibrated confidence`) : `Historical recommendation: ${titleCase(resolvedVerdict ?? report.verdict.label)}`}</em></div>
              </section>
              <section className="review-gates">
                <article><span>JUDGMENT READINESS</span><strong>{titleCase(report.readiness?.state ?? "not reported")}</strong><p>{report.readiness?.state === "human_review_required" ? "Blocking safeguards remain; the verdict is provisional." : "The deterministic readiness gate does not require escalation."}</p></article>
                <article className={citationReady ? "" : "gate-blocked"}><span>EFFECTIVE CITATION ASSURANCE</span><strong>{titleCase(effectiveCitationStatus ?? "not reported")}</strong><p>{citationReady ? "The effective report sentences passed citation matching. This does not establish source authority or independence." : `${report.effective_full_report_assurance?.critical_failure_count ?? 0} critical effective citation failure(s) block publication.`}</p><small>{citationSummary?.authority}</small></article>
                <article className={argumentEligibleCount ? "" : "gate-blocked"}><span>EFFECTIVE INDEPENDENCE</span><strong>{argumentEligibleCount ? titleCase(report.provenance?.requirement_state ?? "not reported") : "Not established"}</strong><p>{argumentEligibleCount ? (report.provenance ? `${report.provenance.confirmed_independent_lower_bound} confirmed; up to ${report.provenance.possible_independent_upper_bound} possible; ${report.provenance.unresolved_dependency_count} unresolved relationship(s).` : "No provenance assessment was recorded.") : `The retained packet recorded ${titleCase(report.provenance?.requirement_state ?? "no state")}, but none of its ${evidence.length} passage(s) is currently argument-eligible.`}</p></article>
                <article><span>VERIFICATION</span><strong>{verificationSummary && !verificationSummary.requiredNumerical && !verificationSummary.requiredTemporal ? "No typed check required" : `${verificationSummary?.completeness ?? 0}% complete`}</strong><p>{verificationSummary?.unresolved ? `${verificationSummary.unresolved} required assertion-level check(s) remain unresolved.` : verificationSummary && !verificationSummary.requiredNumerical && !verificationSummary.requiredTemporal ? "The investigation plan did not require a numerical or temporal assertion-level check." : "No unresolved assertion-level verification check was recorded."}</p><small>{verificationSummary?.authority}</small></article>
                <article><span>SOURCE QUALITY</span><strong>{report.readiness?.source_quality_unknown_count ?? 0} unknown signal(s)</strong><p>Unknown quality is not evidence that a source is poor, but it prevents the system from claiming verified authority.</p></article>
                <article><span>PASSAGE HYGIENE</span><strong>{contaminatedEvidence.length ? `${contaminatedEvidence.length} warning(s)` : "Clean"}</strong><p>{contaminatedEvidence.length ? "Retained passages appear to include navigation text, export controls, encoding damage, or other page boilerplate." : "No common navigation or encoding contamination was detected."}</p></article>
                <article className={blockingSocialCount ? "gate-blocked" : ""}><span>SOCIAL EVIDENCE</span><strong>{socialEvidence.length ? `${socialEvidence.length} item(s)` : "None retained"}</strong><p>{blockingSocialCount ? `${blockingSocialCount} blocking social-evidence finding(s) prevent publication.` : socialRiskCount ? `${socialRiskCount} social-source risk signal(s) require inspection.` : "No unresolved social-evidence risk was recorded."}</p></article>
              </section>
              <div className="review-brief-columns">
                <section className="detail-card">
                  <span>CLAIM FRAMING</span><h2>{report.claim.text}</h2>
                  <dl className="compact-dl"><div><dt>Type</dt><dd>{titleCase(report.claim.claim_type)}</dd></div><div><dt>Checkworthiness</dt><dd>{Math.round(report.claim.checkworthiness * 100)}%</dd></div><div><dt>Geography/context</dt><dd>{report.claim.geography ?? "Not specified"}</dd></div><div><dt>Recorded ambiguities</dt><dd>{report.claim.ambiguities.length}</dd></div></dl>
                  {!report.claim.ambiguities.length && <p className="review-warning">A zero ambiguity count means the automated normalizer recorded none; it is not proof that compound, quantified, comparative, or absolute wording is sufficiently scoped.</p>}
                </section>
                <section className="detail-card">
                  <span>WHY REVIEW WAS ROUTED</span><h2>{report.readiness?.reason_codes.length ?? 0} recorded routing signals</h2>
                  <div className="reason-chips">{report.readiness?.reason_codes.map((reason) => <b key={reason}>{titleCase(reason)}</b>)}</div>
                  <p className="routing-scope-note">The chips preserve the original readiness-routing record. The metrics below describe the current effective packet.</p>
                  <dl className="compact-dl"><div><dt>Argument-ledger blocking challenges</dt><dd>{report.readiness?.blocking_challenge_count ?? 0}</dd></div><div><dt>Effective citation failures</dt><dd>{report.effective_full_report_assurance?.critical_failure_count ?? 0}</dd></div><div><dt>Ineligible retained passages</dt><dd>{Math.max(0, evidence.length - argumentEligibleCount)}</dd></div><div><dt>Effective clause coverage</dt><dd>{citationSummary?.rate ?? 0}%</dd></div></dl>
                </section>
              </div>
              <section className="review-actions-card">
                <div><span>RECOMMENDED REVIEW ACTION</span><h2>{reviewerRecommendation}</h2><p>{overallPublicationReady ? "Confirm the cited sources and approve through the authoritative review thread." : `Inspect and replace or safely re-extract the ${historicalVerdictEvidenceIds.size || contaminatedEvidence.length || "blocked"} ineligible verdict-linked passage(s), record an approved evidentiary use, then rerun the effective argument and citation gates.`}</p></div>
                <div><button onClick={() => setSection("Evidence")}>Inspect exact evidence</button>{(socialEvidence.length > 0 || socialRiskCount > 0) && <button onClick={() => setSection("Social evidence")}>Trace social evidence</button>}<button onClick={() => setSection("Verification")}>Inspect unresolved checks</button><button onClick={() => setSection("Citation audit")}>Inspect citation mapping</button></div>
              </section>
              {reviewPending && job?.interruption && <section className="investigator-decision">
                  <div className="decision-intro"><span>YOUR JUDGMENT</span><h2>Record your evidence-based decision</h2><p>The automated recommendation is advisory. Review the report first, then request stronger evidence, revise, or reject the packet. Approval is unavailable while effective evidence or citation safeguards are blocked.</p><dl><div><dt>Automated recommendation</dt><dd>{reviewerRecommendation}</dd></div><div><dt>Current effective decision</dt><dd>{overallPublicationReady ? titleCase(job.interruption.provisional_verdict) : "Unresolved"}</dd></div><div><dt>Historical recommendation</dt><dd>{titleCase(job.interruption.provisional_verdict)}</dd></div><div><dt>Audit history</dt><dd>{review?.chain_valid ? "Verified" : "Pending"}</dd></div></dl></div>
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
              <section className={`overview-status-hero ${overallPublicationReady ? "ready" : "blocked"}`}>
                <div><span>{overallPublicationReady ? "CURRENT PUBLICATION STATUS" : "CURRENT EFFECTIVE STATUS"}</span><h2>{overallPublicationReady ? `${titleCase(resolvedVerdict ?? report.verdict.label)} · publication ready` : "Publication blocked"}</h2><p>{overallPublicationReady ? "The effective evidence packet, verification, citation assurance and recorded publication decision currently permit publication." : "The retained report remains available for review, but the effective evidence and citation safeguards do not currently support publication."}</p></div>
                <dl><div><dt>Effective evidence</dt><dd>{argumentEligibleCount}/{evidence.length}</dd></div><div><dt>Decisive-use eligible</dt><dd>{decisiveEligibleIds.size}</dd></div><div><dt>Citation gate</dt><dd>{titleCase(effectiveCitationStatus ?? "not reported")}</dd></div><div><dt>Review state</dt><dd>{reviewPending || report.verdict.human_review_required ? "Required" : overallPublicationReady ? "Complete" : "Remediation"}</dd></div></dl>
              </section>
              {!overallPublicationReady && <section className="overview-authority-warning" role="alert">
                <div><span>HISTORICAL VERDICT RETAINED FOR AUDIT</span><h2>Provisional · {titleCase(resolvedVerdict ?? report.verdict.label)}</h2><p>This label was produced against the earlier packet. It is not a current publishable conclusion because {historicalVerdictEvidenceIds.size || "one or more"} historical evidence link(s) no longer satisfy the effective eligibility rules.</p></div>
                <button onClick={() => setSection("Decision rationale")}>Inspect current reasoning</button>
              </section>}
              <section className="overview-next-action">
                <div><span>NEXT BEST ACTION</span><h2>{overallPublicationReady ? "Perform a final source inspection" : reviewPending ? "Request replacement evidence, revise, or reject" : "Remediate the effective evidence packet"}</h2><p>{overallPublicationReady ? "Open the decisive passages and verify the original sources before relying on or sharing the report." : "Inspect why the retained passages became ineligible, then record an allowed review decision. Human review cannot convert blocked evidence into valid support without a persisted remediation."}</p></div>
                <div><button onClick={() => setSection("Evidence")}>{overallPublicationReady ? "Inspect decisive evidence" : "Inspect evidence blockers"}</button><button onClick={() => setSection("Review brief")}>{overallPublicationReady ? "Open review brief" : "Record review decision"}</button></div>
              </section>
              <section className={`report-card overview-blockers-card ${overallPublicationReady ? "ready" : "blocked"}`}>
                <span>{overallPublicationReady ? "PUBLICATION DIAGNOSIS" : "WHY PUBLICATION IS BLOCKED"}</span><h2>{overallPublicationReady ? "No active blocker recorded" : `${Math.max(effectiveCitationStatus === "blocked" ? 1 : 0, report.effective_full_report_assurance?.blocking_reasons.length ?? 0) + (evidenceIntegrityBlocked ? 1 : 0)} safeguard category(s) require action`}</h2>
                {overallPublicationReady ? <p>The effective packet and recorded publication decision currently permit publication.</p> : <ol className="overview-blocker-list">
                  {(report.effective_full_report_assurance?.blocking_reasons.length ? report.effective_full_report_assurance.blocking_reasons : ["Effective citation assurance is not ready."]).slice(0, 3).map((reason, index) => <li key={`${index}-${reason}`}><b>{index + 1}</b><span>{reason}</span></li>)}
                  {evidenceIntegrityBlocked && <li><b>{(report.effective_full_report_assurance?.blocking_reasons.length ?? 0) + 1}</b><span>One or more retained passages fail the current evidence-integrity or approved-use gate.</span></li>}
                </ol>}
                <dl><div><dt>Effective decision</dt><dd>{overallPublicationReady ? titleCase(resolvedVerdict ?? report.verdict.label) : "Unresolved"}</dd></div><div><dt>Historical recommendation</dt><dd>{titleCase(resolvedVerdict ?? report.verdict.label)}</dd></div><div><dt>Critical citation failures</dt><dd>{report.effective_full_report_assurance?.critical_failure_count ?? report.full_report_assurance?.critical_failure_count ?? "—"}</dd></div></dl>
              </section>
              <section className="report-card">
                <span>RESEARCH AND EFFECTIVE COVERAGE</span><h2>{argumentEligibleCount} of {evidence.length} passages eligible</h2>
                <small className="coverage-scope-label">Retained-packet stance · not an effective support count</small>
                <div className={`stance-bars ${argumentEligibleCount === 0 ? "historical" : ""}`}>{["supporting", "contradictory", "qualifying", "context"].map((stance) => { const count = evidence.filter((item) => canonicalStance(item.stance) === stance).length; return <div key={stance}><label>{titleCase(stance)} <b>{count}</b></label><i><b style={{width: `${evidence.length && count ? Math.max(4, count / evidence.length * 100) : 0}%`}} /></i></div>; })}</div>
                <dl><div><dt>Retained passages</dt><dd>{evidence.length}</dd></div><div><dt>Argument-eligible</dt><dd>{argumentEligibleCount}</dd></div><div><dt>Decisive-use eligible</dt><dd>{decisiveEligibleIds.size}</dd></div></dl>
                <small>Research paths: {report.plan.required_research_paths.map(titleCase).join(" · ")}</small>
              </section>
              <section className="report-card">
                <span>INDEPENDENCE & PROVENANCE</span><h2>{argumentEligibleCount ? titleCase(report.provenance?.requirement_state ?? "not reported") : "Not established for effective packet"}</h2>
                <dl><div><dt>Recorded retained-packet state</dt><dd>{titleCase(report.provenance?.requirement_state ?? "not reported")}</dd></div><div><dt>Confirmed independent lower bound</dt><dd>{report.provenance?.confirmed_independent_lower_bound ?? "—"}</dd></div><div><dt>Effective eligible passages</dt><dd>{argumentEligibleCount}</dd></div><div><dt>Unresolved relationships</dt><dd>{report.provenance?.unresolved_dependency_count ?? "—"}</dd></div></dl>
                <small>Independence describes source origin. It does not override passage hygiene, approved-use, citation, or source-quality safeguards.</small>
              </section>
              <section className="report-card">
                <span>VERIFICATION</span><h2>{verificationSummary && !verificationSummary.requiredNumerical && !verificationSummary.requiredTemporal ? "No typed check required" : `${verificationSummary?.completeness ?? 0}% complete`}</h2>
                <dl><div><dt>Unresolved typed checks</dt><dd>{verificationSummary?.unresolved ?? "—"}</dd></div><div><dt>Numerical check required</dt><dd>{verificationSummary?.requiredNumerical ? "Yes" : "No"}</dd></div><div><dt>Temporal check required</dt><dd>{verificationSummary?.requiredTemporal ? "Yes" : "No"}</dd></div><div><dt>Authority</dt><dd>{verificationSummary?.authority ?? "Not reported"}</dd></div></dl>
                <small>A complete verification packet only covers checks that were required. It is not a general truth or confidence score.</small>
              </section>
              <section className={`report-card overview-integrity-card ${evidenceIntegrityBlocked ? "blocked" : ""}`}>
                <span>EVIDENCE INTEGRITY</span><h2>{evidenceIntegrityBlocked ? "Publication blocker recorded" : contaminatedEvidence.length ? "Warnings require inspection" : "No blocker recorded"}</h2>
                <dl><div><dt>Passage hygiene warnings</dt><dd>{contaminatedEvidence.length}</dd></div><div><dt>Historical verdict links removed</dt><dd>{historicalVerdictEvidenceIds.size}</dd></div><div><dt>Argument-eligible passages</dt><dd>{argumentEligibleCount}</dd></div><div><dt>Unknown source-quality signals</dt><dd>{report.readiness?.source_quality_unknown_count ?? "—"}</dd></div></dl>
                <button className="inline-link" onClick={() => setSection("Evidence")}>Inspect evidence integrity →</button>
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
                <div><b>Effective evidence</b><p>Retained evidence that still passes the current integrity, approved-use, and argument-eligibility rules.</p></div>
                <div><b>Decisive use</b><p>Evidence permitted to materially influence a verdict. Relevance or retention alone does not grant this role.</p></div>
                <div><b>Historical verdict</b><p>A preserved earlier recommendation retained for audit. It is not a current conclusion when effective safeguards block publication.</p></div>
              </details>
            </div>}
            {section === "Social evidence" && <div className="social-transparency-dashboard">
              <section className={`social-policy-hero ${report.social_evidence_policy?.publication_blocked ? "blocked" : ""}`}>
                <div>
                  <span>SOCIAL-EVIDENCE POLICY</span>
                  <h2>{report.social_evidence_policy?.publication_blocked ? "Critical social dependency blocks publication" : socialEvidence.length ? "Every social item has a traceable, limited role" : "No social-media passage was retained as evidence"}</h2>
                  <p>Social reach, engagement, and platform badges are not truth signals. When social content is retained, its identity, authenticity, attribution, original-source linkage, approved use, corroboration, and shared origin are evaluated.</p>
                </div>
                <dl>
                  <div><dt>Social passages</dt><dd>{socialEvidence.length}</dd></div>
                  <div><dt>Policy findings</dt><dd>{report.social_evidence_policy?.findings.length ?? 0}</dd></div>
                  <div><dt>Blocking findings</dt><dd>{blockingSocialCount}</dd></div>
                  <div><dt>Social-policy impact</dt><dd>{report.social_evidence_policy?.publication_blocked ? "Blocks publication" : report.social_evidence_policy ? "No blocker recorded" : "Not evaluated"}</dd></div>
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
              </div> : <section className="social-empty-state compact">
                <div><span>NO RETAINED SOCIAL EVIDENCE</span><h2>No social-media passage was retained in the evidence packet.</h2><p>No retained evidence item is classified as social-platform content. The ordinary Evidence view and the current integrity and disposition records remain authoritative. Whether social links served as discovery leads was not recorded.</p></div>
                <dl aria-label="Social evidence empty-state summary">
                  <div><dt>Retained social passages</dt><dd>0</dd></div>
                  <div><dt>Decisive social evidence</dt><dd>0</dd></div>
                  <div><dt>Social-policy blockers</dt><dd>{blockingSocialCount}</dd></div>
                  <div><dt>Social discovery leads</dt><dd>Not recorded</dd></div>
                  <div className="overall-review-state"><dt>Overall investigation status</dt><dd>{report.publication_decision?.human_review_required || report.verdict.human_review_required ? "Human review required" : overallPublicationReady ? "Publication permitted" : "Publication not permitted"}</dd><small>{report.publication_decision?.human_review_required || report.verdict.human_review_required ? "This status originates from the complete investigation; no social-policy blocker was recorded." : "This is the overall publication state, separate from social-evidence policy."}</small></div>
                </dl>
                <div className="social-empty-actions"><button onClick={() => setSection("Evidence")}>View all retained evidence</button><button onClick={() => setSection("Review brief")}>{report.publication_decision?.human_review_required || report.verdict.human_review_required ? "See why human review is required" : "Open review brief"}</button></div>
              </section>}

              {socialEvidence.length ? <p className="transparency-note"><b>Interpretation boundary:</b> authenticity means the account or capture was attributed with recorded evidence. It does not make every statement true. Relevance means topical match. It does not measure correctness, authority, independence, or probability.</p> : <details className="social-interpretation"><summary>How social evidence would be evaluated</summary><p>Authenticity would mean that an account or capture was attributed with recorded evidence; it would not make every statement true. Relevance would mean topical match, not correctness, authority, independence, or probability.</p></details>}
            </div>}
            {section === "Decision rationale" && <div className="decision-dashboard">
              <section className={`decision-hero ${overallPublicationReady ? "current" : "historical"}`}>
                <span>{overallPublicationReady ? "CURRENT VERDICT EXPLANATION" : "HISTORICAL PROVISIONAL VERDICT"}</span><h2>{report.verdict.concise_explanation}</h2>
                {!overallPublicationReady && <strong className="archived-explanation-label">Archived explanation — not a current conclusion</strong>}
                <p>{report.verdict.detailed_reasoning}</p>
                <div className="decision-badge">{overallPublicationReady ? titleCase(report.verdict.label) : `Provisional · ${titleCase(report.verdict.label)}`}</div>
              </section>
              {!overallPublicationReady && <section className="decision-authority-warning" role="alert"><div><span>EVIDENCE AUTHORITY CHANGED</span><h2>This persisted verdict is not currently publication-ready.</h2><p>The explanation above is retained for audit, but the current integrity and disposition rules remove one or more historical verdict links. The effective ledger below is authoritative for what the packet can support now.</p></div><dl><div><dt>Retained passages</dt><dd>{evidence.length}</dd></div><div><dt>Argument-eligible</dt><dd>{argumentEligibleCount}</dd></div><div><dt>Eligible for decisive use</dt><dd>{decisiveEligibleIds.size}</dd></div><div><dt>Historical links removed</dt><dd>{historicalVerdictEvidenceIds.size}</dd></div></dl><button onClick={() => setSection("Evidence")}>Resolve evidence blockers</button></section>}
              {unreflectedQuantifiers.length > 0 && <section className="claim-fidelity-warning" role="note"><b>Exact-wording check</b><p>The recorded claim contains the material qualifier{unreflectedQuantifiers.length === 1 ? "" : "s"} <strong>{unreflectedQuantifiers.map((term) => `“${term}”`).join(", ")}</strong>, but the persisted explanation does not repeat {unreflectedQuantifiers.length === 1 ? "it" : "them"} verbatim. Compare the explanation with the original claim before relying on the verdict.</p></section>}
              <section className="decision-path" aria-label="Decision derivation">
                <div><span>1</span><b>Effective evidence</b><small>{argumentEligibleCount} argument-eligible · {evidence.length} retained</small></div>
                <i aria-hidden="true">→</i><div><span>2</span><b>Effective argument ledger</b><small>{ledgerArguments.length} current proposition resolution{ledgerArguments.length === 1 ? "" : "s"}</small></div>
                <i aria-hidden="true">→</i><div><span>3</span><b>{overallPublicationReady ? "Judgment constraint" : "Historical judgment constraint"}</b><small>{report.judgment_policy?.allowed_labels.map(titleCase).join(" or ") ?? "Not reported"}</small></div>
                <i aria-hidden="true">→</i><div><span>4</span><b>{overallPublicationReady ? "Current verdict" : "Historical verdict"}</b><small>{titleCase(report.judgment_policy?.enforced_label ?? report.verdict.label)}{overallPublicationReady ? "" : " · publication blocked"}</small></div>
              </section>
              <div className="decision-columns">
                <section className="report-card">
                  <span>EFFECTIVE ARGUMENT LEDGER</span><h2>{ledgerArguments.filter((item) => item.resolution !== "unresolved").length} of {ledgerArguments.length} proposition{ledgerArguments.length === 1 ? "" : "s"} resolved</h2>
                  <p>This reconstruction uses only evidence that remains argument-eligible under current integrity and disposition rules. The persisted original remains available as audit history.</p>
                  <dl><div><dt>Supporting links</dt><dd>{aggregateLedger.supporting}</dd></div><div><dt>Contradictory links</dt><dd>{aggregateLedger.contradictory}</dd></div><div><dt>Qualifying links</dt><dd>{aggregateLedger.qualifying}</dd></div></dl>
                  {effectiveLedgerChanged && <small className="historical-note">The effective ledger differs from the persisted historical ledger.</small>}
                </section>
                <section className="report-card">
                  <span>{overallPublicationReady ? "CURRENT JUDGMENT CONSTRAINT" : "HISTORICAL POLICY DECISION"}</span><h2>{titleCase(report.judgment_policy?.enforced_label ?? report.verdict.label)}</h2>
                  <p>{overallPublicationReady ? (report.judgment_policy?.rationale ?? "No separate judgment-policy explanation was recorded.") : "This policy result was recorded against the historical ledger. It does not describe the current unresolved effective ledger."}</p>
                  {!overallPublicationReady && report.judgment_policy?.rationale && <small className="recorded-policy-rationale"><b>Recorded rationale:</b> {report.judgment_policy.rationale}</small>}
                  <dl><div><dt>Proposed verdict</dt><dd>{titleCase(report.judgment_policy?.proposed_label ?? report.verdict.label)}</dd></div><div><dt>Enforced verdict</dt><dd>{titleCase(report.judgment_policy?.enforced_label ?? report.verdict.label)}</dd></div><div><dt>Policy changed verdict</dt><dd>{report.judgment_policy?.changed ? "Yes" : "No"}</dd></div><div><dt>Allowed labels</dt><dd>{report.judgment_policy?.allowed_labels.map(titleCase).join(", ") ?? "—"}</dd></div><div><dt>Reason codes</dt><dd>{report.judgment_policy?.reason_codes.map(titleCase).join(", ") || "None recorded"}</dd></div></dl>
                </section>
              </div>
              <section className="proposition-ledger">
                <div><span>CURRENT PROPOSITION-LEVEL REASONING</span><h2>What the eligible packet resolves now</h2><p>An unresolved proposition cannot inherit support from historical or ineligible evidence links.</p></div>
                {compoundCoverageWarning && <div className="compound-coverage-warning"><b>Compound-claim coverage warning</b><p>Only {ledgerPropositions.length} combined proposition was persisted, but the claim appears to contain {candidateClaimClauses.length} material clauses. Independent resolution is unavailable for:</p><ol>{candidateClaimClauses.map((clause) => <li key={clause}>{clause}</li>)}</ol><button onClick={() => { setClaim(report.claim.text); window.scrollTo({ top: 0, behavior: "smooth" }); }}>Prepare follow-up claim</button><small>This only loads the original wording into the claim form for you to split or edit. It makes no search or model call. Costs can occur only if you submit a new investigation.</small></div>}
                {ledgerArguments.length ? <div className="proposition-table" role="table" aria-label="Argument ledger propositions">
                  <div className="proposition-row header" role="row"><b role="columnheader">Proposition</b><b role="columnheader">Resolution</b><b role="columnheader">Evidence links</b><b role="columnheader">Effect</b></div>
                  {ledgerArguments.map((argument) => { const proposition = ledgerPropositions.find((item) => item.proposition_id === argument.proposition_id); const historical = persistedLedgerArguments.find((item) => item.proposition_id === argument.proposition_id); const historicalCount = historical ? historical.supporting_evidence_ids.length + historical.contradictory_evidence_ids.length + historical.qualifying_evidence_ids.length : 0; const currentCount = argument.supporting_evidence_ids.length + argument.contradictory_evidence_ids.length + argument.qualifying_evidence_ids.length; return <div className={`proposition-row ${argument.resolution === "unresolved" ? "unresolved" : ""}`} role="row" key={argument.proposition_id}><div role="cell"><strong>{proposition?.text ?? "Proposition text not recorded"}</strong><small>{proposition?.material ? "Material to verdict" : "Non-material"}</small></div><div role="cell"><em>{titleCase(argument.resolution)}</em></div><div role="cell"><span>{argument.supporting_evidence_ids.length} support</span><span>{argument.contradictory_evidence_ids.length} contradict</span><span>{argument.qualifying_evidence_ids.length} qualify</span>{historicalCount > currentCount && <small>{historicalCount - currentCount} historical link{historicalCount - currentCount === 1 ? "" : "s"} removed</small>}</div><div role="cell"><p>{argument.unresolved_reasons.length ? argument.unresolved_reasons.join(" ") : argument.resolution === "qualified" ? "Material qualification limits an unqualified verdict." : "Resolution contributes to the permitted verdict labels."}</p></div></div>; })}
                </div> : <p className="empty-copy">No proposition-level argument records were persisted.</p>}
              </section>
              <section className="challenge-card">
                <div><span>CHALLENGER AND SUFFICIENCY FINDINGS</span><h2>{overallPublicationReady ? "What could weaken this decision" : "Current evidence gaps and challenges"}</h2></div>
                {effectiveLedger?.challenge_findings.map((finding) => <article key={finding.finding_id}><div><b>{titleCase(finding.kind)}</b><em>{titleCase(finding.severity)}</em></div><div><p>{finding.rationale.replace("The approved packet", "The current eligible packet")}</p>{finding.kind.includes("absolute") && materialQuantifiers.length > 0 && <small><b>Relevant claim wording:</b> {materialQuantifiers.map((term) => `“${term}”`).join(", ")}</small>}<small><b>Verdict effect:</b> {finding.kind === "insufficient_eligible_evidence" ? "No current verdict can be supported." : finding.severity === "blocking" ? "Blocks publication until resolved." : "Limits how strongly the conclusion can be stated."}</small></div><div>{finding.evidence_ids.map((id) => <button key={id} onClick={() => { const index = evidence.findIndex((item) => item.evidence_id === id); if (index >= 0) { setSelectedEvidence(index); setSection("Evidence"); } }}>Open evidence {shortId(id)} →</button>)}{!finding.evidence_ids.length && <small>No currently eligible evidence link was recorded for this finding.</small>}</div></article>)}
                {!effectiveLedger?.challenge_findings.length && <p>No deterministic challenger findings were recorded for the effective ledger.</p>}
              </section>
              <section className="verdict-alternatives"><div><span>WHY NOT ANOTHER VERDICT?</span><h2>{overallPublicationReady ? "Bounded label comparison" : "Current label comparison is blocked"}</h2></div>{overallPublicationReady ? <div><article><b>Supported</b><p>{aggregateLedger.qualifying || aggregateLedger.contradictory ? "Not selected because the effective ledger contains material qualifying or contradictory links." : "The persisted policy did not select this label."}</p></article><article><b>Contradicted</b><p>{aggregateLedger.contradictory === 0 ? "Not selected because the effective ledger records no contradictory evidence links." : "Contradictory links exist, but the complete ledger did not resolve the claim as contradicted."}</p></article>{report.judgment_policy?.allowed_labels.filter((label) => label !== (report.judgment_policy?.enforced_label ?? report.verdict.label)).map((label) => <article key={label}><b>{titleCase(label)}</b><p>Permitted by policy but not selected. No separate comparative rationale was persisted, so no stronger distinction is claimed.</p></article>)}</div> : <p className="blocked-comparison">The effective evidence packet does not currently support a defensible comparison among Supported, Contradicted, Mixed, or Misleading. The persisted {titleCase(report.verdict.label)} label is historical until the evidence blockers are resolved and judgment is rerun.</p>}</section>
              <section className={`decisive-list ${decisiveEvidenceGroups.length ? "" : "compact-empty"}`}>
                <span>CURRENTLY ELIGIBLE DECISIVE EVIDENCE</span>
                {decisiveEvidenceGroups.map((group) => <article key={`${group.source?.source_id}:${group.familyId}`}><header><div><strong>{group.source?.title ?? "Retained source"}</strong><small>{group.source?.publisher ?? "Publisher not recorded"}</small></div><em>Family {group.familyId ? shortId(group.familyId) : "unassigned"}</em></header>{group.items.map(({ item, roles }) => <button key={item.evidence_id} onClick={() => { const index = evidence.findIndex((candidate) => candidate.evidence_id === item.evidence_id); setSelectedEvidence(Math.max(0, index)); setSection("Evidence"); }}><b>{shortId(item.evidence_id)}</b><span>{roles.join(" · ")}</span><span>{titleCase(item.evidentiary_use)}</span><small>Open exact passage →</small></button>)}</article>)}
                {!decisiveEvidenceGroups.length && <p className="empty-copy">No passage is currently eligible for decisive use.</p>}
              </section>
              {historicalEvidenceGroups.length > 0 && <details className="decisive-list historical-evidence"><summary><span>HISTORICAL VERDICT EVIDENCE · CURRENTLY INELIGIBLE</span><b>{historicalVerdictEvidenceIds.size} link{historicalVerdictEvidenceIds.size === 1 ? "" : "s"} retained for audit</b></summary><p>These links explain the stored verdict but cannot currently satisfy argument or publication safeguards.</p>{historicalEvidenceGroups.map((group) => <article key={`historical-${group.source?.source_id}:${group.familyId}`}><header><div><strong>{group.source?.title ?? "Retained source"}</strong><small>{group.source?.publisher ?? "Publisher not recorded"}</small></div><em>Family {group.familyId ? shortId(group.familyId) : "unassigned"}</em></header>{group.items.map(({ item, roles }) => <button key={item.evidence_id} onClick={() => { const index = evidence.findIndex((candidate) => candidate.evidence_id === item.evidence_id); setSelectedEvidence(Math.max(0, index)); setSection("Evidence"); }}><b>{shortId(item.evidence_id)}</b><span>{roles.join(" · ")}</span><span>Ineligible · {titleCase(integrityByEvidence.get(item.evidence_id)?.approved_use ?? item.evidentiary_use)}</span><small>Inspect blocker →</small></button>)}</article>)}</details>}
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
            {section === "System architecture" && <SystemArchitectureView apiStatus={apiStatus} job={job} graph={graph} report={report} review={review} observedCost={displayedCost} observedTokens={displayedTokens} costScope={costScope} externalSearchPricing={externalSearchPricing} />}
            {section === "Evidence" && <EvidenceWorkspace
              report={report}
              sources={sources}
              selectedIndex={selectedEvidence}
              onSelect={setSelectedEvidence}
              openSocial={() => setSection("Social evidence")}
              openReview={() => setSection("Review brief")}
              prepareFreshInvestigation={() => {
                setInputMode("manual_claim");
                setClaim(report.claim.text);
                window.scrollTo({ top: 0, behavior: "smooth" });
              }}
              recordDisposition={recordEvidenceDisposition}
              dispositionBusy={busy}
              reviewerIdentity={reviewer}
              approverIdentity={approver}
              onReviewerIdentityChange={setReviewer}
              onApproverIdentityChange={setApprover}
            />}
            {["Citation audit", "Review history"].includes(section) && <div className="content-grid">
              <section className="evidence-panel">
                <div className="panel-title"><div><span>{section.toUpperCase()}</span><h2>{section === "Evidence" ? "Evidence packet" : section}</h2></div><span className="filter">{section === "Evidence" ? `${evidence.length} passages` : `${section === "Citation audit" ? report.effective_full_report_assurance?.final_audit.findings.length ?? report.full_report_assurance?.final_audit.findings.length ?? report.audits.length : review?.events.length ?? 0} records`}</span></div>
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
                {section === "Review history" && <ReviewHistoryView review={review} />}
              </section>
              <aside className="review-panel">
                <div className="review-kicker">HUMAN REVIEW</div>
                {!graph ? <div className="approved-state"><div className="approval-mark">{report.verdict.human_review_required || effectiveCitationStatus === "blocked" ? "!" : "✓"}</div><h2>{report.verdict.human_review_required || effectiveCitationStatus === "blocked" ? "Human review required" : "No human review required"}</h2><p>{effectiveCitationStatus === "blocked" ? "The current citation-eligibility gate is blocked. Historical approval does not make this report publication-ready." : report.verdict.human_review_required ? report.verdict.review_reason ?? "The persisted report requires review, but its live graph thread is not loaded in this browser." : "This completed report was publication-ready under the recorded deterministic safeguards."}</p><dl><div><dt>Verdict</dt><dd>{titleCase(report.verdict.label)}</dd></div><div><dt>Effective citation gate</dt><dd>{titleCase(effectiveCitationStatus ?? "recorded")}</dd></div><div><dt>Review record</dt><dd>{review ? `${review.events.length} event(s)` : "None required"}</dd></div></dl></div>
                  : reviewPending ? <>
                    <h2>{approvalBlockedByEvidence ? "Resolve evidence blockers" : job?.interruption?.allowed_decisions.includes("approve") ? "Confirm final verdict" : "Evidence retrieval needs attention"}</h2>
                    <p className="reason">{approvalBlockedByEvidence ? "Final approval is unavailable because the effective citation or evidence-integrity gate is blocked. Request evidence, revise, or reject the packet." : review?.request.reason}</p>
                    <label>Decision<select value={effectiveDecisionKind} onChange={(event) => setDecisionKind(event.target.value)}>{reviewDecisionOptions.filter(([value]) => allowedReviewDecisions.includes(value)).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
                    {reviewConstruction && <label>Verification construction decision<select value={effectiveVerificationDisposition} onChange={(event) => setVerificationDisposition(event.target.value)}>{verificationDispositionOptions.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>}
                    {effectiveDecisionKind === "revise" && <label>Revised verdict<select value={revisedVerdict} onChange={(event) => setRevisedVerdict(event.target.value)}>{["supported", "contradicted", "mixed", "misleading", "unsupported", "unverifiable"].map((label) => <option value={label} key={label}>{titleCase(label)}</option>)}</select></label>}
                    <label>Review rationale<textarea value={rationale} onChange={(event) => setRationale(event.target.value)} /></label>
                    <label>Reviewer identity<input value={reviewer} onChange={(event) => setReviewer(event.target.value)} /></label>
                    {["approve", "revise"].includes(effectiveDecisionKind) && <label>Distinct approver identity<input value={approver} onChange={(event) => setApprover(event.target.value)} /></label>}
                    <button className="primary" onClick={saveDecision} disabled={busy || approvalBlockedByEvidence && effectiveDecisionKind === "approve" || rationale.trim().length < 3 || reviewer.trim().length < 3 || (["approve", "revise"].includes(effectiveDecisionKind) && (approver.trim().length < 3 || approver.trim().toLocaleLowerCase() === reviewer.trim().toLocaleLowerCase()))}>{busy ? "Saving…" : "Save decision & resume workflow"}</button>
                    <small className="immutable">The decision is appended to the immutable audit history.</small>
                  </>
                  : <div className="approved-state"><div className="approval-mark">{graph.status === "complete" ? "✓" : "!"}</div><h2>{titleCase(graph.status)}</h2><p>The graph resumed from its SQLite checkpoint without repeating completed research nodes.</p><dl><div><dt>Final verdict</dt><dd>{graph.final_verdict ? titleCase(graph.final_verdict) : "Not issued"}</dd></div><div><dt>Reviewer</dt><dd>{graph.reviewer_identity ?? "—"}</dd></div><div><dt>Audit chain</dt><dd>{review?.chain_valid ? "Verified" : "Pending"}</dd></div></dl></div>}
              </aside>
            </div>
            }
            </div>
          </>
        )}
      </section>
    </main>
  );
}

