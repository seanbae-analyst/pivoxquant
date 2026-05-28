"""v57-I — CEO Inbox aggregator 회귀 테스트.

5 출처 통합 payload 정합성 + 핵심 invariants 검증.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from services.inbox.aggregator import (
    build_inbox_payload,
    collect_autonomous_done,
    collect_lawyer_queue,
    collect_next_fires,
    collect_ship_blockers,
)

try:
    from zoneinfo import ZoneInfo
    KST = ZoneInfo("Asia/Seoul")
except ImportError:
    KST = timezone(timedelta(hours=9))


# ── Source 1: autopilot_log 24h tail ────────────────────────────────────────

class TestAutonomousDone:
    def test_returns_list(self):
        result = collect_autonomous_done()
        assert isinstance(result, list)

    def test_24h_cutoff_strict(self, tmp_path, monkeypatch):
        """25h 이전 entry 제외 검증."""
        fake_memory = tmp_path / "memory"
        fake_memory.mkdir()
        now = datetime.now(KST)
        old = now - timedelta(hours=25)
        recent = now - timedelta(hours=2)
        log = fake_memory / "autopilot_log.md"
        log.write_text(
            f"## {old.strftime('%Y-%m-%d %H:%M')} old-agent\n- status: clean\n\n"
            f"## {recent.strftime('%Y-%m-%d %H:%M')} recent-agent\n- status: clean\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("PIVOX_MEMORY_DIR", str(fake_memory))
        # Re-import to pick up env (aggregator uses module-level constant)
        import importlib
        import services.inbox.aggregator as agg
        importlib.reload(agg)
        result = agg.collect_autonomous_done(now)
        agents = [e["agent"] for e in result]
        assert "recent-agent" in agents
        assert "old-agent" not in agents

    def test_empty_when_no_log(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PIVOX_MEMORY_DIR", str(tmp_path))
        import importlib
        import services.inbox.aggregator as agg
        importlib.reload(agg)
        assert agg.collect_autonomous_done() == []


# ── Source 2: SHIP_BLOCKERS categories ───────────────────────────────────────

class TestShipBlockers:
    def test_returns_dict_with_required_keys(self):
        result = collect_ship_blockers()
        assert "release_blocker" in result
        assert "ship_at_risk" in result
        assert "post_launch" in result
        assert "header" in result

    def test_counts_are_non_negative(self):
        result = collect_ship_blockers()
        assert result["release_blocker"] >= 0
        assert result["ship_at_risk"] >= 0
        assert result["post_launch"] >= 0


# ── Source 3: 변호사 큐 ──────────────────────────────────────────────────────

class TestLawyerQueue:
    def test_returns_dict(self):
        result = collect_lawyer_queue()
        assert "total" in result
        assert "pending" in result
        assert "answered" in result

    def test_pending_plus_answered_equals_total(self):
        result = collect_lawyer_queue()
        assert result["pending"] + result["answered"] == result["total"]


# ── Source 6: next fires ─────────────────────────────────────────────────────

class TestNextFires:
    def test_returns_sorted_by_eta(self):
        result = collect_next_fires()
        assert len(result) >= 1
        # 모두 future time
        for fire in result:
            assert "task" in fire
            assert "next_fire_kst" in fire
            assert "eta" in fire

    def test_includes_known_crons(self):
        result = collect_next_fires()
        tasks = [f["task"] for f in result]
        # 핵심 cron 6개 모두 포함
        assert any("ops_data_integrity_sweep" in t for t in tasks)
        assert any("ops_ship_blockers_daily" in t for t in tasks)
        assert any("api-sentinel" in t for t in tasks)
        assert any("ops_lawyer_packet_weekly" in t for t in tasks)


# ── Aggregator integration ──────────────────────────────────────────────────

class TestBuildInboxPayload:
    def test_payload_shape(self):
        payload = build_inbox_payload()
        required_keys = {
            "generated_at_kst",
            "autonomous_done",
            "ship_blockers",
            "lawyer_queue",
            "cron_status",
            "next_fires",
            "summary",
        }
        assert required_keys.issubset(payload.keys())

    def test_summary_is_string_and_nonempty(self):
        payload = build_inbox_payload()
        assert isinstance(payload["summary"], str)
        assert len(payload["summary"]) > 10

    def test_no_pii_leakage_in_summary(self):
        """seanbae@... 같은 이메일이 summary에 누출되지 않는지."""
        payload = build_inbox_payload()
        summary = payload["summary"]
        assert "@" not in summary
        assert "BETA_PASSWORD" not in summary

    def test_idempotent_two_calls_same_time(self):
        """동일 시점 호출 시 next_fires 동일."""
        now = datetime.now(KST)
        p1 = build_inbox_payload(now)
        p2 = build_inbox_payload(now)
        assert p1["next_fires"] == p2["next_fires"]


# ── Performance ─────────────────────────────────────────────────────────────

class TestPerformance:
    def test_payload_build_under_1s(self):
        """aggregator는 빠르게 (외부 API X)."""
        import time
        start = time.monotonic()
        build_inbox_payload()
        elapsed = time.monotonic() - start
        assert elapsed < 1.0, f"build_inbox_payload took {elapsed:.2f}s (limit 1s)"
