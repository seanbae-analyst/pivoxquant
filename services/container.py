"""Service singletons — centralized instance management.

The ``engine`` singleton (QuantEngine) was removed on 2026-08-31 with the
scoring/screening surfaces it served. The only keeper route that still
referenced it, ``/api/portfolio/analytics``, has no frontend caller.
"""
from __future__ import annotations

from services.data.fetcher import DataFetcher
from services.ai.service import AIService
from services.data.realtime import RealtimeService

fetcher = DataFetcher()
ai = AIService()
realtime = RealtimeService()
