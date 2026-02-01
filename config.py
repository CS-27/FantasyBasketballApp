# config.py
"""Configuration constants for Yahoo Fantasy Basketball Analyzer."""

# 10-Category H2H Categories
CATEGORIES = [
    "FG%",      # Field Goal Percentage
    "FT%",      # Free Throw Percentage
    "3PTM",     # 3-Pointers Made
    "PTS",      # Points
    "REB",      # Rebounds
    "AST",      # Assists
    "ST",       # Steals
    "BLK",      # Blocks
    "TO",       # Turnovers
    "DD",       # Double-Doubles
]

# Categories where lower is better
NEGATIVE_CATEGORIES = ["TO"]

# Yahoo API stat ID mapping (common mappings)
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

# Roster positions (non-bench/IL)
ACTIVE_POSITIONS = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]

# Strength/weakness thresholds (for 10-team league)
STRENGTH_THRESHOLD = 3   # Top 3 = strength
WEAKNESS_THRESHOLD = 8   # Bottom 3 (rank 8-10) = weakness

# Free agent recommendation count
DEFAULT_FA_RECOMMENDATIONS = 10

# OAuth file path
OAUTH_FILE = "oauth2.json"
