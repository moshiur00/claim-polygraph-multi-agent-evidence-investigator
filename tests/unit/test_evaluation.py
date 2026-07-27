"""Tests for the versioned local evaluation harness."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from claim_polygraph_ng.application import ComplexInvestigationService, InvestigationService
from claim_polygraph_ng.domain import (
    AtomicClaim,
    ClaimDecomposition,
    ModelTask,
    ResearchPath,
    SearchRequest,
)
from claim_polygraph_ng.evaluation import (
    AIReviewAnnotation,
    AIReviewCritique,
    BenchmarkCase,
    BenchmarkDataset,
    BenchmarkEvidenceSearchProvider,
    ComplexEvaluationCaseResult,
    ComplexEvaluationSummary,
    EvaluationCategory,
    RiskLevel,
    export_complex_evaluation,
    export_evaluation,
    load_benchmark,
    merge_complex_evaluations,
    review_benchmark_cases,
    run_complex_evaluation,
    run_evaluation,
    validate_initial_benchmark,
)
from claim_polygraph_ng.persistence import SQLiteInvestigationRepository
from claim_polygraph_ng.providers import (
    DeterministicModelProvider,
    DeterministicSearchProvider,
)

BENCHMARK = Path(__file__).parents[2] / "benchmarks" / "initial_claims_v1.json"


def test_initial_benchmark_has_twenty_cases_and_complete_category_coverage() -> None:
    dataset = load_benchmark(BENCHMARK)

    validate_initial_benchmark(dataset)

    assert len(dataset.cases) == 20
    assert {category for case in dataset.cases for category in case.categories} == set(
        EvaluationCategory
    )
    assert [case.expected_verdict.value for case in dataset.cases[:10]] == [
        "misleading",
        "misleading",
        "misleading",
        "outdated",
        "contradicted",
        "supported",
        "supported",
        "supported",
        "supported",
        "misleading",
    ]
    assert [case.expected_verdict.value for case in dataset.cases[10:]] == [
        "mixed",
        "contradicted",
        "contradicted",
        "mixed",
        "contradicted",
        "contradicted",
        "mixed",
        "mixed",
        "contradicted",
        "misleading",
    ]
    assert all(case.annotation_status.value == "reviewed" for case in dataset.cases)
    assert all(case.proposed_verdict is not None for case in dataset.cases)
    assert all(case.candidate_evidence for case in dataset.cases)
    assert all(
        len(annotation.excerpt.split()) <= 25
        for case in dataset.cases
        for annotation in case.candidate_evidence
    )


def test_reviewed_case_requires_verdict_and_review_metadata() -> None:
    with pytest.raises(ValidationError, match="reviewed cases require an expected verdict"):
        BenchmarkCase(
            case_id="CPNG-999",
            claim="A reviewed claim.",
            categories=(EvaluationCategory.HISTORICAL,),
            expected_claim_type="historical",
            risk_level=RiskLevel.LOW,
            annotation_status="reviewed",
        )

    candidate = load_benchmark(BENCHMARK).cases[0]
    reviewed_payload = candidate.model_dump()
    reviewed_payload.update(
        {
            "annotation_status": "reviewed",
            "expected_verdict": "misleading",
            "annotated_by": None,
            "annotated_at": None,
            "approved_by": None,
            "approved_at": None,
            "reviewed_by": None,
            "reviewed_at": None,
        }
    )
    with pytest.raises(ValidationError, match="annotator identity and annotation date"):
        BenchmarkCase.model_validate(reviewed_payload)

    ai_reviewed_payload = candidate.model_dump()
    ai_reviewed_payload["annotation_status"] = "ai_reviewed"
    ai_reviewed_payload["ai_review"] = None
    with pytest.raises(ValidationError, match="explicit AI review provenance"):
        BenchmarkCase.model_validate(ai_reviewed_payload)


def test_initial_benchmark_validation_rejects_incomplete_dataset() -> None:
    source = load_benchmark(BENCHMARK)
    incomplete = BenchmarkDataset(
        dataset_id="small",
        version=1,
        title="Small evaluation set",
        description="A deliberately incomplete evaluation dataset.",
        created_at=source.created_at,
        cases=source.cases[:1],
    )

    with pytest.raises(ValueError, match="exactly 20"):
        validate_initial_benchmark(incomplete)


def test_deterministic_evaluation_exports_structural_baseline(tmp_path) -> None:
    dataset = load_benchmark(BENCHMARK)
    repository = SQLiteInvestigationRepository(tmp_path / "evaluation.sqlite3")

    def service_factory(_case: BenchmarkCase) -> InvestigationService:
        return InvestigationService(
            repository=repository,
            model_provider=DeterministicModelProvider(),
            search_provider=DeterministicSearchProvider(),
        )

    summary = asyncio.run(
        run_evaluation(
            dataset,
            service_factory,
            provider_mode="deterministic",
            limit=2,
        )
    )
    output = export_evaluation(summary, tmp_path / "summary.json")
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert summary.case_count == 2
    assert summary.completed_case_count == 2
    assert summary.completion_rate == 1.0
    assert summary.reviewed_case_count == 2
    assert summary.verdict_accuracy == 0.0
    assert summary.ai_reviewed_case_count == 0
    assert summary.ai_provisional_comparison_count == 2
    assert summary.ai_provisional_agreement_rate == 0.0
    assert all(result.ai_provisional_verdict is not None for result in summary.results)
    assert all(result.verdict_matches_ai_provisional is False for result in summary.results)
    assert summary.verdict_distribution == {"mixed": 2}
    assert summary.mean_sources_per_completed_case == 3.0
    assert summary.mean_evidence_per_completed_case == 3.0
    assert summary.citation_full_rate == 1.0
    assert payload["limitations"]


def test_complex_evaluation_measures_components_context_and_coverage(tmp_path) -> None:
    source = load_benchmark(BENCHMARK)
    case = source.cases[10]
    dataset = source.model_copy(update={"cases": (case,)})
    repository = SQLiteInvestigationRepository(tmp_path / "complex-evaluation.sqlite3")

    class ExpectedComponentProvider(DeterministicModelProvider):
        async def generate(self, *, task, response_model, inputs):
            if task is not ModelTask.DECOMPOSE_CLAIM:
                return await super().generate(
                    task=task,
                    response_model=response_model,
                    inputs=inputs,
                )
            root = AtomicClaim.model_validate(inputs["root_claim"])
            return ClaimDecomposition(
                root_claim=root,
                requires_decomposition=True,
                components=tuple(
                    AtomicClaim(
                        parent_claim_id=root.claim_id,
                        text=text,
                        reference_date=root.reference_date,
                        geography=root.geography,
                        retained_context=(f"Submitted parent claim: {root.text}",),
                        checkworthiness=0.9,
                    )
                    for text in case.expected_components
                ),
                rationale="Each expected assertion is independently checkable and material.",
            )

    def service_factory(_case: BenchmarkCase) -> ComplexInvestigationService:
        return ComplexInvestigationService(
            repository=repository,
            model_provider=ExpectedComponentProvider(),
            search_provider=DeterministicSearchProvider(),
        )

    summary = asyncio.run(
        run_complex_evaluation(
            dataset,
            service_factory,
            provider_mode="deterministic",
        )
    )
    output = export_complex_evaluation(summary, tmp_path / "complex-summary.json")
    reloaded = ComplexEvaluationSummary.model_validate_json(output.read_text(encoding="utf-8"))

    assert reloaded.completed_case_count == 1
    assert reloaded.completion_rate == 1.0
    assert reloaded.mean_component_recall == 1.0
    assert reloaded.parent_linkage_valid_rate == 1.0
    assert reloaded.context_contract_valid_rate == 1.0
    assert reloaded.material_component_coverage_rate == 1.0
    assert reloaded.parent_citation_full_rate == 1.0
    assert reloaded.verdict_accuracy == 1.0


def test_complex_evaluation_merge_replaces_cases_and_recomputes_metrics() -> None:
    source = load_benchmark(BENCHMARK)
    cases = source.cases[10:12]
    dataset = source.model_copy(update={"cases": cases})
    failed = ComplexEvaluationCaseResult(
        case_id="CPNG-011",
        completed=False,
        expected_component_count=3,
        observed_component_count=0,
        matched_expected_component_count=0,
        component_recall=0.0,
        material_coverage_rate=0.0,
        parent_full_audit_count=0,
        parent_audit_count=0,
        completed_component_count=0,
        failed_or_unresolved_component_count=0,
        duration_seconds=1.0,
        error_type="ModelOutputError",
        error_message="A transient decomposition failed.",
    )
    second = ComplexEvaluationCaseResult(
        case_id="CPNG-012",
        completed=True,
        expected_component_count=2,
        observed_component_count=2,
        observed_components=cases[1].expected_components,
        matched_expected_component_count=2,
        component_recall=1.0,
        parent_linkage_valid=True,
        context_contract_valid=True,
        material_coverage_rate=1.0,
        verdict_label=cases[1].expected_verdict,
        expected_verdict=cases[1].expected_verdict,
        verdict_matches=True,
        parent_full_audit_count=1,
        parent_audit_count=1,
        completed_component_count=2,
        failed_or_unresolved_component_count=0,
        duration_seconds=1.0,
        estimated_model_cost_usd=0.01,
    )
    replacement = ComplexEvaluationCaseResult(
        case_id="CPNG-011",
        completed=True,
        expected_component_count=3,
        observed_component_count=3,
        observed_components=cases[0].expected_components,
        matched_expected_component_count=3,
        component_recall=1.0,
        parent_linkage_valid=True,
        context_contract_valid=True,
        material_coverage_rate=1.0,
        verdict_label=cases[0].expected_verdict,
        expected_verdict=cases[0].expected_verdict,
        verdict_matches=True,
        parent_full_audit_count=1,
        parent_audit_count=1,
        completed_component_count=3,
        failed_or_unresolved_component_count=0,
        duration_seconds=1.0,
        estimated_model_cost_usd=0.01,
    )

    def summary(results):
        return ComplexEvaluationSummary(
            dataset_id=dataset.dataset_id,
            dataset_version=dataset.version,
            provider_mode="benchmark_evidence+test",
            started_at=datetime.now(UTC),
            duration_seconds=1.0,
            case_count=len(results),
            reviewed_case_count=len(results),
            completed_case_count=sum(result.completed for result in results),
            completion_rate=sum(result.completed for result in results) / len(results),
            mean_component_recall=0.0,
            parent_linkage_valid_rate=0.0,
            context_contract_valid_rate=0.0,
            material_component_coverage_rate=0.0,
            results=tuple(results),
            limitations=("Test artifact.",),
        )

    merged = merge_complex_evaluations(
        dataset,
        summary((failed, second)),
        (summary((replacement,)),),
    )

    assert merged.completed_case_count == 2
    assert merged.completion_rate == 1.0
    assert merged.mean_component_recall == 1.0
    assert merged.parent_linkage_valid_rate == 1.0
    assert merged.context_contract_valid_rate == 1.0
    assert merged.material_component_coverage_rate == 1.0
    assert merged.parent_citation_full_rate == 1.0
    assert merged.verdict_accuracy == 1.0
    assert merged.mean_estimated_model_cost_per_completed_component_usd == 0.004


def test_benchmark_evidence_provider_serves_each_reviewed_annotation_once() -> None:
    case = load_benchmark(BENCHMARK).cases[1]
    provider = BenchmarkEvidenceSearchProvider(case)

    async def collect_results():
        requests = (
            SearchRequest(
                claim_id=uuid4(),
                query="official boiling point at atmospheric pressure",
                research_path=ResearchPath.PRIMARY,
            ),
            SearchRequest(
                claim_id=uuid4(),
                query="water boiling point qualifications",
                research_path=ResearchPath.GENERAL,
            ),
            SearchRequest(
                claim_id=uuid4(),
                query="evidence contradicting an exact boiling point",
                research_path=ResearchPath.CONTRADICTION,
            ),
            SearchRequest(
                claim_id=uuid4(),
                query="no curated evidence should remain",
                research_path=ResearchPath.GENERAL,
            ),
        )
        return [await provider.search(request) for request in requests]

    results = asyncio.run(collect_results())

    assert provider.provider_id == "benchmark-evidence:CPNG-002"
    assert [len(batch) for batch in results] == [1, 1, 1, 0]
    returned_urls = {str(batch[0].url) for batch in results[:3]}
    expected_urls = {str(annotation.source_url) for annotation in case.candidate_evidence}
    assert returned_urls == expected_urls
    assert {batch[0].inline_content for batch in results[:3]} == {
        annotation.excerpt for annotation in case.candidate_evidence
    }


def test_benchmark_evidence_provider_filters_independent_component_pools() -> None:
    case = load_benchmark(BENCHMARK).cases[16]
    first = BenchmarkEvidenceSearchProvider.for_component(
        case,
        case.expected_components[0],
    )
    second = BenchmarkEvidenceSearchProvider.for_component(
        case,
        case.expected_components[1],
    )

    async def fetch(provider):
        return await provider.search(
            SearchRequest(
                claim_id=uuid4(),
                query="component evidence",
                research_path=ResearchPath.GENERAL,
            )
        )

    first_results = asyncio.run(fetch(first))
    second_results = asyncio.run(fetch(second))

    assert first.provider_id.endswith(":component-1")
    assert second.provider_id.endswith(":component-2")
    assert str(first_results[0].url) == str(case.candidate_evidence[0].source_url)
    assert str(second_results[0].url) == str(case.candidate_evidence[1].source_url)


def test_ai_review_is_provenanced_and_excluded_from_human_labels() -> None:
    source = load_benchmark(BENCHMARK)
    draft_case = source.cases[0].model_copy(
        update={
            "annotation_status": "draft",
            "ai_review": None,
            "expected_verdict": None,
            "annotated_by": None,
            "annotated_at": None,
            "approved_by": None,
            "approved_at": None,
            "reviewed_by": None,
            "reviewed_at": None,
        }
    )
    dataset = source.model_copy(update={"cases": (draft_case, *source.cases[1:])})

    class FakeReviewProvider:
        prompt_version = "fake"

        def model_for_task(self, task: ModelTask) -> str:
            return "annotator" if task is ModelTask.REVIEW_ANNOTATION else "critic"

        def take_last_usage(self):
            return None

        async def generate(self, *, task, response_model, inputs):
            del response_model, inputs
            if task is ModelTask.REVIEW_ANNOTATION:
                return AIReviewAnnotation(
                    recommended_verdict="misleading",
                    rationale="The supplied evidence makes the exact numerical wording misleading.",
                    resolved_interpretation="The claim is interpreted as an exact universal value.",
                    evidence_sufficient=False,
                    evidence_strengths=("The excerpt addresses the central number.",),
                    evidence_gaps=("An independent calendar authority is missing.",),
                    independence_concerns=("Only one supplied source is available.",),
                    temporal_or_numerical_checks=("Compare 365.25 with 365.2422.",),
                    confidence=0.7,
                )
            return AIReviewCritique(
                agrees_with_verdict=True,
                recommended_verdict="misleading",
                critique=(
                    "The verdict is plausible, but source verification and independence "
                    "remain incomplete."
                ),
                unsupported_or_overstated_points=(),
                missing_checks=("Verify the linked excerpt and add an independent source.",),
                evidence_sufficient=False,
                confidence=0.65,
            )

    reviewed = asyncio.run(
        review_benchmark_cases(
            dataset,
            FakeReviewProvider(),
            ("CPNG-001",),
        )
    )
    case = reviewed.cases[0]

    assert case.annotation_status.value == "ai_reviewed"
    assert case.expected_verdict is None
    assert case.annotated_by is None
    assert case.approved_by is None
    assert case.reviewed_by is None
    assert case.ai_review is not None
    assert case.ai_review.requires_human_review is True
    assert case.ai_review.annotator_model == "annotator"
    assert case.ai_review.critic_model == "critic"
