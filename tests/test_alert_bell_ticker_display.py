"""Regression: ``services.alert`` bell-notification wrappers must apply
the ``name (ticker)`` rule to their titles.

Memory rule ``feedback_ticker_display`` (CEO directive, repeated 3+ times):
- Bell alerts (52w high/low, watchlist event) render the title as
  ``"{name} ({ticker}) reached 52-week high"`` when the resolver hits,
  and ``"{ticker} reached 52-week high"`` (single copy) on miss — never
  ``"X (X)"``.

Background: prior to 2026-05-13 the wrappers fell back to ``ticker`` only
when the caller didn't pre-resolve the name. This bypassed the central
``_label_for_ticker`` resolver. The fix routes the fallback through that
resolver, so even callers that forget to pass ``name=`` still get the
preferred surface format.

This test pins the resulting title shape on both branches (resolved /
unresolved) for each wrapper that takes a ticker.
"""
from __future__ import annotations

import re
from unittest.mock import patch


_DUP_PAREN = re.compile(r"(\S+)\s*\(\1\)")


def _captured_create_alert():
    """Patch services.alert.create_alert to swallow DB writes and let
    each test inspect the title= it was called with."""
    return patch("services.alert.create_alert")


class TestAlert52wHighTitle:
    def test_caller_passed_name_renders_name_with_ticker(self, app):
        from services import alert
        with _captured_create_alert() as ca:
            alert.alert_52w_high(1, "005930.KS", name="삼성전자")
        title = ca.call_args.kwargs["title"]
        assert "삼성전자 (005930.KS)" in title, title
        assert not _DUP_PAREN.search(title), title

    def test_caller_omitted_name_resolver_hits_renders_name_with_ticker(
        self, app,
    ):
        from services import alert
        with _captured_create_alert() as ca, patch(
            "services.name_resolver.resolve_stock_name_with_db",
            return_value="삼성전자",
        ):
            alert.alert_52w_high(1, "005930.KS")
        title = ca.call_args.kwargs["title"]
        assert "삼성전자 (005930.KS)" in title, title
        assert not _DUP_PAREN.search(title), title

    def test_caller_omitted_name_resolver_misses_renders_ticker_only(
        self, app,
    ):
        from services import alert
        with _captured_create_alert() as ca, patch(
            "services.name_resolver.resolve_stock_name_with_db",
            return_value=None,
        ):
            alert.alert_52w_high(1, "ZZZZ")
        title = ca.call_args.kwargs["title"]
        assert "ZZZZ" in title, title
        assert not _DUP_PAREN.search(title), title

    def test_caller_passed_name_equal_to_ticker_collapses(self, app):
        """Upstream fetcher's degenerate name=ticker echo must NOT produce
        ``"X (X)"``."""
        from services import alert
        with _captured_create_alert() as ca:
            alert.alert_52w_high(1, "AAPL", name="AAPL")
        title = ca.call_args.kwargs["title"]
        assert not _DUP_PAREN.search(title), title


class TestAlert52wLowTitle:
    def test_resolved_renders_name_with_ticker(self, app):
        from services import alert
        with _captured_create_alert() as ca:
            alert.alert_52w_low(1, "AAPL", name="Apple Inc.")
        title = ca.call_args.kwargs["title"]
        assert "Apple Inc. (AAPL)" in title, title
        assert not _DUP_PAREN.search(title), title

    def test_unresolved_no_dup(self, app):
        from services import alert
        with _captured_create_alert() as ca, patch(
            "services.name_resolver.resolve_stock_name_with_db",
            return_value=None,
        ):
            alert.alert_52w_low(1, "ZZZZ")
        title = ca.call_args.kwargs["title"]
        assert "ZZZZ" in title, title
        assert not _DUP_PAREN.search(title), title


class TestAlertWatchlistEventTitle:
    def test_resolved_renders_name_with_ticker(self, app):
        from services import alert
        with _captured_create_alert() as ca:
            alert.alert_watchlist_event(1, "AAPL", name="Apple Inc.")
        title = ca.call_args.kwargs["title"]
        assert "Apple Inc. (AAPL)" in title, title
        assert not _DUP_PAREN.search(title), title

    def test_unresolved_no_dup(self, app):
        from services import alert
        with _captured_create_alert() as ca, patch(
            "services.name_resolver.resolve_stock_name_with_db",
            return_value=None,
        ):
            alert.alert_watchlist_event(1, "ZZZZ")
        title = ca.call_args.kwargs["title"]
        assert "ZZZZ" in title, title
        assert not _DUP_PAREN.search(title), title
