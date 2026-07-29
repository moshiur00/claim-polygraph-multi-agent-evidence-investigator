"""Append-only SQLite checkpoints for the authoritative graph state."""

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from claim_polygraph_ng.domain.authoritative_graph import (
    AuthoritativeInvestigationGraphState,
)
from claim_polygraph_ng.persistence.sqlite_runtime import connect_sqlite, enable_wal


class AuthoritativeCheckpointConflictError(RuntimeError):
    """Raised when an append races or violates monotonic state."""


class AuthoritativeCheckpointCorruptionError(RuntimeError):
    """Raised when persisted authoritative state fails integrity validation."""


class SQLiteAuthoritativeGraphCheckpointRepository:
    def __init__(self, database_path: str | Path) -> None:
        self._database_path = str(database_path)

    @contextmanager
    def _connect(self) -> Iterator:
        connection = connect_sqlite(self._database_path)
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
            enable_wal(connection)
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS authoritative_graph_checkpoints (
                    thread_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    schema_version INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    payload_sha256 TEXT,
                    PRIMARY KEY (thread_id, sequence)
                )
                """
            )
            columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(authoritative_graph_checkpoints)"
                ).fetchall()
            }
            if "payload_sha256" not in columns:
                connection.execute(
                    "ALTER TABLE authoritative_graph_checkpoints "
                    "ADD COLUMN payload_sha256 TEXT"
                )

    def append(self, state: AuthoritativeInvestigationGraphState) -> None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload, payload_sha256 FROM authoritative_graph_checkpoints
                WHERE thread_id = ?
                ORDER BY sequence DESC LIMIT 1
                """,
                (state.thread_id,),
            ).fetchone()
            if row is None:
                if state.checkpoint_sequence != 0:
                    raise AuthoritativeCheckpointConflictError(
                        "first checkpoint sequence must be zero"
                    )
            else:
                from claim_polygraph_ng.application.authoritative_graph_state import (
                    validate_monotonic_graph_transition,
                )

                previous = _decode_checkpoint(row[0], row[1])
                try:
                    validate_monotonic_graph_transition(previous, state)
                except ValueError as error:
                    raise AuthoritativeCheckpointConflictError(str(error)) from error
            try:
                connection.execute(
                    """
                    INSERT INTO authoritative_graph_checkpoints
                    (thread_id, sequence, schema_version, payload, payload_sha256)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        state.thread_id,
                        state.checkpoint_sequence,
                        state.schema_version,
                        state.model_dump_json(),
                        _sha256(state.model_dump_json()),
                    ),
                )
            except Exception as error:
                raise AuthoritativeCheckpointConflictError(
                    "checkpoint sequence already exists"
                ) from error

    def latest(self, thread_id: str) -> AuthoritativeInvestigationGraphState | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload, payload_sha256 FROM authoritative_graph_checkpoints
                WHERE thread_id = ?
                ORDER BY sequence DESC LIMIT 1
                """,
                (thread_id,),
            ).fetchone()
        return (
            _decode_checkpoint(row[0], row[1])
            if row is not None
            else None
        )

    def history(self, thread_id: str) -> tuple[AuthoritativeInvestigationGraphState, ...]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT sequence, payload, payload_sha256
                FROM authoritative_graph_checkpoints
                WHERE thread_id = ?
                ORDER BY sequence
                """,
                (thread_id,),
            ).fetchall()
        if rows and tuple(row[0] for row in rows) != tuple(range(len(rows))):
            raise AuthoritativeCheckpointCorruptionError(
                "authoritative checkpoint sequence is not contiguous"
            )
        return tuple(_decode_checkpoint(row[1], row[2]) for row in rows)


def _sha256(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _decode_checkpoint(
    payload: str, expected_sha256: str | None
) -> AuthoritativeInvestigationGraphState:
    from claim_polygraph_ng.application.authoritative_graph_state import (
        migrate_authoritative_graph_state,
    )

    if expected_sha256 is not None and _sha256(payload) != expected_sha256:
        raise AuthoritativeCheckpointCorruptionError(
            "authoritative checkpoint SHA-256 mismatch"
        )
    try:
        return migrate_authoritative_graph_state(json.loads(payload))
    except Exception as error:
        raise AuthoritativeCheckpointCorruptionError(
            "authoritative checkpoint payload is invalid"
        ) from error
