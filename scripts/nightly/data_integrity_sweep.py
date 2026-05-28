"""data_integrity_sweep — T10 일일 데이터 무결성 게이트.

매일 04:00 KST 실행. 3축 invariant 를 가벼운 in-process 체크로 검증하고
회귀 발견 시 Slack alert.

검증 항목 (모두 0원, 외부 API 호출 없음):
1. FX axis  — fx_service.get_rate() 가 USD/KRW 범위(1000~5000) 유지 + is_stale 가용.
2. Freshness — fx_service.STALE_SECONDS 정의 + services.cache_ttl import + price_overlay 모듈.
3. Cache    — risk_snapshot_cache 가 user_id keyed (cross-user isolation 1차 sanity).

agent (`fx-consistency-guard` / `data-freshness-monitor` / `cache-poisoning-sentinel`)
는 인터랙티브 Claude Code 세션에서 호출 — 본 cron 은 자동 sanity 만.

결과:
- 모두 PASS → /tmp/data_integrity_status.json 갱신, exit 0
- 1건이라도 FAIL → Slack alert + /tmp/data_integrity_status.json 갱신, exit 0
  (cron job 자체는 항상 exit 0 — alert 채널이 SoT)
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

STATUS_PATH = "/tmp/data_integrity_status.json"


def _slack_alert(text: str) -> None:
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook:
        logger.info("[data_integrity] SLACK_WEBHOOK_URL unset — alert skipped")
        return
    try:
        import requests
        requests.post(webhook, json={"text": text}, timeout=10)
    except Exception:
        logger.exception("[data_integrity] slack alert failed")


def _check_fx_axis() -> tuple[bool, str]:
    try:
        from services import fx_service
    except Exception as exc:
        return False, f"fx_service import failed: {exc!r}"
    if not callable(getattr(fx_service, "get_rate", None)):
        return False, "fx_service.get_rate removed (Pattern 7 P0)"
    if not callable(getattr(fx_service, "is_stale", None)):
        return False, "fx_service.is_stale removed (freshness signal lost)"
    rate = fx_service.get_rate()
    if not isinstance(rate, (int, float)):
        return False, f"fx rate non-numeric: {rate!r}"
    # set_rate 가 호출되기 전 boot 직후엔 default 1380 — 그래서 1000<rate<5000 로 OK.
    if not (1000 < rate < 5000):
        return False, f"fx rate out of USD/KRW band: {rate}"
    return True, f"fx_service OK (rate={rate}, stale={fx_service.is_stale()})"


def _check_freshness_axis() -> tuple[bool, str]:
    try:
        from services import fx_service
    except Exception as exc:
        return False, f"fx_service import failed: {exc!r}"
    if not hasattr(fx_service, "STALE_SECONDS"):
        return False, "fx_service.STALE_SECONDS removed"
    try:
        from services import cache_ttl  # noqa: F401
    except ImportError as exc:
        return False, f"services.cache_ttl import failed: {exc!r}"
    try:
        from services import price_overlay
    except ImportError as exc:
        return False, f"services.price_overlay import failed: {exc!r}"
    if not callable(getattr(price_overlay, "overlay_prices", None)):
        return False, "price_overlay.overlay_prices missing (3-tier fallback gone)"
    return True, f"freshness OK (STALE_SECONDS={fx_service.STALE_SECONDS})"


def _check_cache_axis() -> tuple[bool, str]:
    try:
        from services import cache_service
    except Exception as exc:
        return False, f"cache_service import failed: {exc!r}"
    # cross-user isolation 직접 검증.
    cache_service.risk_snapshot_cache_clear()
    try:
        sig = f"_sweep_{int(time.time())}"
        cache_service.risk_snapshot_cache_set(
            user_id=99001, signature=sig, payload={"sentinel": True}
        )
        leaked = cache_service.risk_snapshot_cache_get(user_id=99002, signature=sig)
        if leaked is not None:
            return False, f"P0 CACHE POISONING: user_B read user_A payload: {leaked!r}"
        own = cache_service.risk_snapshot_cache_get(user_id=99001, signature=sig)
        if own is None:
            return False, "owner read broken — cache write path damaged"
    finally:
        cache_service.risk_snapshot_cache_clear()
    return True, "cache_service OK (user_id isolation verified)"


def main() -> None:
    started = datetime.now(timezone.utc).isoformat()
    results: dict[str, Any] = {"started_at": started, "axes": {}}

    fx_ok, fx_msg = _check_fx_axis()
    fresh_ok, fresh_msg = _check_freshness_axis()
    cache_ok, cache_msg = _check_cache_axis()

    results["axes"]["fx"] = {"ok": fx_ok, "msg": fx_msg}
    results["axes"]["freshness"] = {"ok": fresh_ok, "msg": fresh_msg}
    results["axes"]["cache"] = {"ok": cache_ok, "msg": cache_msg}
    results["overall_ok"] = fx_ok and fresh_ok and cache_ok

    try:
        with open(STATUS_PATH, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2, sort_keys=True)
    except Exception:
        logger.exception("[data_integrity] status write failed")

    if not results["overall_ok"]:
        failed = [k for k, v in results["axes"].items() if not v["ok"]]
        msg = (
            f"🔴 PivoxQuant data-integrity sweep FAIL\n"
            f"axes: {failed}\n"
            + "\n".join(f"  - {k}: {v['msg']}" for k, v in results["axes"].items() if not v["ok"])
        )
        _slack_alert(msg)
        logger.warning("[data_integrity] %s", msg)
    else:
        logger.info("[data_integrity] OK (all 3 axes pass)")


if __name__ == "__main__":
    main()
