"""마케팅 일일 디스패치 파이프 테스트.

검증 범위
=========
- content-bank 로더: 파싱 / 누락 graceful / 날짜 필터 / status 멱등성.
- §101 게이트: 금지어 캡션은 발행 차단 + blocked 기록 (어떤 채널로도 안 나감).
- 채널 분기: instagram → Slack 리마인더(자동발행 X) / threads·bluesky 토큰
  없으면 graceful skip (에러 아님).
- 토큰 있을 때 자동 발행 → status/published_channels 갱신 (멱등성).
- 플래그 OFF 시 main() 즉시 exit 0 (기존 prod 영향 0).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.marketing.content_bank import (  # noqa: E402
    STATUS_PUBLISHED,
    ContentItem,
    items_for_date,
    load_content_bank,
    save_content_bank,
)
from services.marketing import publishers  # noqa: E402
import scripts.nightly.marketing_daily_dispatch as dispatch  # noqa: E402


# ── content-bank loader ──────────────────────────────────────────────────────

def _write_bank(tmp_path: Path, items: list[dict]) -> Path:
    p = tmp_path / "content-bank.json"
    p.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    return p


def test_load_missing_bank_returns_empty(tmp_path):
    assert load_content_bank(tmp_path / "nope.json") == []


def test_load_malformed_json_returns_empty(tmp_path):
    p = tmp_path / "content-bank.json"
    p.write_text("{ not valid json", encoding="utf-8")
    assert load_content_bank(p) == []


def test_load_parses_items_and_drops_unknown_channel(tmp_path):
    p = _write_bank(tmp_path, [
        {
            "id": "a", "scheduled_date": "2026-05-27",
            "channel": ["instagram", "tiktok"],  # tiktok unknown → dropped
            "caption": "hi", "hashtags": ["#x"],
        },
    ])
    items = load_content_bank(p)
    assert len(items) == 1
    assert items[0].channel == ["instagram"]
    assert items[0].status == "pending"  # default


def test_items_for_date_filters_and_skips_published(tmp_path):
    items = [
        ContentItem(id="a", scheduled_date="2026-05-27", channel=["bluesky"], caption="x"),
        ContentItem(id="b", scheduled_date="2026-05-28", channel=["bluesky"], caption="y"),
        ContentItem(id="c", scheduled_date="2026-05-27", channel=["bluesky"], caption="z",
                    status=STATUS_PUBLISHED),
    ]
    due = items_for_date(items, "2026-05-27")
    assert [i.id for i in due] == ["a"]  # b wrong date, c already published


def test_full_caption_appends_ai_label_and_hashtags():
    it = ContentItem(id="a", scheduled_date="2026-05-27", channel=["instagram"],
                     caption="본문", hashtags=["#투자", "#퀀트"], ai_label=True)
    cap = it.full_caption()
    assert "본문" in cap
    assert "AI로 생성" in cap
    assert "#투자 #퀀트" in cap


def test_save_roundtrip(tmp_path):
    p = tmp_path / "content-bank.json"
    items = [ContentItem(id="a", scheduled_date="2026-05-27", channel=["bluesky"],
                         caption="x", status=STATUS_PUBLISHED)]
    assert save_content_bank(items, p) is True
    reloaded = load_content_bank(p)
    assert reloaded[0].status == STATUS_PUBLISHED


# ── §101 gate ────────────────────────────────────────────────────────────────

def test_forbidden_caption_blocks_dispatch(tmp_path):
    """캡션에 권유어가 있으면 발행 중단 + blocked 기록."""
    p = _write_bank(tmp_path, [
        {
            "id": "bad", "scheduled_date": "2026-05-27",
            "channel": ["instagram", "bluesky"],
            "caption": "지금 삼성전자 매수 추천합니다",  # 금지어
            "ai_label": False,
        },
    ])
    summary = dispatch.dispatch_once(today_iso="2026-05-27", bank_path=p)
    assert summary["blocked"], "forbidden caption must be blocked"
    assert summary["blocked"][0]["id"] == "bad"
    # 차단되면 어떤 채널로도 안 나감.
    assert summary["instagram_reminders"] == []
    assert summary["auto_published"] == []


# ── channel branching ────────────────────────────────────────────────────────

def test_instagram_produces_slack_reminder_not_autopost(tmp_path):
    p = _write_bank(tmp_path, [
        {
            "id": "ig", "scheduled_date": "2026-05-27",
            "channel": ["instagram"], "caption": "이번 주 포트폴리오 정리",
            "image_path": "docs/marketing/week1-cards/d1_cfo_card.png",
            "ai_label": False,
        },
    ])
    summary = dispatch.dispatch_once(today_iso="2026-05-27", bank_path=p)
    assert len(summary["instagram_reminders"]) == 1
    r = summary["instagram_reminders"][0]
    assert r["id"] == "ig"
    assert "포트폴리오" in r["caption"]
    assert summary["auto_published"] == []
    # 인스타는 published 마킹 안 함 (수동) → dirty 아님.
    assert summary["dirty"] is False


def test_bluesky_threads_graceful_skip_without_tokens(tmp_path, monkeypatch):
    """토큰 없으면 skip — 에러 아님, dirty 아님."""
    for var in ("BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD",
                "THREADS_USER_ID", "THREADS_ACCESS_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    p = _write_bank(tmp_path, [
        {
            "id": "auto", "scheduled_date": "2026-05-27",
            "channel": ["threads", "bluesky"], "caption": "정보 제공 도구입니다",
            "ai_label": False,
        },
    ])
    summary = dispatch.dispatch_once(today_iso="2026-05-27", bank_path=p)
    assert summary["auto_published"] == []
    assert summary["errors"] == []
    assert summary["dirty"] is False


def test_autopublish_success_marks_published(tmp_path, monkeypatch):
    """publisher 성공 → published_channels 갱신 + status=published (인스타 없음)."""
    monkeypatch.setattr(
        dispatch, "_AUTO_PUBLISHERS",
        {
            "threads": lambda *a, **k: publishers.PublishResult("threads", "ok", "tid"),
            "bluesky": lambda *a, **k: publishers.PublishResult("bluesky", "ok", "uri"),
        },
    )
    p = _write_bank(tmp_path, [
        {
            "id": "auto", "scheduled_date": "2026-05-27",
            "channel": ["threads", "bluesky"], "caption": "정보 제공 도구",
            "ai_label": False,
        },
    ])
    summary = dispatch.dispatch_once(today_iso="2026-05-27", bank_path=p)
    assert {p["channel"] for p in summary["auto_published"]} == {"threads", "bluesky"}
    assert summary["dirty"] is True
    reloaded = load_content_bank(p)
    assert reloaded[0].status == STATUS_PUBLISHED
    assert set(reloaded[0].published_channels) == {"threads", "bluesky"}


def test_autopublish_error_recorded_not_raised(tmp_path, monkeypatch):
    monkeypatch.setattr(
        dispatch, "_AUTO_PUBLISHERS",
        {"bluesky": lambda *a, **k: publishers.PublishResult("bluesky", "error", "boom")},
    )
    p = _write_bank(tmp_path, [
        {"id": "auto", "scheduled_date": "2026-05-27", "channel": ["bluesky"],
         "caption": "ok", "ai_label": False},
    ])
    summary = dispatch.dispatch_once(today_iso="2026-05-27", bank_path=p)
    assert summary["errors"] and summary["errors"][0]["detail"] == "boom"
    assert summary["auto_published"] == []
    # 발행 실패 → status 그대로.
    assert load_content_bank(p)[0].status != STATUS_PUBLISHED


def test_already_published_channel_not_redispatched(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        dispatch, "_AUTO_PUBLISHERS",
        {"bluesky": lambda *a, **k: (calls.append(1),
                                     publishers.PublishResult("bluesky", "ok", "u"))[1]},
    )
    p = _write_bank(tmp_path, [
        {"id": "auto", "scheduled_date": "2026-05-27", "channel": ["bluesky"],
         "caption": "ok", "ai_label": False, "published_channels": ["bluesky"]},
    ])
    summary = dispatch.dispatch_once(today_iso="2026-05-27", bank_path=p)
    assert calls == [], "already-published channel must not re-dispatch"
    assert summary["auto_published"] == []


# ── flag gating ──────────────────────────────────────────────────────────────

def test_main_noop_when_flag_off(monkeypatch):
    monkeypatch.delenv("PIVOX_MARKETING_AUTOPOST_ENABLED", raising=False)
    called = {"dispatch": False}
    monkeypatch.setattr(dispatch, "dispatch_once",
                        lambda *a, **k: called.__setitem__("dispatch", True))
    assert dispatch.main() == 0
    assert called["dispatch"] is False, "flag off must skip dispatch entirely"


def test_main_runs_when_flag_on(monkeypatch):
    monkeypatch.setenv("PIVOX_MARKETING_AUTOPOST_ENABLED", "true")
    monkeypatch.setattr(dispatch, "dispatch_once", lambda *a, **k: {
        "date": "2026-05-27", "due": 0, "instagram_reminders": [],
        "auto_published": [], "blocked": [], "errors": [], "dirty": False,
    })
    monkeypatch.setattr(dispatch, "post_slack", lambda text: True)
    assert dispatch.main() == 0


# ── publishers no-op contract ────────────────────────────────────────────────

def test_publish_bluesky_skips_without_creds(monkeypatch):
    monkeypatch.delenv("BLUESKY_HANDLE", raising=False)
    monkeypatch.delenv("BLUESKY_APP_PASSWORD", raising=False)
    r = publishers.publish_bluesky("hi")
    assert r.skipped and r.channel == "bluesky"


def test_publish_threads_skips_without_creds(monkeypatch):
    monkeypatch.delenv("THREADS_USER_ID", raising=False)
    monkeypatch.delenv("THREADS_ACCESS_TOKEN", raising=False)
    r = publishers.publish_threads("hi")
    assert r.skipped and r.channel == "threads"


def test_resolve_image_abspath(tmp_path):
    # Existing repo image resolves; bogus path returns None.
    assert publishers.resolve_image_abspath(
        "docs/marketing/week1-cards/d1_cfo_card.png") is not None
    assert publishers.resolve_image_abspath("docs/marketing/does-not-exist.png") is None
    assert publishers.resolve_image_abspath(None) is None


# ── shipped content-bank.json sanity ─────────────────────────────────────────

def test_shipped_content_bank_loads_and_is_legal():
    """저장소에 커밋된 content-bank.json 의 모든 캡션은 §101 게이트 통과해야."""
    from services.legal.forbidden_terms import contains_forbidden_term
    items = load_content_bank()  # default DEFAULT_BANK_PATH
    for it in items:
        hit = contains_forbidden_term(it.full_caption())
        assert hit is None, f"shipped item {it.id!r} contains forbidden term {hit!r}"
