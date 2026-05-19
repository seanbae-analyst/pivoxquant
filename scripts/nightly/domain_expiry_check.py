#!/usr/bin/env python3
"""Domain WHOIS expiry monitor for pivoxquant.com (E-2, Wave I P0).

목적
----
가비아 도메인 자동 갱신이 결제 카드 만료 / 잔액 부족 등으로 실패할 경우
**`pivoxquant.com` 이 grace period 종료와 함께 회수**된다 (KR 도메인 30일
유예 후 redemption 30일 + 즉시 회수). 회수되면 OAuth callback URL / Vercel
custom domain / 이메일 발송 도메인 4곳이 동시에 죽는다.

이 스크립트는 매월 1일 WHOIS 를 조회해 만료일이 D-60 / D-30 안에 들어왔는데
갱신 흔적이 없으면 Slack 으로 경고한다.

WHOIS 안정성
-----------
- `python-whois` 는 raw WHOIS 서버 응답을 파싱 — 가비아 KR 서버 응답 포맷
  변경 시 ``expiration_date`` 가 ``None`` 일 수 있다. None 일 경우 graceful
  skip (rc=0) + Slack alert ``[INFO]`` 로 별도 surface.
- WHOIS rate limit (가비아 ~10 req/min/IP) — 한 도메인 / 월 1회 = 한도 내.

dedup
-----
``state/domain_expiry_alerted.json`` — D-60 / D-30 각 임계 1회만 알림.
만료일이 갱신되면 (expiration_date 이 미래로 이동) state 자동 reset.

비용
----
WHOIS public protocol 만 사용 (TCP 43). 외부 API 결제 0. **0원**.

graceful skip
-------------
- `python-whois` 미설치 → ImportError → exit 0
- WHOIS 조회 실패 (network / parser error) → Slack [INFO] + exit 0
- expiration_date 가 None → Slack [INFO] + exit 0

스케줄
------
APScheduler `CronTrigger(day=1, hour=9, minute=30, timezone='Asia/Seoul')` —
매월 1일 09:30 KST.

왜 매월 1회만:
- 도메인 만료일은 분 단위로 바뀌지 않음 — 매일 조회는 WHOIS rate limit 낭비.
- 60일 / 30일 threshold 모두 매월 1회 검출에 충분 (worst case = D-30 직후
  검출이 4주 지연되어도 갱신할 시간 충분).
"""
from __future__ import annotations

import json
import logging
import os
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_DIR = _ROOT / "state"
STATE_PATH = STATE_DIR / "domain_expiry_alerted.json"

# Domain to monitor. Configurable via env for test environments / fork forks.
DEFAULT_DOMAIN = os.environ.get("PIVOX_WHOIS_DOMAIN", "pivoxquant.com")

# Alert thresholds — descending. D-60 first (renewal lead time), then D-30
# (가비아 자동갱신 1차 시도 실패 시 수동 대응 윈도우).
THRESHOLD_DAYS = (60, 30)

_SSL_CTX = ssl.create_default_context()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def load_state() -> dict:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text("utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("state load failed (%s) — starting fresh", exc)
        return {}


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def lookup_expiration(domain: str, whois_mod) -> datetime | None:
    """Query WHOIS and extract the registration expiration_date.

    ``python-whois`` returns ``expiration_date`` as either a single
    ``datetime`` or a ``list[datetime]`` (some TLDs return multiple values
    for redundant fields). We always pick the **earliest** future date —
    that's the conservative reading for an expiry alert.

    Returns ``None`` on any parse failure (rather than raising) so the
    caller can surface the situation as an [INFO] Slack message instead
    of letting the scheduler thread crash.
    """
    try:
        w = whois_mod.whois(domain)
    except Exception as exc:
        # python-whois throws WhoisError for unknown TLDs / blocked servers.
        # Catch broadly — the only sane response is graceful skip + log.
        logger.warning("whois lookup failed for %s: %s", domain, exc)
        return None

    exp = getattr(w, "expiration_date", None)
    if exp is None:
        return None

    # Normalize to a single datetime.
    candidates = exp if isinstance(exp, list) else [exp]
    valid: list[datetime] = []
    for c in candidates:
        if not isinstance(c, datetime):
            continue
        # Force UTC awareness — WHOIS responses are inconsistent.
        if c.tzinfo is None:
            c = c.replace(tzinfo=timezone.utc)
        valid.append(c)

    if not valid:
        return None
    # Earliest is the conservative pick (closest to expiry).
    return min(valid)


def days_until(expiry: datetime) -> int:
    """Whole-day delta from now (UTC) to expiry. Negative = already expired."""
    delta = expiry - _now_utc()
    return int(delta.total_seconds() // 86400)


def pick_threshold(days_left: int) -> int | None:
    """Return the tightest crossed threshold (e.g. days=29 → 30, days=45 → 60).

    Returns None when no threshold is crossed (days > max threshold). Negative
    days returns the tightest (30) — overdue is always alert-worthy.
    """
    for t in sorted(THRESHOLD_DAYS):
        if days_left <= t:
            return t
    return None


def should_alert(state: dict, domain: str, expiry: datetime, threshold: int) -> bool:
    """Alert iff (a) this (domain, threshold) hasn't been alerted for the
    *current* expiry date.  When the domain is renewed (expiry shifts to a
    later date), state's recorded expiry differs → state effectively resets.
    """
    entry = state.get(domain, {}) or {}
    recorded_expiry = entry.get("expiry_iso")
    alerted_thresholds = set(entry.get("alerted_thresholds", []))
    current_expiry_iso = expiry.isoformat()
    # If expiry has changed (renewal happened), reset alert history.
    if recorded_expiry != current_expiry_iso:
        return True
    return threshold not in alerted_thresholds


def record_alert(state: dict, domain: str, expiry: datetime, threshold: int) -> None:
    entry = state.setdefault(domain, {})
    current_expiry_iso = expiry.isoformat()
    if entry.get("expiry_iso") != current_expiry_iso:
        # Renewal detected → fresh alert log for this expiry.
        entry["expiry_iso"] = current_expiry_iso
        entry["alerted_thresholds"] = []
    alerted = set(entry.get("alerted_thresholds", []))
    alerted.add(threshold)
    entry["alerted_thresholds"] = sorted(alerted)
    entry["last_alert_at"] = _now_utc().isoformat()


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


def format_alert(domain: str, expiry: datetime, days_left: int, threshold: int) -> str:
    if days_left <= 0:
        urgency = f"EXPIRED {-days_left}d ago"
        emoji = "[CRIT]"
    else:
        urgency = f"D-{days_left} (threshold D-{threshold})"
        emoji = "[WARN]"
    return (
        f"{emoji} PivoxQuant domain expiry {urgency}: {domain}\n"
        f"만료일: {expiry.strftime('%Y-%m-%d')} (UTC)\n"
        "조치: 가비아 콘솔 → My가비아 → 도메인 → 자동갱신 카드 확인. "
        "Vercel custom domain + OAuth redirect URI + 이메일 SPF/DKIM 모두 "
        "해당 도메인 의존."
    )


def main() -> int:
    try:
        import whois  # type: ignore[import-not-found]
    except ImportError:
        logger.warning("python-whois 미설치 — domain_expiry_check skip")
        return 0

    domain = DEFAULT_DOMAIN
    expiry = lookup_expiration(domain, whois)
    if expiry is None:
        msg = (
            f"[INFO] WHOIS parse failed for {domain} — expiration_date None. "
            "가비아 WHOIS 응답 포맷이 바뀌었거나 일시적 네트워크 오류 가능. "
            "스크립트는 graceful skip."
        )
        logger.warning(msg)
        post_slack(msg)
        return 0

    days_left = days_until(expiry)
    logger.info(
        "domain=%s expiry=%s days_left=%d",
        domain, expiry.isoformat(), days_left,
    )

    threshold = pick_threshold(days_left)
    if threshold is None:
        logger.info("days_left=%d > max threshold=%d — no alert", days_left, max(THRESHOLD_DAYS))
        return 0

    state = load_state()
    if not should_alert(state, domain, expiry, threshold):
        logger.info(
            "threshold D-%d for %s already alerted (expiry=%s) — dedup",
            threshold, domain, expiry.isoformat(),
        )
        return 0

    msg = format_alert(domain, expiry, days_left, threshold)
    post_slack(msg)
    record_alert(state, domain, expiry, threshold)
    save_state(state)

    return 2 if days_left <= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
