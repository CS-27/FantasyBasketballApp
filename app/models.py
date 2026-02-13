"""Database models."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    yahoo_guid = Column(String, unique=True, index=True, nullable=False)
    display_name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expiry = Column(DateTime, nullable=True)
    stripe_customer_id = Column(String, nullable=True)
    subscription_status = Column(String, default="free")  # free, premium, canceled
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    leagues = relationship("UserLeague", back_populates="user")
    cached_data = relationship("CachedData", back_populates="user")


class UserLeague(Base):
    __tablename__ = "user_leagues"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    league_id = Column(String, nullable=False)
    league_name = Column(String, nullable=True)
    team_key = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="leagues")


class CachedData(Base):
    __tablename__ = "cached_data"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    league_id = Column(String, nullable=False)
    data_type = Column(String, nullable=False)  # e.g., "standings", "team_stats"
    data_json = Column(Text, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="cached_data")
