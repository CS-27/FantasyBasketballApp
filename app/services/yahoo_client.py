"""Yahoo OAuth2 web client - replaces terminal-based yahoo_oauth for web usage."""

import base64
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import requests

from app.config import (
    YAHOO_AUTH_URL,
    YAHOO_CLIENT_ID,
    YAHOO_CLIENT_SECRET,
    YAHOO_REDIRECT_URI,
    YAHOO_TOKEN_URL,
    YAHOO_USERINFO_URL,
)


class WebOAuthContext:
    """OAuth context compatible with yahoo_fantasy_api.

    yahoo_fantasy_api.Game accepts any object with a `.session` attribute
    that is a requests.Session. This class provides exactly that, with
    token refresh capability.
    """

    def __init__(self, access_token: str, refresh_token: str):
        self._access_token = access_token
        self._refresh_token = refresh_token

    @property
    def session(self) -> requests.Session:
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {self._access_token}"})
        return s

    def refresh_if_needed(self, db, user) -> None:
        """Check token_expiry and refresh via Yahoo if expired, updating the DB."""
        if user.token_expiry and datetime.now(timezone.utc) < user.token_expiry:
            return

        credentials = base64.b64encode(
            f"{YAHOO_CLIENT_ID}:{YAHOO_CLIENT_SECRET}".encode()
        ).decode()

        with httpx.Client() as client:
            resp = client.post(
                YAHOO_TOKEN_URL,
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        self._access_token = data["access_token"]
        self._refresh_token = data.get("refresh_token", self._refresh_token)

        user.access_token = self._access_token
        user.refresh_token = self._refresh_token
        user.token_expiry = datetime.now(timezone.utc) + timedelta(
            seconds=data["expires_in"]
        )
        db.commit()


def get_authorization_url(state: str) -> str:
    """Build Yahoo OAuth2 authorize URL."""
    params = {
        "client_id": YAHOO_CLIENT_ID,
        "redirect_uri": YAHOO_REDIRECT_URI,
        "response_type": "code",
        "state": state,
    }
    return f"{YAHOO_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str) -> dict:
    """Exchange authorization code for tokens.

    Returns dict with access_token, refresh_token, expires_in, yahoo_guid.
    """
    credentials = base64.b64encode(
        f"{YAHOO_CLIENT_ID}:{YAHOO_CLIENT_SECRET}".encode()
    ).decode()

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            YAHOO_TOKEN_URL,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": YAHOO_REDIRECT_URI,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_in": data["expires_in"],
        "yahoo_guid": data.get("xoauth_yahoo_guid", ""),
    }


async def get_yahoo_user_info(access_token: str) -> dict:
    """Fetch user profile from Yahoo's userinfo endpoint."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            YAHOO_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()
