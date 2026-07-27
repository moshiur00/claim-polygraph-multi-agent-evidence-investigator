"""Durable Phase 4 operation caches and assignment checkpoints."""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

from claim_polygraph_ng.domain import Evidence, ResearchResult, SearchResult, Source
from claim_polygraph_ng.domain.research import MultiAgentWorkflowCheckpoint
from claim_polygraph_ng.retrieval import FetchedDocument


class SQLiteResearchRepository:
    """Persist successful shared operations and terminal assignment results."""

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = str(database_path)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._database_path)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS research_search_cache (
                    cache_key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS research_fetch_cache (
                    cache_key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS research_assignment_results (
                    assignment_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS research_sources (
                    source_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS research_evidence (
                    evidence_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS research_workflows (
                    investigation_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                """
            )

    def get_search(self, cache_key: str) -> tuple[SearchResult, ...] | None:
        payload = self._get_payload("research_search_cache", "cache_key", cache_key)
        if payload is None:
            return None
        return tuple(SearchResult.model_validate(item) for item in json.loads(payload))

    def save_search(self, cache_key: str, results: tuple[SearchResult, ...]) -> None:
        payload = json.dumps(
            [result.model_dump(mode="json") for result in results],
            ensure_ascii=False,
        )
        self._put_payload("research_search_cache", "cache_key", cache_key, payload)

    def get_fetch(self, cache_key: str) -> FetchedDocument | None:
        payload = self._get_payload("research_fetch_cache", "cache_key", cache_key)
        return FetchedDocument.model_validate_json(payload) if payload is not None else None

    def save_fetch(self, cache_key: str, document: FetchedDocument) -> None:
        self._put_payload(
            "research_fetch_cache",
            "cache_key",
            cache_key,
            document.model_dump_json(),
        )

    def get_result(self, assignment_id: UUID) -> ResearchResult | None:
        payload = self._get_payload(
            "research_assignment_results",
            "assignment_id",
            str(assignment_id),
        )
        return ResearchResult.model_validate_json(payload) if payload is not None else None

    def save_result(self, result: ResearchResult) -> None:
        self._put_payload(
            "research_assignment_results",
            "assignment_id",
            str(result.assignment_id),
            result.model_dump_json(),
        )

    def save_source(self, source: Source) -> None:
        self._put_payload(
            "research_sources", "source_id", str(source.source_id), source.model_dump_json()
        )

    def get_sources(self, source_ids: tuple[UUID, ...]) -> tuple[Source, ...]:
        return tuple(
            source
            for source_id in source_ids
            if (source := self._load_model("research_sources", "source_id", source_id, Source))
            is not None
        )

    def save_evidence(self, evidence: Evidence) -> None:
        self._put_payload(
            "research_evidence",
            "evidence_id",
            str(evidence.evidence_id),
            evidence.model_dump_json(),
        )

    def get_evidence(self, evidence_ids: tuple[UUID, ...]) -> tuple[Evidence, ...]:
        return tuple(
            evidence
            for evidence_id in evidence_ids
            if (
                evidence := self._load_model(
                    "research_evidence", "evidence_id", evidence_id, Evidence
                )
            )
            is not None
        )

    def save_workflow(self, checkpoint: MultiAgentWorkflowCheckpoint) -> None:
        self._put_payload(
            "research_workflows",
            "investigation_id",
            str(checkpoint.investigation_id),
            checkpoint.model_dump_json(),
        )

    def get_workflow(self, investigation_id: UUID) -> MultiAgentWorkflowCheckpoint | None:
        return self._load_model(
            "research_workflows",
            "investigation_id",
            investigation_id,
            MultiAgentWorkflowCheckpoint,
        )

    def _load_model(self, table, key_column, key, model):
        payload = self._get_payload(table, key_column, str(key))
        return model.model_validate_json(payload) if payload is not None else None

    def _get_payload(self, table: str, key_column: str, key: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT payload FROM {table} WHERE {key_column} = ?",
                (key,),
            ).fetchone()
        return str(row[0]) if row else None

    def _put_payload(self, table: str, key_column: str, key: str, payload: str) -> None:
        with self._connect() as connection:
            connection.execute(
                f"""
                INSERT INTO {table} ({key_column}, payload)
                VALUES (?, ?)
                ON CONFLICT({key_column}) DO UPDATE SET payload = excluded.payload
                """,
                (key, payload),
            )
