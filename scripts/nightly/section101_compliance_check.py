#!/usr/bin/env python3
"""O-H: §101 면제 트랙 4요건 일일 self-check (section101_compliance_check.py).

목적
----
유사투자자문업 §101 면제 트랙 4요건 (legal_decision_no_advisory.md 참조) 자동 모니터링.
1건이라도 위배 가능성 발견 시 Slack alert + Sentry capture + compliance_violations.log 누적.

4요건 체크
----------
(1) 광고성 콘텐츠 없음 — 정적 소스 파일 + 이메일 템플릿에서 광고성 키워드 grep
(2) 매월 청구 없음 — Stripe API: recurring.interval == 'month' plan 부재 확인
(3) 특정성 회피 — 최근 24h artifacts 에서 특정 종목 매수/매도 권유 패턴 샘플링
(4) 일반화된 정보 — AI 답변 생성 경로 확인 (template 기반 vs user-specific personalization)

False Positive 주의 (O-H carry-over 명시)
------------------------------------------
- "매수세 강함", "매도 압력" 등 분석 용어 vs "매수 권유" 구분 어려움
- 패턴 매칭은 1단계 힌트 — 실제 판단은 CEO/법무팀
- 위배 가능성으로 보고하되 "위반 확정"이 아님을 명시

비용 검증 (0원)
--------------
- DB query: Railway PostgreSQL
- Stripe API: 무료
- Slack/Sentry: 무료
- 파일 I/O: compliance_violations.log (로컬)

환경변수
--------
DATABASE_URL        — 필수 (Railway PostgreSQL)
STRIPE_SECRET_KEY   — 없으면 Stripe check skip
SLACK_WEBHOOK_URL   — 없으면 stdout
SENTRY_DSN          — 없으면 Sentry skip
PIVOX_REPO_ROOT     — 소스 grep root (default: auto-detect from script location)

실행
----
python scripts/nightly/section101_compliance_check.py
cron: 0 7 * * *  (KST 07:00 daily, morning-brief 이후 1시간)
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
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

_SSL_CTX = ssl.create_default_context()

# 레포 루트: 이 스크립트는 scripts/nightly/ 에 위치
_REPO_ROOT = Path(
    os.environ.get("PIVOX_REPO_ROOT", "")
) or Path(__file__).resolve().parent.parent.parent

_VIOLATIONS_LOG = _REPO_ROOT / "compliance_violations.log"

# (1) 광고성 키워드 패턴
_AD_PATTERNS = re.compile(
    r"(광고|sponsored|스폰서|프로모션|promotion|할인\s*쿠폰|리워드|적립금|cashback|캐시백)",
    re.IGNORECASE,
)

# (3) 특정성 — 매수/매도 권유 패턴 (false positive 가능)
_SOLICITATION_PATTERNS = re.compile(
    r"(매수\s*권유|매도\s*권유|BUY\s+NOW|SELL\s+NOW|즉시\s*매수|즉시\s*매도"
    r"|투자\s*권유|종목\s*추천|buy\s+recommendation|sell\s+recommendation)",
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


# ── 위반 로그 기록 ────────────────────────────────────────────────────────────

def _log_violation(entry: str) -> None:
    now = datetime.now(timezone.utc) + timedelta(hours=9)
    line = f"[{now.strftime('%Y-%m-%d %H:%M KST')}] {entry}\n"
    try:
        with open(_VIOLATIONS_LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError as exc:
        logger.error("compliance_violations.log 쓰기 실패: %s", exc)


# ── (1) 광고성 키워드 grep ───────────────────────────────────────────────────

def _check_ad_keywords() -> list[str]:
    """정적 소스 + 이메일 템플릿에서 광고성 키워드 탐지."""
    hits: list[str] = []
    search_dirs = [
        _REPO_ROOT / "frontend" / "src",
        _REPO_ROOT / "services" / "email",
        _REPO_ROOT / "templates",
    ]
    extensions = {".tsx", ".ts", ".jsx", ".js", ".html", ".txt", ".md"}

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for filepath in search_dir.rglob("*"):
            if filepath.suffix not in extensions:
                continue
            if "node_modules" in filepath.parts or "__pycache__" in filepath.parts:
                continue
            try:
                text = filepath.read_text(encoding="utf-8", errors="ignore")
                matches = _AD_PATTERNS.findall(text)
                if matches:
                    rel = filepath.relative_to(_REPO_ROOT)
                    hits.append(f"{rel}: {matches[:3]}")
            except OSError:
                pass

    return hits


# ── (2) Stripe 매월 청구 plan 확인 ───────────────────────────────────────────

def _check_stripe_monthly() -> list[str]:
    """Stripe API: active subscription plan 중 interval == 'month' 있는지 확인."""
    api_key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not api_key:
        logger.warning("STRIPE_SECRET_KEY 미설정 — Stripe check skip")
        return []

    url = "https://api.stripe.com/v1/prices?active=true&limit=100"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {api_key}")

    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        logger.error("Stripe API HTTP %s", exc.code)
        return []
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.error("Stripe API error: %s", exc)
        return []

    monthly_plans: list[str] = []
    for price in data.get("data", []):
        recurring = price.get("recurring") or {}
        if recurring.get("interval") == "month":
            monthly_plans.append(
                f"price_id={price['id']} amount={price.get('unit_amount')} {price.get('currency','').upper()}"
            )

    return monthly_plans


# ── (3) 최근 24h artifact 특정성 샘플링 ──────────────────────────────────────

def _check_artifact_solicitation(db_url: str) -> list[str]:
    """artifacts 테이블 최근 24h title+data_json 샘플링 — 매수/매도 권유 패턴.

    artifacts 테이블엔 plain text ``content`` 컬럼이 없다. 본문은 ``title`` +
    ``data_json`` (JSON) 에 들어 있으므로 둘을 합쳐 스캔한다.
    """
    import json
    hits: list[str] = []

    def _scan_rows(rows: list) -> None:
        for row in rows:
            artifact_id, title, data_json = row[0], row[1] or "", row[2]
            try:
                blob = f"{title}\n{json.dumps(data_json, ensure_ascii=False, default=str)}"
            except (TypeError, ValueError):
                blob = f"{title}\n{data_json or ''}"
            matches = _SOLICITATION_PATTERNS.findall(blob)
            if matches:
                hits.append(f"artifact_id={artifact_id} patterns={matches[:3]}")

    try:
        import psycopg2  # type: ignore
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, title, data_json
            FROM artifacts
            WHERE created_at >= NOW() - INTERVAL '24 hours'
            LIMIT 200
            """
        )
        _scan_rows(cur.fetchall())
        cur.close()
        conn.close()
        return hits
    except ImportError:
        pass
    except Exception as exc:
        logger.error("artifact solicitation check (psycopg2) failed: %s", exc)
        return hits

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
            rows = conn.execute(
                text("SELECT id, title, data_json FROM artifacts WHERE created_at >= NOW() - INTERVAL '24 hours' LIMIT 200")
            ).fetchall()
        _scan_rows(rows)
    except Exception as exc:
        logger.error("artifact solicitation check (sqlalchemy) failed: %s", exc)

    return hits


# ── (4) 일반화 확인 (template 기반 vs user-specific) ─────────────────────────

def _check_generalization() -> list[str]:
    """
    AI 답변 생성 경로가 template 기반인지 확인.

    PivoxQuant 는 Artifact(Weekly Memo / Brag Card / Earnings Pre-Brief) 를
    template 기반으로 생성한다. route 소스에 personalized 투자 조언 경로가
    추가됐는지 grep 한다.
    """
    hits: list[str] = []
    routes_dir = _REPO_ROOT / "routes"
    if not routes_dir.exists():
        return hits

    # 투자 조언 특정성 패턴 (라우트 코드 레벨)
    advice_pattern = re.compile(
        r"(투자\s*조언|investment\s+advice|종목\s*추천|specific.*recommendation"
        r"|personalized.*investment|맞춤.*투자)",
        re.IGNORECASE,
    )
    for filepath in routes_dir.rglob("*.py"):
        if "__pycache__" in filepath.parts:
            continue
        try:
            text = filepath.read_text(encoding="utf-8", errors="ignore")
            if advice_pattern.search(text):
                rel = filepath.relative_to(_REPO_ROOT)
                hits.append(f"{rel}: 투자 조언 패턴 감지 (검토 필요)")
        except OSError:
            pass

    return hits


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main() -> int:
    now_kst = (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M KST")
    logger.info("section101_compliance_check 시작 (%s)", now_kst)

    violations: dict[str, list[str]] = {}

    # (1) 광고성 키워드
    ad_hits = _check_ad_keywords()
    if ad_hits:
        violations["(1) 광고성 키워드"] = ad_hits
    logger.info("(1) 광고 키워드 hits=%d", len(ad_hits))

    # (2) Stripe 매월 청구
    monthly = _check_stripe_monthly()
    if monthly:
        violations["(2) Stripe 매월 청구 plan"] = monthly
    logger.info("(2) Stripe monthly plans=%d", len(monthly))

    # (3) artifact 특정성
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url:
        solicitations = _check_artifact_solicitation(db_url)
        if solicitations:
            violations["(3) artifact 매수/매도 권유 패턴 (FP 가능)"] = solicitations
        logger.info("(3) artifact solicitation hits=%d", len(solicitations))
    else:
        logger.warning("DATABASE_URL 미설정 — (3) artifact check skip")

    # (4) 일반화 경로 확인
    advice_routes = _check_generalization()
    if advice_routes:
        violations["(4) 투자 조언 경로 감지 (검토 필요)"] = advice_routes
    logger.info("(4) generalization hits=%d", len(advice_routes))

    if not violations:
        msg = f"[PivoxQuant] section101_compliance_check PASS\n생성: {now_kst}"
        logger.info("section101_compliance_check PASS")
        print(msg)
        return 0

    # 위반 보고서 작성
    lines = [
        "[PivoxQuant] section101_compliance_check ALERT — §101 면제 요건 점검 필요",
        f"생성: {now_kst}",
        "⚠️ 아래 항목은 위반 '가능성' 힌트 — 실제 판단은 CEO/법무팀 필수",
        "",
    ]
    for category, items in violations.items():
        lines.append(f"### {category} ({len(items)}건)")
        for item in items[:5]:
            lines.append(f"  - {item}")
        if len(items) > 5:
            lines.append(f"  ... 외 {len(items) - 5}건")
        lines.append("")

    summary = "\n".join(lines)
    logger.warning("section101_compliance_check ALERT — %d 카테고리", len(violations))
    print(summary)

    # violations.log 누적
    for category, items in violations.items():
        _log_violation(f"{category}: {items[:3]}")

    _post_slack(summary)
    _capture_sentry(
        "section101_compliance_check: §101 면제 요건 점검 필요",
        extras={"violations": {k: v[:3] for k, v in violations.items()}},
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
