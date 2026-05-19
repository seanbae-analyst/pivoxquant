#!/usr/bin/env python3
"""
Nightly ticker-health stale-detector alert (O-E).
==================================================

Wraps ``scripts/nightly/ticker_health.py`` outputs (the JSONL artifact)
and Slack-alerts when too many tickers are stale post-market-close.

Why a wrapper, not a patch to ticker_health.py?
-----------------------------------------------
``ticker_health.py`` runs from a GitHub Action and writes JSONL to disk.
Its responsibility is *probing* — it stays alertless so a single-process
failure doesn't gate the artifact upload. This wrapper reads the
artifact, applies the stale rule, and is the only thing that calls
Slack/Sentry. Single-responsibility split.

Stale detection rule
---------------------
For each ticker in the JSONL we count "issue == True" rows. We split
by KR vs US market because their close times differ (KR closes 15:30
KST, US closes 16:00 ET ≈ 06:00 KST next day). The wrapper takes a
``--market`` flag so it can be scheduled separately for each region.

Threshold default: 5% of probed tickers stale → alert (overridable
via ``--threshold-pct``). The flag is intentionally generous because
KIS occasionally rate-limits a handful of symbols on a busy day; a
genuine outage shows up as 30-50% stale immediately.

Exit codes
----------
- ``0`` — under threshold (or no artifact to read)
- ``1`` — stale ratio over threshold (CC scheduled-task picks this up)
- ``2`` — usage error (missing flag etc.)

Cost
----
- Slack webhook free + Sentry free tier
- No external API calls — reads local artifact only
- 추가 비용 0원

CI environment safety
---------------------
``SLACK_WEBHOOK_URL`` or ``SENTRY_DSN`` unset → log + skip the alert.
Never raises. This keeps unit-tests and dry-run executions silent.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger("ticker_health_alert")

# KR tickers are 6-digit numeric (005930, 000660, etc.). US tickers
# include letters. ``ticker_health.py`` keeps the same convention so
# we can classify cheaply.
def _is_kr_ticker(ticker: str) -> bool:
    return ticker.isdigit() and len(ticker) == 6


def _classify(ticker: str) -> str:
    return "KR" if _is_kr_ticker(ticker) else "US"


def _read_artifact(path: Path) -> list[dict[str, Any]]:
    """Read newline-delimited JSON. Tolerant of partial/missing files —
    the wrapper must never crash the cron, only alert."""
    if not path.exists():
        logger.info("artifact not found: %s — skipping alert", path)
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning("skipping malformed JSONL line: %s", line[:80])
    except OSError as exc:
        logger.warning("failed to read artifact %s: %s", path, exc)
    return rows


def compute_stale_stats(
    rows: list[dict[str, Any]], market: str,
) -> dict[str, Any]:
    """Filter rows by market and compute the stale ratio.

    market: "KR", "US", or "ALL"
    """
    market = market.upper()
    if market not in ("KR", "US", "ALL"):
        raise ValueError(f"invalid market: {market}")

    filtered = [
        r for r in rows
        if market == "ALL" or _classify(r.get("ticker", "")) == market
    ]
    total = len(filtered)
    issues = [r for r in filtered if r.get("issue")]
    stale_count = len(issues)
    ratio = (stale_count / total) if total > 0 else 0.0

    return {
        "market": market,
        "total": total,
        "stale_count": stale_count,
        "stale_ratio": ratio,
        "samples": [
            {"ticker": r.get("ticker"), "reason": r.get("reason")}
            for r in issues[:5]
        ],
    }


def _post_slack(message: str) -> bool:
    """Slack webhook. Never raises. Returns True on success."""
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
        try:
            import sentry_sdk
            sentry_sdk.capture_exception(exc)
        except Exception:
            pass
        return False


def _capture_sentry(stats: dict[str, Any]) -> None:
    """Best-effort Sentry capture_message — never raises."""
    try:
        import sentry_sdk
        sentry_sdk.capture_message(
            (
                f"KIS ticker stale rate {stats['stale_ratio']:.1%} "
                f"({stats['stale_count']}/{stats['total']}) on "
                f"market={stats['market']}"
            ),
            level="warning",
        )
    except Exception:
        logger.debug("sentry capture skipped", exc_info=True)


def _format_alert(stats: dict[str, Any], threshold_pct: float) -> str:
    samples_str = (
        "\n".join(
            f"  • `{s['ticker']}`: {s['reason']}" for s in stats["samples"]
        )
        or "  (no samples)"
    )
    return (
        f":rotating_light: *KIS 시세 stale 임계치 초과* "
        f"(market={stats['market']})\n"
        f"• stale: {stats['stale_count']}/{stats['total']} "
        f"({stats['stale_ratio']:.1%}) > 임계치 {threshold_pct:.1%}\n"
        f"• 샘플:\n{samples_str}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--results-path",
        default=os.environ.get(
            "RESULTS_PATH", "nightly_artifacts/ticker_health.jsonl",
        ),
        help="ticker_health.jsonl path",
    )
    parser.add_argument(
        "--market", choices=["KR", "US", "ALL"], default="ALL",
        help="restrict to KR / US tickers (default ALL)",
    )
    parser.add_argument(
        "--threshold-pct", type=float, default=0.05,
        help="stale ratio threshold (default 0.05 = 5%%)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="compute but do not post Slack / Sentry",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    )

    rows = _read_artifact(Path(args.results_path))
    if not rows:
        # Nothing to evaluate — graceful exit. ticker_health.py may not
        # have run yet, or artifact path mismatch. Don't false-alarm.
        return 0

    stats = compute_stale_stats(rows, args.market)
    logger.info(
        "ticker_health stats: market=%s total=%d stale=%d ratio=%.3f",
        stats["market"], stats["total"], stats["stale_count"],
        stats["stale_ratio"],
    )

    if stats["total"] == 0:
        return 0

    if stats["stale_ratio"] > args.threshold_pct:
        message = _format_alert(stats, args.threshold_pct)
        if not args.dry_run:
            _post_slack(message)
            _capture_sentry(stats)
        else:
            logger.info("dry-run: would alert: %s", message)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
