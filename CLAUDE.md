# Yahoo Fantasy Basketball Analyzer

## Project Overview
A Python CLI app that connects to Yahoo Fantasy Basketball API to analyze team performance, compare against league opponents, and recommend free agent pickups.

## League Configuration
- **Format**: 10-team H2H
- **Categories**: FG%, FT%, 3PTM, PTS, REB, AST, ST, BLK, TO, DD (Double-Doubles)

## Quick Start
```bash
pip install -r requirements.txt
python main.py
```

## Project Structure
| File | Purpose |
|------|---------|
| `main.py` | Entry point, CLI menu interface |
| `config.py` | Constants - categories, positions, thresholds |
| `auth.py` | Yahoo OAuth2 authentication |
| `league_analyzer.py` | League-wide stats and rankings |
| `team_analyzer.py` | Team strength/weakness analysis |
| `free_agent_finder.py` | FA recommendations based on team needs |
| `display.py` | CLI output formatting with color-coded tables |
| `oauth2.json` | OAuth credentials (DO NOT COMMIT) |

## Key Dependencies
- `yahoo_oauth` - OAuth2 authentication
- `yahoo_fantasy_api` - Yahoo Fantasy Sports API wrapper
- `tabulate` - CLI table formatting

## Important Files to Never Commit
- `oauth2.json` - Contains API credentials and access tokens

## Common API Patterns
```python
# Get league and team objects
oauth = OAuth2(None, None, from_file='oauth2.json')
gm = yfa.Game(oauth, 'nba')
lg = gm.to_league(league_id)
tm = lg.to_team(team_key)

# Key API calls
lg.standings()          # League standings
lg.teams()              # All teams
lg.free_agents('PG')    # Free agents by position
tm.roster()             # Team roster
```

## Category Analysis Logic
- **Strengths**: Categories where team ranks top 3
- **Weaknesses**: Categories where team ranks bottom 3
- **Negative categories**: TO (lower is better)

## Testing Changes
Run syntax check: `python -m py_compile *.py`
Run app: `python main.py`
