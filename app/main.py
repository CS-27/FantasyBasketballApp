"""FastAPI application entry point."""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.config import SECRET_KEY
from app.database import init_db, SessionLocal
from app.models import User
from app.routers import auth, dashboard, analysis

app = FastAPI(title="Yahoo Fantasy Basketball Analyzer")

# Session middleware for OAuth state and user sessions
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# Include routers
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(analysis.router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
async def landing(request: Request):
    user_id = request.session.get("user_id")
    if user_id:
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user_dict = {"display_name": user.display_name, "subscription_status": user.subscription_status}
                return templates.TemplateResponse("dashboard.html", {"request": request, "user": user_dict})
        finally:
            db.close()
    return templates.TemplateResponse("landing.html", {"request": request})
