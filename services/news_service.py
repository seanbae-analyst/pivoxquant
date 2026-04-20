"""
PivoxQuant — News Service
KR ticker (.KS / .KQ) → Naver Developers Search API (official, commercial OK)
US ticker              → Yahoo Finance RSS / Google News RSS (public feeds)

Response schema (identical to FMP path used by frontend):
    {
        "title":     str,
        "summary":   str,   # may be ""
        "published": str,   # ISO-8601 or raw RFC822 (readable)
        "link":      str,
        "source":    str,
    }

Never raises — returns [] on any failure. Times out in ~8s.

Legal note:
  The legacy implementation scraped Naver's mobile JSON endpoint
  (`m.stock.naver.com/api/news/stock/...`). That endpoint is undocumented
  and violates Naver's robots / scraping ToS. The official Search News
  API (this file) is explicitly commercial-use-allowed under the Naver
  Developers Agreement §2 once NAVER_CLIENT_ID / NAVER_CLIENT_SECRET are
  issued via https://developers.naver.com/apps/#/register.
"""

from __future__ import annotations

import logging
import os
import re
import time
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Dict, List

import feedparser
import requests

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
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

    Returns None if either is missing — caller falls through to RSS feeds.
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
    keys are unset (caller should fall through to Google News RSS) or on
    any error — never raises.
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
            logger.warning("Naver Search API HTTP %s for %s (%s)",
                           resp.status_code, ticker, resp.text[:120])
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


# ── Yahoo Finance RSS (US fallback) ──────────────────────────────────────────

_YAHOO_RSS_URL = (
    "https://feeds.finance.yahoo.com/rss/2.0/headline"
    "?s={symbol}&region=US&lang=en-US"
)


def get_news_yahoo_rss(ticker: str) -> List[dict]:
    """Fetch Yahoo Finance RSS feed for a US ticker.

    Returns [] on any failure.
    """
    cache_key = f"yahoo:{ticker.upper()}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # Yahoo uses bare symbol (no suffix)
    symbol = ticker.split(".")[0].strip().upper()
    if not symbol:
        return []

    url = _YAHOO_RSS_URL.format(symbol=symbol)
    items: List[dict] = []

    # Yahoo throttles requests with ko-KR Accept-Language; use en-only headers.
    yahoo_headers = {
        "User-Agent": _HEADERS["User-Agent"],
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
    }

    try:
        resp = requests.get(url, headers=yahoo_headers, timeout=_REQUEST_TIMEOUT)
        if resp.status_code != 200:
            logger.warning(f"Yahoo RSS HTTP {resp.status_code} for {ticker}")
            return []
        parsed = feedparser.parse(resp.text)
        for entry in (parsed.entries or [])[:_MAX_ITEMS]:
            title = _clean_text(entry.get("title", ""))
            if not title or len(title) < 5:
                continue
            summary = _clean_text(entry.get("summary", ""))[:300]
            items.append({
                "title":     title,
                "summary":   summary,
                "published": entry.get("published", "") or entry.get("updated", ""),
                "link":      entry.get("link", ""),
                "source":    "Yahoo Finance",
            })
    except Exception as ex:
        logger.warning(f"Yahoo RSS fetch failed {ticker}: {ex}")
        return []

    _cache_set(cache_key, items)
    return items


# ── Google News RSS (universal fallback) ─────────────────────────────────────

_GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search"
    "?q={query}&hl=en-US&gl=US&ceid=US:en"
)


def get_news_google(ticker: str) -> List[dict]:
    """Fetch Google News RSS for a ticker (US fallback when Yahoo throttles).

    Uses `{symbol} stock` as the search query. Returns [] on failure.
    """
    cache_key = f"google:{ticker.upper()}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    symbol = ticker.split(".")[0].strip().upper()
    if not symbol:
        return []

    query = f"{symbol}+stock"
    url = _GOOGLE_NEWS_RSS.format(query=query)
    items: List[dict] = []

    headers = {
        "User-Agent": _HEADERS["User-Agent"],
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=_REQUEST_TIMEOUT)
        if resp.status_code != 200:
            logger.warning(f"Google News HTTP {resp.status_code} for {ticker}")
            return []
        parsed = feedparser.parse(resp.text)
        for entry in (parsed.entries or [])[:_MAX_ITEMS]:
            title = _clean_text(entry.get("title", ""))
            if not title or len(title) < 5:
                continue
            # Google News titles end with " - <Source>" — split it out.
            source_name = "Google News"
            if " - " in title:
                title_core, _, src = title.rpartition(" - ")
                if src and len(src) < 40:
                    title = title_core
                    source_name = src
            summary = _clean_text(entry.get("summary", ""))[:300]
            items.append({
                "title":     title,
                "summary":   summary,
                "published": entry.get("published", "") or entry.get("updated", ""),
                "link":      entry.get("link", ""),
                "source":    source_name,
            })
    except Exception as ex:
        logger.warning(f"Google News fetch failed {ticker}: {ex}")
        return []

    _cache_set(cache_key, items)
    return items
