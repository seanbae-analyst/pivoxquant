#!/usr/bin/env python3
"""O-F: 종목명 매핑 누락 감지 (ticker_name_audit.py).

목적
----
``feedback_ticker_display`` 룰 enforcement — naked ticker 회귀 감지.

DB query 대상
-------------
``signal_cache`` 테이블: ``ticker`` primary key + ``data_json`` JSONB.
- ``data_json`` 내 ``name`` 필드가 NULL / 빈 문자열 / 원시 ticker 패턴인 레코드 탐지.

Watchlist 테이블도 점검: ticker 컬럼이 회사명 없이 표시될 가능성이 있는지
name_resolver 로 샘플링 검증한다 (DB 쿼리 아님 — 순수 로직 검증).

알림 임계치
-----------
누락 종목이 1개라도 있으면 Slack alert + Sentry capture.

출력
----
- stdout: 누락 종목 리스트 (최대 10개)
- SLACK_WEBHOOK_URL 있으면 Slack DM
- SENTRY_DSN 있으면 Sentry capture

비용 검증 (0원)
--------------
- DB query: Railway PostgreSQL — 포함 요금
- Slack webhook: 무료
- Sentry: 무료 플랜 포함

환경변수
--------
DATABASE_URL        — 필수 (Railway PostgreSQL)
SLACK_WEBHOOK_URL   — 없으면 stdout
SENTRY_DSN          — 없으면 Sentry skip

실행
----
python scripts/nightly/ticker_name_audit.py
cron: 30 6 * * *  (KST 06:30, morning-brief 이후)
"""
from __future__ import annotations

import json
import logging
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

_SSL_CTX = ssl.create_default_context()

# naked ticker 패턴: 숫자만 + .KS/.KQ 접미사 또는 순수 알파벳만인 경우
_RAW_TICKER_RE = re.compile(
    r"^\d{6}\.(KS|KQ)$",   # 한국 raw ticker
    re.IGNORECASE,
)


# ── Slack ─────────────────────────────────────────────────────────────────────

def _post_slack(text: str) -> None:
    webhook = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not webhook:
        print(f"[SLACK-FALLBACK]\n{text}")
        return
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        webhook,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX):
            pass
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.error("Slack webhook failed: %s", exc)


# ── Sentry ────────────────────────────────────────────────────────────────────

def _capture_sentry(msg: str, extras: dict | None = None) -> None:
    try:
        import sentry_sdk  # type: ignore
        dsn = os.environ.get("SENTRY_DSN", "")
        if not dsn:
            return
        with sentry_sdk.push_scope() as scope:
            if extras:
                for k, v in extras.items():
                    scope.set_extra(k, v)
            sentry_sdk.capture_message(msg, level="warning")
    except ImportError:
        logger.debug("sentry_sdk 미설치 — Sentry capture skip")
    except Exception as exc:
        logger.error("Sentry capture failed: %s", exc)


# ── DB 쿼리 ───────────────────────────────────────────────────────────────────

def _naked_ticker(name_val: str | None, ticker: str) -> bool:
    """True if name_val is NULL/empty/raw ticker pattern."""
    if not name_val:
        return True
    stripped = name_val.strip()
    if not stripped:
        return True
    # raw ticker 그대로인 경우 (e.g. "005930.KS")
    if stripped == ticker.strip():
        return True
    # naked 숫자.KS 패턴
    if _RAW_TICKER_RE.match(stripped):
        return True
    return False


def _run_psycopg2(db_url: str) -> list[dict]:
    import psycopg2  # type: ignore

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    # signal_cache 에서 name 필드 추출
    cur.execute("SELECT ticker, data_json FROM signal_cache")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    missing: list[dict] = []
    for ticker, data_json_raw in rows:
        name_val: str | None = None
        if data_json_raw:
            try:
                name_val = json.loads(data_json_raw).get("name")
            except (json.JSONDecodeError, AttributeError):
                name_val = None
        if _naked_ticker(name_val, ticker):
            missing.append({"ticker": ticker, "name": name_val, "source": "signal_cache"})
    return missing


def _run_sqlalchemy(db_url: str) -> list[dict]:
    from sqlalchemy import create_engine, text  # type: ignore
    from sqlalchemy.pool import NullPool  # transient engine, see note below

    # NullPool: this engine is transient (one scheduler tick, in the web process).
    # 2026-09-10: without it each create_engine kept an idle pooled connection to the
    # Supabase session pooler (15 clients max) until garbage collection. The
    # 5-minute signup-funnel job alone built six engines per tick; production held
    # 11 idle app connections and the next deploy's worker died with
    # EMAXCONNSESSION before it could boot.
    engine = create_engine(db_url, poolclass=NullPool, pool_pre_ping=True, connect_args={"connect_timeout": 10})
    missing: list[dict] = []
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT ticker, data_json FROM signal_cache")).fetchall()
        for ticker, data_json_raw in rows:
            name_val: str | None = None
            if data_json_raw:
                try:
                    name_val = json.loads(data_json_raw).get("name")
                except (json.JSONDecodeError, AttributeError):
                    name_val = None
            if _naked_ticker(name_val, ticker):
                missing.append({"ticker": ticker, "name": name_val, "source": "signal_cache"})
    return missing


def fetch_missing_names() -> list[dict]:
    """signal_cache 에서 name 누락 종목 조회. DB 미연결 시 빈 리스트."""
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        logger.warning("DATABASE_URL 미설정 — ticker_name_audit skip")
        return []

    try:
        return _run_psycopg2(db_url)
    except ImportError:
        logger.debug("psycopg2 없음 — SQLAlchemy fallback")
    except Exception as exc:
        logger.error("psycopg2 query failed: %s", exc)
        return []

    try:
        return _run_sqlalchemy(db_url)
    except Exception as exc:
        logger.error("SQLAlchemy query failed: %s", exc)
        return []


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main() -> int:
    logger.info("ticker_name_audit 시작")
    now_kst = (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M KST")

    missing = fetch_missing_names()
    total = len(missing)
    logger.info("누락 종목 총 %d건", total)

    if total == 0:
        logger.info("ticker_name_audit PASS — 누락 없음")
        print(f"[{now_kst}] ticker_name_audit PASS — 종목명 누락 0건")
        return 0

    # 상위 10개 출력
    preview = missing[:10]
    preview_lines = "\n".join(
        f"  - {item['ticker']} (name={item['name']!r})" for item in preview
    )
    summary = (
        f"[PivoxQuant] ticker_name_audit ALERT — naked ticker {total}건 감지\n"
        f"생성: {now_kst}\n"
        f"feedback_ticker_display 룰 위배 가능성. 즉시 name_resolver 점검 필요.\n\n"
        f"상위 {min(total, 10)}건:\n{preview_lines}"
    )
    if total > 10:
        summary += f"\n  ... 외 {total - 10}건"

    print(summary)
    logger.warning("ticker_name_audit FAIL — %d건 누락", total)

    _post_slack(summary)
    _capture_sentry(
        f"ticker_name_audit: naked ticker {total}건 감지",
        extras={"missing_count": total, "preview": preview},
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
