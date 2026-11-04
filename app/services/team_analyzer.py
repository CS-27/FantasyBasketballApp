"""Team strength/weakness analysis (migrated from CLI version)."""

import logging

from app.config import CATEGORIES, NEGATIVE_CATEGORIES, STRENGTH_THRESHOLD, WEAKNESS_THRESHOLD
from app.services.cache import NullCache

logger = logging.getLogger(__name__)


class TeamAnalyzer:
    """Analyzes a specific team's performance and needs."""

    def __init__(self, team, league, league_analyzer, cache=None):
        self.team = team
        self.team_key = team.team_key
        self.league = league
        self.league_analyzer = league_analyzer
        self.cache = cache or NullCache()
        self._roster = None
        self._roster_with_stats = None
        self._category_rankings = None

    @property
    def roster(self):
        """Get team roster (cached)."""
        if self._roster is None:
            self._roster = self.cache.get_or_fetch("roster", self.team.roster)
        return self._roster

    def get_roster_with_stats(self):
        """Get roster with player stats fetched."""
        if self._roster_with_stats is None:
            self._roster_with_stats = self.cache.get_or_fetch("roster_with_stats", self._fetch_roster_with_stats)
        return self._roster_with_stats

    def _fetch_roster_with_stats(self):
        roster = self.roster
        player_ids = [p.get('player_id') for p in roster if p.get('player_id')]

        # Fetch stats for all players
        player_stats_map = {}
        if player_ids:
            try:
                stats_data = self.league.player_stats(player_ids, 'season')
                for player in stats_data:
                    pid = player.get('player_id')
                    if pid:
                        player_stats_map[pid] = player
            except Exception as e:
                logger.warning("Could not fetch player stats: %s", e)

        # Merge stats into roster
        roster_with_stats = []
        for player in roster:
            pid = player.get('player_id')
            player_data = dict(player)
            if pid in player_stats_map:
                player_data['stats'] = player_stats_map[pid]
            roster_with_stats.append(player_data)

        return roster_with_stats

    def get_roster_players(self):
        """Get list of players on the roster."""
        roster = self.roster
        players = []

        for player in roster:
            players.append({
                'player_id': player.get('player_id'),
                'name': player.get('name', 'Unknown'),
                'position': player.get('eligible_positions', []),
                'selected_position': player.get('selected_position', ''),
                'status': player.get('status', ''),
            })

        return players

    def get_team_totals(self):
        """Aggregate season stats for the team's roster."""
        roster = self.get_roster_with_stats()
        categories = self.league_analyzer.get_category_names()

        totals = {cat: 0 for cat in categories}
        player_count = 0

        # For percentage calculations, track totals
        fg_made = 0
        fg_att = 0
        ft_made = 0
        ft_att = 0

        for player in roster:
            stats = player.get('stats', {})

            if stats:
                player_count += 1

                for cat in categories:
                    value = stats.get(cat)
                    if value is not None:
                        try:
                            value = float(value)
                            if cat not in ['FG%', 'FT%']:
                                totals[cat] += value
                        except (ValueError, TypeError):
                            pass

                # Parse FGM/A and FTM/A for accurate percentage calculation
                fgma = stats.get('FGM/A', '')
                if fgma and '/' in str(fgma):
                    parts = str(fgma).split('/')
                    try:
                        fg_made += float(parts[0])
                        fg_att += float(parts[1])
                    except (ValueError, IndexError):
                        pass

                ftma = stats.get('FTM/A', '')
                if ftma and '/' in str(ftma):
                    parts = str(ftma).split('/')
                    try:
                        ft_made += float(parts[0])
                        ft_att += float(parts[1])
                    except (ValueError, IndexError):
                        pass

        # Calculate team percentages from totals
        if fg_att > 0:
            totals['FG%'] = fg_made / fg_att
        if ft_att > 0:
            totals['FT%'] = ft_made / ft_att

        return totals

    def get_team_stats_from_standings(self):
        """Get team stats from league standings/matchups."""
        team_stats = self.league_analyzer.get_team_stats()

        if self.team_key in team_stats:
            return team_stats[self.team_key].get('stats', {})

        # Fall back to calculating from roster
        return self.get_team_totals()

    def get_category_rankings(self):
        """Rank team in each category vs league."""
        if self._category_rankings is not None:
            return self._category_rankings

        team_key = self.team_key
        team_stats = self.league_analyzer.get_team_stats()
        categories = self.league_analyzer.get_category_names()

        rankings = {}
        num_teams = len(team_stats)

        for cat in categories:
            cat_rankings = self.league_analyzer.rank_teams_by_category(team_stats, cat)

            for team_data in cat_rankings:
                if team_data['team_key'] == team_key:
                    rankings[cat] = {
                        'rank': team_data['rank'],
                        'value': team_data['value'],
                        'total_teams': num_teams
                    }
                    break

            if cat not in rankings:
                rankings[cat] = {
                    'rank': '-',
                    'value': '-',
                    'total_teams': num_teams
                }

        self._category_rankings = rankings
        return rankings

    def identify_strengths(self):
        """Identify categories where team ranks in top 3."""
        rankings = self.get_category_rankings()
        strengths = []

        for cat, data in rankings.items():
            rank = data.get('rank')
            if isinstance(rank, int) and rank <= STRENGTH_THRESHOLD:
                strengths.append({
                    'category': cat,
                    'rank': rank,
                    'value': data.get('value')
                })

        # Sort by rank (best first)
        strengths.sort(key=lambda x: x['rank'])
        return strengths

    def identify_weaknesses(self):
        """Identify categories where team ranks in bottom 3."""
        rankings = self.get_category_rankings()
        weaknesses = []

        for cat, data in rankings.items():
            rank = data.get('rank')
            total = data.get('total_teams', 10)
            if isinstance(rank, int) and rank >= total - (10 - WEAKNESS_THRESHOLD):
                weaknesses.append({
                    'category': cat,
                    'rank': rank,
                    'value': data.get('value')
                })

        # Sort by rank (worst first, i.e., highest rank number)
        weaknesses.sort(key=lambda x: x['rank'], reverse=True)
        return weaknesses

    def get_roster_analysis(self):
        """Get per-player contribution breakdown."""
        roster = self.get_roster_with_stats()
        categories = self.league_analyzer.get_category_names()

        analysis = []

        for player in roster:
            player_data = {
                'name': player.get('name', 'Unknown'),
                'position': player.get('selected_position', ''),
                'eligible_positions': player.get('eligible_positions', []),
                'status': player.get('status', ''),
                'stats': {}
            }

            stats = player.get('stats', {})

            for cat in categories:
                if cat in stats:
                    try:
                        player_data['stats'][cat] = float(stats[cat])
                    except (ValueError, TypeError):
                        player_data['stats'][cat] = 0
                else:
                    player_data['stats'][cat] = 0

            analysis.append(player_data)

        return analysis

    def compare_to_opponent(self, opponent_key):
        """Category-by-category head-to-head projection against another team."""
        team_stats = self.league_analyzer.get_team_stats()
        mine = team_stats.get(self.team_key, {}).get('stats', {})
        theirs = team_stats.get(opponent_key, {}).get('stats', {})
        categories = self.league_analyzer.get_category_names()

        rows = []
        record = {'wins': 0, 'losses': 0, 'ties': 0}

        for cat in categories:
            try:
                my_val = float(mine.get(cat, 0))
                their_val = float(theirs.get(cat, 0))
            except (ValueError, TypeError):
                continue

            if my_val == their_val:
                result = 'tie'
            elif (my_val < their_val) == (cat in NEGATIVE_CATEGORIES):
                result = 'win'
            else:
                result = 'loss'
            record[{'win': 'wins', 'loss': 'losses', 'tie': 'ties'}[result]] += 1

            rows.append({
                'category': cat,
                'my_value': my_val,
                'their_value': their_val,
                'result': result,
            })

        return {
            'opponent_name': team_stats.get(opponent_key, {}).get('name', opponent_key),
            'categories': rows,
            'record': record,
        }

    def get_comparison_to_league_avg(self):
        """Compare team stats to league averages."""
        stats = self.get_team_stats_from_standings()

        league_team_stats = self.league_analyzer.get_team_stats()
        league_avgs = self.league_analyzer.calculate_league_averages(league_team_stats)

        comparison = {}
        categories = self.league_analyzer.get_category_names()

        for cat in categories:
            team_val = stats.get(cat, 0)
            league_avg = league_avgs.get(cat, 0)

            if league_avg != 0:
                diff_pct = ((team_val - league_avg) / abs(league_avg)) * 100
            else:
                diff_pct = 0

            # For negative categories, flip the interpretation
            is_positive_diff = diff_pct > 0
            if cat in NEGATIVE_CATEGORIES:
                is_positive_diff = diff_pct < 0

            comparison[cat] = {
                'team_value': team_val,
                'league_avg': league_avg,
                'difference': team_val - league_avg,
                'diff_percent': diff_pct,
                'is_better': is_positive_diff
            }

        return comparison
