from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_db
from app.models import Employee, UserSession
from app.security import decode_token

async def current_employee(request: Request, db: AsyncSession=Depends(get_db)) -> Employee:
    token = request.cookies.get('wentric_session')
    if not token and request.headers.get('Authorization', '').lower().startswith('bearer '):
        token = request.headers['Authorization'][7:].strip()
    if not token:
        raise HTTPException(401, 'Avval Telegram orqali tizimga kiring')
    try:
        claims = decode_token(token)
        sid = claims['sid']
        eid = int(claims['sub'])
    except Exception:
        raise HTTPException(401, 'Sessiya yaroqsiz, qayta kiring')
    session = await db.get(UserSession, sid)
    now = datetime.now(timezone.utc)
    if not session or session.revoked_at or session.employee_id != eid:
        raise HTTPException(401, 'Sessiya bekor qilingan')
    exp = session.expires_at if session.expires_at.tzinfo else session.expires_at.replace(tzinfo=timezone.utc)
    if exp <= now:
        session.revoked_at = now
        await db.commit()
        raise HTTPException(401, '30 daqiqa faolsizlikdan so‘ng sessiya tugadi')
    employee = await db.get(Employee, eid)
    if not employee or employee.status != 'active':
        session.revoked_at = now
        await db.commit()
        raise HTTPException(403, 'Xodim hisobi faol emas')
    session.last_activity_at = now
    session.expires_at = now + timedelta(minutes=settings.session_idle_minutes)
    await db.commit()
    return employee
