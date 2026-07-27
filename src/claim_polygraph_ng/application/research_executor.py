"""Bounded shared execution substrate for Phase 4 research roles."""

import asyncio
import hashlib
import json
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from claim_polygraph_ng.domain import (
    ResearchAssignment,
    ResearchResult,
    SearchRequest,
    SearchResult,
)
from claim_polygraph_ng.persistence.research import SQLiteResearchRepository
from claim_polygraph_ng.providers import SearchProvider
from claim_polygraph_ng.retrieval import ContentFetcher, FetchedDocument


class ResearchWorker(Protocol):
    """Execute one role using only shared, policy-enforcing operations."""

    async def run(
        self,
        assignment: ResearchAssignment,
        operations: "SharedResearchOperations",
    ) -> ResearchResult: ...


class SharedResearchOperations:
    """Coalesce identical in-flight work and reuse successful durable results."""

    def __init__(
        self,
        *,
        repository: SQLiteResearchRepository,
        search_provider: SearchProvider,
        fetcher: ContentFetcher,
    ) -> None:
        self._repository = repository
        self._search_provider = search_provider
        self._fetcher = fetcher
        self._search_tasks: dict[str, asyncio.Task[tuple[SearchResult, ...]]] = {}
        self._fetch_tasks: dict[str, asyncio.Task[FetchedDocument]] = {}
        self._task_lock = asyncio.Lock()

    async def search(self, request: SearchRequest) -> tuple[SearchResult, ...]:
        cache_key = _search_cache_key(self._search_provider.provider_id, request)
        cached = self._repository.get_search(cache_key)
        if cached is not None:
            return cached
        task = await self._shared_task(
            self._search_tasks,
            cache_key,
            lambda: self._search_and_store(cache_key, request),
        )
        return await task

    async def fetch(self, url: str) -> FetchedDocument:
        cache_key = _fetch_cache_key(self._fetcher.provider_id, url)
        cached = self._repository.get_fetch(cache_key)
        if cached is not None:
            return cached
        task = await self._shared_task(
            self._fetch_tasks,
            cache_key,
            lambda: self._fetch_and_store(cache_key, url),
        )
        return await task

    async def _search_and_store(
        self,
        cache_key: str,
        request: SearchRequest,
    ) -> tuple[SearchResult, ...]:
        results = await self._search_provider.search(request)
        self._repository.save_search(cache_key, results)
        return results

    async def _fetch_and_store(self, cache_key: str, url: str) -> FetchedDocument:
        document = await self._fetcher.fetch(url)
        self._repository.save_fetch(cache_key, document)
        return document

    async def _shared_task(self, tasks: dict, key: str, factory) -> asyncio.Task:
        async with self._task_lock:
            task = tasks.get(key)
            if task is None:
                task = asyncio.create_task(factory())
                tasks[key] = task
                task.add_done_callback(lambda _completed: tasks.pop(key, None))
            return task


class ResearchExecutor:
    """Run compatible assignments concurrently and checkpoint every result."""

    def __init__(
        self,
        *,
        repository: SQLiteResearchRepository,
        operations: SharedResearchOperations,
        worker: ResearchWorker,
        maximum_concurrency: int,
    ) -> None:
        if maximum_concurrency < 1:
            raise ValueError("maximum_concurrency must be positive")
        self._repository = repository
        self._operations = operations
        self._worker = worker
        self._semaphore = asyncio.Semaphore(maximum_concurrency)

    async def execute(
        self,
        assignments: tuple[ResearchAssignment, ...],
    ) -> tuple[ResearchResult, ...]:
        """Return input-ordered results regardless of task completion order."""
        tasks = tuple(asyncio.create_task(self._execute_one(item)) for item in assignments)
        return tuple(await asyncio.gather(*tasks))

    async def _execute_one(self, assignment: ResearchAssignment) -> ResearchResult:
        stored = self._repository.get_result(assignment.assignment_id)
        if stored is not None:
            return stored
        async with self._semaphore:
            try:
                result = await self._worker.run(assignment, self._operations)
                if (
                    result.assignment_id != assignment.assignment_id
                    or result.role is not assignment.role
                    or result.component_id != assignment.component_id
                ):
                    raise ValueError("worker result does not match its assignment identity")
            except Exception as exc:
                result = ResearchResult(
                    assignment_id=assignment.assignment_id,
                    role=assignment.role,
                    component_id=assignment.component_id,
                    query_ids=(),
                    search_call_count=0,
                    fetch_call_count=0,
                    model_call_count=0,
                    estimated_cost_usd=0.0,
                    duration_seconds=0.0,
                    failure_reason=f"{type(exc).__name__}: {exc}",
                )
            self._repository.save_result(result)
            return result


def _search_cache_key(provider_id: str, request: SearchRequest) -> str:
    normalized = {
        "provider_id": provider_id,
        "query": " ".join(request.query.casefold().split()),
        "research_path": request.research_path.value,
        "maximum_results": request.maximum_results,
    }
    return _sha256_json(normalized)


def _fetch_cache_key(provider_id: str, url: str) -> str:
    return _sha256_json(
        {
            "provider_id": provider_id,
            "canonical_url": _canonicalize_url(url),
        }
    )


def _canonicalize_url(url: str) -> str:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").casefold()
    port = parsed.port
    netloc = host
    if port and not (
        (parsed.scheme.casefold() == "http" and port == 80)
        or (parsed.scheme.casefold() == "https" and port == 443)
    ):
        netloc = f"{host}:{port}"
    path = parsed.path or "/"
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    return urlunsplit((parsed.scheme.casefold(), netloc, path, query, ""))


def _sha256_json(value: dict) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()
