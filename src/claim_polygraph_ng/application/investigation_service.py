"""First executable claim-to-audited-verdict workflow."""

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import TypeVar
from uuid import UUID

from pydantic import JsonValue

from claim_polygraph_ng.config import RuntimePolicy
from claim_polygraph_ng.domain import (
    ArtifactType,
    AtomicClaim,
    Evidence,
    ExtractionStatus,
    Investigation,
    InvestigationPlan,
    InvestigationReport,
    InvestigationStage,
    InvestigationStatus,
    ModelTask,
    SearchRequest,
    SearchResult,
    SentenceAudit,
    Source,
    TraceEvent,
    TraceEventType,
    Verdict,
)
from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.persistence import InvestigationRepository
from claim_polygraph_ng.providers import SearchProvider, StructuredModelProvider
from claim_polygraph_ng.retrieval import (
    ContentFetcher,
    DocumentChunk,
    FetchError,
    HttpStatusError,
    deduplicate_chunks,
    extract_readable_text,
    rank_passages,
    segment_document,
)

StructuredResult = TypeVar("StructuredResult", bound=DomainModel)


class BudgetExceededError(RuntimeError):
    """Raised before a provider call would exceed a hard execution budget."""


class DocumentRetrievalError(RuntimeError):
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
        self._active_page_limit = self._policy.budget.maximum_pages_fetched

    async def investigate(self, claim_text: str) -> InvestigationReport:
        """Run and persist one complete deterministic investigation."""
        self._llm_calls = 0
        self._search_calls = 0
        self._pages_fetched = 0
        self._active_page_limit = self._policy.budget.maximum_pages_fetched
        investigation = Investigation(input_claim=claim_text)
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
            claim = await self._generate(
                investigation,
                ModelTask.NORMALIZE_CLAIM,
                AtomicClaim,
                {"claim_text": claim_text},
            )
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
            sources, evidence_items = await self._research(investigation, claim, plan)

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
                    "evidence": [item.model_dump(mode="json") for item in evidence_items],
                },
            )
            self._save_artifact(
                investigation,
                ArtifactType.VERDICT,
                verdict.verdict_id,
                verdict,
            )

            investigation = self._transition(
                investigation,
                stage=InvestigationStage.CITATION_AUDIT,
            )
            audit = await self._generate(
                investigation,
                ModelTask.AUDIT_SENTENCE,
                SentenceAudit,
                {
                    "sentence": verdict.concise_explanation,
                    "evidence_ids": [
                        str(identifier)
                        for identifier in (
                            verdict.decisive_evidence_ids + verdict.contradictory_evidence_ids
                        )
                    ],
                },
            )
            self._save_artifact(
                investigation,
                ArtifactType.AUDIT,
                audit.sentence_id,
                audit,
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
    ) -> tuple[tuple[Source, ...], tuple[Evidence, ...]]:
        sources: list[Source] = []
        candidate_chunks: list[DocumentChunk] = []
        evidence_items: list[Evidence] = []
        budget_exhausted = False
        self._active_page_limit = min(
            plan.maximum_pages_fetched,
            self._policy.budget.maximum_pages_fetched,
        )

        for research_path in plan.required_research_paths:
            request = SearchRequest(
                claim_id=claim.claim_id,
                query=f"{research_path.value}: {claim.text}",
                research_path=research_path,
                maximum_results=3,
            )
            results = await self._search(investigation, request)

            for result in results:
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
                    self._save_artifact(
                        investigation,
                        ArtifactType.CHUNK,
                        chunk.chunk_id,
                        chunk,
                    )
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
                evidence = await self._generate(
                    investigation,
                    ModelTask.CLASSIFY_EVIDENCE,
                    Evidence,
                    {
                        "claim_id": str(claim.claim_id),
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
                self._save_artifact(
                    investigation,
                    ArtifactType.EVIDENCE,
                    evidence.evidence_id,
                    evidence,
                )

        return tuple(sources), tuple(evidence_items)

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

        content = extract_readable_text(document.text, document.content_type)
        if not content:
            raise DocumentRetrievalError("fetched document contains no readable text")
        return content, str(document.final_url), document.retrieved_at

    async def _generate(
        self,
        investigation: Investigation,
        task: ModelTask,
        response_model: type[StructuredResult],
        inputs: Mapping[str, JsonValue],
    ) -> StructuredResult:
        if self._llm_calls >= self._policy.budget.maximum_llm_calls:
            raise BudgetExceededError("maximum LLM calls exceeded")
        self._llm_calls += 1
        self._event(
            investigation,
            TraceEventType.PROVIDER_CALLED,
            f"Structured model provider called for {task.value}.",
            {
                "provider_id": self._model_provider.provider_id,
                "task": task.value,
                "call_number": self._llm_calls,
            },
        )
        return await self._model_provider.generate(
            task=task,
            response_model=response_model,
            inputs=inputs,
        )

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
