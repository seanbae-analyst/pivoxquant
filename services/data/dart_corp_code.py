"""DART corp_code resolver — ticker (6-digit KR stock code) → 8-digit corp_code.

DART Open API keys every endpoint by its proprietary ``corp_code`` (8-digit,
zero-padded). There is a one-shot download endpoint,
``https://opendart.fss.or.kr/api/corpCode.xml``, that returns a ZIP archive
containing ``CORPCODE.xml`` — the full master list of every KR company known
to DART. We fetch it once, parse it into ``{stock_code: corp_code}``, and
cache the result on disk for 7 days.

Design
------
- **Best-effort.** Every public function returns ``None`` / ``{}`` on any
  failure (no API key, network down, parse error). Never raises.
- **On-disk cache** at ``tests/fixtures/dart_corp_code.json`` with 7-day TTL.
  Inside tests (``PYTEST_CURRENT_TEST`` env set) we still honour the cache,
  so fixture files with stubbed mappings make the test hermetic.
- **In-memory cache** wraps the disk cache so hot-path lookups are free.
- **Thread-safe.** Downloads are guarded by a module lock so concurrent
  callers don't race to pull the (~1.5 MB) archive twice.

Environment
-----------
- ``DART_API_KEY`` — required for the download. Missing key → empty map.
- ``DART_CORP_CODE_CACHE`` — optional override for the cache file path.

Public API
----------
- ``corp_code_for(ticker)``        — resolve "005930" / "005930.KS" → "00126380".
- ``load_mapping(force=False)``    — return the full ``{stock_code: corp_code}``.
- ``cache_path()``                 — current on-disk cache location.
"""
from __future__ import annotations

import io
import json
import logging
import os
import threading
import time
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

try:
    import requests as _requests
except ImportError:  # pragma: no cover
    _requests = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

_CORPCODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
_DOWNLOAD_TIMEOUT = 30.0  # archive is ~1.5 MB; allow for slow connections
_CACHE_TTL_SECONDS = 7 * 24 * 3600  # 1 week

_DEFAULT_CACHE_PATH = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "dart_corp_code.json"
)

_lock = threading.Lock()
_mem_cache: dict[str, Any] | None = None
_mem_cache_ts: float = 0.0


# ── cache helpers ────────────────────────────────────────────────────────────

def cache_path() -> Path:
    override = os.environ.get("DART_CORP_CODE_CACHE")
    return Path(override) if override else _DEFAULT_CACHE_PATH


def _has_key() -> bool:
    return bool(os.environ.get("DART_API_KEY"))


def _load_disk_cache() -> dict[str, Any] | None:
    p = cache_path()
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("DART corp_code cache unreadable (%s): %s", p, exc)
        return None
    if not isinstance(raw, dict):
        return None
    mapping = raw.get("mapping") or {}
    fetched_at = float(raw.get("fetched_at") or 0.0)
    if not isinstance(mapping, dict):
        return None
    if time.time() - fetched_at > _CACHE_TTL_SECONDS:
        logger.debug("DART corp_code cache expired (age %.0fs)",
                     time.time() - fetched_at)
        return None
    return {"mapping": {str(k): str(v) for k, v in mapping.items()},
            "fetched_at": fetched_at}


def _save_disk_cache(mapping: dict[str, str]) -> None:
    p = cache_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "fetched_at": time.time(),
            "count":      len(mapping),
            "mapping":    mapping,
        }
        p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        logger.warning("DART corp_code cache write failed: %s", exc)


# ── XML parsing ──────────────────────────────────────────────────────────────

def _parse_corpcode_xml(xml_bytes: bytes) -> dict[str, str]:
    """Parse CORPCODE.xml → {stock_code(6-digit): corp_code(8-digit)}.

    Only listed companies (non-empty ``stock_code``) are retained. DART ships
    ~3,000 listed plus ~60,000 unlisted; we drop the unlisted rows since our
    product only cares about KOSPI/KOSDAQ tickers.
    """
    mapping: dict[str, str] = {}
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        logger.warning("DART CORPCODE.xml parse failed: %s", exc)
        return mapping

    for node in root.iter("list"):
        stock_code = (node.findtext("stock_code") or "").strip()
        corp_code = (node.findtext("corp_code") or "").strip()
        if not stock_code or not corp_code:
            continue
        if not stock_code.isdigit() or len(stock_code) != 6:
            continue
        if not corp_code.isdigit():
            continue
        mapping[stock_code] = corp_code.zfill(8)
    return mapping


def _download_and_parse() -> dict[str, str]:
    """Fetch the ZIP, unpack CORPCODE.xml, and parse it. Empty on any failure."""
    if _requests is None or not _has_key():
        return {}
    api_key = os.environ.get("DART_API_KEY") or ""
    try:
        r = _requests.get(
            _CORPCODE_URL,
            params={"crtfc_key": api_key},
            timeout=_DOWNLOAD_TIMEOUT,
        )
    except Exception as exc:
        logger.warning("DART CORPCODE download failed: %s", exc)
        return {}
    if r.status_code != 200 or not r.content:
        logger.warning("DART CORPCODE HTTP %s (%d bytes)",
                       r.status_code, len(r.content or b""))
        return {}

    # DART sometimes returns an error JSON payload with HTTP 200 when the
    # key is invalid. Detect by magic bytes — ZIP begins with "PK".
    if not r.content.startswith(b"PK"):
        try:
            err = r.json()
            logger.warning("DART CORPCODE non-ZIP response: %s", err)
        except Exception:
            logger.warning("DART CORPCODE non-ZIP response (%d bytes)",
                           len(r.content))
        return {}

    try:
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            names = zf.namelist()
            target = next((n for n in names if n.lower().endswith(".xml")), None)
            if not target:
                logger.warning("DART CORPCODE zip has no XML: %s", names)
                return {}
            xml_bytes = zf.read(target)
    except zipfile.BadZipFile as exc:
        logger.warning("DART CORPCODE bad zip: %s", exc)
        return {}

    return _parse_corpcode_xml(xml_bytes)


# ── public API ───────────────────────────────────────────────────────────────

def load_mapping(force: bool = False) -> dict[str, str]:
    """Return ``{stock_code(6-digit): corp_code(8-digit)}``.

    Resolution order:
    1. In-memory cache (fresh within TTL).
    2. On-disk cache at ``tests/fixtures/dart_corp_code.json`` (fresh within TTL).
    3. Download from DART, parse, persist.

    Never raises. Returns ``{}`` when every step fails.
    """
    global _mem_cache, _mem_cache_ts
    with _lock:
        now = time.time()
        if (not force and _mem_cache is not None
                and now - _mem_cache_ts < _CACHE_TTL_SECONDS):
            return dict(_mem_cache)

        if not force:
            disk = _load_disk_cache()
            if disk and disk["mapping"]:
                _mem_cache = dict(disk["mapping"])
                _mem_cache_ts = float(disk["fetched_at"])
                return dict(_mem_cache)

        mapping = _download_and_parse()
        if mapping:
            _save_disk_cache(mapping)
            _mem_cache = dict(mapping)
            _mem_cache_ts = now
            return dict(_mem_cache)

        # Download failed — fall back to (stale) disk cache if available so
        # we degrade gracefully when the daily DART quota is exhausted.
        stale_p = cache_path()
        if stale_p.exists():
            try:
                raw = json.loads(stale_p.read_text(encoding="utf-8"))
                stale_mapping = raw.get("mapping") or {}
                if isinstance(stale_mapping, dict) and stale_mapping:
                    logger.info("DART corp_code using stale cache (%d entries)",
                                len(stale_mapping))
                    stale_mapping = {str(k): str(v) for k, v in stale_mapping.items()}
                    _mem_cache = dict(stale_mapping)
                    _mem_cache_ts = now  # treat as fresh for this process
                    return dict(_mem_cache)
            except (OSError, json.JSONDecodeError):
                pass
        return {}


def corp_code_for(ticker: str) -> str | None:
    """Map a KR ticker to a DART corp_code.

    Accepts ``"005930"``, ``"005930.KS"``, or ``"005930.KQ"``. Returns
    ``None`` when the ticker is non-KR, the mapping is unavailable, or the
    stock is not listed in DART's master file.
    """
    if not ticker:
        return None
    t = ticker.strip().upper()
    if t.endswith(".KS") or t.endswith(".KQ"):
        stock_code = t.split(".", 1)[0]
    else:
        stock_code = t
    if not (stock_code.isdigit() and len(stock_code) == 6):
        return None

    mapping = load_mapping()
    return mapping.get(stock_code)


def seed_cache(mapping: dict[str, str]) -> None:
    """Test helper — pre-populate the on-disk + in-memory cache."""
    global _mem_cache, _mem_cache_ts
    clean = {str(k): str(v).zfill(8) for k, v in mapping.items()
             if str(k).isdigit() and len(str(k)) == 6
             and str(v).isdigit()}
    _save_disk_cache(clean)
    with _lock:
        _mem_cache = dict(clean)
        _mem_cache_ts = time.time()


def clear_cache() -> None:
    """Test helper — wipe in-memory + on-disk caches."""
    global _mem_cache, _mem_cache_ts
    with _lock:
        _mem_cache = None
        _mem_cache_ts = 0.0
    p = cache_path()
    if p.exists():
        try:
            p.unlink()
        except OSError:
            pass
