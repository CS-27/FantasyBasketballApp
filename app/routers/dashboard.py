"""Main dashboard routes."""

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates

from app.dependencies import require_user, user_to_dict
from app.models import User

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/dashboard")
def dashboard(request: Request, user: User = Depends(require_user)):
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "user": user_to_dict(user)},
    )
