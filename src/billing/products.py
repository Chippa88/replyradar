"""ReplyRadar — Stripe billing configuration and products."""

import os

STRIPE_SECRET = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")

# ── Products & Prices (create in Stripe Dashboard, reference here) ──

PLANS = {
    "starter": {
        "name": "ReplyRadar Starter",
        "price_id": None,  # Fill after creating in Stripe Dashboard
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
        "price_id": None,
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
        "price_id": None,
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
