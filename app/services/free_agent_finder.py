# free_agent_finder.py
"""Free agent recommendations based on team needs."""

import logging

from app.config import (
    CATEGORIES, NEGATIVE_CATEGORIES, POSITIONS,
    ACTIVE_POSITIONS, DEFAULT_FA_RECOMMENDATIONS
)
from app.services.cache import NullCache

logger = logging.getLogger(__name__)


class FreeAgentFinder:
    """Finds and scores free agents based on team needs."""

    def __init__(self, league, team_analyzer, cache=None):
        self.league = league
        self.team_analyzer = team_analyzer
        self.cache = cache or NullCache()
        self._free_agents_cache = {}

    def get_free_agents(self, position=None, with_stats=True):
        """Fetch available free agents, optionally filtered by position."""
        cache_key = f"{position or 'all'}_{'stats' if with_stats else 'nostats'}"

        if cache_key not in self._free_agents_cache:
            self._free_agents_cache[cache_key] = self.cache.get_or_fetch(
                f"free_agents_{cache_key}",
                lambda: self._fetch_free_agents(position, with_stats),
            )
        return self._free_agents_cache[cache_key]

    def _fetch_free_agents(self, position, with_stats):
        try:
            if position:
                fas = self.league.free_agents(position)
            else:
                # Get all positions
                all_fas = []
                seen_ids = set()
                for pos in ['PG', 'SG', 'SF', 'PF', 'C']:
                    try:
                        pos_fas = self.league.free_agents(pos)
                        for fa in pos_fas:
                            pid = fa.get('player_id')
                            if pid and pid not in seen_ids:
                                seen_ids.add(pid)
                                all_fas.append(fa)
                    except Exception:
                        pass
                fas = all_fas

            # Fetch stats for all free agents
            if with_stats and fas:
                fas = self._fetch_fa_stats(fas)

            return fas
        except Exception as e:
            logger.warning("Error fetching free agents: %s", e)
            return []

    def _fetch_fa_stats(self, free_agents):
        """Fetch stats for a list of free agents."""
        player_ids = [fa.get('player_id') for fa in free_agents if fa.get('player_id')]

        if not player_ids:
            return free_agents

        # Fetch stats in batches (API may have limits)
        stats_map = {}
        batch_size = 25

        try:
            for i in range(0, len(player_ids), batch_size):
                batch_ids = player_ids[i:i + batch_size]
                batch_stats = self.league.player_stats(batch_ids, 'season')
                for player in batch_stats:
                    pid = player.get('player_id')
                    if pid:
                        stats_map[pid] = player
        except Exception as e:
            logger.warning("Could not fetch FA stats: %s", e)
            return free_agents

        # Merge stats into free agents
        fas_with_stats = []
        for fa in free_agents:
            pid = fa.get('player_id')
            fa_data = dict(fa)
            if pid in stats_map:
                fa_data['stats'] = stats_map[pid]
            fas_with_stats.append(fa_data)

        return fas_with_stats

    def get_player_stats(self, player):
        """Extract stats from a player object."""
        # Stats are now stored directly in the 'stats' key
        stats = player.get('stats', {})

        # The stats dict contains the player info plus stat values
        # Extract just the stat categories
        categories = self.team_analyzer.league_analyzer.get_category_names()
        result = {}
        for cat in categories:
            if cat in stats:
                result[cat] = stats[cat]

        return result

    def score_free_agent(self, player, weaknesses, weakness_weights):
        """Score a free agent based on how well they address team weaknesses."""
        stats = self.get_player_stats(player)
        if not stats:
            return 0

        score = 0
        categories = self.team_analyzer.league_analyzer.get_category_names()

        for weakness in weaknesses:
            cat = weakness['category']
            weight = weakness_weights.get(cat, 1)

            if cat in stats:
                try:
                    value = float(stats[cat])

                    # For negative categories, lower is better
                    if cat in NEGATIVE_CATEGORIES:
                        # Invert: fewer turnovers = higher score
                        # Use inverse scoring (e.g., 10 - TO)
                        value = max(0, 10 - value)

                    score += value * weight
                except (ValueError, TypeError):
                    pass

        # Bonus for double-double potential
        if 'DD' in [w['category'] for w in weaknesses]:
            pts = float(stats.get('PTS', 0))
            reb = float(stats.get('REB', 0))
            ast = float(stats.get('AST', 0))

            # Check if player has DD potential (avg close to 10 in multiple cats)
            dd_cats = sum([
                1 for val in [pts, reb, ast]
                if val >= 8  # Getting close to double-digit average
            ])
            if dd_cats >= 2:
                score += 5 * weakness_weights.get('DD', 1)

        return score

    def score_free_agents(self, weaknesses):
        """Score all free agents based on team weaknesses."""
        if not weaknesses:
            logger.info("No weaknesses identified. Scoring based on overall stats.")
            weaknesses = [{'category': cat, 'rank': 5} for cat in CATEGORIES[:5]]

        # Calculate weights based on weakness severity
        # Worse rank = higher weight
        weakness_weights = {}
        for w in weaknesses:
            cat = w['category']
            rank = w['rank']
            # Higher rank (worse) = higher weight
            weakness_weights[cat] = rank / 5  # Normalize

        free_agents = self.get_free_agents()
        scored_fas = []

        for fa in free_agents:
            score = self.score_free_agent(fa, weaknesses, weakness_weights)
            scored_fas.append({
                'player': fa,
                'score': score,
                'name': fa.get('name', 'Unknown'),
                'positions': fa.get('eligible_positions', []),
                'stats': self.get_player_stats(fa)
            })

        # Sort by score descending
        scored_fas.sort(key=lambda x: x['score'], reverse=True)
        return scored_fas

    def recommend_pickups(self, n=DEFAULT_FA_RECOMMENDATIONS):
        """Get top N free agents to consider picking up."""
        weaknesses = self.team_analyzer.identify_weaknesses()
        scored = self.score_free_agents(weaknesses)
        return scored[:n]

    def recommend_drops(self):
        """Identify players contributing least to team needs."""
        weaknesses = self.team_analyzer.identify_weaknesses()
        strengths = self.team_analyzer.identify_strengths()
        roster = self.team_analyzer.get_roster_analysis()

        weakness_cats = set(w['category'] for w in weaknesses)
        strength_cats = set(s['category'] for s in strengths)

        drop_candidates = []

        for player in roster:
            # Skip injured players from drop analysis (might want to hold)
            if player.get('status') in ['IL', 'IL+', 'O', 'INJ']:
                continue

            stats = player.get('stats', {})
            weakness_contribution = 0
            strength_contribution = 0

            for cat, value in stats.items():
                if cat in weakness_cats:
                    if cat in NEGATIVE_CATEGORIES:
                        # For TO, lower is better, so negative contribution if high
                        weakness_contribution -= value
                    else:
                        weakness_contribution += value

                if cat in strength_cats:
                    if cat in NEGATIVE_CATEGORIES:
                        strength_contribution -= value
                    else:
                        strength_contribution += value

            # Players who help strengths more than weaknesses are drop candidates
            ratio = strength_contribution / max(weakness_contribution, 0.1)

            drop_candidates.append({
                'name': player['name'],
                'position': player['position'],
                'weakness_contribution': weakness_contribution,
                'strength_contribution': strength_contribution,
                'drop_score': ratio,
                'stats': stats
            })

        # Sort by drop score descending (higher = more expendable)
        drop_candidates.sort(key=lambda x: x['drop_score'], reverse=True)
        return drop_candidates

    def get_pickup_suggestions(self, n=5):
        """Get combined pickup/drop recommendations."""
        pickups = self.recommend_pickups(n)
        drops = self.recommend_drops()

        # Only suggest drops for players in bottom half of roster value
        suggested_drops = drops[:max(2, len(drops) // 2)]

        return {
            'pickups': pickups,
            'drops': suggested_drops,
            'weaknesses': self.team_analyzer.identify_weaknesses()
        }

    def get_fa_by_category(self, category, n=10):
        """Get top free agents for a specific category."""
        free_agents = self.get_free_agents()
        fas_with_cat = []

        for fa in free_agents:
            stats = self.get_player_stats(fa)
            if category in stats:
                try:
                    value = float(stats[category])
                    fas_with_cat.append({
                        'player': fa,
                        'name': fa.get('name', 'Unknown'),
                        'positions': fa.get('eligible_positions', []),
                        'value': value,
                        'stats': stats
                    })
                except (ValueError, TypeError):
                    pass

        # Sort (ascending for negative categories, descending otherwise)
        reverse = category not in NEGATIVE_CATEGORIES
        fas_with_cat.sort(key=lambda x: x['value'], reverse=reverse)

        return fas_with_cat[:n]
