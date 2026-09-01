"""Service singletons — centralized instance management.

The ``engine`` singleton (QuantEngine) was removed on 2026-08-31 with the
scoring/screening surfaces it served. The only keeper route that still
referenced it, ``/api/portfolio/analytics``, has no frontend caller.

The ``ai`` singleton (AIService) was removed on 2026-09-01 together with
``services/ai/``: after the support chatbot was cut, every one of its nine
public methods had zero call sites, so the container was constructing a
Claude client the product never used.
"""
from __future__ import annotations

from services.data.fetcher import DataFetcher
from services.data.realtime import RealtimeService

fetcher = DataFetcher()
realtime = RealtimeService()
