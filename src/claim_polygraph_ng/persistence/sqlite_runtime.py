"""Shared SQLite runtime policy for the measured local MVP."""

import sqlite3

SQLITE_BUSY_TIMEOUT_MS = 10_000


def connect_sqlite(
    path: str,
    *,
    check_same_thread: bool = True,
) -> sqlite3.Connection:
    connection = sqlite3.connect(
        path,
        timeout=SQLITE_BUSY_TIMEOUT_MS / 1_000,
        check_same_thread=check_same_thread,
    )
    connection.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def enable_wal(connection: sqlite3.Connection) -> None:
    mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
    if str(mode).casefold() != "wal":
        mode = connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
    if str(mode).casefold() != "wal":
        raise RuntimeError(f"SQLite WAL could not be enabled: {mode}")
    connection.execute("PRAGMA synchronous = NORMAL")
