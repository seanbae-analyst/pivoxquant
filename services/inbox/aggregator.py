"""CEO Inbox aggregator — v57 Phase A.

5개 출처를 단일 payload로 통합:
1. autopilot_log.md tail (자율 처리 완료, 24h)
2. SHIP_BLOCKERS.md (RELEASE-BLOCKER / AT-RISK / POST-LAUNCH 카운트)
3. legal_question_queue.md (변호사 큐 PENDING / ANSWERED)
4. /tmp/ship_blockers_status.json (06:00 cron 출력)
5. /tmp/data_integrity_status.json (04:00 cron 출력)

읽기 전용 — 외부 API 호출 X, LLM X, DB write X.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo
    _KST = ZoneInfo("Asia/Seoul")
except ImportError:  # pragma: no cover
    _KST = timezone(timedelta(hours=9))

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_env_memory = os.environ.get("PIVOX_MEMORY_DIR", "").strip()
_MEMORY_DIR = Path(_env_memory) if _env_memory else (
    Path.home() / ".claude/projects/-Users-seanbae-Desktop---/memory"
)


def _read_safe(path: Path, max_bytes: int = 200_000) -> str:
    try:
        return path.read_text("utf-8")[:max_bytes]
    except OSError:
        return ""


def _now_kst() -> datetime:
    return datetime.now(_KST)


# ── Source 1: autopilot_log 24h tail ────────────────────────────────────────

def collect_autonomous_done(now: datetime | None = None) -> list[dict[str, Any]]:
    """autopilot_log.md 최근 24h entries 추출.

    포맷 예시:
      ## 2026-05-28 07:53 api-sentinel
      - status: clean
      - checks: 5 endpoints
    """
    now = now or _now_kst()
    cutoff = now - timedelta(hours=24)
    text = _read_safe(_MEMORY_DIR / "autopilot_log.md")
    if not text:
        return []
    entries: list[dict[str, Any]] = []
    header_re = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s+(.+)$")
    current: dict[str, Any] | None = None
    body_lines: list[str] = []

    def _flush() -> None:
        if current is not None:
            current["body"] = "\n".join(body_lines).strip()
            entries.append(current)

    for line in text.splitlines():
        m = header_re.match(line)
        if m:
            _flush()
            body_lines = []
            try:
                ts = datetime.strptime(
                    f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H:%M"
                ).replace(tzinfo=_KST)
            except ValueError:
                current = None
                continue
            if ts < cutoff:
                current = None
                continue
            current = {
                "timestamp_kst": ts.isoformat(),
                "agent": m.group(3).strip(),
            }
        elif current is not None:
            body_lines.append(line)
    _flush()
    return entries


# ── Source 2: SHIP_BLOCKERS categories ───────────────────────────────────────

def collect_ship_blockers() -> dict[str, Any]:
    """SHIP_BLOCKERS.md RELEASE / AT-RISK / POST-LAUNCH 카운트."""
    text = _read_safe(_REPO_ROOT / "SHIP_BLOCKERS.md")
    if not text:
        return {"release_blocker": 0, "ship_at_risk": 0, "post_launch": 0, "header": ""}
    # 헤더 1줄 (06:00 cron이 갱신하는 부분)
    header_match = re.search(r"\*\*최근 갱신\*\*:\s*(.+?)$", text, re.MULTILINE)
    header = header_match.group(1).strip() if header_match else ""
    # row 카운트 (R1-R99 / A1-A99 / P1-P99)
    r_count = len(re.findall(r"^\|\s*R\d+\s*\|", text, re.MULTILINE))
    a_count = len(re.findall(r"^\|\s*A\d+\s*\|", text, re.MULTILINE))
    p_count = len(re.findall(r"^\|\s*P\d+\s*\|", text, re.MULTILINE))
    return {
        "release_blocker": r_count,
        "ship_at_risk": a_count,
        "post_launch": p_count,
        "header": header,
    }


# ── Source 3: 변호사 큐 ──────────────────────────────────────────────────────

def collect_lawyer_queue() -> dict[str, Any]:
    """legal_question_queue.md PENDING / ANSWERED 카운트."""
    text = _read_safe(_MEMORY_DIR / "legal_question_queue.md")
    if not text:
        return {"total": 0, "pending": 0, "answered": 0}
    q_ids = set(re.findall(r"^####\s+(Q[\w-]+)", text, re.MULTILINE))
    answered_ids = set(
        re.findall(
            r"####\s+(Q[\w-]+).*?ANSWERED\s+\d{4}-\d{2}-\d{2}",
            text,
            re.DOTALL,
        )
    )
    return {
        "total": len(q_ids),
        "pending": len(q_ids - answered_ids),
        "answered": len(answered_ids),
    }


# ── Source 4 & 5: /tmp/*.json (cron 출력) ────────────────────────────────────

def collect_cron_status() -> dict[str, Any]:
    """ops_ship_blockers_daily / ops_data_integrity_sweep 출력 JSON 인용."""
    result: dict[str, Any] = {}
    for key, path in [
        ("ship_blockers_audit", "/tmp/ship_blockers_status.json"),
        ("data_integrity_sweep", "/tmp/data_integrity_status.json"),
    ]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                result[key] = json.load(f)
        except (OSError, json.JSONDecodeError):
            result[key] = None
    return result


# ── Source 6: next APScheduler fire (계산) ──────────────────────────────────

def collect_next_fires(now: datetime | None = None) -> list[dict[str, str]]:
    """주요 cron 다음 fire ETA 계산 (KST).

    APScheduler 직접 조회 없이 cron 표현을 직접 계산.
    """
    now = now or _now_kst()
    fires: list[dict[str, str]] = []

    def _next_daily(hour: int, minute: int = 0) -> datetime:
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    def _next_hourly(minute: int) -> datetime:
        candidate = now.replace(minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(hours=1)
        return candidate

    def _next_weekly(weekday: int, hour: int, minute: int = 0) -> datetime:
        """weekday: 0=Mon ... 6=Sun"""
        days_ahead = (weekday - now.weekday()) % 7
        candidate = (now + timedelta(days=days_ahead)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        if candidate <= now:
            candidate += timedelta(days=7)
        return candidate

    schedule = [
        ("ops_data_integrity_sweep", _next_daily(4, 0)),
        ("ops_ship_blockers_daily", _next_daily(6, 0)),
        ("morning-briefing (CC task)", _next_daily(6, 27)),
        ("ops_legal_packet_daily (pivoxquant-legal-guard)", _next_daily(6, 42)),
        ("api-sentinel (CC task hourly)", _next_hourly(47)),
        ("ops_lawyer_packet_weekly", _next_weekly(6, 21, 0)),  # Sunday=6
    ]
    for name, ts in sorted(schedule, key=lambda kv: kv[1]):
        delta = ts - now
        hours = int(delta.total_seconds() // 3600)
        minutes = int((delta.total_seconds() % 3600) // 60)
        fires.append({
            "task": name,
            "next_fire_kst": ts.strftime("%Y-%m-%d %H:%M KST"),
            "eta": f"{hours}h {minutes}m",
        })
    return fires


# ── Aggregator ──────────────────────────────────────────────────────────────

def build_inbox_payload(now: datetime | None = None) -> dict[str, Any]:
    """단일 inbox payload 생성.

    Returns
    -------
    dict
        {
          "generated_at_kst": ISO datetime,
          "autonomous_done": [...],   # autopilot_log 24h
          "ship_blockers": {...},      # R/A/P 카운트 + 헤더
          "lawyer_queue": {...},       # 변호사 큐
          "cron_status": {...},        # /tmp/*.json
          "next_fires": [...],         # 다음 6개 cron
          "summary": str               # 한 줄 요약
        }
    """
    now = now or _now_kst()
    autonomous = collect_autonomous_done(now)
    ship = collect_ship_blockers()
    lawyer = collect_lawyer_queue()
    cron = collect_cron_status()
    fires = collect_next_fires(now)
    summary = (
        f"자율 완료 {len(autonomous)}건 · "
        f"RELEASE {ship['release_blocker']} / AT-RISK {ship['ship_at_risk']} · "
        f"변호사 {lawyer['pending']}/{lawyer['total']} PENDING · "
        f"다음 fire {fires[0]['task'] if fires else '없음'} ({fires[0]['eta'] if fires else '-'})"
    )
    return {
        "generated_at_kst": now.strftime("%Y-%m-%d %H:%M:%S KST"),
        "autonomous_done": autonomous,
        "ship_blockers": ship,
        "lawyer_queue": lawyer,
        "cron_status": cron,
        "next_fires": fires,
        "summary": summary,
    }
