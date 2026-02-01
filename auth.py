# auth.py
"""Authentication handling for Yahoo Fantasy API."""

import os
import json
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

from config import OAUTH_FILE


def create_oauth_file():
    """Guide user through creating oauth2.json file."""
    print("\n" + "=" * 60)
    print("Yahoo OAuth Setup Required")
    print("=" * 60)
    print("""
To use this app, you need Yahoo API credentials.

1. Go to: https://developer.yahoo.com/apps/create/
2. Create an app with these settings:
   - Application Name: "Fantasy Basketball Analyzer"
   - Application Type: "Installed Application"
   - API Permissions: "Fantasy Sports" (Read access)
3. Copy your Consumer Key and Consumer Secret
""")

    consumer_key = input("Enter your Consumer Key: ").strip()
    consumer_secret = input("Enter your Consumer Secret: ").strip()

    if not consumer_key or not consumer_secret:
        print("Error: Both Consumer Key and Consumer Secret are required.")
        return None

    oauth_data = {
        "consumer_key": consumer_key,
        "consumer_secret": consumer_secret
    }

    with open(OAUTH_FILE, 'w') as f:
        json.dump(oauth_data, f, indent=2)

    print(f"\nCredentials saved to {OAUTH_FILE}")
    return oauth_data


def get_oauth():
    """Get OAuth2 object, creating credentials file if needed."""
    if not os.path.exists(OAUTH_FILE):
        result = create_oauth_file()
        if result is None:
            return None

    try:
        oauth = OAuth2(None, None, from_file=OAUTH_FILE)
        if not oauth.token_is_valid():
            oauth.refresh_access_token()
        return oauth
    except Exception as e:
        print(f"Authentication error: {e}")
        print("\nYou may need to re-authenticate. Delete oauth2.json and try again.")
        return None


def get_game(oauth):
    """Get the Yahoo Fantasy NBA game object."""
    try:
        return yfa.Game(oauth, 'nba')
    except Exception as e:
        print(f"Error connecting to Yahoo Fantasy: {e}")
        return None


def get_user_leagues(game):
    """Get all leagues the user is in for the current season."""
    try:
        return game.league_ids()
    except Exception as e:
        print(f"Error fetching leagues: {e}")
        return []


def select_league(game):
    """Let user select which league to analyze."""
    league_ids = get_user_leagues(game)

    if not league_ids:
        print("No fantasy basketball leagues found for this season.")
        return None

    if len(league_ids) == 1:
        league_id = league_ids[0]
        print(f"Found league: {league_id}")
        return game.to_league(league_id)

    print("\nAvailable Leagues:")
    for i, lid in enumerate(league_ids, 1):
        print(f"  {i}. {lid}")

    while True:
        try:
            choice = int(input("\nSelect league number: "))
            if 1 <= choice <= len(league_ids):
                return game.to_league(league_ids[choice - 1])
            print("Invalid selection. Try again.")
        except ValueError:
            print("Please enter a number.")


def get_user_team(league):
    """Get the current user's team from the league."""
    try:
        team_key = league.team_key()
        return league.to_team(team_key)
    except Exception as e:
        print(f"Error getting your team: {e}")
        return None
