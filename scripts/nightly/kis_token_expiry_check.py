#!/usr/bin/env python3
"""
Nightly KIS token expiry early-warning (O-N).
=============================================

KIS OAuth tokens have a 24h server-side TTL but ``KISTokenManager``
rotates them at 12h. Day-to-day this is invisible — the per-request
hot path proactively refreshes when <1h remains. But two edge cases
need a human-visible alarm:

  (a) KIS_APP_KEY / KIS_APP_SECRET expiry: KIS issues *application*
      keys with a 1-year expiry. When the appkey itself is near expiry
      the auto-rotate keeps working — until day N it suddenly returns
      ``EGW00001`` and our entire KR data path goes dark.
  (b) Persistent token-cache file (``~/.kis_token_cache.json``) holds
      an ``expires`` ISO timestamp. If the singleton has been alive for
      a long time, peeking at the cache file is the cheapest way to
      see "next-refresh-within-N-days" without re-calling KIS (which
      is itself 1/minute rate-limited).

This script reads the on-disk cache via the same path KISTokenManager
uses, and posts a Slack alert when the token's ``expires`` is within
7 days. It also dedupes via ``state/kis_token_expiry_alerted.json`` so
the alert doesn't spam Slack daily once the window has been entered —
one alert per expiry timestamp.

Graceful degradation
--------------------
- ``KIS_APP_KEY`` / ``KIS_APP_SECRET`` missing → log + exit 0 (dev/CI).
- Cache file missing → log + exit 0 (cold start; nothing to alert on).
- ``SLACK_WEBHOOK_URL`` unset → log to stderr + exit 0.

Exit codes
----------
- ``0`` — nothing to do (no expiry, alert already sent, or env unset)
- ``1`` — alert posted (expiry within window)
- ``2`` — unexpected error decoding cache (Sentry captured)

Cost
----
- Slack webhook free + Sentry free tier + local file I/O only
- No KIS API call (the whole point — KIS is 1/minute rate-limited)
- 추가 비용 0원
"""
from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("kis_token_expiry")

# Mirror the constants in services/kis/token_manager.py.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CACHE_FILE = _PROJECT_ROOT / ".kis_token_cache.json"
_CACHE_HEADER = b"PIVOX-AES-GCM-v1\n"
_CACHE_AAD = b"kis-token-cache"

# Where we record "last alerted for expiry=X" so re-runs within the
# same window don't spam Slack.
_STATE_DIR = _PROJECT_ROOT / "state"
_STATE_FILE = _STATE_DIR / "kis_token_expiry_alerted.json"

# Default early-warning window: alert when ≤ 7 days remain.
_DEFAULT_WINDOW_DAYS = 7


def _has_kis_credentials() -> bool:
    return bool(
        os.environ.get("KIS_APP_KEY", "").strip()
        and os.environ.get("KIS_APP_SECRET", "").strip()
    )


def read_token_expiry(cache_path: Path = _CACHE_FILE) -> datetime | None:
    """Return the cached token's expiry as tz-aware UTC datetime.

    Handles both the AES-GCM ciphertext format (current) and the legacy
    plaintext JSON format (pre-2026-05-18). Returns ``None`` when the
    file is missing, unreadable, or doesn't contain a valid expiry.

    Never raises — caller treats ``None`` as "nothing to alert on".
    """
    try:
        if not cache_path.exists():
            logger.info("KIS token cache absent at %s — nothing to check", cache_path)
            return None
        raw = cache_path.read_bytes()
        if not raw:
            return None

        if raw.startswith(_CACHE_HEADER):
            try:
                from services.crypto_service import decrypt as _decrypt
                body_b64 = raw[len(_CACHE_HEADER):].decode("ascii").strip()
                plaintext = _decrypt(body_b64, aad=_CACHE_AAD)
                cache = json.loads(plaintext)
            except Exception as exc:
                logger.warning("KIS cache decrypt failed: %s", type(exc).__name__)
                _capture_sentry_exception(exc)
                return None
        else:
            try:
                cache = json.loads(raw.decode("utf-8"))
            except Exception:
                logger.warning("KIS cache plaintext parse failed")
                return None

        expires_raw = cache.get("expires")
        if not expires_raw:
            return None
        expires = datetime.fromisoformat(expires_raw)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return expires
    except Exception as exc:
        logger.exception("KIS cache read failed: %s", exc)
        _capture_sentry_exception(exc)
        return None


def _load_alerted_state() -> dict[str, Any]:
    """Read the dedup state file. Returns {} if missing/malformed."""
    try:
        if _STATE_FILE.exists():
            return json.loads(_STATE_FILE.read_text())
    except Exception:
        logger.debug("alert state read failed", exc_info=True)
    return {}


def _save_alerted_state(state: dict[str, Any]) -> None:
    """Write dedup state. Best-effort — failure logged, never raises."""
    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        _STATE_FILE.write_text(json.dumps(state, indent=2))
    except Exception:
        logger.warning("alert state write failed", exc_info=True)


def _capture_sentry_exception(exc: Exception) -> None:
    try:
        import sentry_sdk
        sentry_sdk.capture_exception(exc)
    except Exception:
        logger.debug("sentry capture skipped", exc_info=True)


def _capture_sentry_message(msg: str) -> None:
    try:
        import sentry_sdk
        sentry_sdk.capture_message(msg, level="warning")
    except Exception:
        logger.debug("sentry capture skipped", exc_info=True)


def _post_slack(message: str) -> bool:
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not webhook_url:
        logger.info("SLACK_WEBHOOK_URL unset — alert printed only")
        print(message, file=sys.stderr)
        return False
    try:
        import requests
        resp = requests.post(webhook_url, json={"text": message}, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as exc:
        logger.exception("Slack post failed: %s", exc)
        _capture_sentry_exception(exc)
        return False


def evaluate(
    expires: datetime | None,
    window_days: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Pure decision function (no I/O) — easy to unit-test.

    Returns:
      ``{"should_alert": bool, "days_left": float | None, "expires": str | None}``
    """
    now = now or datetime.now(timezone.utc)
    if expires is None:
        return {"should_alert": False, "days_left": None, "expires": None}
    delta = expires - now
    days_left = delta.total_seconds() / 86_400
    should = days_left <= window_days
    return {
        "should_alert": should,
        "days_left": days_left,
        "expires": expires.isoformat(),
    }


def _format_alert(days_left: float, expires_iso: str) -> str:
    if days_left < 0:
        urgency = "🟥 *KIS 토큰 만료 (이미 만료됨)*"
    elif days_left < 1:
        urgency = "🟥 *KIS 토큰 만료 임박 (24시간 이내)*"
    elif days_left < 3:
        urgency = "🟧 *KIS 토큰 만료 임박 (3일 이내)*"
    else:
        urgency = "🟨 *KIS 토큰 만료 D-7 알림*"
    return (
        f"{urgency}\n"
        f"• 만료: {expires_iso}\n"
        f"• 잔여: {days_left:.1f}일\n"
        f"• Action: KIS_APP_KEY / KIS_APP_SECRET 만료일 점검 "
        f"(한국투자증권 OpenAPI 콘솔) + Railway env 갱신"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--window-days", type=int, default=_DEFAULT_WINDOW_DAYS,
        help=f"alert window in days (default {_DEFAULT_WINDOW_DAYS})",
    )
    parser.add_argument(
        "--cache-path", default=str(_CACHE_FILE),
        help="override token cache path (testing)",
    )
    parser.add_argument(
        "--state-path", default=None,
        help="override dedup state path (testing)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="evaluate but do not post Slack",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="ignore dedup state (re-alert)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    )

    # Graceful skip if KIS credentials never configured (dev/CI).
    if not _has_kis_credentials():
        logger.info("KIS_APP_KEY / KIS_APP_SECRET unset — skip")
        return 0

    cache_path = Path(args.cache_path)
    expires = read_token_expiry(cache_path)
    decision = evaluate(expires, args.window_days)

    logger.info(
        "KIS token expiry check: expires=%s days_left=%s should_alert=%s",
        decision["expires"], decision["days_left"], decision["should_alert"],
    )

    if not decision["should_alert"]:
        return 0

    # Dedup: state["<expires_iso>"] = "<alert_sent_at_iso>"
    # Declare globals before *any* read so the rebind below is legal.
    global _STATE_DIR, _STATE_FILE
    if args.state_path:
        # Redirect module-level _STATE_DIR / _STATE_FILE for the duration
        # of this call. Cheap because the module-level helpers re-read
        # via the global, but main() owns the override.
        _STATE_FILE = Path(args.state_path)
        _STATE_DIR = _STATE_FILE.parent

    state = _load_alerted_state()
    expiry_key = decision["expires"]
    if not args.force and state.get(expiry_key):
        logger.info(
            "already alerted for expiry=%s at %s — skip (use --force to override)",
            expiry_key, state[expiry_key],
        )
        return 0

    message = _format_alert(decision["days_left"], decision["expires"])
    if args.dry_run:
        logger.info("dry-run: would alert: %s", message)
        return 1

    posted = _post_slack(message)
    _capture_sentry_message(
        f"KIS token expiry within {args.window_days}d "
        f"({decision['days_left']:.1f}d left)"
    )
    if posted:
        state[expiry_key] = datetime.now(timezone.utc).isoformat()
        _save_alerted_state(state)
    return 1


if __name__ == "__main__":
    sys.exit(main())
