"""Append-only SQLite review ledger with a tamper-evident hash chain."""

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TypeVar
from uuid import UUID

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.review import (
    ApprovalDecision,
    ApprovalRecord,
    ReviewAuditAction,
    ReviewAuditEvent,
    ReviewAuditTrail,
    ReviewerDecisionRecord,
    ReviewFinding,
    ReviewRequest,
    VerdictRevision,
)

T = TypeVar("T", bound=DomainModel)


class ReviewLedgerError(RuntimeError):
    """Base review-ledger failure."""


class ReviewConcurrencyError(ReviewLedgerError):
    """The caller acted on a stale event sequence."""


class ReviewPolicyError(ReviewLedgerError):
    """A review or approval policy would be violated."""


class SQLiteReviewLedger:
    """Store immutable review entities and one hash-chained event per append."""

    _TABLES = (
        "review_requests",
        "review_findings",
        "reviewer_decisions",
        "approval_records",
        "verdict_revisions",
        "review_audit_events",
    )

    def __init__(self, database_path: str | Path) -> None:
        self._path = str(database_path)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._path)
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
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS review_requests (
                    entity_id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS review_findings (
                    entity_id TEXT PRIMARY KEY, request_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    FOREIGN KEY(request_id) REFERENCES review_requests(request_id)
                );
                CREATE TABLE IF NOT EXISTS reviewer_decisions (
                    entity_id TEXT PRIMARY KEY, request_id TEXT NOT NULL,
                    decision_id TEXT NOT NULL UNIQUE, payload TEXT NOT NULL,
                    UNIQUE(request_id),
                    FOREIGN KEY(request_id) REFERENCES review_requests(request_id)
                );
                CREATE TABLE IF NOT EXISTS approval_records (
                    entity_id TEXT PRIMARY KEY, request_id TEXT NOT NULL,
                    payload TEXT NOT NULL, UNIQUE(request_id),
                    FOREIGN KEY(request_id) REFERENCES review_requests(request_id)
                );
                CREATE TABLE IF NOT EXISTS verdict_revisions (
                    entity_id TEXT PRIMARY KEY, request_id TEXT NOT NULL,
                    payload TEXT NOT NULL, UNIQUE(request_id),
                    FOREIGN KEY(request_id) REFERENCES review_requests(request_id)
                );
                CREATE TABLE IF NOT EXISTS review_audit_events (
                    request_id TEXT NOT NULL, sequence INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY(request_id, sequence),
                    FOREIGN KEY(request_id) REFERENCES review_requests(request_id)
                );
                """
            )
            for table in self._TABLES:
                connection.executescript(
                    f"""
                    CREATE TRIGGER IF NOT EXISTS {table}_no_update
                    BEFORE UPDATE ON {table}
                    BEGIN SELECT RAISE(ABORT, 'append-only table'); END;
                    CREATE TRIGGER IF NOT EXISTS {table}_no_delete
                    BEFORE DELETE ON {table}
                    BEGIN SELECT RAISE(ABORT, 'append-only table'); END;
                    """
                )

    def create_request(self, request: ReviewRequest) -> ReviewRequest:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO review_requests VALUES (?, ?, ?)",
                (str(request.request_id), str(request.request_id), request.model_dump_json()),
            )
            self._append_event(
                connection,
                request.request_id,
                ReviewAuditAction.REQUEST_CREATED,
                request.request_id,
                request.created_by,
                request,
            )
        return request

    def add_finding(self, finding: ReviewFinding, *, expected_sequence: int) -> ReviewFinding:
        with self._connect() as connection:
            self._check_sequence(connection, finding.request_id, expected_sequence)
            connection.execute(
                "INSERT INTO review_findings VALUES (?, ?, ?)",
                (str(finding.finding_id), str(finding.request_id), finding.model_dump_json()),
            )
            self._append_event(
                connection,
                finding.request_id,
                ReviewAuditAction.FINDING_ADDED,
                finding.finding_id,
                finding.recorded_by,
                finding,
            )
        return finding

    def record_decision(
        self, decision: ReviewerDecisionRecord, *, expected_sequence: int
    ) -> ReviewerDecisionRecord:
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT payload FROM reviewer_decisions WHERE decision_id = ?",
                (str(decision.decision_id),),
            ).fetchone()
            if existing:
                saved = ReviewerDecisionRecord.model_validate_json(existing[0])
                if (
                    saved.decision_id == decision.decision_id
                    and saved.request_id == decision.request_id
                    and saved.kind is decision.kind
                    and saved.reviewer_identity == decision.reviewer_identity
                    and saved.rationale == decision.rationale
                    and saved.proposed_verdict is decision.proposed_verdict
                ):
                    return saved
                raise ReviewPolicyError("decision ID already represents different content")
            self._check_sequence(connection, decision.request_id, expected_sequence)
            try:
                connection.execute(
                    "INSERT INTO reviewer_decisions VALUES (?, ?, ?, ?)",
                    (
                        str(decision.record_id),
                        str(decision.request_id),
                        str(decision.decision_id),
                        decision.model_dump_json(),
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise ReviewPolicyError("the request already has a reviewer decision") from error
            self._append_event(
                connection,
                decision.request_id,
                ReviewAuditAction.DECISION_RECORDED,
                decision.record_id,
                decision.reviewer_identity,
                decision,
            )
        return decision

    def record_approval(
        self, approval: ApprovalRecord, *, expected_sequence: int
    ) -> ApprovalRecord:
        with self._connect() as connection:
            self._check_sequence(connection, approval.request_id, expected_sequence)
            decision = self._one(
                connection,
                "reviewer_decisions",
                approval.decision_record_id,
                ReviewerDecisionRecord,
            )
            if decision.request_id != approval.request_id:
                raise ReviewPolicyError("approval and decision belong to different requests")
            if decision.reviewer_identity.casefold() == approval.approver_identity.casefold():
                raise ReviewPolicyError("approver must be distinct from reviewer")
            try:
                connection.execute(
                    "INSERT INTO approval_records VALUES (?, ?, ?)",
                    (
                        str(approval.approval_id),
                        str(approval.request_id),
                        approval.model_dump_json(),
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise ReviewPolicyError("the request already has an approval") from error
            self._append_event(
                connection,
                approval.request_id,
                ReviewAuditAction.APPROVAL_RECORDED,
                approval.approval_id,
                approval.approver_identity,
                approval,
            )
        return approval

    def record_revision(
        self, revision: VerdictRevision, *, expected_sequence: int
    ) -> VerdictRevision:
        with self._connect() as connection:
            self._check_sequence(connection, revision.request_id, expected_sequence)
            decision = self._one(
                connection,
                "reviewer_decisions",
                revision.decision_record_id,
                ReviewerDecisionRecord,
            )
            if decision.request_id != revision.request_id:
                raise ReviewPolicyError("revision and decision belong to different requests")
            if decision.proposed_verdict != revision.revised_verdict:
                raise ReviewPolicyError("revision does not match the reviewer's proposal")
            if revision.approval_id is None:
                raise ReviewPolicyError("authoritative verdict revisions require approval")
            approval = self._one(
                connection, "approval_records", revision.approval_id, ApprovalRecord
            )
            if approval.request_id != revision.request_id:
                raise ReviewPolicyError("revision and approval belong to different requests")
            if approval.decision is not ApprovalDecision.APPROVE:
                raise ReviewPolicyError("revision requires an approving record")
            if approval.decision_record_id != decision.record_id:
                raise ReviewPolicyError("approval does not cover this decision")
            try:
                connection.execute(
                    "INSERT INTO verdict_revisions VALUES (?, ?, ?)",
                    (
                        str(revision.revision_id),
                        str(revision.request_id),
                        revision.model_dump_json(),
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise ReviewPolicyError("the request already has a verdict revision") from error
            self._append_event(
                connection,
                revision.request_id,
                ReviewAuditAction.REVISION_RECORDED,
                revision.revision_id,
                approval.approver_identity,
                revision,
            )
        return revision

    def load(self, request_id: UUID) -> ReviewAuditTrail:
        with self._connect() as connection:
            request = self._one(connection, "review_requests", request_id, ReviewRequest)
            findings = self._many(connection, "review_findings", request_id, ReviewFinding)
            decisions = self._many(
                connection, "reviewer_decisions", request_id, ReviewerDecisionRecord
            )
            approvals = self._many(connection, "approval_records", request_id, ApprovalRecord)
            revisions = self._many(connection, "verdict_revisions", request_id, VerdictRevision)
            events = self._events(connection, request_id)
        return ReviewAuditTrail(
            request=request,
            findings=findings,
            decisions=decisions,
            approvals=approvals,
            revisions=revisions,
            events=events,
            chain_valid=self._verify(events),
        )

    def list_requests(self) -> tuple[ReviewRequest, ...]:
        """Return immutable review requests in creation order."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM review_requests ORDER BY rowid"
            ).fetchall()
        return tuple(ReviewRequest.model_validate_json(row[0]) for row in rows)

    def find_by_thread(self, graph_thread_id: str) -> ReviewAuditTrail | None:
        """Locate the review associated with one durable graph thread."""
        for request in self.list_requests():
            if request.graph_thread_id == graph_thread_id:
                return self.load(request.request_id)
        return None

    def _append_event(
        self,
        connection: sqlite3.Connection,
        request_id: UUID,
        action: ReviewAuditAction,
        entity_id: UUID,
        actor: str,
        entity: DomainModel,
    ) -> None:
        rows = connection.execute(
            "SELECT payload FROM review_audit_events WHERE request_id = ? ORDER BY sequence",
            (str(request_id),),
        ).fetchall()
        previous = ReviewAuditEvent.model_validate_json(rows[-1][0]) if rows else None
        sequence = len(rows) + 1
        payload_json = json.dumps(
            entity.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        )
        payload_hash = hashlib.sha256(payload_json.encode()).hexdigest()
        occurred_at = entity.created_at
        core = {
            "request_id": str(request_id),
            "sequence": sequence,
            "action": action.value,
            "entity_id": str(entity_id),
            "actor_identity": actor,
            "occurred_at": occurred_at.isoformat(),
            "payload_hash": payload_hash,
            "previous_event_hash": previous.event_hash if previous else None,
        }
        event_hash = hashlib.sha256(
            json.dumps(core, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        event = ReviewAuditEvent(**core, payload_json=payload_json, event_hash=event_hash)
        connection.execute(
            "INSERT INTO review_audit_events VALUES (?, ?, ?)",
            (str(request_id), sequence, event.model_dump_json()),
        )

    @staticmethod
    def _check_sequence(connection: sqlite3.Connection, request_id: UUID, expected: int) -> None:
        row = connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) FROM review_audit_events WHERE request_id = ?",
            (str(request_id),),
        ).fetchone()
        if row[0] != expected:
            raise ReviewConcurrencyError(
                f"stale review version: expected {expected}, current {row[0]}"
            )

    @staticmethod
    def _one(connection: sqlite3.Connection, table: str, entity_id: UUID, model: type[T]) -> T:
        row = connection.execute(
            f"SELECT payload FROM {table} WHERE entity_id = ?", (str(entity_id),)
        ).fetchone()
        if row is None:
            raise ReviewLedgerError(f"{table} entity not found: {entity_id}")
        return model.model_validate_json(row[0])

    @staticmethod
    def _many(
        connection: sqlite3.Connection, table: str, request_id: UUID, model: type[T]
    ) -> tuple[T, ...]:
        rows = connection.execute(
            f"SELECT payload FROM {table} WHERE request_id = ? ORDER BY rowid",
            (str(request_id),),
        ).fetchall()
        return tuple(model.model_validate_json(row[0]) for row in rows)

    @staticmethod
    def _events(connection: sqlite3.Connection, request_id: UUID) -> tuple[ReviewAuditEvent, ...]:
        rows = connection.execute(
            "SELECT payload FROM review_audit_events WHERE request_id = ? ORDER BY sequence",
            (str(request_id),),
        ).fetchall()
        return tuple(ReviewAuditEvent.model_validate_json(row[0]) for row in rows)

    @staticmethod
    def _verify(events: tuple[ReviewAuditEvent, ...]) -> bool:
        previous: str | None = None
        for expected, event in enumerate(events, 1):
            if event.sequence != expected or event.previous_event_hash != previous:
                return False
            if hashlib.sha256(event.payload_json.encode()).hexdigest() != event.payload_hash:
                return False
            core = {
                "request_id": str(event.request_id),
                "sequence": event.sequence,
                "action": event.action.value,
                "entity_id": str(event.entity_id),
                "actor_identity": event.actor_identity,
                "occurred_at": event.occurred_at.isoformat(),
                "payload_hash": event.payload_hash,
                "previous_event_hash": event.previous_event_hash,
            }
            calculated = hashlib.sha256(
                json.dumps(core, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            if calculated != event.event_hash:
                return False
            previous = event.event_hash
        return True
