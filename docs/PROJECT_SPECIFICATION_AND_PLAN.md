# Claim Polygraph NG

## Multi-Agent Evidence Investigator

### Project Specification and Incremental Implementation Plan

| Field | Value |
|---|---|
| Project | Claim Polygraph NG — Multi-Agent Evidence Investigator |
| Project type | Solo, portfolio-grade, production-oriented software and applied-research project |
| Initial release | English textual claims, article text, and public article URLs |
| Default deployment goal | Local-first, with no required paid model or search API |
| Document status | Authoritative working specification |
| Version | 1.0 |
| Date | 25 July 2026 |

---

## 1. Executive summary

Claim Polygraph NG will be an auditable evidence-investigation platform. It will not behave like a simplistic binary “fake-news detector.” A user will submit a factual claim, article, or public URL. The system will identify check-worthy statements, preserve their context, selectively decompose complex claims, retrieve supporting and contradictory evidence, assess the authority and independence of sources, verify numerical and temporal details, and produce a citation-grounded verdict with explicit uncertainty.

The system's main differentiator is **evidence independence**. It will count independent evidence families rather than raw URLs. If several articles repeat the same study, press release, official statement, or wire report, they will not be treated as separate confirmations.

The long-term system will use specialized agents with distinct responsibilities and tool permissions. However, development will begin with a lightweight end-to-end vertical slice. The initial implementation will use simple local components and stable interfaces so that production infrastructure can be added later without rewriting the core investigation logic.

The first coding milestone is:

```text
claim
  → validated query plan
  → search
  → safe page extraction
  → exact evidence passages
  → supporting and contradictory evidence
  → source assessment
  → provisional verdict
  → citation audit
  → persisted JSON report
```

---

## 2. Project mission

Build a transparent and reproducible workbench that investigates factual claims and produces reviewable reports grounded in exact evidence.

The system must make clear:

- What is being claimed.
- Which parts of a complex claim can be checked independently.
- What evidence supports, contradicts, qualifies, or contextualizes the claim.
- Whether apparently different sources share the same origin.
- Whether dates, quantities, units, denominators, and comparisons are valid.
- What remains unknown or unresolved.
- Why a verdict was selected.
- Which evidence supports every material sentence in the final report.
- Which models, tools, prompts, and configuration produced the result.

---

## 3. Problem statement

Automated claim verification is not simply a text-classification problem. A trustworthy investigation must solve several connected problems:

1. **Claim ambiguity**  
   Claims often omit a location, date, population, definition, comparison baseline, or speaker context.

2. **Compound claims**  
   One sentence can contain several factual assertions that require different evidence.

3. **Unsupported model reasoning**  
   A language model can produce a convincing verdict without sufficient evidence.

4. **Confirmation bias**  
   Search queries and synthesis can favor the first plausible interpretation.

5. **False source diversity**  
   Many pages may repeat one original source while appearing to provide independent confirmation.

6. **Temporal mismatch**  
   Evidence may concern a different period or may have been published after the claim was originally made.

7. **Numerical mismatch**  
   A number may use a different unit, denominator, population, baseline, or calculation.

8. **Citation mismatch**  
   A cited page can be relevant to the topic without supporting the sentence attached to it.

9. **Unbounded autonomy**  
   Agent loops can increase cost and latency without improving evidence quality.

10. **Unsafe web content**  
    Retrieved pages may contain prompt injection, malicious redirects, unsafe URLs, or misleading metadata.

Claim Polygraph NG will address these problems through evidence-first reasoning, adversarial research, provenance analysis, deterministic verification, bounded execution, and sentence-level citation auditing.

---

## 4. Product vision

The final product will be an investigation workspace where a user can:

- Submit a factual claim directly.
- Submit article text or a public article URL.
- Inspect extracted and normalized claims.
- Select which claims to investigate.
- Watch the investigation progress through trace events.
- Inspect supporting and contradictory evidence separately.
- View exact passages with source metadata and retrieval dates.
- Understand whether sources are independent or derivative.
- Review numerical and temporal checks.
- See unresolved questions and limitations.
- Approve a verdict, request more evidence, or revise the conclusion.
- Preserve the original machine verdict and all human-reviewed versions.
- Replay an investigation with its model, prompt, provider, cost, and latency records.

### 4.1 Intended users

| User | Primary need | Project value |
|---|---|---|
| Journalist or fact-checker | Rapid evidence discovery and traceability | Primary-source search, contradiction research, provenance, and citations |
| Researcher | Scientific context and source quality | Academic routing, publication metadata, evidence passages, and limitations |
| Policy analyst | Official statistics, law, and temporal context | Domain-aware research, date checks, and authoritative evidence |
| Compliance or risk analyst | Reproducible decision records | Versioned verdicts, audit history, and human approval |
| General user | Understandable and transparent conclusions | Concise verdict, evidence on both sides, and clear uncertainty |
| Engineer or evaluator | Reproducible system behavior | Typed artifacts, traces, benchmark results, and ablations |

---

## 5. Version 1 scope

### 5.1 Inputs

- One manually entered English factual claim.
- English article text.
- A public HTTP or HTTPS article URL.

### 5.2 Outputs

- Original and normalized claims.
- Contextualized or atomic subclaims when decomposition is useful.
- Investigation plan.
- Search queries and research trace.
- Canonical source records.
- Exact evidence passages and surrounding context.
- Evidence stance: support, contradiction, qualification, context, or irrelevant.
- Source-quality assessments.
- Evidence-family and dependency information.
- Numerical and temporal check results when applicable.
- Defender and challenger arguments.
- Nuanced verdict.
- Deterministic confidence features.
- Unresolved questions and limitations.
- Sentence-level citation-audit results.
- Persisted report and execution trace.

### 5.3 Research channels

- General web search.
- Primary and official source search.
- Existing professional fact-check search.
- Academic or biomedical search when the claim domain requires it.
- User-supplied sources.

### 5.4 Explicit non-goals for Version 1

- Image or deepfake verification.
- Audio or video transcription and verification.
- Real-time social-media monitoring.
- Multilingual verification.
- Mobile applications.
- Browser extensions.
- Enterprise multi-tenancy and billing.
- Autonomous public publication of verdicts.
- Mandatory model fine-tuning.
- Kubernetes deployment.
- Self-hosting every external data source.

These may become future extensions, but they must not delay a reliable claim-to-audited-report workflow.

---

## 6. Non-negotiable engineering principles

| Principle | Operational rule |
|---|---|
| Evidence before verdict | The judge receives an approved evidence packet and cannot introduce uncited external knowledge. |
| Typed artifacts | Every agent or model output used by software must pass schema validation. |
| Bounded autonomy | Every workflow stage has tool-call, iteration, time, token, and cost limits. |
| Adversarial balance | At least one research path must attempt to contradict or qualify the claim. |
| Source independence | Confidence uses independent evidence families, not the number of URLs. |
| Deterministic verification | Arithmetic, dates, URL validation, routing thresholds, and confidence features are implemented in code. |
| Human authority | High-risk, uncertain, or conflicting investigations can pause for review. |
| Untrusted content | Web content is treated as data, never as instructions. |
| Observable behavior | Material model and tool operations produce trace events with versions, latency, and outcomes. |
| Mode enforcement | A local-only run must never silently invoke a hosted or paid provider. |
| Evaluation-driven complexity | New agents or infrastructure must demonstrate value against simpler baselines. |
| Versioned decisions | Human revisions create new verdict versions instead of overwriting the original. |

---

## 7. Investigation workflow

```text
START
  |
  v
Validate input and create investigation
  |
  v
Extract and normalize content
  |
  v
Detect and rank check-worthy claims
  |
  v
Preserve context and selectively decompose
  |
  v
Create investigation and query plan
  |
  +---------------- Parallel research ----------------+
  |                                                   |
  |  Primary sources                                  |
  |  Independent web sources                          |
  |  Existing fact checks                             |
  |  Contradiction and qualification sources          |
  |  Academic sources when required                   |
  |                                                   |
  +---------------------------------------------------+
  |
  v
Fetch safely and extract exact passages
  |
  v
Normalize, deduplicate, rank, and classify evidence
  |
  v
Assess sources and infer evidence families
  |
  v
Run numerical and temporal checks when required
  |
  v
Evidence-sufficiency gate
  |
  +--> Revise queries and retry within budget
  +--> Mark unresolved or unverifiable
  +--> Request human review
  +--> Continue
  |
  v
Create defender and challenger arguments
  |
  v
Produce provisional evidence-grounded verdict
  |
  v
Audit each material sentence and citation
  |
  +--> Revise report
  +--> Request more evidence
  +--> Request human review
  +--> Accept
  |
  v
Persist report, verdict version, artifacts, and trace
  |
  v
END
```

### 7.1 Evidence-sufficiency gate

Completing a search does not mean that sufficient evidence was found. The gate will consider:

| Dimension | Initial completion condition |
|---|---|
| Claim coverage | Every material component has relevant evidence or is explicitly unresolved. |
| Balance | A contradiction-oriented search has completed. |
| Independence | At least two independent evidence families exist when realistically available. |
| Primary evidence | A suitable official, original, or peer-reviewed source was found, or its absence is documented. |
| Temporal compatibility | Claim and evidence periods are compatible. |
| Numerical validity | Relevant units, operands, denominators, and calculations were checked. |
| Ambiguity | Material definitions, geography, baseline, and reference period are resolved or disclosed. |

If the system cannot satisfy the gate within its research budget, it must report uncertainty. It must not manufacture a definitive verdict.

---

## 8. Selective claim decomposition

Decomposition will be used only when it improves answerability.

### Decompose when a claim:

- Contains multiple independently checkable assertions.
- Makes a causal claim.
- Makes a comparison across people, places, periods, or categories.
- Combines several entities or quantities.
- Depends on an unstated intermediate assertion.

### Do not decompose when:

- The claim is already atomic.
- Splitting would remove necessary context.
- Subclaims would be redundant.
- The additional pieces would not be independently answerable.

Each atomic claim must retain a link to its parent and preserve relevant:

- Speaker or author.
- Publication or statement date.
- Geography.
- Time range.
- Population.
- Comparison baseline.
- Definitions.
- Quantities and units.
- Modal language such as “may,” “will,” or “caused.”

Decomposition quality will later be evaluated for atomicity, coverage, redundancy, and answerability.

---

## 9. Evidence model

An evidence item is an exact passage with provenance and context. It is not merely a search-result snippet or a URL.

Every evidence record should contain:

- Evidence identifier.
- Claim identifier.
- Source identifier.
- Exact passage.
- Surrounding context when needed.
- Canonical URL.
- Page title.
- Author or institution when available.
- Publisher.
- Publication or last-update date.
- Retrieval date.
- Stance.
- Relevance score.
- Entailment or support assessment.
- Extraction method and status.
- Content hash.
- Temporal compatibility.
- Evidence-family identifier when known.

### 9.1 Evidence stance

| Stance | Meaning |
|---|---|
| Supports | Directly supports a material part of the claim. |
| Contradicts | Directly conflicts with a material part of the claim. |
| Qualifies | Supports only under conditions or supplies important limitations. |
| Context | Helps interpretation but does not directly prove or refute the claim. |
| Irrelevant | Does not materially address the claim. |

---

## 10. Source quality and evidence independence

Source assessment is multi-dimensional. A single opaque “trust score” must not control the verdict.

### 10.1 Source-quality dimensions

| Dimension | Question |
|---|---|
| Authority | Does the source have direct responsibility or recognized expertise? |
| Primary status | Is it the original data, law, statement, study, or report? |
| Relevance | Does the passage address the exact claim and its definitions? |
| Recency | Is it suitable for the claim's reference period? |
| Transparency | Are methods, data, corrections, and limitations visible? |
| Independence | Is it independent of other evidence in the packet? |
| Reputation | Does the publisher have accountable standards? |
| Conflict | Does the source materially benefit from the conclusion? |

Scores are engineering features, not objective truth. Every assessment must include a justification, and weights must later be evaluated and calibrated.

### 10.2 Evidence families

Evidence-family inference attempts to identify pages derived from the same origin.

Possible dependency signals include:

- Direct hyperlinks or citations.
- Identical or near-identical quotations.
- Shared datasets or studies.
- Shared press releases.
- Wire-service syndication.
- Repeated unusual phrasing.
- Publication chronology.
- Matching authors or organizations.
- Canonical URLs and content hashes.
- Explicit attribution.

Dependency must be represented with a confidence level and a reason. The system must distinguish confirmed dependency from likely dependency.

---

## 11. Numerical and temporal verification

Language models may identify which checks are needed, but deterministic code will perform the checks.

### 11.1 Numerical checks

- Parse quantities and units.
- Identify numerator and denominator.
- Normalize compatible units.
- Recompute percentages, ratios, differences, and rates.
- Check rounding.
- Detect absolute-versus-relative change confusion.
- Check whether populations or samples match.
- Verify the comparison baseline.
- Preserve the source values used in the calculation.

### 11.2 Temporal checks

- Extract claim and evidence dates.
- Distinguish publication date from the period described.
- Check whether the evidence existed at the relevant cutoff date.
- Detect outdated evidence.
- Detect claims that became false or misleading over time.
- Record retrieval dates and freshness classes.
- Prevent benchmark temporal leakage where applicable.

---

## 12. Verdict policy

The system will use a nuanced verdict taxonomy.

| Verdict | Operational definition |
|---|---|
| Supported | Strong, relevant evidence supports the material claim. |
| Mostly supported | The central claim is supported, but a minor detail is wrong or imprecise. |
| Mixed | Material subclaims or credible evidence point in different directions. |
| Misleading | The claim uses some true information but omits or distorts critical context. |
| Outdated | The claim was previously supported but is no longer current for the presented time reference. |
| Unsupported | Available evidence does not establish the claim. |
| Contradicted | Strong direct evidence refutes the material claim. |
| Unverifiable | Evidence is inaccessible, insufficient, or inherently unavailable. |

Important distinctions:

- Unsupported does not mean contradicted.
- Mixed does not mean unverifiable.
- Misleading does not require every factual detail to be false.
- Outdated requires a temporal basis.

### 12.1 Confidence policy

The language model must not invent the displayed confidence score.

An initial confidence feature can combine:

```text
evidence coverage
× source quality
× evidence consistency
× citation support
× independence factor
× temporal compatibility
```

The exact formula and weights are hypotheses. Displayed confidence must eventually be calibrated using held-out evaluation data and reported with metrics such as Brier score and Expected Calibration Error.

---

## 13. Multi-agent target architecture

The mature system will use agents with distinct objectives, tool permissions, typed outputs, and stopping conditions.

| Agent | Responsibility | Tool boundary | Primary output |
|---|---|---|---|
| Investigation Coordinator | Plan, route, enforce budgets, evaluate sufficiency, and decide retry, stop, or review | No direct web browsing | Investigation plan and routing decision |
| Claim Analyst | Detect check-worthy claims, preserve context, and selectively decompose | No external research by default | Claim analysis |
| Query Planner | Generate neutral, supporting, contradictory, and primary-source queries | No web access | Query plan |
| Primary-Source Researcher | Find official, original, legal, statistical, or first-party evidence | Search and page extraction | Research result |
| General Evidence Researcher | Find reputable independent evidence | Search and page extraction | Research result |
| Existing Fact-Check Agent | Find exact, partial, or related professional fact checks | Fact-check search API | Fact-check matches |
| Academic Researcher | Find papers and abstracts for scientific claims | Academic APIs | Research result |
| Contradiction Researcher | Search deliberately for refutation or qualification | Search and page extraction | Challenge report |
| Source Intelligence Agent | Assess source quality, recency, and dependency | Stored source metadata and evidence graph | Assessments and families |
| Defender | Build the strongest support case | Approved evidence only; no tools | Argument |
| Challenger | Build the strongest opposing or qualifying case | Approved evidence only; no tools | Argument |
| Evidence Judge | Produce a nuanced verdict and unresolved questions | No browsing; approved packet only | Verdict |
| Citation Auditor | Verify sentence-level support, dates, numbers, and citation coverage | Read-only evidence access | Audit report |

### 13.1 Why this is genuinely multi-agent

- Agents have different objectives rather than different names for one general prompt.
- Research agents can use external tools; the judge cannot.
- The contradiction agent optimizes for counterevidence.
- The coordinator controls bounded routing and stopping.
- Typed handoffs make agent behavior inspectable and testable.
- The citation auditor can block report completion.
- Human review can interrupt and redirect the workflow.

---

## 14. Incremental architecture strategy

The project will preserve the target architecture while avoiding unnecessary infrastructure in the first iteration.

### 14.1 Stage 1: lightweight vertical slice

| Concern | Initial choice |
|---|---|
| API or interface | CLI and/or minimal FastAPI endpoint |
| Persistence | JSON artifacts and SQLite |
| Execution | In-process asynchronous Python |
| Workflow | Explicit application service functions |
| LLM | One configurable provider with a mock provider for tests |
| Search | One provider behind a protocol |
| Retrieval | Deterministic ranking plus optional local embeddings |
| Events | Structured in-memory/file trace events |
| UI | Generated JSON and Markdown/HTML report |
| Deployment | Local Python environment; minimal containerization later |

### 14.2 Stage 2: production-oriented expansion

| Need demonstrated by testing | Upgrade |
|---|---|
| Concurrent investigations or multi-process workers | Redis-backed queue or equivalent |
| Durable recovery and human interrupts | LangGraph checkpoints and workflow state |
| Larger relational workload | PostgreSQL |
| Semantic retrieval at scale | pgvector or a justified alternative |
| Local metasearch control | Self-hosted SearXNG |
| Multiple local model runtimes | Ollama, llama.cpp, and vLLM adapters |
| Live investigation experience | React workspace and event stream |
| Object retention | Object storage |

### 14.3 Architectural rule

Core investigation logic must depend on protocols and domain models, not infrastructure implementations. Replacing SQLite with PostgreSQL or a direct function call with a queued job must not change evidence, verdict, or audit contracts.

---

## 15. Provider abstraction and operating modes

Agents and workflow stages request capabilities, not concrete providers.

### 15.1 Logical model roles

| Role | Typical work |
|---|---|
| Worker | Claim extraction, entities, dates, query planning, simple classification |
| Reasoning | Selective decomposition, conflict synthesis, defender and challenger |
| Judge | Final evidence-grounded verdict |
| Citation | Sentence-evidence support and audit |
| Embedding | Semantic retrieval and clustering |
| Reranker | Claim-passage relevance |

### 15.2 Operating modes

| Mode | Purpose | Model policy | Search policy |
|---|---|---|---|
| Fully local | Default, privacy, and reproducibility | Local model serving only | Local SearXNG and explicitly allowed free public APIs |
| Hybrid | Quality/cost comparison | Local first with explicitly enabled hosted fallback | Local first with explicitly enabled fallback |
| Hosted benchmark | Quality and latency ceiling | Hosted providers permitted | Hosted providers permitted |

### 15.3 Mode rules

- Providers have explicit cost classes.
- Active mode determines allowed cost classes.
- Disallowed providers are rejected before network access.
- Local mode cannot silently fall back to paid services.
- Every fallback attempt is recorded.
- Retries and fallback depth are bounded.
- Missing evidence is not a provider failure.
- Invalid application data is not a reason to switch providers.

### 15.4 Target local runtimes

- Ollama for convenient local development.
- llama.cpp for CPU/GGUF and constrained environments.
- vLLM for GPU serving and higher concurrency.

Only one runtime is required for the first vertical slice. Additional adapters will be added after the provider contract is stable.

---

## 16. Initial domain contracts

The following conceptual schemas define the minimum important artifacts. Exact implementation will use Pydantic models and enums.

### 16.1 Atomic claim

```python
class AtomicClaim(BaseModel):
    claim_id: str
    parent_claim_id: str | None = None
    text: str
    claim_type: ClaimType
    entities: list[str] = Field(default_factory=list)
    quantities: list[str] = Field(default_factory=list)
    reference_date: date | None = None
    geography: str | None = None
    ambiguities: list[str] = Field(default_factory=list)
    checkworthiness: float = Field(ge=0.0, le=1.0)
```

### 16.2 Investigation plan

```python
class InvestigationPlan(BaseModel):
    claim_id: str
    required_research_paths: list[ResearchPath]
    required_source_types: list[SourceType]
    minimum_independent_families: int
    requires_numerical_check: bool
    requires_temporal_check: bool
    maximum_research_rounds: int
    maximum_search_calls: int
    maximum_pages_fetched: int
```

### 16.3 Evidence

```python
class Evidence(BaseModel):
    evidence_id: str
    claim_id: str
    source_id: str
    passage: str
    context: str | None = None
    stance: EvidenceStance
    relevance_score: float = Field(ge=0.0, le=1.0)
    entailment_score: float | None = Field(default=None, ge=0.0, le=1.0)
    extraction_status: ExtractionStatus
```

### 16.4 Source assessment

```python
class SourceAssessment(BaseModel):
    source_id: str
    authority: float
    primary_status: float
    relevance: float
    recency: float
    transparency: float
    independence: float
    reputation: float
    conflict_penalty: float
    justification: str
```

### 16.5 Verdict

```python
class Verdict(BaseModel):
    claim_id: str
    label: VerdictLabel
    confidence: float | None
    concise_explanation: str
    detailed_reasoning: str
    decisive_evidence_ids: list[str]
    contradictory_evidence_ids: list[str]
    unresolved_questions: list[str]
    conditions_that_could_change_verdict: list[str]
    human_review_required: bool
    review_reason: str | None = None
```

### 16.6 Sentence audit

```python
class SentenceAudit(BaseModel):
    sentence_id: str
    sentence: str
    cited_evidence_ids: list[str]
    support_level: SupportLevel
    issue_type: AuditIssue | None = None
    explanation: str | None = None
    suggested_revision: str | None = None
```

These schemas will be implemented before production prompts are written.

---

## 17. Persistence and traceability

### 17.1 Core entities

| Entity | Purpose |
|---|---|
| Investigations | Input, status, active mode, stage, budgets, and timestamps |
| Claims | Original, normalized, and atomic claims with parent relationships |
| Investigation plans | Required research, checks, and budgets |
| Search queries | Query type, provider, research path, round, and result count |
| Sources | Canonical URL, metadata, content hash, and extraction status |
| Evidence | Exact passage, context, stance, scores, and source link |
| Source assessments | Quality dimensions and justifications |
| Evidence families | Root source, members, dependency reason, and confidence |
| Trace events | Stage, model/tool version, prompt version, latency, errors, and usage |
| Verdicts | Versioned label, confidence features, explanation, and evidence IDs |
| Audit results | Sentence-level support and issue type |
| Human reviews | Action, reason, timestamp, reviewer, and resulting version |

### 17.2 Reproducibility

Every completed investigation should record:

- Configuration snapshot.
- Operating mode.
- Code version when available.
- Prompt versions.
- Model and provider identifiers.
- Search queries.
- Retrieved URLs and retrieval timestamps.
- Evidence passages and content hashes.
- Tool and model failures.
- Retry and fallback decisions.
- Budget consumption.
- Verdict and audit versions.

---

## 18. Security and responsible-use requirements

### 18.1 Web security

- Permit only HTTP and HTTPS.
- Resolve and block loopback, link-local, private, and reserved network targets.
- Revalidate every redirect.
- Apply connection, read, and total timeouts.
- Limit response size.
- Restrict content types.
- Normalize and canonicalize URLs.
- Never execute downloaded content.
- Use browser automation only when necessary and within an isolated boundary.

### 18.2 Prompt-injection resistance

- Treat retrieved text as quoted evidence data.
- Never allow page instructions to modify system policy or tool permissions.
- Separate instructions from evidence in prompts.
- Restrict tool access by workflow role.
- Prevent the judge from browsing.
- Require structured outputs and artifact identifiers.
- Add adversarial pages to the security test suite.

### 18.3 Privacy and secrets

- Keep API keys in environment variables or a secret store.
- Redact credentials from logs.
- Avoid storing unnecessary personal information.
- Make data retention configurable.
- Document external provider data handling.

### 18.4 Responsible-use boundary

The system produces evidence-assisted assessments, not unquestionable truth. Reports must show uncertainty, limitations, unresolved questions, and the evidence available at investigation time. High-risk uses require human review.

---

## 19. Evaluation strategy

The central research question is:

> Which components measurably improve evidence quality, verdict correctness, calibration, and auditability relative to their cost and complexity?

### 19.1 Baselines

| System | Purpose |
|---|---|
| LLM only | Measure unsupported model-reasoning behavior |
| Single-agent retrieval | Measure the benefit of basic evidence retrieval |
| Multi-agent without contradiction | Isolate the value of adversarial research |
| Full system | Evaluate the complete architecture |

### 19.2 Ablations

- Full system without provenance weighting.
- Full system without citation auditing.
- Full system with unconditional decomposition.
- Full system without temporal verification.
- Fully local versus hybrid versus hosted.
- Different local serving backends.
- Different quantization levels where applicable.

### 19.3 Benchmark datasets

| Dataset | Intended use |
|---|---|
| AVeriTeC | Open-web evidence-supported verification |
| FEVER | Controlled retrieval and verdict evaluation |
| SciFact | Scientific claim and rationale evaluation |
| ClaimDecomp | Claim-decomposition evaluation |
| Manual 100–200 claim set | Real-world human review across domains and risk levels |

### 19.4 Metrics

| Area | Metrics |
|---|---|
| Claim analysis | Precision, recall, F1, atomicity, coverage, redundancy, answerability |
| Retrieval | Recall@K, MRR, nDCG, passage recall, primary-source rate |
| Verdict | Accuracy, macro-F1, per-class F1, confusion matrix |
| Citation | Precision, completeness, entailment, mismatch rate |
| Provenance | Family precision/recall, independent-source count error |
| Calibration | Brier score, Expected Calibration Error, reliability curve |
| Reliability | Valid-schema rate, fallback rate, recovery rate, termination success |
| Performance | Latency, pages fetched, calls, cache hits, local tokens per second |
| Cost | API cost and local compute profile per investigation |
| Safety | Prompt-injection success rate, SSRF tests, and secret leakage |

### 19.5 Initial evaluation set

Before adding complex orchestration, create twenty representative claims covering:

- Numerical claims.
- Scientific or medical claims.
- Political or policy claims.
- Corporate claims.
- Historical claims.
- Causal claims.
- Comparative claims.
- Ambiguous claims.
- Outdated claims.
- Claims with repeated derivative reporting.

This set will provide the first regression suite and baseline comparison.

---

## 20. Testing strategy

### 20.1 Unit tests

- Schema validation.
- URL canonicalization and safety.
- Date parsing and compatibility.
- Arithmetic and unit conversion.
- Deduplication and hashing.
- Evidence-family rules.
- Confidence-feature calculation.
- Routing and budget limits.

### 20.2 Contract tests

- Every model stage returns a valid typed artifact.
- Every evidence identifier resolves to stored evidence.
- The judge references only approved evidence.
- The report cites only valid evidence identifiers.
- Provider adapters implement consistent error behavior.

### 20.3 Integration tests

- Search provider.
- Safe fetcher.
- Page extraction.
- Persistence.
- End-to-end investigation.
- Retry and fallback behavior.
- Recovery when a provider fails.

### 20.4 Golden investigations

Use stable claims to assert structural behavior rather than exact prose:

- Contradiction research must run.
- Required evidence types must be attempted.
- Unresolved components must be disclosed.
- Citations must support material statements.
- Budget limits must terminate the investigation.

### 20.5 Security tests

- Private and loopback URL attempts.
- Redirects to blocked networks.
- Oversized pages.
- Unsupported content types.
- Prompt-injection pages.
- Malicious metadata.
- Secret-pattern leakage.

---

## 21. Implementation roadmap

The roadmap is organized by capability and exit criterion. Calendar estimates will be refined after the initial repository and baseline are established.

### Phase 0 — Specification and foundations

**Work**

- Approve this project specification.
- Define Architecture Decision Records.
- Implement core enums and Pydantic schemas.
- Define configuration and budget models.
- Select twenty baseline claims.
- Record an LLM-only baseline.
- Write the threat model.

**Exit criterion**

A validated set of domain contracts, architecture decisions, baseline claims, and a stored baseline result.

### Current execution status — 27 July 2026

The lightweight foundation, provider/retrieval interfaces, and five-claim
single-agent vertical slice described in roadmap Phases 1–3 have been
implemented and evaluated together as the first delivery milestone. That
milestone is formally closed in `docs/PHASE_1_COMPLETION_REPORT.md`.

The active execution phase is benchmark expansion and live-retrieval
hardening, defined in `docs/PHASE_2_EXECUTION_PLAN.md`. This delivery naming
does not renumber the long-term architecture roadmap below; it packages the
next evidence-driven work without prematurely adding target infrastructure.

### Phase 1 — Lightweight execution foundation

**Work**

- Establish Python package structure.
- Add configuration loading.
- Add structured logging and trace events.
- Add SQLite persistence and JSON artifact export.
- Add investigation creation and status lifecycle.
- Add mock model and search providers.

**Exit criterion**

An investigation can be created, executed in process, traced, persisted, and replayed in tests.

### Phase 2 — Provider and retrieval layer

**Work**

- Define model and search provider protocols.
- Implement one local model adapter.
- Implement one search adapter.
- Add provider health and normalized errors.
- Add safe URL fetching.
- Add page extraction and canonical source storage.
- Add bounded retry and fallback behavior.

**Exit criterion**

One typed model task and one real search-and-extraction task work through stable provider interfaces.

### Phase 3 — Single-agent evidence vertical slice

**Work**

- Normalize one submitted claim.
- Generate neutral, supporting, contradictory, and primary-source queries.
- Retrieve and rank sources.
- Extract exact passages.
- Classify evidence stance.
- Create simple source assessments.
- Generate a provisional verdict from the evidence packet.
- Audit report citations.
- Persist a JSON and readable report.

**Exit criterion**

The complete first milestone works end to end and is covered by integration tests.

### Phase 4 — Claim analysis and durable workflow state

**Work**

- Add check-worthiness analysis.
- Add context preservation and selective decomposition.
- Add typed workflow state.
- Introduce LangGraph when recovery or review requirements justify it.
- Add checkpointing and resume behavior.

**Exit criterion**

Complex claims can be decomposed selectively, and an interrupted workflow can resume safely.

### Phase 5 — Multi-agent research

**Work**

- Add the coordinator.
- Separate primary, general, fact-check, academic, and contradiction research.
- Run compatible research paths in bounded parallelism.
- Add evidence-sufficiency routing.
- Add diminishing-yield stopping.

**Exit criterion**

Specialized research paths produce typed artifacts and improve evidence adequacy over the single-agent baseline.

### Phase 6 — Source intelligence and provenance

**Work**

- Add source-quality dimensions.
- Add canonical source relationships.
- Add exact and near-duplicate detection.
- Infer evidence families with confidence and reasons.
- Apply independence features to confidence.

**Exit criterion**

The system detects and explains false source diversity in representative investigations.

### Phase 7 — Verification, argument, and judgment

**Work**

- Add numerical verification tools.
- Add temporal compatibility checks.
- Add defender and challenger stages.
- Add constrained evidence judge.
- Add deterministic confidence features.

**Exit criterion**

The system produces nuanced verdicts from approved evidence and discloses numerical, temporal, and evidential uncertainty.

### Phase 8 — Citation audit and human review

**Work**

- Add sentence-level citation support checks.
- Add revision loops with hard limits.
- Add publication-blocking audit conditions.
- Add review interrupts.
- Add approve, request-more-evidence, and revise decisions.
- Version every verdict.

**Exit criterion**

No final report can complete with a critical citation failure, and configured cases can pause and resume after review.

### Phase 9 — Production infrastructure

**Work**

- Migrate to PostgreSQL when workload requires it.
- Add pgvector when semantic scale requires it.
- Add Redis-backed jobs for concurrent or distributed execution.
- Deploy SearXNG.
- Add the remaining Ollama, llama.cpp, and vLLM adapters.
- Add event streaming and object storage if justified.

**Exit criterion**

Concurrent investigations run reliably with durable state, mode-compliant providers, and observable failure recovery.

### Phase 10 — Frontend, evaluation, and release

**Work**

- Build the investigation workspace.
- Add live progress events.
- Add evidence and provenance explorers.
- Add review controls.
- Run benchmarks and ablations.
- Complete security evaluation.
- Add Docker Compose and CI.
- Publish architecture, evaluation, limitations, and demo materials.

**Exit criterion**

A third party can clone, configure, run, evaluate, and understand the project.

---

## 22. Initial repository design

The initial layout should remain compact:

```text
claim-polygraph-ng/
├── apps/
│   ├── api/
│   └── cli/
├── src/
│   └── claim_polygraph_ng/
│       ├── domain/
│       ├── application/
│       ├── providers/
│       ├── retrieval/
│       ├── evidence/
│       ├── verification/
│       ├── persistence/
│       ├── reporting/
│       ├── security/
│       ├── evaluation/
│       └── config/
├── tests/
│   ├── unit/
│   ├── contracts/
│   ├── integration/
│   ├── security/
│   └── golden/
├── datasets/
├── examples/
├── config/
├── docs/
│   └── adr/
├── scripts/
├── pyproject.toml
├── .env.example
└── README.md
```

Production infrastructure folders should be added when the relevant phase begins rather than scaffolded prematurely.

---

## 23. Initial API surface

The first implementation may expose only investigation creation and retrieval. The target API includes:

```text
POST /api/v1/investigations
GET  /api/v1/investigations/{id}
GET  /api/v1/investigations/{id}/events
POST /api/v1/investigations/{id}/cancel

GET  /api/v1/investigations/{id}/claims
GET  /api/v1/claims/{claim_id}/evidence
GET  /api/v1/claims/{claim_id}/provenance
GET  /api/v1/investigations/{id}/report

POST /api/v1/verdicts/{verdict_id}/approve
POST /api/v1/verdicts/{verdict_id}/request-more-evidence
POST /api/v1/verdicts/{verdict_id}/revise

GET  /api/v1/providers/health
GET  /api/v1/config/effective
```

API expansion must follow implemented capabilities rather than precede them.

---

## 24. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Infrastructure dominates development | Build the lightweight vertical slice first and add infrastructure only for measured needs. |
| Local models produce invalid structured output | Use constrained schemas, one bounded repair attempt, contract tests, and model routing. |
| Local inference is too slow | Use smaller worker models, batch work, reduce context, and reserve stronger models for difficult stages. |
| Search quality or availability is poor | Use provider abstraction, caching, source-specific APIs, query revision, and bounded fallback. |
| Agents loop without useful evidence | Enforce budgets, sufficiency gates, and diminishing-yield stopping. |
| Decomposition harms accuracy | Apply selective decomposition, preserve the original claim, and evaluate against unconditional decomposition. |
| Source scoring introduces bias | Expose dimensions and rationales, calibrate weights, and never use the score alone. |
| Provenance inference is uncertain | Store dependency reason and confidence; distinguish confirmed from likely. |
| The judge overstates evidence | Restrict it to an approved packet, use nuanced verdicts, and require citation audit. |
| Prompt injection or SSRF affects the system | Isolate untrusted content, restrict tools, validate networks, and maintain adversarial tests. |
| Evidence becomes stale | Record retrieval dates, apply freshness policies, and support reinvestigation. |
| Benchmark improvement does not transfer | Maintain a diverse manually reviewed real-world claim set. |
| Fine-tuning consumes time without value | Defer it until evaluation identifies a stable, high-impact weakness. |
| Frontend work delays evidence quality | Deliver JSON and readable reports before building an advanced workspace. |

---

## 25. Definition of done

### 25.1 First vertical slice

- Accept one English claim.
- Produce a validated query plan.
- Run supporting, contradictory, and primary-source-oriented searches.
- Safely fetch pages.
- Store exact evidence passages and source metadata.
- Produce a provisional evidence-grounded verdict.
- Audit the report's material citations.
- Persist the investigation and readable report.
- Enforce configured call and page limits.
- Pass unit, contract, and end-to-end tests.

### 25.2 Multi-agent MVP

- Produce validated claim analysis and an investigation plan.
- Run bounded specialized research paths.
- Assess source quality and group likely dependent sources.
- Run numerical and temporal checks when required.
- Produce defender and challenger arguments from approved evidence.
- Generate a nuanced verdict and deterministic confidence features.
- Audit every material report sentence.
- Expose trace events, failures, versions, latency, and provider usage.
- Pause for human review under configured conditions.
- Preserve verdict versions.

### 25.3 Strong portfolio release

- Improve verdict quality or evidence adequacy over LLM-only and single-agent baselines.
- Demonstrate that citation auditing reduces unsupported statements.
- Demonstrate that contradiction research changes or qualifies a meaningful subset of verdicts.
- Demonstrate that provenance analysis reduces false confidence from derivative sources.
- Report confidence calibration rather than merely asserting confidence.
- Pass high-severity security tests.
- Provide reproducible local setup and clear documentation.
- Include architecture diagrams, ADRs, benchmark results, example investigations, screenshots, and a short demo video.

---

## 26. Immediate next actions

Updated 27 July 2026. The original foundation actions are complete; the active
sequence is defined in `docs/PHASE_2_EXECUTION_PLAN.md`:

1. Prepare the ambiguity and evidence requirements for CPNG-006.
2. Build its provisional evidence packet without assigning human-review
   metadata.
3. Complete genuine annotation and distinct approval for CPNG-006.
4. Repeat the bounded process for CPNG-007 through CPNG-010.
5. Harden and diagnose the local SearXNG engine configuration.
6. Capture a non-empty, rights-safe live snapshot for the ten reviewed claims.
7. Run candidate, page, passage, and semantic retrieval evaluations.
8. Run the ten-claim end-to-end benchmark twice.
9. Compare every Phase 2 exit gate and publish the exit report.
10. Decide whether observed recovery requirements justify LangGraph or other
    durable infrastructure in the following phase.

---

## 27. Project decision summary

| Decision | Current position |
|---|---|
| Product identity | Auditable evidence investigator, not a binary fake-news classifier |
| Central differentiator | Independent evidence families rather than raw source count |
| Initial delivery approach | Lightweight end-to-end vertical slice |
| Initial persistence | SQLite plus JSON artifacts |
| Initial execution | In-process asynchronous Python |
| Initial orchestration | Explicit workflow functions; LangGraph introduced when justified |
| Target orchestration | Durable graph with bounded routing and human interrupts |
| Default model policy | Local-first |
| Target local runtimes | Ollama, llama.cpp, and vLLM through adapters |
| Initial search | One provider through a stable protocol |
| Target general search | Self-hosted SearXNG with optional configured fallbacks |
| Judge permissions | Approved evidence packet only; no browsing |
| Confidence | Deterministic features followed by empirical calibration |
| Fine-tuning | Deferred until evaluation identifies a suitable task gap |
| Frontend | After the investigation engine and citation audit are reliable |
| Complexity rule | Add components only when they demonstrate measurable value |

---

## 28. Governing principle

The project succeeds when it can show not only a verdict, but also a defensible chain from the original claim to independent evidence, verified context, explicit uncertainty, and correctly supported citations.

Every future architecture and implementation decision should be evaluated against that goal.
