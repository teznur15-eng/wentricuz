from sqlalchemy import select
from app.database import Base, engine, SessionLocal
from app import models
from app.models import Role
ROLE_SEEDS = [('SUPER_ADMIN', 'Super Admin'), ('CEO', 'Bosh direktor'), ('CTO', 'Texnik direktor'), ('COO', 'Operatsion direktor'), ('PROJECT_LEADER', 'Loyiha rahbari'), ('EMPLOYEE', 'Xodim')]

async def initialize_database():
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    async with SessionLocal() as db:
        existing = set((await db.scalars(select(Role.code))).all())
        for code, name in ROLE_SEEDS:
            if code not in existing:
                db.add(Role(code=code, name_uz=name))
        await db.commit()
