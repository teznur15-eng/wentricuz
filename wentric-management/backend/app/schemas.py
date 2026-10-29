from datetime import datetime
from pydantic import BaseModel, Field

class TelegramLogin(BaseModel):
    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str

class EmployeeCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=180)
    telegram_id: int | None = None
    department: str | None = None
    position: str | None = None
    phone: str | None = None
    email: str | None = None
    role_codes: list[str] = ['EMPLOYEE']

class StatusUpdate(BaseModel):
    status: str

class AppDecision(BaseModel):
    decision: str = Field(pattern='^(approve|reject)$')
    role_codes: list[str] = ['EMPLOYEE']

class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    description: str | None = None
    department: str = Field(default='general', pattern='^(technical|operations|general)$')
    lead_id: int | None = None
    budget_uzs: float = Field(default=0, ge=0)
    deadline: datetime | None = None

class TaskCreate(BaseModel):
    title: str = Field(min_length=2, max_length=240)
    description: str | None = None
    project_id: int | None = None
    assignee_id: int | None = None
    deadline: datetime | None = None
    priority: str = 'normal'

class TaskStatus(BaseModel):
    status: str = Field(pattern='^(new|in_progress|review|done|blocked)$')
    progress: int | None = Field(default=None, ge=0, le=100)

class AttendanceStart(BaseModel):
    mode: str = Field(default='remote', pattern='^(office|remote)$')
    note: str | None = None

class LeaveCreate(BaseModel):
    start_at: datetime
    end_at: datetime
    reason: str = Field(min_length=2, max_length=3000)

class LeaveDecision(BaseModel):
    decision: str = Field(pattern='^(approve|reject)$')

class FinanceCreate(BaseModel):
    kind: str = Field(pattern='^(income|expense)$')
    amount_uzs: float = Field(gt=0)
    title: str = Field(min_length=2, max_length=240)
    description: str | None = None
    project_id: int | None = None

class FinanceDecision(BaseModel):
    decision: str = Field(pattern='^(approve|reject)$')
    comment: str | None = None

class CardIssue(BaseModel):
    employee_id: int

class CardDecision(BaseModel):
    decision: str = Field(pattern='^(approve|reject)$')

class CardVerify(BaseModel):
    token: str = Field(min_length=10, max_length=200)

class AnnouncementCreate(BaseModel):
    title: str
    body: str
    audience: str = 'all'

class MeetingCreate(BaseModel):
    title: str
    description: str | None = None
    starts_at: datetime
    ends_at: datetime
    location: str | None = None

class KnowledgeCreate(BaseModel):
    title: str
    body: str
    category: str = 'umumiy'

class SuggestionCreate(BaseModel):
    title: str
    body: str
    kind: str = Field(default='suggestion', pattern='^(suggestion|problem)$')

class SuggestionStatus(BaseModel):
    status: str = Field(pattern='^(new|reviewing|resolved|rejected)$')

class ApplicationCreate(BaseModel):
    telegram_id: int
    full_name: str
    department: str | None = None
    desired_position: str | None = None
    message: str | None = None
    invite_code: str | None = None

class InviteCreate(BaseModel):
    max_uses: int = Field(default=1, ge=1, le=1000)
    expires_at: datetime | None = None

class RatingCreate(BaseModel):
    employee_id: int
    score: int = Field(ge=1, le=5)
    comment: str | None = None

class WorkScheduleCreate(BaseModel):
    employee_id: int
    weekday: int = Field(ge=0, le=6)
    start_time: str = Field(default='09:00', pattern='^([01][0-9]|2[0-3]):[0-5][0-9]$')
    end_time: str = Field(default='18:00', pattern='^([01][0-9]|2[0-3]):[0-5][0-9]$')
    work_mode: str = Field(default='hybrid', pattern='^(office|remote|hybrid)$')
    timezone: str = 'Asia/Tashkent'

class RoleUpdate(BaseModel):
    role_codes: list[str] = Field(min_length=1)
