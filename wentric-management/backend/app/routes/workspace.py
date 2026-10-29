from datetime import datetime, timezone, timedelta
import uuid
from pathlib import Path
from io import BytesIO
from fastapi import APIRouter, Depends, Header, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from app.config import settings
from app.database import get_db
from app.deps import current_employee
from app.models import Employee, EmployeeApplication, InviteCode, EmployeeRating, WorkSchedule, Notification, Announcement, Meeting, KnowledgeArticle, Suggestion, FileAsset, AuditLog, SecurityEvent, Project, ProjectMember, Task, FinancialTransaction
from app.schemas import ApplicationCreate, AnnouncementCreate, MeetingCreate, KnowledgeCreate, SuggestionCreate, SuggestionStatus, RatingCreate, WorkScheduleCreate
from app.rbac import ensure_roles, ensure_finance, role_scopes
from app.audit import audit
from app.security import digest
router = APIRouter(tags=['Ichki aloqa, fayllar va hisobotlar'])

@router.post('/integrations/applications', include_in_schema=False)
async def bot_application(p: ApplicationCreate, x_bot_secret: str | None=Header(default=None), db: AsyncSession=Depends(get_db)):
    if not settings.bot_api_secret or not x_bot_secret or x_bot_secret != settings.bot_api_secret:
        raise HTTPException(403, 'Bot integratsiyasi ruxsat etilmagan')
    old = await db.scalar(select(EmployeeApplication).where(EmployeeApplication.telegram_id == p.telegram_id, EmployeeApplication.status == 'pending'))
    if old:
        return {'ok': True, 'application_id': old.id, 'message': 'Arizangiz avval yuborilgan'}
    invite = None
    if p.invite_code:
        invite = await db.scalar(select(InviteCode).where(InviteCode.code_hash == digest(p.invite_code.strip()), InviteCode.revoked_at.is_(None)))
        if not invite:
            raise HTTPException(400, 'Taklif kodi yaroqsiz yoki bekor qilingan')
        if invite.expires_at:
            expiry = invite.expires_at if invite.expires_at.tzinfo else invite.expires_at.replace(tzinfo=timezone.utc)
            if expiry <= datetime.now(timezone.utc):
                raise HTTPException(400, 'Taklif kodi muddati tugagan')
        if invite.use_count >= invite.max_uses:
            raise HTTPException(400, 'Taklif kodi ishlatish limiti tugagan')
        invite.use_count += 1
    x = EmployeeApplication(**p.model_dump(exclude={'invite_code'}), invite_code_id=invite.id if invite else None)
    db.add(x)
    await db.commit()
    return {'ok': True, 'application_id': x.id, 'message': 'Ariza qabul qilindi'}

@router.post('/integrations/bot/reminders/run', include_in_schema=False)
async def run_deadline_reminders(x_bot_secret: str | None=Header(default=None), db: AsyncSession=Depends(get_db)):
    if not settings.bot_api_secret or not x_bot_secret or x_bot_secret != settings.bot_api_secret:
        raise HTTPException(403, 'Bot integratsiyasiga ruxsat yo‘q')
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    soon = now + timedelta(hours=24)
    tasks = (await db.scalars(select(Task).where(Task.assignee_id.is_not(None), Task.deadline.is_not(None), Task.status != 'done', Task.deadline <= soon).limit(1000))).all()
    created = 0
    for task in tasks:
        if not task.assignee_id or not task.deadline:
            continue
        exists = await db.scalar(select(Notification.id).where(Notification.employee_id == task.assignee_id, Notification.kind == 'deadline', Notification.body.like(f'[task:{task.id}]%'), Notification.created_at >= day_start).limit(1))
        if exists:
            continue
        deadline = task.deadline if task.deadline.tzinfo else task.deadline.replace(tzinfo=timezone.utc)
        label = 'Muddati o‘tgan' if deadline < now else 'Muddat yaqinlashmoqda'
        db.add(Notification(employee_id=task.assignee_id, title=f'{label}: {task.title}', body=f'[task:{task.id}] Vazifa #{task.id}. Muddat: {deadline.isoformat()}', kind='deadline'))
        created += 1
        if deadline < now:
            targets = {task.created_by_id}
            if task.project_id:
                project = await db.get(Project, task.project_id)
                if project and project.lead_id:
                    targets.add(project.lead_id)
            for target_id in targets:
                if target_id == task.assignee_id:
                    continue
                manager_exists = await db.scalar(select(Notification.id).where(Notification.employee_id == target_id, Notification.kind == 'deadline_manager', Notification.body.like(f'[task:{task.id}]%'), Notification.created_at >= day_start).limit(1))
                if not manager_exists:
                    db.add(Notification(employee_id=target_id, title=f'Vazifa kechikdi: {task.title}', body=f'[task:{task.id}] {task.assignee_id} xodim vazifasi muddati o‘tgan.', kind='deadline_manager'))
    await db.commit()
    return {'ok': True, 'notifications_created': created}

@router.post('/integrations/bot/files', include_in_schema=False)
async def bot_upload_file(telegram_id: int=Form(...), file: UploadFile=File(...), x_bot_secret: str | None=Header(default=None), db: AsyncSession=Depends(get_db)):
    if not settings.bot_api_secret or not x_bot_secret or x_bot_secret != settings.bot_api_secret:
        raise HTTPException(403, 'Bot integratsiyasiga ruxsat yo‘q')
    e = await db.scalar(select(Employee).where(Employee.telegram_id == telegram_id, Employee.status == 'active'))
    if not e:
        raise HTTPException(403, 'Tasdiqlangan faol xodim hisobi topilmadi')
    allowed = {'.pdf', '.png', '.jpg', '.jpeg', '.webp', '.txt', '.docx', '.xlsx', '.csv', '.zip'}
    ext = Path(file.filename or '').suffix.lower()
    if ext not in allowed:
        raise HTTPException(415, 'Fayl turi ruxsat etilmagan')
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f'Fayl {settings.max_upload_mb} MB dan oshmasin')
    folder = Path(settings.storage_dir)
    folder.mkdir(parents=True, exist_ok=True)
    stored = uuid.uuid4().hex + ext
    (folder / stored).write_bytes(content)
    x = FileAsset(original_name=(file.filename or 'telegram_fayl')[:255], stored_name=stored, content_type=file.content_type or 'application/octet-stream', size_bytes=len(content), uploaded_by_id=e.id)
    db.add(x)
    await db.flush()
    await audit(db, e.id, 'telegram_file_uploaded', 'file', x.id, {'name': x.original_name, 'size': len(content)})
    await db.commit()
    return {'ok': True, 'id': x.id, 'original_name': x.original_name, 'size_bytes': x.size_bytes}

@router.get('/notifications')
async def notifications(e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    rows = (await db.scalars(select(Notification).where(Notification.employee_id == e.id).order_by(Notification.created_at.desc()).limit(100))).all()
    return [{'id': x.id, 'title': x.title, 'body': x.body, 'kind': x.kind, 'read_at': x.read_at, 'created_at': x.created_at} for x in rows]

@router.post('/notifications/{ident}/read')
async def notification_read(ident: int, e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    x = await db.get(Notification, ident)
    if not x or x.employee_id != e.id:
        raise HTTPException(404, 'Bildirishnoma topilmadi')
    x.read_at = datetime.now(timezone.utc)
    await db.commit()
    return {'ok': True}

@router.get('/announcements')
async def announcements(e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    rows = (await db.scalars(select(Announcement).order_by(Announcement.created_at.desc()).limit(100))).all()
    return [{'id': x.id, 'title': x.title, 'body': x.body, 'audience': x.audience, 'created_at': x.created_at} for x in rows if x.audience == 'all' or x.audience in e.role_codes or x.audience == e.department]

@router.post('/announcements')
async def create_announcement(p: AnnouncementCreate, request: Request, e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_roles(e, {'SUPER_ADMIN', 'CEO', 'CTO', 'COO'})
    x = Announcement(**p.model_dump(), created_by_id=e.id)
    db.add(x)
    await db.flush()
    people = (await db.scalars(select(Employee).where(Employee.status == 'active'))).all()
    for person in people:
        if p.audience == 'all' or p.audience in person.role_codes or p.audience == person.department:
            db.add(Notification(employee_id=person.id, title='E’lon: ' + p.title, body=p.body[:1000], kind='announcement'))
    await audit(db, e.id, 'announcement_created', 'announcement', x.id, {}, request)
    await db.commit()
    return {'id': x.id, 'title': x.title}

@router.get('/meetings')
async def meetings(e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    rows = (await db.scalars(select(Meeting).order_by(Meeting.starts_at.asc()).limit(200))).all()
    return [{'id': x.id, 'title': x.title, 'description': x.description, 'starts_at': x.starts_at, 'ends_at': x.ends_at, 'location': x.location} for x in rows]

@router.post('/meetings')
async def create_meeting(p: MeetingCreate, request: Request, e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_roles(e, {'SUPER_ADMIN', 'CEO', 'CTO', 'COO', 'PROJECT_LEADER'})
    if p.ends_at <= p.starts_at:
        raise HTTPException(400, 'Uchrashuv tugash vaqti keyin bo‘lishi kerak')
    x = Meeting(**p.model_dump(), created_by_id=e.id)
    db.add(x)
    await db.flush()
    people = (await db.scalars(select(Employee).where(Employee.status == 'active'))).all()
    for person in people:
        db.add(Notification(employee_id=person.id, title='Uchrashuv: ' + x.title, body=x.starts_at.isoformat() + ' · ' + (x.location or 'Joy belgilanmagan'), kind='meeting'))
    await audit(db, e.id, 'meeting_created', 'meeting', x.id, {}, request)
    await db.commit()
    return {'id': x.id, 'title': x.title}

@router.get('/knowledge')
async def knowledge(e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    rows = (await db.scalars(select(KnowledgeArticle).order_by(KnowledgeArticle.updated_at.desc()).limit(300))).all()
    return [{'id': x.id, 'title': x.title, 'body': x.body, 'category': x.category, 'updated_at': x.updated_at} for x in rows]

@router.post('/knowledge')
async def create_knowledge(p: KnowledgeCreate, request: Request, e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_roles(e, {'SUPER_ADMIN', 'CEO', 'CTO', 'COO', 'PROJECT_LEADER'})
    x = KnowledgeArticle(**p.model_dump(), created_by_id=e.id)
    db.add(x)
    await db.flush()
    await audit(db, e.id, 'knowledge_created', 'knowledge_article', x.id, {}, request)
    await db.commit()
    return {'id': x.id, 'title': x.title}

@router.get('/suggestions')
async def suggestions(e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    q = select(Suggestion).order_by(Suggestion.created_at.desc()).limit(300)
    if not set(e.role_codes) & {'SUPER_ADMIN', 'CEO', 'COO'}:
        q = q.where(Suggestion.employee_id == e.id)
    rows = (await db.scalars(q)).all()
    return [{'id': x.id, 'employee_id': x.employee_id, 'title': x.title, 'body': x.body, 'kind': x.kind, 'status': x.status, 'created_at': x.created_at} for x in rows]

@router.post('/suggestions')
async def create_suggestion(p: SuggestionCreate, e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    x = Suggestion(employee_id=e.id, **p.model_dump())
    db.add(x)
    await db.commit()
    return {'id': x.id, 'status': x.status}

@router.patch('/suggestions/{ident}/status')
async def suggestion_status(ident: int, p: SuggestionStatus, e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_roles(e, {'SUPER_ADMIN', 'CEO', 'COO'})
    x = await db.get(Suggestion, ident)
    if not x:
        raise HTTPException(404, 'Taklif topilmadi')
    x.status = p.status
    await db.commit()
    return {'id': x.id, 'status': x.status}

@router.get('/schedules')
async def schedules(e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    q = select(WorkSchedule).order_by(WorkSchedule.employee_id, WorkSchedule.weekday)
    if not set(e.role_codes) & {'SUPER_ADMIN', 'CEO', 'COO'}:
        q = q.where(WorkSchedule.employee_id == e.id)
    rows = (await db.scalars(q.limit(500))).all()
    return [{'id': x.id, 'employee_id': x.employee_id, 'weekday': x.weekday, 'weekday_name': ['Dushanba', 'Seshanba', 'Chorshanba', 'Payshanba', 'Juma', 'Shanba', 'Yakshanba'][x.weekday], 'start_time': x.start_time, 'end_time': x.end_time, 'work_mode': x.work_mode, 'timezone': x.timezone, 'updated_at': x.updated_at} for x in rows]

@router.post('/schedules')
async def save_schedule(p: WorkScheduleCreate, request: Request, e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_roles(e, {'SUPER_ADMIN', 'CEO', 'COO'})
    if p.end_time <= p.start_time:
        raise HTTPException(400, 'Ish tugash vaqti boshlanishdan keyin bo‘lishi kerak')
    target = await db.get(Employee, p.employee_id)
    if not target or target.status != 'active':
        raise HTTPException(404, 'Faol xodim topilmadi')
    x = await db.scalar(select(WorkSchedule).where(WorkSchedule.employee_id == p.employee_id, WorkSchedule.weekday == p.weekday))
    if x:
        x.start_time = p.start_time
        x.end_time = p.end_time
        x.work_mode = p.work_mode
        x.timezone = p.timezone
    else:
        x = WorkSchedule(**p.model_dump())
        db.add(x)
    await db.flush()
    await audit(db, e.id, 'work_schedule_saved', 'work_schedule', x.id, p.model_dump(), request)
    await db.commit()
    return {'id': x.id, 'employee_id': x.employee_id, 'weekday': x.weekday, 'start_time': x.start_time, 'end_time': x.end_time, 'work_mode': x.work_mode}

@router.get('/ratings')
async def ratings(e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    q = select(EmployeeRating).order_by(EmployeeRating.created_at.desc()).limit(500)
    if not set(e.role_codes) & {'SUPER_ADMIN', 'CEO', 'CTO', 'COO', 'PROJECT_LEADER'}:
        q = q.where(EmployeeRating.employee_id == e.id)
    rows = (await db.scalars(q)).all()
    return [{'id': r.id, 'employee_id': r.employee_id, 'reviewer_id': r.reviewer_id, 'score': r.score, 'comment': r.comment, 'created_at': r.created_at} for r in rows]

@router.post('/ratings')
async def create_rating(p: RatingCreate, request: Request, e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_roles(e, {'SUPER_ADMIN', 'CEO', 'CTO', 'COO', 'PROJECT_LEADER'})
    if p.employee_id == e.id:
        raise HTTPException(400, 'Xodim o‘ziga o‘zi baho bera olmaydi')
    target = await db.get(Employee, p.employee_id)
    if not target:
        raise HTTPException(404, 'Xodim topilmadi')
    x = EmployeeRating(employee_id=p.employee_id, reviewer_id=e.id, score=p.score, comment=p.comment)
    db.add(x)
    await db.flush()
    await audit(db, e.id, 'employee_rated', 'employee_rating', x.id, {'employee_id': p.employee_id, 'score': p.score}, request)
    await db.commit()
    db.add(Notification(employee_id=target.id, title='Ish faoliyati baholandi', body=f'Rahbar bahosi: {p.score}/5' + (f' · {p.comment}' if p.comment else ''), kind='rating'))
    await db.commit()
    return {'id': x.id, 'employee_id': x.employee_id, 'score': x.score}

@router.get('/files')
async def files(e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    rows = (await db.scalars(select(FileAsset).order_by(FileAsset.created_at.desc()).limit(200))).all()
    return [{'id': x.id, 'original_name': x.original_name, 'content_type': x.content_type, 'size_bytes': x.size_bytes, 'uploaded_by_id': x.uploaded_by_id, 'created_at': x.created_at} for x in rows]

@router.post('/files')
async def upload_file(request: Request, file: UploadFile=File(...), e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    allowed = {'.pdf', '.png', '.jpg', '.jpeg', '.webp', '.txt', '.docx', '.xlsx', '.csv', '.zip'}
    ext = Path(file.filename or '').suffix.lower()
    if ext not in allowed:
        raise HTTPException(415, 'Fayl turi ruxsat etilmagan')
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f'Fayl {settings.max_upload_mb} MB dan oshmasin')
    folder = Path(settings.storage_dir)
    folder.mkdir(parents=True, exist_ok=True)
    stored = uuid.uuid4().hex + ext
    (folder / stored).write_bytes(content)
    x = FileAsset(original_name=(file.filename or 'fayl')[:255], stored_name=stored, content_type=file.content_type or 'application/octet-stream', size_bytes=len(content), uploaded_by_id=e.id)
    db.add(x)
    await db.flush()
    await audit(db, e.id, 'file_uploaded', 'file', x.id, {'name': x.original_name, 'size': len(content)}, request)
    await db.commit()
    return {'id': x.id, 'original_name': x.original_name, 'size_bytes': x.size_bytes}

@router.get('/files/{ident}/download')
async def download_file(ident: int, e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    x = await db.get(FileAsset, ident)
    if not x:
        raise HTTPException(404, 'Fayl topilmadi')
    if x.uploaded_by_id != e.id and (not set(e.role_codes) & {'SUPER_ADMIN', 'CEO', 'CTO', 'COO', 'PROJECT_LEADER'}):
        raise HTTPException(403, 'Faylga ruxsat yo‘q')
    path = Path(settings.storage_dir) / x.stored_name
    if not path.exists():
        raise HTTPException(404, 'Fayl omborda yo‘q')
    return FileResponse(path, filename=x.original_name, media_type=x.content_type)

async def _report_scope(e: Employee, db: AsyncSession) -> set[int] | None:
    roles = set(e.role_codes)
    if roles & {"SUPER_ADMIN", "CEO"}:
        return None
    scopes = role_scopes(e)
    if scopes:
        projects = (await db.scalars(select(Project.id).where(Project.department.in_(scopes)))).all()
        return set(projects)
    if "PROJECT_LEADER" in roles:
        memberships = set((await db.scalars(select(ProjectMember.project_id).where(ProjectMember.employee_id == e.id))).all())
        led = set((await db.scalars(select(Project.id).where(Project.lead_id == e.id))).all())
        return memberships | led
    return set()


async def _scoped_tasks(e: Employee, db: AsyncSession):
    scope = await _report_scope(e, db)
    query = select(Task).order_by(Task.id)
    if scope is not None:
        if not scope:
            return []
        query = query.where(Task.project_id.in_(scope))
    return list((await db.scalars(query)).all())


@router.get('/reports/summary')
async def report_summary(e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_roles(e, {"SUPER_ADMIN", "CEO", "CTO", "COO", "PROJECT_LEADER"})
    scope = await _report_scope(e, db)
    projects_query = select(Project)
    if scope is not None:
        projects_query = projects_query.where(Project.id.in_(scope)) if scope else projects_query.where(Project.id == -1)
    projects = list((await db.scalars(projects_query)).all())
    tasks = await _scoped_tasks(e, db)
    now = datetime.now(timezone.utc)
    overdue = 0
    done = 0
    for task in tasks:
        if task.status == "done":
            done += 1
        elif task.deadline:
            deadline = task.deadline if task.deadline.tzinfo else task.deadline.replace(tzinfo=timezone.utc)
            overdue += int(deadline < now)
    result = {"active_projects": sum(1 for project in projects if project.status == "active"), "tasks_total": len(tasks), "tasks_done": done, "tasks_overdue": overdue, "finance_visible": bool(set(e.role_codes) & {"SUPER_ADMIN", "CEO"})}
    if result["finance_visible"]:
        result["active_employees"] = int(await db.scalar(select(func.count(Employee.id)).where(Employee.status == "active")) or 0)
    return result

@router.get('/reports/tasks.xlsx')
async def tasks_excel(e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_roles(e, {'SUPER_ADMIN', 'CEO', 'CTO', 'COO', 'PROJECT_LEADER'})
    rows = await _scoped_tasks(e, db)
    wb = Workbook()
    ws = wb.active
    ws.title = 'Vazifalar'
    ws.append(['ID', 'Vazifa', 'Loyiha ID', 'Mas’ul ID', 'Muddat', 'Ustuvorlik', 'Holat', 'Jarayon %'])
    for x in rows:
        ws.append([x.id, x.title, x.project_id, x.assignee_id, x.deadline.isoformat() if x.deadline else '', x.priority, x.status, x.progress])
    out = BytesIO()
    wb.save(out)
    out.seek(0)
    return StreamingResponse(out, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={'Content-Disposition': 'attachment; filename=wentric_tasks.xlsx'})

@router.get('/reports/summary.pdf')
async def summary_pdf(e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_roles(e, {'SUPER_ADMIN', 'CEO', 'CTO', 'COO', 'PROJECT_LEADER'})
    scope = await _report_scope(e, db)
    project_query = select(Project)
    if scope is not None:
        project_query = project_query.where(Project.id.in_(scope)) if scope else project_query.where(Project.id == -1)
    project_rows = list((await db.scalars(project_query)).all())
    task_rows = await _scoped_tasks(e, db)
    pr = sum(1 for project in project_rows if project.status == 'active')
    tt = len(task_rows)
    done = sum(1 for task in task_rows if task.status == 'done')
    out = BytesIO()
    pdf = canvas.Canvas(out, pagesize=A4)
    _, h = A4
    pdf.setTitle('Wentric hisobot')
    pdf.setFont('Helvetica-Bold', 18)
    pdf.drawString(50, h - 60, 'Wentric Management - Hisobot')
    pdf.setFont('Helvetica', 11)
    pdf.drawString(50, h - 100, f'Faol loyihalar: {pr}')
    pdf.drawString(50, h - 125, f'Jami vazifalar: {tt}')
    pdf.drawString(50, h - 150, f'Bajarilgan vazifalar: {done}')
    pdf.save()
    out.seek(0)
    return StreamingResponse(out, media_type='application/pdf', headers={'Content-Disposition': 'attachment; filename=wentric_summary.pdf'})

@router.get('/reports/finance.xlsx')
async def finance_excel(e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_finance(e)
    rows = (await db.scalars(select(FinancialTransaction).order_by(FinancialTransaction.id))).all()
    wb = Workbook()
    ws = wb.active
    ws.title = 'Moliya'
    ws.append(['ID', 'Turi', 'Summa UZS', 'Sarlavha', 'Loyiha ID', 'Holat', 'Sana'])
    for x in rows:
        ws.append([x.id, x.kind, float(x.amount_uzs), x.title, x.project_id, x.status, x.created_at.isoformat()])
    out = BytesIO()
    wb.save(out)
    out.seek(0)
    return StreamingResponse(out, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={'Content-Disposition': 'attachment; filename=wentric_finance.xlsx'})

@router.get('/security-events')
async def security_events(e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_roles(e, {'SUPER_ADMIN'})
    audits = (await db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(300))).all()
    events = (await db.scalars(select(SecurityEvent).order_by(SecurityEvent.created_at.desc()).limit(300))).all()
    result = []
    for x in audits:
        result.append({'id': f'AUD-{x.id}', 'created_at': x.created_at, 'actor': x.actor_id, 'event_type': x.action, 'severity': 'audit', 'entity_type': x.entity_type, 'entity_id': x.entity_id, 'details': x.details, 'ip_address': x.ip_address})
    for x in events:
        result.append({'id': f'SEC-{x.id}', 'created_at': x.created_at, 'actor': x.telegram_id, 'event_type': x.event_type, 'severity': x.severity, 'entity_type': 'security_event', 'entity_id': None, 'details': x.details, 'ip_address': None})
    result.sort(key=lambda x: x['created_at'], reverse=True)
    return result[:500]

@router.get('/audit-logs')
async def audit_logs(e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_roles(e, {'SUPER_ADMIN'})
    rows = (await db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(500))).all()
    return [{'id': x.id, 'actor_id': x.actor_id, 'action': x.action, 'entity_type': x.entity_type, 'entity_id': x.entity_id, 'details': x.details, 'ip_address': x.ip_address, 'created_at': x.created_at} for x in rows]
