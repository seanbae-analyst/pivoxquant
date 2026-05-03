"""Ticker normalization — single source of truth for KR suffix routing.

Why this exists
---------------
Korean tickers travel through the system as ``005930.KS`` (KOSPI) or
``035760.KQ`` (KOSDAQ), but the user typically types the bare 6-digit
code. Many call sites do ad-hoc ``ticker.isdigit() and len == 6`` checks
followed by ``ticker += ".KS"`` — which is wrong for KOSDAQ tickers
(e.g., 035760 CJ ENM lives on KOSDAQ, the .KS suffix produces an
invalid lookup that silently misses).

This module centralises the rule so every input boundary (search,
watchlist add, position add, chart, quote) routes consistently.

Public API
----------
- ``normalize_ticker(raw)`` — main entry. Returns the canonical
  ``XXXXXX.KS`` / ``XXXXXX.KQ`` form for KR codes, or the upper-cased
  raw string for everything else (US tickers pass through). Never
  raises.

- ``is_korean_ticker(ticker)`` — small convenience: ``True`` when the
  normalized ticker ends in ``.KS`` or ``.KQ``.

Resolution rule for bare 6-digit codes
--------------------------------------
1. Try ``XXXXXX.KS`` against the curated registry (KR_STOCKS) — fast
   and covers the top ~250 KOSPI names.
2. Try ``XXXXXX.KQ`` against the curated registry — covers top KOSDAQ.
3. Try ``XXXXXX.KS`` then ``XXXXXX.KQ`` against the full KRX master
   (KR_STOCKS_FULL JSON, ~2,770 entries) — covers everything listed.
4. Fall back to ``.KS`` (legacy default) so existing call sites that
   never knew about KOSDAQ keep behaving the same. Logged at DEBUG so
   missing entries surface during integration testing.

Already-suffixed inputs (``005930.KS``, ``035760.kq``) are upper-cased
and returned as-is.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

_SIX_DIGIT = re.compile(r"^\d{6}$")
_KR_SUFFIXES = (".KS", ".KQ", ".KRX")


def is_korean_ticker(ticker: str) -> bool:
    """True when the (already-normalized) ticker is a KRX listing."""
    if not ticker:
        return False
    t = ticker.upper()
    return t.endswith(".KS") or t.endswith(".KQ")


def _registry_has(symbol: str) -> bool:
    """Membership probe against the static + full KRX registries.

    Imports are lazy so the normalizer can be imported by any module
    (including the registry itself) without a circular dependency.
    """
    try:
        from services.kr_stock_registry import KR_STOCKS, KR_STOCKS_FULL
    except Exception:
        return False
    return symbol in KR_STOCKS or symbol in KR_STOCKS_FULL


def normalize_ticker(raw: str) -> str:
    """Canonicalise a user-provided ticker string.

    Behaviour
    ---------
    - Empty / non-string input → empty string (caller decides how to
      reject; we never raise).
    - Already-suffixed KR tickers (``005930.KS``, ``035760.kq``,
      ``005930.KRX``) → upper-cased; ``.KRX`` is rewritten to ``.KS``
      for downstream compatibility.
    - Bare 6-digit code → registry-guided ``.KS`` or ``.KQ`` (see rule
      above). Falls back to ``.KS`` when neither registry has it.
    - Anything else → upper-cased and returned as-is. US tickers like
      ``aapl`` → ``AAPL``; class shares like ``BRK-B`` → ``BRK-B``.
    """
    if not isinstance(raw, str):
        return ""
    t = raw.strip().upper()
    if not t:
        return ""

    # Handle KRX-suffixed inputs first
    for suf in _KR_SUFFIXES:
        if t.endswith(suf):
            base = t[: -len(suf)]
            if not _SIX_DIGIT.match(base):
                # Suffix present but base isn't 6 digits — return original
                # upper-cased; downstream can decide whether to reject.
                return t
            # ``.KRX`` is a legacy alias; collapse to ``.KS`` for the rest
            # of the system. ``.KS``/``.KQ`` already canonical.
            return f"{base}.KS" if suf == ".KRX" else f"{base}{suf}"

    # Bare 6-digit code → registry-guided suffix
    if _SIX_DIGIT.match(t):
        ks_form = f"{t}.KS"
        kq_form = f"{t}.KQ"
        if _registry_has(ks_form):
            return ks_form
        if _registry_has(kq_form):
            return kq_form
        # Neither hit — log so missing-master cases surface during QA,
        # then fall back to .KS (the legacy default — keeps behaviour
        # identical for the long tail until we expand the master).
        logger.debug(
            "normalize_ticker: 6-digit code %s not in KR registries; "
            "defaulting to .KS",
            t,
        )
        return ks_form

    # Anything else — assume non-KR and return upper-cased
    return t


def strip_kr_suffix(ticker: str) -> Optional[str]:
    """Return the bare 6-digit code for a KR ticker, else None.

    Convenience for code paths (KIS API, alt_data, dart_corp_code) that
    need the raw KRX symbol. Mirrors the older ad-hoc
    ``replace('.KS','').replace('.KQ','')`` patterns scattered through
    the codebase.
    """
    if not isinstance(ticker, str):
        return None
    t = ticker.strip().upper()
    for suf in _KR_SUFFIXES:
        if t.endswith(suf):
            t = t[: -len(suf)]
            break
    return t if _SIX_DIGIT.match(t) else None
