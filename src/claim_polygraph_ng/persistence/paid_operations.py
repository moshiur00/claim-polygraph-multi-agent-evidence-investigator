"""Atomic SQLite paid-operation receipt and result ledger."""

import hashlib
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from claim_polygraph_ng.domain.investigation import ModelCallUsage
from claim_polygraph_ng.domain.paid_operations import (
    PaidCostLedger,
    PaidOperationKind,
    PaidOperationReceipt,
    PaidOperationSpec,
    PaidReceiptClaim,
    PaidReceiptDecision,
    PaidReceiptStatus,
    PaidUsageDisposition,
)
from claim_polygraph_ng.persistence.sqlite_runtime import connect_sqlite, enable_wal


class PaidOperationReceiptError(RuntimeError):
    pass


class PaidOperationActiveError(PaidOperationReceiptError):
    pass


class PaidOperationAmbiguousError(PaidOperationReceiptError):
    pass


class PaidOperationTerminalError(PaidOperationReceiptError):
    pass


class SQLitePaidOperationLedger:
    def __init__(self, database_path: str | Path) -> None:
        self._path = str(database_path)

    @contextmanager
    def _connect(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        connection = connect_sqlite(self._path)
        connection.row_factory = sqlite3.Row
        try:
            if immediate:
                connection.execute("BEGIN IMMEDIATE")
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
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS paid_operation_receipts (
                    operation_key TEXT PRIMARY KEY,
                    investigation_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    lease_expires_at TEXT,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS paid_receipts_investigation
                    ON paid_operation_receipts(investigation_id, status);
                CREATE TABLE IF NOT EXISTS paid_operation_results (
                    receipt_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                """
            )

    def reserve(
        self,
        spec: PaidOperationSpec,
        *,
        worker_id: str,
        lease_seconds: int = 120,
        now: datetime | None = None,
    ) -> PaidReceiptClaim:
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        self.initialize()
        instant = now or datetime.now(UTC)
        with self._connect(immediate=True) as connection:
            row = connection.execute(
                "SELECT payload FROM paid_operation_receipts WHERE operation_key = ?",
                (spec.operation_key,),
            ).fetchone()
            if row is None:
                receipt = PaidOperationReceipt(
                    spec=spec,
                    lease_owner=worker_id,
                    lease_expires_at=instant + timedelta(seconds=lease_seconds),
                    created_at=instant,
                    updated_at=instant,
                )
                self._save(connection, receipt)
                return PaidReceiptClaim(
                    decision=PaidReceiptDecision.EXECUTE,
                    receipt=receipt,
                )
            receipt = PaidOperationReceipt.model_validate_json(row["payload"])
            if receipt.spec != spec:
                raise PaidOperationReceiptError(
                    "operation key collision with different canonical input"
                )
            if receipt.status is PaidReceiptStatus.COMPLETED:
                return PaidReceiptClaim(
                    decision=PaidReceiptDecision.RETURN_CACHED,
                    receipt=receipt,
                )
            if receipt.status is PaidReceiptStatus.RESERVED:
                if receipt.lease_expires_at > instant:
                    return PaidReceiptClaim(
                        decision=PaidReceiptDecision.ACTIVE,
                        receipt=receipt,
                    )
                reclaimed = receipt.model_copy(
                    update={
                        "lease_owner": worker_id,
                        "lease_expires_at": instant + timedelta(seconds=lease_seconds),
                        "updated_at": instant,
                    }
                )
                self._save(connection, reclaimed)
                return PaidReceiptClaim(
                    decision=PaidReceiptDecision.EXECUTE,
                    receipt=reclaimed,
                )
            if receipt.status is PaidReceiptStatus.IN_PROGRESS:
                if receipt.lease_expires_at > instant:
                    return PaidReceiptClaim(
                        decision=PaidReceiptDecision.ACTIVE,
                        receipt=receipt,
                    )
                ambiguous = receipt.model_copy(
                    update={
                        "status": PaidReceiptStatus.AMBIGUOUS,
                        "lease_owner": None,
                        "lease_expires_at": None,
                        "updated_at": instant,
                        "safe_error": (
                            "Provider completion is unknown after worker lease expiry."
                        ),
                    }
                )
                self._save(connection, ambiguous)
                return PaidReceiptClaim(
                    decision=PaidReceiptDecision.AMBIGUOUS,
                    receipt=ambiguous,
                )
            if receipt.status is PaidReceiptStatus.FAILED_RETRYABLE:
                reserved = receipt.model_copy(
                    update={
                        "status": PaidReceiptStatus.RESERVED,
                        "lease_owner": worker_id,
                        "lease_expires_at": instant + timedelta(seconds=lease_seconds),
                        "updated_at": instant,
                        "provider_started_at": None,
                        "error_class": None,
                        "safe_error": None,
                    }
                )
                self._save(connection, reserved)
                return PaidReceiptClaim(
                    decision=PaidReceiptDecision.EXECUTE,
                    receipt=reserved,
                )
            decision = (
                PaidReceiptDecision.AMBIGUOUS
                if receipt.status is PaidReceiptStatus.AMBIGUOUS
                else PaidReceiptDecision.TERMINAL_FAILURE
            )
            return PaidReceiptClaim(decision=decision, receipt=receipt)

    def mark_provider_started(
        self,
        operation_key: str,
        *,
        worker_id: str,
        now: datetime | None = None,
    ) -> PaidOperationReceipt:
        instant = now or datetime.now(UTC)
        with self._connect(immediate=True) as connection:
            receipt = self._owned(connection, operation_key, worker_id)
            if receipt.status is not PaidReceiptStatus.RESERVED:
                raise PaidOperationReceiptError("only a reservation may start a provider")
            started = receipt.model_copy(
                update={
                    "status": PaidReceiptStatus.IN_PROGRESS,
                    "attempt_number": receipt.attempt_number + 1,
                    "provider_started_at": instant,
                    "updated_at": instant,
                }
            )
            self._save(connection, started)
            return started

    def complete(
        self,
        operation_key: str,
        *,
        worker_id: str,
        result_payload: str,
        usage: ModelCallUsage | None = None,
        unknown_cost_upper_bound_usd: float = 0.05,
        duration_seconds: float = 0,
        now: datetime | None = None,
    ) -> PaidOperationReceipt:
        instant = now or datetime.now(UTC)
        if unknown_cost_upper_bound_usd < 0:
            raise ValueError("unknown cost upper bound cannot be negative")
        result_sha256 = hashlib.sha256(result_payload.encode()).hexdigest()
        with self._connect(immediate=True) as connection:
            receipt = self._owned(connection, operation_key, worker_id)
            if receipt.status is not PaidReceiptStatus.IN_PROGRESS:
                raise PaidOperationReceiptError("only in-progress receipt may complete")
            usage_measured = (
                usage is not None and usage.estimated_cost_usd is not None
            )
            search_not_metered = (
                receipt.spec.kind is PaidOperationKind.SEARCH and usage is None
            )
            current_unknown = not usage_measured and not search_not_metered
            prior_unknown = (
                receipt.usage_disposition
                is PaidUsageDisposition.UNKNOWN_WITH_UPPER_BOUND
            )
            completed = receipt.model_copy(
                update={
                    "status": PaidReceiptStatus.COMPLETED,
                    "lease_owner": None,
                    "lease_expires_at": None,
                    "result_reference": f"paid-result:{receipt.receipt_id}",
                    "result_sha256": result_sha256,
                    "input_tokens": receipt.input_tokens
                    + (usage.input_tokens or 0 if usage else 0),
                    "cached_input_tokens": receipt.cached_input_tokens
                    + (usage.cached_input_tokens or 0 if usage else 0),
                    "output_tokens": receipt.output_tokens
                    + (usage.output_tokens or 0 if usage else 0),
                    "estimated_cost_usd": receipt.estimated_cost_usd
                    + (usage.estimated_cost_usd or 0 if usage else 0),
                    "usage_disposition": (
                        PaidUsageDisposition.UNKNOWN_WITH_UPPER_BOUND
                        if prior_unknown or current_unknown
                        else PaidUsageDisposition.NOT_APPLICABLE
                        if search_not_metered
                        else PaidUsageDisposition.MEASURED
                    ),
                    "estimated_cost_upper_bound_usd": (
                        (receipt.estimated_cost_upper_bound_usd or 0)
                        + (
                            unknown_cost_upper_bound_usd
                            if current_unknown
                            else 0
                        )
                        if prior_unknown or current_unknown
                        else None
                    ),
                    "usage_note": (
                        "One or more attempts have unknown priced usage; the "
                        "conservative upper bound is retained."
                        if prior_unknown or current_unknown
                        else "Search billing is not metered by this receipt."
                        if search_not_metered
                        else "Provider usage and price were measured."
                    ),
                    "duration_seconds": (
                        receipt.duration_seconds
                        + (usage.duration_seconds if usage else duration_seconds)
                    ),
                    "updated_at": instant,
                    "completed_at": instant,
                }
            )
            connection.execute(
                "INSERT INTO paid_operation_results(receipt_id, payload) VALUES (?, ?)",
                (str(receipt.receipt_id), result_payload),
            )
            self._save(connection, completed)
            return completed

    def fail(
        self,
        operation_key: str,
        *,
        worker_id: str,
        retryable: bool,
        error: Exception,
        usage: ModelCallUsage | None = None,
        unknown_cost_upper_bound_usd: float = 0.05,
        duration_seconds: float = 0,
    ) -> PaidOperationReceipt:
        if unknown_cost_upper_bound_usd < 0:
            raise ValueError("unknown cost upper bound cannot be negative")
        with self._connect(immediate=True) as connection:
            receipt = self._owned(connection, operation_key, worker_id)
            if receipt.status is not PaidReceiptStatus.IN_PROGRESS:
                raise PaidOperationReceiptError("only in-progress receipt may fail")
            now = datetime.now(UTC)
            usage_measured = (
                usage is not None and usage.estimated_cost_usd is not None
            )
            prior_unknown = (
                receipt.usage_disposition
                is PaidUsageDisposition.UNKNOWN_WITH_UPPER_BOUND
            )
            current_unknown = not usage_measured
            failed = receipt.model_copy(
                update={
                    "status": (
                        PaidReceiptStatus.FAILED_RETRYABLE
                        if retryable
                        else PaidReceiptStatus.FAILED_PERMANENT
                    ),
                    "lease_owner": None,
                    "lease_expires_at": None,
                    "error_class": type(error).__name__,
                    "safe_error": str(error)[:1_000],
                    "input_tokens": receipt.input_tokens
                    + (usage.input_tokens or 0 if usage else 0),
                    "cached_input_tokens": receipt.cached_input_tokens
                    + (usage.cached_input_tokens or 0 if usage else 0),
                    "output_tokens": receipt.output_tokens
                    + (usage.output_tokens or 0 if usage else 0),
                    "estimated_cost_usd": receipt.estimated_cost_usd
                    + (usage.estimated_cost_usd or 0 if usage else 0),
                    "usage_disposition": (
                        PaidUsageDisposition.UNKNOWN_WITH_UPPER_BOUND
                        if prior_unknown or current_unknown
                        else PaidUsageDisposition.MEASURED
                    ),
                    "estimated_cost_upper_bound_usd": (
                        (receipt.estimated_cost_upper_bound_usd or 0)
                        + (
                            unknown_cost_upper_bound_usd
                            if current_unknown
                            else 0
                        )
                        if prior_unknown or current_unknown
                        else None
                    ),
                    "usage_note": (
                        "One or more failed attempts have unknown priced usage; "
                        "the conservative upper bound is retained."
                        if prior_unknown or current_unknown
                        else "Provider response failed validation; measured usage is retained."
                    ),
                    "duration_seconds": (
                        receipt.duration_seconds
                        + (usage.duration_seconds if usage else duration_seconds)
                    ),
                    "updated_at": now,
                }
            )
            self._save(connection, failed)
            return failed

    def authorize_ambiguous_retry(
        self,
        operation_key: str,
        *,
        actor: str,
    ) -> PaidOperationReceipt:
        if len(actor.strip()) < 3:
            raise ValueError("manual recovery actor is required")
        with self._connect(immediate=True) as connection:
            receipt = self._load(connection, operation_key)
            if receipt.status is not PaidReceiptStatus.AMBIGUOUS:
                raise PaidOperationReceiptError("only ambiguous receipts need authorization")
            updated = receipt.model_copy(
                update={
                    "status": PaidReceiptStatus.FAILED_RETRYABLE,
                    "safe_error": f"Manual retry authorized by {actor}.",
                    "updated_at": datetime.now(UTC),
                }
            )
            self._save(connection, updated)
            return updated

    def load_result(self, receipt: PaidOperationReceipt) -> str:
        if receipt.status is not PaidReceiptStatus.COMPLETED:
            raise PaidOperationReceiptError("receipt has no completed result")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM paid_operation_results WHERE receipt_id = ?",
                (str(receipt.receipt_id),),
            ).fetchone()
        if row is None:
            raise PaidOperationReceiptError("completed receipt result is missing")
        payload = row["payload"]
        if hashlib.sha256(payload.encode()).hexdigest() != receipt.result_sha256:
            raise PaidOperationReceiptError("completed receipt result hash mismatch")
        return payload

    def get(self, operation_key: str) -> PaidOperationReceipt | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM paid_operation_receipts WHERE operation_key = ?",
                (operation_key,),
            ).fetchone()
        return PaidOperationReceipt.model_validate_json(row["payload"]) if row else None

    def cost_ledger(self, investigation_id: UUID) -> PaidCostLedger:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload FROM paid_operation_receipts
                WHERE investigation_id = ?
                """,
                (str(investigation_id),),
            ).fetchall()
        receipts = tuple(
            receipt
            for row in rows
            if (
                receipt := PaidOperationReceipt.model_validate_json(row["payload"])
            ).attempt_number
        )
        completed = tuple(
            item for item in receipts if item.status is PaidReceiptStatus.COMPLETED
        )
        failed_attempts = sum(
            max(
                0,
                item.attempt_number
                - (1 if item.status is PaidReceiptStatus.COMPLETED else 0),
            )
            for item in receipts
        )
        unpriced = tuple(
            item
            for item in receipts
            if item.usage_disposition
            in {
                PaidUsageDisposition.UNKNOWN_WITH_UPPER_BOUND,
                PaidUsageDisposition.LEGACY_UNCLASSIFIED,
            }
        )
        measured_cost = sum(item.estimated_cost_usd for item in receipts)
        upper_bound = measured_cost + sum(
            item.estimated_cost_upper_bound_usd or 0 for item in unpriced
        )
        return PaidCostLedger(
            completed_operation_count=len(completed),
            attempted_operation_count=sum(
                item.attempt_number for item in receipts
            ),
            failed_operation_count=failed_attempts,
            model_operation_count=sum(
                item.spec.kind is PaidOperationKind.MODEL for item in completed
            ),
            search_operation_count=sum(
                item.spec.kind is PaidOperationKind.SEARCH for item in completed
            ),
            input_tokens=sum(item.input_tokens for item in receipts),
            cached_input_tokens=sum(item.cached_input_tokens for item in receipts),
            output_tokens=sum(item.output_tokens for item in receipts),
            estimated_cost_usd=measured_cost,
            estimated_cost_upper_bound_usd=upper_bound,
            unpriced_operation_count=len(unpriced),
            cost_is_lower_bound=bool(unpriced),
            duration_seconds=sum(item.duration_seconds for item in receipts),
        )

    def list_receipts(
        self,
        investigation_id: UUID,
    ) -> tuple[PaidOperationReceipt, ...]:
        """Return the durable receipt history for one investigation."""
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload FROM paid_operation_receipts
                WHERE investigation_id = ?
                ORDER BY operation_key
                """,
                (str(investigation_id),),
            ).fetchall()
        return tuple(
            PaidOperationReceipt.model_validate_json(row["payload"]) for row in rows
        )

    def _owned(
        self,
        connection: sqlite3.Connection,
        operation_key: str,
        worker_id: str,
    ) -> PaidOperationReceipt:
        receipt = self._load(connection, operation_key)
        if receipt.lease_owner != worker_id:
            raise PaidOperationReceiptError("worker does not own receipt lease")
        return receipt

    @staticmethod
    def _load(
        connection: sqlite3.Connection,
        operation_key: str,
    ) -> PaidOperationReceipt:
        row = connection.execute(
            "SELECT payload FROM paid_operation_receipts WHERE operation_key = ?",
            (operation_key,),
        ).fetchone()
        if row is None:
            raise PaidOperationReceiptError("paid operation receipt not found")
        return PaidOperationReceipt.model_validate_json(row["payload"])

    @staticmethod
    def _save(
        connection: sqlite3.Connection,
        receipt: PaidOperationReceipt,
    ) -> None:
        connection.execute(
            """
            INSERT INTO paid_operation_receipts
            (operation_key, investigation_id, status, lease_expires_at, payload)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(operation_key) DO UPDATE SET
                status = excluded.status,
                lease_expires_at = excluded.lease_expires_at,
                payload = excluded.payload
            """,
            (
                receipt.spec.operation_key,
                str(receipt.spec.investigation_id),
                receipt.status.value,
                (
                    receipt.lease_expires_at.isoformat()
                    if receipt.lease_expires_at
                    else None
                ),
                receipt.model_dump_json(),
            ),
        )
