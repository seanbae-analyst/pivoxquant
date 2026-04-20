"""
PivoxQuant — News Service
KR ticker (.KS / .KQ) → Naver Finance mobile JSON API
US ticker              → Yahoo Finance RSS (fallback when FMP empty)

Response schema (identical to FMP path used by frontend):
    {
        "title":     str,
        "summary":   str,   # may be ""
        "published": str,   # raw timestamp string (site format)
        "link":      str,
        "source":    str,
    }

Never raises — returns [] on any failure. Times out in ~8s.
"""

from __future__ import annotations

import logging
import re
import time
from html import unescape
from typing import List, Dict

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


# ── Naver Finance (KR) — mobile JSON API ────────────────────────────────────

# Powers the official Naver mobile stock news widget. Returns a list of
# "news group" dicts, each with an `items` array of articles.
_NAVER_API = "https://m.stock.naver.com/api/news/stock/{code}?pageSize={size}&page=1"


def _naver_code(ticker: str) -> str:
    """Extract 6-digit Naver code from '005930.KS' → '005930'."""
    return ticker.split(".")[0].strip()


def _format_naver_datetime(raw: str) -> str:
    """Convert '202604201312' → '2026-04-20 13:12' for readable display."""
    s = (raw or "").strip()
    if len(s) == 12 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]} {s[8:10]}:{s[10:12]}"
    return s


def get_news_naver(ticker: str) -> List[dict]:
    """Fetch news for a KR ticker via Naver's mobile JSON API.

    Returns [] on any failure — never raises.
    """
    cache_key = f"naver:{ticker.upper()}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    code = _naver_code(ticker)
    if not code.isdigit() or len(code) != 6:
        return []

    url = _NAVER_API.format(code=code, size=_MAX_ITEMS)
    items: List[dict] = []

    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_REQUEST_TIMEOUT)
        if resp.status_code != 200:
            logger.warning(f"Naver news HTTP {resp.status_code} for {ticker}")
            return []
        payload = resp.json()
        if not isinstance(payload, list):
            return []

        seen_ids = set()
        for group in payload:
            if not isinstance(group, dict):
                continue
            for entry in group.get("items", []) or []:
                nid = entry.get("id") or entry.get("articleId") or ""
                if nid in seen_ids:
                    continue
                seen_ids.add(nid)

                title = _clean_text(
                    entry.get("titleFull") or entry.get("title") or ""
                )
                if not title or len(title) < 5:
                    continue

                body = _clean_text(entry.get("body") or "")[:300]
                link = entry.get("mobileNewsUrl") or ""
                # Fallback link if API omits mobileNewsUrl
                if not link and entry.get("officeId") and entry.get("articleId"):
                    link = (
                        f"https://n.news.naver.com/mnews/article/"
                        f"{entry['officeId']}/{entry['articleId']}"
                    )

                items.append({
                    "title":     title,
                    "summary":   body,
                    "published": _format_naver_datetime(entry.get("datetime", "")),
                    "link":      link,
                    "source":    entry.get("officeName") or "Naver Finance",
                })
                if len(items) >= _MAX_ITEMS:
                    break
            if len(items) >= _MAX_ITEMS:
                break
    except Exception as ex:
        logger.warning(f"Naver news fetch failed {ticker}: {ex}")
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
