"""Stage 9.1 contract-registry export and release verification."""

import hashlib
from pathlib import Path

from pydantic import Field

from claim_polygraph_ng.application.operation_contracts import (
    AUTHORITATIVE_OPERATION_CONTRACTS,
    validate_operation_contract_registry,
)
from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.operations import (
    OPERATION_INPUT_MODELS,
    OPERATION_RESULT_MODELS,
    AuthoritativeOperation,
    schema_fingerprint,
)
from claim_polygraph_ng.evaluation.phase9_baseline import (
    Phase9ArtifactHash,
    Phase9BaselineVerification,
)


class Phase9OperationSchema(DomainModel):
    operation: AuthoritativeOperation
    input_model: str
    input_schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_model: str
    result_schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Phase9ContractManifest(DomainModel):
    manifest_id: str = "phase9-stage9.1-operation-contracts-v1"
    schema_version: int = 1
    operation_count: int
    paid_operation_count: int
    external_model_calls: int = 0
    live_search_calls: int = 0
    network_fetches: int = 0
    pdf_downloads: int = 0
    schemas: tuple[Phase9OperationSchema, ...]
    release_artifacts: tuple[Phase9ArtifactHash, ...]


_RELEASE_ARTIFACTS = (
    ("operation_models", "src/claim_polygraph_ng/domain/operations.py"),
    ("operation_registry", "src/claim_polygraph_ng/application/operation_contracts.py"),
    ("contract_evaluator", "src/claim_polygraph_ng/evaluation/phase9_contracts.py"),
    ("contract_tests", "tests/unit/test_operation_contracts.py"),
    ("phase9_baseline", "artifacts/evaluations/phase9-stage9.0-baseline-v1.json"),
    ("stage9_1_report", "docs/PHASE_9_STAGE_9.1_COMPLETION_REPORT.md"),
)


def build_phase9_contract_manifest(project_root: str | Path) -> Phase9ContractManifest:
    validate_operation_contract_registry()
    root = Path(project_root).resolve()
    manifest = Phase9ContractManifest(
        operation_count=len(AUTHORITATIVE_OPERATION_CONTRACTS),
        paid_operation_count=sum(
            item.may_invoke_paid_provider for item in AUTHORITATIVE_OPERATION_CONTRACTS
        ),
        schemas=tuple(
            Phase9OperationSchema(
                operation=operation,
                input_model=OPERATION_INPUT_MODELS[operation].__name__,
                input_schema_sha256=schema_fingerprint(OPERATION_INPUT_MODELS[operation]),
                result_model=OPERATION_RESULT_MODELS[operation].__name__,
                result_schema_sha256=schema_fingerprint(OPERATION_RESULT_MODELS[operation]),
            )
            for operation in AuthoritativeOperation
        ),
        release_artifacts=tuple(
            Phase9ArtifactHash(
                artifact_id=artifact_id,
                path=path,
                sha256=_sha256(root / path),
            )
            for artifact_id, path in _RELEASE_ARTIFACTS
        ),
    )
    target = root / "artifacts/evaluations/phase9-stage9.1-operation-contracts-v1.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_phase9_contract_manifest(
    manifest: Phase9ContractManifest,
    project_root: str | Path,
) -> Phase9BaselineVerification:
    root = Path(project_root).resolve()
    errors: list[str] = []
    checked = 0
    for artifact in manifest.release_artifacts:
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
    expected_schemas = {
        operation: (
            schema_fingerprint(OPERATION_INPUT_MODELS[operation]),
            schema_fingerprint(OPERATION_RESULT_MODELS[operation]),
        )
        for operation in AuthoritativeOperation
    }
    for item in manifest.schemas:
        if expected_schemas[item.operation] != (
            item.input_schema_sha256,
            item.result_schema_sha256,
        ):
            errors.append(f"{item.operation}: schema mismatch")
    return Phase9BaselineVerification(
        valid=not errors,
        checked_artifact_count=checked,
        checked_contract_count=len(manifest.schemas),
        errors=tuple(errors),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
