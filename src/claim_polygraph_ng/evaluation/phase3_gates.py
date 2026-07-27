"""Machine-checkable Phase 3 release-gate audit."""

import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import Field

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.evaluation.models import (
    AnnotationStatus,
    BenchmarkDataset,
    ComplexEvaluationSummary,
    PageFetchEvaluationSummary,
    RetrievalEvaluationSummary,
    SemanticPassageEvaluationSummary,
)
from claim_polygraph_ng.evaluation.stability import compare_complex_evaluations


class GateState(StrEnum):
    """Outcome of one declared Phase 3 gate."""

    PASSED = "passed"
    FAILED = "failed"
    PENDING = "pending"


class Phase3GateResult(DomainModel):
    """One auditable threshold comparison."""

    gate_id: str = Field(pattern=r"^[a-z0-9_]+$")
    state: GateState
    requirement: str
    observed: str
    evidence: tuple[str, ...] = ()


class Phase3GateAudit(DomainModel):
    """Aggregate release decision derived from declared artifacts."""

    dataset_id: str
    dataset_version: int
    generated_at: datetime
    release_ready: bool
    passed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    pending_count: int = Field(ge=0)
    gates: tuple[Phase3GateResult, ...]


def audit_phase3_gates(
    dataset: BenchmarkDataset,
    retrieval: RetrievalEvaluationSummary,
    pages: PageFetchEvaluationSummary,
    *,
    baseline_semantic: SemanticPassageEvaluationSummary,
    semantic: SemanticPassageEvaluationSummary | None = None,
    first_run: ComplexEvaluationSummary | None = None,
    second_run: ComplexEvaluationSummary | None = None,
) -> Phase3GateAudit:
    """Evaluate the numerical Phase 3 gates without silently omitting inputs."""
    _require_identity(dataset, retrieval.dataset_id, retrieval.dataset_version, "retrieval")
    _require_identity(dataset, pages.dataset_id, pages.dataset_version, "page evaluation")
    if (
        baseline_semantic.dataset_id != dataset.dataset_id
        or baseline_semantic.dataset_version > dataset.version
    ):
        raise ValueError(
            "Phase 2 semantic baseline must use the same benchmark identity "
            "and an earlier or equal version"
        )
    if semantic is not None:
        _require_identity(dataset, semantic.dataset_id, semantic.dataset_version, "semantic")

    gates: list[Phase3GateResult] = []
    target_cases = tuple(
        case for case in dataset.cases if 1 <= int(case.case_id.removeprefix("CPNG-")) <= 20
    )
    reviewed = tuple(
        case for case in target_cases if case.annotation_status is AnnotationStatus.REVIEWED
    )
    distinct = tuple(
        case
        for case in reviewed
        if case.annotated_by
        and case.approved_by
        and case.annotated_by.casefold() != case.approved_by.casefold()
    )
    gates.append(
        _threshold(
            "human_reviewed_benchmark",
            len(reviewed) == 20 and len(distinct) == 20,
            "CPNG-001 through CPNG-020 reviewed with typed, distinct approval",
            f"{len(reviewed)}/20 reviewed; {len(distinct)}/20 distinctly approved",
            ("benchmark dataset",),
            pending=len(reviewed) < 20,
        )
    )
    reviewed_complex = sum(bool(case.expected_components) for case in reviewed)
    gates.append(
        _threshold(
            "complex_case_representation",
            reviewed_complex >= 5,
            "At least 5 reviewed cases have 2+ material components",
            f"{reviewed_complex} reviewed complex cases",
            ("benchmark dataset",),
            pending=len(reviewed) < 20,
        )
    )

    gates.extend(_retrieval_gates(retrieval, pages, semantic, baseline_semantic))
    gates.append(_rights_gate(pages))
    gates.extend(_run_gates("declared_run_1", first_run, dataset))
    gates.extend(_run_gates("declared_run_2", second_run, dataset))
    gates.extend(_stability_gates(first_run, second_run))

    passed_count = sum(gate.state is GateState.PASSED for gate in gates)
    failed_count = sum(gate.state is GateState.FAILED for gate in gates)
    pending_count = sum(gate.state is GateState.PENDING for gate in gates)
    return Phase3GateAudit(
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.version,
        generated_at=datetime.now(UTC),
        release_ready=failed_count == 0 and pending_count == 0,
        passed_count=passed_count,
        failed_count=failed_count,
        pending_count=pending_count,
        gates=tuple(gates),
    )


def export_phase3_gate_audit(audit: Phase3GateAudit, path: str | Path) -> Path:
    """Persist the gate decision as a stable JSON artifact."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(audit.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output


def _retrieval_gates(
    retrieval: RetrievalEvaluationSummary,
    pages: PageFetchEvaluationSummary,
    semantic: SemanticPassageEvaluationSummary | None,
    baseline: SemanticPassageEvaluationSummary,
) -> tuple[Phase3GateResult, ...]:
    candidate_case_rate = sum(result.result_count > 0 for result in retrieval.results) / len(
        retrieval.results
    )
    combined_recall = (
        semantic.combined_passage_recall if semantic is not None else pages.passage_lexical_recall
    )
    first_ten = tuple(
        result for result in pages.results if int(result.case_id.removeprefix("CPNG-")) <= 10
    )
    first_ten_reference_count = sum(result.reference_count for result in first_ten)
    first_ten_match_count = sum(result.matched_reference_count for result in first_ten)
    first_ten_recall = (
        first_ten_match_count / first_ten_reference_count if first_ten_reference_count else None
    )
    baseline_recall = baseline.combined_passage_recall
    regression_passed = (
        first_ten_recall is not None
        and baseline_recall is not None
        and first_ten_recall >= baseline_recall - 0.03
    )
    return (
        _threshold(
            "live_query_completion",
            retrieval.completion_rate >= 0.9,
            "At least 90% live query completion",
            f"{retrieval.completion_rate:.2%}",
            ("retrieval evaluation",),
        ),
        _threshold(
            "live_candidate_coverage",
            candidate_case_rate >= 0.9,
            "At least 90% of cases have a live candidate",
            f"{candidate_case_rate:.2%}",
            ("retrieval evaluation",),
        ),
        _threshold(
            "component_query_completion",
            retrieval.component_query_completion_rate is not None
            and retrieval.component_query_completion_rate >= 0.9,
            "At least 90% component query completion",
            _percent(retrieval.component_query_completion_rate),
            ("retrieval evaluation",),
        ),
        _threshold(
            "component_candidate_coverage",
            retrieval.component_candidate_rate is not None
            and retrieval.component_candidate_rate >= 0.9,
            "At least 90% of material components have a candidate",
            _percent(retrieval.component_candidate_rate),
            ("retrieval evaluation",),
        ),
        _threshold(
            "reviewed_passage_recall",
            combined_recall is not None and combined_recall >= 0.8,
            "At least 80% combined reviewed-passage recall",
            _percent(combined_recall),
            ("page evaluation", "semantic evaluation" if semantic else "lexical-only pass"),
        ),
        _threshold(
            "first_ten_retrieval_regression",
            regression_passed,
            "First-ten recall no more than 3 points below Phase 2",
            (f"Phase 3 {_percent(first_ten_recall)} vs Phase 2 {_percent(baseline_recall)}"),
            ("page evaluation", "Phase 2 semantic baseline"),
        ),
    )


def _rights_gate(pages: PageFetchEvaluationSummary) -> Phase3GateResult:
    fetched_pdfs = tuple(
        page
        for result in pages.results
        for page in result.pages
        if page.fetched
        and (
            str(page.requested_url).casefold().split("?", maxsplit=1)[0].endswith(".pdf")
            or (page.content_type or "").casefold().startswith("application/pdf")
        )
    )
    return _threshold(
        "rights_compliance",
        not fetched_pdfs,
        "Zero unapproved PDF downloads",
        f"{len(fetched_pdfs)} fetched PDF candidates",
        ("page evaluation",),
    )


def _run_gates(
    prefix: str,
    run: ComplexEvaluationSummary | None,
    dataset: BenchmarkDataset,
) -> tuple[Phase3GateResult, ...]:
    if run is None:
        return tuple(
            Phase3GateResult(
                gate_id=f"{prefix}_{suffix}",
                state=GateState.PENDING,
                requirement=requirement,
                observed="declared run artifact not supplied",
            )
            for suffix, requirement in (
                ("completion", "At least 90% end-to-end completion"),
                ("accuracy", "At least 85% verdict accuracy"),
                ("parent_citations", "At least 95% full parent citation support"),
                ("decomposition", "100% parent linkage and context-contract validity"),
                ("material_coverage", "At least 90% material-component coverage"),
                ("cost", "At most $0.02 per completed component"),
            )
        )
    _require_identity(dataset, run.dataset_id, run.dataset_version, prefix)
    return (
        _threshold(
            f"{prefix}_completion",
            run.completion_rate >= 0.9,
            "At least 90% end-to-end completion",
            f"{run.completion_rate:.2%}",
            (prefix,),
        ),
        _threshold(
            f"{prefix}_accuracy",
            run.verdict_accuracy is not None and run.verdict_accuracy >= 0.85,
            "At least 85% verdict accuracy",
            _percent(run.verdict_accuracy),
            (prefix,),
            pending=run.verdict_accuracy is None,
        ),
        _threshold(
            f"{prefix}_parent_citations",
            run.parent_citation_full_rate is not None and run.parent_citation_full_rate >= 0.95,
            "At least 95% full parent citation support",
            _percent(run.parent_citation_full_rate),
            (prefix,),
        ),
        _threshold(
            f"{prefix}_decomposition",
            run.parent_linkage_valid_rate == 1.0 and run.context_contract_valid_rate == 1.0,
            "100% parent linkage and context-contract validity",
            (
                f"linkage {run.parent_linkage_valid_rate:.2%}; "
                f"context {run.context_contract_valid_rate:.2%}"
            ),
            (prefix,),
        ),
        _threshold(
            f"{prefix}_material_coverage",
            run.material_component_coverage_rate >= 0.9,
            "At least 90% material-component coverage",
            f"{run.material_component_coverage_rate:.2%}",
            (prefix,),
        ),
        _threshold(
            f"{prefix}_cost",
            run.mean_estimated_model_cost_per_completed_component_usd <= 0.02,
            "At most $0.02 per completed component",
            f"${run.mean_estimated_model_cost_per_completed_component_usd:.6f}",
            (prefix,),
        ),
    )


def _stability_gates(
    first: ComplexEvaluationSummary | None,
    second: ComplexEvaluationSummary | None,
) -> tuple[Phase3GateResult, ...]:
    if first is None or second is None:
        pending = Phase3GateResult(
            gate_id="exact_repeated_label_stability",
            state=GateState.PENDING,
            requirement="At least 90% exact repeated-label stability",
            observed="both declared run artifacts are required",
        )
        return (pending,)
    stability = compare_complex_evaluations(first, second)
    return (
        _threshold(
            "exact_repeated_label_stability",
            stability.exact_verdict_stability_rate is not None
            and stability.exact_verdict_stability_rate >= 0.9,
            "At least 90% exact repeated-label stability",
            _percent(stability.exact_verdict_stability_rate),
            ("derived two-run stability comparison",),
        ),
    )


def _threshold(
    gate_id: str,
    passed: bool,
    requirement: str,
    observed: str,
    evidence: tuple[str, ...] = (),
    *,
    pending: bool = False,
) -> Phase3GateResult:
    state = GateState.PENDING if pending else GateState.PASSED if passed else GateState.FAILED
    return Phase3GateResult(
        gate_id=gate_id,
        state=state,
        requirement=requirement,
        observed=observed,
        evidence=evidence,
    )


def _require_identity(
    dataset: BenchmarkDataset,
    dataset_id: str,
    dataset_version: int,
    artifact_name: str,
) -> None:
    if dataset_id != dataset.dataset_id or dataset_version != dataset.version:
        raise ValueError(f"{artifact_name} does not match the benchmark identity and version")


def _percent(value: float | None) -> str:
    return "not available" if value is None else f"{value:.2%}"
