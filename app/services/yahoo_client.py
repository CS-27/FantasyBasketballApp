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

    yahoo_fantasy_api expects an object with:
    - .session: a requests.Session with auth headers
    - .refresh_access_token(): returns dict with 'access_token'
    - .oauth.get_session(token=...): returns a new Session

    This class provides all of these so the library can auto-refresh
    tokens when it gets a 401.
    """

    def __init__(self, access_token: str, refresh_token: str):
        self.access_token = access_token
        self._refresh_token = refresh_token
        self._session = self._build_session(access_token)
        self.oauth = self  # Library calls self.sc.oauth.get_session()

    def _build_session(self, token: str) -> requests.Session:
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {token}"})
        return s

    @property
    def session(self) -> requests.Session:
        return self._session

    @session.setter
    def session(self, value: requests.Session):
        self._session = value

    def get_session(self, token: str = None) -> requests.Session:
        """Called by yahoo_fantasy_api as self.sc.oauth.get_session(token=...)."""
        if token:
            self._session = self._build_session(token)
        return self._session

    def refresh_access_token(self) -> dict:
        """Refresh the token via Yahoo. Called by yahoo_fantasy_api on 401."""
        return _do_token_refresh(self._refresh_token)

    def refresh_if_needed(self, db, user) -> None:
        """Proactively refresh before API calls, updating the DB."""
        if user.token_expiry:
            expiry = user.token_expiry
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) < expiry:
                return

        data = _do_token_refresh(self._refresh_token)

        self.access_token = data["access_token"]
        self._refresh_token = data.get("refresh_token", self._refresh_token)
        self._session = self._build_session(self.access_token)

        user.access_token = self.access_token
        user.refresh_token = self._refresh_token
        user.token_expiry = datetime.now(timezone.utc) + timedelta(
            seconds=data["expires_in"]
        )
        db.commit()


def _do_token_refresh(refresh_token: str) -> dict:
    """Exchange a refresh token for a new access token."""
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
                "refresh_token": refresh_token,
            },
        )
        resp.raise_for_status()
        return resp.json()


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


def _find_key(obj, key):
    """Depth-first search for the first value stored under `key`."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        children = obj.values()
    elif isinstance(obj, list):
        children = obj
    else:
        return None
    for child in children:
        found = _find_key(child, key)
        if found is not None:
            return found
    return None


async def get_fantasy_user_guid(access_token: str) -> str:
    """Get the user's Yahoo GUID from the Fantasy API.

    Fallback for when the token response omits xoauth_yahoo_guid and the
    app lacks OpenID permission for the userinfo endpoint.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://fantasysports.yahooapis.com/fantasy/v2/users;use_login=1",
            params={"format": "json"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return _find_key(resp.json(), "guid") or ""


async def get_yahoo_user_info(access_token: str) -> dict:
    """Fetch user profile from Yahoo's userinfo endpoint."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            YAHOO_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()
