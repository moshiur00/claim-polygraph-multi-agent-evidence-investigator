"""Provider-independent interfaces used by application services."""

from collections.abc import Mapping
from typing import Protocol, TypeVar

from pydantic import JsonValue

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.investigation import ModelTask, SearchRequest, SearchResult

StructuredResult = TypeVar("StructuredResult", bound=DomainModel)


class StructuredModelProvider(Protocol):
    """Generate a validated artifact for a logical model task."""

    provider_id: str

    async def generate(
        self,
        *,
        task: ModelTask,
        response_model: type[StructuredResult],
        inputs: Mapping[str, JsonValue],
    ) -> StructuredResult: ...


class SearchProvider(Protocol):
    """Search for candidate passages without exposing provider details."""

    provider_id: str

    async def search(self, request: SearchRequest) -> tuple[SearchResult, ...]: ...
