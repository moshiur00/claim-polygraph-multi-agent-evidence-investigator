"""Zero-cost preflight and structural dry run for the locked Phase 4 pilot."""

import json
import statistics
from pathlib import Path

from pydantic import Field

from claim_polygraph_ng.application import (
    MultiAgentInvestigationService,
    SharedResearchOperations,
)
from claim_polygraph_ng.domain import (
    AtomicClaim,
    ClaimType,
    ResearchBudget,
    ResearchRequirement,
    ResearchRequirementKind,
    SourceType,
    SupportLevel,
    VerdictLabel,
)
from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.evaluation.evidence_provider import BenchmarkEvidenceSearchProvider
from claim_polygraph_ng.evaluation.models import BenchmarkCase, BenchmarkDataset
from claim_polygraph_ng.evaluation.phase4_manifest import (
    Phase4ExperimentManifest,
    verify_phase4_manifest,
)
from claim_polygraph_ng.evaluation.stability import load_complex_evaluation
from claim_polygraph_ng.persistence import SQLiteResearchRepository


class Phase4PilotCaseBaseline(DomainModel):
    """Matched Phase 3 control values for one locked pilot case."""

    case_id: str
    expected_component_count: int = Field(ge=1)
    verdict_matches: bool | None
    citation_full: bool
    model_call_count: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0.0)
    duration_seconds: float = Field(ge=0.0)


class Phase4PilotPreflight(DomainModel):
    """Machine-checkable authorization boundary before paid execution."""

    manifest_id: str
    valid: bool
    pilot_case_ids: tuple[str, ...]
    component_count: int = Field(ge=0)
    controls: tuple[Phase4PilotCaseBaseline, ...]
    phase3_control_cost_usd: float = Field(ge=0.0)
    maximum_phase4_cost_usd: float = Field(ge=0.0)
    phase3_median_latency_seconds: float = Field(ge=0.0)
    maximum_phase4_median_latency_seconds: float = Field(ge=0.0)
    estimated_role_activations: int = Field(ge=0)
    maximum_search_calls: int = Field(ge=0)
    maximum_fetched_pages: int = Field(ge=0)
    paid_calls_authorized: bool = False
    errors: tuple[str, ...] = ()


class Phase4DryRunCase(DomainModel):
    """Structural result from reviewed evidence with deterministic reasoning."""

    case_id: str
    activated_roles: tuple[str, ...]
    stopping_decision: str
    source_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    independent_family_count: int = Field(ge=0)
    search_calls: int = Field(ge=0)
    fetch_calls: int = Field(ge=0)
    model_calls: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0.0)
    citations_grounded: bool
    failure: str | None = None


class Phase4DryRunSummary(DomainModel):
    """Aggregate zero-cost pilot plumbing check."""

    manifest_id: str
    provider_mode: str
    valid: bool
    case_count: int = Field(ge=0)
    completed_count: int = Field(ge=0)
    total_search_calls: int = Field(ge=0)
    total_fetch_calls: int = Field(ge=0)
    total_model_calls: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0.0)
    results: tuple[Phase4DryRunCase, ...]
    limitations: tuple[str, ...]


class Phase4PaidComponentResult(DomainModel):
    """One component result from the authorized paid pilot."""

    component_number: int = Field(ge=1)
    component_text: str
    verdict_label: VerdictLabel
    citation_support: SupportLevel
    source_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    independent_family_count: int = Field(ge=0)
    model_call_count: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0.0)
    duration_seconds: float = Field(ge=0.0)


class Phase4PaidPilotCaseResult(DomainModel):
    """Matched parent-level result for one locked pilot case."""

    case_id: str
    completed: bool
    expected_verdict: VerdictLabel
    verdict_label: VerdictLabel | None = None
    verdict_matches: bool | None = None
    phase3_verdict_matches: bool | None = None
    component_results: tuple[Phase4PaidComponentResult, ...] = ()
    citation_full: bool = False
    model_call_count: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0.0)
    duration_seconds: float = Field(ge=0.0)
    error: str | None = None


class Phase4PaidPilotSummary(DomainModel):
    """Declared paid pilot result and automatic go/no-go decision."""

    manifest_id: str
    provider_mode: str
    case_count: int = Field(ge=0)
    completed_count: int = Field(ge=0)
    verdict_accuracy: float | None = Field(default=None, ge=0.0, le=1.0)
    phase3_control_accuracy: float | None = Field(default=None, ge=0.0, le=1.0)
    improved_case_count: int = Field(ge=0)
    regressed_case_count: int = Field(ge=0)
    citation_full_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    estimated_cost_usd: float = Field(ge=0.0)
    maximum_cost_usd: float = Field(ge=0.0)
    median_latency_seconds: float = Field(ge=0.0)
    maximum_median_latency_seconds: float = Field(ge=0.0)
    pilot_gate_passed: bool
    results: tuple[Phase4PaidPilotCaseResult, ...]
    limitations: tuple[str, ...]


def build_phase4_pilot_preflight(
    *,
    manifest: Phase4ExperimentManifest,
    dataset: BenchmarkDataset,
    phase3_run_path: str | Path,
    project_root: str | Path,
) -> Phase4PilotPreflight:
    """Validate matched controls and calculate hard pilot ceilings."""
    errors = list(verify_phase4_manifest(manifest, project_root).errors)
    if dataset.dataset_id != manifest.dataset_id or dataset.version != manifest.dataset_version:
        errors.append("dataset identity or version does not match the manifest")
    phase3 = load_complex_evaluation(phase3_run_path)
    if (
        phase3.dataset_id != manifest.dataset_id
        or phase3.dataset_version != manifest.dataset_version
    ):
        errors.append("Phase 3 control identity or version does not match the manifest")

    cases = {case.case_id: case for case in dataset.cases}
    controls_by_id = {result.case_id: result for result in phase3.results}
    controls: list[Phase4PilotCaseBaseline] = []
    role_activations = 0
    component_count = 0
    for case_id in manifest.pilot_case_ids:
        case = cases.get(case_id)
        control = controls_by_id.get(case_id)
        if case is None:
            errors.append(f"{case_id}: benchmark case is missing")
            continue
        if control is None:
            errors.append(f"{case_id}: Phase 3 control result is missing")
            continue
        components = len(case.expected_components) or 1
        component_count += components
        roles_per_component = 3 + int(
            case.expected_claim_type in {ClaimType.CAUSAL, ClaimType.SCIENTIFIC}
        )
        role_activations += components * roles_per_component
        controls.append(
            Phase4PilotCaseBaseline(
                case_id=case_id,
                expected_component_count=components,
                verdict_matches=control.verdict_matches,
                citation_full=(
                    control.parent_audit_count > 0
                    and control.parent_full_audit_count == control.parent_audit_count
                ),
                model_call_count=control.metered_model_call_count,
                estimated_cost_usd=control.estimated_model_cost_usd,
                duration_seconds=control.duration_seconds,
            )
        )

    control_cost = sum(item.estimated_cost_usd for item in controls)
    latencies = [item.duration_seconds for item in controls]
    control_median = statistics.median(latencies) if latencies else 0.0
    maximum_cost = control_cost * manifest.pilot_gate.maximum_mean_cost_ratio
    maximum_latency = control_median * manifest.pilot_gate.maximum_median_latency_ratio
    return Phase4PilotPreflight(
        manifest_id=manifest.manifest_id,
        valid=not errors and len(controls) == len(manifest.pilot_case_ids),
        pilot_case_ids=manifest.pilot_case_ids,
        component_count=component_count,
        controls=tuple(controls),
        phase3_control_cost_usd=round(control_cost, 9),
        maximum_phase4_cost_usd=round(maximum_cost, 9),
        phase3_median_latency_seconds=round(control_median, 6),
        maximum_phase4_median_latency_seconds=round(maximum_latency, 6),
        estimated_role_activations=role_activations,
        maximum_search_calls=role_activations * 2,
        maximum_fetched_pages=component_count * 12,
        paid_calls_authorized=False,
        errors=tuple(errors),
    )


async def run_phase4_structural_dry_run(
    *,
    manifest: Phase4ExperimentManifest,
    dataset: BenchmarkDataset,
    working_directory: str | Path,
) -> Phase4DryRunSummary:
    """Exercise pilot plumbing using reviewed passages and no paid providers."""
    cases = {case.case_id: case for case in dataset.cases}
    output = Path(working_directory)
    output.mkdir(parents=True, exist_ok=True)
    results: list[Phase4DryRunCase] = []
    for case_id in manifest.pilot_case_ids:
        case = cases[case_id]
        repository = SQLiteResearchRepository(output / f"{case_id.casefold()}.sqlite3")
        operations = SharedResearchOperations(
            repository=repository,
            search_provider=BenchmarkEvidenceSearchProvider(case),
            fetcher=_ForbiddenFetcher(),
        )
        service = MultiAgentInvestigationService(
            repository=repository,
            operations=operations,
        )
        try:
            claim = _pilot_claim(case)
            report = await service.investigate(
                claim,
                _pilot_requirements(case, claim.claim_id),
                budget=ResearchBudget(maximum_cost_usd=0),
            )
            stored = {item.evidence_id for item in report.consolidation.evidence}
            grounded = (
                set(report.verdict.decisive_evidence_ids) <= stored
                and set(report.audit.cited_evidence_ids) <= stored
            )
            results.append(
                Phase4DryRunCase(
                    case_id=case_id,
                    activated_roles=tuple(item.role.value for item in report.assignments),
                    stopping_decision=report.assessment.decision.value,
                    source_count=len(report.consolidation.sources),
                    evidence_count=len(report.consolidation.evidence),
                    independent_family_count=(
                        report.consolidation.independence.independent_family_count
                    ),
                    search_calls=sum(item.search_call_count for item in report.results),
                    fetch_calls=sum(item.fetch_call_count for item in report.results),
                    model_calls=sum(item.model_call_count for item in report.results),
                    estimated_cost_usd=sum(item.estimated_cost_usd for item in report.results),
                    citations_grounded=grounded,
                )
            )
        except Exception as exc:
            results.append(
                Phase4DryRunCase(
                    case_id=case_id,
                    activated_roles=(),
                    stopping_decision="failed",
                    source_count=0,
                    evidence_count=0,
                    independent_family_count=0,
                    search_calls=0,
                    fetch_calls=0,
                    model_calls=0,
                    estimated_cost_usd=0,
                    citations_grounded=False,
                    failure=f"{type(exc).__name__}: {exc}",
                )
            )
    completed = tuple(item for item in results if item.failure is None)
    valid = (
        len(completed) == len(manifest.pilot_case_ids)
        and all(item.citations_grounded for item in completed)
        and sum(item.fetch_calls for item in completed) == 0
        and sum(item.model_calls for item in completed) == 0
        and sum(item.estimated_cost_usd for item in completed) == 0
    )
    return Phase4DryRunSummary(
        manifest_id=manifest.manifest_id,
        provider_mode="reviewed_evidence+deterministic_reasoning",
        valid=valid,
        case_count=len(results),
        completed_count=len(completed),
        total_search_calls=sum(item.search_calls for item in results),
        total_fetch_calls=sum(item.fetch_calls for item in results),
        total_model_calls=sum(item.model_calls for item in results),
        estimated_cost_usd=sum(item.estimated_cost_usd for item in results),
        results=tuple(results),
        limitations=(
            "This dry run validates orchestration and grounding, not retrieval or verdict quality.",
            "Reviewed benchmark passages are an evidence oracle and must not enter live queries.",
            "The dry run executes each parent claim once; the paid pilot must "
            "retain component scope.",
        ),
    )


def export_phase4_pilot_artifact(artifact: DomainModel, path: str | Path) -> Path:
    """Write a typed preflight or dry-run artifact."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(artifact.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output


def _pilot_claim(case: BenchmarkCase) -> AtomicClaim:
    return AtomicClaim(
        text=case.claim,
        claim_type=case.expected_claim_type,
        reference_date=case.reference_date,
        geography=case.geography,
        retained_context=tuple(case.annotation_notes[:3]),
        checkworthiness=1.0,
    )


def _pilot_requirements(
    case: BenchmarkCase,
    component_id,
) -> tuple[ResearchRequirement, ...]:
    requirements = [
        ResearchRequirement(
            component_id=component_id,
            kind=ResearchRequirementKind.COMPONENT_COVERAGE,
            rationale="The pilot claim requires at least one relevant stored passage.",
        ),
        ResearchRequirement(
            component_id=component_id,
            kind=ResearchRequirementKind.PRIMARY_SOURCE,
            rationale="The pilot requires an official or original primary source.",
        ),
        ResearchRequirement(
            component_id=component_id,
            kind=ResearchRequirementKind.INDEPENDENT_CORROBORATION,
            minimum_independent_families=2,
            rationale="The pilot requires two genuinely independent evidence families.",
        ),
        ResearchRequirement(
            component_id=component_id,
            kind=ResearchRequirementKind.CONTRADICTION_OR_QUALIFICATION,
            rationale="The pilot requires a completed adversarial evidence path.",
        ),
    ]
    if case.expected_claim_type in {ClaimType.CAUSAL, ClaimType.SCIENTIFIC}:
        requirements.append(
            ResearchRequirement(
                component_id=component_id,
                kind=ResearchRequirementKind.ACADEMIC_EVIDENCE,
                required_source_types=(SourceType.ACADEMIC,),
                rationale="The causal or scientific pilot claim requires academic evidence.",
            )
        )
    return tuple(requirements)


class _ForbiddenFetcher:
    provider_id = "forbidden-dry-run-fetcher"

    async def fetch(self, url):
        raise RuntimeError(f"dry-run fetch is forbidden: {url}")
