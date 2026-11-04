"""Configuration for Yahoo Fantasy Basketball Web App."""

import os
from dotenv import load_dotenv

load_dotenv()

# --- Web App Settings ---
# Enables dev-only conveniences (e.g. /auth/dev-login). Never set in production.
DEV_MODE = os.getenv("DEV_MODE", "").lower() in ("1", "true", "yes")

SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    if not DEV_MODE:
        raise RuntimeError("SECRET_KEY must be set (or set DEV_MODE=true for local development)")
    SECRET_KEY = "dev-secret-key-not-for-production"
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./fantasy.db")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

# --- Yahoo OAuth Settings ---
YAHOO_CLIENT_ID = os.getenv("YAHOO_CLIENT_ID", "")
YAHOO_CLIENT_SECRET = os.getenv("YAHOO_CLIENT_SECRET", "")
YAHOO_REDIRECT_URI = os.getenv("YAHOO_REDIRECT_URI", f"{BASE_URL}/auth/callback")
YAHOO_AUTH_URL = "https://api.login.yahoo.com/oauth2/request_auth"
YAHOO_TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
YAHOO_USERINFO_URL = "https://api.login.yahoo.com/openid/v1/userinfo"

# --- Stripe Settings ---
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "")
SUBSCRIPTION_PRICE = "$4.99/mo"

# --- Fantasy Basketball Categories (10-cat H2H) ---
CATEGORIES = [
    "FG%",   # Field Goal Percentage
    "FT%",   # Free Throw Percentage
    "3PTM",  # 3-Pointers Made
    "PTS",   # Points
    "REB",   # Rebounds
    "AST",   # Assists
    "ST",    # Steals
    "BLK",   # Blocks
    "TO",    # Turnovers
    "DD",    # Double-Doubles
]

# Categories where lower is better
NEGATIVE_CATEGORIES = ["TO"]

# Yahoo API stat ID mapping
STAT_ID_MAP = {
    "FG%": "FG%",
    "FT%": "FT%",
    "3PTM": "3PTM",
    "PTS": "PTS",
    "REB": "REB",
    "AST": "AST",
    "ST": "ST",
    "BLK": "BLK",
    "TO": "TO",
    "DD": "DD",
}

# Basketball positions
POSITIONS = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL", "BN", "IL", "IL+"]
ACTIVE_POSITIONS = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]

# Strength/weakness thresholds (for 10-team league)
STRENGTH_THRESHOLD = 3   # Top 3 = strength
WEAKNESS_THRESHOLD = 8   # Bottom 3 (rank 8-10) = weakness

# Free agent recommendation count
DEFAULT_FA_RECOMMENDATIONS = 10

# Cache TTL in seconds (15 minutes)
CACHE_TTL = 900

# Cache TTL for data that rarely changes, e.g. league settings (24 hours)
STATIC_CACHE_TTL = 86400
