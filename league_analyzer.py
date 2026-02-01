# league_analyzer.py
"""Core league analysis logic."""

from config import CATEGORIES, NEGATIVE_CATEGORIES


class LeagueAnalyzer:
    """Analyzes league-wide statistics and rankings."""

    def __init__(self, league):
        self.league = league
        self._settings = None
        self._standings = None
        self._teams = None
        self._stat_categories = None

    @property
    def settings(self):
        """Get league settings (cached)."""
        if self._settings is None:
            self._settings = self.league.settings()
        return self._settings

    @property
    def stat_categories(self):
        """Get stat categories from league settings."""
        if self._stat_categories is None:
            self._stat_categories = self.league.stat_categories()
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
            self._standings = self.league.standings()
        return self._standings

    def get_teams(self):
        """Get all teams in the league."""
        if self._teams is None:
            self._teams = self.league.teams()
        return self._teams

    def get_team_stats(self):
        """Get stats for all teams in the league."""
        teams = self.get_teams()
        team_stats = {}

        for team_key, team_data in teams.items():
            team_name = team_data.get('name', team_key)
            # Try to get team stats from the API
            try:
                # The stats might be in team_data directly or need separate fetch
                stats = team_data.get('stats', {})
                if not stats:
                    # Try to get from standings
                    standings = self.get_standings()
                    for standing in standings:
                        if standing.get('team_key') == team_key:
                            stats = standing.get('stats', {})
                            break
                team_stats[team_key] = {
                    'name': team_name,
                    'stats': stats
                }
            except Exception as e:
                team_stats[team_key] = {
                    'name': team_name,
                    'stats': {}
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
            display_data.append({
                'rank': standing.get('rank', '-'),
                'name': standing.get('name', 'Unknown'),
                'wins': standing.get('outcome_totals', {}).get('wins', 0),
                'losses': standing.get('outcome_totals', {}).get('losses', 0),
                'ties': standing.get('outcome_totals', {}).get('ties', 0),
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
            print(f"Error fetching matchup: {e}")
        return None
