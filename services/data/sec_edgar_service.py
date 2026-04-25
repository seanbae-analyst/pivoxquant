"""SEC EDGAR Alt-Data Service — Smart Money 13F + Insider Cluster Buy tracker.

Free, no-key, commercial-safe. Complements the existing ``edgar_service.py``
(which focuses on company fundamentals). This module targets **alternative
data**: institutional (13F) holdings and insider (Form 4) trades, with
cluster-buy detection as a tradable signal.

SEC EDGAR rules (strictly enforced):
  - ``User-Agent`` header MUST identify the app + contact email
  - Max 10 req/s (we self-throttle at ~0.11s per request)
  - Non-200 responses => logger.warning + empty list (never raise)

Cache: in-memory TTL 4h (13F filings are quarterly; Form 4 is ~T+2 real-time).

Usage::

    from services.data.sec_edgar_service import SECEdgarService, SMART_MONEY_CIKS

    svc = SECEdgarService()
    berkshire_13f = svc.get_13f_holdings(SMART_MONEY_CIKS["berkshire"])
    aapl_clusters = svc.detect_cluster_buys("AAPL", days=30, min_insiders=3)
"""

from __future__ import annotations

import logging
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from xml.etree import ElementTree as ET

try:
    import requests as _requests
except ImportError:  # pragma: no cover — requests is in requirements.txt
    _requests = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# ── SEC required headers ──────────────────────────────────────────────────────
# Per SEC fair-access rules, the User-Agent must contain contact info.
# Format: "<App> <contact-email>"
_USER_AGENT = "PivoxQuant seanbae1521@gmail.com"
_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate",
}
_XML_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "application/xml,text/xml,*/*",
    "Accept-Encoding": "gzip, deflate",
}

# ── Rate-limit self-throttle (SEC allows 10 req/s) ────────────────────────────
_MIN_REQUEST_INTERVAL = 0.11  # ~9 req/s ceiling, leaves headroom
_rate_lock = threading.Lock()
_last_request_ts: float = 0.0

# ── Cache (TTL 4h) ────────────────────────────────────────────────────────────
_CACHE_TTL_SECONDS = 4 * 3600  # 4 hours
_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = threading.Lock()

# ── Smart Money CIK registry (zero-padded to 10 digits as SEC expects) ────────
SMART_MONEY_CIKS: dict[str, str] = {
    "berkshire":   "0001067983",  # Berkshire Hathaway (Warren Buffett)
    "renaissance": "0001037389",  # Renaissance Technologies (Jim Simons)
    "citadel":     "0001423053",  # Citadel Advisors (Ken Griffin)
    "bridgewater": "0001350694",  # Bridgewater Associates (Ray Dalio)
    "ark":         "0001697748",  # ARK Investment Management (Cathie Wood)
}

# Base URLs
_EDGAR_DATA = "https://data.sec.gov"
_EDGAR_WWW = "https://www.sec.gov"


# ══════════════════════════════════════════════════════════════════════════════
# Public service
# ══════════════════════════════════════════════════════════════════════════════
class SECEdgarService:
    """Client for SEC EDGAR alt-data: 13F holdings + Form 4 insider trades."""

    # ── HTTP plumbing ─────────────────────────────────────────────────────────
    @staticmethod
    def _throttle() -> None:
        """Sleep just enough to stay under SEC's 10 req/s cap (thread-safe)."""
        global _last_request_ts
        with _rate_lock:
            elapsed = time.time() - _last_request_ts
            if elapsed < _MIN_REQUEST_INTERVAL:
                time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
            _last_request_ts = time.time()

    @classmethod
    def _http_get(cls, url: str, *, as_xml: bool = False) -> Any | None:
        """GET with SEC-compliant headers, rate-limit, and safe error handling."""
        if _requests is None:
            logger.warning("requests not installed; SEC EDGAR disabled")
            return None
        cls._throttle()
        try:
            resp = _requests.get(
                url,
                headers=_XML_HEADERS if as_xml else _HEADERS,
                timeout=15,
            )
        except Exception as exc:  # pragma: no cover — network layer
            logger.warning("SEC EDGAR request failed (%s): %s", url, exc)
            return None
        if resp.status_code != 200:
            logger.warning(
                "SEC EDGAR non-200 (%s): %s", resp.status_code, url
            )
            return None
        if as_xml:
            return resp.text
        try:
            return resp.json()
        except ValueError:
            logger.warning("SEC EDGAR JSON parse failed: %s", url)
            return None

    # ── Cache helpers ─────────────────────────────────────────────────────────
    @staticmethod
    def _cache_get(key: str) -> Any | None:
        with _cache_lock:
            hit = _cache.get(key)
            if not hit:
                return None
            expiry, value = hit
            if time.time() > expiry:
                _cache.pop(key, None)
                return None
            return value

    @staticmethod
    def _cache_set(key: str, value: Any, ttl: int = _CACHE_TTL_SECONDS) -> None:
        with _cache_lock:
            _cache[key] = (time.time() + ttl, value)

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── Ticker ↔ CIK lookup ───────────────────────────────────────────────────
    @classmethod
    def _ticker_to_cik(cls, ticker: str) -> str | None:
        """Resolve a ticker symbol to its 10-digit padded CIK (cached 4h)."""
        t = (ticker or "").upper().strip()
        if not t:
            return None
        cache_key = "cik_map"
        mapping = cls._cache_get(cache_key)
        if mapping is None:
            data = cls._http_get(f"{_EDGAR_WWW}/files/company_tickers.json")
            if not isinstance(data, dict):
                return None
            # Payload: {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "..."}, ...}
            mapping = {
                str(row.get("ticker", "")).upper(): str(row.get("cik_str", "")).zfill(10)
                for row in data.values()
                if isinstance(row, dict) and row.get("ticker")
            }
            cls._cache_set(cache_key, mapping)
        return mapping.get(t)

    # ══════════════════════════════════════════════════════════════════════════
    # 1) 13F institutional holdings
    # ══════════════════════════════════════════════════════════════════════════
    @classmethod
    def get_13f_holdings(cls, cik: str) -> list[dict]:
        """Return the latest 13F-HR filing's holdings for a given institution.

        Args:
            cik: 10-digit zero-padded CIK (e.g. "0001067983" for Berkshire)

        Returns:
            list of {"ticker", "company", "shares", "value_usd", "cusip",
            "filing_date", "period"} (empty list on any failure)
        """
        cik10 = (cik or "").zfill(10)
        if not cik10.isdigit():
            return []
        cache_key = f"13f:{cik10}"
        cached = cls._cache_get(cache_key)
        if cached is not None:
            return cached

        # Step 1 — fetch filing index for this CIK
        submissions = cls._http_get(f"{_EDGAR_DATA}/submissions/CIK{cik10}.json")
        if not isinstance(submissions, dict):
            return []
        recent = (submissions.get("filings") or {}).get("recent") or {}
        forms = recent.get("form") or []
        accessions = recent.get("accessionNumber") or []
        filing_dates = recent.get("filingDate") or []
        primary_docs = recent.get("primaryDocument") or []

        # Find the most recent 13F-HR
        idx = next(
            (i for i, f in enumerate(forms) if f in ("13F-HR", "13F-HR/A")),
            None,
        )
        if idx is None:
            cls._cache_set(cache_key, [])
            return []

        accession_raw = accessions[idx]
        accession_nodash = accession_raw.replace("-", "")
        filing_date = filing_dates[idx] if idx < len(filing_dates) else ""

        # Step 2 — locate the information-table XML in the filing folder
        filing_index = cls._http_get(
            f"{_EDGAR_DATA}/submissions/CIK{cik10}/{accession_nodash}/index.json"
        )
        info_table_path: str | None = None
        if isinstance(filing_index, dict):
            for item in ((filing_index.get("directory") or {}).get("item") or []):
                name = str(item.get("name", ""))
                if name.lower().endswith(".xml") and "info" in name.lower():
                    info_table_path = name
                    break

        # Fallback — scan /Archives listing
        base_archive = (
            f"{_EDGAR_WWW}/Archives/edgar/data/"
            f"{int(cik10)}/{accession_nodash}"
        )
        xml_url: str | None = None
        if info_table_path:
            xml_url = f"{base_archive}/{info_table_path}"

        if not xml_url and idx < len(primary_docs):
            # primaryDocument is usually the cover form; info table sits alongside
            xml_url = f"{base_archive}/{primary_docs[idx]}"

        if not xml_url:
            cls._cache_set(cache_key, [])
            return []

        xml_text = cls._http_get(xml_url, as_xml=True)
        if not isinstance(xml_text, str) or not xml_text.strip():
            cls._cache_set(cache_key, [])
            return []

        holdings = _parse_13f_information_table(xml_text)
        for h in holdings:
            h["filing_date"] = filing_date
            h["period"] = recent.get("reportDate", [""] * (idx + 1))[idx] if idx < len(
                recent.get("reportDate") or []
            ) else ""

        cls._cache_set(cache_key, holdings)
        return holdings

    # ══════════════════════════════════════════════════════════════════════════
    # 2) Institutional filers holding a given ticker
    # ══════════════════════════════════════════════════════════════════════════
    @classmethod
    def get_institutional_filers_by_ticker(
        cls, ticker: str, limit: int = 50
    ) -> list[dict]:
        """Scan the Smart Money registry for who currently holds the ticker.

        This is an O(N) scan where N = len(SMART_MONEY_CIKS). We deliberately
        limit to the curated whitelist — broader scans would require EDGAR
        full-text search (separate API tier).
        """
        t = (ticker or "").upper().strip()
        if not t:
            return []
        cache_key = f"smart_money:{t}:{limit}"
        cached = cls._cache_get(cache_key)
        if cached is not None:
            return cached

        results: list[dict] = []
        for name, cik in SMART_MONEY_CIKS.items():
            holdings = cls.get_13f_holdings(cik)
            match = next(
                (h for h in holdings if (h.get("ticker") or "").upper() == t),
                None,
            )
            if match:
                results.append({
                    "filer": name,
                    "cik": cik,
                    "shares": match.get("shares"),
                    "value_usd": match.get("value_usd"),
                    "filing_date": match.get("filing_date"),
                    "period": match.get("period"),
                })
            if len(results) >= limit:
                break
        cls._cache_set(cache_key, results)
        return results

    # ══════════════════════════════════════════════════════════════════════════
    # 3) Form 4 insider trades
    # ══════════════════════════════════════════════════════════════════════════
    @classmethod
    def get_form4_insider_trades(
        cls, ticker: str, days: int = 90
    ) -> list[dict]:
        """Return Form 4 insider trades for a ticker within the last N days.

        Returns:
            list of {"insider", "relationship", "transaction_date",
            "transaction_code", "shares", "price", "value_usd", "acquired",
            "accession"} sorted newest first (empty list on failure).
        """
        t = (ticker or "").upper().strip()
        if not t:
            return []
        cache_key = f"form4:{t}:{days}"
        cached = cls._cache_get(cache_key)
        if cached is not None:
            return cached

        cik10 = cls._ticker_to_cik(t)
        if not cik10:
            return []

        submissions = cls._http_get(f"{_EDGAR_DATA}/submissions/CIK{cik10}.json")
        if not isinstance(submissions, dict):
            return []
        recent = (submissions.get("filings") or {}).get("recent") or {}
        forms = recent.get("form") or []
        accessions = recent.get("accessionNumber") or []
        filing_dates = recent.get("filingDate") or []
        primary_docs = recent.get("primaryDocument") or []

        cutoff = datetime.now(timezone.utc).date() - timedelta(days=max(1, days))
        trades: list[dict] = []

        for i, form in enumerate(forms):
            if form not in ("4", "4/A"):
                continue
            fd = filing_dates[i] if i < len(filing_dates) else ""
            try:
                fd_date = datetime.strptime(fd, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                continue
            if fd_date < cutoff:
                # filings are ordered newest-first; safe to break
                break

            accession_nodash = accessions[i].replace("-", "")
            primary = primary_docs[i] if i < len(primary_docs) else ""
            if not primary.lower().endswith(".xml"):
                # Find the XML in the filing dir
                fidx = cls._http_get(
                    f"{_EDGAR_DATA}/submissions/CIK{cik10}/{accession_nodash}/index.json"
                )
                if isinstance(fidx, dict):
                    for item in ((fidx.get("directory") or {}).get("item") or []):
                        nm = str(item.get("name", ""))
                        if nm.lower().endswith(".xml"):
                            primary = nm
                            break
            if not primary.lower().endswith(".xml"):
                continue

            xml_url = (
                f"{_EDGAR_WWW}/Archives/edgar/data/"
                f"{int(cik10)}/{accession_nodash}/{primary}"
            )
            xml_text = cls._http_get(xml_url, as_xml=True)
            if not isinstance(xml_text, str) or not xml_text.strip():
                continue

            parsed = _parse_form4(xml_text)
            for row in parsed:
                row["accession"] = accessions[i]
                row["filing_date"] = fd
                trades.append(row)

        # Sort newest first by transaction_date (fall back to filing_date)
        trades.sort(
            key=lambda r: (r.get("transaction_date") or r.get("filing_date") or ""),
            reverse=True,
        )
        cls._cache_set(cache_key, trades)
        return trades

    # ══════════════════════════════════════════════════════════════════════════
    # 4) Cluster-buy detector
    # ══════════════════════════════════════════════════════════════════════════
    @classmethod
    def detect_cluster_buys(
        cls, ticker: str, days: int = 30, min_insiders: int = 3
    ) -> dict:
        """Flag a cluster buy when ``min_insiders`` distinct insiders bought
        within the past ``days``.

        Returns:
            {"ticker", "triggered": bool, "insider_count", "unique_insiders",
            "trades": [...], "window_days", "threshold"}
        """
        t = (ticker or "").upper().strip()
        trades = cls.get_form4_insider_trades(t, days=days) if t else []
        # "P" = Open-market purchase (bullish). "S" = sale. "A" = award (skip).
        buys = [
            tr for tr in trades
            if (tr.get("transaction_code") or "").upper() == "P"
            and tr.get("acquired") is True
        ]
        unique_insiders = sorted({(b.get("insider") or "").strip() for b in buys if b.get("insider")})
        return {
            "ticker": t,
            "triggered": len(unique_insiders) >= max(1, int(min_insiders)),
            "insider_count": len(unique_insiders),
            "unique_insiders": unique_insiders,
            "trades": buys,
            "window_days": days,
            "threshold": min_insiders,
        }


# ══════════════════════════════════════════════════════════════════════════════
# XML parsers (module-level for testability)
# ══════════════════════════════════════════════════════════════════════════════
def _strip_ns(tag: str) -> str:
    """Drop the XML namespace prefix from an element tag."""
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _parse_13f_information_table(xml_text: str) -> list[dict]:
    """Parse a 13F-HR ``informationTable`` XML into holding dicts.

    Handles namespaced and non-namespaced variants. Returns [] on any failure.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    holdings: list[dict] = []
    # Walk all descendants; match by local tag name (namespace-agnostic).
    for elem in root.iter():
        if _strip_ns(elem.tag) != "infoTable":
            continue
        row: dict[str, Any] = {}
        for child in elem:
            local = _strip_ns(child.tag)
            if local == "nameOfIssuer":
                row["company"] = (child.text or "").strip()
            elif local == "cusip":
                row["cusip"] = (child.text or "").strip()
            elif local == "value":
                # Pre-2023: thousands. Post-2023 (Q2 2023+): raw dollars.
                try:
                    row["value_usd"] = int((child.text or "0").replace(",", ""))
                except ValueError:
                    row["value_usd"] = 0
            elif local == "shrsOrPrnAmt":
                for sub in child:
                    if _strip_ns(sub.tag) == "sshPrnamt":
                        try:
                            row["shares"] = int((sub.text or "0").replace(",", ""))
                        except ValueError:
                            row["shares"] = 0
        # ticker lookup is not in the filing — leave blank; caller may enrich
        row.setdefault("ticker", "")
        row.setdefault("shares", 0)
        row.setdefault("value_usd", 0)
        holdings.append(row)
    return holdings


_CODE_RE = re.compile(r"[A-Z]")


def _parse_form4(xml_text: str) -> list[dict]:
    """Parse a Form 4 ``ownershipDocument`` XML into trade rows."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    # Reporting owner identity
    insider_name = ""
    relationship_bits: list[str] = []
    for elem in root.iter():
        local = _strip_ns(elem.tag)
        if local == "rptOwnerName" and not insider_name:
            insider_name = (elem.text or "").strip()
        elif local in ("isDirector", "isOfficer", "isTenPercentOwner", "isOther"):
            if (elem.text or "").strip() in ("1", "true", "True"):
                relationship_bits.append(local.replace("is", ""))
        elif local == "officerTitle" and (elem.text or "").strip():
            relationship_bits.append((elem.text or "").strip())

    relationship = ", ".join(sorted(set(relationship_bits))) or ""

    trades: list[dict] = []
    # Non-derivative transactions (plain stock)
    for txn in root.iter():
        if _strip_ns(txn.tag) != "nonDerivativeTransaction":
            continue
        row: dict[str, Any] = {
            "insider": insider_name,
            "relationship": relationship,
            "transaction_date": "",
            "transaction_code": "",
            "shares": 0,
            "price": 0.0,
            "value_usd": 0.0,
            "acquired": None,
        }
        for sub in txn.iter():
            local = _strip_ns(sub.tag)
            if local == "transactionDate":
                val = _get_value(sub)
                if val:
                    row["transaction_date"] = val
            elif local == "transactionCode":
                code = (sub.text or "").strip().upper()
                if _CODE_RE.match(code):
                    row["transaction_code"] = code[:1]
            elif local == "transactionShares":
                try:
                    row["shares"] = float(_get_value(sub) or 0)
                except ValueError:
                    row["shares"] = 0
            elif local == "transactionPricePerShare":
                try:
                    row["price"] = float(_get_value(sub) or 0)
                except ValueError:
                    row["price"] = 0.0
            elif local == "transactionAcquiredDisposedCode":
                ad = (_get_value(sub) or "").strip().upper()
                row["acquired"] = (ad == "A")
        row["value_usd"] = round(float(row["shares"]) * float(row["price"]), 2)
        trades.append(row)
    return trades


def _get_value(elem: ET.Element) -> str:
    """Form 4 wraps fields in ``<value>...</value>`` children — unwrap it."""
    for child in elem:
        if _strip_ns(child.tag) == "value":
            return (child.text or "").strip()
    return (elem.text or "").strip()


# ══════════════════════════════════════════════════════════════════════════════
# Test-only utilities (not part of public API)
# ══════════════════════════════════════════════════════════════════════════════
def _clear_cache_for_tests() -> None:
    """Reset module-level cache — test harness only."""
    with _cache_lock:
        _cache.clear()
