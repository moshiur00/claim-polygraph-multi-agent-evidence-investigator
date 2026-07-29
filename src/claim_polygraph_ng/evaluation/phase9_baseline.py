"""Stage 9.0 reproducible baseline and migration-contract inventory."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.investigation import Investigation, InvestigationReport
from claim_polygraph_ng.domain.models import Evidence


class Phase9ArtifactHash(DomainModel):
    artifact_id: str = Field(pattern=r"^[a-z0-9_]+$")
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Phase9CaseBaseline(DomainModel):
    case_id: str = Field(pattern=r"^CPNG-[0-9]{3}$")
    expected_verdict: str
    annotation_status: str
    evidence_count: int = Field(ge=0)
    evidence_family_count: int = Field(ge=0)
    search_calls: int = Field(ge=0)
    model_calls: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    latency_seconds: float = Field(ge=0)
    review_required: bool
    citation_support_rate: float | None = Field(default=None, ge=0, le=1)


class Phase9Responsibility(DomainModel):
    operation: str
    current_owner: str
    artifacts: tuple[str, ...] = ()
    database_writes: tuple[str, ...] = ()
    paid_operation: bool = False


class Phase9CompatibilityContract(DomainModel):
    contract_id: str
    surface: str
    fields: tuple[str, ...]
    compatibility_rule: str
    schema_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class Phase9ResourcePolicy(DomainModel):
    model_calls: int = 0
    search_calls: int = 0
    network_calls: int = 0
    pdf_downloads: int = 0


class Phase9BaselineManifest(DomainModel):
    manifest_id: str = "phase9-stage9.0-baseline-v1"
    schema_version: int = 1
    dataset_id: str
    dataset_version: int
    case_count: int
    generated_from_existing_artifacts_only: bool = True
    default_orchestrator: str = "langgraph"
    authoritative_domain_service: str = "InvestigationService"
    rollback_path: str = "direct"
    resource_policy: Phase9ResourcePolicy = Phase9ResourcePolicy()
    cases: tuple[Phase9CaseBaseline, ...]
    responsibilities: tuple[Phase9Responsibility, ...]
    compatibility_contracts: tuple[Phase9CompatibilityContract, ...]
    artifacts: tuple[Phase9ArtifactHash, ...]

    @model_validator(mode="after")
    def validate_uniqueness_and_case_count(self) -> Phase9BaselineManifest:
        if self.case_count != len(self.cases):
            raise ValueError("case_count must equal the number of frozen cases")
        for values, label in (
            ((item.case_id for item in self.cases), "case IDs"),
            ((item.operation for item in self.responsibilities), "operations"),
            ((item.contract_id for item in self.compatibility_contracts), "contracts"),
            ((item.artifact_id for item in self.artifacts), "artifact IDs"),
            ((item.path for item in self.artifacts), "artifact paths"),
        ):
            materialized = tuple(values)
            if len(materialized) != len(set(materialized)):
                raise ValueError(f"{label} must be unique")
        return self


class Phase9BaselineVerification(DomainModel):
    valid: bool
    checked_artifact_count: int
    checked_contract_count: int
    errors: tuple[str, ...]


_ARTIFACTS = (
    ("benchmark", "benchmarks/initial_claims_v1.json"),
    ("review_001_005", "benchmarks/review_packets/cpng_001_005.md"),
    ("review_006_010", "benchmarks/review_packets/cpng_006_010.md"),
    ("review_011_020", "benchmarks/review_packets/cpng_011_020.md"),
    ("phase8_closure", "artifacts/evaluations/phase8-stage8.14-closure-audit-v1.json"),
    ("phase8_promotion", "artifacts/evaluations/phase8-stage8.13-controlled-promotion-v1.json"),
    ("phase8_release", "artifacts/evaluations/phase8-final-release-manifest-v1.json"),
    ("investigation_service", "src/claim_polygraph_ng/application/investigation_service.py"),
    ("orchestrator", "src/claim_polygraph_ng/application/orchestrator.py"),
    ("api", "src/claim_polygraph_ng/api.py"),
    ("report_renderer", "src/claim_polygraph_ng/reporting/reports.py"),
    ("dashboard_page", "dashboard/app/page.tsx"),
    ("phase9_plan", "docs/PHASE_9_UNIFIED_AUTHORITATIVE_LANGGRAPH_PLAN.md"),
    ("responsibility_map", "docs/PHASE_9_CURRENT_WORKFLOW_RESPONSIBILITY_MAP.md"),
    ("compatibility_inventory", "docs/PHASE_9_COMPATIBILITY_CONTRACT_INVENTORY.md"),
)


_RESPONSIBILITIES = (
    Phase9Responsibility(
        operation="create_investigation",
        current_owner="InvestigationService.investigate",
        database_writes=("investigations", "trace_events"),
    ),
    Phase9Responsibility(
        operation="normalize_claim",
        current_owner="InvestigationService.investigate/_generate",
        artifacts=("claim",),
        database_writes=("artifacts", "trace_events"),
        paid_operation=True,
    ),
    Phase9Responsibility(
        operation="plan_investigation",
        current_owner="InvestigationService.investigate/_generate",
        artifacts=("plan",),
        database_writes=("artifacts", "trace_events"),
        paid_operation=True,
    ),
    Phase9Responsibility(
        operation="execute_research",
        current_owner="InvestigationService._research/_search/_result_content",
        artifacts=("source", "chunk", "evidence", "independence"),
        database_writes=("artifacts", "trace_events"),
        paid_operation=True,
    ),
    Phase9Responsibility(
        operation="analyze_provenance",
        current_owner="build_investigation_provenance",
        artifacts=("provenance",),
        database_writes=("artifacts", "trace_events"),
    ),
    Phase9Responsibility(
        operation="verify_context",
        current_owner="verify_claim_context/bridge_legacy_verification",
        artifacts=("context_verification", "verification_packet"),
        database_writes=("artifacts", "trace_events"),
    ),
    Phase9Responsibility(
        operation="build_argument_ledger",
        current_owner="build_argument_ledger",
        artifacts=("argument_ledger",),
        database_writes=("artifacts", "trace_events"),
    ),
    Phase9Responsibility(
        operation="draft_and_constrain_verdict",
        current_owner="InvestigationService.investigate safeguards/judgment policy",
        artifacts=("judgment_policy", "verdict"),
        database_writes=("artifacts", "trace_events"),
        paid_operation=True,
    ),
    Phase9Responsibility(
        operation="audit_citations",
        current_owner="InvestigationService.investigate/assure_full_report",
        artifacts=("audit", "full_report_assurance"),
        database_writes=("artifacts", "trace_events"),
        paid_operation=True,
    ),
    Phase9Responsibility(
        operation="assess_readiness",
        current_owner="calculate_judgment_readiness",
        artifacts=("readiness",),
        database_writes=("artifacts", "trace_events"),
    ),
    Phase9Responsibility(
        operation="finalize_or_fail",
        current_owner="InvestigationService.investigate",
        database_writes=("investigations", "trace_events"),
    ),
)


def build_phase9_baseline(project_root: str | Path) -> Phase9BaselineManifest:
    root = Path(project_root).resolve()
    dataset = json.loads((root / "benchmarks/initial_claims_v1.json").read_text("utf-8"))
    contracts = _compatibility_contracts()
    manifest = Phase9BaselineManifest(
        dataset_id=dataset["dataset_id"],
        dataset_version=dataset["version"],
        case_count=len(dataset["cases"]),
        cases=tuple(_case_baseline(case) for case in dataset["cases"]),
        responsibilities=_RESPONSIBILITIES,
        compatibility_contracts=contracts,
        artifacts=tuple(
            Phase9ArtifactHash(
                artifact_id=artifact_id,
                path=path,
                sha256=_sha256(root / path),
            )
            for artifact_id, path in _ARTIFACTS
        ),
    )
    target = root / "artifacts/evaluations/phase9-stage9.0-baseline-v1.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return manifest


def load_phase9_baseline(path: str | Path) -> Phase9BaselineManifest:
    return Phase9BaselineManifest.model_validate_json(Path(path).read_text(encoding="utf-8"))


def verify_phase9_baseline(
    manifest: Phase9BaselineManifest, project_root: str | Path
) -> Phase9BaselineVerification:
    root = Path(project_root).resolve()
    errors: list[str] = []
    checked = 0
    for artifact in manifest.artifacts:
        candidate = (root / artifact.path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            errors.append(f"{artifact.artifact_id}: path escapes project root")
            continue
        if not candidate.is_file():
            errors.append(f"{artifact.artifact_id}: file missing")
            continue
        checked += 1
        if _sha256(candidate) != artifact.sha256:
            errors.append(f"{artifact.artifact_id}: SHA-256 mismatch")

    expected_contracts = {item.contract_id: item for item in _compatibility_contracts()}
    for contract in manifest.compatibility_contracts:
        expected = expected_contracts.get(contract.contract_id)
        if expected is None or expected.schema_sha256 != contract.schema_sha256:
            errors.append(f"{contract.contract_id}: compatibility schema mismatch")
    return Phase9BaselineVerification(
        valid=not errors,
        checked_artifact_count=checked,
        checked_contract_count=len(manifest.compatibility_contracts),
        errors=tuple(errors),
    )


def _case_baseline(case: dict[str, Any]) -> Phase9CaseBaseline:
    evidence = case.get("candidate_evidence") or []
    families = {
        (
            item.get("publisher")
            or urlsplit(str(item.get("url") or "")).hostname
            or item.get("source_id")
            or item.get("evidence_id")
        )
        for item in evidence
    }
    families.discard(None)
    usage = (case.get("ai_review") or {}).get("usage") or []
    return Phase9CaseBaseline(
        case_id=case["case_id"],
        expected_verdict=case["expected_verdict"],
        annotation_status=case["annotation_status"],
        evidence_count=len(evidence),
        evidence_family_count=len(families),
        search_calls=0,
        model_calls=len(usage),
        input_tokens=sum(item.get("input_tokens") or 0 for item in usage),
        output_tokens=sum(item.get("output_tokens") or 0 for item in usage),
        estimated_cost_usd=sum(item.get("estimated_cost_usd") or 0 for item in usage),
        latency_seconds=sum(item.get("duration_seconds") or 0 for item in usage),
        review_required=bool((case.get("ai_review") or {}).get("requires_human_review")),
        citation_support_rate=None,
    )


def _compatibility_contracts() -> tuple[Phase9CompatibilityContract, ...]:
    report_fields = tuple(InvestigationReport.model_fields)
    investigation_fields = tuple(Investigation.model_fields)
    evidence_fields = tuple(Evidence.model_fields)
    return (
        Phase9CompatibilityContract(
            contract_id="investigation_report_v1",
            surface="POST /api/investigations and GET /api/investigations/{id}/report",
            fields=report_fields,
            compatibility_rule=(
                "Existing fields remain readable and keep their meaning; additions are optional."
            ),
            schema_sha256=_schema_hash(InvestigationReport.model_json_schema()),
        ),
        Phase9CompatibilityContract(
            contract_id="investigation_status_v1",
            surface="investigation list/detail and investigation SSE",
            fields=investigation_fields,
            compatibility_rule=(
                "Persisted status/stage values and terminal-state semantics remain readable."
            ),
            schema_sha256=_schema_hash(Investigation.model_json_schema()),
        ),
        Phase9CompatibilityContract(
            contract_id="evidence_v1",
            surface="GET /api/investigations/{id}/evidence",
            fields=evidence_fields,
            compatibility_rule=(
                "Evidence IDs, source/chunk links, stance and passage offsets remain stable."
            ),
            schema_sha256=_schema_hash(Evidence.model_json_schema()),
        ),
        Phase9CompatibilityContract(
            contract_id="report_markdown_v1",
            surface="GET /api/investigations/{id}/report?format=markdown",
            fields=("title", "development_notice", "verdict", "evidence", "citations", "audit"),
            compatibility_rule=(
                "Publication blocking and citation-grounded sections must not weaken."
            ),
        ),
        Phase9CompatibilityContract(
            contract_id="durable_job_sse_v1",
            surface="POST/GET /api/investigation-jobs and /events",
            fields=("job", "investigation_id", "events", "job_event", "job_state"),
            compatibility_rule=(
                "Existing clients can reconnect by sequence without resubmitting work."
            ),
        ),
        Phase9CompatibilityContract(
            contract_id="review_graph_v1",
            surface="/api/graph-runs and /api/reviews",
            fields=("graph", "review", "decision", "approval", "revision"),
            compatibility_rule=(
                "Old graph/review records remain readable and review history stays append-only."
            ),
        ),
    )


def _schema_hash(schema: dict[str, Any]) -> str:
    encoded = json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
