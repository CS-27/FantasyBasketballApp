"""Core league analysis logic (migrated from CLI version)."""

import logging

from app.config import CATEGORIES, NEGATIVE_CATEGORIES, STATIC_CACHE_TTL
from app.services.cache import NullCache

logger = logging.getLogger(__name__)


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
        """Get the actual category names used in this league."""
        try:
            cats = self.stat_categories
            if cats:
                return [cat.get('display_name', cat.get('name', '')) for cat in cats]
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
        totals = {cat: 0 for cat in categories}

        # Track for percentage calculations
        fg_made = 0
        fg_att = 0
        ft_made = 0
        ft_att = 0

        try:
            team = self.league.to_team(team_key)
            roster = team.roster()

            if not roster:
                return totals

            # Get player IDs
            player_ids = [p.get('player_id') for p in roster if p.get('player_id')]

            if not player_ids:
                return totals

            # Fetch stats for all players
            player_stats = self.league.player_stats(player_ids, 'season')

            for player in player_stats:
                for cat in categories:
                    value = player.get(cat)
                    if value is not None and cat not in ['FG%', 'FT%']:
                        try:
                            totals[cat] += float(value)
                        except (ValueError, TypeError):
                            pass

                # Parse FGM/A and FTM/A
                fgma = player.get('FGM/A', '')
                if fgma and '/' in str(fgma):
                    parts = str(fgma).split('/')
                    try:
                        fg_made += float(parts[0])
                        fg_att += float(parts[1])
                    except (ValueError, IndexError):
                        pass

                ftma = player.get('FTM/A', '')
                if ftma and '/' in str(ftma):
                    parts = str(ftma).split('/')
                    try:
                        ft_made += float(parts[0])
                        ft_att += float(parts[1])
                    except (ValueError, IndexError):
                        pass

            # Calculate percentages
            if fg_att > 0:
                totals['FG%'] = fg_made / fg_att
            if ft_att > 0:
                totals['FT%'] = ft_made / ft_att

        except Exception as e:
            logger.warning("Could not fetch stats for team %s: %s", team_key, e)

        return totals

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
