"""Bounded semantic recovery for lexically unmatched reviewed evidence targets."""

import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from claim_polygraph_ng.domain import ModelCallUsage, ModelTask
from claim_polygraph_ng.evaluation.models import (
    BenchmarkDataset,
    PageFetchEvaluationSummary,
    SemanticPassageEvaluationSummary,
    SemanticPassageJudgment,
    SemanticPassageReferenceResult,
)
from claim_polygraph_ng.providers.base import StructuredModelProvider


async def run_semantic_passage_evaluation(
    dataset: BenchmarkDataset,
    page_evaluation: PageFetchEvaluationSummary,
    provider: StructuredModelProvider,
    *,
    page_evaluation_input: str,
    lower_lexical_threshold: float = 0.2,
) -> SemanticPassageEvaluationSummary:
    """Evaluate at most one best borderline passage per unmatched reference."""
    if not 0.0 <= lower_lexical_threshold <= 1.0:
        raise ValueError("lower lexical threshold must be between zero and one")
    if (
        page_evaluation.dataset_id != dataset.dataset_id
        or page_evaluation.dataset_version != dataset.version
    ):
        raise ValueError("page evaluation does not match the benchmark dataset")

    cases_by_id = {case.case_id: case for case in dataset.cases}
    started_at = datetime.now(UTC)
    run_started = perf_counter()
    usages: list[ModelCallUsage] = []
    results: list[SemanticPassageReferenceResult] = []
    lexical_match_count = 0
    semantic_candidate_count = 0

    for case_result in page_evaluation.results:
        case = cases_by_id.get(case_result.case_id)
        if case is None:
            raise ValueError(
                f"page evaluation case is absent from benchmark: {case_result.case_id}"
            )
        for reference in case.candidate_evidence:
            candidates = tuple(
                (page, match)
                for page in case_result.pages
                for match in page.reference_matches
                if match.annotation_id == reference.annotation_id
            )
            if any(match.lexical_match for _, match in candidates):
                lexical_match_count += 1
                continue

            best = max(
                (
                    (page, match)
                    for page, match in candidates
                    if match.passage_text is not None
                ),
                key=lambda item: (
                    item[1].lexical_score,
                    -item[0].candidate_rank,
                    -(item[1].passage_rank or 0),
                ),
                default=None,
            )
            if best is None or best[1].lexical_score < lower_lexical_threshold:
                results.append(
                    SemanticPassageReferenceResult(
                        case_id=case.case_id,
                        annotation_id=reference.annotation_id,
                        source_url=reference.source_url,
                        lexical_score=best[1].lexical_score if best is not None else 0.0,
                        passage_rank=best[1].passage_rank if best is not None else None,
                        evaluated=False,
                    )
                )
                continue

            page, match = best
            semantic_candidate_count += 1
            try:
                judgment = await provider.generate(
                    task=ModelTask.EVALUATE_PASSAGE,
                    response_model=SemanticPassageJudgment,
                    inputs={
                        "claim": case.claim,
                        "reviewed_evidence": {
                            "excerpt": reference.excerpt,
                            "summary": reference.evidence_summary,
                            "stance": reference.stance.value,
                        },
                        "retrieved_passage": match.passage_text,
                    },
                )
            except Exception as error:
                results.append(
                    SemanticPassageReferenceResult(
                        case_id=case.case_id,
                        annotation_id=reference.annotation_id,
                        source_url=reference.source_url,
                        candidate_url=page.final_url or page.requested_url,
                        lexical_score=match.lexical_score,
                        passage_rank=match.passage_rank,
                        evaluated=False,
                        error_type=type(error).__name__,
                        error_message=str(error),
                    )
                )
            else:
                results.append(
                    SemanticPassageReferenceResult(
                        case_id=case.case_id,
                        annotation_id=reference.annotation_id,
                        source_url=reference.source_url,
                        candidate_url=page.final_url or page.requested_url,
                        lexical_score=match.lexical_score,
                        passage_rank=match.passage_rank,
                        evaluated=True,
                        judgment=judgment,
                    )
                )
            finally:
                take_last_usage = getattr(provider, "take_last_usage", None)
                if callable(take_last_usage):
                    usage = take_last_usage()
                    if isinstance(usage, ModelCallUsage):
                        usages.append(usage)

    evaluated = tuple(result for result in results if result.evaluated)
    equivalent_count = sum(
        result.judgment is not None
        and result.judgment.relationship == "equivalent"
        for result in evaluated
    )
    partial_count = sum(
        result.judgment is not None and result.judgment.relationship == "partial"
        for result in evaluated
    )
    not_equivalent_count = sum(
        result.judgment is not None
        and result.judgment.relationship == "not_equivalent"
        for result in evaluated
    )
    reference_count = sum(
        len(case.candidate_evidence)
        for case in dataset.cases
        if case.case_id in {result.case_id for result in page_evaluation.results}
    )
    combined = lexical_match_count + equivalent_count
    model_for_task = getattr(provider, "model_for_task", None)
    model = (
        model_for_task(ModelTask.EVALUATE_PASSAGE)
        if callable(model_for_task)
        else getattr(provider, "model", provider.provider_id)
    )

    return SemanticPassageEvaluationSummary(
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.version,
        page_evaluation_input=page_evaluation_input,
        provider_id=provider.provider_id,
        model=str(model),
        prompt_version=str(getattr(provider, "prompt_version", "unspecified")),
        started_at=started_at,
        duration_seconds=round(perf_counter() - run_started, 6),
        reference_count=reference_count,
        lexical_match_count=lexical_match_count,
        semantic_candidate_count=semantic_candidate_count,
        evaluated_count=len(evaluated),
        equivalent_count=equivalent_count,
        partial_count=partial_count,
        not_equivalent_count=not_equivalent_count,
        combined_match_count=combined,
        combined_passage_recall=(
            round(combined / reference_count, 6) if reference_count else None
        ),
        metered_model_call_count=len(usages),
        input_tokens=sum(usage.input_tokens or 0 for usage in usages),
        cached_input_tokens=sum(usage.cached_input_tokens or 0 for usage in usages),
        output_tokens=sum(usage.output_tokens or 0 for usage in usages),
        estimated_model_cost_usd=round(
            sum(usage.estimated_cost_usd or 0.0 for usage in usages),
            9,
        ),
        results=tuple(results),
        limitations=(
            "Semantic equivalence is a model judgment over supplied text, not human review.",
            "Only the single highest-scoring borderline passage per lexically unmatched "
            "reference is evaluated.",
            "Partial judgments do not count toward combined passage recall.",
            "The evaluator cannot recover evidence absent from fetched and ranked passages.",
        ),
    )


def export_semantic_passage_evaluation(
    summary: SemanticPassageEvaluationSummary,
    path: str | Path,
) -> Path:
    """Write one semantic passage evaluation summary."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(summary.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output
