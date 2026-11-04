"""DB-backed cache for Yahoo API responses (CachedData table)."""

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import CACHE_TTL
from app.models import CachedData

logger = logging.getLogger(__name__)


class DataCache:
    """Caches JSON-serializable API results per user + league.

    Yahoo calls are slow (a full league stats load is ~20 requests), so
    results are stored in the DB and reused until they expire.
    """

    def __init__(self, db: Session, user_id: int, league_id: str):
        self.db = db
        self.user_id = user_id
        self.league_id = league_id

    def _query(self, data_type: str):
        return self.db.query(CachedData).filter(
            CachedData.user_id == self.user_id,
            CachedData.league_id == self.league_id,
            CachedData.data_type == data_type,
        )

    def get(self, data_type: str):
        """Return the cached value, or None if missing/expired."""
        row = self._query(data_type).order_by(CachedData.id.desc()).first()
        if row is None:
            return None
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) >= expires_at:
            return None
        try:
            return json.loads(row.data_json)
        except ValueError:
            return None

    def set(self, data_type: str, value, ttl: int = CACHE_TTL) -> None:
        """Store a value, replacing any previous entry for this data type."""
        try:
            self._query(data_type).delete(synchronize_session=False)
            self.db.add(CachedData(
                user_id=self.user_id,
                league_id=self.league_id,
                data_type=data_type,
                data_json=json.dumps(value, default=str),
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl),
            ))
            self.db.commit()
        except Exception as e:
            # A cache write failure should never break the request
            self.db.rollback()
            logger.warning("Could not cache %s: %s", data_type, e)

    def get_or_fetch(self, data_type: str, fetch, ttl: int = CACHE_TTL):
        """Return the cached value, calling fetch() and storing it on a miss."""
        value = self.get(data_type)
        if value is not None:
            return value
        value = fetch()
        # Don't pin empty results (often a transient API failure) for a full TTL
        if value:
            self.set(data_type, value, ttl)
        return value

    def clear(self) -> None:
        """Drop every cached entry for this user + league."""
        self.db.query(CachedData).filter(
            CachedData.user_id == self.user_id,
            CachedData.league_id == self.league_id,
        ).delete(synchronize_session=False)
        self.db.commit()


class NullCache:
    """No-op cache, used when analyzers run without a DB (e.g. scripts)."""

    def get_or_fetch(self, data_type, fetch, ttl=CACHE_TTL):
        return fetch()
