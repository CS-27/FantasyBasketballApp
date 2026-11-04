"""FastAPI dependencies for auth and authorization."""

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User


def _redirect(request: Request, url: str, htmx_status: int) -> HTTPException:
    """Build an exception that redirects both normal and HTMX requests.

    HTMX follows 3xx redirects transparently and would swap the target page
    into a partial, so HTMX requests get HX-Redirect with an error status.
    """
    if request.headers.get("HX-Request"):
        return HTTPException(status_code=htmx_status, headers={"HX-Redirect": url})
    return HTTPException(status_code=303, headers={"Location": url})


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> User | None:
    """Read user_id from session, fetch User from DB, return User or None."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()


def require_user(request: Request, user: User | None = Depends(get_current_user)) -> User:
    """Require an authenticated user. Redirects to login if not logged in."""
    if user is None:
        raise _redirect(request, "/auth/login", htmx_status=401)
    return user


def require_premium(request: Request, user: User = Depends(require_user)) -> User:
    """Require a premium subscription. Redirects to the upgrade page if not premium."""
    if user.subscription_status != "premium":
        raise _redirect(request, "/billing/upgrade", htmx_status=403)
    return user


def user_to_dict(user: User) -> dict:
    """Convert SQLAlchemy User model to a template-friendly dict."""
    return {
        "id": user.id,
        "display_name": user.display_name,
        "subscription_status": user.subscription_status,
        "is_premium": user.subscription_status == "premium",
        "has_billing": bool(user.stripe_customer_id),
    }
