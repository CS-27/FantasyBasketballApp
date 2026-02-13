"""Main dashboard routes."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.dependencies import get_current_user
from app.models import User

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")


def user_to_dict(user: User) -> dict:
    """Convert SQLAlchemy User model to a template-friendly dict."""
    return {
        "id": user.id,
        "display_name": user.display_name,
        "subscription_status": user.subscription_status,
    }


@router.get("/dashboard")
async def dashboard(request: Request, user: User | None = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/auth/login")
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "user": user_to_dict(user)},
    )
