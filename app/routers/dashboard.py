"""Main dashboard routes."""

from fastapi import APIRouter, Depends, Request

from app.dependencies import require_user, user_to_dict
from app.models import User
from app.templating import templates

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard(request: Request, user: User = Depends(require_user)):
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "user": user_to_dict(user)},
    )
