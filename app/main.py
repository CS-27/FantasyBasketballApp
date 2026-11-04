"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import SECRET_KEY
from app.database import init_db, SessionLocal
from app.dependencies import user_to_dict
from app.models import User
from app.routers import auth, billing, dashboard, analysis, premium
from app.templating import templates


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Yahoo Fantasy Basketball Analyzer", lifespan=lifespan)

# Session middleware for OAuth state and user sessions
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include routers
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(analysis.router)
app.include_router(premium.router)
app.include_router(billing.router)


@app.get("/")
async def landing(request: Request):
    user_id = request.session.get("user_id")
    if user_id:
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                return templates.TemplateResponse("dashboard.html", {"request": request, "user": user_to_dict(user)})
        finally:
            db.close()
    return templates.TemplateResponse("landing.html", {"request": request})
