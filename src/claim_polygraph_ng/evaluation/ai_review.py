"""Transparent LLM-assisted benchmark review workflow."""

import json
from datetime import UTC, datetime
from pathlib import Path

from claim_polygraph_ng.domain import ModelCallUsage, ModelTask
from claim_polygraph_ng.evaluation.models import (
    AIAssistedReviewRecord,
    AIReviewAnnotation,
    AIReviewCritique,
    AnnotationStatus,
    BenchmarkCase,
    BenchmarkDataset,
)
from claim_polygraph_ng.providers import OpenAIStructuredModelProvider

AI_REVIEW_PROMPT_VERSION = "ai-benchmark-review-v1"


async def review_benchmark_cases(
    dataset: BenchmarkDataset,
    provider: OpenAIStructuredModelProvider,
    case_ids: tuple[str, ...],
) -> BenchmarkDataset:
    """Run separate annotator and critic passes without creating human labels."""
    if not case_ids:
        raise ValueError("at least one benchmark case is required")
    cases_by_id = {case.case_id: case for case in dataset.cases}
    missing = [case_id for case_id in case_ids if case_id not in cases_by_id]
    if missing:
        raise LookupError(f"benchmark cases not found: {', '.join(missing)}")

    reviewed: dict[str, BenchmarkCase] = {}
    for case_id in case_ids:
        case = cases_by_id[case_id]
        if case.annotation_status is AnnotationStatus.REVIEWED:
            raise ValueError(f"cannot replace human review for {case_id}")
        reviewed[case_id] = await _review_case(case, provider)

    return dataset.model_copy(
        update={
            "cases": tuple(reviewed.get(case.case_id, case) for case in dataset.cases),
        }
    )


def export_benchmark(dataset: BenchmarkDataset, path: str | Path) -> Path:
    """Atomically write a validated benchmark dataset."""
    output = Path(path)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dataset.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)
    return output


async def _review_case(
    case: BenchmarkCase,
    provider: OpenAIStructuredModelProvider,
) -> BenchmarkCase:
    packet = case.model_dump(
        mode="json",
        exclude={
            "annotation_status",
            "ai_review",
            "proposed_verdict",
            "proposed_rationale",
            "expected_verdict",
            "reviewed_by",
            "reviewed_at",
        },
    )
    usage: list[ModelCallUsage] = []
    annotation = await provider.generate(
        task=ModelTask.REVIEW_ANNOTATION,
        response_model=AIReviewAnnotation,
        inputs={
            "review_scope": "provided_packet_only",
            "case": packet,
            "requirements": (
                "Do not assume linked pages were opened. Assess only the supplied excerpts "
                "and metadata. Deliberately consider support, contradiction, ambiguity, "
                "source independence, temporal context, and numerical context."
            ),
        },
    )
    _take_usage(provider, usage)

    critique = await provider.generate(
        task=ModelTask.REVIEW_CRITIQUE,
        response_model=AIReviewCritique,
        inputs={
            "review_scope": "provided_packet_only",
            "case": packet,
            "annotation": annotation.model_dump(mode="json"),
            "requirements": (
                "Challenge the annotation independently. Identify overstatement, missing "
                "counterevidence, source-dependence problems, and unresolved temporal or "
                "numerical checks. Do not claim human or external source verification."
            ),
        },
    )
    _take_usage(provider, usage)

    disagreements: list[str] = []
    if annotation.recommended_verdict is not critique.recommended_verdict:
        disagreements.append(
            "Annotator recommended "
            f"{annotation.recommended_verdict.value}; critic recommended "
            f"{critique.recommended_verdict.value}."
        )
    if annotation.evidence_sufficient != critique.evidence_sufficient:
        disagreements.append("Annotator and critic disagreed about evidence sufficiency.")
    verdicts_agree = annotation.recommended_verdict is critique.recommended_verdict
    if critique.agrees_with_verdict != verdicts_agree:
        disagreements.append("Critic agreement flag was inconsistent with its recommended verdict.")

    record = AIAssistedReviewRecord(
        reviewed_at=datetime.now(UTC),
        annotator_model=provider.model_for_task(ModelTask.REVIEW_ANNOTATION),
        critic_model=provider.model_for_task(ModelTask.REVIEW_CRITIQUE),
        prompt_version=AI_REVIEW_PROMPT_VERSION,
        source_verification_scope="provided_packet_only",
        annotation=annotation,
        critique=critique,
        provisional_verdict=critique.recommended_verdict,
        disagreements=tuple(disagreements),
        usage=tuple(usage),
    )
    return case.model_copy(
        update={
            "annotation_status": AnnotationStatus.AI_REVIEWED,
            "ai_review": record,
            "expected_verdict": None,
            "reviewed_by": None,
            "reviewed_at": None,
        }
    )


def _take_usage(
    provider: OpenAIStructuredModelProvider,
    usage: list[ModelCallUsage],
) -> None:
    latest = provider.take_last_usage()
    if latest is not None:
        usage.append(latest)
