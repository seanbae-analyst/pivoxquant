#!/usr/bin/env python3
"""
Nightly Anthropic Claude API cost estimation (Wave I G-3).
==========================================================

매일 22:00 KST 실행. anthropic_usage_log 테이블을 집계해 오늘 사용량 +
MTD (Month-to-Date) 누적 비용을 추정하고, 일일 한도(PIVOX_ANTHROPIC_DAILY_LIMIT_USD)
대비 80% / 100% 시 Slack 알림을 발송한다.

SWOT 500 root cause (2026-05-09 v28 세션): Anthropic 크레딧 소진 → API 전면
차단 재발 방지가 핵심 목적이다.

가격표 (2026-05 기준, Anthropic 공식)
--------------------------------------
claude-haiku-4-5-20251001  (사용중 — MODEL in services/ai/service.py)
  Input:  $0.80  / 1M tokens
  Output: $4.00  / 1M tokens

claude-sonnet-4-5          (fallback / 미래 upgrade 대비)
  Input:  $3.00  / 1M tokens
  Output: $15.00 / 1M tokens

claude-opus-4              (premium 기능 / 미래 대비)
  Input:  $15.00 / 1M tokens
  Output: $75.00 / 1M tokens

DB 가 없거나 테이블이 없을 때는 state/anthropic_usage_history.json 만 갱신하고
graceful exit.

비용: 0원 (Slack free tier + DB 는 기존 Railway PostgreSQL)
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

logger = logging.getLogger("anthropic_cost_estimate")

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_STATE_DIR = _PROJECT_ROOT / "state"
_STATE_FILE = _STATE_DIR / "anthropic_usage_history.json"

# ── 일일 한도 (환경변수 override 가능) ──────────────────────────────────
_DEFAULT_DAILY_LIMIT_USD = 5.0
DAILY_LIMIT_USD: float = float(
    os.environ.get("PIVOX_ANTHROPIC_DAILY_LIMIT_USD", str(_DEFAULT_DAILY_LIMIT_USD))
)
WARN_PCT: float = 80.0   # 80% 시 경고
HARD_PCT: float = 100.0  # 100% 시 긴급 알림

# ── 모델별 가격표 (per 1M tokens) ────────────────────────────────────────
PRICE_TABLE: dict[str, dict[str, float]] = {
    # haiku — 현재 PivoxQuant 사용 모델
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
    "claude-haiku-4-5":          {"input": 0.80, "output": 4.00},
    "claude-haiku-3-5":          {"input": 0.80, "output": 4.00},
    # sonnet
    "claude-sonnet-4-5":         {"input": 3.00, "output": 15.00},
    "claude-sonnet-4":           {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet":         {"input": 3.00, "output": 15.00},
    # opus
    "claude-opus-4":             {"input": 15.00, "output": 75.00},
    "claude-opus-4-5":           {"input": 15.00, "output": 75.00},
    # default fallback (haiku 기준)
    "_default":                  {"input": 0.80, "output": 4.00},
}


def _token_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """토큰 수 → USD 추정 비용."""
    prices = PRICE_TABLE.get(model)
    if prices is None:
        # prefix 매칭 (예: "claude-haiku-4-5-20251001-xxx")
        for key, p in PRICE_TABLE.items():
            if key != "_default" and model.startswith(key):
                prices = p
                break
    if prices is None:
        prices = PRICE_TABLE["_default"]
    return (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1_000_000


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _load_state() -> dict:
    try:
        if _STATE_FILE.exists():
            return json.loads(_STATE_FILE.read_text())
    except Exception:
        pass
    return {"history": []}


def _save_state(state: dict) -> None:
    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        _STATE_FILE.write_text(json.dumps(state, indent=2))
    except Exception as exc:
        logger.warning("anthropic_cost_estimate: state save failed: %s", exc)


def _post_slack(text: str) -> bool:
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL 미설정 — stdout: %s", text)
        print(f"[ANTHROPIC-COST-ALERT] {text}")
        return False
    try:
        import urllib.request
        payload = json.dumps({"text": text}).encode()
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as exc:
        logger.error("anthropic_cost_estimate: Slack POST failed: %s", exc)
        return False


def _capture_sentry_warning(msg: str) -> None:
    try:
        import sentry_sdk
        sentry_sdk.capture_message(msg, level="warning")
    except Exception:
        pass


# ── DB 집계 ──────────────────────────────────────────────────────────────

def _query_usage(today_iso: str, month_iso: str) -> dict:
    """
    Returns:
        {
          "today": {"input_tokens": int, "output_tokens": int, "calls": int},
          "mtd":   {"input_tokens": int, "output_tokens": int, "calls": int},
          "by_model_today": {model: {"input": int, "output": int}},
        }
    """
    empty = {
        "today": {"input_tokens": 0, "output_tokens": 0, "calls": 0},
        "mtd": {"input_tokens": 0, "output_tokens": 0, "calls": 0},
        "by_model_today": {},
    }
    try:
        _root = str(_PROJECT_ROOT)
        if _root not in sys.path:
            sys.path.insert(0, _root)

        # Flask app context 없이 raw SQLAlchemy engine 직접 사용
        from config import Config
        from sqlalchemy import create_engine, text as sa_text

        db_url = (
            os.environ.get("DATABASE_URL")
            or getattr(Config, "SQLALCHEMY_DATABASE_URI", None)
            or ""
        )
        if not db_url:
            logger.warning("anthropic_cost_estimate: DATABASE_URL 미설정 — DB 집계 skip")
            return empty

        engine = create_engine(db_url, pool_pre_ping=True)
        with engine.connect() as conn:
            # anthropic_usage_log 테이블 존재 확인
            check = conn.execute(
                sa_text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = 'anthropic_usage_log' LIMIT 1"
                )
            ).fetchone()
            if not check:
                logger.info(
                    "anthropic_cost_estimate: anthropic_usage_log 테이블 없음 — "
                    "alembic 042 migration 미적용 가능성"
                )
                return empty

            # 오늘 집계
            today_row = conn.execute(
                sa_text(
                    "SELECT COALESCE(SUM(input_tokens),0), "
                    "       COALESCE(SUM(output_tokens),0), "
                    "       COUNT(*) "
                    "FROM anthropic_usage_log "
                    "WHERE DATE(created_at) = :d"
                ),
                {"d": today_iso},
            ).fetchone()

            # MTD 집계
            mtd_row = conn.execute(
                sa_text(
                    "SELECT COALESCE(SUM(input_tokens),0), "
                    "       COALESCE(SUM(output_tokens),0), "
                    "       COUNT(*) "
                    "FROM anthropic_usage_log "
                    "WHERE created_at >= :m"
                ),
                {"m": month_iso + " 00:00:00"},
            ).fetchone()

            # 모델별 오늘
            model_rows = conn.execute(
                sa_text(
                    "SELECT model, "
                    "       COALESCE(SUM(input_tokens),0), "
                    "       COALESCE(SUM(output_tokens),0) "
                    "FROM anthropic_usage_log "
                    "WHERE DATE(created_at) = :d "
                    "GROUP BY model"
                ),
                {"d": today_iso},
            ).fetchall()

        result = {
            "today": {
                "input_tokens": int(today_row[0]),
                "output_tokens": int(today_row[1]),
                "calls": int(today_row[2]),
            },
            "mtd": {
                "input_tokens": int(mtd_row[0]),
                "output_tokens": int(mtd_row[1]),
                "calls": int(mtd_row[2]),
            },
            "by_model_today": {
                row[0]: {"input": int(row[1]), "output": int(row[2])}
                for row in model_rows
            },
        }
        return result

    except Exception as exc:
        logger.warning("anthropic_cost_estimate: DB query failed: %s", exc)
        return empty


# ── 핵심 실행 ─────────────────────────────────────────────────────────────

def run_cost_estimate() -> int:
    """
    Returns:
        0 — 정상 (한도 미달)
        1 — 80% 경고 알림 발송
        2 — 100% 긴급 알림 발송
        3 — 예외 발생
    """
    try:
        today = date.today()
        today_iso = today.isoformat()
        month_iso = today.replace(day=1).isoformat()

        usage = _query_usage(today_iso, month_iso)

        # 비용 추정
        today_cost = 0.0
        today_in = usage["today"]["input_tokens"]
        today_out = usage["today"]["output_tokens"]
        by_model = usage["by_model_today"]

        if by_model:
            for model, tok in by_model.items():
                today_cost += _token_cost_usd(model, tok["input"], tok["output"])
        else:
            # 단일 모델 default 추정
            today_cost = _token_cost_usd("_default", today_in, today_out)

        mtd_in = usage["mtd"]["input_tokens"]
        mtd_out = usage["mtd"]["output_tokens"]
        # MTD 비용은 모델별 분해가 없으므로 가중 평균으로 추정
        # (haiku 비중 > 95% 가정 — 보수적 상한을 위해 sonnet 가격 혼용 없음)
        mtd_cost = _token_cost_usd("claude-haiku-4-5-20251001", mtd_in, mtd_out)

        pct = (today_cost / DAILY_LIMIT_USD * 100) if DAILY_LIMIT_USD > 0 else 0

        logger.info(
            "anthropic_cost: today=%.4f USD (%.1f%% of limit), "
            "MTD=%.4f USD, calls_today=%d",
            today_cost, pct, mtd_cost, usage["today"]["calls"],
        )

        # state 업데이트
        state = _load_state()
        entry = {
            "date": today_iso,
            "today_cost_usd": round(today_cost, 6),
            "mtd_cost_usd": round(mtd_cost, 6),
            "today_input_tokens": today_in,
            "today_output_tokens": today_out,
            "today_calls": usage["today"]["calls"],
            "pct_of_daily_limit": round(pct, 2),
            "recorded_at": _now_utc().isoformat(),
        }
        history: list = state.get("history", [])
        # 오늘 날짜 항목 upsert
        history = [h for h in history if h.get("date") != today_iso]
        history.append(entry)
        # 최대 90일 보관
        history = sorted(history, key=lambda h: h.get("date", ""))[-90:]
        state["history"] = history
        _save_state(state)

        # 알림 판단
        if pct >= HARD_PCT:
            msg = (
                f":rotating_light: *[PivoxQuant] Anthropic 일일 한도 도달!* "
                f"오늘 추정 비용: *${today_cost:.4f}* / ${DAILY_LIMIT_USD} "
                f"(*{pct:.1f}%*). "
                f"호출 수: {usage['today']['calls']}회. "
                f"MTD 누적: ${mtd_cost:.4f}. "
                f"PIVOX_ANTHROPIC_ENABLED 점검 요망."
            )
            _capture_sentry_warning(
                f"Anthropic daily limit reached: {pct:.1f}% "
                f"(${today_cost:.4f}/${DAILY_LIMIT_USD})"
            )
            _post_slack(msg)
            return 2
        elif pct >= WARN_PCT:
            msg = (
                f":warning: *[PivoxQuant] Anthropic 비용 경고* — "
                f"오늘 추정 비용: *${today_cost:.4f}* / ${DAILY_LIMIT_USD} "
                f"(*{pct:.1f}%*). "
                f"호출 수: {usage['today']['calls']}회. "
                f"MTD 누적: ${mtd_cost:.4f}."
            )
            _post_slack(msg)
            return 1
        else:
            return 0

    except Exception as exc:
        logger.error(
            "anthropic_cost_estimate: unexpected error: %s", exc, exc_info=True
        )
        try:
            import sentry_sdk
            sentry_sdk.capture_exception(exc)
        except Exception:
            pass
        return 3


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    sys.exit(run_cost_estimate())


if __name__ == "__main__":
    main()
