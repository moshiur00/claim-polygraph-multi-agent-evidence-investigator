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
    numerical: { required: boolean; status: string; claim_values: string[]; evidence_values: string[]; issues: string[] };
    temporal: { required: boolean; status: string; reference_date: string | null; issues: string[] };
    limitations: string[];
  } | null;
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
  full_report_assurance: {
    publication_status: string; material_sentence_count: number;
    audited_material_sentence_count: number; critical_failure_count: number;
    revisions: unknown[]; blocking_reasons: string[];
  } | null;
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
  decisions: Array<{ decision_id: string; kind: string; reviewer_identity: string; rationale: string; proposed_verdict: string | null; created_at: string }>;
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
  const citationRate = report?.audits.length
    ? Math.round(report.audits.filter((audit) => audit.support_level === "full").length / report.audits.length * 100) : 0;
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
  const judgmentReady = report?.readiness?.state !== "human_review_required" && !report?.verdict.human_review_required;
  const socialPolicyReady = !report?.social_evidence_policy?.publication_blocked;
  const authoritativePublicationReady = report?.publication_decision
    ? report.publication_decision.publication_allowed
    : true;
  const overallPublicationReady = Boolean(
    report && citationReady && judgmentReady && socialPolicyReady
    && authoritativePublicationReady && contaminatedEvidence.length === 0,
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
              <div><small>WORKFLOW POSITION</small><strong>{reviewPending ? "Human review" : overallPublicationReady ? "Ready to publish" : titleCase(graph?.status ?? report.investigation.status)}</strong><em>{evidence.length} evidence passage{evidence.length === 1 ? "" : "s"} · {report.audits.length} audited sentence{report.audits.length === 1 ? "" : "s"}</em></div>
            </section>
            <div className="summary-row">
              <div><span>{graph?.final_verdict ? "FINAL VERDICT" : "PROVISIONAL VERDICT"}</span><strong>{titleCase(graph?.final_verdict ?? report.verdict.label)}</strong></div>
              <div><span>CONFIDENCE <button className="info-dot" aria-label="Explain confidence" title="A calibrated probability of verdict correctness. A dash means the system has not been empirically calibrated and will not invent a probability.">?</button></span><strong>{report.verdict.confidence == null ? "—" : `${Math.round(report.verdict.confidence * 100)}%`}</strong><small>{report.verdict.confidence == null ? "Not calibrated" : "Calibrated probability"}</small></div>
              <div><span>CITATION SUPPORT <button className="info-dot" aria-label="Explain citation support" title="Material report sentences marked fully supported by their cited evidence, divided by all audited material sentences.">?</button></span><strong>{citationRate}%</strong><small>{report.audits.filter((audit) => audit.support_level === "full").length}/{report.audits.length} audited sentences</small></div>
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
                <div><span>REVIEW RECOMMENDATION</span><h2>{reviewerRecommendation}</h2><p>{overallPublicationReady ? "The packet passes both judgment-readiness and full-report citation gates, with no detected passage-hygiene warning." : "Do not treat citation-ready as publication-ready. One or more evidence, verification, provenance, or passage-quality safeguards still requires attention."}</p></div>
                <div className="review-verdict"><small>PROVISIONAL FACTUAL VERDICT</small><strong>{titleCase(report.verdict.label)}</strong><em>{report.verdict.confidence == null ? "Confidence not calibrated" : `${Math.round(report.verdict.confidence * 100)}% calibrated confidence`}</em></div>
              </section>
              <section className="review-gates">
                <article><span>JUDGMENT READINESS</span><strong>{titleCase(report.readiness?.state ?? "not reported")}</strong><p>{report.readiness?.state === "human_review_required" ? "Blocking safeguards remain; the verdict is provisional." : "The deterministic readiness gate does not require escalation."}</p></article>
                <article><span>CITATION ASSURANCE</span><strong>{titleCase(report.full_report_assurance?.publication_status ?? "not reported")}</strong><p>{citationReady ? "The report sentences passed citation matching. This does not establish source authority or independence." : "The report has citation-assurance failures."}</p></article>
                <article><span>INDEPENDENCE</span><strong>{titleCase(report.provenance?.requirement_state ?? "not reported")}</strong><p>{report.provenance ? `${report.provenance.confirmed_independent_lower_bound} confirmed; up to ${report.provenance.possible_independent_upper_bound} possible; ${report.provenance.unresolved_dependency_count} unresolved relationship(s).` : "No provenance assessment was recorded."}</p></article>
                <article><span>VERIFICATION</span><strong>{Math.round((report.readiness?.verification_completeness ?? 0) * 100)}% complete</strong><p>{report.context_verification?.temporal.issues.join(" ") || report.context_verification?.numerical.issues.join(" ") || "No unresolved numerical or temporal issue was recorded."}</p></article>
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
                <span>DECISION</span><h2>{titleCase(graph?.final_verdict ?? report.verdict.label)}</h2>
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
                <span>VERIFICATION</span><h2>{Math.round((report.readiness?.verification_completeness ?? 0) * 100)}% complete</h2>
                <dl><div><dt>Material claim coverage</dt><dd>{Math.round((report.readiness?.material_coverage ?? 0) * 100)}%</dd></div><div><dt>Numerical check required</dt><dd>{report.plan.requires_numerical_check ? "Yes" : "No"}</dd></div><div><dt>Temporal check required</dt><dd>{report.plan.requires_temporal_check ? "Yes" : "No"}</dd></div></dl>
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
            {section === "Verification" && <div className="verification-dashboard">
              <section className="report-card"><span>NUMERICAL CONTEXT</span><h2>{titleCase(report.context_verification?.numerical.status ?? "not reported")}</h2><dl><div><dt>Required</dt><dd>{report.context_verification?.numerical.required ? "Yes" : "No"}</dd></div><div><dt>Claim values</dt><dd>{report.context_verification?.numerical.claim_values.join(", ") || "None extracted"}</dd></div><div><dt>Evidence values</dt><dd>{report.context_verification?.numerical.evidence_values.slice(0, 8).join(", ") || "None extracted"}</dd></div></dl></section>
              <section className="report-card"><span>TEMPORAL CONTEXT</span><h2>{titleCase(report.context_verification?.temporal.status ?? "not reported")}</h2><dl><div><dt>Required</dt><dd>{report.context_verification?.temporal.required ? "Yes" : "No"}</dd></div><div><dt>Reference date</dt><dd>{report.context_verification?.temporal.reference_date ?? "Not specified"}</dd></div><div><dt>Issues</dt><dd>{report.context_verification?.temporal.issues.length ?? 0}</dd></div></dl></section>
              <section className="reason-list"><span>READINESS SIGNALS</span>{report.readiness?.reason_codes.map((reason) => <div key={reason}><b>{titleCase(reason)}</b><p>A persisted safeguard contributing to the current readiness state.</p></div>)}</section>
              <section className="reason-list"><span>KNOWN LIMITATIONS</span>{[...(report.context_verification?.limitations ?? []), ...(report.readiness?.limitations ?? [])].map((limitation, index) => <div key={index}><b>Limitation {index + 1}</b><p>{limitation}</p></div>)}</section>
            </div>}
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
                <div className="panel-title"><div><span>{section.toUpperCase()}</span><h2>{section === "Evidence" ? "Evidence packet" : section}</h2></div><span className="filter">{section === "Evidence" ? `${evidence.length} passages` : `${section === "Citation audit" ? report.audits.length : review?.events.length ?? 0} records`}</span></div>
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
                {section === "Citation audit" && <div className="citation-records">{report.audits.map((audit, index) => <article key={audit.sentence_id ?? index}><div><b>Sentence {index + 1}</b><em className={`support-${audit.support_level}`}>{titleCase(audit.support_level)}</em><span>{audit.cited_evidence_ids.length} citation{audit.cited_evidence_ids.length === 1 ? "" : "s"}</span></div><blockquote>{audit.sentence}</blockquote>{audit.explanation && <p>{audit.explanation}</p>}{audit.issue_type && <small>Issue: {titleCase(audit.issue_type)}</small>}{audit.suggested_revision && <details><summary>Suggested bounded revision</summary><p>{audit.suggested_revision}</p></details>}<div className="citation-links">{audit.cited_evidence_ids.map((id) => <button key={id} onClick={() => { const evidenceIndex = evidence.findIndex((item) => item.evidence_id === id); setSelectedEvidence(Math.max(0, evidenceIndex)); setSection("Evidence"); }}>{shortId(id)} →</button>)}</div></article>)}</div>}
                {section === "Review history" && <div className="record-list">{review?.events.map((event) => <article key={event.sequence}><b>{event.sequence}. {titleCase(event.action)}</b><span>{event.actor_identity}</span></article>)}{!review && <p className="empty-copy">Start a review workflow to create an immutable history.</p>}</div>}
              </section>
              <aside className="review-panel">
                <div className="review-kicker">HUMAN REVIEW</div>
                {!graph ? <div className="approved-state"><div className="approval-mark">{report.verdict.human_review_required ? "!" : "✓"}</div><h2>{report.verdict.human_review_required ? "Human review required" : "No human review required"}</h2><p>{report.verdict.human_review_required ? report.verdict.review_reason ?? "The persisted report requires review, but its live graph thread is not loaded in this browser." : "This completed report was publication-ready under the recorded deterministic safeguards."}</p><dl><div><dt>Verdict</dt><dd>{titleCase(report.verdict.label)}</dd></div><div><dt>Publication</dt><dd>{titleCase(report.full_report_assurance?.publication_status ?? "recorded")}</dd></div><div><dt>Review record</dt><dd>{review ? `${review.events.length} event(s)` : "None required"}</dd></div></dl></div>
                  : reviewPending ? <><h2>{job?.interruption?.allowed_decisions.includes("approve") ? "Confirm final verdict" : "Evidence retrieval needs attention"}</h2><p className="reason">{review?.request.reason}</p><label>Decision<select value={effectiveDecisionKind} onChange={(event) => setDecisionKind(event.target.value)}>{reviewDecisionOptions.filter(([value]) => allowedReviewDecisions.includes(value)).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>{effectiveDecisionKind === "revise" && <label>Revised verdict<select value={revisedVerdict} onChange={(event) => setRevisedVerdict(event.target.value)}>{["supported", "contradicted", "mixed", "misleading", "unsupported", "unverifiable"].map((label) => <option value={label} key={label}>{titleCase(label)}</option>)}</select></label>}<label>Review rationale<textarea value={rationale} onChange={(event) => setRationale(event.target.value)} /></label><label>Reviewer identity<input value={reviewer} onChange={(event) => setReviewer(event.target.value)} /></label>{["approve", "revise"].includes(effectiveDecisionKind) && <label>Distinct approver identity<input value={approver} onChange={(event) => setApprover(event.target.value)} /></label>}<button className="primary" onClick={saveDecision} disabled={busy || rationale.trim().length < 3 || reviewer.trim().length < 3 || (["approve", "revise"].includes(effectiveDecisionKind) && (approver.trim().length < 3 || approver.trim().toLocaleLowerCase() === reviewer.trim().toLocaleLowerCase()))}>{busy ? "Saving…" : "Save decision & resume graph"}</button><small className="immutable">The decision is appended to the immutable audit history.</small></>
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

