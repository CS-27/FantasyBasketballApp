"""Builds the Yahoo league/team objects and analyzers for a logged-in user."""

import yahoo_fantasy_api as yfa
from sqlalchemy.orm import Session

from app.models import User, UserLeague
from app.services.cache import DataCache
from app.services.free_agent_finder import FreeAgentFinder
from app.services.league_analyzer import LeagueAnalyzer
from app.services.team_analyzer import TeamAnalyzer
from app.services.yahoo_client import WebOAuthContext


class NoLeagueError(Exception):
    """Raised when the user has no NBA fantasy league."""


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
            raise NoLeagueError("No league found.")

        self.league = self.game.to_league(self.league_id)
        self.cache = DataCache(db, user.id, self.league_id)

        self._league_analyzer = None
        self._team_analyzer = None
        self._fa_finder = None

    def _get_user_league(self):
        """Get the user's active league info from DB, or discover it from Yahoo."""
        user_league = (
            self.db.query(UserLeague)
            .filter(UserLeague.user_id == self.user.id, UserLeague.is_active == True)
            .first()
        )
        if user_league:
            return user_league.league_id, user_league.team_key

        league_ids = self.game.league_ids()
        if not league_ids:
            return None, None

        league_id = league_ids[-1]  # Most recent league
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
