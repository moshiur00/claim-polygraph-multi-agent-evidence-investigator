"""Resumable single-coordinator workflow for selectively decomposed claims."""

import re
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from claim_polygraph_ng.analysis import aggregate_component_label
from claim_polygraph_ng.application.investigation_service import (
    InvestigationService,
    _anchor_claim_to_user_text,
)
from claim_polygraph_ng.config import RuntimePolicy
from claim_polygraph_ng.domain import (
    ArtifactType,
    AtomicClaim,
    AuditIssue,
    ClaimCoverage,
    ClaimDecomposition,
    ComplexCheckpointStage,
    ComplexInvestigationReport,
    ComplexWorkflowCheckpoint,
    ComponentExecution,
    ComponentFailure,
    ComponentOutcome,
    ComponentStatus,
    Investigation,
    InvestigationReport,
    InvestigationStage,
    InvestigationStatus,
    ModelCallUsage,
    ModelTask,
    SentenceAudit,
    SupportLevel,
    TraceEvent,
    TraceEventType,
    Verdict,
    VerdictLabel,
)
from claim_polygraph_ng.persistence import InvestigationRepository
from claim_polygraph_ng.providers import (
    ModelOutputError,
    ModelUnavailableError,
    SearchProvider,
    StructuredModelProvider,
)
from claim_polygraph_ng.reporting import load_complex_report, load_report
from claim_polygraph_ng.retrieval import ContentFetcher


class ComplexWorkflowInterrupted(RuntimeError):
    """Deliberate test/development interruption after a durable checkpoint."""


_MERGED_MATERIAL_COMPONENT = re.compile(
    r"(?:\band\s+therefore\b|,\s*so\b|;\s*therefore\b|\bboth\b.+\band\b)",
    re.IGNORECASE,
)


def _contains_merged_material_component(decomposition: ClaimDecomposition) -> bool:
    return decomposition.requires_decomposition and any(
        _MERGED_MATERIAL_COMPONENT.search(component.text) for component in decomposition.components
    )


class ComplexInvestigationService:
    """Coordinate typed material components and resume completed child work."""

    def __init__(
        self,
        *,
        repository: InvestigationRepository,
        model_provider: StructuredModelProvider,
        search_provider: SearchProvider,
        component_search_provider_factory: Callable[[AtomicClaim], SearchProvider] | None = None,
        content_fetcher: ContentFetcher | None = None,
        runtime_policy: RuntimePolicy | None = None,
    ) -> None:
        self._repository = repository
        self._model_provider = model_provider
        self._search_provider = search_provider
        self._component_search_provider_factory = component_search_provider_factory
        self._content_fetcher = content_fetcher
        self._runtime_policy = runtime_policy
        self._model_usage: list[ModelCallUsage] = []

    @property
    def model_usage(self) -> tuple[ModelCallUsage, ...]:
        return tuple(self._model_usage)

    async def investigate(
        self,
        claim_text: str,
        *,
        interrupt_after: ComplexCheckpointStage | None = None,
        interrupt_after_components: int | None = None,
    ) -> ComplexInvestigationReport:
        """Start a new complex investigation and execute from its first checkpoint."""
        self._repository.initialize()
        root = Investigation(input_claim=claim_text)
        self._repository.save_investigation(root)
        self._event(root, TraceEventType.INVESTIGATION_CREATED, "Complex investigation created.")
        root = self._transition(
            root,
            status=InvestigationStatus.RUNNING,
            stage=InvestigationStage.CLAIM_ANALYSIS,
        )
        normalized = await self._generate(
            ModelTask.NORMALIZE_CLAIM,
            AtomicClaim,
            {"claim_text": claim_text},
        )
        normalized = _anchor_claim_to_user_text(normalized, claim_text)
        self._repository.save_artifact(
            root.investigation_id,
            ArtifactType.CLAIM,
            normalized.claim_id,
            normalized,
        )
        decomposition = await self._generate(
            ModelTask.DECOMPOSE_CLAIM,
            ClaimDecomposition,
            {"root_claim": normalized.model_dump(mode="json")},
        )
        for _refinement_attempt in range(2):
            if not _contains_merged_material_component(decomposition):
                break
            decomposition = await self._generate(
                ModelTask.DECOMPOSE_CLAIM,
                ClaimDecomposition,
                {
                    "root_claim": normalized.model_dump(mode="json"),
                    "rejected_decomposition": decomposition.model_dump(mode="json"),
                    "validation_feedback": (
                        "At least one proposed component still joins independently "
                        "checkable assertions using a causal connector or a 'both A and B' "
                        "coordination. Split every independently checkable assertion into "
                        "its own complete component. Retain any shared premise, causal "
                        "direction, date, geography, and quantity in retained_context. Do "
                        "not include the full root as a component."
                    ),
                },
            )
        if _contains_merged_material_component(decomposition):
            raise ModelOutputError(
                "decomposition refinements still merge an independently checkable "
                "material assertion"
            )
        self._repository.save_artifact(
            root.investigation_id,
            ArtifactType.DECOMPOSITION,
            decomposition.decomposition_id,
            decomposition,
        )
        checkpoint = ComplexWorkflowCheckpoint(
            checkpoint_id=root.investigation_id,
            stage=ComplexCheckpointStage.DECOMPOSED,
            decomposition_id=decomposition.decomposition_id,
        )
        self._save_checkpoint(root, checkpoint)
        if interrupt_after is ComplexCheckpointStage.DECOMPOSED:
            raise ComplexWorkflowInterrupted("interrupted after decomposition checkpoint")
        return await self._execute(
            root,
            decomposition,
            checkpoint,
            interrupt_after=interrupt_after,
            interrupt_after_components=interrupt_after_components,
        )

    async def resume(
        self,
        investigation_id: UUID,
        *,
        interrupt_after: ComplexCheckpointStage | None = None,
        interrupt_after_components: int | None = None,
    ) -> ComplexInvestigationReport:
        """Resume from the latest valid typed checkpoint."""
        self._repository.initialize()
        self._model_usage = []
        root = self._repository.get_investigation(investigation_id)
        if root is None:
            raise LookupError(f"investigation not found: {investigation_id}")
        if root.status is InvestigationStatus.COMPLETED:
            return load_complex_report(self._repository, root.investigation_id)
        checkpoints = self._repository.list_artifacts(
            investigation_id,
            ArtifactType.CHECKPOINT,
            ComplexWorkflowCheckpoint,
        )
        decompositions = self._repository.list_artifacts(
            investigation_id,
            ArtifactType.DECOMPOSITION,
            ClaimDecomposition,
        )
        if not checkpoints or not decompositions:
            raise ValueError("complex investigation has no valid resume checkpoint")
        return await self._execute(
            root,
            decompositions[-1],
            checkpoints[-1],
            interrupt_after=interrupt_after,
            interrupt_after_components=interrupt_after_components,
        )

    async def _execute(
        self,
        root: Investigation,
        decomposition: ClaimDecomposition,
        checkpoint: ComplexWorkflowCheckpoint,
        *,
        interrupt_after: ComplexCheckpointStage | None,
        interrupt_after_components: int | None,
    ) -> ComplexInvestigationReport:
        completed = {item.claim_id: item for item in checkpoint.completed_components}
        failed = {item.claim_id: item for item in checkpoint.failed_components}
        component_reports: dict[UUID, InvestigationReport] = {
            claim_id: load_report(self._repository, item.investigation_id)
            for claim_id, item in completed.items()
        }
        newly_completed = 0
        for component in decomposition.components:
            if component.claim_id in component_reports or component.claim_id in failed:
                continue
            child_service = InvestigationService(
                repository=self._repository,
                model_provider=self._model_provider,
                search_provider=(
                    self._component_search_provider_factory(component)
                    if self._component_search_provider_factory is not None
                    else self._search_provider
                ),
                content_fetcher=self._content_fetcher,
                runtime_policy=self._runtime_policy,
            )
            try:
                report = await child_service.investigate(
                    component.text,
                    prepared_claim=component,
                    parent_investigation_id=root.investigation_id,
                )
            except Exception as error:
                matching_children = [
                    item
                    for item in self._repository.list_investigations()
                    if item.parent_investigation_id == root.investigation_id
                    and item.component_claim_id == component.claim_id
                ]
                failure = ComponentFailure(
                    claim_id=component.claim_id,
                    investigation_id=(
                        matching_children[-1].investigation_id if matching_children else None
                    ),
                    reason=f"{type(error).__name__}: {error}",
                )
                failed[component.claim_id] = failure
                checkpoint = checkpoint.model_copy(
                    update={
                        "stage": ComplexCheckpointStage.COMPONENTS,
                        "failed_components": tuple(failed.values()),
                    }
                )
                self._save_checkpoint(root, checkpoint)
                newly_completed += 1
                if (
                    interrupt_after_components is not None
                    and newly_completed >= interrupt_after_components
                ):
                    raise ComplexWorkflowInterrupted(
                        "interrupted after component checkpoint"
                    ) from error
                continue
            self._model_usage.extend(child_service.model_usage)
            link = ComponentExecution(
                claim_id=component.claim_id,
                investigation_id=report.investigation.investigation_id,
            )
            completed[component.claim_id] = link
            component_reports[component.claim_id] = report
            checkpoint = checkpoint.model_copy(
                update={
                    "stage": ComplexCheckpointStage.COMPONENTS,
                    "completed_components": tuple(completed.values()),
                    "failed_components": tuple(failed.values()),
                }
            )
            self._save_checkpoint(root, checkpoint)
            newly_completed += 1
            if (
                interrupt_after_components is not None
                and newly_completed >= interrupt_after_components
            ):
                raise ComplexWorkflowInterrupted("interrupted after component checkpoint")

        ordered_reports = tuple(
            component_reports[component.claim_id]
            for component in decomposition.components
            if component.claim_id in component_reports
        )
        stored_coverages = self._repository.list_artifacts(
            root.investigation_id,
            ArtifactType.COVERAGE,
            ClaimCoverage,
        )
        if stored_coverages:
            coverage = stored_coverages[-1]
        else:
            outcomes = tuple(
                (
                    ComponentOutcome(
                        claim_id=component.claim_id,
                        status=ComponentStatus.COMPLETED,
                        verdict_id=component_reports[component.claim_id].verdict.verdict_id,
                        verdict_label=component_reports[component.claim_id].verdict.label,
                        evidence_ids=tuple(
                            item.evidence_id
                            for item in component_reports[component.claim_id].evidence
                        ),
                    )
                    if component.claim_id in component_reports
                    else ComponentOutcome(
                        claim_id=component.claim_id,
                        status=ComponentStatus.FAILED,
                        unresolved_reason=failed[component.claim_id].reason,
                    )
                )
                for component in decomposition.components
            )
            coverage = ClaimCoverage(
                root_claim_id=decomposition.root_claim.claim_id,
                outcomes=outcomes,
            )
            self._repository.save_artifact(
                root.investigation_id,
                ArtifactType.COVERAGE,
                coverage.coverage_id,
                coverage,
            )
        component_verdicts = tuple(report.verdict for report in ordered_reports)
        evidence_ids = tuple(
            item.evidence_id for report in ordered_reports for item in report.evidence
        )
        stored_verdicts = self._repository.list_artifacts(
            root.investigation_id,
            ArtifactType.VERDICT,
            Verdict,
        )
        if checkpoint.stage in {
            ComplexCheckpointStage.AGGREGATED,
            ComplexCheckpointStage.AUDITED,
        }:
            if not stored_verdicts:
                raise ValueError("aggregation checkpoint is missing its parent verdict")
            parent_verdict = stored_verdicts[-1]
        else:
            label = (
                aggregate_component_label(component_verdicts)
                if component_verdicts
                else VerdictLabel.UNVERIFIABLE
            )
            if failed and component_verdicts:
                label = VerdictLabel.MIXED
            component_findings = "; ".join(
                (
                    f"({index}) "
                    f"{_abbreviate_component(component.text)} "
                    "— "
                    f"{component_reports[component.claim_id].verdict.label.value}"
                )
                for index, component in enumerate(decomposition.components, start=1)
                if component.claim_id in component_reports
            )
            parent_verdict = Verdict(
                claim_id=decomposition.root_claim.claim_id,
                label=label,
                concise_explanation=(
                    f"Component findings: {component_findings or 'none completed'}. "
                    f"With {len(failed)} failed component(s), these findings produce a "
                    f"{label.value} result for the submitted claim."
                ),
                detailed_reasoning=(
                    "The parent label was deterministically constrained from every material "
                    "component verdict; no component was omitted."
                ),
                decisive_evidence_ids=evidence_ids,
                unresolved_questions=tuple(
                    question
                    for verdict in component_verdicts
                    for question in verdict.unresolved_questions
                ),
                human_review_required=bool(failed)
                or any(verdict.human_review_required for verdict in component_verdicts),
                review_reason=(
                    "At least one material component failed or requires human review."
                    if failed
                    or any(verdict.human_review_required for verdict in component_verdicts)
                    else None
                ),
            )
            self._repository.save_artifact(
                root.investigation_id,
                ArtifactType.VERDICT,
                parent_verdict.verdict_id,
                parent_verdict,
            )
            checkpoint = checkpoint.model_copy(update={"stage": ComplexCheckpointStage.AGGREGATED})
            self._save_checkpoint(root, checkpoint)
            if interrupt_after is ComplexCheckpointStage.AGGREGATED:
                raise ComplexWorkflowInterrupted("interrupted after aggregation checkpoint")

        stored_audits = self._repository.list_artifacts(
            root.investigation_id,
            ArtifactType.AUDIT,
            SentenceAudit,
        )
        if checkpoint.stage is ComplexCheckpointStage.AUDITED:
            if not stored_audits:
                raise ValueError("audit checkpoint is missing its parent citation audit")
            audit = stored_audits[-1]
        else:
            child_audits = tuple(
                child_audit for report in ordered_reports for child_audit in report.audits
            )
            fully_composed = (
                bool(child_audits)
                and not failed
                and all(
                    child_audit.support_level is SupportLevel.FULL for child_audit in child_audits
                )
            )
            audit = SentenceAudit(
                sentence=parent_verdict.concise_explanation,
                cited_evidence_ids=evidence_ids,
                support_level=(SupportLevel.FULL if fully_composed else SupportLevel.PARTIAL),
                issue_type=None if fully_composed else AuditIssue.PARTIAL_SUPPORT,
                explanation=(
                    None
                    if fully_composed
                    else (
                        "At least one component failed or lacked a fully supported "
                        "child citation audit, so full support cannot be inherited."
                    )
                ),
            )
            self._repository.save_artifact(
                root.investigation_id,
                ArtifactType.AUDIT,
                audit.sentence_id,
                audit,
            )
            checkpoint = checkpoint.model_copy(update={"stage": ComplexCheckpointStage.AUDITED})
            self._save_checkpoint(root, checkpoint)
            if interrupt_after is ComplexCheckpointStage.AUDITED:
                raise ComplexWorkflowInterrupted("interrupted after audit checkpoint")

        root = self._transition(
            root,
            status=InvestigationStatus.COMPLETED,
            stage=InvestigationStage.COMPLETE,
        )
        checkpoint = checkpoint.model_copy(update={"stage": ComplexCheckpointStage.COMPLETE})
        self._save_checkpoint(root, checkpoint)
        self._event(
            root,
            TraceEventType.INVESTIGATION_COMPLETED,
            "Complex investigation completed with full material-component coverage.",
            {
                "component_count": len(ordered_reports),
                "coverage_rate": coverage.material_coverage_rate,
            },
        )
        return ComplexInvestigationReport(
            investigation=root,
            decomposition=decomposition,
            component_reports=ordered_reports,
            coverage=coverage,
            verdict=parent_verdict,
            audits=(audit,),
        )

    async def _generate(self, task, response_model, inputs):
        last_error: ModelOutputError | ModelUnavailableError | None = None
        for attempt in range(2):
            try:
                return await self._model_provider.generate(
                    task=task,
                    response_model=response_model,
                    inputs=inputs,
                )
            except (ModelOutputError, ModelUnavailableError) as error:
                last_error = error
                if attempt:
                    raise
            finally:
                take_usage = getattr(self._model_provider, "take_last_usage", None)
                if callable(take_usage):
                    usage = take_usage()
                    if usage is not None:
                        self._model_usage.append(usage)
        assert last_error is not None
        raise last_error

    def _save_checkpoint(
        self,
        root: Investigation,
        checkpoint: ComplexWorkflowCheckpoint,
    ) -> None:
        self._repository.save_artifact(
            root.investigation_id,
            ArtifactType.CHECKPOINT,
            checkpoint.checkpoint_id,
            checkpoint,
        )

    def _transition(
        self,
        investigation: Investigation,
        *,
        status: InvestigationStatus | None = None,
        stage: InvestigationStage | None = None,
    ) -> Investigation:
        updated = investigation.model_copy(
            update={
                "status": status or investigation.status,
                "stage": stage or investigation.stage,
                "updated_at": datetime.now(UTC),
            }
        )
        updated = Investigation.model_validate(updated.model_dump())
        self._repository.save_investigation(updated)
        return updated

    def _event(
        self,
        investigation: Investigation,
        event_type: TraceEventType,
        message: str,
        details: dict | None = None,
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


def _abbreviate_component(text: str) -> str:
    return text if len(text) <= 80 else text[:77] + "..."
