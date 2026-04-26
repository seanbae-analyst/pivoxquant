"""
PivoxQuant — News Service

Legal-compliant per-ticker news.

Sources:
  - KR ticker (.KS / .KQ) → Naver Developers Search News API (official,
    commercial-use-allowed under the Naver Developers Agreement §2 once
    NAVER_CLIENT_ID / NAVER_CLIENT_SECRET are set).
  - US ticker              → FMP `/news/stock` (paid subscription, commercial OK).
    No RSS fallback. When FMP returns nothing the caller sees an empty list
    and the UI renders a "no recent news" state.

Removed (2026-04-19):
  - ``get_news_google``      — Google News RSS is grey-area for commercial
                               use and Google has announced its retirement.
  - ``get_news_yahoo_rss``   — Yahoo Finance RSS ToS forbids commercial use
                               and it was rate-limited into uselessness.
  - Naver mobile-JSON scrape — violated Naver's robots/scraping ToS (already
                               removed in commit 2421871, documented here).

Response schema (stable — matches the FMP path the frontend consumes):

    {
        "title":     str,
        "summary":   str,   # may be ""
        "published": str,   # ISO-8601 or raw RFC822 (readable)
        "link":      str,
        "source":    str,
    }

Never raises — returns [] on any failure. Times out in ~8s.
"""

from __future__ import annotations

import logging
import os
import re
import time
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Dict, List

import requests

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "PivoxQuant/1.0 (contact: seanbae1521@gmail.com)",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

_REQUEST_TIMEOUT = 8  # seconds
_MAX_ITEMS = 15

# ── Module-level cache (30 min TTL) ─────────────────────────────────────────
_CACHE: Dict[str, tuple] = {}  # {key: (ts, items)}
_CACHE_TTL = 1800  # 30 min


def _cache_get(key: str):
    hit = _CACHE.get(key)
    if not hit:
        return None
    ts, items = hit
    if time.time() - ts > _CACHE_TTL:
        return None
    return items


def _cache_set(key: str, items: list):
    _CACHE[key] = (time.time(), items)


_TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(raw: str) -> str:
    return unescape(_TAG_RE.sub("", raw or "")).strip()


def _rfc822_to_iso(raw: str) -> str:
    """Convert Naver's RFC822 `pubDate` ('Mon, 20 Apr 2026 13:12:00 +0900')
    to an ISO-8601 string. Returns the raw value if parsing fails so the
    frontend gets *something* rather than a blank."""
    if not raw:
        return ""
    try:
        dt = parsedate_to_datetime(raw)
        if dt is None:
            return raw
        return dt.isoformat()
    except (TypeError, ValueError):
        return raw


# ── Naver Developers Search API (KR) ───────────────────────────────────────
# https://developers.naver.com/docs/serviceapi/search/news/news.md
# Free tier: 25,000 calls/day. Commercial use allowed.

_NAVER_API = "https://openapi.naver.com/v1/search/news.json"


def _naver_credentials() -> tuple[str, str] | None:
    """Read NAVER_CLIENT_ID / NAVER_CLIENT_SECRET from env.

    Returns None if either is missing — caller gets an empty list (no RSS
    fallback; this is intentional post-2026-04-19).
    """
    cid = os.environ.get("NAVER_CLIENT_ID", "").strip()
    secret = os.environ.get("NAVER_CLIENT_SECRET", "").strip()
    if not cid or not secret:
        return None
    return cid, secret


def _resolve_query(ticker: str) -> str:
    """Pick a Korean search query for a KRX ticker.

    Prefers the curated ``kr_stock_registry`` name (e.g. 삼성전자) over the
    bare 6-digit code — searching by code returns far fewer and noisier
    hits. Falls back to ``<code> 주가`` when the name is unknown.
    """
    try:
        from services import kr_stock_registry
        name = kr_stock_registry.get_name(ticker)
        if name:
            return f"{name} 주가"
    except Exception:
        pass
    code = ticker.split(".")[0].strip()
    if code:
        return f"{code} 주가"
    return ticker


def get_news_naver(ticker: str) -> List[dict]:
    """Fetch news for a KR ticker via Naver's official Search News API.

    Requires NAVER_CLIENT_ID + NAVER_CLIENT_SECRET env. Returns [] when the
    keys are unset or on any error — never raises.
    """
    cache_key = f"naver:{ticker.upper()}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    creds = _naver_credentials()
    if creds is None:
        logger.info("Naver Search API disabled — NAVER_CLIENT_ID/SECRET not set")
        return []
    client_id, client_secret = creds

    query = _resolve_query(ticker)
    params = {
        "query": query,
        "display": _MAX_ITEMS,   # max 100 per Naver docs
        "start": 1,
        "sort": "date",          # most-recent first
    }
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
        "User-Agent": _HEADERS["User-Agent"],
    }

    items: List[dict] = []
    try:
        resp = requests.get(
            _NAVER_API, headers=headers, params=params, timeout=_REQUEST_TIMEOUT
        )
        if resp.status_code != 200:
            # Don't dump raw response body — security scanner flags resp.text[:N]
            # as potential credential leakage even though Naver Search responses
            # contain no secrets. Status code + ticker is enough for triage.
            logger.warning("Naver Search API HTTP %s for %s",
                           resp.status_code, ticker)
            return []
        payload = resp.json() or {}
        for entry in payload.get("items", []) or []:
            title = _clean_text(entry.get("title", ""))
            if not title or len(title) < 5:
                continue
            summary = _clean_text(entry.get("description", ""))[:300]
            link = entry.get("link") or entry.get("originallink") or ""
            source_hint = entry.get("originallink") or ""
            # Extract domain for a readable `source` label when the original
            # publisher link is present; fallback to "Naver News".
            source_label = "Naver News"
            if source_hint:
                m = re.search(r"https?://(?:www\.)?([^/]+)", source_hint)
                if m:
                    source_label = m.group(1)

            items.append({
                "title":     title,
                "summary":   summary,
                "published": _rfc822_to_iso(entry.get("pubDate", "")),
                "link":      link,
                "source":    source_label,
            })
            if len(items) >= _MAX_ITEMS:
                break
    except Exception as ex:
        logger.warning("Naver Search API fetch failed %s: %s", ticker, ex)
        return []

    _cache_set(cache_key, items)
    return items
