"""Premium feature routes - free agent recommendations and pickup suggestions."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_premium, user_to_dict
from app.models import User
from app.services.league_context import LeagueContext
from app.templating import render_partial, templates

# Router-level gate so any route added here is premium-only by default
router = APIRouter(prefix="/premium", tags=["premium"], dependencies=[Depends(require_premium)])


@router.get("/fa-recs")
def fa_recs_page(request: Request, user: User = Depends(require_premium)):
    """Full page for free agent recommendations."""
    return templates.TemplateResponse("fa_recs.html", {"request": request, "user": user_to_dict(user)})


@router.get("/fa-recs-data")
def fa_recs_data(request: Request, user: User = Depends(require_premium), db: Session = Depends(get_db)):
    """HTMX partial returning free agent recommendations."""
    def build():
        ctx = LeagueContext(user, db)
        return {
            "recommendations": ctx.fa_finder.recommend_pickups(10),
            "weaknesses": ctx.team_analyzer.identify_weaknesses(),
        }

    return render_partial(
        request, "partials/fa_recommendations.html", build,
        {"recommendations": [], "weaknesses": []},
    )


@router.get("/pickups")
def pickups_page(request: Request, user: User = Depends(require_premium)):
    """Full page for pickup suggestions."""
    return templates.TemplateResponse("pickups.html", {"request": request, "user": user_to_dict(user)})


@router.get("/pickups-data")
def pickups_data(request: Request, user: User = Depends(require_premium), db: Session = Depends(get_db)):
    """HTMX partial returning pickup/drop suggestions."""
    def build():
        return LeagueContext(user, db).fa_finder.get_pickup_suggestions(5)

    return render_partial(
        request, "partials/pickup_suggestions.html", build,
        {"pickups": [], "drops": [], "weaknesses": []},
    )
