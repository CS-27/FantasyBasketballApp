"""Yahoo OAuth2 authentication routes."""

import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import DEV_MODE
from app.database import get_db
from app.models import User
from app.services.yahoo_client import (
    exchange_code_for_tokens,
    get_authorization_url,
    get_fantasy_user_guid,
    get_yahoo_user_info,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
async def login(request: Request):
    """Redirect user to Yahoo OAuth2 authorize page."""
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    url = get_authorization_url(state)
    return RedirectResponse(url=url)


@router.get("/callback")
async def callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
    db: Session = Depends(get_db),
):
    """Handle Yahoo OAuth2 callback."""
    # User clicked "Deny" (or Yahoo rejected the request)
    if error or not code:
        return RedirectResponse(url="/?error=login_canceled")

    # Verify state matches what we stored in session
    stored_state = request.session.pop("oauth_state", None)
    if not stored_state or stored_state != state:
        return RedirectResponse(url="/?error=invalid_state")

    # Exchange authorization code for tokens
    tokens = await exchange_code_for_tokens(code)

    # Profile info needs OpenID permission, which the app may not have
    display_name = ""
    email = None
    user_info = {}
    try:
        user_info = await get_yahoo_user_info(tokens["access_token"])
        display_name = user_info.get("name", "")
        email = user_info.get("email")
    except Exception as e:
        logger.info("Yahoo userinfo unavailable: %s", e)

    # yahoo_guid: token response, then userinfo, then the Fantasy API
    yahoo_guid = tokens["yahoo_guid"] or user_info.get("sub", "")
    if not yahoo_guid:
        try:
            yahoo_guid = await get_fantasy_user_guid(tokens["access_token"])
        except Exception:
            logger.exception("Could not determine Yahoo GUID")
    if not yahoo_guid:
        return RedirectResponse(url="/?error=login_failed")

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


@router.get("/dev-login")
async def dev_login(request: Request, db: Session = Depends(get_db)):
    """Dev-only: log in as the dev user (imported from oauth2.json)."""
    if not DEV_MODE:
        raise HTTPException(status_code=404)
    user =db.query(User).filter(User.yahoo_guid == "dev-user").first()
    if not user:
        return RedirectResponse(url="/?error=run_dev_setup")
    request.session["user_id"] = user.id
    return RedirectResponse(url="/dashboard")


@router.get("/logout")
async def logout(request: Request):
    """Clear session and redirect to landing page."""
    request.session.clear()
    return RedirectResponse(url="/")
