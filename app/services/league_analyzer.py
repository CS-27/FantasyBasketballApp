"""Core league analysis logic (migrated from CLI version)."""

import logging

from app.config import CATEGORIES, NEGATIVE_CATEGORIES, STATIC_CACHE_TTL
from app.services.cache import NullCache

logger = logging.getLogger(__name__)


def _parse_made_attempted(value):
    """Parse a Yahoo "made/attempted" string like "45/100" into floats."""
    try:
        made, attempted = str(value).split('/')
        return float(made), float(attempted)
    except ValueError:
        return 0.0, 0.0


def sum_player_stats(players, categories):
    """Total counting stats across players and compute team FG%/FT%.

    Percentages come from summed FGM/A and FTM/A, not averaged player
    percentages. Non-numeric values (Yahoo uses "-" for no stats) are skipped.
    """
    totals = {cat: 0 for cat in categories}
    fg_made = fg_att = ft_made = ft_att = 0.0

    for stats in players:
        for cat in categories:
            if cat in ('FG%', 'FT%'):
                continue
            try:
                totals[cat] += float(stats.get(cat))
            except (ValueError, TypeError):
                pass

        made, att = _parse_made_attempted(stats.get('FGM/A', ''))
        fg_made, fg_att = fg_made + made, fg_att + att
        made, att = _parse_made_attempted(stats.get('FTM/A', ''))
        ft_made, ft_att = ft_made + made, ft_att + att

    if fg_att > 0:
        totals['FG%'] = fg_made / fg_att
    if ft_att > 0:
        totals['FT%'] = ft_made / ft_att

    return totals


class LeagueAnalyzer:
    """Analyzes league-wide statistics and rankings."""

    def __init__(self, league, cache=None):
        self.league = league
        self.cache = cache or NullCache()
        self._settings = None
        self._standings = None
        self._teams = None
        self._stat_categories = None
        self._team_stats_cache = None

    @property
    def settings(self):
        """Get league settings (cached)."""
        if self._settings is None:
            self._settings = self.cache.get_or_fetch("settings", self.league.settings, STATIC_CACHE_TTL)
        return self._settings

    @property
    def stat_categories(self):
        """Get stat categories from league settings."""
        if self._stat_categories is None:
            self._stat_categories = self.cache.get_or_fetch(
                "stat_categories", self.league.stat_categories, STATIC_CACHE_TTL
            )
        return self._stat_categories

    def get_category_names(self):
        """Get the scoring category names used in this league.

        Display-only stats like FGM/A and FTM/A are excluded; they feed the
        FG%/FT% calculation but aren't categories teams compete in.
        """
        try:
            cats = self.stat_categories
            if cats:
                names = [cat.get('display_name', cat.get('name', '')) for cat in cats]
                return [name for name in names if name and '/' not in name]
        except Exception:
            pass
        return CATEGORIES

    def get_standings(self):
        """Get current league standings."""
        if self._standings is None:
            self._standings = self.cache.get_or_fetch("standings", self.league.standings)
        return self._standings

    def get_teams(self):
        """Get all teams in the league."""
        if self._teams is None:
            self._teams = self.cache.get_or_fetch("teams", self.league.teams, STATIC_CACHE_TTL)
        return self._teams

    def _fetch_team_roster_stats(self, team_key):
        """Fetch roster and player stats for a specific team."""
        categories = self.get_category_names()

        try:
            roster = self.league.to_team(team_key).roster()
            player_ids = [p.get('player_id') for p in roster or [] if p.get('player_id')]
            if not player_ids:
                return {cat: 0 for cat in categories}
            player_stats = self.league.player_stats(player_ids, 'season')
            return sum_player_stats(player_stats, categories)
        except Exception as e:
            logger.warning("Could not fetch stats for team %s: %s", team_key, e)
            return {cat: 0 for cat in categories}

    def get_team_stats(self):
        """Get stats for all teams in the league."""
        if self._team_stats_cache is None:
            self._team_stats_cache = self.cache.get_or_fetch("team_stats", self._fetch_all_team_stats)
        return self._team_stats_cache

    def _fetch_all_team_stats(self):
        """Fetch roster stats for every team (~2 API calls per team)."""
        teams = self.get_teams()
        team_stats = {}

        logger.info("Fetching team stats for %d teams...", len(teams))

        for i, (team_key, team_data) in enumerate(teams.items()):
            team_name = team_data.get('name', team_key)
            logger.debug("Loading %s (%d/%d)", team_name, i + 1, len(teams))

            stats = self._fetch_team_roster_stats(team_key)
            team_stats[team_key] = {
                'name': team_name,
                'stats': stats
            }

        return team_stats

    def calculate_league_averages(self, team_stats):
        """Calculate league-wide averages for each category."""
        categories = self.get_category_names()
        averages = {}

        for cat in categories:
            values = []
            for team_data in team_stats.values():
                stats = team_data.get('stats', {})
                if cat in stats:
                    try:
                        values.append(float(stats[cat]))
                    except (ValueError, TypeError):
                        pass
            if values:
                averages[cat] = sum(values) / len(values)
            else:
                averages[cat] = 0

        return averages

    def rank_teams_by_category(self, team_stats, category):
        """Rank all teams by a specific category."""
        rankings = []
        is_negative = category in NEGATIVE_CATEGORIES

        for team_key, team_data in team_stats.items():
            stats = team_data.get('stats', {})
            value = stats.get(category)
            if value is not None:
                try:
                    rankings.append({
                        'team_key': team_key,
                        'name': team_data['name'],
                        'value': float(value)
                    })
                except (ValueError, TypeError):
                    pass

        # Sort: ascending for negative categories, descending for positive
        rankings.sort(key=lambda x: x['value'], reverse=not is_negative)

        # Add rank
        for i, team in enumerate(rankings, 1):
            team['rank'] = i

        return rankings

    def get_category_rankings_matrix(self, team_stats):
        """Generate a matrix of all teams ranked by all categories."""
        categories = self.get_category_names()
        matrix = {}

        for cat in categories:
            matrix[cat] = self.rank_teams_by_category(team_stats, cat)

        return matrix

    def get_standings_display(self):
        """Get formatted standings data."""
        standings = self.get_standings()
        display_data = []

        for standing in standings:
            outcome = standing.get('outcome_totals', {})
            wins = int(outcome.get('wins', 0) or 0)
            losses = int(outcome.get('losses', 0) or 0)
            ties = int(outcome.get('ties', 0) or 0)
            display_data.append({
                'team_key': standing.get('team_key'),
                'rank': int(standing.get('rank', 0) or 0),
                'name': standing.get('name', 'Unknown'),
                'wins': wins,
                'losses': losses,
                'ties': ties,
                'points_for': standing.get('points_for', '-'),
                'points_against': standing.get('points_against', '-'),
            })

        return display_data

    def get_matchup_analysis(self, user_team_key):
        """Analyze current week matchup for user's team."""
        try:
            matchups = self.league.matchups()
            for matchup in matchups:
                teams = matchup.get('teams', [])
                for team in teams:
                    if team.get('team_key') == user_team_key:
                        return matchup
        except Exception as e:
            logger.warning("Error fetching matchup: %s", e)
        return None
