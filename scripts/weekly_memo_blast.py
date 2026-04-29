#!/usr/bin/env python3
"""Tier 1 Weekly Memo blast — fan out the Sunday/Monday cron.

Runs `WeeklyMemoService().run_for_user(user)` for every "active" user, where
active is defined as:

    1. subscription_tier ∈ {pro, premium}, AND
    2. has at least one Position row.

(There is no `last_login` column in the User model today — when one is
added, gate (1) should add a 30-day recency clause. Per spec, the
position-count gate substitutes for "actually using the product" today.)

The script wraps `WeeklyMemoService.run_weekly()` thinly so the GitHub
Actions cron has a single, predictable shell entrypoint that prints a
summary block plus a non-zero exit code on partial failure.

Usage:
    # Default: target_date = today
    python3 scripts/weekly_memo_blast.py

    # Explicit target date (replays prior weeks for QA/backfill)
    python3 scripts/weekly_memo_blast.py --target-date 2026-04-26

    # Dry-run: fetch user list, render previews, but skip email + persist
    python3 scripts/weekly_memo_blast.py --dry-run

Exit codes:
    0   all users succeeded (or were correctly skipped)
    1   one or more users failed mid-blast (non-fatal — the rest ran)
    2   fatal error before the blast started (DB unreachable, etc.)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date

logger = logging.getLogger("weekly_memo_blast")


_PAID_TIERS = ("pro", "premium")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run the Tier 1 Weekly Memo blast for all active users.",
    )
    p.add_argument(
        "--target-date",
        dest="target_date",
        default=None,
        help="ISO date (YYYY-MM-DD). Default: today.",
    )
    p.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Generate previews but skip email send and DB persist.",
    )
    p.add_argument(
        "--verbose",
        dest="verbose",
        action="store_true",
        help="Verbose per-user logging.",
    )
    return p.parse_args()


def _resolve_active_users():
    """Return (queryset list, raw count of paid users).

    Active = paid tier + at least one position. The position check is a
    Python-side filter so we do not rely on a JOIN (the Position table is
    small enough that the round trip is negligible compared to the
    memo-render pipeline downstream).
    """
    from models import Position, User

    paid_users = (
        User.query
        .filter(User.subscription_tier.in_(list(_PAID_TIERS)))
        .all()
    )
    active = []
    for u in paid_users:
        try:
            if Position.query.filter_by(user_id=u.id).count() > 0:
                active.append(u)
        except Exception as exc:
            logger.warning("position count failed for user %s: %s", u.id, exc)
    return active, len(paid_users)


def _run_blast(target_date: date | None, dry_run: bool) -> dict:
    """End-to-end blast. Returns a summary dict matching `run_weekly`."""
    from extensions import db
    from services.artifacts.weekly_memo_service import WeeklyMemoService

    active, total_paid = _resolve_active_users()
    logger.info(
        "weekly memo blast: %d paid users, %d active (have positions)",
        total_paid, len(active),
    )

    target_date = target_date or date.today()
    svc = WeeklyMemoService()

    successes = 0
    failures = 0
    skipped = 0

    for user in active:
        try:
            result = svc.run_for_user(
                user,
                target_date=target_date,
                send=not dry_run,
            )
            if result is None:
                skipped += 1
                logger.info("user %s skipped (empty portfolio)", user.id)
            else:
                successes += 1
                if dry_run:
                    # Roll back the persistence side-effect — `run_for_user`
                    # commits unconditionally, so we explicitly clean up.
                    try:
                        db.session.delete(result)
                        db.session.commit()
                    except Exception as exc:
                        logger.warning(
                            "dry-run rollback failed for user %s: %s",
                            user.id, exc,
                        )
        except Exception as exc:
            db.session.rollback()
            failures += 1
            logger.error("weekly memo failed for user %s: %s", user.id, exc)

    return {
        "date":           target_date.isoformat(),
        "paid_users":     total_paid,
        "active_users":   len(active),
        "attempted":      len(active),
        "success":        successes,
        "failed":         failures,
        "skipped":        skipped,
        "dry_run":        dry_run,
    }


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    target_date: date | None = None
    if args.target_date:
        try:
            target_date = date.fromisoformat(args.target_date)
        except ValueError:
            logger.error(
                "invalid --target-date: %r (expected YYYY-MM-DD)",
                args.target_date,
            )
            return 2

    # Late import — keeps `--help` fast and avoids touching the DB unless
    # we actually need to run the blast.
    try:
        from app import create_app
    except Exception as exc:
        logger.error("could not import app factory: %s", exc)
        return 2

    try:
        app = create_app()
    except Exception as exc:
        logger.error("create_app() failed: %s", exc)
        return 2

    with app.app_context():
        try:
            summary = _run_blast(target_date=target_date, dry_run=args.dry_run)
        except Exception as exc:
            logger.exception("fatal error during blast: %s", exc)
            return 2

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 1 if summary["failed"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
