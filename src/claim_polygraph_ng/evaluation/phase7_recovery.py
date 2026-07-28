"""Deterministic Stage 7.7 end-to-end recovery demonstration."""

import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import httpx
from pydantic import Field, model_validator

from claim_polygraph_ng.api import ApiDependencies, create_app
from claim_polygraph_ng.application import InvestigationService
from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.investigation import InvestigationReport
from claim_polygraph_ng.persistence import (
    SQLiteInvestigationRepository,
    SQLiteReviewLedger,
)
from claim_polygraph_ng.providers import (
    DeterministicModelProvider,
    DeterministicSearchProvider,
)


class RecoveryJourney(DomainModel):
    journey_id: str
    expected_outcome: str
    observed_outcome: str
    passed: bool
    checkpoint_reconstructed: bool = False
    audit_chain_valid: bool = True
    duplicate_operations: int = Field(default=0, ge=0)
    assertions: tuple[str, ...]


class Phase7RecoveryEvaluation(DomainModel):
    evaluation_id: str = "phase7-stage7.7-recovery-v1"
    journeys: tuple[RecoveryJourney, ...]
    passed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    all_paths_passed: bool
    model_calls: int = 0
    search_calls: int = 0
    network_calls: int = 0
    pdf_downloads: int = 0
    estimated_cost_usd: float = 0.0

    @model_validator(mode="after")
    def validate_counts(self) -> "Phase7RecoveryEvaluation":
        passed = sum(item.passed for item in self.journeys)
        if self.passed_count != passed or self.failed_count != len(self.journeys) - passed:
            raise ValueError("journey counts do not match results")
        if self.all_paths_passed != (self.failed_count == 0):
            raise ValueError("overall gate does not match journey results")
        return self


async def evaluate_phase7_recovery() -> Phase7RecoveryEvaluation:
    """Exercise every Stage 7.7 path through fresh ASGI application instances."""
    with TemporaryDirectory(prefix="claim-polygraph-stage7.7-") as temporary:
        root = Path(temporary)
        journeys = (
            await _automatic(root / "automatic"),
            await _review_path(root / "approval", "approve", "completed"),
            await _revision(root / "revision"),
            await _review_path(
                root / "more-evidence", "request_evidence", "more_evidence_required"
            ),
            await _review_path(root / "rejection", "reject", "rejected"),
            await _provider_failure(root / "provider-failure"),
            await _restart(root / "restart"),
            await _idempotent_resume(root / "idempotent"),
        )
    passed = sum(item.passed for item in journeys)
    return Phase7RecoveryEvaluation(
        journeys=journeys,
        passed_count=passed,
        failed_count=len(journeys) - passed,
        all_paths_passed=passed == len(journeys),
    )


def export_phase7_recovery(evaluation: Phase7RecoveryEvaluation, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evaluation.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    return output


async def _automatic(root: Path) -> RecoveryJourney:
    app, report, _ = await _context(root)
    started = await _call(
        app,
        "POST",
        "/api/graph-runs",
        json=_graph_body(report, review_required=False),
    )
    graph = started.json()["graph"]
    passed = (
        started.status_code == 201
        and graph["status"] == "completed"
        and graph["final_verdict"] == report.verdict.label.value
        and started.json()["review"] is None
    )
    return RecoveryJourney(
        journey_id="automatic_completion",
        expected_outcome="completed",
        observed_outcome=graph["status"],
        passed=passed,
        duplicate_operations=_duplicates(graph),
        assertions=("No review record created.", "Authoritative verdict preserved."),
    )


async def _review_path(root: Path, kind: str, expected_status: str) -> RecoveryJourney:
    app, report, _ = await _context(root)
    started = await _call(app, "POST", "/api/graph-runs", json=_graph_body(report))
    review_id = started.json()["review"]["request_id"]
    completed = await _decision(app, review_id, kind)
    payload = completed.json()
    graph = payload["graph"]
    history = payload["review"]
    passed = (
        completed.status_code == 200
        and graph["status"] == expected_status
        and len(history["decisions"]) == 1
        and history["chain_valid"]
    )
    return RecoveryJourney(
        journey_id={
            "approve": "review_approval",
            "request_evidence": "request_more_evidence",
            "reject": "review_rejection",
        }[kind],
        expected_outcome=expected_status,
        observed_outcome=graph["status"],
        passed=passed and _duplicates(graph) == 0,
        audit_chain_valid=history["chain_valid"],
        duplicate_operations=_duplicates(graph),
        assertions=("Decision attributed.", "Audit chain verified."),
    )


async def _revision(root: Path) -> RecoveryJourney:
    app, report, _ = await _context(root)
    started = await _call(app, "POST", "/api/graph-runs", json=_graph_body(report))
    review_id = started.json()["review"]["request_id"]
    decided = await _decision(app, review_id, "revise", revised_verdict="supported")
    history = decided.json()["review"]
    decision = history["decisions"][0]
    approval = {
        "request_id": review_id,
        "decision_record_id": decision["record_id"],
        "approver_identity": "Distinct Stage 7.7 Approver",
        "decision": "approve",
        "rationale": "The evidence and rationale justify this stored revision.",
    }
    approved = await _call(
        app,
        "POST",
        f"/api/reviews/{review_id}/approvals",
        json={"expected_sequence": len(history["events"]), "approval": approval},
        headers={"X-Reviewer-Identity": "Distinct Stage 7.7 Approver"},
    )
    approved_history = approved.json()
    approval_id = approved_history["approvals"][0]["approval_id"]
    revision = {
        "request_id": review_id,
        "decision_record_id": decision["record_id"],
        "approval_id": approval_id,
        "original_verdict_id": str(report.verdict.verdict_id),
        "original_verdict": report.verdict.label.value,
        "revised_verdict": "supported",
        "change_kind": "investigation_verdict",
        "rationale": "Append the approved revision without overwriting the original.",
    }
    revised = await _call(
        app,
        "POST",
        f"/api/reviews/{review_id}/revisions",
        json={
            "expected_sequence": len(approved_history["events"]),
            "revision": revision,
        },
        headers={"X-Reviewer-Identity": "Distinct Stage 7.7 Approver"},
    )
    final_history = revised.json()
    graph = decided.json()["graph"]
    passed = (
        decided.status_code == approved.status_code == revised.status_code == 200
        and graph["final_verdict"] == "supported"
        and len(final_history["revisions"]) == 1
        and final_history["revisions"][0]["original_verdict"] == report.verdict.label.value
        and final_history["chain_valid"]
    )
    return RecoveryJourney(
        journey_id="verdict_revision",
        expected_outcome="approved_revision_appended",
        observed_outcome=(
            "approved_revision_appended" if final_history.get("revisions") else "missing"
        ),
        passed=passed and _duplicates(graph) == 0,
        audit_chain_valid=final_history["chain_valid"],
        duplicate_operations=_duplicates(graph),
        assertions=("Distinct approval enforced.", "Original verdict retained."),
    )


async def _provider_failure(root: Path) -> RecoveryJourney:
    async def fail(_claim: str) -> InvestigationReport:
        raise RuntimeError("provider secret must not leak")

    app, _, _ = await _context(root, investigate=fail, create_report=False)
    response = await _call(
        app,
        "POST",
        "/api/investigations",
        json={"claim": "A deterministic provider failure fixture."},
    )
    detail = response.json()["detail"]
    health = await _call(app, "GET", "/health")
    passed = (
        response.status_code == 502
        and detail == "investigation provider failed: RuntimeError"
        and health.status_code == 200
        and health.json()["status"] == "ok"
    )
    return RecoveryJourney(
        journey_id="provider_failure",
        expected_outcome="sanitized_502",
        observed_outcome=f"{response.status_code}:{detail}",
        passed=passed,
        assertions=("Provider exception sanitized.", "API remains responsive."),
    )


async def _restart(root: Path) -> RecoveryJourney:
    app, report, dependencies = await _context(root)
    started = await _call(app, "POST", "/api/graph-runs", json=_graph_body(report))
    review_id = started.json()["review"]["request_id"]
    paused = started.json()["graph"]
    restarted = create_app(dependencies)
    reconstructed = await _call(restarted, "GET", f"/api/graph-runs/{paused['thread_id']}")
    completed = await _decision(restarted, review_id, "approve")
    graph = completed.json()["graph"]
    same_checkpoint = reconstructed.json() == paused
    passed = (
        reconstructed.status_code == completed.status_code == 200
        and same_checkpoint
        and graph["status"] == "completed"
        and _duplicates(graph) == 0
    )
    return RecoveryJourney(
        journey_id="process_restart",
        expected_outcome="checkpoint_reconstructed_and_completed",
        observed_outcome=("checkpoint_reconstructed_and_completed" if passed else graph["status"]),
        passed=passed,
        checkpoint_reconstructed=same_checkpoint,
        audit_chain_valid=completed.json()["review"]["chain_valid"],
        duplicate_operations=_duplicates(graph),
        assertions=("Fresh application instance used.", "Pre-review nodes not repeated."),
    )


async def _idempotent_resume(root: Path) -> RecoveryJourney:
    app, report, _ = await _context(root)
    started = await _call(app, "POST", "/api/graph-runs", json=_graph_body(report))
    review_id = started.json()["review"]["request_id"]
    decision_id = "c03e74ef-441d-4fd9-b2d8-658906133e5a"
    first = await _decision(app, review_id, "approve", decision_id=decision_id)
    replay = await _decision(app, review_id, "approve", decision_id=decision_id)
    graph = replay.json()["graph"]
    history = replay.json()["review"]
    passed = (
        first.status_code == replay.status_code == 200
        and first.json() == replay.json()
        and len(history["decisions"]) == 1
        and _duplicates(graph) == 0
    )
    return RecoveryJourney(
        journey_id="idempotent_resume",
        expected_outcome="identical_response_single_decision",
        observed_outcome=(
            "identical_response_single_decision" if passed else "replay_changed_state"
        ),
        passed=passed,
        audit_chain_valid=history["chain_valid"],
        duplicate_operations=_duplicates(graph),
        assertions=("Identical decision replay accepted.", "One decision record retained."),
    )


async def _context(
    root: Path,
    *,
    investigate: Callable[[str], Awaitable[InvestigationReport]] | None = None,
    create_report: bool = True,
) -> tuple[Any, InvestigationReport | None, ApiDependencies]:
    root.mkdir(parents=True, exist_ok=True)
    repository = SQLiteInvestigationRepository(root / "investigations.db")
    service = InvestigationService(
        repository=repository,
        model_provider=DeterministicModelProvider(),
        search_provider=DeterministicSearchProvider(),
    )
    runner = investigate or service.investigate
    dependencies = ApiDependencies(
        investigations=repository,
        reviews=SQLiteReviewLedger(root / "reviews.db"),
        graph_checkpoint_path=root / "graph.db",
        investigate=runner,
    )
    app = create_app(dependencies)
    report = None
    if create_report:
        response = await _call(
            app,
            "POST",
            "/api/investigations",
            json={"claim": "The example policy reduced emissions by ten percent."},
        )
        report = InvestigationReport.model_validate(response.json())
    return app, report, dependencies


def _graph_body(
    report: InvestigationReport | None, *, review_required: bool = True
) -> dict[str, Any]:
    assert report is not None
    return {
        "investigation_id": str(report.investigation.investigation_id),
        "claim_id": str(report.claim.claim_id),
        "graph": {
            "claim_text": report.claim.text,
            "approved_evidence_ids": [str(item.evidence_id) for item in report.evidence],
            "authoritative_verdict": report.verdict.label.value,
            "review_required": review_required,
            "review_reason": (
                "Stage 7.7 requires deterministic human review." if review_required else None
            ),
        },
    }


async def _decision(
    app: Any,
    review_id: str,
    kind: str,
    *,
    revised_verdict: str | None = None,
    decision_id: str | None = None,
) -> httpx.Response:
    decision: dict[str, Any] = {
        "kind": kind,
        "reviewer_identity": "Stage 7.7 Fixture Reviewer",
        "rationale": "This deterministic decision exercises the recovery path.",
    }
    if revised_verdict is not None:
        decision["revised_verdict"] = revised_verdict
    if decision_id is not None:
        decision["decision_id"] = decision_id
    return await _call(
        app,
        "POST",
        f"/api/reviews/{review_id}/decisions",
        json={"expected_sequence": 1, "decision": decision},
        headers={"X-Reviewer-Identity": "Stage 7.7 Fixture Reviewer"},
    )


async def _call(app: Any, method: str, path: str, **kwargs: Any) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://stage7.7"
    ) as client:
        return await client.request(method, path, **kwargs)


def _duplicates(graph: dict[str, Any]) -> int:
    return sum(max(0, count - 1) for count in graph["operation_counts"].values())
