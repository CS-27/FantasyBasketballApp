"""Analysis feature routes - standings, team analysis, comparison, rankings.

Data endpoints are plain `def` (not `async def`) because the Yahoo client is
blocking; FastAPI runs them in a threadpool so they don't stall the server.
"""

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_user, user_to_dict
from app.models import User
from app.services.league_context import LeagueContext, NoLeagueError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])
templates = Jinja2Templates(directory="app/templates")


def render_partial(request: Request, template: str, build, defaults: dict):
    """Render an HTMX partial, turning failures into an inline error message.

    `build` returns the template context; `defaults` fills the context when
    it fails so the template can still render.
    """
    try:
        context = build()
    except NoLeagueError as e:
        context = {**defaults, "error": str(e)}
    except Exception as e:
        logger.exception("Error rendering %s", template)
        context = {**defaults, "error": str(e)}
    return templates.TemplateResponse(template, {"request": request, **context})


def _page(request: Request, template: str, user: User):
    return templates.TemplateResponse(template, {"request": request, "user": user_to_dict(user)})


@router.get("/standings")
def standings_page(request: Request, user: User = Depends(require_user)):
    """Full standings page (loads detail via HTMX)."""
    return _page(request, "standings.html", user)


@router.get("/standings-data")
def standings_data(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Return standings partial (loaded via HTMX)."""
    def build():
        ctx = LeagueContext(user, db)
        return {"standings": ctx.league_analyzer.get_standings_display()}

    return render_partial(request, "partials/standings.html", build, {"standings": []})


@router.get("/team")
def team_page(request: Request, user: User = Depends(require_user)):
    """Full team analysis page (loads detail via HTMX)."""
    return _page(request, "team_analysis.html", user)


@router.get("/team-data")
def team_data(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Return team analysis partial (loaded via HTMX)."""
    def build():
        team_analyzer = LeagueContext(user, db).team_analyzer
        return {
            "rankings": team_analyzer.get_category_rankings(),
            "strengths": team_analyzer.identify_strengths(),
            "weaknesses": team_analyzer.identify_weaknesses(),
        }

    return render_partial(request, "partials/team_analysis.html", build, {})


@router.get("/comparison")
def comparison_page(request: Request, user: User = Depends(require_user)):
    """League comparison page (loads detail via HTMX)."""
    return _page(request, "comparison.html", user)


@router.get("/comparison-data")
def comparison_data(
    request: Request,
    opponent: str = "",
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Return comparison partial: vs league average (free) and vs an opponent (premium)."""
    is_premium = user.subscription_status == "premium"

    def build():
        ctx = LeagueContext(user, db)
        team_analyzer = ctx.team_analyzer
        team_stats = ctx.league_analyzer.get_team_stats()

        opponents = sorted(
            ({"team_key": key, "name": data["name"]} for key, data in team_stats.items()
             if key != ctx.team_key),
            key=lambda o: o["name"],
        )

        head_to_head = None
        if opponent and is_premium and opponent in team_stats:
            head_to_head = team_analyzer.compare_to_opponent(opponent)

        return {
            "comparison": team_analyzer.get_comparison_to_league_avg(),
            "opponents": opponents,
            "selected_opponent": opponent,
            "head_to_head": head_to_head,
            "is_premium": is_premium,
        }

    return render_partial(
        request, "partials/comparison.html", build,
        {"comparison": {}, "opponents": [], "selected_opponent": opponent,
         "head_to_head": None, "is_premium": is_premium},
    )


@router.get("/rankings")
def rankings_page(request: Request, user: User = Depends(require_user)):
    """Category rankings page."""
    return _page(request, "rankings.html", user)


@router.get("/rankings-data")
def rankings_data(
    request: Request,
    category: str = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Return category rankings partial (loaded via HTMX)."""
    def build():
        analyzer = LeagueContext(user, db).league_analyzer
        team_stats = analyzer.get_team_stats()
        if category:
            rankings = analyzer.rank_teams_by_category(team_stats, category)
        else:
            rankings = analyzer.get_category_rankings_matrix(team_stats)
        return {
            "categories": analyzer.get_category_names(),
            "selected_category": category,
            "rankings": rankings,
        }

    return render_partial(
        request, "partials/category_rankings.html", build,
        {"categories": [], "selected_category": None, "rankings": {}},
    )


@router.post("/refresh")
def refresh(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Clear cached Yahoo data so the next load fetches fresh stats."""
    try:
        LeagueContext(user, db).cache.clear()
    except NoLeagueError:
        pass
    return Response(status_code=204, headers={"HX-Refresh": "true"})
