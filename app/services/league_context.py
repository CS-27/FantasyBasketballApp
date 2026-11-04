"""Builds the Yahoo league/team objects and analyzers for a logged-in user."""

import time

import yahoo_fantasy_api as yfa
from sqlalchemy.orm import Session

from app.config import STATIC_CACHE_TTL
from app.models import User, UserLeague
from app.services.cache import DataCache
from app.services.free_agent_finder import FreeAgentFinder
from app.services.league_analyzer import LeagueAnalyzer
from app.services.team_analyzer import TeamAnalyzer
from app.services.yahoo_client import WebOAuthContext


class NoLeagueError(Exception):
    """Raised when the user has no NBA fantasy league."""


# Current NBA game ID (changes each season), shared across users: (game_id, fetched_at)
_current_game = {"id": None, "fetched_at": 0.0}


def _current_game_id(game) -> str:
    if not _current_game["id"] or time.time() - _current_game["fetched_at"] > STATIC_CACHE_TTL:
        _current_game["id"] = str(game.game_id())
        _current_game["fetched_at"] = time.time()
    return _current_game["id"]


class LeagueContext:
    """Everything a route needs to analyze the user's league.

    Analyzers are created lazily and share one DataCache, so repeated
    page loads within CACHE_TTL don't hit the Yahoo API.
    """

    def __init__(self, user: User, db: Session):
        self.user = user
        self.db = db

        self.oauth = WebOAuthContext(user.access_token, user.refresh_token)
        self.oauth.refresh_if_needed(db, user)
        self.game = yfa.Game(self.oauth, "nba")

        self.league_id, self.team_key = self._get_user_league()
        if not self.league_id:
            raise NoLeagueError("No league found for the current NBA season.")

        self.league = self.game.to_league(self.league_id)
        self.cache = DataCache(db, user.id, self.league_id)

        self._league_analyzer = None
        self._team_analyzer = None
        self._fa_finder = None

    def _get_user_league(self):
        """Get the user's active league info from DB, or discover it from Yahoo.

        League IDs are prefixed with the season's game ID ("466.l.55263"), so a
        stored league from a past season is retired and rediscovered.
        """
        user_league = (
            self.db.query(UserLeague)
            .filter(UserLeague.user_id == self.user.id, UserLeague.is_active == True)
            .first()
        )
        if user_league:
            if user_league.league_id.split(".")[0] == _current_game_id(self.game):
                return user_league.league_id, user_league.team_key
            user_league.is_active = False
            self.db.commit()

        current = _current_game_id(self.game)
        league_ids = [lid for lid in self.game.league_ids() if lid.startswith(current + ".")]
        if not league_ids:
            return None, None

        league_id = league_ids[-1]
        team_key = self.game.to_league(league_id).team_key()

        self.db.add(UserLeague(user_id=self.user.id, league_id=league_id, team_key=team_key))
        self.db.commit()

        return league_id, team_key

    @property
    def league_analyzer(self) -> LeagueAnalyzer:
        if self._league_analyzer is None:
            self._league_analyzer = LeagueAnalyzer(self.league, cache=self.cache)
        return self._league_analyzer

    @property
    def team_analyzer(self) -> TeamAnalyzer:
        if self._team_analyzer is None:
            team = self.league.to_team(self.team_key)
            self._team_analyzer = TeamAnalyzer(team, self.league, self.league_analyzer, cache=self.cache)
        return self._team_analyzer

    @property
    def fa_finder(self) -> FreeAgentFinder:
        if self._fa_finder is None:
            self._fa_finder = FreeAgentFinder(self.league, self.team_analyzer, cache=self.cache)
        return self._fa_finder
