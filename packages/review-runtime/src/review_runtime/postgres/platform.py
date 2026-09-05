from __future__ import annotations

import base64
import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from review_core.application.execution import (
    CommitOutcomeUnknown,
    ExecutionAdmission,
    ExecutionClaim,
    ExecutionFailure,
    ExecutionTerminal,
)
from review_core.application.findings import next_decision
from review_core.application.idempotency import require_idempotency_key
from review_core.application.platform import DocumentRecord, ReviewExecutor, RunRecord
from review_core.application.profiles import ProfileVersion
from review_core.canonical import canonical_bytes, digest_value, strong_etag
from review_core.dialogue.engine import deterministic_dialogue_response
from review_core.domain.errors import Conflict, InvalidRequest, NotFound, PayloadTooLarge

from review_runtime.artifacts.posix import PosixArtifactStore
from review_runtime.config.settings import OperatorSettings
from review_runtime.documents.pdf import PdfDocumentParser
from review_runtime.documents.text import TextDocumentParser
from review_runtime.postgres.artifact_fence import advisory_fence_key
from review_runtime.reports import CanonicalReportValidator

CODEC = "jcs-rfc8785-0.1.4"
RELEASE_PROFILE_SEMANTIC = {
    "name": "Base data specification review",
    "role": "Analyst with developer and tester viewpoints",
    "goal": "Find ambiguity before implementation",
    "checks": ["Sources and fields", "Transformations and schedules"],
}


def utc_now() -> datetime:
    return datetime.now(UTC)


def wire_time(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@dataclass(frozen=True, slots=True)
class ReviewStorageRequest:
    workspace_id: str
    idempotency_key: str
    request_body: dict[str, Any]
    run_id: str
    snapshot_id: str
    snapshot: dict[str, Any]
    run_value: dict[str, Any]
    sources: tuple[dict[str, Any], ...]


class PostgresReviewExecutionStorage:
    """Short, connection-owned PostgreSQL phases for one review execution."""

    def __init__(
        self,
        *,
        database_url: str,
        organization_id: str,
        workspace_id: str,
        artifacts: PosixArtifactStore,
        report_validator: CanonicalReportValidator,
        dialogue_policy: dict[str, Any],
        terminal_committer: Callable[[psycopg.Connection[dict[str, Any]]], None] | None = None,
    ) -> None:
        self.database_url = database_url
        self.organization_id = organization_id
        self.workspace_id = workspace_id
        self.artifacts = artifacts
        self.report_validator = report_validator
        self.dialogue_policy = dialogue_policy
        self._terminal_committer = terminal_committer or (lambda connection: connection.commit())

    def connect(self) -> psycopg.Connection[dict[str, Any]]:
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def admit(self, request: ReviewStorageRequest, deadline_at: datetime) -> ExecutionAdmission:
        if request.workspace_id != self.workspace_id:
            raise NotFound()
        if deadline_at.tzinfo is None:
            raise ValueError("deadline_at must be timezone-aware")
        require_idempotency_key(request.idempotency_key)
        request_digest = digest_value(request.request_body)
        operation = "create_run"
        lock_key = advisory_fence_key(
            "review-admission",
            f"{self.organization_id}:{request.workspace_id}:{operation}:{request.idempotency_key}",
            "v1",
        )
        execution_id = str(uuid4())
        work_item_id = str(uuid4())
        connection = self.connect()
        try:
            connection.execute("SELECT pg_advisory_xact_lock(%s)", (lock_key,))
            existing = connection.execute(
                """SELECT request_digest, resource_id
                   FROM idempotency_records
                   WHERE organization_id=%s AND workspace_id=%s
                     AND operation=%s AND key=%s""",
                (
                    self.organization_id,
                    request.workspace_id,
                    operation,
                    request.idempotency_key,
                ),
            ).fetchone()
            if existing is not None:
                if existing["request_digest"] != request_digest:
                    raise Conflict(
                        "idempotency_conflict",
                        "The key was already used with a different request.",
                    )
                execution = connection.execute(
                    """SELECT id FROM review_run_executions
                       WHERE organization_id=%s AND workspace_id=%s AND run_id=%s""",
                    (self.organization_id, request.workspace_id, existing["resource_id"]),
                ).fetchone()
                if execution is None:
                    raise RuntimeError("replayed review run has no execution record")
                connection.commit()
                return ExecutionAdmission(
                    resource_id=existing["resource_id"],
                    execution_id=execution["id"],
                    replay=True,
                )
            created_at = datetime.now(UTC)
            connection.execute(
                """INSERT INTO execution_snapshots(
                     organization_id,workspace_id,id,digest,codec_id,value,created_at
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (organization_id,workspace_id,digest) DO NOTHING""",
                (
                    self.organization_id,
                    request.workspace_id,
                    request.snapshot_id,
                    digest_value(request.snapshot),
                    CODEC,
                    Jsonb(request.snapshot),
                    created_at,
                ),
            )
            connection.execute(
                """INSERT INTO review_runs(
                     organization_id,workspace_id,id,document_id,state,revision,snapshot,value,
                     cancel_requested_at
                   ) VALUES(%s,%s,%s,%s,'queued',0,%s,%s,NULL)""",
                (
                    self.organization_id,
                    request.workspace_id,
                    request.run_id,
                    request.request_body["document_id"],
                    Jsonb(request.snapshot),
                    Jsonb(request.run_value),
                ),
            )
            for source in request.sources:
                connection.execute(
                    """INSERT INTO review_run_sources(
                         organization_id,workspace_id,run_id,source_id,document_id,role,ordinal,prepared
                       ) VALUES(%s,%s,%s,%s,%s,%s,%s,NULL)""",
                    (
                        self.organization_id,
                        request.workspace_id,
                        request.run_id,
                        source["source_id"],
                        source["document_id"],
                        source["role"],
                        source["ordinal"],
                    ),
                )
            execution_value = {
                "deadline_at": wire_time(deadline_at),
                "prepared_input_digest": None,
                "started_at": None,
                "finished_at": None,
                "error": None,
            }
            connection.execute(
                """INSERT INTO review_run_executions(
                     run_id,organization_id,workspace_id,id,state,checkpoint,attempt_count,
                     lease_token,lease_owner,revision,value
                   ) VALUES(%s,%s,%s,%s,'accepted','accepted',0,NULL,NULL,0,%s)""",
                (
                    request.run_id,
                    self.organization_id,
                    request.workspace_id,
                    execution_id,
                    Jsonb(execution_value),
                ),
            )
            connection.execute(
                """INSERT INTO review_work_items(
                     organization_id,workspace_id,execution_id,id,ordinal,fragment_id,state,value
                   ) VALUES(%s,%s,%s,%s,0,NULL,'accepted',%s)""",
                (
                    self.organization_id,
                    request.workspace_id,
                    execution_id,
                    work_item_id,
                    Jsonb({"source_ids": [source["source_id"] for source in request.sources]}),
                ),
            )
            connection.execute(
                """INSERT INTO idempotency_records(
                     organization_id,workspace_id,operation,key,request_digest,codec_id,
                     resource_kind,resource_id
                   ) VALUES(%s,%s,%s,%s,%s,%s,'review_run',%s)""",
                (
                    self.organization_id,
                    request.workspace_id,
                    operation,
                    request.idempotency_key,
                    request_digest,
                    CODEC,
                    request.run_id,
                ),
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()
        return ExecutionAdmission(
            resource_id=request.run_id,
            execution_id=execution_id,
            replay=False,
        )

    def claim(self, admission: ExecutionAdmission, owner_token: str) -> ExecutionClaim | None:
        connection = self.connect()
        try:
            row = connection.execute(
                """SELECT e.state, e.value, r.state AS run_state, r.cancel_requested_at, r.value AS run_value
                   FROM review_run_executions e
                   JOIN review_runs r
                     ON (r.organization_id,r.workspace_id,r.id) =
                        (e.organization_id,e.workspace_id,e.run_id)
                   WHERE e.organization_id=%s AND e.workspace_id=%s
                     AND e.id=%s AND e.run_id=%s
                   FOR UPDATE OF e, r""",
                (
                    self.organization_id,
                    self.workspace_id,
                    admission.execution_id,
                    admission.resource_id,
                ),
            ).fetchone()
            if (
                row is None
                or row["state"] != "accepted"
                or row["run_state"] != "queued"
                or row["cancel_requested_at"] is not None
            ):
                connection.rollback()
                return None
            if not connection.execute(
                "SELECT clock_timestamp() < (%s->>'deadline_at')::timestamptz",
                (Jsonb(row["value"]),),
            ).fetchone()["?column?"]:
                connection.rollback()
                return None
            started_at = datetime.now(UTC)
            execution_value = row["value"] | {"started_at": wire_time(started_at)}
            updated = connection.execute(
                """UPDATE review_run_executions
                   SET state='running',checkpoint='preparing',attempt_count=attempt_count+1,
                       lease_token=%s,lease_owner=%s,revision=revision+1,value=%s
                   WHERE organization_id=%s AND workspace_id=%s AND id=%s
                     AND run_id=%s AND state='accepted' AND lease_token IS NULL
                   RETURNING id""",
                (
                    owner_token,
                    owner_token,
                    Jsonb(execution_value),
                    self.organization_id,
                    self.workspace_id,
                    admission.execution_id,
                    admission.resource_id,
                ),
            ).fetchone()
            if updated is None:
                connection.rollback()
                return None
            connection.execute(
                """UPDATE review_work_items SET state='running'
                   WHERE organization_id=%s AND workspace_id=%s AND execution_id=%s
                     AND state='accepted'""",
                (self.organization_id, self.workspace_id, admission.execution_id),
            )
            run_value = row["run_value"] | {
                "state": "preparing",
                "started_at": wire_time(started_at),
                "progress": {"percent": 20, "message": "Preparing sources"},
            }
            connection.execute(
                """UPDATE review_runs SET state='preparing',revision=revision+1,value=%s
                   WHERE organization_id=%s AND workspace_id=%s AND id=%s AND state='queued'""",
                (
                    Jsonb(run_value),
                    self.organization_id,
                    self.workspace_id,
                    admission.resource_id,
                ),
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()
        return ExecutionClaim(
            resource_id=admission.resource_id,
            execution_id=admission.execution_id,
            owner_token=owner_token,
        )

    def save_prepared(self, claim: ExecutionClaim, prepared: dict[str, Any]) -> None:
        sources = prepared.get("sources")
        if not isinstance(sources, dict):
            raise ValueError("prepared review must contain source snapshots")
        prepared_digest = prepared.get("prepared_input_digest") or digest_value(prepared)
        connection = self.connect()
        try:
            row = connection.execute(
                """SELECT e.state, e.lease_token, e.value, r.state AS run_state,
                          r.cancel_requested_at, r.value AS run_value
                   FROM review_run_executions e
                   JOIN review_runs r
                     ON (r.organization_id,r.workspace_id,r.id) =
                        (e.organization_id,e.workspace_id,e.run_id)
                   WHERE e.organization_id=%s AND e.workspace_id=%s
                     AND e.id=%s AND e.run_id=%s
                   FOR UPDATE OF e, r""",
                (
                    self.organization_id,
                    self.workspace_id,
                    claim.execution_id,
                    claim.resource_id,
                ),
            ).fetchone()
            if row is None or row["lease_token"] != claim.owner_token or row["state"] != "running":
                raise Conflict("execution_owner_conflict", "Review execution owner is stale.")
            if row["cancel_requested_at"] is not None or row["run_state"] == "cancelled":
                raise Conflict("execution_cancelled", "Review execution was cancelled.")
            deadline_open = connection.execute(
                "SELECT clock_timestamp() < (%s->>'deadline_at')::timestamptz AS open",
                (Jsonb(row["value"]),),
            ).fetchone()
            if deadline_open is None or not deadline_open["open"]:
                raise TimeoutError("review execution deadline expired")
            persisted_sources = connection.execute(
                """SELECT source_id FROM review_run_sources
                   WHERE organization_id=%s AND workspace_id=%s AND run_id=%s
                   ORDER BY ordinal""",
                (self.organization_id, self.workspace_id, claim.resource_id),
            ).fetchall()
            expected_source_ids = [item["source_id"] for item in persisted_sources]
            if set(sources) != set(expected_source_ids):
                raise ValueError("prepared review source inventory is not exact")
            for source_id in expected_source_ids:
                connection.execute(
                    """UPDATE review_run_sources SET prepared=%s
                       WHERE organization_id=%s AND workspace_id=%s AND run_id=%s
                         AND source_id=%s AND prepared IS NULL""",
                    (
                        Jsonb(sources[source_id]),
                        self.organization_id,
                        self.workspace_id,
                        claim.resource_id,
                        source_id,
                    ),
                )
            work_item_value = prepared.get("work_item", {})
            connection.execute(
                """UPDATE review_work_items SET state='prepared', value=%s
                   WHERE organization_id=%s AND workspace_id=%s AND execution_id=%s
                     AND state='running'""",
                (
                    Jsonb(work_item_value),
                    self.organization_id,
                    self.workspace_id,
                    claim.execution_id,
                ),
            )
            run_value = row["run_value"] | {
                "state": "reviewing",
                "progress": {"percent": 60, "message": "Reviewing document"},
            }
            connection.execute(
                """UPDATE review_runs SET state='reviewing', revision=revision+1, value=%s
                   WHERE organization_id=%s AND workspace_id=%s AND id=%s
                     AND state='preparing' AND cancel_requested_at IS NULL""",
                (
                    Jsonb(run_value),
                    self.organization_id,
                    self.workspace_id,
                    claim.resource_id,
                ),
            )
            execution_value = row["value"] | {"prepared_input_digest": prepared_digest}
            owner_cas = connection.execute(
                """UPDATE review_run_executions
                   SET checkpoint='reviewing', revision=revision+1, value=%s
                   WHERE organization_id=%s AND workspace_id=%s AND id=%s AND run_id=%s
                     AND state='running' AND lease_token=%s
                   RETURNING id""",
                (
                    Jsonb(execution_value),
                    self.organization_id,
                    self.workspace_id,
                    claim.execution_id,
                    claim.resource_id,
                    claim.owner_token,
                ),
            ).fetchone()
            if owner_cas is None:
                raise Conflict("execution_owner_conflict", "Review execution owner is stale.")
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def publish(
        self,
        claim: ExecutionClaim,
        result: dict[str, Any],
        deadline_at: datetime,
    ) -> ExecutionTerminal:
        self.report_validator.validate(result)
        report_bytes = canonical_bytes(result)
        digest = hashlib.sha256(report_bytes).hexdigest()
        etag = strong_etag(report_bytes)
        staged = self.artifacts.stage(self.workspace_id, report_bytes, expected_sha256=digest)
        connection = self.connect()
        commit_started = False
        try:
            current = connection.execute(
                """SELECT e.state AS execution_state, e.lease_token, e.value AS execution_value,
                          r.state AS run_state, r.cancel_requested_at, r.value AS run_value
                   FROM review_run_executions e
                   JOIN review_runs r
                     ON (r.organization_id,r.workspace_id,r.id) =
                        (e.organization_id,e.workspace_id,e.run_id)
                   WHERE e.organization_id=%s AND e.workspace_id=%s
                     AND e.id=%s AND e.run_id=%s
                   FOR UPDATE OF e, r""",
                (
                    self.organization_id,
                    self.workspace_id,
                    claim.execution_id,
                    claim.resource_id,
                ),
            ).fetchone()
            if current is None:
                raise Conflict("execution_owner_conflict", "Review execution owner is stale.")
            if current["run_state"] == "cancelled" or current["execution_state"] == "cancelled":
                connection.rollback()
                return ExecutionTerminal(claim.resource_id, "cancelled")
            if (
                current["lease_token"] != claim.owner_token
                or current["execution_state"] != "running"
                or current["run_state"] not in {"preparing", "reviewing", "validating"}
            ):
                raise Conflict("execution_owner_conflict", "Review execution owner is stale.")
            database_deadline = connection.execute(
                "SELECT clock_timestamp() < %s AS open",
                (deadline_at,),
            ).fetchone()
            if database_deadline is None or not database_deadline["open"]:
                raise TimeoutError("review execution deadline expired")
            store_key = self.artifacts.promote(staged)
            artifact_id = str(uuid4())
            report_id = result["id"]
            created_at = datetime.now(UTC)
            fence = advisory_fence_key(self.workspace_id, store_key, digest)
            connection.execute("SELECT pg_advisory_xact_lock(%s)", (fence,))
            connection.execute(
                """INSERT INTO artifacts(
                     organization_id,workspace_id,id,kind,store_key,sha256,size_bytes,
                     media_type,canonical_codec_id,created_at
                   ) VALUES(%s,%s,%s,'report_canonical',%s,%s,%s,'application/json',%s,%s)""",
                (
                    self.organization_id,
                    self.workspace_id,
                    artifact_id,
                    store_key,
                    digest,
                    len(report_bytes),
                    CODEC,
                    created_at,
                ),
            )
            connection.execute(
                """INSERT INTO review_reports(
                     organization_id,workspace_id,id,run_id,artifact_id,canonical_sha256,
                     etag,codec_id,graph,created_at
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    self.organization_id,
                    self.workspace_id,
                    report_id,
                    claim.resource_id,
                    artifact_id,
                    digest,
                    etag,
                    CODEC,
                    Jsonb(result),
                    created_at,
                ),
            )
            connection.execute(
                """INSERT INTO report_coverage(organization_id,workspace_id,report_id,value)
                   VALUES(%s,%s,%s,%s)""",
                (self.organization_id, self.workspace_id, report_id, Jsonb(result["coverage"])),
            )
            connection.execute(
                """INSERT INTO report_provenance(organization_id,workspace_id,report_id,value)
                   VALUES(%s,%s,%s,%s)""",
                (self.organization_id, self.workspace_id, report_id, Jsonb(result["provenance"])),
            )
            self._insert_findings(connection, claim.resource_id, report_id, result["findings"])
            connection.execute(
                """UPDATE review_work_items SET state='completed'
                   WHERE organization_id=%s AND workspace_id=%s AND execution_id=%s
                     AND state='prepared'""",
                (self.organization_id, self.workspace_id, claim.execution_id),
            )
            finished_at = datetime.now(UTC)
            completed_run = current["run_value"] | {
                "state": "completed",
                "progress": {"percent": 100, "message": "Review completed"},
                "finished_at": wire_time(finished_at),
                "report_available": True,
                "error": None,
            }
            completed_execution = current["execution_value"] | {
                "finished_at": wire_time(finished_at),
                "error": None,
            }
            terminal_cas = connection.execute(
                """WITH execution_terminal AS (
                     UPDATE review_run_executions e
                     SET state='completed', checkpoint='published', revision=e.revision+1, value=%s
                     WHERE e.organization_id=%s AND e.workspace_id=%s
                       AND e.id=%s AND e.run_id=%s AND e.state='running'
                       AND e.lease_token=%s AND clock_timestamp() < %s
                       AND EXISTS (
                         SELECT 1 FROM review_runs r
                         WHERE r.organization_id=e.organization_id
                           AND r.workspace_id=e.workspace_id AND r.id=e.run_id
                           AND r.state IN ('preparing','reviewing','validating')
                           AND r.cancel_requested_at IS NULL
                       )
                     RETURNING e.run_id
                   ), run_terminal AS (
                     UPDATE review_runs r
                     SET state='completed', revision=r.revision+1, value=%s
                     WHERE r.organization_id=%s AND r.workspace_id=%s AND r.id=%s
                       AND r.state IN ('preparing','reviewing','validating')
                       AND r.cancel_requested_at IS NULL
                       AND EXISTS (SELECT 1 FROM execution_terminal e WHERE e.run_id=r.id)
                     RETURNING r.id
                   )
                   SELECT (SELECT count(*) FROM execution_terminal) AS executions,
                          (SELECT count(*) FROM run_terminal) AS runs""",
                (
                    Jsonb(completed_execution),
                    self.organization_id,
                    self.workspace_id,
                    claim.execution_id,
                    claim.resource_id,
                    claim.owner_token,
                    deadline_at,
                    Jsonb(completed_run),
                    self.organization_id,
                    self.workspace_id,
                    claim.resource_id,
                ),
            ).fetchone()
            if terminal_cas is None or terminal_cas["executions"] != 1 or terminal_cas["runs"] != 1:
                raise TimeoutError("review terminal publication was not admitted")
            commit_started = True
            self._terminal_committer(connection)
        except psycopg.Error as error:
            if commit_started:
                raise CommitOutcomeUnknown from error
            connection.rollback()
            raise
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()
        return ExecutionTerminal(claim.resource_id, "completed")

    def _insert_findings(
        self,
        connection: psycopg.Connection[dict[str, Any]],
        run_id: str,
        report_id: str,
        findings: list[dict[str, Any]],
    ) -> None:
        for finding in findings:
            connection.execute(
                """INSERT INTO findings(organization_id,workspace_id,report_id,id,ordinal,value)
                   VALUES(%s,%s,%s,%s,%s,%s)""",
                (
                    self.organization_id,
                    self.workspace_id,
                    report_id,
                    finding["id"],
                    finding["ordinal"],
                    Jsonb(finding),
                ),
            )
            for ordinal, anchor in enumerate(finding["anchors"], start=1):
                connection.execute(
                    """INSERT INTO finding_anchors(
                         organization_id,workspace_id,finding_id,ordinal,value
                       ) VALUES(%s,%s,%s,%s,%s)""",
                    (
                        self.organization_id,
                        self.workspace_id,
                        finding["id"],
                        ordinal,
                        Jsonb(anchor),
                    ),
                )
            decision = {
                "status": "unreviewed",
                "revision": 0,
                "actor": None,
                "reason": None,
                "resolution": None,
                "decided_at": None,
            }
            dialogue_id = str(uuid4())
            dialogue = {
                "id": dialogue_id,
                "run_id": run_id,
                "finding_id": finding["id"],
                "revision": 0,
                "state": "open",
                "turn_count": 0,
                "can_send_message": True,
                "blocked_reason": None,
                "policy": self.dialogue_policy,
                "turns": [],
            }
            connection.execute(
                """INSERT INTO finding_states(
                     organization_id,workspace_id,finding_id,decision_revision,value
                   ) VALUES(%s,%s,%s,0,%s)""",
                (self.organization_id, self.workspace_id, finding["id"], Jsonb(decision)),
            )
            connection.execute(
                """INSERT INTO finding_dialogues(
                     organization_id,workspace_id,id,finding_id,revision,value
                   ) VALUES(%s,%s,%s,%s,0,%s)""",
                (
                    self.organization_id,
                    self.workspace_id,
                    dialogue_id,
                    finding["id"],
                    Jsonb(dialogue),
                ),
            )

    def fail(self, claim: ExecutionClaim, failure: ExecutionFailure) -> ExecutionTerminal:
        connection = self.connect()
        try:
            current = connection.execute(
                """SELECT e.state AS execution_state, e.lease_token, e.value AS execution_value,
                          r.state AS run_state, r.value AS run_value
                   FROM review_run_executions e
                   JOIN review_runs r
                     ON (r.organization_id,r.workspace_id,r.id) =
                        (e.organization_id,e.workspace_id,e.run_id)
                   WHERE e.organization_id=%s AND e.workspace_id=%s
                     AND e.id=%s AND e.run_id=%s
                   FOR UPDATE OF e, r""",
                (
                    self.organization_id,
                    self.workspace_id,
                    claim.execution_id,
                    claim.resource_id,
                ),
            ).fetchone()
            if current is None:
                raise Conflict("execution_owner_conflict", "Review execution owner is stale.")
            if current["run_state"] == "cancelled" or current["execution_state"] == "cancelled":
                connection.rollback()
                return ExecutionTerminal(claim.resource_id, "cancelled")
            if current["run_state"] == "completed" and current["execution_state"] == "completed":
                connection.rollback()
                return ExecutionTerminal(claim.resource_id, "completed")
            if current["lease_token"] != claim.owner_token or current["execution_state"] != "running":
                raise Conflict("execution_owner_conflict", "Review execution owner is stale.")
            finished_at = datetime.now(UTC)
            public_error = {
                "code": failure.code,
                "message": failure.safe_message,
                "retryable": failure.retryable,
            }
            failed_run = current["run_value"] | {
                "state": "failed",
                "finished_at": wire_time(finished_at),
                "report_available": False,
                "error": public_error,
            }
            failed_execution = current["execution_value"] | {
                "finished_at": wire_time(finished_at),
                "error": public_error,
            }
            connection.execute(
                """UPDATE review_work_items SET state='failed'
                   WHERE organization_id=%s AND workspace_id=%s AND execution_id=%s
                     AND state IN ('accepted','running','prepared')""",
                (self.organization_id, self.workspace_id, claim.execution_id),
            )
            terminal_cas = connection.execute(
                """WITH execution_terminal AS (
                     UPDATE review_run_executions e
                     SET state='failed', checkpoint='failed', revision=e.revision+1, value=%s
                     WHERE e.organization_id=%s AND e.workspace_id=%s
                       AND e.id=%s AND e.run_id=%s AND e.state='running' AND e.lease_token=%s
                     RETURNING e.run_id
                   ), run_terminal AS (
                     UPDATE review_runs r SET state='failed', revision=r.revision+1, value=%s
                     WHERE r.organization_id=%s AND r.workspace_id=%s AND r.id=%s
                       AND r.state NOT IN ('completed','failed','cancelled')
                       AND EXISTS (SELECT 1 FROM execution_terminal e WHERE e.run_id=r.id)
                     RETURNING r.id
                   )
                   SELECT (SELECT count(*) FROM execution_terminal) AS executions,
                          (SELECT count(*) FROM run_terminal) AS runs""",
                (
                    Jsonb(failed_execution),
                    self.organization_id,
                    self.workspace_id,
                    claim.execution_id,
                    claim.resource_id,
                    claim.owner_token,
                    Jsonb(failed_run),
                    self.organization_id,
                    self.workspace_id,
                    claim.resource_id,
                ),
            ).fetchone()
            if terminal_cas is None or terminal_cas["executions"] != 1 or terminal_cas["runs"] != 1:
                raise Conflict("execution_owner_conflict", "Review execution owner is stale.")
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()
        return ExecutionTerminal(claim.resource_id, "failed", error_code=failure.code)

    def read_terminal(self, resource_id: str) -> ExecutionTerminal | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT state, value->'error'->>'code' AS error_code
                   FROM review_runs
                   WHERE organization_id=%s AND workspace_id=%s AND id=%s""",
                (self.organization_id, self.workspace_id, resource_id),
            ).fetchone()
        if row is None or row["state"] not in {"completed", "failed", "cancelled"}:
            return None
        return ExecutionTerminal(resource_id, row["state"], error_code=row["error_code"])


class PostgresReviewPlatform:
    """Normalized PostgreSQL/POSIX composition implementing the canonical application facade."""

    def __init__(self, executor: ReviewExecutor, settings: OperatorSettings) -> None:
        self.executor = executor
        self.settings = settings
        self.database_url = settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        self.artifacts = PosixArtifactStore(settings.artifact_root)
        self.report_validator = CanonicalReportValidator(settings.report_contract_path)
        self.organization_id = str(settings.organization_id)
        self.workspace_id = str(settings.workspace_id)
        self.actor = {"id": str(settings.actor_id), "display_name": settings.actor_display_name}
        self.max_upload_bytes = 52_428_800
        self.model_profile = {
            "id": settings.model_profile_id,
            "version": "1.0.0",
            "name": "Deterministic offline",
            "description": "Offline technical conformance profile without semantic model claims.",
            "capabilities": ["text_generation", "native_structured_output"],
            "availability": "available",
        }
        self.dialogue_policy = {
            "id": settings.dialogue_policy_id,
            "version": "1.0.0",
            "digest": digest_value({"max_member_turns": None}),
            "max_member_turns": None,
        }
        self._seed_exact()
        self.review_storage = PostgresReviewExecutionStorage(
            database_url=self.database_url,
            organization_id=self.organization_id,
            workspace_id=self.workspace_id,
            artifacts=self.artifacts,
            report_validator=self.report_validator,
            dialogue_policy=self.dialogue_policy,
        )

    def _connect(self) -> psycopg.Connection[dict[str, Any]]:
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def _workspace(self, workspace_id: str) -> None:
        if workspace_id != self.workspace_id:
            raise NotFound()

    def _seed_exact(self) -> None:
        now = utc_now()
        semantic = RELEASE_PROFILE_SEMANTIC
        model_payload = {"adapter_kind": "deterministic", "capabilities": ["text_generation"]}
        skill_payload = {"package_sha256": self.settings.skill_package_sha256}
        policy_payload = {"max_member_turns": None}
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO deployments(id, release_version, created_at) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
                (str(self.settings.deployment_id), "0.1.0", now),
            )
            connection.execute(
                "INSERT INTO organizations(id,name) VALUES(%s,%s) ON CONFLICT DO NOTHING",
                (self.organization_id, self.settings.organization_name),
            )
            connection.execute(
                "INSERT INTO workspaces(organization_id,id,name) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
                (self.organization_id, self.workspace_id, self.settings.workspace_name),
            )
            connection.execute(
                "INSERT INTO actors(organization_id,workspace_id,id,display_name) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (self.organization_id, self.workspace_id, self.actor["id"], self.actor["display_name"]),
            )
            family_row = str(self.settings.deployment_id)
            connection.execute(
                """INSERT INTO review_profile_families
                (row_id,organization_id,workspace_id,deployment_id,public_id,scope,created_at)
                VALUES(%s,NULL,NULL,%s,%s,'system',%s) ON CONFLICT DO NOTHING""",
                (family_row, str(self.settings.deployment_id), self.settings.system_profile_id, now),
            )
            connection.execute(
                """INSERT INTO review_profile_versions
                (family_row_id,version,semantic_digest,semantic_codec_id,name,role,goal,checks,
                 supersedes_version,created_at) VALUES(%s,'1.0.0',%s,%s,%s,%s,%s,%s,NULL,%s)
                ON CONFLICT DO NOTHING""",
                (
                    family_row,
                    digest_value(semantic),
                    CODEC,
                    semantic["name"],
                    semantic["role"],
                    semantic["goal"],
                    Jsonb(semantic["checks"]),
                    now,
                ),
            )
            connection.execute(
                "INSERT INTO review_profile_heads(family_row_id,head_version,revision) VALUES(%s,'1.0.0',0) ON CONFLICT DO NOTHING",
                (family_row,),
            )
            for table, config_id, payload in (
                ("model_profile_versions", self.settings.model_profile_id, model_payload),
                ("skill_versions", self.settings.skill_id, skill_payload),
                ("dialogue_policy_versions", self.settings.dialogue_policy_id, policy_payload),
            ):
                connection.execute(
                    f"INSERT INTO {table}(id,version,digest,codec_id,payload,created_at) VALUES(%s,'1.0.0',%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    (config_id, digest_value(payload), CODEC, Jsonb(payload), now),
                )
            connection.execute(
                """INSERT INTO model_profile_availability
                (deployment_id,model_profile_id,model_profile_version,state,reason_code,checked_at,
                 expires_at,revision) VALUES(%s,%s,'1.0.0','available',NULL,%s,%s,0)
                ON CONFLICT DO NOTHING""",
                (
                    str(self.settings.deployment_id),
                    self.settings.model_profile_id,
                    now,
                    now + timedelta(days=3650),
                ),
            )
            checks = connection.execute(
                """SELECT d.release_version,o.name,w.name AS workspace_name,a.display_name,
                pv.semantic_digest,m.digest AS model_digest,s.payload->>'package_sha256' AS skill_digest,
                p.digest AS policy_digest,av.state,av.expires_at
                FROM deployments d
                JOIN review_profile_families f ON f.deployment_id=d.id
                JOIN review_profile_heads h ON h.family_row_id=f.row_id
                JOIN review_profile_versions pv ON pv.family_row_id=h.family_row_id AND pv.version=h.head_version
                JOIN model_profile_versions m ON m.id=%s AND m.version='1.0.0'
                JOIN skill_versions s ON s.id=%s AND s.version='1.0.0'
                JOIN dialogue_policy_versions p ON p.id=%s AND p.version='1.0.0'
                JOIN model_profile_availability av ON av.deployment_id=d.id
                AND av.model_profile_id=m.id AND av.model_profile_version=m.version
                CROSS JOIN organizations o
                JOIN workspaces w ON w.organization_id=o.id
                JOIN actors a ON a.organization_id=w.organization_id AND a.workspace_id=w.id
                WHERE d.id=%s AND o.id=%s AND w.id=%s AND a.id=%s AND f.public_id=%s""",
                (
                    self.settings.model_profile_id,
                    self.settings.skill_id,
                    self.settings.dialogue_policy_id,
                    str(self.settings.deployment_id),
                    self.organization_id,
                    self.workspace_id,
                    self.actor["id"],
                    self.settings.system_profile_id,
                ),
            ).fetchone()
            expected = (
                checks
                and checks["release_version"] == "0.1.0"
                and checks["name"] == self.settings.organization_name
                and checks["workspace_name"] == self.settings.workspace_name
                and checks["display_name"] == self.settings.actor_display_name
                and checks["semantic_digest"] == digest_value(semantic)
                and checks["model_digest"] == digest_value(model_payload)
                and checks["skill_digest"] == self.settings.skill_package_sha256
                and checks["policy_digest"] == digest_value(policy_payload)
                and checks["state"] == "available"
                and checks["expires_at"] > now
            )
            if not expected:
                raise RuntimeError("configured runtime seed is missing or drifted")

    def bootstrap(self) -> dict[str, Any]:
        return {
            "actor": self.actor,
            "workspace": {
                "id": self.workspace_id,
                "organization_id": self.organization_id,
                "organization_name": self.settings.organization_name,
                "name": self.settings.workspace_name,
            },
            "limits": {"document_upload_max_bytes": self.max_upload_bytes, "max_context_documents": 50},
        }

    def check_seed(self) -> bool:
        self._seed_exact()
        check_configuration = getattr(self.executor, "check_release_configuration", None)
        if callable(check_configuration):
            check_configuration(
                review_profile_semantic_digest=digest_value(RELEASE_PROFILE_SEMANTIC),
                skill_package_sha256=self.settings.skill_package_sha256,
                engine_version="1.0.0",
            )
        return True

    @staticmethod
    def _validate_upload(filename: str, media_type: str, content: bytes, limit: int) -> None:
        if not content:
            raise InvalidRequest("empty_document", "Zero-byte documents are not accepted.")
        if len(content) > limit:
            raise PayloadTooLarge("Document exceeds configured byte limit.")
        allowed = {
            "text/markdown": (".md", ".markdown"),
            "text/plain": (".txt",),
            "application/pdf": (".pdf",),
        }
        suffix_ok = any(filename.lower().endswith(suffix) for suffix in allowed.get(media_type, ()))
        bytes_ok = content.startswith(b"%PDF-") if media_type == "application/pdf" else media_type in allowed
        if not suffix_ok or not bytes_ok:
            raise InvalidRequest(
                "media_type_mismatch", "Declared media type does not match filename or bytes."
            )
        if media_type != "application/pdf":
            try:
                content.decode("utf-8")
            except UnicodeDecodeError as error:
                raise InvalidRequest("invalid_utf8", "Text document is not valid UTF-8.") from error

    def upload(self, workspace_id: str, filename: str, media_type: str, content: bytes) -> dict[str, Any]:
        self._workspace(workspace_id)
        self._validate_upload(filename, media_type, content, self.max_upload_bytes)
        now = utc_now()
        document_id, artifact_id, extraction_id = str(uuid4()), str(uuid4()), str(uuid4())
        digest = hashlib.sha256(content).hexdigest()
        staged = self.artifacts.stage(self.workspace_id, bytes(content), expected_sha256=digest)
        parser = PdfDocumentParser() if media_type == "application/pdf" else TextDocumentParser()
        try:
            fragments = parser.parse(content, source_id="source-main", document_id=document_id)
            extraction_state, error_code = "completed", None
        except ValueError:
            fragments, extraction_state, error_code = [], "failed", "extraction_failed"
        store_key = f"{staged.namespace}/{staged.object_name}"
        fence = advisory_fence_key(self.workspace_id, store_key, digest)
        with self._connect() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(%s)", (fence,))
            promoted = self.artifacts.promote(staged)
            connection.execute(
                """INSERT INTO artifacts(organization_id,workspace_id,id,kind,store_key,sha256,
                size_bytes,media_type,canonical_codec_id,created_at) VALUES(%s,%s,%s,'document_original',
                %s,%s,%s,%s,NULL,%s)""",
                (
                    self.organization_id,
                    self.workspace_id,
                    artifact_id,
                    promoted,
                    digest,
                    len(content),
                    media_type,
                    now,
                ),
            )
            connection.execute(
                """INSERT INTO document_versions(organization_id,workspace_id,id,artifact_id,filename,
                media_type,sha256,size_bytes,extraction_state,created_by,created_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'pending',%s,%s)""",
                (
                    self.organization_id,
                    self.workspace_id,
                    document_id,
                    artifact_id,
                    Path(filename).name,
                    media_type,
                    digest,
                    len(content),
                    self.actor["id"],
                    now,
                ),
            )
            connection.execute(
                """INSERT INTO document_extractions(organization_id,workspace_id,id,state,checkpoint,
                attempt_count,lease_token,lease_owner,lease_expires_at,heartbeat_at,revision,document_id,
                parser_name,parser_version,settings_digest,settings_codec_id,error_code,safe_error_message,value)
                VALUES(%s,%s,%s,%s,%s,1,NULL,NULL,NULL,NULL,1,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    self.organization_id,
                    self.workspace_id,
                    extraction_id,
                    extraction_state,
                    "fragments_persisted" if fragments else "bytes_verified",
                    document_id,
                    parser.name,
                    parser.version,
                    parser.settings_digest,
                    CODEC,
                    error_code,
                    None if error_code is None else "Source has no usable extractable text.",
                    Jsonb({}),
                ),
            )
            for fragment in fragments:
                connection.execute(
                    """INSERT INTO fragments(organization_id,workspace_id,id,document_id,extraction_id,
                    ordinal,kind,text,content_sha256,location,created_at)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        self.organization_id,
                        self.workspace_id,
                        fragment["id"],
                        document_id,
                        extraction_id,
                        fragment["ordinal"],
                        fragment["kind"],
                        fragment["text"],
                        fragment["content_sha256"],
                        Jsonb(fragment["location"]),
                        now,
                    ),
                )
        return self.document_value(self.get_document(workspace_id, document_id))

    def get_document(self, workspace_id: str, document_id: str) -> DocumentRecord:
        self._workspace(workspace_id)
        with self._connect() as connection:
            row = connection.execute(
                """SELECT d.*,a.store_key,e.state AS extraction_state
                FROM document_versions d JOIN artifacts a ON a.organization_id=d.organization_id
                AND a.workspace_id=d.workspace_id AND a.id=d.artifact_id
                JOIN document_extractions e ON e.organization_id=d.organization_id
                AND e.workspace_id=d.workspace_id AND e.document_id=d.id
                WHERE d.organization_id=%s AND d.workspace_id=%s AND d.id=%s""",
                (self.organization_id, workspace_id, document_id),
            ).fetchone()
            if row is None:
                raise NotFound()
            fragments = connection.execute(
                "SELECT id,ordinal,kind,text,content_sha256,location FROM fragments WHERE organization_id=%s AND workspace_id=%s AND document_id=%s ORDER BY ordinal",
                (self.organization_id, workspace_id, document_id),
            ).fetchall()
        return DocumentRecord(
            id=row["id"],
            workspace_id=row["workspace_id"],
            filename=row["filename"],
            media_type=row["media_type"],
            content=self.artifacts.get(row["store_key"]),
            sha256=row["sha256"],
            created_at=wire_time(row["created_at"]),
            extraction_state=row["extraction_state"],
            fragments=[
                dict(item) | {"source_id": "source-main", "document_id": document_id} for item in fragments
            ],
        )

    def document_value(self, record: DocumentRecord) -> dict[str, Any]:
        return {
            "id": record.id,
            "workspace_id": record.workspace_id,
            "filename": record.filename,
            "media_type": record.media_type,
            "size_bytes": len(record.content),
            "sha256": record.sha256,
            "extraction_state": record.extraction_state,
            "created_by": self.actor,
            "created_at": record.created_at,
        }

    def list_documents(self, workspace_id: str, cursor: str | None, limit: int) -> dict[str, Any]:
        self._workspace(workspace_id)
        try:
            offset = 0 if cursor is None else int(base64.urlsafe_b64decode(cursor + "===").decode())
        except (ValueError, UnicodeDecodeError) as error:
            raise InvalidRequest("invalid_cursor", "Cursor is malformed or unknown.") from error
        with self._connect() as connection:
            ids = connection.execute(
                "SELECT id FROM document_versions WHERE organization_id=%s AND workspace_id=%s ORDER BY created_at DESC,id DESC OFFSET %s LIMIT %s",
                (self.organization_id, workspace_id, offset, limit + 1),
            ).fetchall()
        page = ids[:limit]
        next_cursor = None
        if len(ids) > limit:
            next_cursor = base64.urlsafe_b64encode(str(offset + limit).encode()).decode().rstrip("=")
        return {
            "items": [self.document_value(self.get_document(workspace_id, row["id"])) for row in page],
            "next_cursor": next_cursor,
        }

    @staticmethod
    def profile_value(profile: ProfileVersion, workspace_id: str) -> dict[str, Any]:
        return {
            "id": profile.id,
            "workspace_id": None if profile.scope == "system" else workspace_id,
            "scope": profile.scope,
            "version": profile.version,
            "digest": profile.digest,
            "name": profile.name,
            "role": profile.role,
            "goal": profile.goal,
            "checks": list(profile.checks),
            "supersedes": None
            if profile.supersedes is None
            else {"id": profile.supersedes[0], "version": profile.supersedes[1]},
            "created_at": "2026-09-05T00:00:00.000000Z",
        }

    @staticmethod
    def _profile(row: dict[str, Any]) -> ProfileVersion:
        supersedes = None
        if row["supersedes_version"] is not None:
            supersedes = (row["public_id"], row["supersedes_version"])
        return ProfileVersion(
            id=row["public_id"],
            version=row["version"],
            scope=row["scope"],
            digest=row["semantic_digest"],
            name=row["name"],
            role=row["role"],
            goal=row["goal"],
            checks=tuple(row["checks"]),
            supersedes=supersedes,
        )

    def list_profiles(self, workspace_id: str) -> dict[str, Any]:
        self._workspace(workspace_id)
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT f.public_id,f.scope,v.* FROM review_profile_families f
                JOIN review_profile_heads h ON h.family_row_id=f.row_id
                JOIN review_profile_versions v ON v.family_row_id=h.family_row_id AND v.version=h.head_version
                WHERE f.scope='system' OR (f.organization_id=%s AND f.workspace_id=%s)
                ORDER BY f.scope,f.public_id""",
                (self.organization_id, workspace_id),
            ).fetchall()
        return {"items": [self.profile_value(self._profile(row), workspace_id) for row in rows]}

    def create_profile(self, workspace_id: str, body: dict[str, Any]) -> dict[str, Any]:
        self._workspace(workspace_id)
        semantic = {key: body[key] for key in ("name", "role", "goal", "checks")}
        digest = digest_value(semantic)
        supersedes = body.get("supersedes")
        with self._connect() as connection:
            now = utc_now()
            if supersedes is None:
                family_row, public_id, version = str(uuid4()), str(uuid4()), "1.0.0"
                connection.execute(
                    """INSERT INTO review_profile_families(row_id,organization_id,workspace_id,deployment_id,
                    public_id,scope,created_at) VALUES(%s,%s,%s,NULL,%s,'workspace',%s)""",
                    (family_row, self.organization_id, workspace_id, public_id, now),
                )
                prior = None
            else:
                row = connection.execute(
                    """SELECT f.*,h.head_version FROM review_profile_families f
                    JOIN review_profile_heads h ON h.family_row_id=f.row_id
                    WHERE f.public_id=%s FOR UPDATE OF h""",
                    (supersedes["id"],),
                ).fetchone()
                if row is None:
                    raise NotFound()
                if row["scope"] == "system":
                    raise InvalidRequest("invalid_supersedes", "System profile is immutable.")
                if row["organization_id"] != self.organization_id or row["workspace_id"] != workspace_id:
                    raise NotFound()
                if row["head_version"] != supersedes["version"]:
                    raise Conflict("profile_version_conflict", "Profile head changed.")
                previous = connection.execute(
                    "SELECT semantic_digest FROM review_profile_versions WHERE family_row_id=%s AND version=%s",
                    (row["row_id"], row["head_version"]),
                ).fetchone()
                if previous and previous["semantic_digest"] == digest:
                    raise Conflict("profile_content_unchanged", "Profile content is unchanged.")
                family_row, public_id, prior = row["row_id"], row["public_id"], row["head_version"]
                major, minor, patch = (int(part) for part in prior.split("."))
                version = f"{major}.{minor}.{patch + 1}"
            connection.execute(
                """INSERT INTO review_profile_versions(family_row_id,version,semantic_digest,
                semantic_codec_id,name,role,goal,checks,supersedes_version,created_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    family_row,
                    version,
                    digest,
                    CODEC,
                    body["name"],
                    body["role"],
                    body["goal"],
                    Jsonb(body["checks"]),
                    prior,
                    now,
                ),
            )
            if supersedes is None:
                connection.execute(
                    "INSERT INTO review_profile_heads(family_row_id,head_version,revision) VALUES(%s,%s,0)",
                    (family_row, version),
                )
            else:
                connection.execute(
                    "UPDATE review_profile_heads SET head_version=%s,revision=revision+1 WHERE family_row_id=%s",
                    (version, family_row),
                )
        return self.profile_value(
            ProfileVersion(
                public_id,
                version,
                "workspace",
                digest,
                body["name"],
                body["role"],
                body["goal"],
                tuple(body["checks"]),
                None if prior is None else (public_id, prior),
            ),
            workspace_id,
        )

    def _snapshot(self, profile: ProfileVersion) -> dict[str, Any]:
        return {
            "profile": {"id": profile.id, "version": profile.version, "digest": profile.digest},
            "skill": {
                "id": self.settings.skill_id,
                "version": "1.0.0",
                "package_sha256": self.settings.skill_package_sha256,
            },
            "model_profile": {
                "id": self.settings.model_profile_id,
                "version": "1.0.0",
                "config_sha256": digest_value(
                    {"adapter_kind": "deterministic", "capabilities": ["text_generation"]}
                ),
            },
            "dialogue_policy": self.dialogue_policy,
            "engine_version": "1.0.0",
        }

    def snapshot_for_profile_reference(self, reference: dict[str, str]) -> dict[str, Any]:
        with self._connect() as connection:
            profile = self._exact_profile(connection, reference)
        return self._snapshot(profile)

    def _exact_profile(
        self, connection: psycopg.Connection[dict[str, Any]], reference: dict[str, str]
    ) -> ProfileVersion:
        row = connection.execute(
            """SELECT f.public_id,f.scope,v.* FROM review_profile_families f
            JOIN review_profile_versions v ON v.family_row_id=f.row_id
            WHERE f.public_id=%s AND v.version=%s AND (f.scope='system' OR
            (f.organization_id=%s AND f.workspace_id=%s))""",
            (reference["id"], reference["version"], self.organization_id, self.workspace_id),
        ).fetchone()
        if row is None:
            raise NotFound()
        return self._profile(row)

    def create_run(self, workspace_id: str, body: dict[str, Any], key: str) -> dict[str, Any]:
        self._workspace(workspace_id)
        require_idempotency_key(key)
        context_ids = body.get("context_document_ids", [])
        if len(context_ids) > 50:
            raise InvalidRequest("context_limit", "At most 50 context documents are accepted.")
        if len(context_ids) != len(set(context_ids)):
            raise InvalidRequest("duplicate_context", "Context document IDs must be unique.")
        primary = self.get_document(workspace_id, body["document_id"])
        contexts = [self.get_document(workspace_id, item) for item in context_ids]
        with self._connect() as connection:
            profile = self._exact_profile(connection, body["profile"])
        if body["model_profile"] != {
            "id": self.model_profile["id"],
            "version": self.model_profile["version"],
        }:
            raise NotFound()
        snapshot = self._snapshot(profile)
        run_id = str(uuid4())
        created = utc_now()
        run = {
            "id": run_id,
            "workspace_id": workspace_id,
            "state": "queued",
            "progress": {"percent": 0, "message": "Review queued"},
            "document_id": primary.id,
            "context_document_ids": [item.id for item in contexts],
            "execution_snapshot": snapshot,
            "created_by": self.actor,
            "created_at": wire_time(created),
            "started_at": None,
            "finished_at": None,
            "cancel_requested_at": None,
            "report_available": False,
            "error": None,
        }
        sources = tuple(
            {
                "source_id": "source-main" if ordinal == 1 else f"source-context-{ordinal - 1}",
                "document_id": document.id,
                "role": "document" if ordinal == 1 else "context",
                "ordinal": ordinal,
            }
            for ordinal, document in enumerate([primary, *contexts], start=1)
        )
        request = ReviewStorageRequest(
            workspace_id=workspace_id,
            idempotency_key=key,
            request_body=body,
            run_id=run_id,
            snapshot_id=str(uuid4()),
            snapshot=snapshot,
            run_value=run,
            sources=sources,
        )
        deadline_at = created + timedelta(seconds=300)
        admission = self.review_storage.admit(request, deadline_at)
        if admission.replay:
            return self.get_run(workspace_id, admission.resource_id).value
        claim = self.review_storage.claim(admission, str(uuid4()))
        if claim is None:
            raise RuntimeError("accepted review execution could not be claimed")
        prepared = {
            "prepared_input_digest": digest_value(
                {
                    "snapshot": snapshot,
                    "sources": [
                        {
                            "source_id": source["source_id"],
                            "document_id": document.id,
                            "sha256": document.sha256,
                        }
                        for source, document in zip(sources, [primary, *contexts], strict=True)
                    ],
                }
            ),
            "sources": {
                source["source_id"]: {
                    "document_id": document.id,
                    "sha256": document.sha256,
                    "role": source["role"],
                    "ordinal": source["ordinal"],
                }
                for source, document in zip(sources, [primary, *contexts], strict=True)
            },
            "work_item": {"source_ids": [source["source_id"] for source in sources]},
        }
        try:
            self.review_storage.save_prepared(claim, prepared)
            report = self.executor.execute(
                run_id=admission.resource_id,
                report_id=str(uuid4()),
                document=primary,
                context=contexts,
                snapshot=snapshot,
                created_at=wire_time(utc_now()),
            )
        except ValueError as error:
            self.review_storage.fail(
                claim,
                ExecutionFailure("extraction_failed", str(error), False),
            )
            return self.get_run(workspace_id, admission.resource_id).value
        try:
            self.report_validator.validate(report)
        except ValueError:
            self.review_storage.fail(
                claim,
                ExecutionFailure(
                    "validation_failed",
                    "Generated review report did not satisfy the canonical schema.",
                    False,
                ),
            )
            return self.get_run(workspace_id, admission.resource_id).value
        try:
            self.review_storage.publish(claim, report, deadline_at)
        except CommitOutcomeUnknown:
            terminal = self.review_storage.read_terminal(admission.resource_id)
            if terminal is None:
                raise
        return self.get_run(workspace_id, admission.resource_id).value

    def _legacy_create_run(self, workspace_id: str, body: dict[str, Any], key: str) -> dict[str, Any]:
        self._workspace(workspace_id)
        require_idempotency_key(key)
        context_ids = body.get("context_document_ids", [])
        if len(context_ids) > 50:
            raise InvalidRequest("context_limit", "At most 50 context documents are accepted.")
        if len(context_ids) != len(set(context_ids)):
            raise InvalidRequest("duplicate_context", "Context document IDs must be unique.")
        request_digest = digest_value(body)
        run_id, snapshot_id = (str(uuid4()) for _ in range(2))
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT request_digest,resource_id FROM idempotency_records WHERE organization_id=%s AND workspace_id=%s AND operation='create_run' AND key=%s FOR UPDATE",
                (self.organization_id, workspace_id, key),
            ).fetchone()
            if existing:
                if existing["request_digest"] != request_digest:
                    raise Conflict(
                        "idempotency_conflict", "The key was already used with a different request."
                    )
                return self.get_run(workspace_id, existing["resource_id"]).value
            primary = self.get_document(workspace_id, body["document_id"])
            contexts = [self.get_document(workspace_id, item) for item in context_ids]
            profile = self._exact_profile(connection, body["profile"])
            if body["model_profile"] != {"id": self.model_profile["id"], "version": "1.0.0"}:
                raise NotFound()
            snapshot = self._snapshot(profile)
            created = utc_now()
            run = {
                "id": run_id,
                "workspace_id": workspace_id,
                "state": "queued",
                "progress": {"percent": 0, "message": "Review queued"},
                "document_id": primary.id,
                "context_document_ids": [item.id for item in contexts],
                "execution_snapshot": snapshot,
                "created_by": self.actor,
                "created_at": wire_time(created),
                "started_at": None,
                "finished_at": None,
                "cancel_requested_at": None,
                "report_available": False,
                "error": None,
            }
            connection.execute(
                "INSERT INTO execution_snapshots(organization_id,workspace_id,id,digest,codec_id,value,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (organization_id,workspace_id,digest) DO NOTHING",
                (
                    self.organization_id,
                    workspace_id,
                    snapshot_id,
                    digest_value(snapshot),
                    CODEC,
                    Jsonb(snapshot),
                    created,
                ),
            )
            connection.execute(
                "INSERT INTO review_runs(organization_id,workspace_id,id,document_id,state,revision,snapshot,value,cancel_requested_at) VALUES(%s,%s,%s,%s,'queued',0,%s,%s,NULL)",
                (self.organization_id, workspace_id, run_id, primary.id, Jsonb(snapshot), Jsonb(run)),
            )
            for ordinal, document in enumerate([primary, *contexts], start=1):
                connection.execute(
                    "INSERT INTO review_run_sources(organization_id,workspace_id,run_id,source_id,document_id,role,ordinal,prepared) VALUES(%s,%s,%s,%s,%s,%s,%s,NULL)",
                    (
                        self.organization_id,
                        workspace_id,
                        run_id,
                        "source-main" if ordinal == 1 else f"source-context-{ordinal - 1}",
                        document.id,
                        "document" if ordinal == 1 else "context",
                        ordinal,
                    ),
                )
            connection.execute(
                "INSERT INTO idempotency_records(organization_id,workspace_id,operation,key,request_digest,codec_id,resource_kind,resource_id) VALUES(%s,%s,'create_run',%s,%s,%s,'review_run',%s)",
                (self.organization_id, workspace_id, key, request_digest, CODEC, run_id),
            )
        self.execute_review(run_id)
        return self.get_run(workspace_id, run_id).value

    def execute_review(self, run_id: str) -> None:
        now = utc_now()
        with self._connect() as connection:
            run_row = connection.execute(
                "SELECT * FROM review_runs WHERE organization_id=%s AND workspace_id=%s AND id=%s FOR UPDATE",
                (self.organization_id, self.workspace_id, run_id),
            ).fetchone()
            if run_row is None or run_row["state"] in {"completed", "failed", "cancelled"}:
                return
            run = run_row["value"]
            run.update(
                state="preparing",
                started_at=wire_time(now),
                progress={"percent": 20, "message": "Preparing sources"},
            )
            connection.execute(
                "UPDATE review_runs SET state='preparing',revision=revision+1,value=%s WHERE organization_id=%s AND workspace_id=%s AND id=%s",
                (Jsonb(run), self.organization_id, self.workspace_id, run_id),
            )
        with self._connect() as connection:
            source_rows = connection.execute(
                "SELECT document_id,role,ordinal FROM review_run_sources WHERE organization_id=%s AND workspace_id=%s AND run_id=%s ORDER BY ordinal",
                (self.organization_id, self.workspace_id, run_id),
            ).fetchall()
            run_row = connection.execute(
                "SELECT * FROM review_runs WHERE organization_id=%s AND workspace_id=%s AND id=%s",
                (self.organization_id, self.workspace_id, run_id),
            ).fetchone()
        assert run_row is not None
        documents = [self.get_document(self.workspace_id, item["document_id"]) for item in source_rows]
        report_id = str(uuid4())
        created = utc_now()
        try:
            report = self.executor.execute(
                run_id=run_id,
                report_id=report_id,
                document=documents[0],
                context=documents[1:],
                snapshot=run_row["snapshot"],
                created_at=wire_time(created),
            )
        except ValueError as error:
            with self._connect() as connection:
                run = run_row["value"] | {
                    "state": "failed",
                    "finished_at": wire_time(utc_now()),
                    "error": {"code": "extraction_failed", "message": str(error), "retryable": False},
                    "progress": {"percent": 35, "message": "Source preparation failed"},
                }
                connection.execute(
                    "UPDATE review_runs SET state='failed',value=%s,revision=revision+1 WHERE organization_id=%s AND workspace_id=%s AND id=%s",
                    (Jsonb(run), self.organization_id, self.workspace_id, run_id),
                )
            return
        try:
            self.report_validator.validate(report)
        except ValueError:
            with self._connect() as connection:
                run = run_row["value"] | {
                    "state": "failed",
                    "finished_at": wire_time(utc_now()),
                    "error": {
                        "code": "validation_failed",
                        "message": "Generated review report did not satisfy the canonical schema.",
                        "retryable": False,
                    },
                    "progress": {"percent": 95, "message": "Report validation failed"},
                }
                connection.execute(
                    "UPDATE review_runs SET state='failed',value=%s,revision=revision+1 WHERE organization_id=%s AND workspace_id=%s AND id=%s",
                    (Jsonb(run), self.organization_id, self.workspace_id, run_id),
                )
            return
        report_bytes = canonical_bytes(report)
        digest = hashlib.sha256(report_bytes).hexdigest()
        etag = strong_etag(report_bytes)
        staged = self.artifacts.stage(self.workspace_id, report_bytes, expected_sha256=digest)
        store_key = f"{staged.namespace}/{staged.object_name}"
        artifact_id = str(uuid4())
        fence = advisory_fence_key(self.workspace_id, store_key, digest)
        with self._connect() as connection:
            current = connection.execute(
                "SELECT state,cancel_requested_at,value,revision FROM review_runs WHERE organization_id=%s AND workspace_id=%s AND id=%s FOR UPDATE",
                (self.organization_id, self.workspace_id, run_id),
            ).fetchone()
            if (
                current is None
                or current["cancel_requested_at"] is not None
                or current["state"] in {"cancelled", "completed"}
            ):
                return
            connection.execute("SELECT pg_advisory_xact_lock(%s)", (fence,))
            promoted = self.artifacts.promote(staged)
            connection.execute(
                "INSERT INTO artifacts(organization_id,workspace_id,id,kind,store_key,sha256,size_bytes,media_type,canonical_codec_id,created_at) VALUES(%s,%s,%s,'report_canonical',%s,%s,%s,'application/json',%s,%s)",
                (
                    self.organization_id,
                    self.workspace_id,
                    artifact_id,
                    promoted,
                    digest,
                    len(report_bytes),
                    CODEC,
                    created,
                ),
            )
            connection.execute(
                "INSERT INTO review_reports(organization_id,workspace_id,id,run_id,artifact_id,canonical_sha256,etag,codec_id,graph,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    self.organization_id,
                    self.workspace_id,
                    report_id,
                    run_id,
                    artifact_id,
                    digest,
                    etag,
                    CODEC,
                    Jsonb(report),
                    created,
                ),
            )
            connection.execute(
                "INSERT INTO report_coverage(organization_id,workspace_id,report_id,value) VALUES(%s,%s,%s,%s)",
                (self.organization_id, self.workspace_id, report_id, Jsonb(report["coverage"])),
            )
            connection.execute(
                "INSERT INTO report_provenance(organization_id,workspace_id,report_id,value) VALUES(%s,%s,%s,%s)",
                (self.organization_id, self.workspace_id, report_id, Jsonb(report["provenance"])),
            )
            for finding in report["findings"]:
                connection.execute(
                    "INSERT INTO findings(organization_id,workspace_id,report_id,id,ordinal,value) VALUES(%s,%s,%s,%s,%s,%s)",
                    (
                        self.organization_id,
                        self.workspace_id,
                        report_id,
                        finding["id"],
                        finding["ordinal"],
                        Jsonb(finding),
                    ),
                )
                for ordinal, anchor in enumerate(finding["anchors"], start=1):
                    connection.execute(
                        "INSERT INTO finding_anchors(organization_id,workspace_id,finding_id,ordinal,value) VALUES(%s,%s,%s,%s,%s)",
                        (self.organization_id, self.workspace_id, finding["id"], ordinal, Jsonb(anchor)),
                    )
                decision = {
                    "status": "unreviewed",
                    "revision": 0,
                    "actor": None,
                    "reason": None,
                    "resolution": None,
                    "decided_at": None,
                }
                dialogue_id = str(uuid4())
                dialogue = {
                    "id": dialogue_id,
                    "run_id": run_id,
                    "finding_id": finding["id"],
                    "revision": 0,
                    "state": "open",
                    "turn_count": 0,
                    "can_send_message": True,
                    "blocked_reason": None,
                    "policy": self.dialogue_policy,
                    "turns": [],
                }
                connection.execute(
                    "INSERT INTO finding_states(organization_id,workspace_id,finding_id,decision_revision,value) VALUES(%s,%s,%s,0,%s)",
                    (self.organization_id, self.workspace_id, finding["id"], Jsonb(decision)),
                )
                connection.execute(
                    "INSERT INTO finding_dialogues(organization_id,workspace_id,id,finding_id,revision,value) VALUES(%s,%s,%s,%s,0,%s)",
                    (self.organization_id, self.workspace_id, dialogue_id, finding["id"], Jsonb(dialogue)),
                )
            completed = current["value"] | {
                "state": "completed",
                "progress": {"percent": 100, "message": "Review completed"},
                "finished_at": wire_time(utc_now()),
                "report_available": True,
            }
            connection.execute(
                "UPDATE review_runs SET state='completed',value=%s,revision=revision+1 WHERE organization_id=%s AND workspace_id=%s AND id=%s AND revision=%s AND cancel_requested_at IS NULL",
                (
                    Jsonb(completed),
                    self.organization_id,
                    self.workspace_id,
                    run_id,
                    current["revision"],
                ),
            )

    def get_run(self, workspace_id: str, run_id: str) -> RunRecord:
        self._workspace(workspace_id)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM review_runs WHERE organization_id=%s AND workspace_id=%s AND id=%s",
                (self.organization_id, workspace_id, run_id),
            ).fetchone()
        if row is None:
            raise NotFound()
        return RunRecord(row["value"])

    def list_runs(self, workspace_id: str, cursor: str | None, limit: int) -> dict[str, Any]:
        self._workspace(workspace_id)
        if cursor is not None:
            raise InvalidRequest("invalid_cursor", "Cursor is malformed or unknown.")
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT value FROM review_runs WHERE organization_id=%s AND workspace_id=%s ORDER BY id DESC LIMIT %s",
                (self.organization_id, workspace_id, limit),
            ).fetchall()
        return {"items": [row["value"] for row in rows], "next_cursor": None}

    def cancel_run(self, workspace_id: str, run_id: str) -> dict[str, Any]:
        self._workspace(workspace_id)
        connection = self._connect()
        try:
            row = connection.execute(
                """SELECT state, value FROM review_runs
                   WHERE organization_id=%s AND workspace_id=%s AND id=%s
                   FOR UPDATE""",
                (self.organization_id, workspace_id, run_id),
            ).fetchone()
            if row is None:
                raise NotFound()
            if row["state"] in {"completed", "failed", "cancelled"}:
                raise Conflict("run_terminal", "A terminal review run cannot be cancelled.")
            cancelled_at = utc_now()
            cancelled = row["value"] | {
                "state": "cancelled",
                "cancel_requested_at": wire_time(cancelled_at),
                "finished_at": wire_time(cancelled_at),
                "report_available": False,
            }
            connection.execute(
                """WITH execution_terminal AS (
                     UPDATE review_run_executions e
                     SET state='cancelled', checkpoint='cancelled', revision=e.revision+1,
                         value=e.value::jsonb || %s::jsonb
                     WHERE e.organization_id=%s AND e.workspace_id=%s AND e.run_id=%s
                       AND e.state IN ('accepted','running')
                     RETURNING e.run_id
                   )
                   UPDATE review_runs r
                   SET state='cancelled', cancel_requested_at=%s, value=%s, revision=r.revision+1
                   WHERE r.organization_id=%s AND r.workspace_id=%s AND r.id=%s
                     AND r.state NOT IN ('completed','failed','cancelled')""",
                (
                    Jsonb({"finished_at": wire_time(cancelled_at), "error": None}),
                    self.organization_id,
                    workspace_id,
                    run_id,
                    cancelled_at,
                    Jsonb(cancelled),
                    self.organization_id,
                    workspace_id,
                    run_id,
                ),
            )
            connection.commit()
            return cancelled
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def report(self, workspace_id: str, run_id: str) -> tuple[bytes, str]:
        self._workspace(workspace_id)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT r.etag,a.store_key FROM review_reports r JOIN artifacts a ON a.organization_id=r.organization_id AND a.workspace_id=r.workspace_id AND a.id=r.artifact_id WHERE r.organization_id=%s AND r.workspace_id=%s AND r.run_id=%s",
                (self.organization_id, workspace_id, run_id),
            ).fetchone()
        if row is None:
            raise Conflict("report_unavailable", "The review report is not published.")
        return self.artifacts.get(row["store_key"]), row["etag"]

    def _dialogue(self, workspace_id: str, run_id: str, finding_id: str) -> dict[str, Any]:
        self.get_run(workspace_id, run_id)
        with self._connect() as connection:
            row = connection.execute(
                """SELECT d.value FROM finding_dialogues d JOIN findings f ON f.organization_id=d.organization_id AND f.workspace_id=d.workspace_id AND f.id=d.finding_id JOIN review_reports r ON r.organization_id=f.organization_id AND r.workspace_id=f.workspace_id AND r.id=f.report_id WHERE d.organization_id=%s AND d.workspace_id=%s AND d.finding_id=%s AND r.run_id=%s""",
                (self.organization_id, workspace_id, finding_id, run_id),
            ).fetchone()
        if row is None:
            raise NotFound()
        return cast(dict[str, Any], row["value"])

    def states(self, workspace_id: str, run_id: str) -> dict[str, Any]:
        self.get_run(workspace_id, run_id)
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT s.finding_id,s.value AS decision,d.value AS dialogue FROM finding_states s JOIN findings f ON f.organization_id=s.organization_id AND f.workspace_id=s.workspace_id AND f.id=s.finding_id JOIN review_reports r ON r.organization_id=f.organization_id AND r.workspace_id=f.workspace_id AND r.id=f.report_id JOIN finding_dialogues d ON d.organization_id=s.organization_id AND d.workspace_id=s.workspace_id AND d.finding_id=s.finding_id WHERE s.organization_id=%s AND s.workspace_id=%s AND r.run_id=%s ORDER BY f.ordinal""",
                (self.organization_id, workspace_id, run_id),
            ).fetchall()
        return {
            "items": [
                {
                    "finding_id": row["finding_id"],
                    "decision": row["decision"],
                    "dialogue": self._dialogue_summary(row["dialogue"]),
                }
                for row in rows
            ]
        }

    @staticmethod
    def _dialogue_summary(dialogue: dict[str, Any]) -> dict[str, Any]:
        return {
            "dialogue_id": dialogue["id"],
            "revision": dialogue["revision"],
            "state": dialogue["state"],
            "turn_count": dialogue["turn_count"],
            "can_send_message": dialogue["can_send_message"],
            "blocked_reason": dialogue["blocked_reason"],
            "policy": dialogue["policy"],
        }

    def get_dialogue(self, workspace_id: str, run_id: str, finding_id: str) -> dict[str, Any]:
        return self._dialogue(workspace_id, run_id, finding_id)

    def create_dialogue_turn(
        self, workspace_id: str, run_id: str, finding_id: str, body: dict[str, Any], key: str
    ) -> dict[str, Any]:
        require_idempotency_key(key)
        dialogue = self._dialogue(workspace_id, run_id, finding_id)
        digest = digest_value(body)
        turn_id = str(uuid4())
        now = utc_now()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT request_digest,resource_id FROM idempotency_records WHERE organization_id=%s AND workspace_id=%s AND operation=%s AND key=%s FOR UPDATE",
                (self.organization_id, workspace_id, f"dialogue:{dialogue['id']}", key),
            ).fetchone()
            if existing:
                if existing["request_digest"] != digest:
                    raise Conflict(
                        "idempotency_conflict", "The key was already used with a different request."
                    )
                return self._dialogue(workspace_id, run_id, finding_id)
            row = connection.execute(
                "SELECT revision,value FROM finding_dialogues WHERE organization_id=%s AND workspace_id=%s AND id=%s FOR UPDATE",
                (self.organization_id, workspace_id, dialogue["id"]),
            ).fetchone()
            assert row is not None
            if row["revision"] != body["expected_revision"]:
                raise Conflict("revision_conflict", "Dialogue revision changed.")
            if not row["value"]["can_send_message"]:
                raise Conflict("dialogue_blocked", "Dialogue cannot accept a new turn.")
            message = body.get("message")
            if not isinstance(message, str) or not message.strip() or len(message) > 8000:
                raise InvalidRequest(
                    "invalid_message", "Dialogue message must be non-empty and at most 8000 characters."
                )
            turn = {
                "id": turn_id,
                "ordinal": len(dialogue["turns"]) + 1,
                "state": "generating",
                "actor": self.actor,
                "member_message": message,
                "created_at": wire_time(now),
                "assistant_response": None,
                "error": None,
                "finished_at": None,
            }
            updated = row["value"]
            updated["turns"].append(turn)
            updated.update(
                revision=row["revision"] + 1,
                state="generating",
                turn_count=len(updated["turns"]),
                can_send_message=False,
                blocked_reason="generation_in_progress",
            )
            connection.execute(
                "UPDATE finding_dialogues SET revision=revision+1,value=%s WHERE organization_id=%s AND workspace_id=%s AND id=%s AND revision=%s",
                (Jsonb(updated), self.organization_id, workspace_id, dialogue["id"], row["revision"]),
            )
            connection.execute(
                "INSERT INTO dialogue_turns(organization_id,workspace_id,id,dialogue_id,ordinal,state,value) VALUES(%s,%s,%s,%s,%s,'generating',%s)",
                (self.organization_id, workspace_id, turn_id, dialogue["id"], turn["ordinal"], Jsonb(turn)),
            )
            connection.execute(
                "INSERT INTO idempotency_records(organization_id,workspace_id,operation,key,request_digest,codec_id,resource_kind,resource_id) VALUES(%s,%s,%s,%s,%s,%s,'dialogue_turn',%s)",
                (
                    self.organization_id,
                    workspace_id,
                    f"dialogue:{dialogue['id']}",
                    key,
                    digest,
                    CODEC,
                    turn_id,
                ),
            )
        self.execute_dialogue(turn_id, run_id, finding_id)
        return self._dialogue(workspace_id, run_id, finding_id)

    def execute_dialogue(self, turn_id: str, run_id: str, finding_id: str) -> None:
        with self._connect() as connection:
            turn = connection.execute(
                "SELECT * FROM dialogue_turns WHERE organization_id=%s AND workspace_id=%s AND id=%s FOR UPDATE",
                (self.organization_id, self.workspace_id, turn_id),
            ).fetchone()
            finding = connection.execute(
                "SELECT f.value,r.graph->'provenance'->'execution_snapshot' AS snapshot FROM findings f JOIN review_reports r ON r.organization_id=f.organization_id AND r.workspace_id=f.workspace_id AND r.id=f.report_id WHERE f.organization_id=%s AND f.workspace_id=%s AND f.id=%s AND r.run_id=%s",
                (self.organization_id, self.workspace_id, finding_id, run_id),
            ).fetchone()
            assert turn is not None
            assert finding is not None
            response = deterministic_dialogue_response(finding["snapshot"], finding["value"]["anchors"])
            turn_value = turn["value"] | {
                "state": "completed",
                "assistant_response": response,
                "finished_at": wire_time(utc_now()),
            }
            connection.execute(
                "UPDATE dialogue_turns SET state='completed',value=%s WHERE organization_id=%s AND workspace_id=%s AND id=%s",
                (Jsonb(turn_value), self.organization_id, self.workspace_id, turn["id"]),
            )
            dialogue = connection.execute(
                "SELECT revision,value FROM finding_dialogues WHERE organization_id=%s AND workspace_id=%s AND id=%s FOR UPDATE",
                (self.organization_id, self.workspace_id, turn["dialogue_id"]),
            ).fetchone()
            assert dialogue is not None
            value = dialogue["value"]
            value["turns"][-1] = turn_value
            value.update(
                revision=dialogue["revision"] + 1, state="open", can_send_message=True, blocked_reason=None
            )
            connection.execute(
                "UPDATE finding_dialogues SET revision=revision+1,value=%s WHERE organization_id=%s AND workspace_id=%s AND id=%s",
                (Jsonb(value), self.organization_id, self.workspace_id, turn["dialogue_id"]),
            )

    def retry_dialogue_turn(
        self, workspace_id: str, run_id: str, finding_id: str, turn_id: str, body: dict[str, Any], key: str
    ) -> dict[str, Any]:
        require_idempotency_key(key)
        dialogue = self._dialogue(workspace_id, run_id, finding_id)
        turn = next((item for item in dialogue["turns"] if item["id"] == turn_id), None)
        if turn is None:
            raise NotFound()
        if turn["state"] != "failed":
            raise Conflict("turn_not_retryable", "Only failed turns can be retried.")
        return self.create_dialogue_turn(
            workspace_id,
            run_id,
            finding_id,
            {"message": turn["member_message"], "expected_revision": body["expected_revision"]},
            f"retry:{key}",
        )

    def put_decision(
        self, workspace_id: str, run_id: str, finding_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        dialogue = self._dialogue(workspace_id, run_id, finding_id)
        with self._connect() as connection:
            state = connection.execute(
                "SELECT decision_revision,value FROM finding_states WHERE organization_id=%s AND workspace_id=%s AND finding_id=%s FOR UPDATE",
                (self.organization_id, workspace_id, finding_id),
            ).fetchone()
            assert state is not None
            try:
                decision = next_decision(
                    state["value"], body, actor=self.actor, decided_at=wire_time(utc_now())
                )
            except ValueError as error:
                if "stale" in str(error):
                    raise Conflict("revision_conflict", str(error)) from error
                raise InvalidRequest("invalid_decision", str(error)) from error
            connection.execute(
                "UPDATE finding_states SET decision_revision=%s,value=%s WHERE organization_id=%s AND workspace_id=%s AND finding_id=%s AND decision_revision=%s",
                (
                    decision["revision"],
                    Jsonb(decision),
                    self.organization_id,
                    workspace_id,
                    finding_id,
                    state["decision_revision"],
                ),
            )
            dvalue = dialogue
            dvalue.update(
                revision=dialogue["revision"] + 1,
                state="open" if decision["status"] == "unreviewed" else "closed",
                can_send_message=decision["status"] == "unreviewed",
                blocked_reason=None if decision["status"] == "unreviewed" else "human_decision_recorded",
            )
            connection.execute(
                "UPDATE finding_dialogues SET revision=revision+1,value=%s WHERE organization_id=%s AND workspace_id=%s AND id=%s",
                (Jsonb(dvalue), self.organization_id, workspace_id, dialogue["id"]),
            )
            connection.execute(
                "INSERT INTO human_decisions(organization_id,workspace_id,finding_id,revision,value) VALUES(%s,%s,%s,%s,%s)",
                (self.organization_id, workspace_id, finding_id, decision["revision"], Jsonb(decision)),
            )
        return decision
