from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.deps import current_employee
from app.models import Employee, Project, ProjectMember, Task, TaskReview, AttendanceRecord, LeaveRequest, Notification
from app.schemas import ProjectCreate, TaskCreate, TaskStatus, AttendanceStart, LeaveCreate, LeaveDecision
from app.rbac import ensure_roles, ensure_confirmed, department_scope, role_scopes
from app.audit import audit
router = APIRouter(tags=['Loyihalar, vazifalar va davomat'])

@router.get('/employees')
async def employees(e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_roles(e, {'SUPER_ADMIN', 'CEO', 'CTO', 'COO', 'PROJECT_LEADER'})
    rows = (await db.scalars(select(Employee).order_by(Employee.id.desc()))).all()
    roles = set(e.role_codes)
    if not roles & {'SUPER_ADMIN', 'CEO'} and roles & {'CTO', 'COO'}:
        scopes = role_scopes(e)
        rows = [x for x in rows if x.id == e.id or department_scope(x.department) in scopes]
    return [{'id': x.id, 'full_name': x.full_name, 'telegram_id': x.telegram_id, 'department': x.department, 'position': x.position, 'status': x.status, 'roles': x.role_codes, 'work_mode': x.work_mode} for x in rows]

@router.get('/projects')
async def projects(e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    rows = (await db.scalars(select(Project).order_by(Project.id.desc()))).all()
    roles = set(e.role_codes)
    scopes = role_scopes(e)
    if 'all' in scopes:
        picked = rows
    elif scopes:
        picked = [p for p in rows if p.department in scopes]
    else:
        mids = set((await db.scalars(select(ProjectMember.project_id).where(ProjectMember.employee_id == e.id))).all())
        mids.update((p.id for p in rows if p.lead_id == e.id))
        picked = [p for p in rows if p.id in mids]
    return [{'id': p.id, 'name': p.name, 'description': p.description, 'department': p.department, 'status': p.status, 'lead_id': p.lead_id, 'budget_uzs': float(p.budget_uzs or 0), 'deadline': p.deadline} for p in picked]

@router.post('/projects')
async def create_project(p: ProjectCreate, request: Request, e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_roles(e, {'SUPER_ADMIN', 'CEO', 'CTO', 'COO'})
    roles = set(e.role_codes)
    if 'SUPER_ADMIN' not in roles and 'CEO' not in roles:
        scopes = role_scopes(e)
        if p.department not in scopes:
            raise HTTPException(403, 'CTO faqat technical, COO faqat operations loyihasini yaratishi mumkin')
    x = Project(**p.model_dump())
    db.add(x)
    await db.flush()
    await audit(db, e.id, 'project_created', 'project', x.id, {'name': x.name}, request)
    await db.commit()
    return {'id': x.id, 'name': x.name, 'status': x.status}

@router.get('/tasks')
async def tasks(e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    rows = (await db.scalars(select(Task).order_by(Task.id.desc()).limit(1000))).all()
    roles = set(e.role_codes)
    if roles & {'SUPER_ADMIN', 'CEO'}:
        picked = rows
    elif roles & {'CTO', 'COO'}:
        scopes = role_scopes(e)
        projects_map = {x.id: x for x in (await db.scalars(select(Project))).all()}
        people_map = {x.id: x for x in (await db.scalars(select(Employee))).all()}
        picked = []
        for task in rows:
            project = projects_map.get(task.project_id)
            if project and project.department in scopes:
                picked.append(task)
                continue
            if project is None:
                assignee = people_map.get(task.assignee_id)
                creator = people_map.get(task.created_by_id)
                if task.assignee_id == e.id or task.created_by_id == e.id or (assignee and department_scope(assignee.department) in scopes) or (creator and department_scope(creator.department) in scopes):
                    picked.append(task)
    elif 'PROJECT_LEADER' in roles:
        member_ids = set((await db.scalars(select(ProjectMember.project_id).where(ProjectMember.employee_id == e.id))).all())
        member_ids.update(x.id for x in (await db.scalars(select(Project).where(Project.lead_id == e.id))).all())
        picked = [t for t in rows if t.project_id in member_ids or t.assignee_id == e.id or t.created_by_id == e.id]
    else:
        picked = [t for t in rows if t.assignee_id == e.id or t.created_by_id == e.id]
    return [{'id': t.id, 'title': t.title, 'description': t.description, 'project_id': t.project_id, 'assignee_id': t.assignee_id, 'created_by_id': t.created_by_id, 'deadline': t.deadline, 'priority': t.priority, 'status': t.status, 'progress': t.progress} for t in picked]

@router.post('/tasks')
async def create_task(p: TaskCreate, request: Request, e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_roles(e, {'SUPER_ADMIN', 'CEO', 'CTO', 'COO', 'PROJECT_LEADER'})
    roles = set(e.role_codes)
    project = await db.get(Project, p.project_id) if p.project_id else None
    if p.project_id and not project:
        raise HTTPException(404, 'Loyiha topilmadi')
    assignee = None
    if p.assignee_id:
        assignee = await db.get(Employee, p.assignee_id)
        if not assignee or assignee.status != 'active':
            raise HTTPException(404, 'Faol xodim topilmadi')
    if not roles & {'SUPER_ADMIN', 'CEO'}:
        if roles & {'CTO', 'COO'}:
            scopes = role_scopes(e)
            if not project or project.department not in scopes:
                raise HTTPException(403, 'CTO/COO vazifasi tegishli bo‘lim loyihasiga biriktirilishi kerak')
            if assignee and department_scope(assignee.department) not in scopes:
                raise HTTPException(403, 'Vazifa faqat tegishli bo‘lim xodimiga biriktirilishi mumkin')
        elif 'PROJECT_LEADER' in roles:
            if not project or not (project.lead_id == e.id or await db.scalar(select(ProjectMember.id).where(ProjectMember.project_id == project.id, ProjectMember.employee_id == e.id))):
                raise HTTPException(403, 'Faqat o‘zingiz rahbarlik qilayotgan yoki a’zo bo‘lgan loyihaga vazifa berishingiz mumkin')
            if assignee and assignee.id != project.lead_id and not await db.scalar(select(ProjectMember.id).where(ProjectMember.project_id == project.id, ProjectMember.employee_id == assignee.id)):
                raise HTTPException(403, 'Vazifa faqat loyiha a’zosiga biriktirilishi mumkin')
    x = Task(**p.model_dump(), created_by_id=e.id)
    db.add(x)
    await db.flush()
    if x.assignee_id:
        db.add(Notification(employee_id=x.assignee_id, title='Yangi vazifa', body=x.title, kind='task'))
    await audit(db, e.id, 'task_created', 'task', x.id, {'assignee_id': x.assignee_id}, request)
    await db.commit()
    return {'id': x.id, 'title': x.title, 'status': x.status}

@router.patch('/tasks/{task_id}/status')
async def update_task(task_id: int, p: TaskStatus, request: Request, e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    x = await db.get(Task, task_id)
    if not x:
        raise HTTPException(404, 'Vazifa topilmadi')
    roles = set(e.role_codes)
    mgr = bool(roles & {'SUPER_ADMIN', 'CEO'})
    if not mgr and roles & {'CTO', 'COO'}:
        project = await db.get(Project, x.project_id) if x.project_id else None
        mgr = bool(project and project.department in role_scopes(e))
    if not mgr and 'PROJECT_LEADER' in roles:
        project = await db.get(Project, x.project_id) if x.project_id else None
        membership = await db.scalar(select(ProjectMember.id).where(ProjectMember.project_id == x.project_id, ProjectMember.employee_id == e.id)) if x.project_id else None
        mgr = bool(project and (project.lead_id == e.id or membership))
    if not mgr and x.assignee_id != e.id:
        raise HTTPException(403, 'Bu vazifa sizga tegishli emas yoki rolingizda uni boshqarish ruxsati yo‘q')
    if p.status == 'done' and (not mgr):
        x.status = 'review'
        x.progress = 100
    else:
        x.status = p.status
        x.progress = p.progress if p.progress is not None else 100 if p.status == 'done' else x.progress
    if p.status in {'done', 'review'}:
        db.add(TaskReview(task_id=x.id, reviewer_id=e.id, decision='submitted' if not mgr else 'approved'))
    await audit(db, e.id, 'task_status_changed', 'task', x.id, {'status': x.status, 'progress': x.progress}, request)
    await db.commit()
    return {'ok': True, 'id': x.id, 'status': x.status, 'progress': x.progress}

@router.post('/attendance/start')
async def start_attendance(p: AttendanceStart, request: Request, e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    x = await db.scalar(select(AttendanceRecord).where(AttendanceRecord.employee_id == e.id, AttendanceRecord.work_date == today, AttendanceRecord.finished_at.is_(None)))
    if x and x.started_at:
        raise HTTPException(409, 'Bugungi ish vaqti boshlangan')
    if not x:
        x = AttendanceRecord(employee_id=e.id, work_date=today, mode=p.mode, source='web')
        db.add(x)
    x.started_at = now
    x.mode = p.mode
    x.note = p.note
    await audit(db, e.id, 'attendance_started', 'attendance', x.id, {'mode': p.mode}, request)
    await db.commit()
    return {'ok': True, 'started_at': x.started_at, 'mode': x.mode}

@router.post('/attendance/finish')
async def finish_attendance(request: Request, e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    today = datetime.now(timezone.utc).date().isoformat()
    x = await db.scalar(select(AttendanceRecord).where(AttendanceRecord.employee_id == e.id, AttendanceRecord.work_date == today, AttendanceRecord.finished_at.is_(None)))
    if not x or not x.started_at:
        raise HTTPException(400, 'Avval ishni boshlang')
    x.finished_at = datetime.now(timezone.utc)
    await audit(db, e.id, 'attendance_finished', 'attendance', x.id, {}, request)
    await db.commit()
    return {'ok': True, 'finished_at': x.finished_at}

@router.get('/attendance')
async def attendance(e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    q = select(AttendanceRecord).order_by(AttendanceRecord.id.desc()).limit(200)
    if not set(e.role_codes) & {'SUPER_ADMIN', 'CEO', 'COO'}:
        q = q.where(AttendanceRecord.employee_id == e.id)
    rows = (await db.scalars(q)).all()
    return [{'id': r.id, 'employee_id': r.employee_id, 'work_date': r.work_date, 'started_at': r.started_at, 'finished_at': r.finished_at, 'mode': r.mode, 'note': r.note} for r in rows]

@router.post('/leave-requests')
async def create_leave(p: LeaveCreate, e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    if p.end_at <= p.start_at:
        raise HTTPException(400, 'Tugash vaqti keyin bo‘lishi kerak')
    x = LeaveRequest(employee_id=e.id, **p.model_dump())
    db.add(x)
    admins = (await db.scalars(select(Employee).where(Employee.status == 'active'))).all()
    for a in admins:
        if set(a.role_codes) & {'SUPER_ADMIN', 'CEO', 'COO'}:
            db.add(Notification(employee_id=a.id, title='Ruxsat so‘rovi', body=f'{e.full_name}: {p.reason}', kind='approval'))
    await db.commit()
    return {'id': x.id, 'status': x.status}

@router.get('/leave-requests')
async def leaves(e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    q = select(LeaveRequest).order_by(LeaveRequest.created_at.desc()).limit(200)
    if not set(e.role_codes) & {'SUPER_ADMIN', 'CEO', 'COO'}:
        q = q.where(LeaveRequest.employee_id == e.id)
    rows = (await db.scalars(q)).all()
    return [{'id': x.id, 'employee_id': x.employee_id, 'start_at': x.start_at, 'end_at': x.end_at, 'reason': x.reason, 'status': x.status, 'created_at': x.created_at} for x in rows]

@router.post('/leave-requests/{ident}/decision')
async def decide_leave(ident: int, p: LeaveDecision, request: Request, e: Employee=Depends(current_employee), db: AsyncSession=Depends(get_db)):
    ensure_roles(e, {'SUPER_ADMIN', 'CEO', 'COO'})
    ensure_confirmed(request)
    x = await db.get(LeaveRequest, ident)
    if not x:
        raise HTTPException(404, 'So‘rov topilmadi')
    x.status = 'approved' if p.decision == 'approve' else 'rejected'
    x.reviewed_by_id = e.id
    await audit(db, e.id, 'leave_decision', 'leave_request', x.id, {'status': x.status}, request)
    await db.commit()
    return {'id': x.id, 'status': x.status}
