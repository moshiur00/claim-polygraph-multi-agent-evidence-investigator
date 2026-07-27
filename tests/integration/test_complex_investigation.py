"""Integration tests for decomposition, aggregation, and durable resume."""

import asyncio
from collections import Counter
from uuid import uuid4

import pytest

from claim_polygraph_ng.application import (
    ComplexInvestigationService,
    ComplexWorkflowInterrupted,
)
from claim_polygraph_ng.domain import (
    ArtifactType,
    AtomicClaim,
    ClaimDecomposition,
    ComplexCheckpointStage,
    ComplexWorkflowCheckpoint,
    ComponentStatus,
    InvestigationStatus,
    ModelTask,
    SupportLevel,
)
from claim_polygraph_ng.persistence import SQLiteInvestigationRepository
from claim_polygraph_ng.providers import (
    DeterministicModelProvider,
    DeterministicSearchProvider,
    ModelOutputError,
)


class TwoComponentProvider(DeterministicModelProvider):
    def __init__(self) -> None:
        self.calls = Counter()

    async def generate(self, *, task, response_model, inputs):
        self.calls[task] += 1
        if task is not ModelTask.DECOMPOSE_CLAIM:
            return await super().generate(
                task=task,
                response_model=response_model,
                inputs=inputs,
            )
        root = AtomicClaim.model_validate(inputs["root_claim"])
        shared = {
            "parent_claim_id": root.claim_id,
            "retained_context": (
                "The programme and measurement period are inherited from the submitted claim.",
            ),
            "checkworthiness": 0.9,
        }
        return ClaimDecomposition(
            root_claim=root,
            requires_decomposition=True,
            components=(
                AtomicClaim(
                    claim_id=uuid4(),
                    text="The programme reduced costs.",
                    **shared,
                ),
                AtomicClaim(
                    claim_id=uuid4(),
                    text="The programme increased output.",
                    **shared,
                ),
            ),
            rationale="Cost and output are separate material outcomes requiring separate evidence.",
        )


class OneFailingComponentProvider(TwoComponentProvider):
    async def generate(self, *, task, response_model, inputs):
        if (
            task is ModelTask.PLAN_INVESTIGATION
            and inputs.get("claim_text") == "The programme increased output."
        ):
            self.calls[task] += 1
            raise RuntimeError("simulated exhausted component failure")
        return await super().generate(
            task=task,
            response_model=response_model,
            inputs=inputs,
        )


class RefiningCausalProvider(DeterministicModelProvider):
    def __init__(self) -> None:
        self.decomposition_calls = 0

    async def generate(self, *, task, response_model, inputs):
        if task is not ModelTask.DECOMPOSE_CLAIM:
            return await super().generate(
                task=task,
                response_model=response_model,
                inputs=inputs,
            )
        self.decomposition_calls += 1
        root = AtomicClaim.model_validate(inputs["root_claim"])
        shared = {
            "parent_claim_id": root.claim_id,
            "retained_context": (f"Submitted parent claim: {root.text}",),
            "checkworthiness": 0.9,
        }
        if "rejected_decomposition" not in inputs:
            components = (
                AtomicClaim(text="The grid is renewable.", **shared),
                AtomicClaim(
                    text=(
                        "Total energy is renewable and therefore the country no longer "
                        "uses fossil fuels."
                    ),
                    **shared,
                ),
            )
        else:
            assert "causal connector" in str(inputs["validation_feedback"])
            components = (
                AtomicClaim(text="The grid is renewable.", **shared),
                AtomicClaim(text="Total energy is renewable.", **shared),
                AtomicClaim(
                    text="The country no longer uses fossil fuels.",
                    retained_context=(
                        f"Submitted parent claim: {root.text}",
                        "This is presented as a consequence of renewable total energy.",
                    ),
                    parent_claim_id=root.claim_id,
                    checkworthiness=0.9,
                ),
            )
        return ClaimDecomposition(
            root_claim=root,
            requires_decomposition=True,
            components=components,
            rationale="Each independently checkable assertion must have separate coverage.",
        )


class OneInvalidDecompositionProvider(TwoComponentProvider):
    def __init__(self) -> None:
        super().__init__()
        self.invalid_once = False

    async def generate(self, *, task, response_model, inputs):
        if task is ModelTask.DECOMPOSE_CLAIM and not self.invalid_once:
            self.invalid_once = True
            self.calls[task] += 1
            raise ModelOutputError("inconsistent decomposition flag")
        return await super().generate(
            task=task,
            response_model=response_model,
            inputs=inputs,
        )


def test_complex_investigation_covers_and_aggregates_every_component(tmp_path) -> None:
    repository = SQLiteInvestigationRepository(tmp_path / "complex.sqlite3")
    provider = TwoComponentProvider()
    service = ComplexInvestigationService(
        repository=repository,
        model_provider=provider,
        search_provider=DeterministicSearchProvider(),
    )

    report = asyncio.run(service.investigate("The programme reduced costs and increased output."))

    assert report.investigation.status is InvestigationStatus.COMPLETED
    assert report.decomposition.requires_decomposition is True
    assert len(report.component_reports) == 2
    assert report.coverage.completed_count == 2
    assert report.coverage.material_coverage_rate == 1.0
    assert report.verdict.claim_id == report.decomposition.root_claim.claim_id
    assert report.audits[0].cited_evidence_ids
    assert set(report.audits[0].cited_evidence_ids) == {
        item.evidence_id
        for component_report in report.component_reports
        for item in component_report.evidence
    }
    assert report.audits[0].support_level is SupportLevel.FULL
    assert provider.calls[ModelTask.AUDIT_SENTENCE] == 2
    assert all(
        child.investigation.parent_investigation_id == report.investigation.investigation_id
        for child in report.component_reports
    )


def test_complex_root_generation_retries_one_invalid_decomposition(tmp_path) -> None:
    provider = OneInvalidDecompositionProvider()
    service = ComplexInvestigationService(
        repository=SQLiteInvestigationRepository(tmp_path / "complex-retry.sqlite3"),
        model_provider=provider,
        search_provider=DeterministicSearchProvider(),
    )

    report = asyncio.run(service.investigate("The programme reduced costs and increased output."))

    assert report.investigation.status is InvestigationStatus.COMPLETED
    assert provider.calls[ModelTask.DECOMPOSE_CLAIM] == 2


def test_complex_workflow_refines_a_merged_causal_component(tmp_path) -> None:
    provider = RefiningCausalProvider()
    service = ComplexInvestigationService(
        repository=SQLiteInvestigationRepository(tmp_path / "causal-refinement.sqlite3"),
        model_provider=provider,
        search_provider=DeterministicSearchProvider(),
    )

    report = asyncio.run(
        service.investigate(
            "The grid and total energy are renewable, so the country uses no fossil fuels."
        )
    )

    assert provider.decomposition_calls == 2
    assert len(report.decomposition.components) == 3
    assert all(
        "therefore" not in component.text.casefold()
        for component in report.decomposition.components
    )


def test_resume_does_not_repeat_a_completed_component(tmp_path) -> None:
    repository = SQLiteInvestigationRepository(tmp_path / "resume.sqlite3")
    provider = TwoComponentProvider()
    service = ComplexInvestigationService(
        repository=repository,
        model_provider=provider,
        search_provider=DeterministicSearchProvider(),
    )

    with pytest.raises(ComplexWorkflowInterrupted):
        asyncio.run(
            service.investigate(
                "The programme reduced costs and increased output.",
                interrupt_after_components=1,
            )
        )

    roots = [
        investigation
        for investigation in repository.list_investigations()
        if investigation.parent_investigation_id is None
    ]
    assert len(roots) == 1
    root = roots[0]
    checkpoint = repository.list_artifacts(
        root.investigation_id,
        ArtifactType.CHECKPOINT,
        ComplexWorkflowCheckpoint,
    )[-1]
    assert checkpoint.stage is ComplexCheckpointStage.COMPONENTS
    assert len(checkpoint.completed_components) == 1
    plan_calls_before_resume = provider.calls[ModelTask.PLAN_INVESTIGATION]

    report = asyncio.run(service.resume(root.investigation_id))

    assert report.investigation.status is InvestigationStatus.COMPLETED
    assert len(report.component_reports) == 2
    assert provider.calls[ModelTask.NORMALIZE_CLAIM] == 1
    assert provider.calls[ModelTask.DECOMPOSE_CLAIM] == 1
    assert provider.calls[ModelTask.PLAN_INVESTIGATION] == plan_calls_before_resume + 1

    calls_before_reload = provider.calls.copy()
    reloaded = asyncio.run(service.resume(root.investigation_id))
    assert reloaded == report
    assert provider.calls == calls_before_reload


@pytest.mark.parametrize(
    ("stage", "expected_added_audits"),
    (
        (ComplexCheckpointStage.DECOMPOSED, 2),
        (ComplexCheckpointStage.AGGREGATED, 0),
        (ComplexCheckpointStage.AUDITED, 0),
    ),
)
def test_resume_reuses_every_completed_stage(
    tmp_path,
    stage: ComplexCheckpointStage,
    expected_added_audits: int,
) -> None:
    repository = SQLiteInvestigationRepository(tmp_path / f"{stage.value}.sqlite3")
    provider = TwoComponentProvider()
    service = ComplexInvestigationService(
        repository=repository,
        model_provider=provider,
        search_provider=DeterministicSearchProvider(),
    )

    with pytest.raises(ComplexWorkflowInterrupted):
        asyncio.run(
            service.investigate(
                "The programme reduced costs and increased output.",
                interrupt_after=stage,
            )
        )
    root = next(
        investigation
        for investigation in repository.list_investigations()
        if investigation.parent_investigation_id is None
    )
    before = provider.calls.copy()

    report = asyncio.run(service.resume(root.investigation_id))

    assert report.investigation.status is InvestigationStatus.COMPLETED
    assert provider.calls[ModelTask.NORMALIZE_CLAIM] == before[ModelTask.NORMALIZE_CLAIM]
    assert provider.calls[ModelTask.DECOMPOSE_CLAIM] == before[ModelTask.DECOMPOSE_CLAIM]
    assert (
        provider.calls[ModelTask.AUDIT_SENTENCE]
        == before[ModelTask.AUDIT_SENTENCE] + expected_added_audits
    )


def test_failed_material_component_is_explicit_and_forces_review(tmp_path) -> None:
    repository = SQLiteInvestigationRepository(tmp_path / "failed-component.sqlite3")
    service = ComplexInvestigationService(
        repository=repository,
        model_provider=OneFailingComponentProvider(),
        search_provider=DeterministicSearchProvider(),
    )

    report = asyncio.run(service.investigate("The programme reduced costs and increased output."))

    assert report.investigation.status is InvestigationStatus.COMPLETED
    assert len(report.component_reports) == 1
    assert report.coverage.material_coverage_rate == 1.0
    assert [outcome.status for outcome in report.coverage.outcomes] == [
        ComponentStatus.COMPLETED,
        ComponentStatus.FAILED,
    ]
    assert report.coverage.outcomes[1].unresolved_reason is not None
    assert "simulated exhausted component failure" in report.coverage.outcomes[1].unresolved_reason
    assert report.verdict.human_review_required is True
    assert report.audits[0].support_level is SupportLevel.PARTIAL
