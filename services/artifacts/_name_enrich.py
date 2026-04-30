"""Name enrichment for v3 PDF data — fills `name` field from ticker
when missing, so templates can render company name primary + ticker
secondary instead of ticker-as-hero.

Why
---
PDFs/emails historically showed ticker (`AAPL`, `005930.KS`) as the
visual hero. Per CEO 2026-05-01: 'ticker번호만 크게 오고 종목 이름을
써라' — name should be primary, ticker secondary. Templates were
patched to render `{{ x.name | default(x.ticker) }}` first, but most
service `_to_v3_shape()` builders only populated `ticker`. This helper
walks the v3 dict recursively and backfills `name` via
`services.name_resolver.resolve_stock_name` so every ticker-bearing
item displays its company name.

Usage
-----
    from services.artifacts._name_enrich import enrich_v3_names
    ctx["v3"] = enrich_v3_names(self._to_v3_shape(data))

The helper is idempotent — if `name` is already set on an item, it's
preserved. Only items with `ticker` but no `name` are enriched.

Failure mode
------------
If `name_resolver` returns None (unknown ticker), the item is left
untouched and templates fall back to displaying the ticker via the
existing `default(ticker, true)` filter chain.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _resolve(ticker: str) -> str | None:
    """Lazy import to avoid circular dependencies + tolerate name_resolver
    being absent in test contexts."""
    if not ticker or not isinstance(ticker, str):
        return None
    try:
        from services.serializers import _resolve_display_name
        return _resolve_display_name(ticker)
    except Exception:
        return None


def enrich_v3_names(data: Any, *, depth: int = 0, max_depth: int = 12) -> Any:
    """Recursively walk a v3 dict / list structure and backfill `name`
    on every dict that has a non-empty `ticker` but no `name`.

    Returns the same structure (mutated in place for dicts, but lists
    are not replaced — items inside lists may be mutated). Safe to call
    multiple times.

    `max_depth` guards against pathological cyclic structures; v3
    shapes never nest deeper than ~6 in practice.
    """
    if depth > max_depth:
        return data

    if isinstance(data, dict):
        # Skip enrichment if already has name.
        ticker = data.get("ticker")
        name = data.get("name")
        if ticker and (not name or not str(name).strip()):
            resolved = _resolve(str(ticker))
            if resolved:
                data["name"] = resolved
        # Recurse into all values.
        for k, v in list(data.items()):
            if isinstance(v, (dict, list)):
                enrich_v3_names(v, depth=depth + 1, max_depth=max_depth)
        return data

    if isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                enrich_v3_names(item, depth=depth + 1, max_depth=max_depth)
        return data

    return data


__all__ = ["enrich_v3_names"]
