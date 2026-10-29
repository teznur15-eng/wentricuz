from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_db
from app.security import decrypt_secret
from app.models import Employee, Task, AttendanceRecord, Notification, Announcement, Suggestion, EmployeeCard, AuditLog
router = APIRouter(prefix='/integrations/bot', tags=['Telegram bot integratsiyasi'])

class Identity(BaseModel):
    telegram_id: int

class StartWork(Identity):
    mode: str = Field(default='remote', pattern='^(office|remote)$')

class SuggestionInput(Identity):
    title: str = Field(min_length=2, max_length=240)
    body: str = Field(min_length=2)
    kind: str = Field(default='suggestion', pattern='^(suggestion|problem)$')

def check_secret(value: str | None):
    if not settings.bot_api_secret or not value or value != settings.bot_api_secret:
        raise HTTPException(403, 'Bot integratsiyasiga ruxsat yo‘q')

async def find_employee(telegram_id: int, db: AsyncSession):
    e = await db.scalar(select(Employee).where(Employee.telegram_id == telegram_id, Employee.status == 'active'))
    if not e:
        raise HTTPException(403, 'Tasdiqlangan faol xodim hisobi topilmadi')
    return e

@router.post('/cards')
async def employee_cards(p: Identity, x_bot_secret: str | None=Header(default=None), db: AsyncSession=Depends(get_db)):
    check_secret(x_bot_secret)
    e = await find_employee(p.telegram_id, db)
    rows = (await db.scalars(select(EmployeeCard).where(EmployeeCard.employee_id == e.id).order_by(EmployeeCard.id.desc()))).all()
    return [{
        'card_number': c.card_number,
        'status': c.status,
        'created_at': c.created_at,
        'employee_name': e.full_name,
        'department': e.department,
        'position': e.position,
        'roles': e.role_codes,
        'qr_token': decrypt_secret(c.qr_token_encrypted) if c.status == 'active' and c.qr_token_encrypted else None,
    } for c in rows]

@router.post('/cards/block-request')
async def card_block_request(p: Identity, x_bot_secret: str | None=Header(default=None), db: AsyncSession=Depends(get_db)):
    check_secret(x_bot_secret)
    e = await find_employee(p.telegram_id, db)
    cards = (await db.scalars(select(EmployeeCard).where(EmployeeCard.employee_id == e.id, EmployeeCard.status.in_(['active', 'pending'])))).all()
    if not cards:
        raise HTTPException(404, 'Bloklanadigan faol karta topilmadi')
    now = datetime.now(timezone.utc)
    for card in cards:
        card.status = 'blocked'
        card.blocked_at = now
    db.add(AuditLog(actor_id=e.id, action='employee_requested_card_block', entity_type='employee_card', entity_id=','.join((str(x.id) for x in cards)), details={'employee_id': e.id}, ip_address=None))
    admins = (await db.scalars(select(Employee).where(Employee.status == 'active'))).all()
    for admin in admins:
        if set(admin.role_codes) & {'SUPER_ADMIN', 'CEO'}:
            db.add(Notification(employee_id=admin.id, title='Wentric Card bloklandi', body=f'{e.full_name} o‘z kartasini bloklashni so‘radi.', kind='security'))
    await db.commit()
    return {'ok': True, 'status': 'blocked', 'cards_blocked': len(cards)}

@router.post('/profile')
async def profile(p: Identity, x_bot_secret: str | None=Header(default=None), db: AsyncSession=Depends(get_db)):
    check_secret(x_bot_secret)
    e = await find_employee(p.telegram_id, db)
    return {'id': e.id, 'full_name': e.full_name, 'department': e.department, 'position': e.position, 'status': e.status, 'roles': e.role_codes}

@router.post('/tasks')
async def tasks(p: Identity, x_bot_secret: str | None=Header(default=None), db: AsyncSession=Depends(get_db)):
    check_secret(x_bot_secret)
    e = await find_employee(p.telegram_id, db)
    rows = (await db.scalars(select(Task).where(Task.assignee_id == e.id).order_by(Task.id.desc()).limit(20))).all()
    return [{'id': x.id, 'title': x.title, 'status': x.status, 'deadline': x.deadline, 'priority': x.priority} for x in rows]

@router.post('/attendance/start')
async def attendance_start(p: StartWork, x_bot_secret: str | None=Header(default=None), db: AsyncSession=Depends(get_db)):
    check_secret(x_bot_secret)
    e = await find_employee(p.telegram_id, db)
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    x = await db.scalar(select(AttendanceRecord).where(AttendanceRecord.employee_id == e.id, AttendanceRecord.work_date == today, AttendanceRecord.finished_at.is_(None)))
    if x and x.started_at:
        raise HTTPException(409, 'Bugungi ish vaqti allaqachon boshlangan')
    if not x:
        x = AttendanceRecord(employee_id=e.id, work_date=today, mode=p.mode, source='telegram')
        db.add(x)
    x.started_at = now
    x.mode = p.mode
    await db.commit()
    return {'ok': True, 'started_at': x.started_at, 'mode': x.mode}

@router.post('/attendance/finish')
async def attendance_finish(p: Identity, x_bot_secret: str | None=Header(default=None), db: AsyncSession=Depends(get_db)):
    check_secret(x_bot_secret)
    e = await find_employee(p.telegram_id, db)
    today = datetime.now(timezone.utc).date().isoformat()
    x = await db.scalar(select(AttendanceRecord).where(AttendanceRecord.employee_id == e.id, AttendanceRecord.work_date == today, AttendanceRecord.finished_at.is_(None)))
    if not x or not x.started_at:
        raise HTTPException(400, 'Avval ishni boshlang')
    x.finished_at = datetime.now(timezone.utc)
    await db.commit()
    return {'ok': True, 'finished_at': x.finished_at}

@router.post('/notifications')
async def notifications(p: Identity, x_bot_secret: str | None=Header(default=None), db: AsyncSession=Depends(get_db)):
    check_secret(x_bot_secret)
    e = await find_employee(p.telegram_id, db)
    rows = (await db.scalars(select(Notification).where(Notification.employee_id == e.id).order_by(Notification.created_at.desc()).limit(10))).all()
    return [{'title': x.title, 'body': x.body, 'kind': x.kind, 'created_at': x.created_at} for x in rows]

@router.post('/announcements')
async def announcements(p: Identity, x_bot_secret: str | None=Header(default=None), db: AsyncSession=Depends(get_db)):
    check_secret(x_bot_secret)
    e = await find_employee(p.telegram_id, db)
    rows = (await db.scalars(select(Announcement).order_by(Announcement.created_at.desc()).limit(10))).all()
    return [{'title': x.title, 'body': x.body, 'created_at': x.created_at} for x in rows if x.audience == 'all' or x.audience in e.role_codes or x.audience == e.department]

@router.post('/suggestions')
async def send_suggestion(p: SuggestionInput, x_bot_secret: str | None=Header(default=None), db: AsyncSession=Depends(get_db)):
    check_secret(x_bot_secret)
    e = await find_employee(p.telegram_id, db)
    x = Suggestion(employee_id=e.id, title=p.title, body=p.body, kind=p.kind)
    db.add(x)
    await db.commit()
    return {'ok': True, 'id': x.id}
