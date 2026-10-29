from datetime import datetime, timezone
import secrets, base64
from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.config import settings
from app.deps import current_employee
from app.models import Employee, Role, EmployeeApplication, InviteCode, UserSession, EmployeeCard, FinancialTransaction, Task, Project, Notification
from app.schemas import EmployeeCreate, StatusUpdate, AppDecision, FinanceCreate, FinanceDecision, CardIssue, CardDecision, CardVerify, InviteCreate, RoleUpdate
from app.rbac import ensure_roles, ensure_finance, ensure_confirmed
from app.audit import audit
from app.security import opaque_token, digest, encrypt_secret
router = APIRouter(tags=['Boshqaruv, moliya va karta'])

@router.post('/employees')
async def add_employee(p: EmployeeCreate, request: Request, e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_roles(e, {'SUPER_ADMIN', 'CEO', 'COO'})
    ensure_confirmed(request)
    if p.telegram_id and await db.scalar(select(Employee).where(Employee.telegram_id == p.telegram_id)):
        raise HTTPException(409, 'Telegram ID allaqachon mavjud')
    x = Employee(full_name=p.full_name, telegram_id=p.telegram_id, department=p.department, position=p.position, phone=p.phone, email=p.email, status='active')
    for code in p.role_codes:
        r = await db.scalar(select(Role).where(Role.code == code))
        if not r:
            raise HTTPException(400, f'Noma’lum rol: {code}')
        if code in {'SUPER_ADMIN', 'CEO', 'CTO', 'COO'} and 'SUPER_ADMIN' not in e.role_codes:
            raise HTTPException(403, 'Rahbar va Super Admin rollarini faqat Super Admin beradi')
        x.roles.append(r)
    db.add(x)
    await db.flush()
    await audit(db, e.id, 'employee_created', 'employee', x.id, {'roles': p.role_codes}, request)
    await db.commit()
    return {'id': x.id, 'full_name': x.full_name, 'status': x.status, 'roles': x.role_codes}

@router.patch('/employees/{ident}/roles')
async def update_employee_roles(ident: int, p: RoleUpdate, request: Request, e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_roles(e, {'SUPER_ADMIN'})
    ensure_confirmed(request)
    target = await db.get(Employee, ident)
    if not target:
        raise HTTPException(404, 'Xodim topilmadi')
    codes = list(dict.fromkeys(p.role_codes))
    valid = {'SUPER_ADMIN', 'CEO', 'CTO', 'COO', 'PROJECT_LEADER', 'EMPLOYEE'}
    if set(codes) - valid:
        raise HTTPException(400, 'Noma’lum rol: ' + ', '.join(sorted(set(codes) - valid)))
    if 'SUPER_ADMIN' in target.role_codes and 'SUPER_ADMIN' not in codes:
        other = (await db.scalars(select(Employee).where(Employee.id != target.id, Employee.status == 'active'))).all()
        if not any(('SUPER_ADMIN' in x.role_codes for x in other)):
            raise HTTPException(409, 'Oxirgi faol Super Admin rolini olib tashlab bo‘lmaydi')
    role_rows = []
    for code in codes:
        role = await db.scalar(select(Role).where(Role.code == code))
        if not role:
            raise HTTPException(400, 'Rol tizimda topilmadi: ' + code)
        role_rows.append(role)
    target.roles = role_rows
    await audit(db, e.id, 'employee_roles_changed', 'employee', target.id, {'role_codes': codes}, request)
    await db.commit()
    return {'id': target.id, 'roles': target.role_codes}

@router.patch('/employees/{ident}/status')
async def employee_status(ident: int, p: StatusUpdate, request: Request, e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_roles(e, {'SUPER_ADMIN', 'CEO', 'COO'})
    ensure_confirmed(request)
    if p.status not in {'active', 'blocked', 'terminated'}:
        raise HTTPException(400, 'Status active, blocked yoki terminated bo‘lishi kerak')
    x = await db.get(Employee, ident)
    if not x:
        raise HTTPException(404, 'Xodim topilmadi')
    if 'SUPER_ADMIN' in x.role_codes and 'SUPER_ADMIN' not in e.role_codes:
        raise HTTPException(403, 'Super Admin hisobini o‘zgartirishga ruxsat yo‘q')
    if x.id == e.id and p.status != 'active':
        raise HTTPException(400, 'O‘z hisobingizni bloklay olmaysiz')
    x.status = p.status
    if p.status == 'terminated':
        x.terminated_at = datetime.now(timezone.utc)
        cards = (await db.scalars(select(EmployeeCard).where(EmployeeCard.employee_id == x.id))).all()
        for c in cards:
            c.status = 'revoked'
            c.blocked_at = datetime.now(timezone.utc)
    if p.status != 'active':
        sessions = (await db.scalars(select(UserSession).where(UserSession.employee_id == x.id, UserSession.revoked_at.is_(None)))).all()
        for s in sessions:
            s.revoked_at = datetime.now(timezone.utc)
    await audit(db, e.id, 'employee_status_changed', 'employee', x.id, {'status': p.status}, request)
    await db.commit()
    return {'ok': True, 'status': x.status, 'history_preserved': True}

@router.get('/applications')
async def applications(e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_roles(e, {'SUPER_ADMIN', 'CEO', 'COO'})
    rows = (await db.scalars(select(EmployeeApplication).order_by(EmployeeApplication.created_at.desc()))).all()
    return [{'id': a.id, 'telegram_id': a.telegram_id, 'full_name': a.full_name, 'department': a.department, 'desired_position': a.desired_position, 'message': a.message, 'status': a.status, 'created_at': a.created_at} for a in rows]

@router.post('/applications/{ident}/decision')
async def application_decision(ident: int, p: AppDecision, request: Request, e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_roles(e, {'SUPER_ADMIN', 'CEO', 'COO'})
    ensure_confirmed(request)
    a = await db.get(EmployeeApplication, ident)
    if not a or a.status != 'pending':
        raise HTTPException(404, 'Kutilayotgan ariza topilmadi')
    if p.decision == 'reject':
        a.status = 'rejected'
    else:
        if await db.scalar(select(Employee).where(Employee.telegram_id == a.telegram_id)):
            raise HTTPException(409, 'Bu Telegram ID allaqachon xodim')
        x = Employee(telegram_id=a.telegram_id, full_name=a.full_name, department=a.department, position=a.desired_position, status='active')
        for code in p.role_codes:
            if code in {'SUPER_ADMIN', 'CEO', 'CTO', 'COO'} and 'SUPER_ADMIN' not in e.role_codes:
                raise HTTPException(403, 'Rahbar va Super Admin rollarini faqat Super Admin beradi')
            r = await db.scalar(select(Role).where(Role.code == code))
            if not r:
                raise HTTPException(400, f'Noma’lum rol: {code}')
            x.roles.append(r)
        db.add(x)
        a.status = 'approved'
    a.reviewed_by_id = e.id
    await audit(db, e.id, 'application_decision', 'employee_application', a.id, {'decision': p.decision}, request)
    await db.commit()
    return {'ok': True, 'status': a.status}

@router.get('/invites')
async def list_invites(e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_roles(e, {'SUPER_ADMIN', 'CEO', 'COO'})
    rows = (await db.scalars(select(InviteCode).order_by(InviteCode.id.desc()).limit(200))).all()
    now = datetime.now(timezone.utc)
    result = []
    for x in rows:
        expired = bool(x.expires_at and (x.expires_at.replace(tzinfo=timezone.utc) if x.expires_at.tzinfo is None else x.expires_at) <= now)
        result.append({'id': x.id, 'code_suffix': x.code_suffix, 'max_uses': x.max_uses, 'use_count': x.use_count, 'expires_at': x.expires_at, 'status': 'revoked' if x.revoked_at else 'expired' if expired else 'used' if x.use_count >= x.max_uses else 'active', 'created_at': x.created_at})
    return result

@router.post('/invites')
async def create_invite(p: InviteCreate, request: Request, e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_roles(e, {'SUPER_ADMIN', 'CEO', 'COO'})
    ensure_confirmed(request)
    if p.expires_at:
        exp = p.expires_at if p.expires_at.tzinfo else p.expires_at.replace(tzinfo=timezone.utc)
        if exp <= datetime.now(timezone.utc):
            raise HTTPException(400, 'Taklif kodi muddati kelajakda bo‘lishi kerak')
    from app.security import digest
    code = secrets.token_urlsafe(9)
    x = InviteCode(code_hash=digest(code), code_suffix=code[-4:], max_uses=p.max_uses, expires_at=exp if p.expires_at else None, created_by_id=e.id)
    db.add(x)
    await db.flush()
    await audit(db, e.id, 'invite_created', 'invite_code', x.id, {'max_uses': p.max_uses}, request)
    await db.commit()
    link = f'https://t.me/{settings.telegram_bot_username}?start=invite-{code}' if settings.telegram_bot_username else None
    return {'id': x.id, 'status': 'active', 'invite_code_once': code, 'invite_link': link, 'max_uses': x.max_uses}

@router.post('/invites/{ident}/revoke')
async def revoke_invite(ident: int, request: Request, e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_roles(e, {'SUPER_ADMIN', 'CEO', 'COO'})
    ensure_confirmed(request)
    x = await db.get(InviteCode, ident)
    if not x:
        raise HTTPException(404, 'Taklif kodi topilmadi')
    x.revoked_at = datetime.now(timezone.utc)
    await audit(db, e.id, 'invite_revoked', 'invite_code', x.id, {}, request)
    await db.commit()
    return {'id': x.id, 'status': 'revoked'}

@router.get('/finance')
async def finance(e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_finance(e)
    rows = (await db.scalars(select(FinancialTransaction).order_by(FinancialTransaction.id.desc()).limit(500))).all()
    return [{'id': x.id, 'kind': x.kind, 'amount_uzs': float(x.amount_uzs), 'title': x.title, 'description': x.description, 'project_id': x.project_id, 'status': x.status, 'created_at': x.created_at, 'approved_at': x.approved_at} for x in rows]

@router.post('/finance')
async def create_finance(p: FinanceCreate, request: Request, e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_finance(e)
    x = FinancialTransaction(**p.model_dump(), created_by_id=e.id, status='pending')
    db.add(x)
    await db.flush()
    await audit(db, e.id, 'finance_created', 'financial_transaction', x.id, {'kind': x.kind, 'amount_uzs': float(x.amount_uzs)}, request)
    await db.commit()
    return {'id': x.id, 'status': x.status}

@router.post('/finance/{ident}/decision')
async def decide_finance(ident: int, p: FinanceDecision, request: Request, e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_finance(e)
    ensure_confirmed(request)
    x = await db.get(FinancialTransaction, ident)
    if not x:
        raise HTTPException(404, 'Moliya yozuvi topilmadi')
    if x.status != 'pending':
        raise HTTPException(409, 'Bu yozuv ko‘rib chiqilgan')
    x.status = 'approved' if p.decision == 'approve' else 'rejected'
    x.approved_by_id = e.id
    x.approved_at = datetime.now(timezone.utc)
    await audit(db, e.id, 'finance_decision', 'financial_transaction', x.id, {'decision': p.decision}, request)
    await db.commit()
    return {'id': x.id, 'status': x.status}

@router.get('/finance/summary')
async def finance_summary(e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_finance(e)

    async def total(kind):
        return float(await db.scalar(select(func.coalesce(func.sum(FinancialTransaction.amount_uzs), 0)).where(FinancialTransaction.kind == kind, FinancialTransaction.status == 'approved')) or 0)
    inc = await total('income')
    out = await total('expense')
    return {'currency': 'UZS', 'income_uzs': inc, 'expenses_uzs': out, 'balance_uzs': inc - out}

@router.get('/cards')
async def cards(e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    q = select(EmployeeCard).order_by(EmployeeCard.id.desc())
    if not set(e.role_codes) & {'SUPER_ADMIN', 'CEO'}:
        q = q.where(EmployeeCard.employee_id == e.id)
    rows = (await db.scalars(q)).all()
    return [{'id': c.id, 'employee_id': c.employee_id, 'card_number': c.card_number, 'status': c.status, 'created_at': c.created_at} for c in rows]

@router.post('/cards')
async def issue_card(p: CardIssue, request: Request, e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_roles(e, {'SUPER_ADMIN', 'CEO'})
    ensure_confirmed(request)
    target = await db.get(Employee, p.employee_id)
    if not target or target.status != 'active':
        raise HTTPException(404, 'Faol xodim topilmadi')
    raw = opaque_token()
    number = f'WTR-{secrets.token_hex(4).upper()}'
    c = EmployeeCard(employee_id=target.id, card_number=number, qr_token_hash=digest(raw), qr_token_encrypted=encrypt_secret(raw), status='pending', issued_by_id=e.id)
    db.add(c)
    await db.flush()
    await audit(db, e.id, 'card_issued_pending_approval', 'employee_card', c.id, {}, request)
    await db.commit()
    import qrcode
    image = qrcode.make('wentric-card:' + raw)
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    qr_data = 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode('ascii')
    return {'id': c.id, 'card_number': number, 'status': 'pending', 'qr_token_once': raw, 'qr_png_data_url': qr_data, 'note': 'Token bir marta ko‘rsatiladi; DB’da faqat hash saqlanadi.'}

@router.post('/cards/verify')
async def verify_card(p: CardVerify, e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_roles(e, {'SUPER_ADMIN', 'CEO', 'COO'})
    c = await db.scalar(select(EmployeeCard).where(EmployeeCard.qr_token_hash == digest(p.token.replace('wentric-card:', '', 1)), EmployeeCard.status == 'active'))
    if not c:
        raise HTTPException(404, 'Karta haqiqiy faol karta sifatida topilmadi')
    target = await db.get(Employee, c.employee_id)
    if not target or target.status != 'active':
        raise HTTPException(404, 'Xodim hisobi faol emas')
    return {'valid': True, 'card_number': c.card_number, 'employee': {'id': target.id, 'full_name': target.full_name, 'department': target.department, 'position': target.position}}

@router.post('/cards/{ident}/decision')
async def card_decision(ident: int, p: CardDecision, request: Request, e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_roles(e, {'SUPER_ADMIN', 'CEO'})
    ensure_confirmed(request)
    c = await db.get(EmployeeCard, ident)
    if not c:
        raise HTTPException(404, 'Karta topilmadi')
    c.status = 'active' if p.decision == 'approve' else 'revoked'
    c.blocked_at = None if p.decision == 'approve' else datetime.now(timezone.utc)
    await audit(db, e.id, 'card_decision', 'employee_card', c.id, {'decision': p.decision}, request)
    await db.commit()
    return {'id': c.id, 'status': c.status}

@router.post('/cards/{ident}/block')
async def block_card(ident: int, request: Request, e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_confirmed(request)
    c = await db.get(EmployeeCard, ident)
    if not c:
        raise HTTPException(404, 'Karta topilmadi')
    if c.employee_id != e.id:
        ensure_roles(e, {'SUPER_ADMIN', 'CEO'})
    c.status = 'blocked'
    c.blocked_at = datetime.now(timezone.utc)
    await audit(db, e.id, 'card_blocked', 'employee_card', c.id, {}, request)
    await db.commit()
    return {'id': c.id, 'status': c.status}
