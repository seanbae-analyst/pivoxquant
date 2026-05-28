#!/usr/bin/env python3
"""SHIP_BLOCKERS.md 일일 자동 audit (T9).

목적
====
launch-coordinator agent 명세를 매일 06:00 KST 실측 layer로 자동 fire한다.
- 변호사 큐 (legal_question_queue.md) 항목 카운트
- SHIP_BLOCKERS.md 본문 카테고리별 카운트 (RELEASE-BLOCKER / SHIP-AT-RISK / POST-LAUNCH)
- DNS / Brevo / Slack / Sentry / 통신판매업 등 env 기반 상태 측정
- 결과를 ``/tmp/ship_blockers_status.json`` 저장 (morning-briefing 06:27 prepend용)
- SHIP_BLOCKERS.md 헤더의 "최근 갱신" 1줄만 patch (본문 무손상)

원칙
====
- 본문 자동 수정 금지 — 헤더 "최근 갱신" 줄만 patch (CEO 수동 편집 보존)
- 변호사 답변 / 통신판매업 / DNS 상태 추측 금지 — 메모리 파일 grep + env 확인만
- 외부 API 호출 금지 — 모두 로컬 file/env grep
- 추가 비용 0원 (feedback_no_extra_cost 준수)
- 실측 결과만 인용 (feedback_no_false_reports 준수)

cron
====
``services/scheduler/cron_jobs.py:_job_specs()`` 의 ``ops_ship_blockers_daily``
(``CronTrigger(hour=6, minute=0, timezone=KST)``). morning-briefing(06:27)이
fire 되기 전 status JSON 을 갱신해두는 순서.

환경변수 / 파일 의존 (전부 optional, 없으면 PENDING으로 표기)
============================================================
- ``MEMORY_DIR``                 — legal_question_queue.md 등 메모리 위치
  (기본: ``~/.claude/projects/-Users-seanbae-Desktop---/memory``)
- ``SHIP_BLOCKERS_PATH``         — SHIP_BLOCKERS.md 경로
  (기본: ``<repo>/SHIP_BLOCKERS.md``)
- ``SHIP_BLOCKERS_STATUS_JSON``  — JSON 출력 위치
  (기본: ``/tmp/ship_blockers_status.json``)
- ``BREVO_API_KEY``              — 미설정 시 A2 PENDING
- ``SLACK_WEBHOOK_URL``          — 미설정 시 A5 PENDING
- ``SENTRY_AUTH_TOKEN``          — 미설정 시 Sentry alert PENDING
- ``PIVOX_COMMERCE_REGISTERED``  — 'true'면 R3 RESOLVED, 그 외 PENDING
- ``SENDGRID_WEBHOOK_PUBLIC_KEY`` — 미설정 시 A3 PENDING

플래그
======
- ``--dry-run`` : SHIP_BLOCKERS.md 헤더 patch 생략 (JSON 만 출력)
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ── 경로 상수 ──────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_MEMORY_DIR = Path.home() / ".claude/projects/-Users-seanbae-Desktop---/memory"
_DEFAULT_SHIP_BLOCKERS = _ROOT / "SHIP_BLOCKERS.md"
_DEFAULT_STATUS_JSON = Path("/tmp/ship_blockers_status.json")

# ── 카운트 파서 ────────────────────────────────────────────────────────────────
# legal_question_queue.md 의 질문 헤더 패턴 — `#### Q5` / `#### Q-S1` / `#### Q-M1`
_LEGAL_Q_RE = re.compile(r"^####\s+(Q[\-A-Z0-9]+)\b", re.MULTILINE)
# SHIP_BLOCKERS.md 표 row — `| R1 | ... | BLOCKED |` 형태
_BLOCKER_ROW_RE = re.compile(
    r"^\|\s*([RAP])(\d+)\s*\|[^|]*\|[^|]*\|[^|]*\|[^|]*\|[^|]*\|\s*([A-Z_]+)\s*\|",
    re.MULTILINE,
)
# 헤더의 "최근 갱신" 줄 — 본문 무손상 patch 대상
_LAST_UPDATED_RE = re.compile(
    r"^\*\*최근 갱신\*\*:\s*.*$", re.MULTILINE
)


def _now_kst() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=9)


def _bool_env(name: str) -> bool:
    val = os.environ.get(name, "").strip().lower()
    return val in {"1", "true", "yes", "on"}


def _has_env(name: str) -> bool:
    val = os.environ.get(name, "").strip()
    return bool(val)


# ── 카운트 헬퍼 ────────────────────────────────────────────────────────────────
def count_legal_questions(memory_dir: Path) -> dict:
    """legal_question_queue.md 의 질문 개수 + status frontmatter 읽기."""
    path = memory_dir / "legal_question_queue.md"
    if not path.exists():
        return {"total": 0, "status": "FILE_NOT_FOUND", "path": str(path)}
    try:
        text = path.read_text("utf-8")
    except OSError as exc:
        return {"total": 0, "status": f"READ_ERROR:{exc}", "path": str(path)}

    questions = _LEGAL_Q_RE.findall(text)
    # frontmatter status: pending CEO ... 같은 1줄
    status_match = re.search(r"^status:\s*(.+)$", text, re.MULTILINE)
    fm_status = status_match.group(1).strip() if status_match else "unknown"

    return {
        "total": len(questions),
        "ids": sorted(set(questions)),
        "frontmatter_status": fm_status,
        "path": str(path),
    }


def count_ship_blocker_rows(ship_blockers_path: Path) -> dict:
    """SHIP_BLOCKERS.md 본문 표 카테고리별 카운트 (R/A/P prefix)."""
    if not ship_blockers_path.exists():
        return {"release": 0, "at_risk": 0, "post_launch": 0, "status": "FILE_NOT_FOUND"}
    try:
        text = ship_blockers_path.read_text("utf-8")
    except OSError as exc:
        return {
            "release": 0,
            "at_risk": 0,
            "post_launch": 0,
            "status": f"READ_ERROR:{exc}",
        }

    rows = _BLOCKER_ROW_RE.findall(text)
    counts = {"R": 0, "A": 0, "P": 0}
    statuses_per_category = {"R": [], "A": [], "P": []}
    for prefix, num, status in rows:
        counts[prefix] = counts.get(prefix, 0) + 1
        statuses_per_category[prefix].append(f"{prefix}{num}:{status}")
    return {
        "release": counts["R"],
        "at_risk": counts["A"],
        "post_launch": counts["P"],
        "release_rows": statuses_per_category["R"],
        "at_risk_rows": statuses_per_category["A"],
        "post_launch_rows": statuses_per_category["P"],
    }


def measure_env_status() -> dict:
    """외부 액션 carry-over 의 env 기반 status 측정. 외부 API 호출 0건."""
    commerce = "RESOLVED" if _bool_env("PIVOX_COMMERCE_REGISTERED") else "PENDING"
    return {
        "commerce_registration": commerce,        # R3
        "brevo_api_key": "SET" if _has_env("BREVO_API_KEY") else "PENDING",       # A2
        "slack_webhook": "SET" if _has_env("SLACK_WEBHOOK_URL") else "PENDING",   # A5
        "sendgrid_webhook_key": (
            "SET" if _has_env("SENDGRID_WEBHOOK_PUBLIC_KEY") else "PENDING"
        ),                                                                          # A3
        "sentry_token": "SET" if _has_env("SENTRY_AUTH_TOKEN") else "PENDING",
        "naver_news_api": (
            "SET" if _has_env("NAVER_NEWS_CLIENT_ID") else "PENDING"
        ),                                                                          # A6
        "vapid_public": "SET" if _has_env("VAPID_PUBLIC_KEY") else "PENDING",     # A10
        "stripe_secret": "SET" if _has_env("STRIPE_SECRET_KEY") else "PENDING",   # B5
    }


def measure_dns_status() -> dict:
    """DNS 상태는 외부 API 호출 X — env hint flag 만 본다.

    실측 dig 은 launch-runner agent 가 별도로 수행 (Bash 권한 필요).
    본 audit 은 ``PIVOX_DNS_CONFIGURED`` env flag 만 신호로 사용.
    CEO 가 가비아 콘솔에서 4 레코드 (MX/SPF/DKIM/DMARC) 설정 후 Railway env
    에 ``PIVOX_DNS_CONFIGURED=true`` 토글 → 본 status RESOLVED.
    """
    return {
        "dns_status": (
            "RESOLVED" if _bool_env("PIVOX_DNS_CONFIGURED") else "PENDING"
        ),
        "note": "실측 dig은 launch-runner agent 수행 (Bash 권한). 본 audit은 env flag만.",
    }


# ── status JSON 빌드 ───────────────────────────────────────────────────────────
def build_status_payload(memory_dir: Path, ship_blockers_path: Path) -> dict:
    legal = count_legal_questions(memory_dir)
    rows = count_ship_blocker_rows(ship_blockers_path)
    env = measure_env_status()
    dns = measure_dns_status()

    payload = {
        "generated_at_kst": _now_kst().strftime("%Y-%m-%d %H:%M:%S KST"),
        "source": "scripts/nightly/ship_blockers_audit.py",
        "legal": legal,
        "ship_blockers": rows,
        "env": env,
        "dns": dns,
        "summary": (
            f"RELEASE-BLOCKER {rows.get('release', 0)}건 / "
            f"SHIP-AT-RISK {rows.get('at_risk', 0)}건 / "
            f"POST-LAUNCH {rows.get('post_launch', 0)}건 / "
            f"변호사 큐 {legal.get('total', 0)}건"
        ),
    }
    return payload


def write_status_json(payload: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("status JSON written: %s", out_path)


# ── SHIP_BLOCKERS.md 헤더 patch (1줄만) ────────────────────────────────────────
def patch_ship_blockers_header(ship_blockers_path: Path, payload: dict) -> bool:
    """헤더 '최근 갱신' 1줄만 in-place patch. 본문은 절대 건드리지 않는다.

    Returns True if patched, False if no change / file missing / pattern miss.
    """
    if not ship_blockers_path.exists():
        logger.warning("SHIP_BLOCKERS.md 없음, header patch 생략: %s", ship_blockers_path)
        return False
    try:
        text = ship_blockers_path.read_text("utf-8")
    except OSError as exc:
        logger.error("read failed: %s", exc)
        return False

    new_line = (
        f"**최근 갱신**: {_now_kst().strftime('%Y-%m-%d %H:%M KST')} "
        f"(ship_blockers_audit 자동 — {payload['summary']})"
    )
    new_text, count = _LAST_UPDATED_RE.subn(new_line, text, count=1)
    if count == 0:
        logger.warning("'최근 갱신' 라인 못 찾음 — 본문 무손상 유지")
        return False
    if new_text == text:
        logger.info("헤더 동일 (no diff) — skip write")
        return False
    try:
        ship_blockers_path.write_text(new_text, encoding="utf-8")
    except OSError as exc:
        logger.error("write failed: %s", exc)
        return False
    logger.info("SHIP_BLOCKERS.md 헤더 1줄 patch 완료")
    return True


# ── 엔트리포인트 ───────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    dry_run = "--dry-run" in argv

    memory_dir = Path(os.environ.get("MEMORY_DIR", _DEFAULT_MEMORY_DIR))
    ship_blockers_path = Path(
        os.environ.get("SHIP_BLOCKERS_PATH", _DEFAULT_SHIP_BLOCKERS)
    )
    status_json = Path(
        os.environ.get("SHIP_BLOCKERS_STATUS_JSON", _DEFAULT_STATUS_JSON)
    )

    try:
        payload = build_status_payload(memory_dir, ship_blockers_path)
    except Exception as exc:  # pragma: no cover - 방어
        logger.exception("build_status_payload 실패: %s", exc)
        try:
            from services.observability.alerts import emit_failure
            emit_failure(
                "ops_ship_blockers_daily",
                exc,
                context={"memory_dir": str(memory_dir)},
            )
        except Exception:
            pass
        return 1

    write_status_json(payload, status_json)
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if not dry_run:
        patch_ship_blockers_header(ship_blockers_path, payload)
    else:
        logger.info("--dry-run: SHIP_BLOCKERS.md patch 생략")

    try:
        from services.observability.alerts import record_success
        record_success("ops_ship_blockers_daily")
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
