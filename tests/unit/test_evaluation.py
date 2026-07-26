"""Tests for the versioned local evaluation harness."""

import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from claim_polygraph_ng.application import InvestigationService
from claim_polygraph_ng.domain import ModelTask, ResearchPath, SearchRequest
from claim_polygraph_ng.evaluation import (
    AIReviewAnnotation,
    AIReviewCritique,
    BenchmarkCase,
    BenchmarkDataset,
    BenchmarkEvidenceSearchProvider,
    EvaluationCategory,
    RiskLevel,
    export_evaluation,
    load_benchmark,
    review_benchmark_cases,
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
    assert [case.expected_verdict.value for case in dataset.cases[:5]] == [
        "misleading",
        "misleading",
        "misleading",
        "outdated",
        "contradicted",
    ]
    assert all(case.expected_verdict is None for case in dataset.cases[5:])
    assert all(case.annotation_status.value == "reviewed" for case in dataset.cases[:5])
    assert all(case.proposed_verdict is not None for case in dataset.cases[:5])
    assert all(case.candidate_evidence for case in dataset.cases[:5])
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
            "reviewed_by": None,
            "reviewed_at": None,
        }
    )
    with pytest.raises(ValidationError, match="reviewer identity and review date"):
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
    assert {
        batch[0].inline_content for batch in results[:3]
    } == {annotation.excerpt for annotation in case.candidate_evidence}


def test_ai_review_is_provenanced_and_excluded_from_human_labels() -> None:
    source = load_benchmark(BENCHMARK)
    draft_case = source.cases[0].model_copy(
        update={
            "annotation_status": "draft",
            "ai_review": None,
            "expected_verdict": None,
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
    assert case.reviewed_by is None
    assert case.ai_review is not None
    assert case.ai_review.requires_human_review is True
    assert case.ai_review.annotator_model == "annotator"
    assert case.ai_review.critic_model == "critic"
