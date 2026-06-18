"""Cross-process mutual exclusion for queue-drain ticks.

Why
===
The scheduled-email dispatchers (onboarding / retention / checkout-followup)
pull due rows with ``SELECT … FOR UPDATE SKIP LOCKED`` and then commit PER
ROW. On PostgreSQL the first ``commit()`` ends the transaction and releases
*all* row locks taken by that SELECT — every later row in the batch is
processed unlocked, so an OVERLAPPING drain (Railway in-process APScheduler
tick racing the macOS crontab fallback, or two crontab fires) can re-select
and re-send those rows. 2026-06-09 bug-hunt W2-P2.

Rather than forcing the "retire one of the two schedulers" architecture
decision, each drain takes a short-lived PostgreSQL advisory lock for the
duration of its tick — whichever process loses simply skips (the winner is
already draining the same queue). Same mechanics as app.py CONN-001
(`_try_acquire_scheduler_lock`): a raw psycopg2 connection outside the
SQLAlchemy pool, `pg_try_advisory_lock`, released explicitly (and by PG on
disconnect if the process dies mid-drain).

SQLite (dev/test) has no advisory locks and no process overlap → always
acquires. Any unexpected error also yields True (fail-safe: a missed lock
must never stop email delivery; the worst case is the pre-existing race).
"""
from __future__ import annotations

import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Base key deliberately distinct from app.py _SCHEDULER_LOCK_KEY (0x5049564F58
# = "PIVOX"): these locks serialize a single drain *tick*, not scheduler
# ownership. Each queue gets its own key so different queues never contend.
_BASE_KEY = 0x50_49_56_4F_58_00  # "PIVOX" << 8

DRAIN_ONBOARDING = _BASE_KEY + 1
DRAIN_RETENTION = _BASE_KEY + 2
DRAIN_CHECKOUT_FOLLOWUP = _BASE_KEY + 3


@contextmanager
def drain_lock(key: int):
    """Yield True if this process owns the drain tick, False to skip.

    Usage::

        with drain_lock(DRAIN_ONBOARDING) as acquired:
            if not acquired:
                return {"skipped_lock": 1}
            ...drain...
    """
    conn = None
    got = True
    try:
        try:
            from config import IS_POSTGRES
        except Exception:
            IS_POSTGRES = False
        if IS_POSTGRES:
            import psycopg2
            from config import _db_url

            conn = psycopg2.connect(_db_url, connect_timeout=5)
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("SELECT pg_try_advisory_lock(%s)", (key,))
                got = bool(cur.fetchone()[0])
            if not got:
                conn.close()
                conn = None
    except Exception:
        # Fail-safe: never block email delivery on lock plumbing.
        logger.exception("drain_lock(%s): acquire failed — proceeding unlocked", key)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            conn = None
        got = True

    try:
        yield got
    finally:
        if conn is not None:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_unlock(%s)", (key,))
            except Exception:
                logger.debug("drain_lock(%s): unlock failed (PG will reap)", key)
            try:
                conn.close()
            except Exception:
                pass
