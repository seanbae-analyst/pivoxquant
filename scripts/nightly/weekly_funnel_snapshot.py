#!/usr/bin/env python3
"""주간 퍼널 스냅샷 — funnel_events 7일 집계 + K-factor + WAMR → Slack.

목적
----
``funnel_events`` (``POST /api/track`` 가 적재) 의 지난 7일치를 집계해 바이럴
루프 건강도를 주 1회 Slack 으로 보고한다. 외부 분석 SaaS 없이 자체 DB 만
사용 — 추가 비용 0원. Slack webhook 도 무료 tier.

집계 지표 (지난 7일)
--------------------
- acq          : landing_view 수 (acquisition / 퍼널 최상단)
- signup       : signup 수
- onboard      : onboarding_done 수
- activate     : artifact_opened 수 (engagement / activation proxy)
- shares       : share_clicked 수 (invites)
- ref_signup   : referral_signup 수 (referral conversions)
- WAMR         : Weekly Active ≈ 최근 7일 distinct user_id (이벤트 있는 유저)

K-factor 추정
-------------
  i (invite rate)     = shares / active
  c (conversion rate) = ref_signup / shares
  K                   = i * c
분모 0 가드. K 는 "추정치" — funnel_events 자체 추적 기반이라 GA 같은 정밀
세션 트래킹 아님 (라벨 명시). active = WAMR.

스케줄
------
APScheduler 주 1회 (월 09:30 KST). cron_jobs.py ``_job_specs`` 에 등록.

환경변수
--------
DATABASE_URL       — 미설정 시 SQLite (config 의 기본 dev DB) fallback.
SLACK_WEBHOOK_URL  — 없으면 stdout 출력 (fallback).

실행
----
python scripts/nightly/weekly_funnel_snapshot.py
"""
from __future__ import annotations

import json
import logging
import os
import ssl
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

_SSL_CTX = ssl.create_default_context()


def post_slack(text: str) -> bool:
    """Best-effort Slack webhook. Falls back to stdout when unset."""
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook:
        print(f"[SLACK-FALLBACK]\n{text}")
        return False
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        webhook, data=payload, headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.error("Slack webhook failed: %s", exc)
        return False


def _resolve_db_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        # Railway sometimes hands a `postgres://` URL — SQLAlchemy wants
        # `postgresql://`. Normalise so the engine builds.
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url
    # Local dev fallback — mirror config.py default SQLite path.
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return f"sqlite:///{os.path.join(root, 'pivoxquant.db')}"


def collect_metrics(db_url: str) -> dict:
    """Aggregate the last 7 days of funnel_events into the KPI shape.

    Single round-trip per metric via SQLAlchemy Core (psycopg2 or sqlite).
    Window uses the DB's own clock so it matches ``created_at`` semantics.
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool  # transient engine, see note below

    # NullPool: this engine is transient (one scheduler tick, in the web process).
    # 2026-09-10: without it each create_engine kept an idle pooled connection to the
    # Supabase session pooler (15 clients max) until garbage collection. The
    # 5-minute signup-funnel job alone built six engines per tick; production held
    # 11 idle app connections and the next deploy's worker died with
    # EMAXCONNSESSION before it could boot.
    engine = create_engine(
        db_url, poolclass=NullPool, pool_pre_ping=True,
        connect_args={"connect_timeout": 10} if db_url.startswith("postgresql") else {},
    )
    is_pg = db_url.startswith("postgresql")
    # Portable "7 days ago" predicate.
    if is_pg:
        since = "created_at >= NOW() - INTERVAL '7 days'"
    else:
        since = "created_at >= datetime('now', '-7 days')"

    counts: dict[str, int] = {}
    event_map = {
        "acq":        "landing_view",
        "signup":     "signup",
        "onboard":    "onboarding_done",
        "activate":   "artifact_opened",
        "shares":     "share_clicked",
        "ref_signup": "referral_signup",
    }
    with engine.connect() as conn:
        for key, ev in event_map.items():
            try:
                v = conn.execute(
                    text(f"SELECT COUNT(*) FROM funnel_events "
                         f"WHERE event = :ev AND {since}"),
                    {"ev": ev},
                ).scalar()
                counts[key] = int(v or 0)
            except Exception as exc:
                logger.error("count failed for %s: %s", ev, exc)
                counts[key] = 0
        # WAMR — distinct non-null user_id with any event in the window.
        try:
            wamr = conn.execute(
                text(f"SELECT COUNT(DISTINCT user_id) FROM funnel_events "
                     f"WHERE user_id IS NOT NULL AND {since}")
            ).scalar()
            counts["wamr"] = int(wamr or 0)
        except Exception as exc:
            logger.error("WAMR query failed: %s", exc)
            counts["wamr"] = 0

    # K-factor (estimate) — guard every divisor.
    active = counts["wamr"]
    shares = counts["shares"]
    ref_signup = counts["ref_signup"]
    i = (shares / active) if active > 0 else 0.0
    c = (ref_signup / shares) if shares > 0 else 0.0
    k = i * c
    counts["i"] = round(i, 3)
    counts["c"] = round(c, 3)
    counts["k"] = round(k, 3)
    return counts


def _format_report(m: dict) -> str:
    return (
        "📊 *PivoxQuant 주간 퍼널 스냅샷* (지난 7일)\n"
        f"• acquisition (landing_view): {m['acq']}\n"
        f"• signup: {m['signup']}\n"
        f"• onboarding_done: {m['onboard']}\n"
        f"• activation (artifact_opened): {m['activate']}\n"
        f"• shares (share_clicked): {m['shares']}\n"
        f"• referral_signup: {m['ref_signup']}\n"
        f"• WAMR (주간 활성 유저): {m['wamr']}\n"
        f"— K-factor 추정: K={m['k']} (i={m['i']} × c={m['c']})\n"
        "  i=shares/active, c=ref_signup/shares. funnel_events 자체 추적 기반 추정치."
    )


def main() -> int:
    db_url = _resolve_db_url()
    try:
        metrics = collect_metrics(db_url)
    except Exception as exc:
        logger.error("weekly funnel snapshot failed: %s", exc)
        post_slack(f"⚠️ PivoxQuant 주간 퍼널 스냅샷 실패: {exc}")
        return 1
    report = _format_report(metrics)
    post_slack(report)
    logger.info("weekly funnel snapshot: %s", json.dumps(metrics))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
