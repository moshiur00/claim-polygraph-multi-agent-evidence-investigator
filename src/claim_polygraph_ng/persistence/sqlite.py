"""SQLite persistence for the lightweight investigation lifecycle."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TypeVar
from uuid import UUID

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.investigation import ArtifactType, Investigation, TraceEvent

StoredArtifact = TypeVar("StoredArtifact", bound=DomainModel)


class SQLiteInvestigationRepository:
    """Persist complete Pydantic artifacts as validated JSON documents."""

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = str(database_path)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        """Create the minimal durable schema idempotently."""
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS investigations (
                    investigation_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS artifacts (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    investigation_id TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    artifact_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    UNIQUE (investigation_id, artifact_type, artifact_id),
                    FOREIGN KEY (investigation_id)
                        REFERENCES investigations (investigation_id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS trace_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    investigation_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    FOREIGN KEY (investigation_id)
                        REFERENCES investigations (investigation_id)
                        ON DELETE CASCADE
                );
                """
            )

    def save_investigation(self, investigation: Investigation) -> None:
        """Insert or replace the current investigation snapshot."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO investigations (investigation_id, payload)
                VALUES (?, ?)
                ON CONFLICT(investigation_id)
                DO UPDATE SET payload = excluded.payload
                """,
                (
                    str(investigation.investigation_id),
                    investigation.model_dump_json(),
                ),
            )

    def get_investigation(self, investigation_id: UUID) -> Investigation | None:
        """Load and validate the current investigation snapshot."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM investigations WHERE investigation_id = ?",
                (str(investigation_id),),
            ).fetchone()
        if row is None:
            return None
        return Investigation.model_validate_json(row[0])

    def list_investigations(self) -> tuple[Investigation, ...]:
        """Load all investigations in creation order."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM investigations ORDER BY rowid"
            ).fetchall()
        return tuple(Investigation.model_validate_json(row[0]) for row in rows)

    def save_artifact(
        self,
        investigation_id: UUID,
        artifact_type: ArtifactType,
        artifact_id: UUID,
        artifact: DomainModel,
    ) -> None:
        """Persist one typed artifact under an investigation."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO artifacts (
                    investigation_id,
                    artifact_type,
                    artifact_id,
                    payload
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(investigation_id, artifact_type, artifact_id)
                DO UPDATE SET payload = excluded.payload
                """,
                (
                    str(investigation_id),
                    artifact_type.value,
                    str(artifact_id),
                    artifact.model_dump_json(),
                ),
            )

    def list_artifacts(
        self,
        investigation_id: UUID,
        artifact_type: ArtifactType,
        artifact_model: type[StoredArtifact],
    ) -> tuple[StoredArtifact, ...]:
        """Load artifacts in insertion order and revalidate each payload."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload
                FROM artifacts
                WHERE investigation_id = ? AND artifact_type = ?
                ORDER BY sequence
                """,
                (str(investigation_id), artifact_type.value),
            ).fetchall()
        return tuple(artifact_model.model_validate_json(row[0]) for row in rows)

    def append_event(self, event: TraceEvent) -> None:
        """Append one immutable trace event."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO trace_events (event_id, investigation_id, payload)
                VALUES (?, ?, ?)
                """,
                (
                    str(event.event_id),
                    str(event.investigation_id),
                    event.model_dump_json(),
                ),
            )

    def list_events(self, investigation_id: UUID) -> tuple[TraceEvent, ...]:
        """Load trace events in append order."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload
                FROM trace_events
                WHERE investigation_id = ?
                ORDER BY sequence
                """,
                (str(investigation_id),),
            ).fetchall()
        return tuple(TraceEvent.model_validate_json(row[0]) for row in rows)
