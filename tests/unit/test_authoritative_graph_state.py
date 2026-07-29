"""Stage 9.3 authoritative graph state, migration and checkpoint tests."""

from uuid import uuid4

import pytest

from claim_polygraph_ng.application.authoritative_graph_state import (
    migrate_authoritative_graph_state,
    reconstruct_authoritative_graph_state,
    validate_monotonic_graph_transition,
)
from claim_polygraph_ng.domain.authoritative_graph import (
    AuthoritativeGraphPhase,
    AuthoritativeInvestigationGraphState,
)
from claim_polygraph_ng.domain.graph import (
    DurableComponentReference,
    DurableMultiAgentGraphState,
)
from claim_polygraph_ng.domain.investigation import ArtifactType
from claim_polygraph_ng.domain.operations import ArtifactReference, AuthoritativeOperation
from claim_polygraph_ng.persistence.authoritative_graph import (
    AuthoritativeCheckpointConflictError,
    SQLiteAuthoritativeGraphCheckpointRepository,
)


def _state() -> AuthoritativeInvestigationGraphState:
    investigation_id = uuid4()
    claim_id = uuid4()
    claim_ref = ArtifactReference(
        investigation_id=investigation_id,
        artifact_type=ArtifactType.CLAIM,
        artifact_id=claim_id,
    )
    return AuthoritativeInvestigationGraphState(
        thread_id=str(investigation_id),
        investigation_id=investigation_id,
        parent_claim_id=claim_id,
        phase=AuthoritativeGraphPhase.CLAIM_ANALYSIS,
        completed_operations=(AuthoritativeOperation.CREATE_INVESTIGATION,),
        operation_versions={AuthoritativeOperation.CREATE_INVESTIGATION: 1},
        artifacts=(claim_ref,),
        components=(
            DurableComponentReference(
                component_id=claim_id,
                parent_claim_id=claim_id,
                claim_summary="A durable factual claim.",
            ),
        ),
    )


def test_monotonic_transition_accepts_progress_and_rejects_erasure() -> None:
    previous = _state()
    current = previous.model_copy(
        update={
            "checkpoint_sequence": 1,
            "phase": AuthoritativeGraphPhase.PLANNING,
            "completed_operations": (
                *previous.completed_operations,
                AuthoritativeOperation.NORMALIZE_CLAIM,
            ),
            "operation_versions": {
                **previous.operation_versions,
                AuthoritativeOperation.NORMALIZE_CLAIM: 1,
            },
        }
    )
    validate_monotonic_graph_transition(previous, current)

    erased = current.model_copy(
        update={
            "checkpoint_sequence": 2,
            "completed_operations": (),
        }
    )
    with pytest.raises(ValueError, match="cannot disappear"):
        validate_monotonic_graph_transition(current, erased)

    decreased = current.model_copy(
        update={
            "checkpoint_sequence": 2,
            "consumption": current.consumption.model_copy(
                update={"search_calls": -1}
            ),
        }
    )
    with pytest.raises(ValueError):
        AuthoritativeInvestigationGraphState.model_validate(decreased.model_dump())


def test_checkpoint_repository_is_append_only_and_recovers_latest(tmp_path) -> None:
    repository = SQLiteAuthoritativeGraphCheckpointRepository(tmp_path / "graph.db")
    first = _state()
    second = first.model_copy(
        update={
            "checkpoint_sequence": 1,
            "phase": AuthoritativeGraphPhase.PLANNING,
            "completed_operations": (
                *first.completed_operations,
                AuthoritativeOperation.NORMALIZE_CLAIM,
            ),
            "operation_versions": {
                **first.operation_versions,
                AuthoritativeOperation.NORMALIZE_CLAIM: 1,
            },
        }
    )
    repository.append(first)
    repository.append(second)

    assert repository.latest(first.thread_id) == second
    assert repository.history(first.thread_id) == (first, second)
    with pytest.raises(AuthoritativeCheckpointConflictError):
        repository.append(second)


def test_reconstruction_requires_every_authoritative_artifact() -> None:
    state = _state()
    known = {state.artifacts[0].artifact_id}

    reconstructed = reconstruct_authoritative_graph_state(
        state.model_dump(mode="json"),
        artifact_exists=lambda item: item.artifact_id in known,
    )
    assert reconstructed == state

    with pytest.raises(ValueError, match="missing authoritative artifacts"):
        reconstruct_authoritative_graph_state(
            state.model_dump(mode="json"),
            artifact_exists=lambda _item: False,
        )


def test_legacy_multi_agent_state_migrates_without_embedding_evidence() -> None:
    investigation_id = uuid4()
    claim_id = uuid4()
    evidence_id = uuid4()
    legacy = DurableMultiAgentGraphState(
        investigation_id=investigation_id,
        parent_claim_id=claim_id,
        components=(
            DurableComponentReference(
                component_id=claim_id,
                parent_claim_id=claim_id,
                claim_summary="A legacy checkpoint claim.",
            ),
        ),
        stored_evidence_ids=(evidence_id,),
        approved_evidence_ids=(evidence_id,),
    )

    migrated = migrate_authoritative_graph_state(legacy.model_dump(mode="json"))

    assert migrated.schema_version == 1
    assert migrated.graph_version == "authoritative-investigation-graph-v1"
    assert migrated.phase is AuthoritativeGraphPhase.RESEARCH
    assert migrated.approved_evidence_ids == (evidence_id,)
    assert migrated.artifacts[0].artifact_id == evidence_id
    assert AuthoritativeOperation.CONSOLIDATE_EVIDENCE in migrated.completed_operations


def test_unsupported_future_state_version_is_rejected() -> None:
    payload = _state().model_dump(mode="json")
    payload["schema_version"] = 99
    with pytest.raises(ValueError, match="unsupported"):
        migrate_authoritative_graph_state(payload)


def test_stage9_3_schema_and_release_manifest_verifies() -> None:
    from pathlib import Path

    from claim_polygraph_ng.evaluation.phase9_graph_state import (
        build_phase9_graph_state_manifest,
        verify_phase9_graph_state_manifest,
    )

    root = Path(__file__).parents[2]
    manifest = build_phase9_graph_state_manifest(root)
    result = verify_phase9_graph_state_manifest(manifest, root)

    assert manifest.schema_version == 1
    assert manifest.invariant_count == 12
    assert len(manifest.artifacts) == 7
    assert result.valid
