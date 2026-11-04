"""Dev setup: import oauth2.json tokens into the local database and create .env."""

import json
import os
import secrets
from datetime import datetime, timedelta, timezone

from app.database import init_db, SessionLocal
from app.models import User


def create_env_file(creds):
    """Create .env from oauth2.json credentials if it doesn't exist."""
    if os.path.exists(".env"):
        print(".env already exists, skipping")
        return

    env_content = f"""DEV_MODE=true
SECRET_KEY={secrets.token_urlsafe(32)}
BASE_URL=http://localhost:8000
DATABASE_URL=sqlite:///./fantasy.db
YAHOO_CLIENT_ID={creds["consumer_key"]}
YAHOO_CLIENT_SECRET={creds["consumer_secret"]}
YAHOO_REDIRECT_URI=http://localhost:8000/auth/callback
"""
    with open(".env", "w") as f:
        f.write(env_content)
    print("Created .env from oauth2.json credentials")


def main():
    with open("oauth2.json") as f:
        creds = json.load(f)

    create_env_file(creds)
    init_db()

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.yahoo_guid == "dev-user").first()

        if user:
            user.access_token = creds["access_token"]
            user.refresh_token = creds["refresh_token"]
            user.token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
            print(f"Updated existing dev user (id={user.id})")
        else:
            user = User(
                yahoo_guid="dev-user",
                display_name="Dev User",
                access_token=creds["access_token"],
                refresh_token=creds["refresh_token"],
                token_expiry=datetime.now(timezone.utc) + timedelta(hours=1),
                subscription_status="premium",
            )
            db.add(user)
            print("Created dev user with premium access")

        db.commit()
        db.refresh(user)
        print(f"User ID: {user.id}")
        print("Run the app and go to http://localhost:8000/auth/dev-login")

    finally:
        db.close()


if __name__ == "__main__":
    main()
