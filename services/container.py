"""Service singletons — centralized instance management."""
from __future__ import annotations

from services.quant.engine import QuantEngine
from services.data.fetcher import DataFetcher
from services.ai.service import AIService
from services.data.realtime import RealtimeService

engine = QuantEngine()
fetcher = DataFetcher()
ai = AIService()
realtime = RealtimeService()
