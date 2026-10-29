from datetime import datetime, timedelta, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_db
from app.deps import current_employee
from app.models import Employee, Role, UserSession
from app.schemas import TelegramLogin
from app.security import create_token, verify_telegram
from app.audit import audit, security_event
router = APIRouter(prefix='/auth', tags=['Autentifikatsiya'])

@router.post('/telegram')
async def login(payload: TelegramLogin, request: Request, response: Response, db: AsyncSession=Depends(get_db)):
    ok, reason = verify_telegram(payload.model_dump(exclude_none=True))
    if not ok:
        await security_event(db, payload.id, 'telegram_login_failed', 'warning', {'reason': reason})
        await db.commit()
        raise HTTPException(401, reason)
    e = await db.scalar(select(Employee).where(Employee.telegram_id == payload.id))
    if e is None and payload.id in settings.super_admin_ids:
        full = ' '.join((x for x in [payload.first_name, payload.last_name] if x)) or f'Super Admin {payload.id}'
        e = Employee(telegram_id=payload.id, full_name=full, status='active', department='Boshqaruv', position='Super Admin')
        role = await db.scalar(select(Role).where(Role.code == 'SUPER_ADMIN'))
        if role:
            e.roles.append(role)
        db.add(e)
        await db.flush()
        await audit(db, e.id, 'super_admin_bootstrap', 'employee', e.id, {'telegram_id': payload.id}, request)
    if not e or e.status != 'active':
        await security_event(db, payload.id, 'telegram_login_not_authorized', 'warning', {})
        await db.commit()
        raise HTTPException(403, 'Hisob topilmadi yoki hali tasdiqlanmagan. Bot orqali xodimlik arizasi yuboring.')
    if not settings.jwt_is_configured:
        raise HTTPException(503, '.env ichida JWT_SECRET ni kamida 32 ta tasodifiy belgi qilib sozlang')
    sid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db.add(UserSession(id=sid, employee_id=e.id, created_at=now, last_activity_at=now, expires_at=now + timedelta(minutes=settings.session_idle_minutes), user_agent=request.headers.get('user-agent', '')[:500]))
    await audit(db, e.id, 'login_success', 'session', sid, {}, request)
    await db.commit()
    response.set_cookie('wentric_session', create_token(sid, e.id), httponly=True, secure=False, samesite='lax', max_age=7 * 86400, path='/')
    return {'ok': True, 'employee': {'id': e.id, 'full_name': e.full_name, 'telegram_id': e.telegram_id, 'department': e.department, 'position': e.position, 'roles': e.role_codes}, 'session_idle_minutes': settings.session_idle_minutes}

@router.get('/me')
async def me(e: Employee=Depends(current_employee)):
    return {'id': e.id, 'full_name': e.full_name, 'telegram_id': e.telegram_id, 'department': e.department, 'position': e.position, 'status': e.status, 'roles': e.role_codes}

@router.post('/logout')
async def logout(request: Request, response: Response, db: AsyncSession=Depends(get_db)):
    token = request.cookies.get('wentric_session')
    if token:
        try:
            from app.security import decode_token
            claims = decode_token(token)
            s = await db.get(UserSession, claims.get('sid'))
            if s:
                s.revoked_at = datetime.now(timezone.utc)
                await db.commit()
        except Exception:
            pass
    response.delete_cookie('wentric_session', path='/')
    return {'ok': True}
