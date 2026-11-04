# Fantasy Basketball Analyzer

A web app for Yahoo Fantasy Basketball managers in head-to-head category leagues. Sign in with Yahoo and see where your team stands in every scoring category, how you compare to the rest of your league, and which free agents would fix your weak spots.

> **Status:** In active development. Not yet publicly launched.

## Features

- **League standings**: current records and rankings for every team in your league.
- **Team analysis**: your rank in each scoring category (FG%, FT%, 3PTM, PTS, REB, AST, ST, BLK, TO, DD), with your strongest and weakest categories highlighted.
- **Category rankings**: every team ranked across every category, filterable by category.
- **League comparison**: your totals against the league average in each category, plus a category-by-category head-to-head projection against any opponent.
- **Free agent recommendations**: available players scored by how much they would help in your weakest categories.
- **Pickup suggestions**: recommended adds alongside roster players who contribute least to your team's needs.

## How it uses Yahoo Fantasy data

The app is **read-only**. It never makes roster moves, trades, or other changes; you act on recommendations in Yahoo Fantasy yourself.

After a user signs in with Yahoo OAuth, the app reads data **only for that user's own leagues**:

- The user's NBA leagues and team
- League settings and scoring categories
- Standings and teams
- Team rosters and season player stats
- Available free agents and their season stats

Responses are cached briefly (15 minutes for stats, up to 24 hours for league settings) to keep API usage low. Yahoo data is never shared with third parties or used outside the signed-in user's session.

## Tech stack

- **Backend:** Python, FastAPI, SQLAlchemy
- **Frontend:** Jinja2 templates, HTMX, Tailwind CSS
- **Data:** Yahoo Fantasy Sports API via [`yahoo_fantasy_api`](https://github.com/spilchen/yahoo_fantasy_api)
- **Hosting:** Railway (planned)

## Local development

Requires Python 3.10+ and a Yahoo Developer app with Fantasy Sports read access.

```bash
python -m venv venv
venv\Scripts\activate        # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env         # then fill in your Yahoo client ID/secret and a SECRET_KEY
uvicorn app.main:app --reload
```

Open http://localhost:8000 and sign in with Yahoo.

For local testing with an existing token, copy `oauth2.json.example` to `oauth2.json`, add your credentials and tokens, set `DEV_MODE=true` in `.env`, then run `python dev_setup.py` and visit `/auth/dev-login`. Never enable `DEV_MODE` in production.
