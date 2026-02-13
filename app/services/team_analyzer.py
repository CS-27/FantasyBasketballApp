"""Team strength/weakness analysis (migrated from CLI version)."""

import logging

from app.config import CATEGORIES, NEGATIVE_CATEGORIES, STRENGTH_THRESHOLD, WEAKNESS_THRESHOLD

logger = logging.getLogger(__name__)


class TeamAnalyzer:
    """Analyzes a specific team's performance and needs."""

    def __init__(self, team, league, league_analyzer):
        self.team = team
        self.league = league
        self.league_analyzer = league_analyzer
        self._roster = None
        self._roster_with_stats = None

    @property
    def roster(self):
        """Get team roster (cached)."""
        if self._roster is None:
            self._roster = self.team.roster()
        return self._roster

    def get_roster_with_stats(self):
        """Get roster with player stats fetched."""
        if self._roster_with_stats is not None:
            return self._roster_with_stats

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

        self._roster_with_stats = roster_with_stats
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
        team_key = self.league.team_key()
        team_stats = self.league_analyzer.get_team_stats()

        if team_key in team_stats:
            return team_stats[team_key].get('stats', {})

        # Fall back to calculating from roster
        return self.get_team_totals()

    def get_category_rankings(self):
        """Rank team in each category vs league."""
        team_key = self.league.team_key()
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

    def get_comparison_to_league_avg(self):
        """Compare team stats to league averages."""
        team_stats = self.get_team_stats_from_standings()
        team_totals = self.get_team_totals()

        # Use whichever has data
        stats = team_stats if team_stats else team_totals

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
