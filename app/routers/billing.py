"""Stripe billing routes - upgrade page, checkout, customer portal, webhook."""

import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import (
    BASE_URL,
    STRIPE_PRICE_ID,
    STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET,
    SUBSCRIPTION_PRICE,
)
from app.database import get_db
from app.dependencies import require_user, user_to_dict
from app.models import User
from app.templating import templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])

stripe.api_key = STRIPE_SECRET_KEY

# Stripe subscription statuses that grant premium access
ACTIVE_STATUSES = {"active", "trialing"}


def _billing_enabled() -> bool:
    return bool(STRIPE_SECRET_KEY and STRIPE_PRICE_ID)


def _get(obj, key, default=None):
    """Read a field from a Stripe object or plain dict."""
    try:
        return obj[key]
    except (KeyError, TypeError):
        return default


@router.get("/upgrade")
def upgrade_page(request: Request, user: User = Depends(require_user)):
    """Pricing / upgrade page shown when a free user hits a premium feature."""
    amount, _, period = SUBSCRIPTION_PRICE.partition("/")
    return templates.TemplateResponse(
        "upgrade.html",
        {
            "request": request,
            "user": user_to_dict(user),
            "price": SUBSCRIPTION_PRICE,
            "price_amount": amount,
            "price_period": period or "mo",
            "billing_enabled": _billing_enabled(),
            "status": request.query_params.get("status"),
        },
    )


@router.post("/checkout")
def checkout(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Create a Stripe Checkout session and redirect to it."""
    if not _billing_enabled():
        raise HTTPException(status_code=503, detail="Billing is not configured")
    if user.subscription_status == "premium":
        return RedirectResponse("/dashboard", status_code=303)

    if not user.stripe_customer_id:
        customer = stripe.Customer.create(
            email=user.email or None,
            name=user.display_name,
            metadata={"user_id": str(user.id)},
        )
        user.stripe_customer_id = customer.id
        db.commit()

    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=user.stripe_customer_id,
        client_reference_id=str(user.id),
        line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
        success_url=f"{BASE_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{BASE_URL}/billing/upgrade?status=canceled",
        allow_promotion_codes=True,
    )
    return RedirectResponse(session.url, status_code=303)


@router.get("/success")
def success(session_id: str = "", user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Landing page after Checkout.

    The webhook is the source of truth, but it may arrive after the user is
    redirected back, so confirm the session directly to avoid a confusing
    "still free" state.
    """
    if session_id and _billing_enabled() and user.subscription_status != "premium":
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.customer == user.stripe_customer_id and session.status == "complete":
                user.subscription_status = "premium"
                db.commit()
        except stripe.StripeError as e:
            logger.warning("Could not verify checkout session %s: %s", session_id, e)
    return RedirectResponse("/premium/fa-recs", status_code=303)


@router.post("/portal")
def portal(user: User = Depends(require_user)):
    """Redirect to the Stripe customer portal to manage or cancel."""
    if not _billing_enabled() or not user.stripe_customer_id:
        return RedirectResponse("/billing/upgrade", status_code=303)
    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=f"{BASE_URL}/dashboard",
    )
    return RedirectResponse(session.url, status_code=303)


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    """Stripe webhook - keeps User.subscription_status in sync."""
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook secret not configured")

    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, signature, STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid webhook")

    event_type = event["type"]
    obj = event["data"]["object"]

    if event_type == "checkout.session.completed":
        user = None
        user_id = _get(obj, "client_reference_id")
        if user_id and user_id.isdigit():
            user = db.query(User).filter(User.id == int(user_id)).first()
        if user is None:
            user = _user_for_customer(db, _get(obj, "customer"))
        if user:
            user.stripe_customer_id = _get(obj, "customer") or user.stripe_customer_id
            user.subscription_status = "premium"
            db.commit()
        else:
            logger.warning("checkout.session.completed for unknown user (event %s)", event["id"])

    elif event_type in ("customer.subscription.created", "customer.subscription.updated",
                        "customer.subscription.deleted"):
        user = _user_for_customer(db, _get(obj, "customer"))
        if user:
            status = _get(obj, "status")
            active = event_type != "customer.subscription.deleted" and status in ACTIVE_STATUSES
            user.subscription_status = "premium" if active else "canceled"
            db.commit()
        else:
            logger.warning("%s for unknown customer (event %s)", event_type, event["id"])

    return {"received": True}


def _user_for_customer(db: Session, customer_id: str | None) -> User | None:
    if not customer_id:
        return None
    return db.query(User).filter(User.stripe_customer_id == customer_id).first()
