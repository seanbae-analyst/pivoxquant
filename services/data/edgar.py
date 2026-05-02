"""SEC EDGAR API service — free, unlimited, commercial-safe fundamental data.

SEC EDGAR requires:
  - User-Agent header with app name + contact email
  - Max 10 requests/second (we self-throttle)
  - No API key needed; commercial use allowed
"""

import json
import logging
import time

try:
    import requests as _requests
except ImportError:
    _requests = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# SEC requires User-Agent with contact info
_USER_AGENT = "PivoxQuant/1.0 (sanghyun0115@naver.com)"
_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate",
}

_CACHE: dict[str, tuple] = {}  # {key: (data, expiry_ts)}
_TICKER_TO_CIK: dict[str, str] | None = None  # loaded once
_LAST_REQUEST_TS: float = 0.0  # for rate-limit self-throttle

TTL_FUNDAMENTALS = 86400   # 24h — SEC data changes quarterly
TTL_CIK_MAP = 604800       # 7 days
TTL_INSIDER = 3600          # 1h
_MIN_REQUEST_INTERVAL = 0.12  # ~8 req/s ceiling (SEC allows 10)


class EdgarService:

    @staticmethod
    def _get(url: str, retries: int = 2) -> dict | list | None:
        """Fetch JSON from SEC EDGAR with rate-limiting and retries.

        Returns parsed JSON on success, None on any failure.
        Logs warnings on non-200 responses for debugging.
        """
        global _LAST_REQUEST_TS

        for attempt in range(1, retries + 1):
            # Self-throttle to stay under SEC rate limit
            elapsed = time.time() - _LAST_REQUEST_TS
            if elapsed < _MIN_REQUEST_INTERVAL:
                time.sleep(_MIN_REQUEST_INTERVAL - elapsed)

            _LAST_REQUEST_TS = time.time()

            try:
                if _requests is not None:
                    resp = _requests.get(url, headers=_HEADERS, timeout=15)
                    if resp.status_code == 200:
                        return resp.json()
                    logger.warning(
                        "SEC EDGAR %s returned %d (attempt %d/%d)",
                        url, resp.status_code, attempt, retries,
                    )
                    if resp.status_code == 429:
                        time.sleep(2 * attempt)
                        continue
                    if resp.status_code == 403:
                        logger.warning(
                            "SEC EDGAR 403 — possible IP rate-limit or geo block"
                        )
                        time.sleep(1 * attempt)
                        continue
                    return None
                else:
                    # Fallback: urllib (no requests installed)
                    import urllib.request
                    import ssl
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    req = urllib.request.Request(url, headers=_HEADERS)
                    with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                        return json.loads(resp.read())
            except Exception as exc:
                logger.warning(
                    "SEC EDGAR request failed: %s (attempt %d/%d)",
                    exc, attempt, retries,
                )
                if attempt < retries:
                    time.sleep(1 * attempt)

        return None

    @staticmethod
    def _cached(key: str, ttl: int, fetch_fn):
        """Simple in-memory cache with TTL."""
        now = time.time()
        if key in _CACHE and _CACHE[key][1] > now:
            return _CACHE[key][0]
        data = fetch_fn()
        if data is not None:
            _CACHE[key] = (data, now + ttl)
        return data

    @classmethod
    def _load_cik_map(cls) -> dict:
        """Load ticker -> CIK mapping (all US public companies)."""
        global _TICKER_TO_CIK
        if _TICKER_TO_CIK:
            return _TICKER_TO_CIK

        def fetch():
            data = cls._get("https://www.sec.gov/files/company_tickers.json")
            if not data:
                return {}
            mapping = {}
            for entry in data.values():
                ticker = entry.get("ticker", "").upper()
                cik = str(entry.get("cik_str", "")).zfill(10)
                if ticker:
                    mapping[ticker] = cik
            return mapping

        result = cls._cached("cik_map", TTL_CIK_MAP, fetch)
        if result:
            _TICKER_TO_CIK = result
        return _TICKER_TO_CIK or {}

    @classmethod
    def get_cik(cls, ticker: str) -> str | None:
        """Get 10-digit CIK for a US ticker symbol."""
        cik_map = cls._load_cik_map()
        clean = ticker.upper().replace(".KS", "").replace(".KQ", "")
        return cik_map.get(clean)

    @classmethod
    def get_fundamentals(cls, ticker: str) -> dict | None:
        """Get key fundamental metrics from SEC EDGAR XBRL data.

        Returns dict with: source, revenue, prev_revenue, net_income, eps,
        total_debt, total_equity, profit_margin, revenue_growth, debt_to_equity.
        Returns None if CIK lookup or EDGAR fetch fails.
        """
        cache_key = f"edgar_fund:{ticker}"

        def fetch():
            cik = cls.get_cik(ticker)
            if not cik:
                return None

            url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
            data = cls._get(url)
            if not data:
                return None

            facts = data.get("facts", {})
            us_gaap = facts.get("us-gaap", {})

            def _annual_values(concept: str, unit: str = "USD") -> list:
                """Get all annual (10-K) values sorted by end date descending."""
                concept_data = us_gaap.get(concept, {})
                units = concept_data.get("units", {})
                values = units.get(unit, [])
                annual = [
                    v for v in values
                    if v.get("form") == "10-K" and v.get("val") is not None
                ]
                annual.sort(key=lambda x: x.get("end", ""), reverse=True)
                return annual

            def get_latest(concept: str, unit: str = "USD") -> float | None:
                vals = _annual_values(concept, unit)
                return vals[0]["val"] if vals else None

            def get_previous(concept: str, unit: str = "USD") -> float | None:
                vals = _annual_values(concept, unit)
                return vals[1]["val"] if len(vals) >= 2 else None

            # Companies use different XBRL concept tags for revenue
            revenue_concepts = [
                "Revenues",
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                "SalesRevenueNet",
                "RevenueFromContractWithCustomerIncludingAssessedTax",
            ]

            revenue = None
            prev_revenue = None
            for concept in revenue_concepts:
                revenue = get_latest(concept)
                if revenue is not None:
                    prev_revenue = get_previous(concept)
                    break

            net_income = get_latest("NetIncomeLoss") or get_latest("ProfitLoss")
            eps = (
                get_latest("EarningsPerShareDiluted")
                or get_latest("EarningsPerShareBasic", "USD/shares")
            )
            total_debt = (
                get_latest("LongTermDebt")
                or get_latest("LongTermDebtNoncurrent")
            )
            total_equity = (
                get_latest("StockholdersEquity")
                or get_latest("StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest")
            )

            # Derived metrics
            profit_margin = None
            if revenue and net_income and revenue != 0:
                profit_margin = round(net_income / revenue * 100, 2)

            revenue_growth = None
            if revenue and prev_revenue and prev_revenue != 0:
                revenue_growth = round(
                    (revenue - prev_revenue) / abs(prev_revenue) * 100, 2
                )

            debt_to_equity = None
            if total_debt is not None and total_equity and total_equity != 0:
                debt_to_equity = round(total_debt / total_equity * 100, 2)

            return {
                "source": "SEC EDGAR",
                "revenue": revenue,
                "prev_revenue": prev_revenue,
                "net_income": net_income,
                "eps": eps,
                "total_debt": total_debt,
                "total_equity": total_equity,
                "profit_margin": profit_margin,
                "revenue_growth": revenue_growth,
                "debt_to_equity": debt_to_equity,
            }

        return cls._cached(cache_key, TTL_FUNDAMENTALS, fetch)

    @classmethod
    def get_insider_trades(cls, ticker: str, limit: int = 20) -> list:
        """Get recent insider transactions from SEC Form 4 filings.

        Returns list of dicts with: date, form, description.
        """
        cache_key = f"edgar_insider:{ticker}"

        def fetch():
            cik = cls.get_cik(ticker)
            if not cik:
                return []

            url = f"https://data.sec.gov/submissions/CIK{cik}.json"
            data = cls._get(url)
            if not data:
                return []

            recent = data.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            descriptions = recent.get("primaryDocDescription", [])

            insider_filings = []
            for i, form in enumerate(forms):
                if form == "4" and i < len(dates):
                    insider_filings.append({
                        "date": dates[i] if i < len(dates) else None,
                        "form": form,
                        "description": descriptions[i] if i < len(descriptions) else None,
                    })
                    if len(insider_filings) >= limit:
                        break

            return insider_filings

        return cls._cached(cache_key, TTL_INSIDER, fetch) or []
