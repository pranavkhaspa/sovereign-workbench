"""Append-only audit log backed by SQLite.

Every meaningful action (tool call, model selection, artifact creation, egress
decision) is recorded so the trajectory of a task — and the sovereignty claim —
can be inspected after the fact.
"""

from __future__ import annotations

import json
from typing import Any

from sovereign_workbench.db.models import AuditEventRow
from sovereign_workbench.db.session import session_scope
from sovereign_workbench.observability.logging import get_logger

log = get_logger(__name__)


class AuditLog:
    def record(
        self,
        event_type: str,
        *,
        actor: str = "system",
        detail: str = "",
        data: dict[str, Any] | None = None,
    ) -> None:
        try:
            with session_scope() as session:
                session.add(
                    AuditEventRow(
                        type=event_type,
                        actor=actor,
                        detail=detail,
                        data=json.dumps(data) if data else None,
                    )
                )
        except Exception:  # auditing must never break the request
            log.exception("failed to write audit event", extra={"extra_fields": {"type": event_type}})

    def recent(self, *, limit: int = 200, event_type: str | None = None) -> list[dict[str, Any]]:
        from sqlalchemy import desc, select

        with session_scope() as session:
            stmt = select(AuditEventRow).order_by(desc(AuditEventRow.created_at)).limit(limit)
            if event_type:
                stmt = stmt.where(AuditEventRow.type == event_type)
            rows = session.execute(stmt).scalars().all()
            return [
                {
                    "id": row.id,
                    "type": row.type,
                    "actor": row.actor,
                    "detail": row.detail,
                    "data": json.loads(row.data) if row.data else None,
                    "created_at": row.created_at,
                }
                for row in rows
            ]


_log: AuditLog | None = None


def get_audit_log() -> AuditLog:
    global _log
    if _log is None:
        _log = AuditLog()
    return _log
