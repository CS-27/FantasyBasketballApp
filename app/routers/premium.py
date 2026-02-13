"""Premium feature routes - free agent recommendations and pickup suggestions."""

import logging

import yahoo_fantasy_api as yfa
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_user
from app.models import User, UserLeague
from app.services.free_agent_finder import FreeAgentFinder
from app.services.league_analyzer import LeagueAnalyzer
from app.services.team_analyzer import TeamAnalyzer
from app.services.yahoo_client import WebOAuthContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/premium", tags=["premium"])
templates = Jinja2Templates(directory="app/templates")


def _get_user_league(user: User, db: Session):
    """Get the user's active league info from DB, or discover it from Yahoo."""
    user_league = (
        db.query(UserLeague)
        .filter(UserLeague.user_id == user.id, UserLeague.is_active == True)
        .first()
    )
    if user_league:
        return user_league.league_id, user_league.team_key

    # Discover leagues from Yahoo API
    ctx = WebOAuthContext(user.access_token, user.refresh_token)
    ctx.refresh_if_needed(db, user)
    game = yfa.Game(ctx, "nba")
    league_ids = game.league_ids()

    if not league_ids:
        return None, None

    league_id = league_ids[-1]  # Most recent league
    league = game.to_league(league_id)
    team_key = league.team_key()

    # Store for future use
    user_league = UserLeague(
        user_id=user.id,
        league_id=league_id,
        team_key=team_key,
    )
    db.add(user_league)
    db.commit()

    return league_id, team_key


@router.get("/fa-recs")
async def fa_recs_page(
    request: Request,
    user: User | None = Depends(get_current_user),
):
    """Full page for free agent recommendations."""
    if not user:
        return RedirectResponse("/auth/login")

    return templates.TemplateResponse(
        "fa_recs.html",
        {"request": request, "user": {"display_name": user.display_name, "subscription_status": user.subscription_status}},
    )


@router.get("/fa-recs-data")
async def fa_recs_data(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """HTMX partial returning free agent recommendations."""
    if not user:
        return RedirectResponse("/auth/login")

    try:
        league_id, team_key = _get_user_league(user, db)
        if not league_id:
            return templates.TemplateResponse(
                "partials/fa_recommendations.html",
                {"request": request, "recommendations": [], "weaknesses": [], "error": "No league found."},
            )

        ctx = WebOAuthContext(user.access_token, user.refresh_token)
        ctx.refresh_if_needed(db, user)
        game = yfa.Game(ctx, "nba")
        league = game.to_league(league_id)
        team = league.to_team(team_key)

        league_analyzer = LeagueAnalyzer(league)
        team_analyzer = TeamAnalyzer(team, league, league_analyzer)
        fa_finder = FreeAgentFinder(league, team_analyzer)

        recommendations = fa_finder.recommend_pickups(10)
        weaknesses = team_analyzer.identify_weaknesses()

        return templates.TemplateResponse(
            "partials/fa_recommendations.html",
            {
                "request": request,
                "recommendations": recommendations,
                "weaknesses": weaknesses,
            },
        )
    except Exception as e:
        logger.exception("Error fetching FA recommendations")
        return templates.TemplateResponse(
            "partials/fa_recommendations.html",
            {"request": request, "recommendations": [], "weaknesses": [], "error": str(e)},
        )


@router.get("/pickups")
async def pickups_page(
    request: Request,
    user: User | None = Depends(get_current_user),
):
    """Full page for pickup suggestions."""
    if not user:
        return RedirectResponse("/auth/login")

    return templates.TemplateResponse(
        "pickups.html",
        {"request": request, "user": {"display_name": user.display_name, "subscription_status": user.subscription_status}},
    )


@router.get("/pickups-data")
async def pickups_data(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """HTMX partial returning pickup/drop suggestions."""
    if not user:
        return RedirectResponse("/auth/login")

    try:
        league_id, team_key = _get_user_league(user, db)
        if not league_id:
            return templates.TemplateResponse(
                "partials/pickup_suggestions.html",
                {"request": request, "pickups": [], "drops": [], "weaknesses": [], "error": "No league found."},
            )

        ctx = WebOAuthContext(user.access_token, user.refresh_token)
        ctx.refresh_if_needed(db, user)
        game = yfa.Game(ctx, "nba")
        league = game.to_league(league_id)
        team = league.to_team(team_key)

        league_analyzer = LeagueAnalyzer(league)
        team_analyzer = TeamAnalyzer(team, league, league_analyzer)
        fa_finder = FreeAgentFinder(league, team_analyzer)

        suggestions = fa_finder.get_pickup_suggestions(5)

        return templates.TemplateResponse(
            "partials/pickup_suggestions.html",
            {
                "request": request,
                "pickups": suggestions["pickups"],
                "drops": suggestions["drops"],
                "weaknesses": suggestions["weaknesses"],
            },
        )
    except Exception as e:
        logger.exception("Error fetching pickup suggestions")
        return templates.TemplateResponse(
            "partials/pickup_suggestions.html",
            {"request": request, "pickups": [], "drops": [], "weaknesses": [], "error": str(e)},
        )
