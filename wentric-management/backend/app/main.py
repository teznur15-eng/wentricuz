from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.bootstrap import initialize_database
from app.routes import auth, work, admin, workspace, bot

@asynccontextmanager
async def lifespan(app: FastAPI):
    await initialize_database()
    yield
app = FastAPI(title=settings.app_name, version='0.1.0', description='Wentric IT Group boshqaruv tizimi - mahalliy MVP', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[settings.web_origin, 'http://127.0.0.1:3000'], allow_credentials=True, allow_methods=['GET', 'POST', 'PATCH', 'PUT', 'DELETE', 'OPTIONS'], allow_headers=['Authorization', 'Content-Type', 'X-Bot-Secret', 'X-Confirm-Action'])
for r in [auth.router, work.router, admin.router, workspace.router, bot.router]:
    app.include_router(r, prefix='/api/v1')

@app.get('/health', tags=['Tizim'])
async def health():
    return {'status': 'ok', 'app': settings.app_name, 'environment': settings.environment}
