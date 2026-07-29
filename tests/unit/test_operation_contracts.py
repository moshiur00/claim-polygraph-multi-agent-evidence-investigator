"""Stage 9.1 authoritative operation contract tests."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from claim_polygraph_ng.application import InvestigationService
from claim_polygraph_ng.application.operation_contracts import (
    AUTHORITATIVE_OPERATION_CONTRACTS,
    legacy_report_artifact_references,
    legacy_report_final_results,
    validate_operation_contract_registry,
)
from claim_polygraph_ng.domain.investigation import ArtifactType
from claim_polygraph_ng.domain.operations import (
    OPERATION_INPUT_MODELS,
    OPERATION_RESULT_MODELS,
    AuthoritativeOperation,
    NormalizeClaimInput,
    NormalizeClaimResult,
    OperationBudget,
    OperationRetryClass,
    canonical_operation_idempotency_key,
    validate_operation_pair,
)
from claim_polygraph_ng.persistence import SQLiteInvestigationRepository
from claim_polygraph_ng.providers import (
    DeterministicModelProvider,
    DeterministicSearchProvider,
)


def test_registry_covers_every_operation_once_and_guards_paid_retries() -> None:
    validate_operation_contract_registry()

    contracts = {item.operation: item for item in AUTHORITATIVE_OPERATION_CONTRACTS}
    assert set(contracts) == set(AuthoritativeOperation)
    assert set(OPERATION_INPUT_MODELS) == set(AuthoritativeOperation)
    assert set(OPERATION_RESULT_MODELS) == set(AuthoritativeOperation)
    assert all(
        not item.may_invoke_paid_provider
        or item.retry_class is OperationRetryClass.RECEIPT_GUARDED
        for item in contracts.values()
    )


def test_idempotency_key_is_canonical_and_input_contract_is_strict() -> None:
    investigation_id = uuid4()
    first = canonical_operation_idempotency_key(
        operation=AuthoritativeOperation.NORMALIZE_CLAIM,
        investigation_id=investigation_id,
        operation_version=1,
        payload={"claim": "A claim", "options": {"b": 2, "a": 1}},
    )
    second = canonical_operation_idempotency_key(
        operation=AuthoritativeOperation.NORMALIZE_CLAIM,
        investigation_id=investigation_id,
        operation_version=1,
        payload={"options": {"a": 1, "b": 2}, "claim": "A claim"},
    )
    assert first == second

    request = NormalizeClaimInput(
        operation_id=uuid4(),
        investigation_id=investigation_id,
        original_claim="A factual claim.",
        idempotency_key=first,
        budget=OperationBudget(maximum_model_calls=1, maximum_cost_usd=0.01),
    )
    assert request.operation is AuthoritativeOperation.NORMALIZE_CLAIM
    with pytest.raises(ValueError):
        NormalizeClaimInput.model_validate(
            {**request.model_dump(), "unexpected": "not allowed"}
        )


def test_request_result_pair_rejects_cross_operation_or_identity() -> None:
    investigation_id = uuid4()
    operation_id = uuid4()
    request = NormalizeClaimInput(
        operation_id=operation_id,
        investigation_id=investigation_id,
        original_claim="A factual claim.",
        idempotency_key="op:normalize:0123456789abcdef",
    )
    claim_ref = {
        "investigation_id": investigation_id,
        "artifact_type": "claim",
        "artifact_id": uuid4(),
    }
    result = NormalizeClaimResult(
        operation_id=operation_id,
        investigation_id=investigation_id,
        claim_ref=claim_ref,
        output_artifacts=(claim_ref,),
        completed_at=datetime.now(UTC),
    )
    validate_operation_pair(request, result)

    with pytest.raises(ValueError, match="IDs"):
        validate_operation_pair(
            request,
            result.model_copy(update={"operation_id": uuid4()}),
        )


def test_legacy_report_adapter_preserves_authoritative_artifact_identity(tmp_path) -> None:
    repository = SQLiteInvestigationRepository(tmp_path / "operations.db")
    service = InvestigationService(
        repository=repository,
        model_provider=DeterministicModelProvider(),
        search_provider=DeterministicSearchProvider(),
    )
    report = asyncio.run(service.investigate("The example programme reduced waste."))

    references = legacy_report_artifact_references(report)
    policy, final = legacy_report_final_results(
        report=report,
        apply_policy_operation_id=uuid4(),
        finalize_operation_id=uuid4(),
    )

    assert references[ArtifactType.CLAIM][0].artifact_id == report.claim.claim_id
    assert references[ArtifactType.VERDICT][0].artifact_id == report.verdict.verdict_id
    assert len(references[ArtifactType.EVIDENCE]) == len(report.evidence)
    assert policy.enforced_verdict_ref == references[ArtifactType.VERDICT][0]
    assert final.investigation_id == report.investigation.investigation_id


def test_stage9_1_schema_manifest_is_hash_valid() -> None:
    from pathlib import Path

    from claim_polygraph_ng.evaluation.phase9_contracts import (
        build_phase9_contract_manifest,
        verify_phase9_contract_manifest,
    )

    root = Path(__file__).parents[2]
    manifest = build_phase9_contract_manifest(root)
    result = verify_phase9_contract_manifest(manifest, root)

    assert manifest.operation_count == 18
    assert manifest.paid_operation_count == 5
    assert len(manifest.schemas) == 18
    assert result.valid
