# Yahoo Fantasy Basketball Analyzer

## Project Overview
A FastAPI web app that connects to the Yahoo Fantasy Basketball API to analyze team performance, compare against league opponents, and recommend free agent pickups. Free tier covers analysis; a Stripe subscription ($4.99/mo) unlocks premium features.

The original Python CLI (root-level `main.py`, `auth.py`, `*_analyzer.py`, `display.py`) still exists but is legacy. New work goes in `app/`.

## League Configuration
- **Format**: 10-team H2H
- **Categories**: FG%, FT%, 3PTM, PTS, REB, AST, ST, BLK, TO, DD (Double-Doubles)

## Quick Start (local)
```bash
pip install -r requirements.txt
python dev_setup.py          # imports oauth2.json tokens as a premium "dev-user", writes .env with DEV_MODE=true
uvicorn app.main:app --reload
# then visit http://localhost:8000/auth/dev-login
```

## Project Structure
| Path | Purpose |
|------|---------|
| `app/main.py` | FastAPI app, middleware, router registration, landing page |
| `app/config.py` | Env settings, categories, thresholds, cache TTLs |
| `app/models.py` | SQLAlchemy models: `User`, `UserLeague`, `CachedData` |
| `app/dependencies.py` | `require_user`, `require_premium`, `user_to_dict` |
| `app/routers/auth.py` | Yahoo OAuth2 login/callback, dev-login, logout |
| `app/routers/analysis.py` | Free pages: standings, team analysis, comparison, rankings, cache refresh |
| `app/routers/premium.py` | Premium pages: FA recs, pickup suggestions (gated by `require_premium`) |
| `app/routers/billing.py` | Stripe upgrade page, checkout, customer portal, webhook |
| `app/services/league_context.py` | `LeagueContext`: builds league/team objects + analyzers for a user |
| `app/services/cache.py` | `DataCache`: DB-backed cache for Yahoo responses |
| `app/services/*_analyzer.py`, `free_agent_finder.py` | Analysis logic |
| `app/services/yahoo_client.py` | Web OAuth context compatible with `yahoo_fantasy_api` |
| `app/templates/` | Jinja pages; `partials/` are HTMX fragments loaded by the pages |
| `dev_setup.py` | Local dev bootstrap from `oauth2.json` |

## Key Patterns
- **Pages vs partials**: each feature has a page route (`/analysis/team`) that renders a shell, and a `-data` route (`/analysis/team-data`) that HTMX loads into it.
- **Data routes** build a `LeagueContext(user, db)` and pass a `build()` closure to `render_partial`, which turns exceptions into an inline error panel.
- **Blocking I/O**: the Yahoo client is synchronous, so data routes are plain `def` (threadpool), not `async def`.
- **Auth gates**: use `Depends(require_user)` / `Depends(require_premium)`. They redirect normal requests (303) and HTMX requests (`HX-Redirect`).
- **Caching**: analyzers take a `cache` and wrap API calls in `cache.get_or_fetch(key, fetch, ttl)`. `CACHE_TTL` (15 min) for stats, `STATIC_CACHE_TTL` (24 h) for settings/teams. Empty results aren't cached. `POST /analysis/refresh` clears a user's cache.
- **Team key**: use `TeamAnalyzer.team_key` (from the team object). `league.team_key()` makes an API call.

## Category Analysis Logic
- **Strengths**: Categories where team ranks top 3
- **Weaknesses**: Categories where team ranks bottom 3
- **Negative categories**: TO (lower is better)
- Team FG%/FT% are computed from summed `FGM/A` / `FTM/A`, not averaged percentages.

## Environment
See `.env.example`. Production needs `SECRET_KEY` (the app refuses to start without it unless `DEV_MODE=true`), Yahoo client credentials, and the four `STRIPE_*` values. Never set `DEV_MODE` in production; it enables `/auth/dev-login`.

Stripe setup: create a recurring Price and set `STRIPE_PRICE_ID`; point a webhook at `{BASE_URL}/billing/webhook` with events `checkout.session.completed` and `customer.subscription.created/updated/deleted`; enable the Customer Portal in the Stripe dashboard.

## Deployment
Railway (`railway.toml`) / Procfile run `uvicorn app.main:app`. SQLite by default; set `DATABASE_URL` to Postgres in production.

## Important Files to Never Commit
- `oauth2.json` - Yahoo API credentials and tokens
- `.env` - secrets
- `fantasy.db` - local database (contains user tokens)

## Testing Changes
Syntax check: `python -m py_compile app/*.py app/*/*.py`
Run app: `uvicorn app.main:app --reload`
