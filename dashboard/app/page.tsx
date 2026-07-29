"use client";
/* eslint-disable react-hooks/set-state-in-effect */

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

type Investigation = { investigation_id: string; input_claim: string; status: string; stage: string };
type Evidence = { evidence_id: string; source_id: string; passage: string; stance: string; relevance_score: number; evidence_family_id: string | null };
type Source = { source_id: string; title: string; publisher: string | null; source_type: string; url: string };
type Report = {
  investigation: Investigation;
  claim: { claim_id: string; text: string };
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
  audits: Array<{ support_level: string; cited_evidence_ids: string[] }>;
  independence_analysis: { independent_family_count: number; required_independent_families: number; limitations: string[] } | null;
  provenance: {
    confirmed_independent_lower_bound: number; possible_independent_upper_bound: number;
    unresolved_dependency_count: number; requirement_state: string; limitations: string[];
  } | null;
  readiness: {
    state: string; material_coverage: number; verification_completeness: number;
    citation_audit_complete: boolean; reason_codes: string[]; limitations: string[];
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

const graphOrder = ["normalize", "research", "consolidate", "verify_context", "build_argument_ledger", "draft_verdict", "audit_citations", "assess_readiness", "route_review", "interrupt_for_review", "finalize"] as const;
const graphLabels: Record<string, string> = {
  normalize: "Normalize", research: "Research", consolidate: "Consolidate",
  verify_context: "Verify context", build_argument_ledger: "Argument ledger",
  draft_verdict: "Draft verdict", audit_citations: "Citation audit",
  assess_readiness: "Readiness", route_review: "Route review",
  interrupt_for_review: "Human review", finalize: "Final report",
};
const investigationStageOrder = ["claim_analysis", "planning", "research", "evidence_analysis", "judgment", "citation_audit", "complete"] as const;
const defaultApi = "http://127.0.0.1:8000";
const titleCase = (value: string) => value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
const shortId = (value: string) => value.slice(0, 8).toUpperCase();

export default function Home() {
  const [apiBase, setApiBase] = useState(defaultApi);
  const [apiDraft, setApiDraft] = useState(defaultApi);
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [graph, setGraph] = useState<GraphSnapshot | null>(null);
  const [review, setReview] = useState<ReviewHistory | null>(null);
  const [section, setSection] = useState("Overview");
  const [selectedEvidence, setSelectedEvidence] = useState(0);
  const [claim, setClaim] = useState("");
  const [inputMode, setInputMode] = useState<"manual_claim" | "article_text" | "public_url">("manual_claim");
  const [claimCandidates, setClaimCandidates] = useState<ClaimCandidate[]>([]);
  const [decisionKind, setDecisionKind] = useState("approve");
  const [revisedVerdict, setRevisedVerdict] = useState("mixed");
  const [rationale, setRationale] = useState("The cited evidence supports this review decision.");
  const [reviewer, setReviewer] = useState("Md Moshiur Rahman");
  const [busy, setBusy] = useState(false);
  const [activity, setActivity] = useState<"investigation" | "extraction" | "review" | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [job, setJob] = useState<InvestigationJob | null>(null);
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
  const jobActive = job != null && !["completed", "cancelled", "failed", "dead_letter"].includes(job.job.status);
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
    void request<InvestigationJob>(`/api/investigation-jobs/${storedJob}`)
      .then((restored) => {
        if (["completed", "cancelled", "failed", "dead_letter"].includes(restored.job.status)) {
          window.localStorage.removeItem("claim-polygraph-active-job");
          setJob(null);
          return;
        }
        setJob(restored);
      })
      .catch(() => window.localStorage.removeItem("claim-polygraph-active-job"));
  }, [request]);
  useEffect(() => {
    if (!job?.job.job_id || !jobActive) return;
    const stream = new EventSource(`${apiBase}/api/investigation-jobs/${job.job.job_id}/events?after=0&follow=true`);
    stream.addEventListener("job_state", (event) => {
      const state = JSON.parse((event as MessageEvent).data) as InvestigationJob;
      setJob(state);
      if (state.investigation_id) setSelectedId(state.investigation_id);
      if (["completed", "cancelled", "failed", "dead_letter"].includes(state.job.status)) {
        stream.close();
        window.localStorage.removeItem("claim-polygraph-active-job");
        if (state.job.status === "completed" && state.investigation_id) {
          void request<Report>(`/api/investigations/${state.investigation_id}/report`).then(async (completed) => {
            setReport(completed);
            setInvestigations(await request<Investigation[]>("/api/investigations"));
            const snapshot = await request<GraphSnapshot>(`/api/graph-runs/${state.investigation_id}`).catch(() => null);
            setGraph(snapshot);
            setTelemetry(await request<TelemetrySnapshot>("/api/operations/telemetry"));
            setActivity(null);
          });
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
  const citationRate = report?.audits.length
    ? Math.round(report.audits.filter((audit) => audit.support_level === "full").length / report.audits.length * 100) : 0;
  const reviewPending = graph?.status === "review_required" && review?.decisions.length === 0;
  const stageNode: Record<string, number> = { created: 0, claim_analysis: 0, planning: 1, research: 2, evidence_analysis: 3, judgment: 4, citation_audit: 5, complete: 6 };
  const liveNodeIndex = liveStage ? (stageNode[liveStage] ?? 0) : 0;
  const completedGraphNodes = graph?.completed_nodes.filter((node) => graphOrder.includes(node as typeof graphOrder[number])).length ?? 0;
  const graphProgress = graph ? Math.round(completedGraphNodes / graphOrder.length * 100) : 0;

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
      const created = await request<InvestigationJob>("/api/investigation-jobs", {
        method: "POST",
        body: JSON.stringify({ claim: selectedClaim, idempotency_key: `dashboard:${crypto.randomUUID()}` }),
      });
      window.localStorage.setItem("claim-polygraph-active-job", created.job.job_id);
      setJob(created); setLiveStage("created"); setReport(null); setGraph(null); setReview(null);
      setClaim(""); setClaimCandidates([]); setError(null);
  }

  async function cancelJob() {
    if (!jobActive || !job) return;
    const cancelled = await request<InvestigationJob>(`/api/investigation-jobs/${job.job.job_id}/cancel`, {
      method: "POST", headers: { "X-Reviewer-Identity": reviewer },
    });
    setJob(cancelled);
  }

  async function startReview() {
    if (!report || !evidence.length) return; setBusy(true); setActivity("review");
    try {
      const payload = await request<{ graph: GraphSnapshot; review: ReviewRequest | null }>("/api/graph-runs", {
        method: "POST",
        body: JSON.stringify({
          investigation_id: report.investigation.investigation_id,
          claim_id: report.claim.claim_id,
          graph: {
            claim_text: report.claim.text,
            approved_evidence_ids: evidence.map((item) => item.evidence_id),
            authoritative_verdict: report.verdict.label,
            review_required: true,
            review_reason: report.verdict.review_reason ?? "A reviewer requested confirmation before publication.",
          },
        }),
      });
      setGraph(payload.graph);
      if (payload.review) setReview(await request<ReviewHistory>(`/api/reviews/${payload.review.request_id}`));
      setError(null);
    } catch (reason) { setError((reason as Error).message); } finally { setBusy(false); setActivity(null); }
  }

  async function saveDecision() {
    if (!review) return; setBusy(true); setActivity("review");
    try {
      const decision: Record<string, unknown> = { kind: decisionKind, reviewer_identity: reviewer, rationale };
      if (decisionKind === "revise") decision.revised_verdict = revisedVerdict;
      const result = await request<{ graph: GraphSnapshot; review: ReviewHistory }>(
        `/api/reviews/${review.request.request_id}/decisions`,
        {
          method: "POST", headers: { "X-Reviewer-Identity": reviewer },
          body: JSON.stringify({ expected_sequence: review.events.length, decision }),
        },
      );
      setGraph(result.graph); setReview(result.review); setError(null);
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
            <button key={item.investigation_id} className={selectedId === item.investigation_id ? "case active" : "case"} onClick={() => { setSelectedId(item.investigation_id); setGraph(null); setReview(null); }}>
              <b>{shortId(item.investigation_id)}</b><small>{item.input_claim}</small>
            </button>
          ))}
        </div>
        <div className="phase-card"><span>{apiStatus?.live_research ? "LIVE WEB RESEARCH" : "FIXTURE RESEARCH"}</span><strong>{titleCase(apiStatus?.orchestrator ?? "connecting")} orchestrator</strong><div className="meter"><i /></div><small>Retrieval · {apiStatus?.retrieval_provider ?? "Not reported"}</small><small>Reasoning · {apiStatus?.model_provider ?? "Not reported"}</small></div>
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
            <span className={graph?.status === "completed" ? "status complete" : "status"}><i /> {graph ? titleCase(graph.status) : report ? titleCase(report.investigation.status) : "Ready"}</span>
            {report && <a className="ghost" href={`${apiBase}/api/investigations/${report.investigation.investigation_id}/report?format=markdown`} target="_blank">Export</a>}
          </div>
        </header>

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
          <div className="graph-progress" role="progressbar" aria-valuenow={Math.round((liveNodeIndex + 1) / investigationStageOrder.length * 100)} aria-valuemin={0} aria-valuemax={100}><i style={{width: `${Math.round((liveNodeIndex + 1) / investigationStageOrder.length * 100)}%`}} /></div>
          <div className="graph investigation-graph graph-running">
            {investigationStageOrder.map((node, index) => <div className={`node ${index < liveNodeIndex ? "done" : index === liveNodeIndex ? "active" : "waiting"}`} key={node}><div>{index < liveNodeIndex ? "✓" : index === liveNodeIndex ? "↻" : index + 1}</div><span>{titleCase(node)}</span>{index < investigationStageOrder.length - 1 && <i />}</div>)}
          </div>
          <p>InvestigationService is producing the authoritative evidence packet. The separate review and publication workflow begins after this research completes.</p>
        </section>}
        {claimCandidates.length > 0 && <section className="record-list" aria-label="Extracted claim candidates">
          {claimCandidates.map((candidate) => <article key={candidate.candidate_id}>
            <b>{candidate.rank}. {candidate.text}</b>
            <span>Check-worthiness {Math.round(candidate.checkworthiness * 100)}%</span>
            <button className="ghost" disabled={busy} onClick={() => { setBusy(true); setActivity("investigation"); void investigateCandidate(candidate.text).catch((reason: Error) => setError(reason.message)).finally(() => { setBusy(false); setActivity(null); }); }}>Investigate this claim</button>
          </article>)}
        </section>}
        {error && <div className="error-banner" role="alert">{error}</div>}

        {!report ? (
          <section className="empty-state">
            <span>CONNECTED EVIDENCE WORKSPACE</span><h2>{connected ? "Submit your first claim" : "Connect the evidence API"}</h2>
            <p>{connected ? "The investigation service will produce a typed evidence packet and citation-grounded verdict." : "Start the local API, then retry. You can also change its address below."}</p>
            <form onSubmit={saveApiAddress}><input aria-label="API address" value={apiDraft} onChange={(event) => setApiDraft(event.target.value)} /><button className="ghost">Save & retry</button></form>
          </section>
        ) : (
          <>
            <div className="summary-row">
              <div><span>{graph?.final_verdict ? "FINAL VERDICT" : "PROVISIONAL VERDICT"}</span><strong>{titleCase(graph?.final_verdict ?? report.verdict.label)}</strong></div>
              <div><span>CONFIDENCE <button className="info-dot" aria-label="Explain confidence" title="A calibrated probability of verdict correctness. A dash means the system has not been empirically calibrated and will not invent a probability.">?</button></span><strong>{report.verdict.confidence == null ? "—" : `${Math.round(report.verdict.confidence * 100)}%`}</strong><small>{report.verdict.confidence == null ? "Not calibrated" : "Calibrated probability"}</small></div>
              <div><span>CITATION SUPPORT <button className="info-dot" aria-label="Explain citation support" title="Material report sentences marked fully supported by their cited evidence, divided by all audited material sentences.">?</button></span><strong>{citationRate}%</strong><small>{report.audits.filter((audit) => audit.support_level === "full").length}/{report.audits.length} audited sentences</small></div>
              <div><span>INDEPENDENT FAMILIES <button className="info-dot" aria-label="Explain evidence families" title="Groups of sources that appear to originate independently. Multiple pages repeating one original report count as one family.">?</button></span><strong>{report.independence_analysis?.independent_family_count ?? "—"}</strong><small>Target {report.plan.minimum_independent_families}</small></div>
              <div><span>EVIDENCE ITEMS</span><strong>{evidence.length}</strong></div>
            </div>
            <div className="graph-card">
              <div className="card-heading"><div><span>REVIEW AND PUBLICATION WORKFLOW</span><h2>{graph ? titleCase(graph.status) : apiStatus?.orchestrator === "direct" ? "Direct rollback selected" : "Awaiting review workflow"}</h2></div>{graph ? <div className="graph-progress-label"><strong>{graphProgress}%</strong><small>{completedGraphNodes} of {graphOrder.length} nodes checkpointed</small></div> : apiStatus?.orchestrator === "direct" ? <button className="ghost" onClick={startReview} disabled={busy || !evidence.length}>Start review workflow</button> : null}</div>
              {graph && <div className="graph-progress" role="progressbar" aria-valuenow={graphProgress} aria-valuemin={0} aria-valuemax={100} aria-label="Checkpointed graph progress"><i style={{width: `${graphProgress}%`}} /></div>}
              <div className="graph">
                {graphOrder.map((node, index) => {
                  const done = graph?.completed_nodes.includes(node);
                  const active = graph?.status === "review_required" && node === "interrupt_for_review";
                  return <div className={`node ${done ? "done" : active ? "active" : "waiting"}`} key={node}><div>{done ? "✓" : active ? "!" : index + 1}</div><span>{graphLabels[node]}</span>{index < graphOrder.length - 1 && <i />}</div>;
                })}
              </div>
            </div>
            <div className="tabs" role="tablist">
              {["Overview", "Decision rationale", "Evidence", "Verification", "Citation audit", "Review history"].map((item) => <button key={item} role="tab" aria-selected={section === item} className={section === item ? "active" : ""} onClick={() => setSection(item)}>{item}</button>)}
            </div>
            {section === "Overview" && <div className="report-dashboard">
              <section className="report-card verdict-card">
                <span>DECISION</span><h2>{titleCase(graph?.final_verdict ?? report.verdict.label)}</h2>
                <p>{report.readiness?.state === "human_review_required" ? "The evidence points to this verdict, but one or more safeguards require human review." : "The evidence packet has passed the current deterministic readiness checks."}</p>
                <dl><div><dt>Readiness</dt><dd>{titleCase(report.readiness?.state ?? "not reported")}</dd></div><div><dt>Publication</dt><dd>{titleCase(report.full_report_assurance?.publication_status ?? "not reported")}</dd></div><div><dt>Critical citation failures</dt><dd>{report.full_report_assurance?.critical_failure_count ?? "—"}</dd></div></dl>
              </section>
              <section className="report-card">
                <span>RESEARCH COVERAGE</span><h2>{evidence.length} retained passages</h2>
                <div className="stance-bars">{["supporting", "contradictory", "qualifying", "context"].map((stance) => { const count = evidence.filter((item) => item.stance === stance).length; return <div key={stance}><label>{titleCase(stance)} <b>{count}</b></label><i><b style={{width: `${evidence.length ? Math.max(4, count / evidence.length * 100) : 0}%`}} /></i></div>; })}</div>
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
              <details className="score-guide">
                <summary>How to read scores and safeguards</summary>
                <div><b>Relevance</b><p>A model-assigned claim-to-passage match from 0–100%. It measures topical usefulness, not source truth, quality, or verdict confidence.</p></div>
                <div><b>Citation support</b><p>The share of audited material sentences fully supported by their cited passages.</p></div>
                <div><b>Readiness</b><p>A deterministic completeness gate. It is deliberately separate from probability or confidence.</p></div>
                <div><b>Independent families</b><p>Source-origin groups. Repetition across dependent sources does not increase the confirmed independent count.</p></div>
              </details>
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
            {["Evidence", "Citation audit", "Review history"].includes(section) && <div className="content-grid">
              <section className="evidence-panel">
                <div className="panel-title"><div><span>{section.toUpperCase()}</span><h2>{section === "Evidence" ? "Evidence packet" : section}</h2></div><span className="filter">{section === "Evidence" ? `${evidence.length} passages` : `${section === "Citation audit" ? report.audits.length : review?.events.length ?? 0} records`}</span></div>
                {section === "Evidence" && <div className="evidence-layout">
                  <div className="evidence-list">
                    {evidence.map((item, index) => {
                      const source = sources.get(item.source_id);
                      return <button className={selectedEvidence === index ? "evidence-item active" : "evidence-item"} onClick={() => setSelectedEvidence(index)} key={item.evidence_id}><div><span>{shortId(item.evidence_id)}</span><b>{titleCase(item.stance)}</b></div><strong>{source?.publisher ?? source?.title ?? "Stored source"}</strong><p>{item.passage}</p></button>;
                    })}
                    {!evidence.length && <p className="empty-copy">No retained evidence passages.</p>}
                  </div>
                  <article className="passage">
                    {selected ? <><div className="passage-meta"><span>EXACT PASSAGE</span><b>{shortId(selected.evidence_id)}</b></div><blockquote>“{selected.passage}”</blockquote><dl><div><dt>Source</dt><dd>{sources.get(selected.source_id)?.title ?? "Stored source"}</dd></div><div><dt>Source type</dt><dd>{titleCase(sources.get(selected.source_id)?.source_type ?? "unknown")}</dd></div><div><dt>Relevance <button className="info-dot" title="Claim-to-passage topical match. It is not a truth, quality, or confidence score." aria-label="Explain relevance score">?</button></dt><dd>{Math.round(selected.relevance_score * 100)}%</dd></div><div><dt>Evidence family</dt><dd>{selected.evidence_family_id ? shortId(selected.evidence_family_id) : "Unassigned"}</dd></div></dl><div className="score-explanation"><b>What {Math.round(selected.relevance_score * 100)}% means</b><p>The passage was rated as highly related to this claim. This score does not establish that the passage is correct or independent; those are evaluated separately.</p></div><div className="support-note">Citation data loaded from the authoritative report.</div></> : <p className="empty-copy">Select an evidence passage.</p>}
                  </article>
                </div>}
                {section === "Citation audit" && <div className="record-list">{report.audits.map((audit, index) => <article key={index}><b>Sentence {index + 1} · {titleCase(audit.support_level)}</b><span>{audit.cited_evidence_ids.length} citation{audit.cited_evidence_ids.length === 1 ? "" : "s"}</span></article>)}</div>}
                {section === "Review history" && <div className="record-list">{review?.events.map((event) => <article key={event.sequence}><b>{event.sequence}. {titleCase(event.action)}</b><span>{event.actor_identity}</span></article>)}{!review && <p className="empty-copy">Start a review workflow to create an immutable history.</p>}</div>}
              </section>
              <aside className="review-panel">
                <div className="review-kicker">HUMAN REVIEW</div>
                {!graph ? <><h2>Start durable review</h2><p className="reason">The evidence packet is complete. Start LangGraph to checkpoint its path and create a review request.</p><button className="primary" onClick={startReview} disabled={busy || !evidence.length}>Start review workflow</button></>
                  : reviewPending ? <><h2>Confirm final verdict</h2><p className="reason">{review?.request.reason}</p><label>Decision<select value={decisionKind} onChange={(event) => setDecisionKind(event.target.value)}><option value="approve">Approve provisional verdict</option><option value="revise">Revise verdict</option><option value="request_evidence">Request more evidence</option><option value="reject">Reject packet</option></select></label>{decisionKind === "revise" && <label>Revised verdict<select value={revisedVerdict} onChange={(event) => setRevisedVerdict(event.target.value)}>{["supported", "contradicted", "mixed", "misleading", "unsupported", "unverifiable"].map((label) => <option value={label} key={label}>{titleCase(label)}</option>)}</select></label>}<label>Review rationale<textarea value={rationale} onChange={(event) => setRationale(event.target.value)} /></label><label>Reviewer identity<input value={reviewer} onChange={(event) => setReviewer(event.target.value)} /></label><button className="primary" onClick={saveDecision} disabled={busy || rationale.trim().length < 3 || reviewer.trim().length < 3}>{busy ? "Saving…" : "Save decision & resume graph"}</button><small className="immutable">The decision is appended to the immutable audit history.</small></>
                  : <div className="approved-state"><div className="approval-mark">{graph.status === "completed" ? "✓" : "!"}</div><h2>{titleCase(graph.status)}</h2><p>The graph resumed from its SQLite checkpoint without repeating completed research nodes.</p><dl><div><dt>Final verdict</dt><dd>{graph.final_verdict ? titleCase(graph.final_verdict) : "Not issued"}</dd></div><div><dt>Reviewer</dt><dd>{graph.reviewer_identity ?? "—"}</dd></div><div><dt>Audit chain</dt><dd>{review?.chain_valid ? "Verified" : "Pending"}</dd></div></dl></div>}
              </aside>
            </div>
            }
          </>
        )}
      </section>
    </main>
  );
}

