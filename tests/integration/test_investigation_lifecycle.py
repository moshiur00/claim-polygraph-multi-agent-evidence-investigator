"""End-to-end tests for the first executable investigation lifecycle."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from claim_polygraph_ng.application import BudgetExceededError, InvestigationService
from claim_polygraph_ng.application.investigation_service import (
    _claim_retrieval_context,
    _enforce_evidence_label_consistency,
    _research_query,
)
from claim_polygraph_ng.config import ExecutionBudget, RuntimePolicy
from claim_polygraph_ng.domain import (
    ArtifactType,
    AtomicClaim,
    AuditIssue,
    Evidence,
    EvidenceStance,
    InvestigationPlan,
    InvestigationStage,
    InvestigationStatus,
    ModelTask,
    ResearchPath,
    SentenceAudit,
    Source,
    SupportLevel,
    TraceEventType,
    Verdict,
    VerdictLabel,
)
from claim_polygraph_ng.persistence import SQLiteInvestigationRepository
from claim_polygraph_ng.providers import (
    DeterministicModelProvider,
    DeterministicSearchProvider,
    ModelOutputError,
    ModelUnavailableError,
)
from claim_polygraph_ng.retrieval import DocumentChunk


def test_complete_investigation_is_persisted_and_reloadable(tmp_path) -> None:
    repository = SQLiteInvestigationRepository(tmp_path / "investigations.sqlite3")
    service = InvestigationService(
        repository=repository,
        model_provider=DeterministicModelProvider(),
        search_provider=DeterministicSearchProvider(),
    )

    report = asyncio.run(
        service.investigate("The example policy reduced emissions by ten percent.")
    )
    investigation_id = report.investigation.investigation_id

    stored_investigation = repository.get_investigation(investigation_id)
    assert stored_investigation is not None
    assert stored_investigation.status is InvestigationStatus.COMPLETED
    assert stored_investigation.stage is InvestigationStage.COMPLETE

    assert repository.list_artifacts(investigation_id, ArtifactType.CLAIM, AtomicClaim) == (
        report.claim,
    )
    assert repository.list_artifacts(investigation_id, ArtifactType.PLAN, InvestigationPlan) == (
        report.plan,
    )
    assert (
        repository.list_artifacts(investigation_id, ArtifactType.SOURCE, Source) == report.sources
    )
    chunks = repository.list_artifacts(
        investigation_id,
        ArtifactType.CHUNK,
        DocumentChunk,
    )
    assert len(chunks) == 3
    assert {chunk.chunk_id for chunk in chunks} == {item.chunk_id for item in report.evidence}
    assert (
        repository.list_artifacts(investigation_id, ArtifactType.EVIDENCE, Evidence)
        == report.evidence
    )
    assert report.independence_analysis is not None
    assert report.independence_analysis.independent_family_count == 3
    assert report.context_verification is not None
    assert all(item.evidence_family_id is not None for item in report.evidence)
    assert repository.list_artifacts(investigation_id, ArtifactType.VERDICT, Verdict) == (
        report.verdict,
    )
    assert (
        repository.list_artifacts(investigation_id, ArtifactType.AUDIT, SentenceAudit)
        == report.audits
    )

    assert len(report.sources) == 3
    assert len(report.evidence) == 3
    assert all(item.chunk_id is not None for item in report.evidence)
    assert report.verdict.label is VerdictLabel.MIXED
    assert report.audits[0].cited_evidence_ids

    events = repository.list_events(investigation_id)
    assert events[0].event_type is TraceEventType.INVESTIGATION_CREATED
    assert events[-1].event_type is TraceEventType.INVESTIGATION_COMPLETED
    assert any(event.event_type is TraceEventType.PROVIDER_CALLED for event in events)


def test_research_queries_are_path_specific_and_keep_the_claim_verbatim() -> None:
    claim = "Cigarette smoking causes lung cancer."

    queries = {path: _research_query(claim, path) for path in ResearchPath}

    assert len(set(queries.values())) == len(ResearchPath)
    assert all(query.endswith(f": {claim}") for query in queries.values())
    assert "official primary source dataset" in queries[ResearchPath.PRIMARY]
    assert "peer reviewed academic evidence" in queries[ResearchPath.ACADEMIC]
    assert "counterevidence limitations exceptions" in queries[ResearchPath.CONTRADICTION]


def test_research_query_includes_bounded_material_component_context() -> None:
    claim = AtomicClaim(
        parent_claim_id=uuid4(),
        text="The programme increased output.",
        quantities=("12 percent",),
        reference_date=datetime(2024, 12, 31, tzinfo=UTC).date(),
        geography="Germany",
        retained_context=("Output means audited units delivered during calendar year 2024.",),
        checkworthiness=0.9,
    )

    query = _research_query(
        claim.text,
        ResearchPath.PRIMARY,
        retained_context=_claim_retrieval_context(claim),
    )

    assert claim.text in query
    assert "Reference date 2024-12-31" in query
    assert "Geography Germany" in query
    assert "12 percent" in query
    assert "audited units delivered" in query
    assert len(query) <= 1_000


def test_claim_context_is_supplied_to_evidence_classification_and_judgment(tmp_path) -> None:
    class CapturingModelProvider(DeterministicModelProvider):
        def __init__(self) -> None:
            self.inputs_by_task = {}

        async def generate(self, *, task, response_model, inputs):
            self.inputs_by_task.setdefault(task, []).append(inputs)
            return await super().generate(
                task=task,
                response_model=response_model,
                inputs=inputs,
            )

    provider = CapturingModelProvider()
    service = InvestigationService(
        repository=SQLiteInvestigationRepository(tmp_path / "claim-context.sqlite3"),
        model_provider=provider,
        search_provider=DeterministicSearchProvider(),
    )
    claim_text = "Every adult human has exactly 206 bones."

    asyncio.run(service.investigate(claim_text))

    classification_inputs = provider.inputs_by_task[ModelTask.CLASSIFY_EVIDENCE]
    judgment_inputs = provider.inputs_by_task[ModelTask.JUDGE_EVIDENCE]
    audit_inputs = provider.inputs_by_task[ModelTask.AUDIT_SENTENCE]
    assert all(item["claim"]["text"] == claim_text for item in classification_inputs)
    assert judgment_inputs[0]["claim"]["text"] == claim_text
    assert audit_inputs[0]["original_claim"]["text"] == claim_text
    assert audit_inputs[0]["verdict_label"] == "mixed"
    assert audit_inputs[0]["evidence"]
    assert all(item["passage"] for item in audit_inputs[0]["evidence"])


def test_partial_audit_can_revise_and_reaudit_concise_explanation(tmp_path) -> None:
    class RevisingAuditProvider(DeterministicModelProvider):
        def __init__(self) -> None:
            self.audit_calls = 0

        async def generate(self, *, task, response_model, inputs):
            if task is not ModelTask.AUDIT_SENTENCE:
                return await super().generate(
                    task=task,
                    response_model=response_model,
                    inputs=inputs,
                )
            self.audit_calls += 1
            evidence_id = next(iter(inputs["evidence_ids"]))
            if self.audit_calls == 1:
                return SentenceAudit(
                    sentence=str(inputs["sentence"]),
                    cited_evidence_ids=(evidence_id,),
                    support_level=SupportLevel.PARTIAL,
                    issue_type=AuditIssue.PARTIAL_SUPPORT,
                    explanation="One clause is broader than the supplied passage.",
                    suggested_revision="The packet contains conflicting evidence.",
                )
            assert inputs["prior_audit"]["support_level"] == "partial"
            return SentenceAudit(
                sentence=str(inputs["sentence"]),
                cited_evidence_ids=(evidence_id,),
                support_level=SupportLevel.FULL,
            )

    provider = RevisingAuditProvider()
    service = InvestigationService(
        repository=SQLiteInvestigationRepository(tmp_path / "audit-revision.sqlite3"),
        model_provider=provider,
        search_provider=DeterministicSearchProvider(),
    )

    report = asyncio.run(service.investigate("A factual claim."))

    assert provider.audit_calls == 2
    assert report.verdict.concise_explanation == "The packet contains conflicting evidence."
    assert report.audits[0].sentence == report.verdict.concise_explanation
    assert report.audits[0].support_level is SupportLevel.FULL


def test_partial_audit_can_apply_two_bounded_revisions(tmp_path) -> None:
    class TwiceRevisingAuditProvider(DeterministicModelProvider):
        def __init__(self) -> None:
            self.audit_calls = 0

        async def generate(self, *, task, response_model, inputs):
            if task is not ModelTask.AUDIT_SENTENCE:
                return await super().generate(
                    task=task,
                    response_model=response_model,
                    inputs=inputs,
                )
            self.audit_calls += 1
            evidence_id = next(iter(inputs["evidence_ids"]))
            if self.audit_calls < 3:
                return SentenceAudit(
                    sentence=str(inputs["sentence"]),
                    cited_evidence_ids=(evidence_id,),
                    support_level=SupportLevel.PARTIAL,
                    issue_type=AuditIssue.PARTIAL_SUPPORT,
                    explanation="One clause remains broader than the supplied passage.",
                    suggested_revision=(
                        "The packet contains conflicting evidence."
                        if self.audit_calls == 1
                        else "The retained passage directly conflicts with the claim."
                    ),
                )
            return SentenceAudit(
                sentence=str(inputs["sentence"]),
                cited_evidence_ids=(evidence_id,),
                support_level=SupportLevel.FULL,
            )

    provider = TwiceRevisingAuditProvider()
    service = InvestigationService(
        repository=SQLiteInvestigationRepository(tmp_path / "two-audit-revisions.sqlite3"),
        model_provider=provider,
        search_provider=DeterministicSearchProvider(),
    )

    report = asyncio.run(service.investigate("A factual claim."))

    assert provider.audit_calls == 3
    assert (
        report.verdict.concise_explanation
        == "The retained passage directly conflicts with the claim."
    )
    assert report.audits[0].support_level is SupportLevel.FULL


def test_all_directly_contradictory_evidence_constrains_inconsistent_label() -> None:
    claim_id = uuid4()
    evidence = Evidence(
        claim_id=claim_id,
        source_id=uuid4(),
        passage="The observed result directly conflicts with the submitted assertion.",
        stance=EvidenceStance.CONTRADICTS,
        relevance_score=0.9,
    )
    verdict = Verdict(
        claim_id=claim_id,
        label=VerdictLabel.UNSUPPORTED,
        concise_explanation="The packet does not provide enough evidence to decide the claim.",
        detailed_reasoning="The model incorrectly treated direct counterevidence as insufficient.",
    )

    constrained = _enforce_evidence_label_consistency(verdict, (evidence,))

    assert constrained.label is VerdictLabel.CONTRADICTED
    assert constrained.contradictory_evidence_ids == (evidence.evidence_id,)
    assert constrained.human_review_required is True


def test_user_temporal_wording_is_preserved_and_anchored(tmp_path) -> None:
    class MeaningDroppingProvider(DeterministicModelProvider):
        async def generate(self, *, task, response_model, inputs):
            result = await super().generate(
                task=task,
                response_model=response_model,
                inputs=inputs,
            )
            if task is ModelTask.NORMALIZE_CLAIM:
                return result.model_copy(
                    update={
                        "text": "WHO classifies the condition as an emergency.",
                        "reference_date": None,
                    }
                )
            return result

    service = InvestigationService(
        repository=SQLiteInvestigationRepository(tmp_path / "temporal-anchor.sqlite3"),
        model_provider=MeaningDroppingProvider(),
        search_provider=DeterministicSearchProvider(),
    )
    original = "WHO still classifies the condition as an emergency."

    report = asyncio.run(service.investigate(original))

    assert report.claim.text == original
    assert report.claim.reference_date == datetime.now(UTC).date()


def test_invalid_structured_output_is_retried_once(tmp_path) -> None:
    class OneInvalidOutputProvider(DeterministicModelProvider):
        def __init__(self):
            self.failed_once = False
            self.calls = 0

        async def generate(self, *, task, response_model, inputs):
            self.calls += 1
            if task is ModelTask.JUDGE_EVIDENCE and not self.failed_once:
                self.failed_once = True
                raise ModelOutputError("invalid UUID in structured verdict")
            return await super().generate(
                task=task,
                response_model=response_model,
                inputs=inputs,
            )

    provider = OneInvalidOutputProvider()
    repository = SQLiteInvestigationRepository(tmp_path / "output-retry.sqlite3")
    service = InvestigationService(
        repository=repository,
        model_provider=provider,
        search_provider=DeterministicSearchProvider(),
    )

    report = asyncio.run(service.investigate("The retry path returns a valid report."))

    assert report.investigation.status is InvestigationStatus.COMPLETED
    assert provider.failed_once
    failures = [
        event
        for event in repository.list_events(report.investigation.investigation_id)
        if event.event_type is TraceEventType.PROVIDER_FAILED
    ]
    assert any("retrying once" in event.message for event in failures)


def test_transient_model_unavailability_is_retried_once(tmp_path) -> None:
    class OneTimeoutProvider(DeterministicModelProvider):
        def __init__(self):
            self.failed_once = False

        async def generate(self, *, task, response_model, inputs):
            if task is ModelTask.PLAN_INVESTIGATION and not self.failed_once:
                self.failed_once = True
                raise ModelUnavailableError("temporary timeout")
            return await super().generate(
                task=task,
                response_model=response_model,
                inputs=inputs,
            )

    provider = OneTimeoutProvider()
    repository = SQLiteInvestigationRepository(tmp_path / "timeout-retry.sqlite3")
    service = InvestigationService(
        repository=repository,
        model_provider=provider,
        search_provider=DeterministicSearchProvider(),
    )

    report = asyncio.run(service.investigate("The retry path survives one timeout."))

    assert report.investigation.status is InvestigationStatus.COMPLETED
    failures = [
        event
        for event in repository.list_events(report.investigation.investigation_id)
        if event.event_type is TraceEventType.PROVIDER_FAILED
    ]
    assert any("provider unavailable" in event.message.casefold() for event in failures)


def test_budget_failure_is_persisted_and_traced(tmp_path) -> None:
    repository = SQLiteInvestigationRepository(tmp_path / "budget-failure.sqlite3")
    service = InvestigationService(
        repository=repository,
        model_provider=DeterministicModelProvider(),
        search_provider=DeterministicSearchProvider(),
        runtime_policy=RuntimePolicy(
            budget=ExecutionBudget(maximum_llm_calls=1),
        ),
    )

    with pytest.raises(BudgetExceededError, match="maximum LLM calls"):
        asyncio.run(service.investigate("A claim that exceeds its model-call budget."))

    investigations = repository.list_investigations()
    assert len(investigations) == 1
    stored = investigations[0]
    assert stored.status is InvestigationStatus.FAILED
    assert stored.stage is InvestigationStage.FAILED
    assert "maximum LLM calls exceeded" in stored.failure_reason

    events = repository.list_events(stored.investigation_id)
    assert events[-1].event_type is TraceEventType.INVESTIGATION_FAILED
