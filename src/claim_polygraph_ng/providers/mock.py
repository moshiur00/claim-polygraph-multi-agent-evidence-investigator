"""Deterministic providers for tests and local workflow development."""

from collections.abc import Mapping
from typing import cast
from uuid import UUID

from pydantic import JsonValue

from claim_polygraph_ng.analysis.stance import deterministic_stance_label
from claim_polygraph_ng.domain import (
    AtomicClaim,
    AuditIssue,
    ClaimDecomposition,
    ClaimType,
    Evidence,
    EvidenceStance,
    EvidentiaryUse,
    ExtractionStatus,
    InvestigationPlan,
    ModelTask,
    ResearchPath,
    SearchRequest,
    SearchResult,
    SentenceAudit,
    SourceType,
    SupportLevel,
    Verdict,
    VerdictLabel,
)
from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.providers.base import StructuredResult


class DeterministicModelProvider:
    """Produce predictable typed artifacts without calling a model."""

    provider_id = "deterministic-model"

    async def generate(
        self,
        *,
        task: ModelTask,
        response_model: type[StructuredResult],
        inputs: Mapping[str, JsonValue],
    ) -> StructuredResult:
        artifact = self._build(task, inputs)
        if not isinstance(artifact, response_model):
            raise TypeError(
                f"task {task} produced {type(artifact).__name__}, "
                f"expected {response_model.__name__}"
            )
        return cast(StructuredResult, artifact)

    def _build(self, task: ModelTask, inputs: Mapping[str, JsonValue]) -> DomainModel:
        if task is ModelTask.NORMALIZE_CLAIM:
            return self._normalize_claim(inputs)
        if task is ModelTask.DECOMPOSE_CLAIM:
            return self._decompose(inputs)
        if task is ModelTask.PLAN_INVESTIGATION:
            return self._plan(inputs)
        if task is ModelTask.CLASSIFY_EVIDENCE:
            return self._classify_evidence(inputs)
        if task is ModelTask.JUDGE_EVIDENCE:
            return self._judge(inputs)
        if task is ModelTask.AUDIT_SENTENCE:
            return self._audit(inputs)
        raise ValueError(f"unsupported model task: {task}")

    @staticmethod
    def _normalize_claim(inputs: Mapping[str, JsonValue]) -> AtomicClaim:
        claim_text = str(inputs["claim_text"]).strip()
        return AtomicClaim(
            text=claim_text,
            claim_type=ClaimType.FACTUAL,
            ambiguities=("Mock analysis: real context extraction has not run.",),
            checkworthiness=0.9,
        )

    @staticmethod
    def _plan(inputs: Mapping[str, JsonValue]) -> InvestigationPlan:
        return InvestigationPlan(
            claim_id=UUID(str(inputs["claim_id"])),
            required_research_paths=(
                ResearchPath.PRIMARY,
                ResearchPath.GENERAL,
                ResearchPath.CONTRADICTION,
            ),
            required_source_types=(SourceType.OFFICIAL, SourceType.NEWS),
            maximum_research_rounds=1,
            maximum_search_calls=3,
            maximum_pages_fetched=9,
        )

    @staticmethod
    def _decompose(inputs: Mapping[str, JsonValue]) -> ClaimDecomposition:
        root = AtomicClaim.model_validate(inputs["root_claim"])
        component = root.model_copy(
            update={
                "claim_id": UUID(int=root.claim_id.int ^ 1),
                "parent_claim_id": root.claim_id,
                "retained_context": (
                    "The submitted claim is already atomic; all root context is retained.",
                ),
            }
        )
        return ClaimDecomposition(
            root_claim=root,
            requires_decomposition=False,
            components=(component,),
            rationale="The deterministic provider treats this submitted claim as atomic.",
        )

    @staticmethod
    def _classify_evidence(inputs: Mapping[str, JsonValue]) -> Evidence:
        research_path = ResearchPath(str(inputs["research_path"]))
        chunk_id = inputs.get("chunk_id")
        passage_start_char = inputs.get("passage_start_char")
        passage_end_char = inputs.get("passage_end_char")
        retrieval_score = inputs.get("retrieval_score")
        stance_by_path = {
            ResearchPath.PRIMARY: EvidenceStance.SUPPORTS,
            ResearchPath.GENERAL: EvidenceStance.QUALIFIES,
            ResearchPath.CONTRADICTION: EvidenceStance.CONTRADICTS,
        }
        stance = stance_by_path.get(research_path, EvidenceStance.CONTEXT)
        return Evidence(
            claim_id=UUID(str(inputs["claim_id"])),
            source_id=UUID(str(inputs["source_id"])),
            chunk_id=UUID(str(chunk_id)) if chunk_id else None,
            passage=str(inputs["passage"]),
            passage_start_char=(
                int(passage_start_char) if passage_start_char is not None else None
            ),
            passage_end_char=(int(passage_end_char) if passage_end_char is not None else None),
            stance=stance,
            relevance_score=0.92,
            retrieval_score=(float(retrieval_score) if retrieval_score is not None else None),
            entailment_score=0.84,
            extraction_status=ExtractionStatus.EXTRACTED,
            temporal_compatibility=0.9,
            evidentiary_use=EvidentiaryUse.QUALIFIED_OBSERVATION,
        )

    @staticmethod
    def _judge(inputs: Mapping[str, JsonValue]) -> Verdict:
        evidence_items = cast(list[dict[str, JsonValue]], inputs["evidence"])
        typed_evidence = tuple(Evidence.model_validate(item) for item in evidence_items)
        supporting = [
            UUID(str(item["evidence_id"]))
            for item in evidence_items
            if item["stance"] in {EvidenceStance.SUPPORTS, EvidenceStance.QUALIFIES}
        ]
        contradicting = [
            UUID(str(item["evidence_id"]))
            for item in evidence_items
            if item["stance"] == EvidenceStance.CONTRADICTS
        ]

        label = deterministic_stance_label(typed_evidence)
        explanation = {
            VerdictLabel.MIXED: (
                "The deterministic evidence packet contains material qualification "
                "or both supporting and contradictory evidence."
            ),
            VerdictLabel.SUPPORTED: "The deterministic evidence packet supports the claim.",
            VerdictLabel.CONTRADICTED: (
                "The deterministic evidence packet contradicts the claim."
            ),
            VerdictLabel.UNVERIFIABLE: "The deterministic evidence packet is insufficient.",
        }[label]

        return Verdict(
            claim_id=UUID(str(inputs["claim_id"])),
            label=label,
            confidence=None,
            concise_explanation=explanation,
            detailed_reasoning=(
                "This provisional result was produced by a deterministic mock "
                "provider to validate orchestration and persistence contracts."
            ),
            decisive_evidence_ids=tuple(supporting),
            contradictory_evidence_ids=tuple(contradicting),
            unresolved_questions=("Real retrieval and model-based analysis have not run.",),
            conditions_that_could_change_verdict=(
                "Replacing mock passages with independently retrieved evidence.",
            ),
        )

    @staticmethod
    def _audit(inputs: Mapping[str, JsonValue]) -> SentenceAudit:
        evidence_ids = tuple(UUID(str(value)) for value in cast(list[str], inputs["evidence_ids"]))
        if evidence_ids:
            return SentenceAudit(
                sentence=str(inputs["sentence"]),
                cited_evidence_ids=evidence_ids,
                support_level=SupportLevel.FULL,
            )
        return SentenceAudit(
            sentence=str(inputs["sentence"]),
            support_level=SupportLevel.NONE,
            issue_type=AuditIssue.MISSING_CITATION,
            explanation="The material sentence has no cited evidence.",
        )


class DeterministicSearchProvider:
    """Return one synthetic passage per research path."""

    provider_id = "deterministic-search"

    async def search(self, request: SearchRequest) -> tuple[SearchResult, ...]:
        claim_text = request.query.split(": ", maxsplit=1)[-1]
        path_results = {
            ResearchPath.PRIMARY: SearchResult(
                url="https://example.org/official-record",
                title="Mock official record",
                snippet="Synthetic supporting result.",
                inline_content=f"The mock official record supports: {claim_text}",
                source_type=SourceType.OFFICIAL,
                publisher="Example Public Authority",
            ),
            ResearchPath.GENERAL: SearchResult(
                url="https://example.net/context-report",
                title="Mock contextual report",
                snippet="Synthetic qualifying result.",
                inline_content=f"The mock independent report qualifies: {claim_text}",
                source_type=SourceType.NEWS,
                publisher="Example Independent Newsroom",
            ),
            ResearchPath.CONTRADICTION: SearchResult(
                url="https://example.com/contrary-record",
                title="Mock contrary record",
                snippet="Synthetic contradictory result.",
                inline_content=f"The mock contrary record contradicts: {claim_text}",
                source_type=SourceType.PRIMARY_DOCUMENT,
                publisher="Example Records Office",
            ),
        }
        result = path_results.get(request.research_path)
        return (result,) if result is not None else ()
