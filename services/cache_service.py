"""Signal cache and discovery cache management."""
import json
import logging
from datetime import datetime

from extensions import db
from models import SignalCache

logger = logging.getLogger(__name__)

# ── In-memory caches ──
discover_cache: dict = {}  # user_id -> {ts, data}
DISCOVER_TTL = 600         # 10 minutes

ca_cache: dict = {}        # cross-asset cache


def save_signal(ticker: str, data: dict):
    """Upsert signal cache for a ticker."""
    c = db.session.get(SignalCache, ticker)
    if c:
        c.data_json = json.dumps(data, ensure_ascii=False)
        c.updated_at = datetime.utcnow()
    else:
        db.session.add(SignalCache(
            ticker=ticker,
            data_json=json.dumps(data, ensure_ascii=False),
        ))
    db.session.commit()


def cache_ticker(ticker: str, capital: float, engine):
    """Analyze and cache a single ticker."""
    try:
        r = engine.analyze(ticker, capital)
        if r:
            save_signal(ticker, r)
    except Exception as e:
        logger.error(f"Cache update failed {ticker}: {e}")
