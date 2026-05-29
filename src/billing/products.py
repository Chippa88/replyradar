"""ReplyRadar — Stripe billing configuration and products."""

import os

STRIPE_SECRET = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")

# ── Products & Prices ──

PLANS = {
    "starter": {
        "name": "ReplyRadar Starter",
        "price_id": "price_1TcK1fQ8joGBqSnAt2ujM4Yk",
        "amount": 2900,
        "currency": "usd",
        "interval": "month",
        "keywords": 50,
        "platforms": ["reddit"],
        "features": [
            "50 monitored keywords",
            "Reddit monitoring",
            "AI reply drafts",
            "Approval queue",
            "Email notifications",
        ],
    },
    "pro": {
        "name": "ReplyRadar Pro",
        "price_id": "price_1TcK1gQ8joGBqSnArNlyjnPG",
        "amount": 7900,
        "currency": "usd",
        "interval": "month",
        "keywords": 200,
        "platforms": ["reddit", "twitter"],
        "features": [
            "200 monitored keywords",
            "Reddit + X/Twitter monitoring",
            "Priority AI replies",
            "Advanced approval queue",
            "Analytics dashboard",
            "Slack/email notifications",
        ],
    },
    "enterprise": {
        "name": "ReplyRadar Enterprise",
        "price_id": "price_1TcK1gQ8joGBqSnAsAlWchCH",
        "amount": 19900,
        "currency": "usd",
        "interval": "month",
        "keywords": -1,  # unlimited
        "platforms": ["reddit", "twitter", "hackernews", "producthunt"],
        "features": [
            "Unlimited keywords",
            "All platforms",
            "API access",
            "White-label reports",
            "Dedicated support",
            "Custom integrations",
        ],
    },
}


def get_stripe_checkout_url(price_id, customer_email=None, success_url=None, cancel_url=None):
    """Create a Stripe Checkout session and return the URL."""
    import stripe
    
    if not success_url:
        success_url = "https://chippa88.github.io/replyradar/success?session_id={CHECKOUT_SESSION_ID}"
    if not cancel_url:
        cancel_url = "https://chippa88.github.io/replyradar/cancel"
    
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        customer_email=customer_email,
        metadata={"source": "replyradar_landing"},
    )
    
    return session.url
