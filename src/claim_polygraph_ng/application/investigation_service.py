"""First executable claim-to-audited-verdict workflow."""

import hashlib
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import TypeVar
from uuid import UUID

from pydantic import JsonValue

from claim_polygraph_ng.analysis import (
    analyze_source_independence,
    build_argument_ledger,
    calculate_judgment_readiness,
    enforce_judgment_policy,
    verify_claim_context,
)
from claim_polygraph_ng.analysis.investigation_provenance import (
    build_investigation_provenance,
)
from claim_polygraph_ng.analysis.verification_bridge import bridge_legacy_verification
from claim_polygraph_ng.config import RuntimePolicy
from claim_polygraph_ng.domain import (
    ArtifactType,
    AtomicClaim,
    ContextVerification,
    Evidence,
    EvidenceStance,
    ExtractionStatus,
    IndependenceAnalysis,
    Investigation,
    InvestigationPlan,
    InvestigationReport,
    InvestigationStage,
    InvestigationStatus,
    ModelCallUsage,
    ModelTask,
    ResearchPath,
    SearchRequest,
    SearchResult,
    SentenceAudit,
    Source,
    SupportLevel,
    TraceEvent,
    TraceEventType,
    Verdict,
    VerdictLabel,
)
from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.persistence import InvestigationRepository
from claim_polygraph_ng.providers import (
    ModelOutputError,
    ModelUnavailableError,
    SearchProvider,
    StructuredModelProvider,
)
from claim_polygraph_ng.retrieval import (
    ContentFetcher,
    DocumentChunk,
    FetchError,
    HttpStatusError,
    deduplicate_chunks,
    extract_document_text,
    rank_passages,
    segment_document,
)

StructuredResult = TypeVar("StructuredResult", bound=DomainModel)
_TEMPORAL_CUE_PATTERN = re.compile(
    r"\b(current|currently|today|now|still|as of|no longer)\b",
    re.IGNORECASE,
)
_RESEARCH_QUERY_PREFIXES = {
    ResearchPath.PRIMARY: "official primary source dataset",
    ResearchPath.GENERAL: "authoritative independent context",
    ResearchPath.FACT_CHECK: "independent fact check evidence",
    ResearchPath.ACADEMIC: "peer reviewed academic evidence",
    ResearchPath.CONTRADICTION: "counterevidence limitations exceptions",
}


def _anchor_claim_to_user_text(claim: AtomicClaim, original_text: str) -> AtomicClaim:
    updates: dict[str, object] = {"text": original_text.strip()}
    if claim.reference_date is None and _TEMPORAL_CUE_PATTERN.search(original_text):
        updates["reference_date"] = datetime.now(UTC).date()
    return AtomicClaim.model_validate({**claim.model_dump(), **updates})


def _research_query(
    claim_text: str,
    research_path: ResearchPath,
    *,
    retained_context: tuple[str, ...] = (),
) -> str:
    """Shape a generic non-oracle query for one planned research path."""
    query = f"{_RESEARCH_QUERY_PREFIXES[research_path]}: {claim_text}"
    if retained_context:
        bounded_context = " ".join(item[:160] for item in retained_context[:4])
        query = f"{query} Context: {bounded_context}"
    return query[:1_000]


def _claim_retrieval_context(claim: AtomicClaim) -> tuple[str, ...]:
    """Return material, claim-derived context without benchmark-specific hints."""
    context: list[str] = []
    if claim.reference_date is not None:
        context.append(f"Reference date {claim.reference_date.isoformat()}.")
    if claim.geography:
        context.append(f"Geography {claim.geography}.")
    if claim.quantities:
        context.append(f"Quantities {'; '.join(claim.quantities)}.")
    context.extend(claim.retained_context)
    return tuple(dict.fromkeys(context))


def _taxonomy_guidance(verification: ContextVerification) -> tuple[str, ...]:
    guidance: list[str] = []
    numerical = verification.numerical
    if numerical.exactness_terms and set(numerical.claim_values).intersection(
        numerical.evidence_values
    ):
        guidance.append(
            "The packet preserves a claimed numerical value under a credible qualification. "
            "If the claim fails because absolute wording omits that qualification, use "
            "misleading rather than contradicted."
        )
    if verification.temporal.reference_date is not None:
        guidance.append(
            "Evaluate time-sensitive status at the supplied reference date. When the claim "
            "uses still/currently and the evidence says the earlier status ended, use outdated "
            "rather than contradicted."
        )
    return tuple(guidance)


def _enforce_review_safeguards(
    verdict: Verdict,
    *,
    independence_requirement_met: bool,
    numerical_status: str,
    temporal_status: str,
) -> Verdict:
    reasons: list[str] = []
    if not independence_requirement_met:
        reasons.append("Required independent evidence-family count was not met.")
    if numerical_status == "insufficient":
        reasons.append("Required numerical context verification was insufficient.")
    if temporal_status == "insufficient":
        reasons.append("Required temporal context verification was insufficient.")
    if not reasons:
        return verdict
    if verdict.review_reason:
        reasons.insert(0, verdict.review_reason)
    return Verdict.model_validate(
        {
            **verdict.model_dump(),
            "human_review_required": True,
            "review_reason": " ".join(reasons),
        }
    )


def _enforce_evidence_label_consistency(
    verdict: Verdict,
    evidence: tuple[Evidence, ...],
) -> Verdict:
    """Reject non-contradiction labels when every usable passage directly conflicts."""
    usable = tuple(
        item
        for item in evidence
        if item.relevance_score >= 0.5 and item.stance is not EvidenceStance.IRRELEVANT
    )
    inconsistent_labels = {
        VerdictLabel.UNSUPPORTED,
        VerdictLabel.UNVERIFIABLE,
    }
    if (
        not usable
        or verdict.label not in inconsistent_labels
        or any(item.stance is not EvidenceStance.CONTRADICTS for item in usable)
    ):
        return verdict

    evidence_ids = tuple(dict.fromkeys(item.evidence_id for item in usable))
    reason = (
        f"Verdict constrained from {verdict.label.value} to contradicted because every "
        "usable retained passage was classified as directly contradictory."
    )
    if verdict.review_reason:
        reason = f"{verdict.review_reason} {reason}"
    return Verdict.model_validate(
        {
            **verdict.model_dump(),
            "label": VerdictLabel.CONTRADICTED,
            "concise_explanation": (
                "The supplied packet contains direct evidence that conflicts with the claim "
                "as stated."
            ),
            "detailed_reasoning": (
                f"{reason} The original model reasoning was: {verdict.detailed_reasoning}"
            ),
            "contradictory_evidence_ids": evidence_ids,
            "human_review_required": True,
            "review_reason": reason,
        }
    )


class BudgetExceededError(RuntimeError):
    """Raised before a provider call would exceed a hard execution budget."""


class DocumentRetrievalError(FetchError):
    """Raised when a real search result cannot produce usable page text."""


class InvestigationService:
    """Coordinate the lightweight workflow through stable boundaries."""

    def __init__(
        self,
        *,
        repository: InvestigationRepository,
        model_provider: StructuredModelProvider,
        search_provider: SearchProvider,
        content_fetcher: ContentFetcher | None = None,
        runtime_policy: RuntimePolicy | None = None,
    ) -> None:
        self._repository = repository
        self._model_provider = model_provider
        self._search_provider = search_provider
        self._content_fetcher = content_fetcher
        self._policy = runtime_policy or RuntimePolicy()
        self._llm_calls = 0
        self._search_calls = 0
        self._pages_fetched = 0
        self._model_usage: list[ModelCallUsage] = []
        self._active_page_limit = self._policy.budget.maximum_pages_fetched

    @property
    def model_usage(self) -> tuple[ModelCallUsage, ...]:
        """Return metered model calls captured during the latest investigation."""
        return tuple(self._model_usage)

    async def investigate(
        self,
        claim_text: str,
        *,
        prepared_claim: AtomicClaim | None = None,
        parent_investigation_id: UUID | None = None,
    ) -> InvestigationReport:
        """Run and persist one complete deterministic investigation."""
        if prepared_claim is not None and prepared_claim.text != claim_text.strip():
            raise ValueError("prepared claim text must equal the submitted component text")
        if prepared_claim is not None and prepared_claim.parent_claim_id is None:
            raise ValueError("prepared component claim must retain its parent claim ID")
        if (prepared_claim is None) != (parent_investigation_id is None):
            raise ValueError("prepared_claim and parent_investigation_id must be supplied together")
        self._llm_calls = 0
        self._search_calls = 0
        self._pages_fetched = 0
        self._model_usage = []
        self._active_page_limit = self._policy.budget.maximum_pages_fetched
        investigation = Investigation(
            input_claim=claim_text,
            parent_investigation_id=parent_investigation_id,
            component_claim_id=prepared_claim.claim_id if prepared_claim is not None else None,
        )
        self._repository.initialize()
        self._repository.save_investigation(investigation)
        self._event(
            investigation,
            TraceEventType.INVESTIGATION_CREATED,
            "Investigation created.",
        )

        investigation = self._transition(
            investigation,
            status=InvestigationStatus.RUNNING,
            stage=InvestigationStage.CLAIM_ANALYSIS,
        )

        try:
            if prepared_claim is None:
                claim = await self._generate(
                    investigation,
                    ModelTask.NORMALIZE_CLAIM,
                    AtomicClaim,
                    {"claim_text": claim_text},
                )
                claim = _anchor_claim_to_user_text(claim, claim_text)
            else:
                claim = prepared_claim
            self._save_artifact(
                investigation,
                ArtifactType.CLAIM,
                claim.claim_id,
                claim,
            )

            investigation = self._transition(
                investigation,
                stage=InvestigationStage.PLANNING,
            )
            plan = await self._generate(
                investigation,
                ModelTask.PLAN_INVESTIGATION,
                InvestigationPlan,
                {"claim_id": str(claim.claim_id), "claim_text": claim.text},
            )
            self._save_artifact(
                investigation,
                ArtifactType.PLAN,
                claim.claim_id,
                plan,
            )

            investigation = self._transition(
                investigation,
                stage=InvestigationStage.RESEARCH,
            )
            sources, evidence_items, independence = await self._research(investigation, claim, plan)
            provenance = build_investigation_provenance(
                plan=plan,
                sources=sources,
                evidence=evidence_items,
            )
            self._save_artifact(
                investigation,
                ArtifactType.PROVENANCE,
                claim.claim_id,
                provenance,
            )
            context_verification = verify_claim_context(
                claim=claim,
                plan=plan,
                sources=sources,
                evidence=evidence_items,
            )
            self._save_artifact(
                investigation,
                ArtifactType.CONTEXT_VERIFICATION,
                claim.claim_id,
                context_verification,
            )
            verification_packet = bridge_legacy_verification(
                claim=claim,
                legacy=context_verification,
                sources=sources,
                evidence=evidence_items,
            )
            self._save_artifact(
                investigation,
                ArtifactType.VERIFICATION_PACKET,
                claim.claim_id,
                verification_packet,
            )
            argument_ledger = build_argument_ledger(
                claim=claim,
                evidence=evidence_items,
                verification=verification_packet,
                provenance=provenance,
            )
            self._save_artifact(
                investigation,
                ArtifactType.ARGUMENT_LEDGER,
                claim.claim_id,
                argument_ledger,
            )

            investigation = self._transition(
                investigation,
                stage=InvestigationStage.JUDGMENT,
            )
            verdict = await self._generate(
                investigation,
                ModelTask.JUDGE_EVIDENCE,
                Verdict,
                {
                    "claim_id": str(claim.claim_id),
                    "claim": claim.model_dump(mode="json"),
                    "sources": [source.model_dump(mode="json") for source in sources],
                    "evidence": [item.model_dump(mode="json") for item in evidence_items],
                    "independence_analysis": independence.model_dump(mode="json"),
                    "context_verification": context_verification.model_dump(mode="json"),
                    "taxonomy_guidance": _taxonomy_guidance(context_verification),
                },
            )
            verdict = _enforce_review_safeguards(
                verdict,
                independence_requirement_met=independence.requirement_met,
                numerical_status=context_verification.numerical.status.value,
                temporal_status=context_verification.temporal.status.value,
            )
            verdict = _enforce_evidence_label_consistency(verdict, evidence_items)
            _policy_candidate, judgment_policy = enforce_judgment_policy(
                verdict, argument_ledger
            )
            judgment_policy = judgment_policy.model_copy(update={"applied": False})
            self._save_artifact(
                investigation,
                ArtifactType.JUDGMENT_POLICY,
                verdict.verdict_id,
                judgment_policy,
            )
            investigation = self._transition(
                investigation,
                stage=InvestigationStage.CITATION_AUDIT,
            )
            audit_inputs: dict[str, JsonValue] = {
                "original_claim": claim.model_dump(mode="json"),
                "verdict_label": verdict.label.value,
                "sentence": verdict.concise_explanation,
                "evidence_ids": [str(item.evidence_id) for item in evidence_items],
                "evidence": [item.model_dump(mode="json") for item in evidence_items],
            }
            audit = await self._generate(
                investigation,
                ModelTask.AUDIT_SENTENCE,
                SentenceAudit,
                audit_inputs,
            )
            for _revision_attempt in range(2):
                revision = (audit.suggested_revision or "").strip()
                if (
                    audit.support_level is not SupportLevel.PARTIAL
                    or not 10 <= len(revision) <= 1_000
                    or revision == verdict.concise_explanation
                ):
                    break
                verdict = Verdict.model_validate(
                    {
                        **verdict.model_dump(),
                        "concise_explanation": revision,
                    }
                )
                audit_inputs = {
                    **audit_inputs,
                    "sentence": revision,
                    "prior_audit": audit.model_dump(mode="json"),
                }
                audit = await self._generate(
                    investigation,
                    ModelTask.AUDIT_SENTENCE,
                    SentenceAudit,
                    audit_inputs,
                )
            self._save_artifact(
                investigation,
                ArtifactType.VERDICT,
                verdict.verdict_id,
                verdict,
            )
            self._save_artifact(
                investigation,
                ArtifactType.AUDIT,
                audit.sentence_id,
                audit,
            )
            readiness = calculate_judgment_readiness(
                ledger=argument_ledger,
                verification=verification_packet,
                provenance=provenance,
                audits=(audit,),
                unresolved_question_count=len(verdict.unresolved_questions),
            )
            self._save_artifact(
                investigation,
                ArtifactType.READINESS,
                claim.claim_id,
                readiness,
            )

            investigation = self._transition(
                investigation,
                status=InvestigationStatus.COMPLETED,
                stage=InvestigationStage.COMPLETE,
            )
            self._event(
                investigation,
                TraceEventType.INVESTIGATION_COMPLETED,
                "Investigation completed with an audited provisional verdict.",
                {
                    "llm_calls": self._llm_calls,
                    "search_calls": self._search_calls,
                    "pages_fetched": self._pages_fetched,
                    "evidence_count": len(evidence_items),
                },
            )
            return InvestigationReport(
                investigation=investigation,
                claim=claim,
                plan=plan,
                sources=sources,
                evidence=evidence_items,
                independence_analysis=independence,
                provenance=provenance,
                verification_packet=verification_packet,
                argument_ledger=argument_ledger,
                judgment_policy=judgment_policy,
                readiness=readiness,
                context_verification=context_verification,
                verdict=verdict,
                audits=(audit,),
            )
        except Exception as error:
            failed = investigation.model_copy(
                update={
                    "status": InvestigationStatus.FAILED,
                    "stage": InvestigationStage.FAILED,
                    "updated_at": datetime.now(UTC),
                    "failure_reason": str(error),
                }
            )
            failed = Investigation.model_validate(failed.model_dump())
            self._repository.save_investigation(failed)
            self._event(
                failed,
                TraceEventType.INVESTIGATION_FAILED,
                "Investigation failed.",
                {"error_type": type(error).__name__, "error": str(error)},
            )
            raise

    async def _research(
        self,
        investigation: Investigation,
        claim: AtomicClaim,
        plan: InvestigationPlan,
    ) -> tuple[tuple[Source, ...], tuple[Evidence, ...], IndependenceAnalysis]:
        sources: list[Source] = []
        candidate_chunks: list[DocumentChunk] = []
        evidence_items: list[Evidence] = []
        seen_result_urls: set[str] = set()
        budget_exhausted = False
        self._active_page_limit = min(
            plan.maximum_pages_fetched,
            self._policy.budget.maximum_pages_fetched,
        )

        for research_path in plan.required_research_paths:
            request = SearchRequest(
                claim_id=claim.claim_id,
                query=_research_query(
                    claim.text,
                    research_path,
                    retained_context=_claim_retrieval_context(claim),
                ),
                research_path=research_path,
                maximum_results=3,
            )
            results = await self._search(investigation, request)

            for result in results:
                result_key = str(result.url).rstrip("/").casefold()
                if result_key in seen_result_urls:
                    continue
                seen_result_urls.add(result_key)
                try:
                    content, canonical_url, retrieved_at = await self._result_content(
                        investigation,
                        result,
                    )
                except BudgetExceededError:
                    self._event(
                        investigation,
                        TraceEventType.STATUS_CHANGED,
                        "Page-fetch budget reached; research stopped.",
                        {
                            "pages_fetched": self._pages_fetched,
                            "page_limit": self._active_page_limit,
                        },
                    )
                    budget_exhausted = True
                    break
                except FetchError as error:
                    blocked_source = Source(
                        url=result.url,
                        canonical_url=result.url,
                        title=result.title,
                        source_type=result.source_type,
                        publisher=result.publisher,
                        retrieved_at=datetime.now(UTC),
                        extraction_status=(
                            ExtractionStatus.BLOCKED
                            if isinstance(error, HttpStatusError)
                            else ExtractionStatus.FAILED
                        ),
                    )
                    sources.append(blocked_source)
                    self._save_artifact(
                        investigation,
                        ArtifactType.SOURCE,
                        blocked_source.source_id,
                        blocked_source,
                    )
                    self._event(
                        investigation,
                        TraceEventType.PROVIDER_FAILED,
                        "Source retrieval failed; trying the next candidate.",
                        {
                            "provider_id": self._content_fetcher.provider_id,
                            "url": str(result.url),
                            "research_path": research_path.value,
                            "error_type": type(error).__name__,
                            "error": str(error),
                        },
                    )
                    continue

                source = Source(
                    url=result.url,
                    canonical_url=canonical_url,
                    title=result.title,
                    source_type=result.source_type,
                    publisher=result.publisher,
                    retrieved_at=retrieved_at,
                    content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                    extraction_status=ExtractionStatus.EXTRACTED,
                )
                sources.append(source)
                self._save_artifact(
                    investigation,
                    ArtifactType.SOURCE,
                    source.source_id,
                    source,
                )

                chunks = segment_document(
                    source_id=source.source_id,
                    research_path=research_path,
                    text=content,
                )
                for chunk in chunks:
                    candidate_chunks.append(chunk)
                break

            if budget_exhausted:
                break

        for research_path in plan.required_research_paths:
            path_chunks = deduplicate_chunks(
                tuple(chunk for chunk in candidate_chunks if chunk.research_path is research_path)
            )
            ranked_passages = rank_passages(
                claim.text,
                path_chunks,
                top_k=1,
            )
            for ranked in ranked_passages:
                if ranked.score <= 0:
                    self._event(
                        investigation,
                        TraceEventType.STATUS_CHANGED,
                        "No lexically relevant passage found for research path.",
                        {"research_path": research_path.value},
                    )
                    continue
                chunk = ranked.chunk
                self._save_artifact(
                    investigation,
                    ArtifactType.CHUNK,
                    chunk.chunk_id,
                    chunk,
                )
                evidence = await self._generate(
                    investigation,
                    ModelTask.CLASSIFY_EVIDENCE,
                    Evidence,
                    {
                        "claim_id": str(claim.claim_id),
                        "claim": claim.model_dump(mode="json"),
                        "source_id": str(chunk.source_id),
                        "chunk_id": str(chunk.chunk_id),
                        "passage": chunk.text,
                        "passage_start_char": chunk.start_char,
                        "passage_end_char": chunk.end_char,
                        "retrieval_score": ranked.score,
                        "research_path": research_path.value,
                    },
                )
                evidence_items.append(evidence)

        updated_evidence, independence = analyze_source_independence(
            claim_id=claim.claim_id,
            sources=tuple(sources),
            evidence=tuple(evidence_items),
            required_families=plan.minimum_independent_families,
        )
        for evidence in updated_evidence:
            self._save_artifact(
                investigation,
                ArtifactType.EVIDENCE,
                evidence.evidence_id,
                evidence,
            )
        self._save_artifact(
            investigation,
            ArtifactType.INDEPENDENCE,
            claim.claim_id,
            independence,
        )
        return tuple(sources), updated_evidence, independence

    async def _result_content(
        self,
        investigation: Investigation,
        result: SearchResult,
    ) -> tuple[str, str, datetime]:
        if result.inline_content:
            return result.inline_content, str(result.url), datetime.now(UTC)
        if self._content_fetcher is None:
            raise DocumentRetrievalError("search result requires a configured content fetcher")
        if self._pages_fetched >= self._active_page_limit:
            raise BudgetExceededError("maximum pages fetched exceeded")

        self._pages_fetched += 1
        self._event(
            investigation,
            TraceEventType.PROVIDER_CALLED,
            "Safe content fetcher called.",
            {
                "provider_id": self._content_fetcher.provider_id,
                "url": str(result.url),
                "call_number": self._pages_fetched,
            },
        )
        document = await self._content_fetcher.fetch(str(result.url))

        content = extract_document_text(document)
        if not content:
            raise DocumentRetrievalError("fetched document contains no readable text")
        return content, str(document.final_url), document.retrieved_at

    async def _generate(
        self,
        investigation: Investigation,
        task: ModelTask,
        response_model: type[StructuredResult],
        inputs: Mapping[str, JsonValue],
        *,
        retry_invalid_output: bool = True,
        retry_unavailable: bool = True,
    ) -> StructuredResult:
        if self._llm_calls >= self._policy.budget.maximum_llm_calls:
            raise BudgetExceededError("maximum LLM calls exceeded")
        self._llm_calls += 1
        provider_details: dict[str, JsonValue] = {
            "provider_id": self._model_provider.provider_id,
            "task": task.value,
            "call_number": self._llm_calls,
        }
        for attribute in ("model", "prompt_version"):
            value = getattr(self._model_provider, attribute, None)
            if isinstance(value, str):
                provider_details[attribute] = value
        model_for_task = getattr(self._model_provider, "model_for_task", None)
        if callable(model_for_task):
            selected_model = model_for_task(task)
            if isinstance(selected_model, str):
                provider_details["model"] = selected_model
        self._event(
            investigation,
            TraceEventType.PROVIDER_CALLED,
            f"Structured model provider called for {task.value}.",
            provider_details,
        )
        invalid_output: ModelOutputError | None = None
        unavailable: ModelUnavailableError | None = None
        try:
            result = await self._model_provider.generate(
                task=task,
                response_model=response_model,
                inputs=inputs,
            )
        except ModelOutputError as error:
            invalid_output = error
        except ModelUnavailableError as error:
            unavailable = error
        finally:
            take_last_usage = getattr(self._model_provider, "take_last_usage", None)
            if callable(take_last_usage):
                usage = take_last_usage()
                if isinstance(usage, ModelCallUsage):
                    self._model_usage.append(usage)
                    self._event(
                        investigation,
                        TraceEventType.MODEL_USAGE_RECORDED,
                        f"Model usage recorded for {task.value}.",
                        usage.model_dump(mode="json"),
                    )
        if invalid_output is not None:
            if not retry_invalid_output:
                raise invalid_output
            self._event(
                investigation,
                TraceEventType.PROVIDER_FAILED,
                f"Invalid structured output for {task.value}; retrying once.",
                {
                    "provider_id": self._model_provider.provider_id,
                    "task": task.value,
                    "error_type": type(invalid_output).__name__,
                    "error": str(invalid_output),
                },
            )
            return await self._generate(
                investigation,
                task,
                response_model,
                inputs,
                retry_invalid_output=False,
                retry_unavailable=retry_unavailable,
            )
        if unavailable is not None:
            if not retry_unavailable:
                raise unavailable
            self._event(
                investigation,
                TraceEventType.PROVIDER_FAILED,
                f"Structured provider unavailable for {task.value}; retrying once.",
                {
                    "provider_id": self._model_provider.provider_id,
                    "task": task.value,
                    "error_type": type(unavailable).__name__,
                    "error": str(unavailable),
                },
            )
            return await self._generate(
                investigation,
                task,
                response_model,
                inputs,
                retry_invalid_output=retry_invalid_output,
                retry_unavailable=False,
            )
        return result

    async def _search(
        self,
        investigation: Investigation,
        request: SearchRequest,
    ) -> tuple[SearchResult, ...]:
        if self._search_calls >= self._policy.budget.maximum_search_calls:
            raise BudgetExceededError("maximum search calls exceeded")
        self._search_calls += 1
        self._event(
            investigation,
            TraceEventType.PROVIDER_CALLED,
            f"Search provider called for {request.research_path.value} research.",
            {
                "provider_id": self._search_provider.provider_id,
                "research_path": request.research_path.value,
                "call_number": self._search_calls,
            },
        )
        return await self._search_provider.search(request)

    def _transition(
        self,
        investigation: Investigation,
        *,
        status: InvestigationStatus | None = None,
        stage: InvestigationStage,
    ) -> Investigation:
        updated = investigation.model_copy(
            update={
                "status": status or investigation.status,
                "stage": stage,
                "updated_at": datetime.now(UTC),
            }
        )
        updated = Investigation.model_validate(updated.model_dump())
        self._repository.save_investigation(updated)
        self._event(
            updated,
            TraceEventType.STATUS_CHANGED,
            f"Investigation moved to {stage.value}.",
            {"status": updated.status.value, "stage": stage.value},
        )
        return updated

    def _save_artifact(
        self,
        investigation: Investigation,
        artifact_type: ArtifactType,
        artifact_id: UUID,
        artifact: DomainModel,
    ) -> None:
        self._repository.save_artifact(
            investigation.investigation_id,
            artifact_type,
            artifact_id,
            artifact,
        )
        self._event(
            investigation,
            TraceEventType.ARTIFACT_CREATED,
            f"{artifact_type.value} artifact created.",
            {
                "artifact_type": artifact_type.value,
                "artifact_id": str(artifact_id),
            },
        )

    def _event(
        self,
        investigation: Investigation,
        event_type: TraceEventType,
        message: str,
        details: dict[str, JsonValue] | None = None,
    ) -> None:
        self._repository.append_event(
            TraceEvent(
                investigation_id=investigation.investigation_id,
                event_type=event_type,
                stage=investigation.stage,
                message=message,
                details=details or {},
            )
        )
