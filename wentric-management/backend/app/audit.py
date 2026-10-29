from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import AuditLog, SecurityEvent

async def audit(db: AsyncSession, actor: int | None, action: str, kind: str, ident=None, details: dict | None=None, request: Request | None=None):
    ip = request.client.host if request and request.client else None
    db.add(AuditLog(actor_id=actor, action=action, entity_type=kind, entity_id=str(ident) if ident is not None else None, details=details or {}, ip_address=ip))

async def security_event(db: AsyncSession, telegram_id: int | None, kind: str, severity='info', details=None):
    db.add(SecurityEvent(telegram_id=telegram_id, event_type=kind, severity=severity, details=details or {}))
