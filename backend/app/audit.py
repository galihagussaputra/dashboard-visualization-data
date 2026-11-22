from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditEvent


def request_context(request: Request | None) -> dict[str, Any]:
    if request is None:
        return {}
    context: dict[str, Any] = {
        "path": request.url.path,
        "method": request.method,
    }
    if request.client is not None:
        context["client_host"] = request.client.host
    user_agent = request.headers.get("user-agent")
    if user_agent:
        context["user_agent"] = user_agent[:200]
    return context


def record_audit(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: str,
    actor_id: int | None = None,
    before_state: dict | None = None,
    after_state: dict | None = None,
    reason: str | None = None,
    context: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_state=before_state,
        after_state=after_state,
        reason=reason,
        request_context=context or {},
    )
    db.add(event)
    db.flush()
    return event
