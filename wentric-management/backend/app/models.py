from datetime import datetime, timezone
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, Text, Table, Column, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

def utcnow():
    return datetime.now(timezone.utc)
roles_link = Table('employee_roles', Base.metadata, Column('employee_id', ForeignKey('employees.id', ondelete='CASCADE'), primary_key=True), Column('role_id', ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True))

class Role(Base):
    __tablename__ = 'roles'
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name_uz: Mapped[str] = mapped_column(String(120))
    employees: Mapped[list['Employee']] = relationship(secondary=roles_link, back_populates='roles')

class Employee(Base):
    __tablename__ = 'employees'
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True, nullable=True)
    full_name: Mapped[str] = mapped_column(String(180))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    position: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default='active', index=True)
    work_mode: Mapped[str] = mapped_column(String(24), default='hybrid')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    terminated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    roles: Mapped[list[Role]] = relationship(secondary=roles_link, back_populates='employees', lazy='selectin')

    @property
    def role_codes(self):
        return [r.code for r in self.roles]

class UserSession(Base):
    __tablename__ = 'user_sessions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey('employees.id', ondelete='CASCADE'), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

class Project(Base):
    __tablename__ = 'projects'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    department: Mapped[str] = mapped_column(String(32), default='general', index=True)
    status: Mapped[str] = mapped_column(String(24), default='active', index=True)
    lead_id: Mapped[int | None] = mapped_column(ForeignKey('employees.id', ondelete='SET NULL'), nullable=True)
    budget_uzs: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class ProjectMember(Base):
    __tablename__ = 'project_members'
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id', ondelete='CASCADE'), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey('employees.id', ondelete='CASCADE'), index=True)
    membership_role: Mapped[str] = mapped_column(String(40), default='member')

class Task(Base):
    __tablename__ = 'tasks'
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(240), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey('projects.id', ondelete='SET NULL'), nullable=True, index=True)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey('employees.id', ondelete='SET NULL'), nullable=True, index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey('employees.id', ondelete='RESTRICT'))
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    priority: Mapped[str] = mapped_column(String(20), default='normal')
    status: Mapped[str] = mapped_column(String(24), default='new', index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class TaskReview(Base):
    __tablename__ = 'task_reviews'
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey('tasks.id', ondelete='CASCADE'), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey('employees.id', ondelete='RESTRICT'))
    decision: Mapped[str] = mapped_column(String(24))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class WorkSchedule(Base):
    __tablename__ = 'work_schedules'
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey('employees.id', ondelete='CASCADE'), index=True)
    weekday: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[str] = mapped_column(String(5), default='09:00')
    end_time: Mapped[str] = mapped_column(String(5), default='18:00')
    work_mode: Mapped[str] = mapped_column(String(24), default='hybrid')
    timezone: Mapped[str] = mapped_column(String(64), default='Asia/Tashkent')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class AttendanceRecord(Base):
    __tablename__ = 'attendance_records'
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey('employees.id', ondelete='RESTRICT'), index=True)
    work_date: Mapped[str] = mapped_column(String(10), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mode: Mapped[str] = mapped_column(String(24), default='remote')
    source: Mapped[str] = mapped_column(String(24), default='telegram')
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

class LeaveRequest(Base):
    __tablename__ = 'leave_requests'
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey('employees.id', ondelete='RESTRICT'), index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default='pending', index=True)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey('employees.id', ondelete='SET NULL'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class FinancialTransaction(Base):
    __tablename__ = 'financial_transactions'
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(12), index=True)
    amount_uzs: Mapped[float] = mapped_column(Numeric(16, 2))
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey('projects.id', ondelete='SET NULL'), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default='pending', index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey('employees.id', ondelete='RESTRICT'))
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey('employees.id', ondelete='SET NULL'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class EmployeeCard(Base):
    __tablename__ = 'employee_cards'
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey('employees.id', ondelete='RESTRICT'), index=True)
    card_number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    qr_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    qr_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default='pending', index=True)
    issued_by_id: Mapped[int] = mapped_column(ForeignKey('employees.id', ondelete='RESTRICT'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey('employees.id', ondelete='SET NULL'), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

class SecurityEvent(Base):
    __tablename__ = 'security_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    severity: Mapped[str] = mapped_column(String(24), default='info')
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Notification(Base):
    __tablename__ = 'notifications'
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey('employees.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(240))
    body: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(40), default='info')
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Announcement(Base):
    __tablename__ = 'announcements'
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(240))
    body: Mapped[str] = mapped_column(Text)
    audience: Mapped[str] = mapped_column(String(40), default='all')
    created_by_id: Mapped[int] = mapped_column(ForeignKey('employees.id', ondelete='RESTRICT'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Meeting(Base):
    __tablename__ = 'meetings'
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    location: Mapped[str | None] = mapped_column(String(240), nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey('employees.id', ondelete='RESTRICT'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class KnowledgeArticle(Base):
    __tablename__ = 'knowledge_articles'
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(240), index=True)
    body: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(120), default='umumiy')
    created_by_id: Mapped[int] = mapped_column(ForeignKey('employees.id', ondelete='RESTRICT'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class Suggestion(Base):
    __tablename__ = 'suggestions'
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey('employees.id', ondelete='RESTRICT'), index=True)
    title: Mapped[str] = mapped_column(String(240))
    body: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(24), default='suggestion')
    status: Mapped[str] = mapped_column(String(24), default='new', index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class FileAsset(Base):
    __tablename__ = 'files'
    id: Mapped[int] = mapped_column(primary_key=True)
    original_name: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(255), unique=True)
    content_type: Mapped[str] = mapped_column(String(120), default='application/octet-stream')
    size_bytes: Mapped[int] = mapped_column(Integer)
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey('employees.id', ondelete='RESTRICT'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class InviteCode(Base):
    __tablename__ = 'invite_codes'
    id: Mapped[int] = mapped_column(primary_key=True)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    code_suffix: Mapped[str] = mapped_column(String(12))
    max_uses: Mapped[int] = mapped_column(Integer, default=1)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey('employees.id', ondelete='RESTRICT'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class EmployeeRating(Base):
    __tablename__ = 'employee_ratings'
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey('employees.id', ondelete='RESTRICT'), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey('employees.id', ondelete='RESTRICT'), index=True)
    score: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class EmployeeApplication(Base):
    __tablename__ = 'employee_applications'
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    full_name: Mapped[str] = mapped_column(String(180))
    department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    desired_position: Mapped[str | None] = mapped_column(String(120), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    invite_code_id: Mapped[int | None] = mapped_column(ForeignKey('invite_codes.id', ondelete='SET NULL'), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default='pending', index=True)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey('employees.id', ondelete='SET NULL'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
