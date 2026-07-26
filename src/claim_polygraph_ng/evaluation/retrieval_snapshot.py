"""Record and replay normalized search responses for reproducible ablations."""

import json
from datetime import UTC, datetime
from pathlib import Path

from claim_polygraph_ng.domain import SearchRequest, SearchResult
from claim_polygraph_ng.evaluation.models import (
    BenchmarkDataset,
    RetrievalSearchSnapshot,
    RetrievalSnapshotCandidate,
    RetrievalSnapshotQuery,
)
from claim_polygraph_ng.providers.base import SearchProvider
from claim_polygraph_ng.providers.searxng import SearchProviderError


class RecordingSearchProvider:
    """Delegate searches while retaining each normalized response or failure."""

    def __init__(self, provider: SearchProvider) -> None:
        self._provider = provider
        self.provider_id = f"{provider.provider_id}+recording"
        self.source_provider_id = provider.provider_id
        self._queries: dict[str, RetrievalSnapshotQuery] = {}

    @property
    def queries(self) -> tuple[RetrievalSnapshotQuery, ...]:
        """Return captured queries in first-call order."""
        return tuple(self._queries.values())

    async def search(self, request: SearchRequest) -> tuple[SearchResult, ...]:
        """Record the normalized provider response and preserve provider behavior."""
        try:
            results = await self._provider.search(request)
        except Exception as error:
            self._queries[request.query] = RetrievalSnapshotQuery(
                query=request.query,
                results=(),
                error_type=type(error).__name__,
                error_message=str(error),
            )
            raise

        self._queries[request.query] = RetrievalSnapshotQuery(
            query=request.query,
            results=tuple(
                RetrievalSnapshotCandidate(
                    url=result.url,
                    title=result.title,
                    snippet=result.snippet,
                    source_type=result.source_type,
                    publisher=result.publisher,
                )
                for result in results
            ),
        )
        return results


class SnapshotReplaySearchProvider:
    """Serve captured responses by exact query without network access."""

    def __init__(self, snapshot: RetrievalSearchSnapshot) -> None:
        self.snapshot = snapshot
        self.provider_id = f"snapshot:{snapshot.provider_id}"
        self._queries = {item.query: item for item in snapshot.queries}

    async def search(self, request: SearchRequest) -> tuple[SearchResult, ...]:
        """Replay one captured response, enforcing its original result budget."""
        if request.maximum_results > self.snapshot.top_k:
            raise SearchProviderError(
                f"snapshot top-k is {self.snapshot.top_k}, "
                f"but replay requested {request.maximum_results}"
            )
        captured = self._queries.get(request.query)
        if captured is None:
            raise SearchProviderError(f"query is absent from snapshot: {request.query}")
        if captured.error_type is not None:
            raise SearchProviderError(
                f"captured {captured.error_type}: {captured.error_message}"
            )
        return tuple(
            SearchResult(
                url=item.url,
                title=item.title,
                snippet=item.snippet,
                source_type=item.source_type,
                publisher=item.publisher,
            )
            for item in captured.results[: request.maximum_results]
        )


def build_retrieval_snapshot(
    dataset: BenchmarkDataset,
    provider: RecordingSearchProvider,
    *,
    top_k: int,
    require_nonempty: bool = False,
) -> RetrievalSearchSnapshot:
    """Build a versioned snapshot from one completed recording run."""
    snapshot = RetrievalSearchSnapshot(
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.version,
        provider_id=provider.source_provider_id,
        captured_at=datetime.now(UTC),
        top_k=top_k,
        queries=provider.queries,
    )
    if require_nonempty:
        empty_queries = tuple(
            query.query
            for query in snapshot.queries
            if not query.results and query.error_type is None
        )
        if empty_queries:
            raise SearchProviderError(
                f"snapshot capture is incomplete: {len(empty_queries)} queries returned no results"
            )
    return snapshot


def load_retrieval_snapshot(path: str | Path) -> RetrievalSearchSnapshot:
    """Load and validate a retrieval snapshot."""
    return RetrievalSearchSnapshot.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


def export_retrieval_snapshot(
    snapshot: RetrievalSearchSnapshot,
    path: str | Path,
) -> Path:
    """Write one versioned raw retrieval snapshot."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(snapshot.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output
