"""Stage 9.12 frozen comparison of direct, wrapper, unified and ablated paths."""

from __future__ import annotations

import hashlib
from pathlib import Path
from statistics import median
from time import perf_counter

from pydantic import Field

from claim_polygraph_ng.application import (
    AuthoritativeMultiAgentResearchAdapter,
    InvestigationService,
    LangGraphInvestigationOrchestrator,
    LangGraphResearchFanOutWorkflow,
    SharedResearchOperations,
    StructuredResearchWorker,
)
from claim_polygraph_ng.application.langgraph_authoritative import (
    AuthoritativeFixtureLangGraphWorkflow,
)
from claim_polygraph_ng.domain import (
    EvidenceStance,
    ResearchBudget,
    ResearchResult,
    ResearchRole,
    ReviewDecision,
    ReviewDecisionKind,
)
from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.investigation import InvestigationReport
from claim_polygraph_ng.evaluation.evidence_provider import (
    BenchmarkEvidenceSearchProvider,
)
from claim_polygraph_ng.evaluation.phase9_baseline import (
    Phase9ArtifactHash,
    Phase9BaselineVerification,
    load_phase9_baseline,
)
from claim_polygraph_ng.evaluation.runner import load_benchmark
from claim_polygraph_ng.persistence import (
    SQLiteInvestigationRepository,
    SQLiteResearchRepository,
    SQLiteReviewLedger,
)
from claim_polygraph_ng.providers import DeterministicModelProvider


class Phase9VariantCaseResult(DomainModel):
    case_id: str
    expected_verdict: str
    verdict: str
    verdict_matches_review: bool
    verdict_equivalent_to_direct: bool
    completed: bool
    review_routed: bool
    evidence_count: int = Field(ge=0)
    reviewed_evidence_count: int = Field(ge=1)
    evidence_coverage_ratio: float = Field(ge=0)
    evidence_family_count: int = Field(ge=0)
    reviewed_family_count: int = Field(ge=1)
    family_coverage_ratio: float = Field(ge=0)
    challenge_evidence_count: int = Field(ge=0)
    citation_support_rate: float = Field(ge=0, le=1)
    search_calls: int = Field(ge=0)
    model_calls: int = Field(ge=0)
    paid_operation_count: int = Field(ge=0)
    duplicate_paid_operations: int = Field(ge=0)
    latency_seconds: float = Field(ge=0)


class Phase9VariantSummary(DomainModel):
    variant: str
    case_count: int = Field(ge=1)
    completion_rate: float = Field(ge=0, le=1)
    reviewed_label_accuracy: float = Field(ge=0, le=1)
    direct_verdict_equivalence: float = Field(ge=0, le=1)
    review_routing_recall: float = Field(ge=0, le=1)
    mean_evidence_coverage_ratio: float = Field(ge=0)
    mean_family_coverage_ratio: float = Field(ge=0)
    challenge_coverage_rate: float = Field(ge=0, le=1)
    citation_support_rate: float = Field(ge=0, le=1)
    total_search_calls: int = Field(ge=0)
    total_model_calls: int = Field(ge=0)
    observed_fixture_cost_usd: float = 0
    provider_work_unit_ratio: float = Field(ge=0)
    duplicate_paid_operations: int = Field(ge=0)
    median_latency_seconds: float = Field(ge=0)
    median_latency_ratio_to_direct: float = Field(ge=0)
    cases: tuple[Phase9VariantCaseResult, ...]


class Phase9ComparisonEvaluation(DomainModel):
    evaluation_id: str = "phase9-stage9.12-frozen-comparison-v1"
    dataset_id: str
    dataset_version: int
    case_count: int = 20
    direct: Phase9VariantSummary
    previous_wrapper: Phase9VariantSummary
    unified: Phase9VariantSummary
    minus_challenger: Phase9VariantSummary
    mandatory_gates_passed: bool
    failed_gates: tuple[str, ...]
    challenger_material_gain_cases: int = Field(ge=0)
    unified_material_gain_cases: int = Field(ge=0)
    recommended_disposition: str
    recorded_baseline_cost_usd: float = Field(ge=0)
    observed_fixture_cost_usd: float = 0
    external_model_calls: int = 0
    live_search_calls: int = 0
    network_fetches: int = 0
    pdf_downloads: int = 0
    limitations: tuple[str, ...]


class Phase9ComparisonManifest(DomainModel):
    manifest_id: str = "phase9-stage9.12-release-manifest-v1"
    artifacts: tuple[Phase9ArtifactHash, ...]
    external_model_calls: int = 0
    live_search_calls: int = 0
    network_fetches: int = 0
    pdf_downloads: int = 0


class _AblatedResearchWorker:
    def __init__(self, delegate, roles: frozenset[ResearchRole]) -> None:
        self._delegate = delegate
        self._roles = roles

    async def run(self, assignment, operations) -> ResearchResult:
        if assignment.role not in self._roles:
            return await self._delegate.run(assignment, operations)
        return ResearchResult(
            assignment_id=assignment.assignment_id,
            role=assignment.role,
            component_id=assignment.component_id,
            query_ids=(),
            unresolved_requirement_ids=assignment.requirement_ids,
            search_call_count=0,
            fetch_call_count=0,
            model_call_count=0,
            estimated_cost_usd=0,
            duration_seconds=0,
            failure_reason=f"{assignment.role.value} removed by declared ablation",
        )


class _InlineOnlyFetcher:
    async def fetch(self, url: str):
        raise RuntimeError(f"reviewed benchmark evidence must remain inline: {url}")


class _BenchmarkStanceModelProvider(DeterministicModelProvider):
    """Deterministic classifier using only reviewed passage-level stance labels."""

    def __init__(self, case) -> None:
        self._stance_by_passage = {
            item.excerpt.strip(): item.stance for item in case.candidate_evidence
        }

    def _classify_evidence(self, inputs):
        evidence = super()._classify_evidence(inputs)
        stance = self._stance_by_passage.get(str(inputs["passage"]).strip())
        return evidence if stance is None else evidence.model_copy(update={"stance": stance})


_ARTIFACTS = (
    ("comparison_evaluator", "src/claim_polygraph_ng/evaluation/phase9_comparison.py"),
    ("comparison_runner", "scripts/run_phase9_comparison.py"),
    ("comparison_tests", "tests/integration/test_phase9_comparison.py"),
    ("comparison_result", "artifacts/evaluations/phase9-stage9.12-frozen-comparison-v1.json"),
    ("stage9_11_manifest", "artifacts/evaluations/phase9-stage9.11-release-manifest-v1.json"),
    ("stage9_12_report", "docs/PHASE_9_STAGE_9.12_COMPLETION_REPORT.md"),
)


async def evaluate_phase9_comparison(
    project_root: str | Path,
    work_directory: str | Path,
    *,
    limit: int | None = None,
) -> Phase9ComparisonEvaluation:
    root = Path(project_root).resolve()
    work = Path(work_directory).resolve()
    work.mkdir(parents=True, exist_ok=True)
    dataset = load_benchmark(root / "benchmarks/initial_claims_v1.json")
    cases = dataset.cases[:limit]
    if not cases:
        raise ValueError("comparison requires at least one benchmark case")
    baseline = load_phase9_baseline(
        root / "artifacts/evaluations/phase9-stage9.0-baseline-v1.json"
    )
    direct_results: list[Phase9VariantCaseResult] = []
    wrapper_results: list[Phase9VariantCaseResult] = []
    unified_results: list[Phase9VariantCaseResult] = []
    ablated_results: list[Phase9VariantCaseResult] = []

    for case in cases:
        direct_report, direct_meta = await _run_direct(case, work / "direct")
        direct_result = _case_result(
            case, direct_report, direct_report.verdict.label.value, direct_meta
        )
        direct_results.append(direct_result)

        wrapper_report, wrapper_meta = await _run_wrapper(case, work / "wrapper")
        wrapper_results.append(
            _case_result(
                case, wrapper_report, direct_result.verdict, wrapper_meta
            )
        )

        unified_report, unified_meta = await _run_unified(
            case, work / "unified", ablate=frozenset()
        )
        unified_results.append(
            _case_result(
                case, unified_report, direct_result.verdict, unified_meta
            )
        )

        ablated_report, ablated_meta = await _run_unified(
            case,
            work / "minus-challenger",
            ablate=frozenset({ResearchRole.CHALLENGER}),
        )
        ablated_results.append(
            _case_result(
                case, ablated_report, direct_result.verdict, ablated_meta
            )
        )

    direct = _summary("direct", direct_results, direct_results)
    wrapper = _summary("previous_wrapper", wrapper_results, direct_results)
    unified = _summary("unified", unified_results, direct_results)
    ablated = _summary("minus_challenger", ablated_results, direct_results)
    challenger_gain = sum(
        full.challenge_evidence_count > removed.challenge_evidence_count
        or full.evidence_family_count > removed.evidence_family_count
        for full, removed in zip(unified_results, ablated_results, strict=True)
    )
    unified_gain = sum(
        full.evidence_count > control.evidence_count
        or full.evidence_family_count > control.evidence_family_count
        for full, control in zip(unified_results, direct_results, strict=True)
    )
    failed = []
    gates = {
        "direct workflow did not complete every case": direct.completion_rate == 1,
        "previous wrapper changed an authoritative verdict": (
            wrapper.direct_verdict_equivalence == 1
        ),
        "unified graph changed an authoritative verdict": (
            unified.direct_verdict_equivalence == 1
        ),
        "unified graph reduced reviewed-label accuracy": (
            unified.reviewed_label_accuracy >= direct.reviewed_label_accuracy
        ),
        "unified graph reduced evidence coverage": (
            unified.mean_evidence_coverage_ratio >= direct.mean_evidence_coverage_ratio
        ),
        "unified graph reduced family coverage": (
            unified.mean_family_coverage_ratio >= direct.mean_family_coverage_ratio
        ),
        "unified citation support below 95%": unified.citation_support_rate >= 0.95,
        "review routing recall below 100%": unified.review_routing_recall == 1,
        "duplicate paid operations observed": unified.duplicate_paid_operations == 0,
        "unified deterministic latency above 3x direct": (
            unified.median_latency_ratio_to_direct <= 3
        ),
    }
    failed.extend(message for message, passed in gates.items() if not passed)
    mandatory_passed = not failed
    disposition = (
        "eligible_for_stage9_13_audit"
        if mandatory_passed and unified_gain > 0
        else "retain_observational_default"
        if mandatory_passed
        else "do_not_promote_before_remediation"
    )
    return Phase9ComparisonEvaluation(
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.version,
        case_count=len(cases),
        direct=direct,
        previous_wrapper=wrapper,
        unified=unified,
        minus_challenger=ablated,
        mandatory_gates_passed=mandatory_passed,
        failed_gates=tuple(failed),
        challenger_material_gain_cases=challenger_gain,
        unified_material_gain_cases=unified_gain,
        recommended_disposition=disposition,
        recorded_baseline_cost_usd=round(
            sum(item.estimated_cost_usd for item in baseline.cases[: len(cases)]), 9
        ),
        limitations=(
            "All paths replay the same reviewed evidence annotations through local "
            "case-scoped providers; no workflow receives hidden benchmark labels.",
            "Observed fixture cost is zero. Provider work units expose relative call "
            "volume, while recorded historical cost is context rather than a new quote.",
            "Local SQLite and fixture latency measures orchestration overhead, not "
            "hosted provider latency.",
            "Reviewed-label accuracy remains descriptive on only twenty curated cases "
            "and is not an empirical confidence calibration.",
            "The minus-challenger run suppresses challenger execution after assignment; "
            "it preserves routing and stopping behavior so the role contribution is auditable.",
        ),
    )


async def _run_direct(case, directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    repository = SQLiteInvestigationRepository(directory / f"{case.case_id}.db")
    service = InvestigationService(
        repository=repository,
        model_provider=_BenchmarkStanceModelProvider(case),
        search_provider=BenchmarkEvidenceSearchProvider(case),
    )
    started = perf_counter()
    report = await service.investigate(case.claim)
    return report, _metadata(report, repository, perf_counter() - started, False, 0)


async def _run_wrapper(case, directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    repository = SQLiteInvestigationRepository(directory / f"{case.case_id}.db")
    reviews = SQLiteReviewLedger(directory / f"{case.case_id}-reviews.db")
    service = InvestigationService(
        repository=repository,
        model_provider=_BenchmarkStanceModelProvider(case),
        search_provider=BenchmarkEvidenceSearchProvider(case),
    )
    wrapper = LangGraphInvestigationOrchestrator(
        investigate_authoritatively=service.investigate,
        checkpoint_path=directory / f"{case.case_id}-wrapper.db",
        reviews=reviews,
    )
    started = perf_counter()
    report = await wrapper.investigate(case.claim)
    routed = any(
        item.investigation_id == report.investigation.investigation_id
        for item in reviews.list_requests()
    )
    return report, _metadata(
        report, repository, perf_counter() - started, routed, 0
    )


async def _run_unified(case, directory: Path, *, ablate: frozenset[ResearchRole]):
    directory.mkdir(parents=True, exist_ok=True)
    repository = SQLiteInvestigationRepository(directory / f"{case.case_id}.db")
    research = SQLiteResearchRepository(directory / f"{case.case_id}-research.db")
    reviews = SQLiteReviewLedger(directory / f"{case.case_id}-reviews.db")
    provider = BenchmarkEvidenceSearchProvider(case)
    model_provider = _BenchmarkStanceModelProvider(case)
    service = InvestigationService(
        repository=repository,
        model_provider=model_provider,
        search_provider=provider,
    )
    base_worker = StructuredResearchWorker(research, model_provider)
    worker = (
        _AblatedResearchWorker(base_worker, ablate) if ablate else base_worker
    )
    workflow = AuthoritativeFixtureLangGraphWorkflow(
        service=service,
        investigations=repository,
        langgraph_checkpoint_path=directory / f"{case.case_id}-langgraph.db",
        state_checkpoint_path=directory / f"{case.case_id}-state.db",
        research_adapter=AuthoritativeMultiAgentResearchAdapter(
            workflow=LangGraphResearchFanOutWorkflow(
                repository=research,
                operations=SharedResearchOperations(
                    repository=research,
                    search_provider=provider,
                    fetcher=_InlineOnlyFetcher(),
                ),
                worker=worker,
            )
        ),
        research_budget=ResearchBudget(
            maximum_rounds=2,
            maximum_concurrent_roles=3,
            maximum_role_activations_per_component=5,
            maximum_pages_per_component=20,
            maximum_search_calls=20,
            maximum_model_calls=20,
            maximum_cost_usd=0,
        ),
        review_ledger=reviews,
        require_human_review=True,
    )
    thread_id = f"stage9.12:{case.case_id}:{'minus-challenger' if ablate else 'unified'}"
    started = perf_counter()
    result = await workflow.start(case.claim, thread_id=thread_id)
    routed = result.interrupt is not None
    if result.interrupt is not None:
        result = await workflow.resume(
            thread_id,
            ReviewDecision(
                kind=ReviewDecisionKind.APPROVE,
                reviewer_identity="Stage 9.12 Replay Reviewer",
                rationale="Approve the frozen deterministic comparison disposition.",
            ),
            approver_identity="Stage 9.12 Distinct Approver",
        )
    if result.report is None:
        raise RuntimeError(f"{case.case_id} unified workflow produced no report")
    duplicates = len(result.state.paid_receipts) - len(
        {item.receipt_id for item in result.state.paid_receipts}
    )
    return result.report, _metadata(
        result.report,
        repository,
        perf_counter() - started,
        routed,
        max(0, duplicates),
        state=result.state,
    )


def _metadata(report, repository, latency, routed, duplicates, *, state=None):
    events = repository.list_events(report.investigation.investigation_id)
    terminal = events[-1].details if events else {}
    return {
        "latency": round(latency, 6),
        "routed": routed,
        "duplicates": duplicates,
        "search_calls": (
            state.consumption.search_calls
            if state is not None
            else int(terminal.get("search_calls", 0))
        ),
        "model_calls": (
            int(terminal.get("llm_calls", 0)) + state.consumption.model_calls
            if state is not None
            else int(terminal.get("llm_calls", 0))
        ),
        "paid_operations": len(state.paid_receipts) if state is not None else 0,
    }


def _case_result(case, report: InvestigationReport, direct_verdict: str, metadata):
    families = report.independence_analysis.independent_family_count
    citation_rate = (
        sum(item.support_level.value == "full" for item in report.audits)
        / len(report.audits)
        if report.audits
        else 1
    )
    challenge = sum(
        item.stance in {EvidenceStance.CONTRADICTS, EvidenceStance.QUALIFIES}
        for item in report.evidence
    )
    reviewed_families = len(
        {item.independence_note for item in case.candidate_evidence}
    )
    return Phase9VariantCaseResult(
        case_id=case.case_id,
        expected_verdict=case.expected_verdict.value,
        verdict=report.verdict.label.value,
        verdict_matches_review=report.verdict.label is case.expected_verdict,
        verdict_equivalent_to_direct=report.verdict.label.value == direct_verdict,
        completed=report.investigation.status.value == "completed",
        review_routed=metadata["routed"],
        evidence_count=len(report.evidence),
        reviewed_evidence_count=len(case.candidate_evidence),
        evidence_coverage_ratio=len(report.evidence) / len(case.candidate_evidence),
        evidence_family_count=families,
        reviewed_family_count=max(1, reviewed_families),
        family_coverage_ratio=families / max(1, reviewed_families),
        challenge_evidence_count=challenge,
        citation_support_rate=citation_rate,
        search_calls=metadata["search_calls"],
        model_calls=metadata["model_calls"],
        paid_operation_count=metadata["paid_operations"],
        duplicate_paid_operations=metadata["duplicates"],
        latency_seconds=metadata["latency"],
    )


def _summary(variant, results, direct_results):
    count = len(results)
    direct_median = median(item.latency_seconds for item in direct_results)
    work = sum(item.search_calls + item.model_calls for item in results)
    direct_work = sum(
        item.search_calls + item.model_calls for item in direct_results
    )
    return Phase9VariantSummary(
        variant=variant,
        case_count=count,
        completion_rate=sum(item.completed for item in results) / count,
        reviewed_label_accuracy=sum(item.verdict_matches_review for item in results) / count,
        direct_verdict_equivalence=sum(
            item.verdict_equivalent_to_direct for item in results
        )
        / count,
        review_routing_recall=sum(item.review_routed for item in results) / count,
        mean_evidence_coverage_ratio=sum(
            item.evidence_coverage_ratio for item in results
        )
        / count,
        mean_family_coverage_ratio=sum(item.family_coverage_ratio for item in results)
        / count,
        challenge_coverage_rate=sum(
            item.challenge_evidence_count > 0 for item in results
        )
        / count,
        citation_support_rate=sum(item.citation_support_rate for item in results)
        / count,
        total_search_calls=sum(item.search_calls for item in results),
        total_model_calls=sum(item.model_calls for item in results),
        provider_work_unit_ratio=work / max(1, direct_work),
        duplicate_paid_operations=sum(item.duplicate_paid_operations for item in results),
        median_latency_seconds=median(item.latency_seconds for item in results),
        median_latency_ratio_to_direct=(
            median(item.latency_seconds for item in results) / max(direct_median, 0.000001)
        ),
        cases=tuple(results),
    )


def export_evaluation(evaluation: Phase9ComparisonEvaluation, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(evaluation.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return target


def build_release_manifest(root: str | Path) -> Phase9ComparisonManifest:
    project = Path(root).resolve()
    manifest = Phase9ComparisonManifest(
        artifacts=tuple(
            Phase9ArtifactHash(
                artifact_id=artifact_id,
                path=path,
                sha256=hashlib.sha256((project / path).read_bytes()).hexdigest(),
            )
            for artifact_id, path in _ARTIFACTS
        )
    )
    target = project / "artifacts/evaluations/phase9-stage9.12-release-manifest-v1.json"
    target.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_release_manifest(manifest, root):
    project = Path(root).resolve()
    errors = tuple(
        f"{item.artifact_id}: SHA-256 mismatch"
        for item in manifest.artifacts
        if not (project / item.path).is_file()
        or hashlib.sha256((project / item.path).read_bytes()).hexdigest() != item.sha256
    )
    return Phase9BaselineVerification(
        valid=not errors,
        checked_artifact_count=len(manifest.artifacts) - len(errors),
        checked_contract_count=10,
        errors=errors,
    )
