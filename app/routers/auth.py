"""Yahoo OAuth2 authentication routes."""

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services.yahoo_client import (
    exchange_code_for_tokens,
    get_authorization_url,
    get_yahoo_user_info,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
async def login(request: Request):
    """Redirect user to Yahoo OAuth2 authorize page."""
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    url = get_authorization_url(state)
    return RedirectResponse(url=url)


@router.get("/callback")
async def callback(request: Request, code: str, state: str, db: Session = Depends(get_db)):
    """Handle Yahoo OAuth2 callback."""
    # Verify state matches what we stored in session
    stored_state = request.session.pop("oauth_state", None)
    if not stored_state or stored_state != state:
        return RedirectResponse(url="/?error=invalid_state")

    # Exchange authorization code for tokens
    tokens = await exchange_code_for_tokens(code)

    # Get yahoo_guid - prefer token response, fall back to userinfo
    yahoo_guid = tokens["yahoo_guid"]
    display_name = ""
    email = None

    if not yahoo_guid:
        user_info = await get_yahoo_user_info(tokens["access_token"])
        yahoo_guid = user_info.get("sub", "")
        display_name = user_info.get("name", "")
        email = user_info.get("email")
    else:
        # Fetch display name even if we got guid from token
        try:
            user_info = await get_yahoo_user_info(tokens["access_token"])
            display_name = user_info.get("name", "")
            email = user_info.get("email")
        except Exception:
            display_name = "Yahoo User"

    token_expiry = datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])

    # Create or update user in DB
    user = db.query(User).filter(User.yahoo_guid == yahoo_guid).first()
    if user:
        user.access_token = tokens["access_token"]
        user.refresh_token = tokens["refresh_token"]
        user.token_expiry = token_expiry
        if display_name:
            user.display_name = display_name
        if email:
            user.email = email
    else:
        user = User(
            yahoo_guid=yahoo_guid,
            display_name=display_name or "Yahoo User",
            email=email,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_expiry=token_expiry,
        )
        db.add(user)

    db.commit()
    db.refresh(user)

    # Store user_id in session
    request.session["user_id"] = user.id

    return RedirectResponse(url="/dashboard")


@router.get("/logout")
async def logout(request: Request):
    """Clear session and redirect to landing page."""
    request.session.clear()
    return RedirectResponse(url="/")
