#!/usr/bin/env python3
# main.py
"""Entry point for Yahoo Fantasy Basketball Analyzer."""

import sys

from auth import get_oauth, get_game, select_league, get_user_team
from league_analyzer import LeagueAnalyzer
from team_analyzer import TeamAnalyzer
from free_agent_finder import FreeAgentFinder
from display import (
    display_menu, display_header, display_error, display_info,
    display_category_rankings, display_strengths_weaknesses,
    display_league_comparison, display_standings, display_roster,
    display_free_agent_recommendations, display_pickup_suggestions,
    display_category_leaders, Colors, color_text
)
from config import CATEGORIES


class FantasyAnalyzer:
    """Main application class."""

    def __init__(self):
        self.oauth = None
        self.game = None
        self.league = None
        self.team = None
        self.league_analyzer = None
        self.team_analyzer = None
        self.fa_finder = None

    def initialize(self):
        """Initialize connections to Yahoo Fantasy API."""
        print("\nConnecting to Yahoo Fantasy...")

        # Get OAuth
        self.oauth = get_oauth()
        if not self.oauth:
            display_error("Failed to authenticate with Yahoo.")
            return False

        # Get game
        self.game = get_game(self.oauth)
        if not self.game:
            display_error("Failed to connect to Yahoo Fantasy NBA.")
            return False

        # Select league
        self.league = select_league(self.game)
        if not self.league:
            display_error("Failed to select a league.")
            return False

        # Get user's team
        self.team = get_user_team(self.league)
        if not self.team:
            display_error("Failed to get your team.")
            return False

        # Initialize analyzers
        self.league_analyzer = LeagueAnalyzer(self.league)
        self.team_analyzer = TeamAnalyzer(self.team, self.league, self.league_analyzer)
        self.fa_finder = FreeAgentFinder(self.league, self.team_analyzer)

        display_info("Connected successfully!")
        return True

    def view_team_analysis(self):
        """View team's category analysis."""
        try:
            rankings = self.team_analyzer.get_category_rankings()
            display_category_rankings(rankings)

            strengths = self.team_analyzer.identify_strengths()
            weaknesses = self.team_analyzer.identify_weaknesses()
            display_strengths_weaknesses(strengths, weaknesses)
        except Exception as e:
            display_error(f"Failed to analyze team: {e}")

    def view_league_comparison(self):
        """Compare team to league averages."""
        try:
            comparison = self.team_analyzer.get_comparison_to_league_avg()
            display_league_comparison(comparison)
        except Exception as e:
            display_error(f"Failed to compare to league: {e}")

    def view_standings(self):
        """View league standings."""
        try:
            standings = self.league_analyzer.get_standings_display()
            display_standings(standings)
        except Exception as e:
            display_error(f"Failed to get standings: {e}")

    def view_category_rankings(self):
        """View all teams ranked by category."""
        try:
            team_stats = self.league_analyzer.get_team_stats()
            categories = self.league_analyzer.get_category_names()

            print("\nAvailable categories:")
            for i, cat in enumerate(categories, 1):
                print(f"  {i}. {cat}")
            print(f"  0. All categories")

            choice = input("\nSelect category (0 for all): ").strip()

            if choice == '0' or choice == '':
                # Show all
                for cat in categories:
                    rankings = self.league_analyzer.rank_teams_by_category(team_stats, cat)
                    display_header(f"Rankings - {cat}")
                    for team in rankings:
                        print(f"  #{team['rank']}: {team['name'][:25]} - {team['value']:.2f}")
            else:
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(categories):
                        cat = categories[idx]
                        rankings = self.league_analyzer.rank_teams_by_category(team_stats, cat)
                        display_header(f"Rankings - {cat}")
                        for team in rankings:
                            print(f"  #{team['rank']}: {team['name'][:25]} - {team['value']:.2f}")
                    else:
                        display_error("Invalid selection")
                except ValueError:
                    display_error("Please enter a number")

        except Exception as e:
            display_error(f"Failed to get category rankings: {e}")

    def view_fa_recommendations(self):
        """Get free agent recommendations."""
        try:
            print("\nAnalyzing free agents based on your team's needs...")
            pickups = self.fa_finder.recommend_pickups(10)
            weaknesses = self.team_analyzer.identify_weaknesses()
            display_free_agent_recommendations(pickups, weaknesses)
        except Exception as e:
            display_error(f"Failed to get recommendations: {e}")

    def view_pickup_suggestions(self):
        """Get combined pickup/drop suggestions."""
        try:
            print("\nAnalyzing roster and free agents...")
            suggestions = self.fa_finder.get_pickup_suggestions(5)
            display_pickup_suggestions(suggestions)
        except Exception as e:
            display_error(f"Failed to get suggestions: {e}")

    def browse_fa_by_category(self):
        """Browse free agents by specific category."""
        try:
            categories = self.league_analyzer.get_category_names()

            print("\nAvailable categories:")
            for i, cat in enumerate(categories, 1):
                print(f"  {i}. {cat}")

            choice = input("\nSelect category number: ").strip()

            try:
                idx = int(choice) - 1
                if 0 <= idx < len(categories):
                    cat = categories[idx]
                    fas = self.fa_finder.get_fa_by_category(cat, 15)
                    display_category_leaders(cat, fas)
                else:
                    display_error("Invalid selection")
            except ValueError:
                display_error("Please enter a number")

        except Exception as e:
            display_error(f"Failed to browse free agents: {e}")

    def run(self):
        """Main application loop."""
        if not self.initialize():
            return 1

        while True:
            display_menu()

            try:
                choice = input("Enter choice (1-8): ").strip()

                if choice == '1':
                    self.view_team_analysis()
                elif choice == '2':
                    self.view_league_comparison()
                elif choice == '3':
                    self.view_standings()
                elif choice == '4':
                    self.view_category_rankings()
                elif choice == '5':
                    self.view_fa_recommendations()
                elif choice == '6':
                    self.view_pickup_suggestions()
                elif choice == '7':
                    self.browse_fa_by_category()
                elif choice == '8':
                    print("\nGoodbye!")
                    break
                else:
                    display_error("Invalid choice. Please enter 1-8.")

                input("\nPress Enter to continue...")

            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                display_error(f"An error occurred: {e}")

        return 0


def main():
    """Entry point."""
    app = FantasyAnalyzer()
    sys.exit(app.run())


if __name__ == '__main__':
    main()
