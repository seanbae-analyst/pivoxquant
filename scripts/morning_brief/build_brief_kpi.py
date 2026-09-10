#!/usr/bin/env python3
"""Morning Brief KPI 확장 모듈 (S6 + O-M + O-I 통합).

목적
----
기존 ``scripts/morning_brief/build_brief.py`` 가 GitHub Actions 워크플로우
메트릭만 다루는 것을 보완해, **비즈니스 KPI 섹션 4개** 를 추가한다.

추가 섹션
---------
(a) DAU/WAU   — DB query: users 테이블 + artifacts.created_at 활동 기준
(b) 신규 가입 24h — DB query: users.created_at
(c) Stripe 매출 강화 (O-I) — 전일/MoM 매출, 환불, MRR 추정, top 5 customer
(d) Sentry 이슈 수 — Sentry API: projects/{org}/{project}/issues/

출력
----
- Slack DM (CEO) via Slack Incoming Webhook (SLACK_WEBHOOK_URL)
- 파일: morning_briefs/YYYY-MM-DD.md

비용 검증 (0원)
--------------
- DB query: Railway PostgreSQL — 포함 요금
- Stripe API: 무료 (추가 비용 없음, BalanceTransaction + Subscription)
- Sentry API: 무료 플랜 포함
- Slack webhook: 무료

추측 라벨
---------
- DAU 계산: 고유 user_id 기준 artifacts 활동 / artifacts 없는 순수 방문은
  미추적 (sessions 테이블 없음) — "추측: 방문자 아닌 활성 액션 기준"
- Stripe API: STRIPE_SECRET_KEY 미설정 시 "N/A (미연결)" 표기
- Sentry API: SENTRY_AUTH_TOKEN + SENTRY_ORG + SENTRY_PROJECT 모두 필요
- MRR: active subscription * unit_amount / 100 — 할인/trial 미반영 추정치

환경변수
--------
DATABASE_URL           — 필수 (Railway PostgreSQL)
SLACK_WEBHOOK_URL      — 없으면 stdout 출력
STRIPE_SECRET_KEY      — 없으면 Stripe 섹션 skip
SENTRY_AUTH_TOKEN      — 없으면 Sentry 섹션 skip
SENTRY_ORG             — Sentry 조직 슬러그
SENTRY_PROJECT         — Sentry 프로젝트 슬러그

실행
----
python scripts/morning_brief/build_brief_kpi.py [--output PATH]
"""
from __future__ import annotations

import argparse
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

_SSL_CTX = ssl.create_default_context()
_ROOT = Path(__file__).resolve().parent.parent.parent
BRIEFS_DIR = _ROOT / "morning_briefs"


# ── 날짜 헬퍼 ──────────────────────────────────────────────────────────────────

def _now_kst() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=9)


def _today_kst() -> str:
    return _now_kst().strftime("%Y-%m-%d")


def _utc_ts(hours_ago: int = 0) -> str:
    """ISO-8601 UTC timestamp (hours_ago 이전)."""
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _today_start_unix() -> int:
    """오늘 UTC 00:00:00 의 Unix timestamp."""
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(today.timestamp())


def _yesterday_start_unix() -> int:
    """어제 UTC 00:00:00 의 Unix timestamp."""
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return int(yesterday.timestamp())


def _month_start_unix() -> int:
    """이번 달 1일 UTC 00:00:00 의 Unix timestamp."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return int(month_start.timestamp())


def _prev_month_range_unix() -> tuple[int, int]:
    """전월 시작/종료 UTC timestamp (시작 inclusive, 종료 exclusive)."""
    now = datetime.now(timezone.utc)
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # 전월 말일 = 이번 달 1일 - 1초
    prev_month_end = this_month_start - timedelta(seconds=1)
    prev_month_start = prev_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return int(prev_month_start.timestamp()), int(this_month_start.timestamp())


# ── Slack ─────────────────────────────────────────────────────────────────────

def post_slack(text: str) -> bool:
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook:
        logger.warning("SLACK_WEBHOOK_URL 미설정 — stdout 출력")
        print(f"[SLACK-FALLBACK]\n{text}")
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


# ── (a)(b) DB KPI — DAU/WAU + 신규 가입 ──────────────────────────────────────

def fetch_db_kpi() -> dict:
    """Railway PostgreSQL 에서 DAU/WAU/신규 가입 쿼리.

    추측 라벨: DAU = artifacts 테이블 고유 user_id 기반 (방문자 != 활동자).
    sessions/audit_log 테이블 없음 — carry-over 검증 필요.
    """
    result: dict = {
        "dau": "N/A (DB 미연결)",
        "wau": "N/A (DB 미연결)",
        "new_users_24h": "N/A (DB 미연결)",
        "total_users": "N/A (DB 미연결)",
        "caveat": None,
    }

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        logger.warning("DATABASE_URL 미설정 — DB KPI skip")
        return result

    # psycopg2 또는 sqlalchemy 중 하나라도 있으면 사용
    try:
        import psycopg2  # type: ignore
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        # DAU: 오늘 artifacts 생성한 고유 user_id (추측 — 방문자 기준 아님)
        cur.execute(
            """
            SELECT COUNT(DISTINCT user_id)
            FROM artifacts
            WHERE created_at >= NOW() - INTERVAL '24 hours'
            """
        )
        row = cur.fetchone()
        result["dau"] = row[0] if row else 0

        # WAU: 7일 artifacts 고유 user_id
        cur.execute(
            """
            SELECT COUNT(DISTINCT user_id)
            FROM artifacts
            WHERE created_at >= NOW() - INTERVAL '7 days'
            """
        )
        row = cur.fetchone()
        result["wau"] = row[0] if row else 0

        # 신규 가입 24h
        cur.execute(
            """
            SELECT COUNT(*)
            FROM users
            WHERE created_at >= NOW() - INTERVAL '24 hours'
            """
        )
        row = cur.fetchone()
        result["new_users_24h"] = row[0] if row else 0

        # 전체 유저 수
        cur.execute("SELECT COUNT(*) FROM users")
        row = cur.fetchone()
        result["total_users"] = row[0] if row else 0

        cur.close()
        conn.close()
        result["caveat"] = "추측: DAU/WAU = artifacts 활동 기준 (방문자 아님)"
        return result

    except ImportError:
        logger.warning("psycopg2 없음 — SQLAlchemy fallback 시도")

    try:
        from sqlalchemy import create_engine, text  # type: ignore
        from sqlalchemy.pool import NullPool  # transient engine, see note below

        # NullPool: this engine is transient (one scheduler tick, in the web process).
        # 2026-09-10: without it each create_engine kept an idle pooled connection to the
        # Supabase session pooler (15 clients max) until garbage collection. The
        # 5-minute signup-funnel job alone built six engines per tick; production held
        # 11 idle app connections and the next deploy's worker died with
        # EMAXCONNSESSION before it could boot.
        engine = create_engine(db_url, poolclass=NullPool, pool_pre_ping=True, connect_args={"connect_timeout": 10})
        with engine.connect() as conn:
            dau = conn.execute(
                text("SELECT COUNT(DISTINCT user_id) FROM artifacts WHERE created_at >= NOW() - INTERVAL '24 hours'")
            ).scalar() or 0
            wau = conn.execute(
                text("SELECT COUNT(DISTINCT user_id) FROM artifacts WHERE created_at >= NOW() - INTERVAL '7 days'")
            ).scalar() or 0
            new_24h = conn.execute(
                text("SELECT COUNT(*) FROM users WHERE created_at >= NOW() - INTERVAL '24 hours'")
            ).scalar() or 0
            total = conn.execute(text("SELECT COUNT(*) FROM users")).scalar() or 0

        result.update({"dau": dau, "wau": wau, "new_users_24h": new_24h, "total_users": total})
        result["caveat"] = "추측: DAU/WAU = artifacts 활동 기준 (방문자 아님)"
        return result

    except Exception as exc:
        logger.error("DB KPI query failed: %s", exc)
        result["error"] = str(exc)
        return result


# ── (c) Stripe KPI (O-I 강화) ─────────────────────────────────────────────────

def _stripe_get(api_key: str, path: str) -> dict | None:
    """Stripe REST GET helper. None on error."""
    url = f"https://api.stripe.com/v1/{path}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        logger.error("Stripe GET %s HTTP %s", path, exc.code)
        return None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.error("Stripe GET %s error: %s", path, exc)
        return None


def _stripe_balance_transactions(api_key: str, ts_gte: int, ts_lt: int | None = None) -> list:
    """BalanceTransaction.list — 특정 기간 실수령 합산용."""
    qs = f"created[gte]={ts_gte}&limit=100&type=charge"
    if ts_lt:
        qs += f"&created[lt]={ts_lt}"
    data = _stripe_get(api_key, f"balance_transactions?{qs}")
    return (data or {}).get("data", [])


def _stripe_refunds(api_key: str, ts_gte: int) -> list:
    """Refund.list — 전일 환불 건수/금액."""
    data = _stripe_get(api_key, f"refunds?created[gte]={ts_gte}&limit=100")
    return (data or {}).get("data", [])


def _stripe_subscriptions(api_key: str) -> list:
    """Subscription.list (active) — MRR 추정용."""
    data = _stripe_get(api_key, "subscriptions?status=active&limit=100&expand[]=data.items")
    return (data or {}).get("data", [])


def _stripe_top_customers(api_key: str, ts_gte: int) -> list[dict]:
    """이번 달 PaymentIntent 기준 top 5 customer (email + 누적 금액 USD)."""
    data = _stripe_get(api_key, f"payment_intents?created[gte]={ts_gte}&limit=100")
    intents = (data or {}).get("data", [])

    customer_rev: dict[str, int] = {}
    for pi in intents:
        if pi.get("status") != "succeeded":
            continue
        cid = pi.get("customer") or pi.get("receipt_email") or "unknown"
        amt = pi.get("amount_received", 0)
        customer_rev[cid] = customer_rev.get(cid, 0) + amt

    sorted_customers = sorted(customer_rev.items(), key=lambda x: x[1], reverse=True)[:5]
    return [
        {"customer": cid, "revenue_usd": f"${cents / 100:.2f}"}
        for cid, cents in sorted_customers
    ]


def fetch_stripe_kpi() -> dict:
    """Stripe API: 매출 강화 섹션 (O-I).

    - 전일 매출 (KRW + USD)
    - MoM 매출 추세 (전월 대비)
    - 환불 금액 + 건수
    - MRR 추정 (active subscription 합산)
    - top 5 customer (revenue, 이번달 기준)
    - 결제 성공/실패 수 (기존 유지)

    Stripe API 무료 — 추가 비용 없음.
    """
    result: dict = {
        "charges_success": "N/A",
        "charges_fail": "N/A",
        "revenue_today_usd": "N/A",
        # O-I 신규
        "revenue_yesterday_usd": "N/A",
        "revenue_this_month_usd": "N/A",
        "revenue_prev_month_usd": "N/A",
        "mom_change_pct": "N/A",
        "refund_count": "N/A",
        "refund_amount_usd": "N/A",
        "mrr_estimate_usd": "N/A",
        "top_customers": [],
    }

    api_key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not api_key:
        logger.warning("STRIPE_SECRET_KEY 미설정 — Stripe KPI skip")
        result["caveat"] = "STRIPE_SECRET_KEY 미설정"
        return result

    today_start = _today_start_unix()
    yesterday_start = _yesterday_start_unix()
    month_start = _month_start_unix()
    prev_month_start, prev_month_end = _prev_month_range_unix()

    # 1. 오늘 PaymentIntent (기존 로직 유지)
    pi_data = _stripe_get(
        api_key,
        f"payment_intents?created[gte]={today_start}&limit=100"
    )
    intents_today = (pi_data or {}).get("data", [])
    success = sum(1 for p in intents_today if p.get("status") == "succeeded")
    fail = sum(1 for p in intents_today if p.get("status") in ("requires_payment_method", "canceled"))
    rev_today_cents = sum(
        p.get("amount_received", 0)
        for p in intents_today
        if p.get("status") == "succeeded" and p.get("currency", "").lower() == "usd"
    )

    # 2. 전일 BalanceTransaction
    bt_yesterday = _stripe_balance_transactions(api_key, yesterday_start, today_start)
    rev_yesterday_cents = sum(t.get("net", 0) for t in bt_yesterday)

    # 3. 이번달 BalanceTransaction
    bt_this_month = _stripe_balance_transactions(api_key, month_start)
    rev_this_month_cents = sum(t.get("net", 0) for t in bt_this_month)

    # 4. 전월 BalanceTransaction
    bt_prev_month = _stripe_balance_transactions(api_key, prev_month_start, prev_month_end)
    rev_prev_month_cents = sum(t.get("net", 0) for t in bt_prev_month)

    # MoM 변화율
    if rev_prev_month_cents > 0:
        mom_pct = ((rev_this_month_cents - rev_prev_month_cents) / rev_prev_month_cents) * 100
        mom_str = f"{mom_pct:+.1f}%"
    elif rev_this_month_cents > 0:
        mom_str = "+∞ (전월 0)"
    else:
        mom_str = "N/A"

    # 5. 환불
    refunds = _stripe_refunds(api_key, yesterday_start)
    refund_count = len(refunds)
    refund_cents = sum(r.get("amount", 0) for r in refunds)

    # 6. MRR 추정
    subs = _stripe_subscriptions(api_key)
    mrr_cents = 0
    for sub in subs:
        for item in (sub.get("items") or {}).get("data", []):
            price = item.get("price") or {}
            recurring = price.get("recurring") or {}
            amount = price.get("unit_amount") or 0
            interval = recurring.get("interval", "")
            qty = item.get("quantity", 1)
            if interval == "month":
                mrr_cents += amount * qty
            elif interval == "year":
                mrr_cents += (amount * qty) // 12

    # 7. top 5 customer (이번달)
    top_customers = _stripe_top_customers(api_key, month_start)

    result.update({
        "charges_success": success,
        "charges_fail": fail,
        "revenue_today_usd": f"${rev_today_cents / 100:.2f}",
        "revenue_yesterday_usd": f"${rev_yesterday_cents / 100:.2f}",
        "revenue_this_month_usd": f"${rev_this_month_cents / 100:.2f}",
        "revenue_prev_month_usd": f"${rev_prev_month_cents / 100:.2f}",
        "mom_change_pct": mom_str,
        "refund_count": refund_count,
        "refund_amount_usd": f"${refund_cents / 100:.2f}",
        "mrr_estimate_usd": f"${mrr_cents / 100:.2f}",
        "top_customers": top_customers,
    })
    logger.info(
        "Stripe KPI: today=$%.2f yesterday=$%.2f MRR=$%.2f MoM=%s",
        rev_today_cents / 100, rev_yesterday_cents / 100, mrr_cents / 100, mom_str,
    )
    return result


# ── (d) Sentry KPI ────────────────────────────────────────────────────────────

def fetch_sentry_kpi() -> dict:
    """Sentry API: 최근 24h 이슈 수 + unresolved critical 수.

    Sentry 무료 플랜 포함 — 추가 비용 없음.
    """
    result: dict = {
        "total_issues_24h": "N/A",
        "unresolved_critical": "N/A",
    }

    token = os.environ.get("SENTRY_AUTH_TOKEN", "")
    org = os.environ.get("SENTRY_ORG", "")
    project = os.environ.get("SENTRY_PROJECT", "")

    if not all([token, org, project]):
        logger.warning("Sentry env 미설정 (SENTRY_AUTH_TOKEN/ORG/PROJECT) — skip")
        result["caveat"] = "Sentry env 미설정"
        return result

    since = _utc_ts(24)
    url = (
        f"https://sentry.io/api/0/projects/{org}/{project}/issues/"
        f"?query=is:unresolved&firstSeen:>{since}&limit=100"
    )
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            issues = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        logger.error("Sentry API HTTP %s", exc.code)
        result["error"] = f"HTTP {exc.code}"
        return result
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.error("Sentry API error: %s", exc)
        result["error"] = str(exc)
        return result

    total = len(issues)
    critical = sum(1 for i in issues if i.get("level") in ("fatal", "error"))
    result.update({"total_issues_24h": total, "unresolved_critical": critical})
    return result


# ── 렌더 ──────────────────────────────────────────────────────────────────────

def render_kpi_brief(db: dict, stripe: dict, sentry: dict) -> str:
    today = _today_kst()
    now_str = _now_kst().strftime("%Y-%m-%d %H:%M KST")

    db_caveat = f"\n  > _{db.get('caveat', '')}_" if db.get("caveat") else ""
    stripe_caveat = f"\n  > _{stripe.get('caveat', '')}_" if stripe.get("caveat") else ""
    sentry_caveat = f"\n  > _{sentry.get('caveat', '')}_" if sentry.get("caveat") else ""

    db_err = f"\n  > 오류: `{db.get('error')}`" if db.get("error") else ""
    stripe_err = f"\n  > 오류: `{stripe.get('error')}`" if stripe.get("error") else ""
    sentry_err = f"\n  > 오류: `{sentry.get('error')}`" if sentry.get("error") else ""

    # top 5 customer 렌더링
    top_customers = stripe.get("top_customers", [])
    if top_customers:
        top_lines = "\n".join(
            f"| {i+1} | {c['customer']} | {c['revenue_usd']} |"
            for i, c in enumerate(top_customers)
        )
        top_table = (
            "\n\n**Top 5 Customer (이번달)**\n\n"
            "| # | Customer | Revenue |\n|---|---|---|\n"
            + top_lines
        )
    else:
        top_table = ""

    return f"""## PivoxQuant Morning Brief KPI — {today}

생성: {now_str}

---

### (a) 사용자 활동{db_caveat}{db_err}

| 지표 | 값 |
|---|---|
| DAU (24h 활성) | {db.get('dau', 'N/A')} |
| WAU (7일 활성) | {db.get('wau', 'N/A')} |
| 신규 가입 24h  | {db.get('new_users_24h', 'N/A')} |
| 전체 유저 수   | {db.get('total_users', 'N/A')} |

---

### (b) Stripe 매출 현황 (O-I 강화){stripe_caveat}{stripe_err}

| 지표 | 값 |
|---|---|
| 결제 성공 (오늘)     | {stripe.get('charges_success', 'N/A')} |
| 결제 실패 (오늘)     | {stripe.get('charges_fail', 'N/A')} |
| 오늘 매출 USD        | {stripe.get('revenue_today_usd', 'N/A')} |
| 전일 매출 USD        | {stripe.get('revenue_yesterday_usd', 'N/A')} |
| 이번달 매출 USD      | {stripe.get('revenue_this_month_usd', 'N/A')} |
| 전월 매출 USD        | {stripe.get('revenue_prev_month_usd', 'N/A')} |
| MoM 변화율           | {stripe.get('mom_change_pct', 'N/A')} |
| 환불 건수 (전일)     | {stripe.get('refund_count', 'N/A')} |
| 환불 금액 USD (전일) | {stripe.get('refund_amount_usd', 'N/A')} |
| MRR 추정 USD         | {stripe.get('mrr_estimate_usd', 'N/A')} |

> _MRR = active subscription 합산 추정치 (할인/trial 미반영)_{top_table}

---

### (c) Sentry 에러 현황 (24h){sentry_caveat}{sentry_err}

| 지표 | 값 |
|---|---|
| 전체 이슈 (24h)  | {sentry.get('total_issues_24h', 'N/A')} |
| Unresolved critical | {sentry.get('unresolved_critical', 'N/A')} |

---

_이 KPI brief는 매일 06:05 KST에 자동 생성됩니다 (build_brief_kpi.py)._
"""


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PivoxQuant Morning Brief KPI")
    parser.add_argument("--output", default=None, help="출력 파일 경로 (기본: morning_briefs/YYYY-MM-DD.md)")
    parser.add_argument("--no-slack", action="store_true", help="Slack 전송 skip")
    args = parser.parse_args(argv)

    logger.info("Morning Brief KPI 생성 시작")

    db = fetch_db_kpi()
    stripe = fetch_stripe_kpi()
    sentry = fetch_sentry_kpi()

    brief = render_kpi_brief(db, stripe, sentry)

    # 파일 저장
    out_path = Path(args.output) if args.output else BRIEFS_DIR / f"{_today_kst()}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(brief, encoding="utf-8")
    logger.info("Brief saved: %s (%d chars)", out_path, len(brief))

    # Slack 전송
    if not args.no_slack:
        # 요약만 Slack에 전송 (전문은 파일)
        dau = db.get("dau", "N/A")
        new_u = db.get("new_users_24h", "N/A")
        s_ok = stripe.get("charges_success", "N/A")
        rev_yday = stripe.get("revenue_yesterday_usd", "N/A")
        mrr = stripe.get("mrr_estimate_usd", "N/A")
        mom = stripe.get("mom_change_pct", "N/A")
        sentry_c = sentry.get("unresolved_critical", "N/A")
        summary = (
            f"[PivoxQuant KPI {_today_kst()}]\n"
            f"DAU: {dau} | 신규 가입: {new_u}\n"
            f"결제 성공: {s_ok} | 전일 매출: {rev_yday} | MRR: {mrr} | MoM: {mom}\n"
            f"Sentry critical: {sentry_c}\n"
            f"상세: {out_path}"
        )
        post_slack(summary)

    logger.info("Morning Brief KPI 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
