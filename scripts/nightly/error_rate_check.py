#!/usr/bin/env python3
"""Sentry error-rate 5-minute poll (O-A).

목적
----
Production 환경의 에러 spike 를 5분 단위로 감지. 첫 1주는 **baseline 수집 모드**
(alert 발송 X) — 한 주치 데이터로 median + 3σ threshold 산출 후 alert 모드 전환.

스케줄
------
crontab ``*/5 * * * *`` — 5분 간격.

audit 조건 (#5)
---------------
- 기본 mode 는 ``baseline`` — Slack alert 미발송, state 누적만.
- 1주 이상 데이터가 쌓이고 운영자가 ``PIVOX_ERROR_RATE_MODE=alert`` env 를 설정하면
  alert 모드 전환. threshold = median + 3*MAD (robust σ).
- 어떤 경우에도 자동 페이지/롤백 X.

환경변수
--------
SENTRY_AUTH_TOKEN     — 필수 (없으면 graceful skip + exit 0)
SENTRY_ORG_SLUG       — 필수
SENTRY_PROJECT_SLUG   — 필수
PIVOX_ERROR_RATE_MODE — baseline (default) | alert
PIVOX_ERROR_RATE_BASELINE_DAYS — int (default 7)
SLACK_WEBHOOK_URL     — 선택 (alert mode 에서만 사용)

state
-----
``state/error_rate_history.json`` — { "samples": [{"ts": ISO, "events": N}, ...],
"mode": "baseline|alert", "last_alert_at": ISO|null }. Cap at 8064 (1주 = 5분 * 12 * 24 * 7).

비용
----
Sentry free tier (5k events/mo 포함). Stats API quota 미소모. 0원.
"""
from __future__ import annotations

import json
import logging
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_DIR = _ROOT / "state"
STATE_PATH = STATE_DIR / "error_rate_history.json"

# Sample retention — 1주 of 5-min samples = 2016. We keep ~4 weeks to allow
# rolling-window threshold refinement after we go alert-mode.
MAX_SAMPLES = 2016 * 4
# Minimum samples required before alert mode can fire (= 1 week by default).
DEFAULT_BASELINE_DAYS = 7
SAMPLES_PER_DAY = 12 * 24  # 5-min samples
# Dedup — never alert more than once per ALERT_DEDUP_MIN.
ALERT_DEDUP_MIN = 30

_SSL_CTX = ssl.create_default_context()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def load_state() -> dict:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not STATE_PATH.exists():
        return {"samples": [], "mode": "baseline", "last_alert_at": None}
    try:
        data = json.loads(STATE_PATH.read_text("utf-8"))
        data.setdefault("samples", [])
        data.setdefault("mode", "baseline")
        data.setdefault("last_alert_at", None)
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("state load failed (%s) — starting fresh", exc)
        return {"samples": [], "mode": "baseline", "last_alert_at": None}


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def fetch_sentry_events_5min(
    auth_token: str, org_slug: str, project_slug: str
) -> int:
    """Fetch 5-min window event count. -1 on error."""
    end = _now_utc()
    start = end - timedelta(minutes=5)
    # Sentry stats endpoint: /api/0/projects/{org}/{project}/stats/
    # stat=received, resolution=10s (lowest), since/until = epoch seconds.
    qs = urllib.parse.urlencode({
        "stat": "received",
        "resolution": "10s",
        "since": int(start.timestamp()),
        "until": int(end.timestamp()),
    })
    url = (
        f"https://sentry.io/api/0/projects/{org_slug}/{project_slug}/stats/?{qs}"
    )
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        logger.error("Sentry stats HTTP %s: %s", exc.code, exc.reason)
        return -1
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.error("Sentry stats network error: %s", exc)
        return -1

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Sentry stats JSON parse error: %s", exc)
        return -1

    # Response shape: [[timestamp, count], ...]. Sum counts.
    if not isinstance(data, list):
        return 0
    total = 0
    for entry in data:
        if isinstance(entry, list) and len(entry) >= 2:
            try:
                total += int(entry[1])
            except (TypeError, ValueError):
                continue
    return total


def compute_threshold(samples: list[dict]) -> Optional[float]:
    """Robust threshold = median + 3 * MAD. None if insufficient data."""
    if len(samples) < SAMPLES_PER_DAY:  # at least 1 day
        return None
    counts = sorted(s.get("events", 0) for s in samples)
    n = len(counts)
    median = counts[n // 2] if n % 2 else (counts[n // 2 - 1] + counts[n // 2]) / 2
    deviations = sorted(abs(c - median) for c in counts)
    mad = (
        deviations[n // 2]
        if n % 2
        else (deviations[n // 2 - 1] + deviations[n // 2]) / 2
    )
    # MAD-to-σ conversion factor 1.4826 (standard).
    return median + 3 * 1.4826 * mad


def baseline_ready(samples: list[dict], baseline_days: int) -> bool:
    required = baseline_days * SAMPLES_PER_DAY
    return len(samples) >= required


def post_slack(text: str) -> bool:
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook:
        logger.warning("SLACK_WEBHOOK_URL 미설정 — stdout fallback")
        print(f"[SLACK-FALLBACK] {text}")
        return False
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        webhook,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.error("Slack webhook failed: %s", exc)
        return False


def _dedup_ok(state: dict) -> bool:
    last = state.get("last_alert_at")
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return True
    return _now_utc() - last_dt >= timedelta(minutes=ALERT_DEDUP_MIN)


def main() -> int:
    auth_token = os.environ.get("SENTRY_AUTH_TOKEN", "")
    org_slug = os.environ.get("SENTRY_ORG_SLUG", "")
    project_slug = os.environ.get("SENTRY_PROJECT_SLUG", "")

    if not (auth_token and org_slug and project_slug):
        logger.warning(
            "SENTRY_AUTH_TOKEN / SENTRY_ORG_SLUG / SENTRY_PROJECT_SLUG 중 일부 "
            "미설정 — graceful skip (exit 0)"
        )
        return 0

    count = fetch_sentry_events_5min(auth_token, org_slug, project_slug)
    if count < 0:
        logger.error("Sentry fetch failed — sample 누락, exit 1")
        return 1

    state = load_state()
    # mode env can override stored mode (latest wins).
    requested_mode = os.environ.get("PIVOX_ERROR_RATE_MODE", state.get("mode", "baseline"))
    if requested_mode not in ("baseline", "alert"):
        requested_mode = "baseline"
    state["mode"] = requested_mode

    baseline_days = int(os.environ.get("PIVOX_ERROR_RATE_BASELINE_DAYS", DEFAULT_BASELINE_DAYS))

    state["samples"].append({"ts": _now_utc().isoformat(), "events": count})
    # Trim to MAX_SAMPLES (drop oldest).
    if len(state["samples"]) > MAX_SAMPLES:
        state["samples"] = state["samples"][-MAX_SAMPLES:]

    logger.info(
        "sample stored events=%d mode=%s samples=%d",
        count, state["mode"], len(state["samples"]),
    )

    rc = 0
    if state["mode"] == "alert":
        if not baseline_ready(state["samples"], baseline_days):
            logger.info(
                "alert mode 요청됐으나 baseline 부족 (samples=%d, 필요=%d) — alert skip",
                len(state["samples"]), baseline_days * SAMPLES_PER_DAY,
            )
        else:
            threshold = compute_threshold(state["samples"])
            if threshold is not None and count > threshold:
                if _dedup_ok(state):
                    msg = (
                        f"[ALERT] PivoxQuant error spike: events={count} > "
                        f"threshold={threshold:.1f} (5min window, baseline={baseline_days}d). "
                        f"Sentry 확인: https://sentry.io/organizations/{org_slug}/projects/{project_slug}/"
                    )
                    post_slack(msg)
                    state["last_alert_at"] = _now_utc().isoformat()
                    rc = 2
                else:
                    logger.info("threshold 초과지만 dedup 윈도우 내 — alert skip")
    else:
        # baseline mode — never alert.
        if baseline_ready(state["samples"], baseline_days):
            logger.info(
                "baseline %dd 수집 완료 (%d samples). "
                "alert 모드 전환은 PIVOX_ERROR_RATE_MODE=alert env 설정 필요.",
                baseline_days, len(state["samples"]),
            )

    save_state(state)
    return rc


if __name__ == "__main__":
    sys.exit(main())
