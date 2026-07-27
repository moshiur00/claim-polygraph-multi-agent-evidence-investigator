"""Run the explicitly authorized, cost-capped three-claim Phase 4 pilot."""

import argparse
import asyncio
import statistics
from pathlib import Path
from time import perf_counter

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from claim_polygraph_ng.analysis import aggregate_component_label, verify_claim_context
from claim_polygraph_ng.application import (
    MultiAgentInvestigationService,
    SharedResearchOperations,
    StructuredResearchWorker,
)
from claim_polygraph_ng.domain import (
    AtomicClaim,
    InvestigationPlan,
    ModelTask,
    ResearchBudget,
    ResearchPath,
    ResearchRequirement,
    ResearchRequirementKind,
    SentenceAudit,
    SourceType,
    SupportLevel,
    Verdict,
)
from claim_polygraph_ng.evaluation import (
    BenchmarkEvidenceSearchProvider,
    Phase4PaidComponentResult,
    Phase4PaidPilotCaseResult,
    Phase4PaidPilotSummary,
    build_phase4_pilot_preflight,
    export_phase4_pilot_artifact,
    load_benchmark,
    load_phase4_manifest,
)
from claim_polygraph_ng.persistence import SQLiteResearchRepository
from claim_polygraph_ng.providers import OpenAIStructuredModelProvider

ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "artifacts/evaluations/phase4-paid-pilot.json"


class _Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    openai_api_key: SecretStr
    openai_model: str = "gpt-5.4-mini"
    openai_fast_model: str = "gpt-4o-mini"
    openai_timeout_seconds: float = 60.0


class _ForbiddenFetcher:
    provider_id = "forbidden-pilot-fetcher"

    async def fetch(self, url):
        raise RuntimeError(f"paid benchmark-evidence pilot may not fetch pages: {url}")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorize-paid", action="store_true")
    args = parser.parse_args()
    if not args.authorize_paid:
        raise SystemExit("Paid pilot requires --authorize-paid")

    manifest = load_phase4_manifest(
        ROOT / "artifacts/evaluations/phase4-experiment-manifest-v1.json"
    )
    dataset = load_benchmark(ROOT / "benchmarks/initial_claims_v1.json")
    preflight = build_phase4_pilot_preflight(
        manifest=manifest,
        dataset=dataset,
        phase3_run_path=ROOT / "artifacts/evaluations/phase3-v5-final-run-a.json",
        project_root=ROOT,
    )
    if not preflight.valid:
        raise SystemExit("Phase 4 pilot preflight is invalid")

    settings = _Settings()
    (ROOT / "data/phase4-paid-pilot").mkdir(parents=True, exist_ok=True)
    model = OpenAIStructuredModelProvider(
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.openai_model,
        fast_model=settings.openai_fast_model,
        timeout_seconds=settings.openai_timeout_seconds,
    )
    cases = {case.case_id: case for case in dataset.cases}
    controls = {item.case_id: item for item in preflight.controls}
    results: list[Phase4PaidPilotCaseResult] = []
    total_cost = 0.0

    for case_id in manifest.pilot_case_ids:
        case = cases[case_id]
        started = perf_counter()
        component_results: list[Phase4PaidComponentResult] = []
        component_verdicts: list[Verdict] = []
        try:
            for number, component_text in enumerate(case.expected_components, start=1):
                component_started = perf_counter()
                claim = AtomicClaim(
                    parent_claim_id=None,
                    text=component_text,
                    claim_type=case.expected_claim_type,
                    reference_date=case.reference_date,
                    geography=case.geography,
                    retained_context=(f"Submitted parent claim: {case.claim}",),
                    checkworthiness=1.0,
                )
                repository = SQLiteResearchRepository(
                    ROOT / f"data/phase4-paid-pilot/{case_id.casefold()}-{number}.sqlite3"
                )
                operations = SharedResearchOperations(
                    repository=repository,
                    search_provider=BenchmarkEvidenceSearchProvider.for_component(
                        case, component_text
                    ),
                    fetcher=_ForbiddenFetcher(),
                )
                worker = StructuredResearchWorker(repository, model)
                service = MultiAgentInvestigationService(
                    repository=repository,
                    operations=operations,
                    worker=worker,
                )
                report = await service.investigate(
                    claim,
                    _requirements(claim, case.expected_claim_type.value),
                    budget=ResearchBudget(
                        maximum_cost_usd=preflight.maximum_phase4_cost_usd,
                    ),
                )
                classification_cost = sum(item.estimated_cost_usd for item in report.results)
                plan = InvestigationPlan(
                    claim_id=claim.claim_id,
                    required_research_paths=(
                        ResearchPath.PRIMARY,
                        ResearchPath.GENERAL,
                        ResearchPath.CONTRADICTION,
                    ),
                    minimum_independent_families=2,
                    maximum_search_calls=6,
                    maximum_pages_fetched=12,
                )
                context = verify_claim_context(
                    claim=claim,
                    plan=plan,
                    sources=report.consolidation.sources,
                    evidence=report.consolidation.evidence,
                )
                verdict = await model.generate(
                    task=ModelTask.JUDGE_EVIDENCE,
                    response_model=Verdict,
                    inputs={
                        "claim_id": str(claim.claim_id),
                        "claim": claim.model_dump(mode="json"),
                        "sources": [
                            item.model_dump(mode="json") for item in report.consolidation.sources
                        ],
                        "evidence": [
                            item.model_dump(mode="json") for item in report.consolidation.evidence
                        ],
                        "independence_analysis": (
                            report.consolidation.independence.model_dump(mode="json")
                        ),
                        "context_verification": context.model_dump(mode="json"),
                        "taxonomy_guidance": (
                            "Universal and absolute wording is material; distinguish "
                            "misleading qualified truth from direct contradiction.",
                        ),
                    },
                )
                judge_usage = model.take_last_usage()
                audit = await model.generate(
                    task=ModelTask.AUDIT_SENTENCE,
                    response_model=SentenceAudit,
                    inputs={
                        "original_claim": claim.model_dump(mode="json"),
                        "verdict_label": verdict.label.value,
                        "sentence": verdict.concise_explanation,
                        "evidence_ids": [
                            str(item.evidence_id) for item in report.consolidation.evidence
                        ],
                        "evidence": [
                            item.model_dump(mode="json") for item in report.consolidation.evidence
                        ],
                    },
                )
                audit_usage = model.take_last_usage()
                extra_cost = sum(
                    usage.estimated_cost_usd or 0.0
                    for usage in (judge_usage, audit_usage)
                    if usage is not None
                )
                component_cost = classification_cost + extra_cost
                total_cost += component_cost
                if total_cost > preflight.maximum_phase4_cost_usd:
                    raise RuntimeError("paid pilot exceeded its predeclared cost ceiling")
                component_verdicts.append(verdict)
                component_results.append(
                    Phase4PaidComponentResult(
                        component_number=number,
                        component_text=component_text,
                        verdict_label=verdict.label,
                        citation_support=audit.support_level,
                        source_count=len(report.consolidation.sources),
                        evidence_count=len(report.consolidation.evidence),
                        independent_family_count=(
                            report.consolidation.independence.independent_family_count
                        ),
                        model_call_count=sum(item.model_call_count for item in report.results) + 2,
                        estimated_cost_usd=round(component_cost, 9),
                        duration_seconds=round(perf_counter() - component_started, 6),
                    )
                )
            parent_label = aggregate_component_label(component_verdicts)
            expected = case.expected_verdict
            assert expected is not None
            results.append(
                Phase4PaidPilotCaseResult(
                    case_id=case_id,
                    completed=True,
                    expected_verdict=expected,
                    verdict_label=parent_label,
                    verdict_matches=parent_label is expected,
                    phase3_verdict_matches=controls[case_id].verdict_matches,
                    component_results=tuple(component_results),
                    citation_full=all(
                        item.citation_support is SupportLevel.FULL for item in component_results
                    ),
                    model_call_count=sum(item.model_call_count for item in component_results),
                    estimated_cost_usd=round(
                        sum(item.estimated_cost_usd for item in component_results), 9
                    ),
                    duration_seconds=round(perf_counter() - started, 6),
                )
            )
        except Exception as exc:
            expected = case.expected_verdict
            assert expected is not None
            results.append(
                Phase4PaidPilotCaseResult(
                    case_id=case_id,
                    completed=False,
                    expected_verdict=expected,
                    phase3_verdict_matches=controls[case_id].verdict_matches,
                    component_results=tuple(component_results),
                    model_call_count=sum(item.model_call_count for item in component_results),
                    estimated_cost_usd=round(
                        sum(item.estimated_cost_usd for item in component_results), 9
                    ),
                    duration_seconds=round(perf_counter() - started, 6),
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            break

    completed = tuple(item for item in results if item.completed)
    scored = tuple(item for item in completed if item.verdict_matches is not None)
    control_scored = tuple(item for item in results if item.phase3_verdict_matches is not None)
    improved = sum(
        item.verdict_matches is True and item.phase3_verdict_matches is False for item in completed
    )
    regressed = sum(
        item.verdict_matches is False and item.phase3_verdict_matches is True for item in completed
    )
    citation_rate = (
        sum(item.citation_full for item in completed) / len(completed) if completed else None
    )
    latency = statistics.median(item.duration_seconds for item in completed) if completed else 0
    accuracy = (
        sum(item.verdict_matches is True for item in scored) / len(scored) if scored else None
    )
    control_accuracy = (
        sum(item.phase3_verdict_matches is True for item in control_scored) / len(control_scored)
        if control_scored
        else None
    )
    gate_passed = (
        len(completed) == len(manifest.pilot_case_ids)
        and improved >= manifest.pilot_gate.minimum_improved_cases
        and regressed <= manifest.pilot_gate.verdict_regressions_allowed
        and citation_rate is not None
        and citation_rate >= 0.95
        and total_cost <= preflight.maximum_phase4_cost_usd
        and latency <= preflight.maximum_phase4_median_latency_seconds
    )
    summary = Phase4PaidPilotSummary(
        manifest_id=manifest.manifest_id,
        provider_mode=f"benchmark_evidence+{model.provider_id}",
        case_count=len(manifest.pilot_case_ids),
        completed_count=len(completed),
        verdict_accuracy=accuracy,
        phase3_control_accuracy=control_accuracy,
        improved_case_count=improved,
        regressed_case_count=regressed,
        citation_full_rate=citation_rate,
        estimated_cost_usd=round(total_cost, 9),
        maximum_cost_usd=preflight.maximum_phase4_cost_usd,
        median_latency_seconds=round(latency, 6),
        maximum_median_latency_seconds=preflight.maximum_phase4_median_latency_seconds,
        pilot_gate_passed=gate_passed,
        results=tuple(results),
        limitations=(
            "Reviewed evidence mode isolates orchestration and judgment; it does not "
            "measure live retrieval.",
            "At least two case-level quality improvements are required for automatic "
            "promotion to the ten-claim evaluation.",
            "No PDF or live page fetch is permitted in this run.",
        ),
    )
    export_phase4_pilot_artifact(summary, OUTPUT)
    print(f"Completed: {summary.completed_count}/{summary.case_count}")
    print(f"Accuracy: {summary.verdict_accuracy}")
    print(f"Control accuracy: {summary.phase3_control_accuracy}")
    print(f"Improved/regressed: {summary.improved_case_count}/{summary.regressed_case_count}")
    print(f"Cost: ${summary.estimated_cost_usd:.6f} / ${summary.maximum_cost_usd:.6f}")
    print(f"Pilot gate passed: {summary.pilot_gate_passed}")
    print(f"Artifact: {OUTPUT}")
    return 0 if summary.pilot_gate_passed else 2


def _requirements(claim: AtomicClaim, claim_type: str) -> tuple[ResearchRequirement, ...]:
    requirements = [
        ResearchRequirement(
            component_id=claim.claim_id,
            kind=ResearchRequirementKind.COMPONENT_COVERAGE,
            rationale="The component requires relevant evidence.",
        ),
        ResearchRequirement(
            component_id=claim.claim_id,
            kind=ResearchRequirementKind.PRIMARY_SOURCE,
            rationale="The component requires a suitable primary source.",
        ),
        ResearchRequirement(
            component_id=claim.claim_id,
            kind=ResearchRequirementKind.INDEPENDENT_CORROBORATION,
            minimum_independent_families=2,
            rationale="The component requires independent corroboration.",
        ),
        ResearchRequirement(
            component_id=claim.claim_id,
            kind=ResearchRequirementKind.CONTRADICTION_OR_QUALIFICATION,
            rationale="The component requires adversarial research.",
        ),
    ]
    if claim_type in {"causal", "scientific"}:
        requirements.append(
            ResearchRequirement(
                component_id=claim.claim_id,
                kind=ResearchRequirementKind.ACADEMIC_EVIDENCE,
                required_source_types=(SourceType.ACADEMIC,),
                rationale="The causal or scientific component requires academic evidence.",
            )
        )
    return tuple(requirements)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
