"""Analysis feature routes - standings, team analysis, comparison, rankings."""

import logging

import yahoo_fantasy_api as yfa
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User, UserLeague
from app.services.league_analyzer import LeagueAnalyzer
from app.services.team_analyzer import TeamAnalyzer
from app.services.yahoo_client import WebOAuthContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])
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


@router.get("/standings")
async def standings(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return standings partial (loaded via HTMX from dashboard)."""
    if not user:
        return RedirectResponse("/auth/login")

    try:
        league_id, _ = _get_user_league(user, db)
        if not league_id:
            return templates.TemplateResponse(
                "partials/standings.html",
                {"request": request, "standings": [], "error": "No league found."},
            )

        ctx = WebOAuthContext(user.access_token, user.refresh_token)
        ctx.refresh_if_needed(db, user)
        game = yfa.Game(ctx, "nba")
        league = game.to_league(league_id)

        analyzer = LeagueAnalyzer(league)
        standings_data = analyzer.get_standings_display()

        return templates.TemplateResponse(
            "partials/standings.html",
            {"request": request, "standings": standings_data},
        )
    except Exception as e:
        logger.exception("Error fetching standings")
        return templates.TemplateResponse(
            "partials/standings.html",
            {"request": request, "standings": [], "error": str(e)},
        )


@router.get("/team")
async def team_page(
    request: Request,
    user: User | None = Depends(get_current_user),
):
    """Full team analysis page (loads detail via HTMX)."""
    if not user:
        return RedirectResponse("/auth/login")

    return templates.TemplateResponse(
        "team_analysis.html",
        {"request": request, "user": {"display_name": user.display_name, "subscription_status": user.subscription_status}},
    )


@router.get("/team-data")
async def team_data(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return team analysis partial (loaded via HTMX)."""
    if not user:
        return RedirectResponse("/auth/login")

    try:
        league_id, team_key = _get_user_league(user, db)
        if not league_id:
            return templates.TemplateResponse(
                "partials/team_analysis.html",
                {"request": request, "error": "No league found."},
            )

        ctx = WebOAuthContext(user.access_token, user.refresh_token)
        ctx.refresh_if_needed(db, user)
        game = yfa.Game(ctx, "nba")
        league = game.to_league(league_id)
        team = league.to_team(team_key)

        league_analyzer = LeagueAnalyzer(league)
        team_analyzer = TeamAnalyzer(team, league, league_analyzer)

        rankings = team_analyzer.get_category_rankings()
        strengths = team_analyzer.identify_strengths()
        weaknesses = team_analyzer.identify_weaknesses()

        return templates.TemplateResponse(
            "partials/team_analysis.html",
            {
                "request": request,
                "rankings": rankings,
                "strengths": strengths,
                "weaknesses": weaknesses,
            },
        )
    except Exception as e:
        logger.exception("Error fetching team data")
        return templates.TemplateResponse(
            "partials/team_analysis.html",
            {"request": request, "error": str(e)},
        )


@router.get("/comparison")
async def comparison(
    request: Request,
    user: User | None = Depends(get_current_user),
):
    """League comparison page (placeholder)."""
    if not user:
        return RedirectResponse("/auth/login")

    return templates.TemplateResponse(
        "comparison.html",
        {"request": request, "user": {"display_name": user.display_name, "subscription_status": user.subscription_status}},
    )


@router.get("/rankings")
async def rankings_page(
    request: Request,
    user: User | None = Depends(get_current_user),
):
    """Category rankings page."""
    if not user:
        return RedirectResponse("/auth/login")

    return templates.TemplateResponse(
        "rankings.html",
        {"request": request, "user": {"display_name": user.display_name, "subscription_status": user.subscription_status}},
    )


@router.get("/rankings-data")
async def rankings_data(
    request: Request,
    category: str = None,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return category rankings partial (loaded via HTMX)."""
    if not user:
        return RedirectResponse("/auth/login")

    try:
        league_id, _ = _get_user_league(user, db)
        if not league_id:
            return templates.TemplateResponse(
                "partials/category_rankings.html",
                {"request": request, "categories": [], "selected_category": None, "rankings": {}, "error": "No league found."},
            )

        ctx = WebOAuthContext(user.access_token, user.refresh_token)
        ctx.refresh_if_needed(db, user)
        game = yfa.Game(ctx, "nba")
        league = game.to_league(league_id)

        analyzer = LeagueAnalyzer(league)
        categories = analyzer.get_category_names()
        team_stats = analyzer.get_team_stats()

        if category:
            rankings = analyzer.rank_teams_by_category(team_stats, category)
        else:
            rankings = analyzer.get_category_rankings_matrix(team_stats)

        return templates.TemplateResponse(
            "partials/category_rankings.html",
            {
                "request": request,
                "categories": categories,
                "selected_category": category,
                "rankings": rankings,
            },
        )
    except Exception as e:
        logger.exception("Error fetching category rankings")
        return templates.TemplateResponse(
            "partials/category_rankings.html",
            {"request": request, "categories": [], "selected_category": None, "rankings": {}, "error": str(e)},
        )
