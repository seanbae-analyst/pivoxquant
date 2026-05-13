"""Prod schema parity check — alembic head vs actual columns.

Usage
-----
    DATABASE_URL=postgresql://... python scripts/verify_prod_schema.py

Or against Railway prod (read-only):

    DATABASE_URL=$(railway variables --service Postgres --kv \
        | grep '^DATABASE_PUBLIC_URL=' | cut -d= -f2-) \
    python scripts/verify_prod_schema.py

Exit codes
----------
    0  schema parity is OK (all critical columns present)
    1  schema drift detected (missing columns / tables / indexes)
    2  cannot reach DB or unexpected error

Why this exists
---------------
PivoxQuant prod runs on a hybrid migration strategy:

  1. ``db.create_all()`` creates tables on first boot from SQLAlchemy models.
  2. ``_do_migrations()`` in app.py runs idempotent ``ADD COLUMN`` guards
     for every model column added after the initial baseline.
  3. ``flask db upgrade`` (alembic) is best-effort — fails silently on a
     prod DB that was created via path (1) because alembic_version table
     doesn't exist and early migrations (003/004/005/007/...) are not
     idempotent ``op.create_table`` calls that error on existing tables.

This script is the canonical check that — regardless of which path
populated the schema — every column the running code reads/writes is
actually present in the DB. Run it after any deploy that touches schema.
"""
from __future__ import annotations

import os
import sys
from typing import Iterable

import psycopg2  # type: ignore

# (table, column) pairs that the running code expects to be present.
# Keep this in lockstep with the latest model + migration.
REQUIRED_COLUMNS: list[tuple[str, str]] = [
    # --- users (latest = 032_users_is_simulated) ---
    ("users", "id"),
    ("users", "email"),
    ("users", "subscription_tier"),
    ("users", "email_opt_out"),                  # 021
    ("users", "marketing_consent_at"),           # 023
    ("users", "cross_border_consent_at"),        # 024
    ("users", "birthdate"),                      # 031
    ("users", "is_simulated"),                   # 032 — SHIP-BLOCKER P0
    # --- broker_connections (encrypted) ---
    ("broker_connections", "encrypted_app_key"),
    ("broker_connections", "encrypted_app_secret"),
    ("broker_connections", "encrypted_account_no"),
    ("broker_connections", "account_prod"),
    ("broker_connections", "encrypted_access_token"),
    ("broker_connections", "encryption_key_version"),
    # --- artifacts (SendGrid event webhook tracking, migration 025) ---
    ("artifacts", "bounced_at"),
    ("artifacts", "unsubscribed_at"),
    ("artifacts", "sg_message_id"),
    # --- alerts (notification bell, migration 022) ---
    ("alerts", "kind"),
    ("alerts", "title"),
    ("alerts", "body"),
    ("alerts", "link"),
    ("alerts", "read_at"),
    # --- watchlist (note, migration 022) ---
    ("watchlist", "note"),
]

REQUIRED_TABLES: list[str] = [
    "users",
    "positions",
    "alerts",
    "artifacts",
    "watchlist",
    "broker_connections",
    "signal_cache",
    "trade_history",
    "investment_profiles",
    "morning_briefs",
    "persona_snapshots",
    "pre_trade_reflections",
    "behavioral_scores",
    "ai_twin_portfolios",
    "ai_twin_positions",
    "ai_twin_trades",
    "ai_twin_weekly_reports",
    "processed_stripe_events",       # 028
    "user_referrals",                # 008
    "companion_waitlist",            # 012
    "persona_group_stats",           # 013
    "user_agent_audit",              # 010
    "push_subscriptions",
    "portfolio_shares",
    "position_dd_checks",            # 022
    "agent_kill_switch",
    "artifact_feedback",
    "weekly_pulse",
]

# Recommended (perf indexes from 030, FK cascade from 029, positions unique
# from 027). Reported as WARN, not FAIL — they affect performance and PIPA
# §35 cascade safety but don't cause endpoint 500s.
# Names MUST match migrations/versions/030_perf_indexes.py _INDEXES.
RECOMMENDED_INDEXES: list[tuple[str, str]] = [
    ("alerts", "ix_alerts_user_created"),                # 030
    ("alerts", "ix_alerts_user_ticker_created"),         # 030
    ("alerts", "ix_alerts_user_unread"),                 # 030
    ("trade_history", "ix_trade_history_user_traded"),   # 030
    ("signal_cache", "ix_signal_cache_updated"),         # 030
    ("persona_snapshots", "ix_persona_snapshots_user_created"),  # 030
    ("positions", "uq_positions_user_ticker"),           # 027
]


def _normalize_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url


def _check(conn, sql: str, params: tuple = ()) -> bool:
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur.fetchone() is not None


def main(argv: Iterable[str]) -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        return 2

    url = _normalize_url(url)
    try:
        # Default to require for Railway public proxy; local can be 'disable'.
        ssl = "require" if "railway" in url or "rlwy" in url else "prefer"
        conn = psycopg2.connect(url, sslmode=ssl, connect_timeout=10)
    except Exception as exc:
        print(f"ERROR: cannot connect to DB: {exc}", file=sys.stderr)
        return 2

    fail_count = 0
    warn_count = 0

    print("=== Tables ===")
    for t in REQUIRED_TABLES:
        ok = _check(
            conn,
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name=%s",
            (t,),
        )
        status = "OK" if ok else "MISSING"
        if not ok:
            fail_count += 1
        print(f"  {status:8} {t}")

    print("\n=== Required columns ===")
    for t, c in REQUIRED_COLUMNS:
        ok = _check(
            conn,
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=%s AND column_name=%s",
            (t, c),
        )
        status = "OK" if ok else "MISSING"
        if not ok:
            fail_count += 1
        print(f"  {status:8} {t}.{c}")

    print("\n=== alembic_version ===")
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name='alembic_version'"
    )
    if cur.fetchone():
        cur.execute("SELECT version_num FROM alembic_version")
        rows = [r[0] for r in cur.fetchall()]
        print(f"  alembic_version rows: {rows}")
    else:
        warn_count += 1
        print("  WARN: alembic_version table is MISSING — alembic state untracked")
        print("        Fix: `flask db stamp 032_users_is_simulated` to register state.")

    print("\n=== Recommended indexes / unique constraints ===")
    for t, idx in RECOMMENDED_INDEXES:
        ok = _check(
            conn,
            "SELECT 1 FROM pg_indexes "
            "WHERE schemaname='public' AND tablename=%s AND indexname=%s",
            (t, idx),
        )
        status = "OK" if ok else "WARN"
        if not ok:
            warn_count += 1
        print(f"  {status:8} {t}.{idx}")

    conn.close()

    print("\n=== Summary ===")
    print(f"  FAIL: {fail_count}")
    print(f"  WARN: {warn_count}")

    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
