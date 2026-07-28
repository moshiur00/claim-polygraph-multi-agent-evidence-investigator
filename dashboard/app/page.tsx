"use client";
/* eslint-disable react-hooks/set-state-in-effect */

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

type Investigation = { investigation_id: string; input_claim: string; status: string; stage: string };
type Evidence = { evidence_id: string; source_id: string; passage: string; stance: string; relevance_score: number; evidence_family_id: string | null };
type Source = { source_id: string; title: string; publisher: string | null; source_type: string; url: string };
type Report = {
  investigation: Investigation;
  claim: { claim_id: string; text: string };
  sources: Source[];
  evidence: Evidence[];
  verdict: { verdict_id: string; label: string; confidence: number | null; human_review_required: boolean; review_reason: string | null };
  audits: Array<{ support_level: string; cited_evidence_ids: string[] }>;
  independence_analysis: { independent_family_count: number } | null;
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

const graphOrder = ["normalize", "research", "consolidate", "verify_context", "build_argument_ledger", "draft_verdict", "audit_citations", "assess_readiness", "route_review", "interrupt_for_review", "finalize"] as const;
const graphLabels: Record<string, string> = {
  normalize: "Normalize", research: "Research", consolidate: "Consolidate",
  verify_context: "Verify context", build_argument_ledger: "Argument ledger",
  draft_verdict: "Draft verdict", audit_citations: "Citation audit",
  assess_readiness: "Readiness", route_review: "Route review",
  interrupt_for_review: "Human review", finalize: "Final report",
};
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
  const [section, setSection] = useState("Evidence");
  const [selectedEvidence, setSelectedEvidence] = useState(0);
  const [claim, setClaim] = useState("");
  const [inputMode, setInputMode] = useState<"manual_claim" | "article_text" | "public_url">("manual_claim");
  const [claimCandidates, setClaimCandidates] = useState<ClaimCandidate[]>([]);
  const [decisionKind, setDecisionKind] = useState("approve");
  const [revisedVerdict, setRevisedVerdict] = useState("mixed");
  const [rationale, setRationale] = useState("The cited evidence supports this review decision.");
  const [reviewer, setReviewer] = useState("Md Moshiur Rahman");
  const [busy, setBusy] = useState(false);
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

  const sources = useMemo(() => new Map(report?.sources.map((source) => [source.source_id, source]) ?? []), [report]);
  const evidence = report?.evidence ?? [];
  const selected = evidence[selectedEvidence] ?? null;
  const citationRate = report?.audits.length
    ? Math.round(report.audits.filter((audit) => audit.support_level === "full").length / report.audits.length * 100) : 0;
  const reviewPending = graph?.status === "review_required" && review?.decisions.length === 0;

  async function submitClaim(event: FormEvent) {
    event.preventDefault(); if (!claim.trim()) return; setBusy(true);
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
    } catch (reason) { setError((reason as Error).message); } finally { setBusy(false); }
  }

  async function investigateCandidate(selectedClaim: string) {
      const created = await request<Report>("/api/investigations", { method: "POST", body: JSON.stringify({ claim: selectedClaim }) });
      setInvestigations((items) => [...items, created.investigation]);
      setSelectedId(created.investigation.investigation_id); setReport(created);
      if (apiStatus?.orchestrator !== "direct") {
        const snapshot = await request<GraphSnapshot>(`/api/graph-runs/${created.investigation.investigation_id}`);
        setGraph(snapshot);
        const requests = await request<ReviewRequest[]>("/api/reviews");
        const pending = requests.find((item) => item.investigation_id === created.investigation.investigation_id);
        setReview(pending ? await request<ReviewHistory>(`/api/reviews/${pending.request_id}`) : null);
      } else {
        setGraph(null); setReview(null);
      }
      setClaim(""); setClaimCandidates([]); setError(null);
      setTelemetry(await request<TelemetrySnapshot>("/api/operations/telemetry"));
  }

  async function startReview() {
    if (!report || !evidence.length) return; setBusy(true);
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
    } catch (reason) { setError((reason as Error).message); } finally { setBusy(false); }
  }

  async function saveDecision() {
    if (!review) return; setBusy(true);
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
    } catch (reason) { setError((reason as Error).message); } finally { setBusy(false); }
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
        {claimCandidates.length > 0 && <section className="record-list" aria-label="Extracted claim candidates">
          {claimCandidates.map((candidate) => <article key={candidate.candidate_id}>
            <b>{candidate.rank}. {candidate.text}</b>
            <span>Check-worthiness {Math.round(candidate.checkworthiness * 100)}%</span>
            <button className="ghost" disabled={busy} onClick={() => { setBusy(true); void investigateCandidate(candidate.text).catch((reason: Error) => setError(reason.message)).finally(() => setBusy(false)); }}>Investigate this claim</button>
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
              <div><span>CONFIDENCE</span><strong>{report.verdict.confidence == null ? "—" : `${Math.round(report.verdict.confidence * 100)}%`}</strong></div>
              <div><span>CITATION SUPPORT</span><strong>{citationRate}%</strong></div>
              <div><span>INDEPENDENT FAMILIES</span><strong>{report.independence_analysis?.independent_family_count ?? "—"}</strong></div>
              <div><span>EVIDENCE ITEMS</span><strong>{evidence.length}</strong></div>
            </div>
            <div className="graph-card">
              <div className="card-heading"><div><span>LIVE LANGGRAPH PATH</span><h2>{graph ? titleCase(graph.status) : apiStatus?.orchestrator === "direct" ? "Direct rollback selected" : "Awaiting graph state"}</h2></div>{graph ? <span className="checkpoint">Checkpoint saved · SQLite</span> : apiStatus?.orchestrator === "direct" ? <button className="ghost" onClick={startReview} disabled={busy || !evidence.length}>Start review workflow</button> : null}</div>
              <div className="graph">
                {graphOrder.map((node, index) => {
                  const done = graph?.completed_nodes.includes(node);
                  const active = graph?.status === "review_required" && node === "interrupt_for_review";
                  return <div className={`node ${done ? "done" : active ? "active" : "waiting"}`} key={node}><div>{done ? "✓" : active ? "!" : index + 1}</div><span>{graphLabels[node]}</span>{index < graphOrder.length - 1 && <i />}</div>;
                })}
              </div>
            </div>
            <div className="tabs" role="tablist">
              {["Evidence", "Citation audit", "Review history"].map((item) => <button key={item} role="tab" aria-selected={section === item} className={section === item ? "active" : ""} onClick={() => setSection(item)}>{item}</button>)}
            </div>
            <div className="content-grid">
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
                    {selected ? <><div className="passage-meta"><span>EXACT PASSAGE</span><b>{shortId(selected.evidence_id)}</b></div><blockquote>“{selected.passage}”</blockquote><dl><div><dt>Source</dt><dd>{sources.get(selected.source_id)?.title ?? "Stored source"}</dd></div><div><dt>Source type</dt><dd>{titleCase(sources.get(selected.source_id)?.source_type ?? "unknown")}</dd></div><div><dt>Relevance</dt><dd>{Math.round(selected.relevance_score * 100)}%</dd></div><div><dt>Evidence family</dt><dd>{selected.evidence_family_id ? shortId(selected.evidence_family_id) : "Unassigned"}</dd></div></dl><div className="support-note">Citation data loaded from the authoritative report.</div></> : <p className="empty-copy">Select an evidence passage.</p>}
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
          </>
        )}
      </section>
    </main>
  );
}

