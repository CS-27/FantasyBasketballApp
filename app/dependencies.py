"""FastAPI dependencies for auth and authorization."""

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> User | None:
    """Read user_id from session, fetch User from DB, return User or None."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()


def require_user(user: User | None = Depends(get_current_user)) -> User:
    """Require an authenticated user. Raises 401 if not logged in."""
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"HX-Redirect": "/auth/login"},
        )
    return user


def require_premium(user: User = Depends(require_user)) -> User:
    """Require a premium subscription. Raises 403 if not premium."""
    if user.subscription_status != "premium":
        raise HTTPException(
            status_code=403,
            detail="Premium subscription required",
        )
    return user
