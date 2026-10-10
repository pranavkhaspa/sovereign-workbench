from __future__ import annotations

from fastapi import APIRouter

from sovereign_workbench.core.security.airgap import get_egress_guard
from sovereign_workbench.core.security.audit import get_audit_log
from sovereign_workbench.schemas.audit import AuditEvent, EgressStatus

router = APIRouter(tags=["audit"])


@router.get("/audit", response_model=list[AuditEvent])
async def list_audit(
    limit: int = 200,
    type: str | None = None,
) -> list[AuditEvent]:
    events = get_audit_log().recent(limit=min(max(limit, 1), 1000), event_type=type)
    return [AuditEvent(**event) for event in events]


@router.get("/audit/egress", response_model=EgressStatus)
async def audit_egress() -> EgressStatus:
    return EgressStatus(**get_egress_guard().status())  # type: ignore[arg-type]
