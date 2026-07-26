"""Persistence protocol for investigations and typed artifacts."""

from typing import Protocol, TypeVar
from uuid import UUID

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.investigation import ArtifactType, Investigation, TraceEvent

StoredArtifact = TypeVar("StoredArtifact", bound=DomainModel)


class InvestigationRepository(Protocol):
    """Minimal persistence boundary for the first vertical slice."""

    def initialize(self) -> None: ...

    def save_investigation(self, investigation: Investigation) -> None: ...

    def get_investigation(self, investigation_id: UUID) -> Investigation | None: ...

    def list_investigations(self) -> tuple[Investigation, ...]: ...

    def save_artifact(
        self,
        investigation_id: UUID,
        artifact_type: ArtifactType,
        artifact_id: UUID,
        artifact: DomainModel,
    ) -> None: ...

    def list_artifacts(
        self,
        investigation_id: UUID,
        artifact_type: ArtifactType,
        artifact_model: type[StoredArtifact],
    ) -> tuple[StoredArtifact, ...]: ...

    def append_event(self, event: TraceEvent) -> None: ...

    def list_events(self, investigation_id: UUID) -> tuple[TraceEvent, ...]: ...
