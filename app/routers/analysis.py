"""Analysis feature routes - standings, team analysis, comparison, rankings.

Data endpoints are plain `def` (not `async def`) because the Yahoo client is
blocking; FastAPI runs them in a threadpool so they don't stall the server.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_user, user_to_dict
from app.models import User
from app.services.league_context import LeagueContext, NoLeagueError
from app.templating import render_partial, templates

router = APIRouter(prefix="/analysis", tags=["analysis"])


def _page(request: Request, template: str, user: User, **extra):
    return templates.TemplateResponse(template, {"request": request, "user": user_to_dict(user), **extra})


@router.get("/summary-data")
def summary_data(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Dashboard summary cards: rank, record, strength/weakness counts."""
    def build():
        ctx = LeagueContext(user, db)
        standings = ctx.league_analyzer.get_standings_display()
        mine = next((s for s in standings if s.get("team_key") == ctx.team_key), None)
        return {
            "standing": mine,
            "num_teams": len(standings),
            "strengths": ctx.team_analyzer.identify_strengths(),
            "weaknesses": ctx.team_analyzer.identify_weaknesses(),
        }

    return render_partial(
        request, "partials/summary.html", build,
        {"standing": None, "num_teams": 0, "strengths": [], "weaknesses": []},
    )


@router.get("/standings")
def standings_page(request: Request, user: User = Depends(require_user)):
    """Full standings page (loads detail via HTMX)."""
    return _page(request, "standings.html", user)


@router.get("/standings-data")
def standings_data(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Return standings partial (loaded via HTMX)."""
    def build():
        ctx = LeagueContext(user, db)
        return {"standings": ctx.league_analyzer.get_standings_display(), "my_team_key": ctx.team_key}

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
def comparison_page(request: Request, opponent: str = "", user: User = Depends(require_user)):
    """League comparison page (loads detail via HTMX).

    `opponent` is kept in the page URL so a selected matchup survives a
    refresh and can be bookmarked.
    """
    return _page(request, "comparison.html", user, opponent=opponent)


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
