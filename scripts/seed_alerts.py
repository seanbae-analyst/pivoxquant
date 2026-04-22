"""Seed 8 sample notification-bell alerts for the test user.

Usage:
    python3 scripts/seed_alerts.py                 # seeds seanbae1521@gmail.com
    python3 scripts/seed_alerts.py --email foo@bar # seeds a specific user
    python3 scripts/seed_alerts.py --wipe          # deletes existing first

Observation-only language — BUY/SELL/recommend/advice/target banned.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Make project root importable when run directly.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from models import Alert, User  # noqa: E402


SEED_ALERTS = [
    {
        "kind": "price_52w_high",
        "title": "AAPL reached 52-week high",
        "body": "Observation — price level noted against trailing 52-week range.",
        "ticker": "AAPL",
        "link": "/detail/AAPL",
        "offset_minutes": 30,
    },
    {
        "kind": "concentration_alert",
        "title": "Portfolio concentration — Tech 34.2%",
        "body": "Observation — single-sector weighting exceeds 30% of portfolio.",
        "ticker": None,
        "link": "/risk",
        "offset_minutes": 2 * 60,
    },
    {
        "kind": "macro_event",
        "title": "FOMC meeting tomorrow 2 PM ET",
        "body": "Macro calendar event noted.",
        "ticker": None,
        "link": "/market",
        "offset_minutes": 6 * 60,
    },
    {
        "kind": "artifact_ready",
        "title": "Weekly Memo ready",
        "body": "Artifact rendered and available for review.",
        "ticker": None,
        "link": "/reports",
        "offset_minutes": 24 * 60,
    },
    {
        "kind": "account_sync",
        "title": "KIS account sync complete",
        "body": "Positions refreshed from broker.",
        "ticker": None,
        "link": "/settings",
        "offset_minutes": 2 * 24 * 60,
    },
    {
        "kind": "watchlist_event",
        "title": "NVDA movement noted",
        "body": "Watchlist observation — significant intraday move recorded.",
        "ticker": "NVDA",
        "link": "/detail/NVDA",
        "offset_minutes": 3 * 24 * 60,
    },
    {
        "kind": "price_52w_low",
        "title": "INTC at 52-week low",
        "body": "Observation — price level noted against trailing 52-week range.",
        "ticker": "INTC",
        "link": "/detail/INTC",
        "offset_minutes": 4 * 24 * 60,
    },
    {
        "kind": "artifact_ready",
        "title": "Earnings Pre-Brief ready",
        "body": "Artifact rendered and available for review.",
        "ticker": None,
        "link": "/reports",
        "offset_minutes": 5 * 24 * 60,
    },
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default="seanbae1521@gmail.com")
    parser.add_argument("--wipe", action="store_true", help="Delete existing alerts first")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        user = User.query.filter_by(email=args.email).first()
        if user is None:
            print(f"[seed_alerts] user not found: {args.email}")
            print("[seed_alerts] available users:")
            for u in User.query.limit(5).all():
                print(f"  - {u.email}")
            sys.exit(1)

        if args.wipe:
            count = Alert.query.filter_by(user_id=user.id).delete()
            print(f"[seed_alerts] wiped {count} existing alerts for {user.email}")

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        inserted = 0
        for spec in SEED_ALERTS:
            created_at = now - timedelta(minutes=spec["offset_minutes"])
            a = Alert(
                user_id=user.id,
                kind=spec["kind"],
                title=spec["title"],
                body=spec["body"],
                ticker=spec["ticker"],
                link=spec["link"],
                message=spec["title"],  # legacy mirror
                is_read=False,
                created_at=created_at,
            )
            db.session.add(a)
            inserted += 1

        db.session.commit()
        print(f"[seed_alerts] inserted {inserted} alerts for {user.email} (user_id={user.id})")
        for spec in SEED_ALERTS:
            print(f"  • [{spec['kind']}] {spec['title']}")


if __name__ == "__main__":
    main()
