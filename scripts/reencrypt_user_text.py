#!/usr/bin/env python3
"""Roll every EncryptedText column forward to the current key version.

Why
===
``services.crypto_service`` now keeps a *key ring*: user free-text is stored as
``pqenc:{version}:…`` and the version selects the decryption key. Rotating the
user-text key is therefore safe — you add ``PIVOX_USER_TEXT_KEY_V2`` (base64, 32
bytes), new writes carry ``pqenc:2:``, and existing ``pqenc:1:`` rows still
decrypt with the v1 (master) key.

This script performs the *eager* part of a rotation: it re-encrypts any row
still on an older key version up to the current one, so the old key can
eventually be retired. It is OPTIONAL — rows also roll forward lazily whenever
they are next written through the ORM — but a sweep means you are not depending
on every row being touched.

Safety
======
- Dry-run by default. Pass ``--apply`` to actually write.
- Per (table, column) it reads the *raw stored* value (bypassing the ORM
  decoder), asks ``crypto_service.reencrypt_user_text`` for a rolled-forward
  ciphertext, and only UPDATEs rows that changed (current-version rows,
  legacy plaintext, and NULLs are skipped — ``reencrypt_user_text`` returns
  ``None`` for them).
- Idempotent: a second run is a no-op once everything is at the current version.
- Never decrypts to plaintext on disk or in logs — it moves ciphertext to
  ciphertext.

Usage
=====
    # See what would change (no writes):
    python scripts/reencrypt_user_text.py

    # Apply, after PIVOX_USER_TEXT_KEY_V2 is set in the environment:
    python scripts/reencrypt_user_text.py --apply
"""
from __future__ import annotations

import argparse
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("reencrypt_user_text")


# Every column that uses services.crypto_service.EncryptedText. Keep in sync
# with the models — a missing entry just means that column is not swept.
ENCRYPTED_COLUMNS = [
    ("pre_trade_reflections", "rationale"),
    ("pre_trade_reflections", "devil_advocate_seen"),
    ("positions", "thesis"),
    ("positions", "thesis_reason"),
    ("watchlist", "note"),
    ("position_dd_checks", "note"),
    ("weekly_pulse", "worry"),
    ("weekly_pulse", "learn"),
    ("behavioral_scores", "notes"),
    ("inquiries", "body"),
    ("inquiries", "admin_reply"),
    ("ai_twin_trades", "rationale"),
    ("ai_twin_weekly_reports", "rationale_summary"),
]


def _sweep(apply: bool) -> dict:
    from sqlalchemy import text

    from extensions import db
    from services import crypto_service as cs

    current = cs.current_text_key_version()
    logger.info(
        "current user-text key version = %s (ring versions: %s)",
        current, cs.user_text_key_versions(),
    )

    totals = {"scanned": 0, "rolled": 0, "skipped": 0}
    for table, column in ENCRYPTED_COLUMNS:
        try:
            rows = db.session.execute(
                text(
                    f"SELECT id, {column} FROM {table} "
                    f"WHERE {column} LIKE 'pqenc:%'"
                )
            ).fetchall()
        except Exception as exc:
            logger.warning("skip %s.%s (table/column unavailable): %s", table, column, exc)
            continue

        rolled = 0
        for row_id, stored in rows:
            totals["scanned"] += 1
            new_ct = cs.reencrypt_user_text(stored)
            if new_ct is None:
                totals["skipped"] += 1
                continue
            rolled += 1
            if apply:
                db.session.execute(
                    text(f"UPDATE {table} SET {column} = :v WHERE id = :id"),
                    {"v": new_ct, "id": row_id},
                )
        if rolled:
            logger.info(
                "%s.%s: %s row(s) %s -> v%s",
                table, column, rolled,
                "rolled" if apply else "WOULD roll", current,
            )
        totals["rolled"] += rolled

    if apply:
        db.session.commit()
        logger.info("committed.")
    return totals


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true",
        help="actually write the rolled-forward ciphertext (default: dry-run)",
    )
    args = parser.parse_args()

    from app import create_app

    app = create_app()
    with app.app_context():
        totals = _sweep(apply=args.apply)

    mode = "APPLIED" if args.apply else "DRY-RUN"
    logger.info(
        "%s — scanned=%s rolled=%s skipped=%s",
        mode, totals["scanned"], totals["rolled"], totals["skipped"],
    )
    if not args.apply and totals["rolled"]:
        logger.info("re-run with --apply to write these changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
