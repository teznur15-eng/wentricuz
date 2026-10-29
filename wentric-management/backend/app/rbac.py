from fastapi import HTTPException, Request
from app.models import Employee

FINANCE_ROLES = {"SUPER_ADMIN", "CEO"}
MANAGERS = {"SUPER_ADMIN", "CEO", "CTO", "COO", "PROJECT_LEADER"}
TECHNICAL_MARKERS = (
    "technical", "tech", "development", "developer", "engineering", "engineer",
    "it", "cyber", "security", "qa", "pentest", "backend", "frontend", "ai", "ml",
    "texnik", "dasturlash", "kiber", "test", "infrastructure",
)
OPERATIONS_MARKERS = (
    "operations", "operation", "logistics", "hr", "human resources", "support",
    "office", "operats", "logistika", "kadr", "xo‘jalik", "xojalik", "administration",
)


def department_scope(value: str | None) -> str:
    normalized = (value or "").strip().casefold()
    if any(marker in normalized for marker in TECHNICAL_MARKERS):
        return "technical"
    if any(marker in normalized for marker in OPERATIONS_MARKERS):
        return "operations"
    return "general"


def role_scopes(employee: Employee) -> set[str]:
    roles = set(employee.role_codes)
    if roles & {"SUPER_ADMIN", "CEO"}:
        return {"all"}
    scopes: set[str] = set()
    if "CTO" in roles:
        scopes.add("technical")
    if "COO" in roles:
        scopes.add("operations")
    return scopes


def ensure_roles(employee: Employee, allowed: set[str]):
    if not (set(employee.role_codes) & allowed):
        raise HTTPException(403, "Bu amal uchun ruxsat mavjud emas")


def ensure_finance(employee: Employee):
    ensure_roles(employee, FINANCE_ROLES)


def ensure_confirmed(request: Request):
    if request.headers.get("x-confirm-action") != "confirmed":
        raise HTTPException(428, "Bu xavfli amal uchun qo‘shimcha tasdiqlash talab qilinadi")
