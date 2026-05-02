"""Alternative data services (pyKRX, etc.)."""

# Re-exports for relocated modules (2026-05-02 refactor):
# data_fetcher.py / fmp_service.py / edgar_service.py / realtime_service.py
# moved from project root into services/data/.
from services.data.fetcher import DataFetcher  # noqa: F401
from services.data.edgar import EdgarService  # noqa: F401
from services.data.realtime import RealtimeService  # noqa: F401
# fmp module exposes module-level functions (no public class); import as namespace.
from services.data import fmp  # noqa: F401
