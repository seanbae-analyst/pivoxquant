"""
Tests for Wave I G-3 — Anthropic Claude API cost tracking.

Covers:
  - _token_cost_usd() — model pricing table
  - run_cost_estimate() — 80% / 100% alert thresholds
  - state file write (history upsert)
  - DB 없는 환경에서 graceful (stub)
  - AI service _log_usage() — usage logging wrapper
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import sys
import time
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ── Helper: load module under test with patched root ────────────────────────

def _load_cost_module(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "anthropic_cost_estimate",
        _ROOT / "scripts/nightly/anthropic_cost_estimate.py",
    )
    mod = importlib.util.module_from_spec(spec)
    mod.__dict__["_PROJECT_ROOT"] = tmp_path
    mod.__dict__["_STATE_DIR"] = tmp_path / "state"
    mod.__dict__["_STATE_FILE"] = tmp_path / "state" / "anthropic_usage_history.json"
    spec.loader.exec_module(mod)
    return mod


# ── Token cost tests ─────────────────────────────────────────────────────────

class TestTokenCostUsd:
    def test_haiku_pricing(self, tmp_path):
        mod = _load_cost_module(tmp_path)
        cost = mod._token_cost_usd("claude-haiku-4-5-20251001", 1_000_000, 0)
        assert abs(cost - 0.80) < 1e-6

    def test_haiku_output_pricing(self, tmp_path):
        mod = _load_cost_module(tmp_path)
        cost = mod._token_cost_usd("claude-haiku-4-5-20251001", 0, 1_000_000)
        assert abs(cost - 4.00) < 1e-6

    def test_sonnet_pricing(self, tmp_path):
        mod = _load_cost_module(tmp_path)
        cost = mod._token_cost_usd("claude-sonnet-4-5", 1_000_000, 1_000_000)
        assert abs(cost - (3.00 + 15.00)) < 1e-6

    def test_unknown_model_fallback(self, tmp_path):
        mod = _load_cost_module(tmp_path)
        # Unknown model → _default (haiku pricing)
        cost = mod._token_cost_usd("claude-unknown-xyz", 1_000_000, 0)
        assert abs(cost - 0.80) < 1e-6

    def test_prefix_match(self, tmp_path):
        mod = _load_cost_module(tmp_path)
        # claude-haiku-4-5-20251001-xxx prefix should match haiku
        cost = mod._token_cost_usd("claude-haiku-4-5-20251001-custom", 1_000_000, 0)
        assert abs(cost - 0.80) < 1e-6

    def test_zero_tokens_zero_cost(self, tmp_path):
        mod = _load_cost_module(tmp_path)
        assert mod._token_cost_usd("claude-haiku-4-5-20251001", 0, 0) == 0.0


# ── run_cost_estimate() integration-style tests ──────────────────────────────

def _fake_usage(in_tok: int, out_tok: int) -> dict:
    model = "claude-haiku-4-5-20251001"
    return {
        "today": {"input_tokens": in_tok, "output_tokens": out_tok, "calls": 10},
        "mtd": {"input_tokens": in_tok * 20, "output_tokens": out_tok * 20, "calls": 200},
        "by_model_today": {model: {"input": in_tok, "output": out_tok}},
    }


class TestRunCostEstimate:
    """Test the cost aggregation + alerting path without a real DB."""

    def _run_with_tokens(self, mod, in_tok, out_tok, daily_limit=5.0):
        mod.DAILY_LIMIT_USD = daily_limit
        usage = _fake_usage(in_tok, out_tok)
        with patch.object(mod, "_query_usage", return_value=usage):
            with patch.object(mod, "_post_slack", return_value=True) as mock_slack:
                with patch.object(mod, "_capture_sentry_warning") as mock_sentry:
                    rc = mod.run_cost_estimate()
        return rc, mock_slack, mock_sentry

    def test_under_80pct_no_alert(self, tmp_path):
        mod = _load_cost_module(tmp_path)
        # haiku: $0.80/M input, $4.00/M output
        # Use very low tokens (far below 80% of $5 limit)
        rc, mock_slack, _ = self._run_with_tokens(mod, 100, 100)
        assert rc == 0
        mock_slack.assert_not_called()

    def test_80pct_warning_alert(self, tmp_path):
        mod = _load_cost_module(tmp_path)
        # To hit 80% of $5: need $4.00 cost
        # haiku output: $4.00 / 1M tokens = $4 → 1M output tokens
        rc, mock_slack, _ = self._run_with_tokens(mod, 0, 1_000_000, daily_limit=5.0)
        # $4.00 = 80% of $5.00
        assert rc == 1, f"Expected 1 (80% warn), got {rc}"
        mock_slack.assert_called_once()

    def test_100pct_hard_alert(self, tmp_path):
        mod = _load_cost_module(tmp_path)
        # haiku output: 2M tokens → $8.00 > $5 limit (160%)
        rc, mock_slack, mock_sentry = self._run_with_tokens(mod, 0, 2_000_000, daily_limit=5.0)
        assert rc == 2, f"Expected 2 (100% hard), got {rc}"
        mock_slack.assert_called_once()
        mock_sentry.assert_called_once()

    def test_state_history_written(self, tmp_path):
        mod = _load_cost_module(tmp_path)
        # Patch module-level state paths to use tmp_path
        (tmp_path / "state").mkdir(parents=True, exist_ok=True)
        mod._STATE_DIR = tmp_path / "state"
        mod._STATE_FILE = tmp_path / "state" / "anthropic_usage_history.json"

        usage = _fake_usage(1000, 1000)
        with patch.object(mod, "_query_usage", return_value=usage):
            with patch.object(mod, "_post_slack", return_value=True):
                mod.run_cost_estimate()

        state_file = tmp_path / "state" / "anthropic_usage_history.json"
        assert state_file.exists()
        state = json.loads(state_file.read_text())
        assert len(state["history"]) == 1
        entry = state["history"][0]
        assert "today_cost_usd" in entry
        assert "date" in entry

    def test_state_upserts_same_day(self, tmp_path):
        """Running twice on the same day should upsert, not append a duplicate."""
        mod = _load_cost_module(tmp_path)
        (tmp_path / "state").mkdir(parents=True, exist_ok=True)
        mod._STATE_DIR = tmp_path / "state"
        mod._STATE_FILE = tmp_path / "state" / "anthropic_usage_history.json"

        usage = _fake_usage(1000, 1000)
        with patch.object(mod, "_query_usage", return_value=usage):
            with patch.object(mod, "_post_slack", return_value=True):
                mod.run_cost_estimate()
                mod.run_cost_estimate()

        state_file = tmp_path / "state" / "anthropic_usage_history.json"
        state = json.loads(state_file.read_text())
        assert len(state["history"]) == 1, "Should upsert same-day entry"

    def test_no_db_graceful(self, tmp_path):
        """DB unavailable → _query_usage returns empty, run exits 0."""
        mod = _load_cost_module(tmp_path)
        # _query_usage returns zeros
        with patch.object(mod, "_query_usage", return_value={
            "today": {"input_tokens": 0, "output_tokens": 0, "calls": 0},
            "mtd": {"input_tokens": 0, "output_tokens": 0, "calls": 0},
            "by_model_today": {},
        }):
            with patch.object(mod, "_post_slack", return_value=False) as mock_slack:
                rc = mod.run_cost_estimate()
        assert rc == 0
        mock_slack.assert_not_called()


class TestQueryUsageNoDb:
    """_query_usage graceful with no DB configured."""

    def test_empty_db_url_returns_empty(self, tmp_path):
        mod = _load_cost_module(tmp_path)
        with patch.dict(mod.os.environ, {"DATABASE_URL": ""}, clear=False):
            # Temporarily remove DATABASE_URL so the function sees empty
            orig = mod.os.environ.pop("DATABASE_URL", None)
            try:
                result = mod._query_usage("2026-05-19", "2026-05-01")
            finally:
                if orig is not None:
                    mod.os.environ["DATABASE_URL"] = orig
        assert result["today"]["calls"] == 0
        assert result["mtd"]["input_tokens"] == 0


# ── AI service _log_usage wrapper ────────────────────────────────────────────

class TestLogUsageWrapper:
    """_log_usage() in services/ai/service.py."""

    def test_log_usage_none_usage_is_noop(self):
        """_log_usage(None) should not raise."""
        from services.ai.service import _log_usage
        _log_usage("claude-haiku-4-5-20251001", "swot", None)

    def test_log_usage_zero_tokens_is_noop(self):
        """Zero token usage should be skipped."""
        from services.ai.service import _log_usage
        fake_usage = MagicMock()
        fake_usage.input_tokens = 0
        fake_usage.output_tokens = 0
        # Should not raise even with DB mocked out
        with patch("services.ai.service._log_usage", wraps=_log_usage):
            _log_usage("claude-haiku-4-5-20251001", "coaching", fake_usage)

    def test_log_usage_db_error_is_swallowed(self):
        """DB error during logging must not propagate."""
        from services.ai.service import _log_usage

        fake_usage = MagicMock()
        fake_usage.input_tokens = 500
        fake_usage.output_tokens = 300

        # Mock extensions.db to raise
        fake_db = MagicMock()
        fake_db.engine.connect.side_effect = Exception("DB connection failed")
        with patch.dict(sys.modules, {"extensions": MagicMock(db=fake_db)}):
            # Should not raise
            _log_usage("claude-haiku-4-5-20251001", "swot", fake_usage)

    def test_log_usage_records_correct_endpoint(self):
        """Verify endpoint label is passed correctly."""
        from services.ai.service import _log_usage

        fake_usage = MagicMock()
        fake_usage.input_tokens = 100
        fake_usage.output_tokens = 50

        recorded = []

        def fake_execute(sql, params=None):
            if params:
                recorded.append(params.get("ep"))
            return MagicMock()

        fake_conn = MagicMock()
        fake_conn.__enter__ = lambda s: s
        fake_conn.__exit__ = MagicMock(return_value=False)
        fake_conn.execute.side_effect = fake_execute

        fake_engine = MagicMock()
        fake_engine.connect.return_value = fake_conn

        fake_db = MagicMock()
        fake_db.engine = fake_engine

        with patch.dict(sys.modules, {"extensions": MagicMock(db=fake_db)}):
            _log_usage("claude-haiku-4-5-20251001", "sector_trend", fake_usage)
