#!/usr/bin/env python3
"""마케팅 일일 디스패치 — content-bank → §101 게이트 → Slack + (토큰시)자동발행.

흐름
====
1. ``PIVOX_MARKETING_AUTOPOST_ENABLED`` 플래그 확인 (기본 false → 즉시 exit 0).
2. 오늘(KST) 날짜에 해당하는 content-bank 항목 조회 (status!=published).
3. 각 항목:
   a. ``contains_forbidden_term(caption)`` §101 게이트 → 걸리면 발행 **중단**
      + Slack RED 경고. (자본시장법 §49 투자권유 차단)
   b. 채널별 분기:
      - instagram → 자동발행 불가(페북 페이지 없음) → Slack 리마인더 전송.
        CEO 가 캡션+해시태그+이미지경로 보고 수동 1탭.
      - threads / bluesky → 토큰 있으면 공식 API 자동 발행, 없으면 graceful skip.
   c. 발행 성공 채널 → content-bank ``status``/``published_channels`` 갱신.
4. Slack 요약 로그.

비용 0원
========
- LLM 호출 0건 (캡션은 미리 작성된 파일에서 읽음).
- Threads/Bluesky 공식 무료 API + Slack webhook 무료 tier.

환경변수
========
PIVOX_MARKETING_AUTOPOST_ENABLED  — "1"/"true" 일 때만 동작 (기본 off).
SLACK_WEBHOOK_URL                 — 없으면 stdout fallback.
BLUESKY_HANDLE / BLUESKY_APP_PASSWORD     — 없으면 Bluesky no-op.
THREADS_USER_ID / THREADS_ACCESS_TOKEN    — 없으면 Threads no-op.

실행
====
python scripts/nightly/marketing_daily_dispatch.py
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

# Repo root on sys.path (mirror sibling nightly scripts).
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.legal.forbidden_terms import contains_forbidden_term  # noqa: E402
from services.marketing.content_bank import (  # noqa: E402
    STATUS_PUBLISHED,
    items_for_date,
    load_content_bank,
    save_content_bank,
)
from services.marketing.publishers import (  # noqa: E402
    publish_bluesky,
    publish_threads,
    resolve_image_abspath,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

_SSL_CTX = ssl.create_default_context()
_KST = timezone(timedelta(hours=9))

# 토큰 없는 채널 → 이 함수로 매핑되지 않음 (instagram 은 항상 Slack 리마인더).
_AUTO_PUBLISHERS = {
    "threads": publish_threads,
    "bluesky": publish_bluesky,
}


def _flag_enabled() -> bool:
    val = os.environ.get("PIVOX_MARKETING_AUTOPOST_ENABLED", "").strip().lower()
    return val in ("1", "true", "yes", "on")


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


def dispatch_once(today_iso: str | None = None, bank_path: Path | str | None = None) -> dict:
    """Run one dispatch pass. Returns a summary dict (테스트 검증용).

    순수 로직 — Slack 전송과 분리해 테스트가 결과를 introspect 한다.
    """
    items = load_content_bank(bank_path)
    today = today_iso or datetime.now(_KST).date().isoformat()
    due = items_for_date(items, today)

    summary = {
        "date": today,
        "due": len(due),
        "instagram_reminders": [],   # list[dict]
        "auto_published": [],        # list[dict]
        "blocked": [],               # §101 위반 list[dict]
        "errors": [],                # list[dict]
        "dirty": False,              # content-bank 갱신 필요 여부
    }

    for item in due:
        # ── (a) §101 게이트 ──────────────────────────────────────────────
        hit = contains_forbidden_term(item.full_caption())
        if hit is not None:
            summary["blocked"].append({"id": item.id, "term": hit})
            continue  # 발행 중단 — 이 항목은 어떤 채널로도 안 나감

        caption = item.full_caption()
        published_now: list[str] = []

        for channel in item.channel:
            if channel in item.published_channels:
                continue  # 이미 발행됨 (부분 재시도 멱등성)

            if channel == "instagram":
                # 자동발행 불가 → Slack 리마인더 (CEO 수동 1탭).
                summary["instagram_reminders"].append({
                    "id": item.id,
                    "caption": caption,
                    "image_path": item.image_path,
                    "image_abspath": resolve_image_abspath(item.image_path),
                })
                # 인스타는 "발행 완료"로 마킹하지 않음 — 수동이므로 매일 리마인더.
                continue

            publisher = _AUTO_PUBLISHERS.get(channel)
            if publisher is None:
                continue
            result = publisher(caption, item.image_path)
            if result.ok:
                published_now.append(channel)
                summary["auto_published"].append({"id": item.id, "channel": channel})
            elif result.status == "error":
                summary["errors"].append(
                    {"id": item.id, "channel": channel, "detail": result.detail},
                )
            # skipped (토큰 없음) → 조용히 통과 (정상)

        if published_now:
            item.published_channels.extend(published_now)
            summary["dirty"] = True
            # 모든 자동 채널이 발행됐고 인스타가 없으면 전체 published 마킹.
            auto_channels = [c for c in item.channel if c != "instagram"]
            if auto_channels and all(c in item.published_channels for c in auto_channels):
                if "instagram" not in item.channel:
                    item.status = STATUS_PUBLISHED

    if summary["dirty"]:
        save_content_bank(items, bank_path)

    return summary


def _format_summary(s: dict) -> str:
    lines = [f"📣 *PivoxQuant 마케팅 일일 디스패치* ({s['date']})"]
    lines.append(f"• 오늘 예정 항목: {s['due']}")

    if s["blocked"]:
        lines.append("🟥 *§101 게이트 차단* (발행 중단 — 캡션 수정 필요):")
        for b in s["blocked"]:
            lines.append(f"   - {b['id']}: 금지어 '{b['term']}'")

    if s["instagram_reminders"]:
        lines.append("📸 *오늘 인스타 포스트* (수동 1탭):")
        for r in s["instagram_reminders"]:
            img = r.get("image_abspath") or r.get("image_path") or "(이미지 없음)"
            lines.append(f"   ── {r['id']} ──\n{r['caption']}\n   🖼 {img}")

    if s["auto_published"]:
        chans = ", ".join(f"{p['id']}:{p['channel']}" for p in s["auto_published"])
        lines.append(f"✅ 자동 발행 완료: {chans}")

    if s["errors"]:
        lines.append("⚠️ 자동 발행 실패:")
        for e in s["errors"]:
            lines.append(f"   - {e['id']} ({e['channel']}): {e['detail'][:200]}")

    if s["due"] == 0:
        lines.append("(오늘 예정된 콘텐츠 없음)")

    return "\n".join(lines)


def main() -> int:
    if not _flag_enabled():
        logger.info(
            "[marketing] PIVOX_MARKETING_AUTOPOST_ENABLED off — skip dispatch",
        )
        return 0
    try:
        summary = dispatch_once()
    except Exception as exc:  # noqa: BLE001
        logger.exception("[marketing] daily dispatch failed")
        post_slack(f"⚠️ PivoxQuant 마케팅 디스패치 실패: {exc}")
        return 1

    # 차단/리마인더/발행/실패 중 하나라도 있으면 Slack 전송.
    if summary["blocked"] or summary["instagram_reminders"] or \
            summary["auto_published"] or summary["errors"]:
        post_slack(_format_summary(summary))
    logger.info("[marketing] dispatch: %s", json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
