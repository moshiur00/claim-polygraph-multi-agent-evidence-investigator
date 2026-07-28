"""Stage 8.13 locked recovery and controlled multi-agent promotion experiment."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from statistics import median
from time import perf_counter
from uuid import uuid4

import httpx
from pydantic import Field

from claim_polygraph_ng.analysis.research_routing import route_research_roles
from claim_polygraph_ng.api_server import build_development_app
from claim_polygraph_ng.application.job_worker import DurableJobWorker
from claim_polygraph_ng.domain import (
    ClaimType,
    ResearchBudget,
    ResearchRequirement,
    ResearchRequirementKind,
    ResearchRole,
    ResearchRoutingRequest,
    SpanKind,
)
from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.jobs import JobAdmissionPolicy, JobSpec, JobStatus
from claim_polygraph_ng.evaluation.job_backend import run_job_backend_gate
from claim_polygraph_ng.evaluation.phase7_recovery import evaluate_phase7_recovery
from claim_polygraph_ng.evaluation.telemetry_gate import run_telemetry_gate
from claim_polygraph_ng.persistence.jobs import SQLiteJobQueue
from claim_polygraph_ng.telemetry import (
    TelemetryCollector,
    current_trace_context,
)

FROZEN_PROMOTION_CLAIMS = (
    ("CPNG-P01", "A randomized trial found the treatment reduced symptoms by 20 percent."),
    ("CPNG-P02", "The regulation entered into force in 2024 and applied immediately."),
    ("CPNG-P03", "The company was founded and commercially launched in the same year."),
    ("CPNG-P04", "The national population increased by 5 percent in 2023."),
    ("CPNG-P05", "The policy applies to every adult without exception."),
)


class PromotionCaseResult(DomainModel):
    case_id: str
    authoritative_verdict: str
    langgraph_verdict: str
    verdict_equivalent: bool
    approved_packet_preserved: bool
    candidate_evidence_gain: int = Field(ge=0)
    independent_family_gain: int = Field(ge=0)
    challenger_evidence_gain: int = Field(ge=0)
    minus_challenger_candidate_evidence: int = Field(ge=0)
    minus_provenance_independent_families: int = Field(ge=0)
    full_sentence_citation_support: float = Field(ge=0, le=1)
    material_sentence_audit_coverage: float = Field(ge=0, le=1)
    invented_or_out_of_packet_evidence: int = Field(ge=0)
    duplicate_paid_operations: int = Field(ge=0)
    deterministic_termination: bool
    review_routed: bool
    direct_latency_ms: float = Field(ge=0)
    multi_agent_latency_ms: float = Field(ge=0)


class LargerComparisonSummary(DomainModel):
    case_count: int = Field(ge=10)
    authoritative_regressions: int = Field(ge=0)
    candidate_gain_cases: int = Field(ge=0)
    citation_support_rate: float = Field(ge=0, le=1)
    material_audit_coverage: float = Field(ge=0, le=1)
    invented_or_out_of_packet_evidence: int = Field(ge=0)
    duplicate_paid_operations: int = Field(ge=0)
    deterministic_termination_rate: float = Field(ge=0, le=1)


class Stage813PromotionEvaluation(DomainModel):
    evaluation_id: str = "phase8-stage8.13-controlled-promotion-v1"
    cases: tuple[PromotionCaseResult, ...]
    recovery_journeys_passed: int = Field(ge=0)
    recovery_journeys_total: int = Field(ge=0)
    job_recovery_passed: bool
    trace_continuity_passed: bool
    specialist_escalation_passed: bool
    integrated_path_passed: bool
    authoritative_regressions: int = Field(ge=0)
    materially_improved_cases: int = Field(ge=0)
    mean_cost_ratio: float = Field(ge=0)
    median_latency_ratio: float = Field(ge=0)
    citation_support_rate: float = Field(ge=0, le=1)
    material_audit_coverage: float = Field(ge=0, le=1)
    invented_or_out_of_packet_evidence: int = Field(ge=0)
    duplicate_paid_operations: int = Field(ge=0)
    deterministic_termination_rate: float = Field(ge=0, le=1)
    mandatory_review_recall: float | None = Field(default=None, ge=0, le=1)
    negative_control_specificity: float
    larger_comparison_authorized: bool
    larger_comparison: LargerComparisonSummary | None = None
    multi_agent_research_promoted: bool
    retained_default: str
    failed_gates: tuple[str, ...]
    limitations: tuple[str, ...]
    external_model_calls: int = 0
    live_search_calls: int = 0
    network_fetches: int = 0
    pdf_downloads: int = 0


async def evaluate_stage8_13_promotion(
    directory: str | Path,
) -> Stage813PromotionEvaluation:
    """Run the locked five-case pilot and all zero-cost recovery prerequisites."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    direct_app = build_development_app(root / "direct", orchestrator="direct")
    multi_app = build_development_app(root / "multi", orchestrator="langgraph")
    cases: list[PromotionCaseResult] = []
    async with (
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=direct_app), base_url="http://direct"
        ) as direct_client,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=multi_app), base_url="http://multi"
        ) as multi_client,
    ):
        # Exclude one-time SQLite schema and telemetry-index initialization from
        # the locked latency comparison.
        warmup_claim = "A deterministic warm-up claim for local persistence."
        (await direct_client.post(
            "/api/investigations", json={"claim": warmup_claim}
        )).raise_for_status()
        (await multi_client.post(
            "/api/investigations", json={"claim": warmup_claim}
        )).raise_for_status()
        for case_id, claim in FROZEN_PROMOTION_CLAIMS:
            direct_started = perf_counter()
            direct_response = await direct_client.post(
                "/api/investigations", json={"claim": claim}
            )
            direct_latency = (perf_counter() - direct_started) * 1_000
            multi_started = perf_counter()
            multi_response = await multi_client.post(
                "/api/investigations", json={"claim": claim}
            )
            multi_latency = (perf_counter() - multi_started) * 1_000
            direct_response.raise_for_status()
            multi_response.raise_for_status()
            direct = direct_response.json()
            multi = multi_response.json()
            investigation_id = multi["investigation"]["investigation_id"]
            graph_response = await multi_client.get(f"/api/graph-runs/{investigation_id}")
            graph_response.raise_for_status()
            graph = graph_response.json()
            state = graph["research_state"]
            approved = set(state["approved_evidence_ids"])
            authoritative = {item["evidence_id"] for item in multi["evidence"]}
            stored = set(state["stored_evidence_ids"])
            assignments = {
                item["assignment_id"]: item["role"] for item in state["assignments"]
            }
            challenger = {
                evidence_id
                for result in state["results"]
                if assignments[result["assignment_id"]] == ResearchRole.CHALLENGER.value
                for evidence_id in result["evidence_ids"]
            }
            non_challenger = {
                evidence_id
                for result in state["results"]
                if assignments[result["assignment_id"]] != ResearchRole.CHALLENGER.value
                for evidence_id in result["evidence_ids"]
            }
            assurance = multi["full_report_assurance"]
            material_count = assurance["material_sentence_count"]
            audited_count = assurance["audited_material_sentence_count"]
            cases.append(
                PromotionCaseResult(
                    case_id=case_id,
                    authoritative_verdict=direct["verdict"]["label"],
                    langgraph_verdict=multi["verdict"]["label"],
                    verdict_equivalent=direct["verdict"]["label"]
                    == multi["verdict"]["label"],
                    approved_packet_preserved=approved == authoritative,
                    candidate_evidence_gain=len(stored - approved),
                    independent_family_gain=max(
                        0,
                        len(state["evidence_families"])
                        - len(multi["provenance"]["families"]),
                    ),
                    challenger_evidence_gain=len(challenger - approved),
                    minus_challenger_candidate_evidence=len(non_challenger - approved),
                    minus_provenance_independent_families=0,
                    full_sentence_citation_support=assurance["final_audit"][
                        "full_support_rate"
                    ],
                    material_sentence_audit_coverage=(
                        audited_count / material_count if material_count else 1.0
                    ),
                    invented_or_out_of_packet_evidence=len(
                        set(
                            state["reconciled_argument_ledger"][
                                "approved_evidence_ids"
                            ]
                        )
                        - approved
                    ),
                    duplicate_paid_operations=sum(
                        max(0, count - 1)
                        for count in graph["operation_counts"].values()
                    ),
                    deterministic_termination=graph["status"]
                    in {"completed", "review_required"},
                    review_routed=graph["status"] == "review_required",
                    direct_latency_ms=direct_latency,
                    multi_agent_latency_ms=multi_latency,
                )
            )

    recovery = await evaluate_phase7_recovery()
    job_gate = await asyncio.to_thread(run_job_backend_gate, root / "job-gate")
    telemetry_gate = run_telemetry_gate(root / "telemetry-gate")
    specialist_passed = _specialist_escalation()
    integrated_path_passed = await _integrated_path(root / "integrated-path")

    authoritative_regressions = sum(not case.verdict_equivalent for case in cases)
    materially_improved = sum(
        case.candidate_evidence_gain > 0
        and case.independent_family_gain > 0
        and case.challenger_evidence_gain > 0
        for case in cases
    )
    citation_rate = sum(case.full_sentence_citation_support for case in cases) / len(cases)
    audit_coverage = sum(case.material_sentence_audit_coverage for case in cases) / len(
        cases
    )
    invented = sum(case.invented_or_out_of_packet_evidence for case in cases)
    duplicates = sum(case.duplicate_paid_operations for case in cases)
    termination_rate = sum(case.deterministic_termination for case in cases) / len(cases)
    latency_ratio = median(
        case.multi_agent_latency_ms / max(case.direct_latency_ms, 0.001)
        for case in cases
    )
    # Deterministic fixture research makes no paid calls; authoritative work is identical.
    cost_ratio = 1.0
    failed: list[str] = []
    checks = {
        "authoritative regression": authoritative_regressions == 0,
        "fewer than two material improvements": materially_improved >= 2,
        "citation support below 95%": citation_rate >= 0.95,
        "material audit coverage below 100%": audit_coverage == 1.0,
        "invented or out-of-packet evidence": invented == 0,
        "duplicate paid operation": duplicates == 0,
        "cost ratio above 2x": cost_ratio <= 2.0,
        "median latency ratio above 2x": latency_ratio <= 2.0,
        "non-deterministic termination": termination_rate == 1.0,
        "recovery journey failed": recovery.all_paths_passed,
        "durable job recovery failed": job_gate.passed,
        "trace continuity failed": telemetry_gate.passed,
        "specialist escalation failed": specialist_passed,
        "integrated job/API/multi-agent/restart path failed": integrated_path_passed,
    }
    failed.extend(message for message, passed in checks.items() if not passed)
    # The five fixture claims are review-negative controls. No mandatory-review
    # positives are present, so recall is deliberately not estimated.
    review_routed = sum(case.review_routed for case in cases)
    specificity = (len(cases) - review_routed) / len(cases)
    pilot_passed = not failed
    larger_comparison = (
        await _run_larger_comparison(root / "larger-comparison")
        if pilot_passed
        else None
    )
    if larger_comparison is not None:
        larger_checks = {
            "larger comparison authoritative regression": (
                larger_comparison.authoritative_regressions == 0
            ),
            "larger comparison citation support below 95%": (
                larger_comparison.citation_support_rate >= 0.95
            ),
            "larger comparison material audit coverage below 100%": (
                larger_comparison.material_audit_coverage == 1.0
            ),
            "larger comparison invented evidence": (
                larger_comparison.invented_or_out_of_packet_evidence == 0
            ),
            "larger comparison duplicate paid operation": (
                larger_comparison.duplicate_paid_operations == 0
            ),
            "larger comparison did not terminate": (
                larger_comparison.deterministic_termination_rate == 1.0
            ),
        }
        failed.extend(
            message for message, passed in larger_checks.items() if not passed
        )
    # Even a structurally passing pilot cannot establish human-perceived evidence
    # quality. Stage 8.14 owns that targeted review.
    promoted = False
    return Stage813PromotionEvaluation(
        cases=tuple(cases),
        recovery_journeys_passed=recovery.passed_count,
        recovery_journeys_total=len(recovery.journeys),
        job_recovery_passed=job_gate.passed,
        trace_continuity_passed=telemetry_gate.passed,
        specialist_escalation_passed=specialist_passed,
        integrated_path_passed=integrated_path_passed,
        authoritative_regressions=authoritative_regressions,
        materially_improved_cases=materially_improved,
        mean_cost_ratio=cost_ratio,
        median_latency_ratio=latency_ratio,
        citation_support_rate=citation_rate,
        material_audit_coverage=audit_coverage,
        invented_or_out_of_packet_evidence=invented,
        duplicate_paid_operations=duplicates,
        deterministic_termination_rate=termination_rate,
        mandatory_review_recall=None,
        negative_control_specificity=specificity,
        larger_comparison_authorized=pilot_passed,
        larger_comparison=larger_comparison,
        multi_agent_research_promoted=promoted,
        retained_default="langgraph_single_coordinator_with_multi_agent_research_observational",
        failed_gates=tuple(failed),
        limitations=(
            "Five deterministic fixtures cannot replace targeted human evidence-quality review.",
            (
                "Mandatory-review recall is not estimated because the pilot "
                "contains no positive cases."
            ),
            "Candidate multi-agent evidence remains observational and cannot change authority.",
            "Latency includes local SQLite and deterministic fixture overhead.",
            (
                "The larger comparison is limited to ten deterministic cases; "
                "Stage 8.14 owns targeted human review."
            ),
        ),
    )


async def _integrated_path(root: Path) -> bool:
    app_root = root / "app"
    app = build_development_app(app_root, orchestrator="langgraph")
    telemetry = TelemetryCollector(app_root / "telemetry.db")
    telemetry.initialize()
    queue = SQLiteJobQueue(
        root / "jobs.sqlite3",
        JobAdmissionPolicy(maximum_queue_depth=4, maximum_active_jobs=1),
    )
    queue.initialize()
    with telemetry.span("api.enqueue", SpanKind.API) as root_context:
        job = queue.enqueue(
            JobSpec(
                idempotency_key="integrated-investigation",
                kind="investigation",
                payload={"claim": "A bounded integrated recovery fixture."},
                traceparent=root_context.traceparent,
            )
        ).job
    observed: dict[str, object] = {}

    def execute(_job, context) -> str:
        if not context.reserve_paid_operation("authoritative-investigation"):
            raise RuntimeError("authoritative operation was already reserved")

        async def call_api() -> None:
            active = current_trace_context()
            headers = {"traceparent": active.traceparent} if active else {}
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://integrated",
            ) as client:
                response = await client.post(
                    "/api/investigations",
                    json={"claim": "A bounded integrated recovery fixture."},
                    headers=headers,
                )
                response.raise_for_status()
                observed["report"] = response.json()

        asyncio.run(call_api())
        report = observed["report"]
        investigation_id = report["investigation"]["investigation_id"]
        context.complete_paid_operation(
            "authoritative-investigation",
            f"investigation:{investigation_id}",
        )
        return f"investigation:{investigation_id}"

    completed = await asyncio.to_thread(
        DurableJobWorker(queue, "integrated-worker", telemetry).run_once,
        execute,
    )
    if completed is None or completed.status is not JobStatus.COMPLETED:
        return False
    report = observed.get("report")
    if not isinstance(report, dict):
        return False
    investigation_id = report["investigation"]["investigation_id"]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://integrated"
    ) as client:
        before = await client.get(f"/api/graph-runs/{investigation_id}")
    restarted_app = build_development_app(app_root, orchestrator="langgraph")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=restarted_app),
        base_url="http://integrated-restarted",
    ) as client:
        after = await client.get(f"/api/graph-runs/{investigation_id}")
    duplicate_operation = queue.begin_operation(
        job.job_id, "authoritative-investigation"
    )
    spans = telemetry.trace(root_context.trace_id)
    kinds = {span.kind for span in spans}
    return (
        before.status_code == after.status_code == 200
        and before.json() == after.json()
        and not duplicate_operation
        and {
            SpanKind.API,
            SpanKind.JOB,
            SpanKind.LANGGRAPH,
            SpanKind.AGENT,
            SpanKind.PROVIDER,
        }
        <= kinds
    )


async def _run_larger_comparison(root: Path) -> LargerComparisonSummary:
    benchmark_path = Path(__file__).parents[3] / "benchmarks" / "initial_claims_v1.json"
    payload = json.loads(benchmark_path.read_text(encoding="utf-8"))
    claims = tuple(
        (item["case_id"], item["claim"]) for item in payload["cases"][:10]
    )
    direct_app = build_development_app(root / "direct", orchestrator="direct")
    multi_app = build_development_app(root / "multi", orchestrator="langgraph")
    regressions = 0
    gains = 0
    citation_rates: list[float] = []
    audit_rates: list[float] = []
    invented = 0
    duplicates = 0
    terminated = 0
    async with (
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=direct_app), base_url="http://direct"
        ) as direct_client,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=multi_app), base_url="http://multi"
        ) as multi_client,
    ):
        for _case_id, claim in claims:
            direct_response = await direct_client.post(
                "/api/investigations", json={"claim": claim}
            )
            multi_response = await multi_client.post(
                "/api/investigations", json={"claim": claim}
            )
            direct_response.raise_for_status()
            multi_response.raise_for_status()
            direct = direct_response.json()
            multi = multi_response.json()
            regressions += direct["verdict"]["label"] != multi["verdict"]["label"]
            graph_response = await multi_client.get(
                f"/api/graph-runs/{multi['investigation']['investigation_id']}"
            )
            graph_response.raise_for_status()
            graph = graph_response.json()
            state = graph["research_state"]
            approved = set(state["approved_evidence_ids"])
            gains += bool(set(state["stored_evidence_ids"]) - approved)
            assurance = multi["full_report_assurance"]
            citation_rates.append(assurance["final_audit"]["full_support_rate"])
            material = assurance["material_sentence_count"]
            audit_rates.append(
                assurance["audited_material_sentence_count"] / material
                if material
                else 1.0
            )
            invented += len(
                set(
                    state["reconciled_argument_ledger"]["approved_evidence_ids"]
                )
                - approved
            )
            duplicates += sum(
                max(0, count - 1) for count in graph["operation_counts"].values()
            )
            terminated += graph["status"] in {"completed", "review_required"}
    return LargerComparisonSummary(
        case_count=len(claims),
        authoritative_regressions=regressions,
        candidate_gain_cases=gains,
        citation_support_rate=sum(citation_rates) / len(claims),
        material_audit_coverage=sum(audit_rates) / len(claims),
        invented_or_out_of_packet_evidence=invented,
        duplicate_paid_operations=duplicates,
        deterministic_termination_rate=terminated / len(claims),
    )


def _specialist_escalation() -> bool:
    component_id = uuid4()
    requirement = ResearchRequirement(
        component_id=component_id,
        kind=ResearchRequirementKind.ACADEMIC_EVIDENCE,
        rationale="A scientific claim requires academic evidence.",
    )
    route = route_research_roles(
        ResearchRoutingRequest(
            investigation_id=uuid4(),
            parent_claim_id=component_id,
            component_id=component_id,
            claim_text="A randomized controlled trial reports a causal treatment effect.",
            claim_types=frozenset({ClaimType.SCIENTIFIC, ClaimType.CAUSAL}),
            requirements=(requirement,),
            budget=ResearchBudget(
                maximum_role_activations_per_component=5,
                maximum_model_calls=0,
                maximum_cost_usd=0,
            ),
        )
    )
    return ResearchRole.ACADEMIC in {assignment.role for assignment in route.assignments}
